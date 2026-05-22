#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深圳学位房规划助手 - 后端API服务
FastAPI + Coze Chat API + 深圳政府开放平台数据
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
import json
import urllib.request
import urllib.parse
import ssl
import time
import os
from datetime import datetime, timedelta

# ============ 配置（从环境变量读取） ============
COZE_API_TOKEN = os.environ.get("COZE_API_TOKEN", "")
COZE_BOT_ID = os.environ.get("COZE_BOT_ID", "")
COZE_BASE_URL = "https://api.coze.cn"
COZE_TIMEOUT = 120
COZE_POLL_INTERVAL = 3

SZ_OPEN_APPKEY = os.environ.get("SZ_OPEN_APPKEY", "")
SZ_OPEN_API = "https://opendata.sz.gov.cn/api/29200_01903513/1/service.xhtml"

app = FastAPI(
    title="深圳学位房规划助手 API",
    description="学位房规划助手Web后端，对接Coze智能体+政府成交数据",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ 请求/响应模型 ============

class ChatRequest(BaseModel):
    message: str
    mode: str = "quick"
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    success: bool
    response: str
    mode: str
    timestamp: str
    conversation_id: Optional[str] = None

class DealRecord(BaseModel):
    date: str
    zone: str
    usage: str
    num: int
    area: float

class DealResponse(BaseModel):
    success: bool
    zone: str
    days: int
    data: List[DealRecord]
    timestamp: str

# ============ 深圳政府开放平台 API ============

def fetch_sz_deals(zone: str = None, days: int = 30, usage: str = "住宅") -> list:
    """拉取深圳二手房成交汇总数据"""
    records = []
    page = 1
    # 估算总页数（91848条/100条每页），从最新数据开始
    # 最新数据在最后页，倒序拉取
    total_pages = 920  # 略大于实际页数
    
    # 先拉最后一页确定最新日期
    url = f"{SZ_OPEN_API}?appKey={SZ_OPEN_APPKEY}&page={total_pages}&rows=100"
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url)
    
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            all_data = result.get("data", [])
            
            if not all_data:
                # 尝试前一页
                total_pages = 919
                url = f"{SZ_OPEN_API}?appKey={SZ_OPEN_APPKEY}&page={total_pages}&rows=100"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, context=ctx, timeout=30) as resp2:
                    result = json.loads(resp2.read().decode("utf-8"))
                    all_data = result.get("data", [])
            
            # 找到最新日期
            if all_data:
                latest_date = max(r["TJ_DATE"] for r in all_data)
                cutoff = (datetime.strptime(latest_date, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
                
                # 需要向前翻页获取足够数据
                collected = []
                for p in range(total_pages, max(total_pages - days // 2, 1), -1):
                    if p != total_pages:
                        url = f"{SZ_OPEN_API}?appKey={SZ_OPEN_APPKEY}&page={p}&rows=100"
                        req = urllib.request.Request(url)
                        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp_p:
                            result = json.loads(resp_p.read().decode("utf-8"))
                            page_data = result.get("data", [])
                    else:
                        page_data = all_data
                    
                    for r in page_data:
                        if r["TJ_DATE"] >= cutoff:
                            if zone and r["ZONE"] != zone:
                                continue
                            if r["HOUSE_USAGE2"] != usage:
                                continue
                            collected.append(DealRecord(
                                date=r["TJ_DATE"],
                                zone=r["ZONE"],
                                usage=r["HOUSE_USAGE2"],
                                num=r["CJ_NUM"],
                                area=r["CJ_AREA"]
                            ))
                    
                    # 如果最早数据已经早于cutoff，停止翻页
                    if page_data and page_data[0]["TJ_DATE"] < cutoff:
                        break
                
                records = collected
    except Exception as e:
        raise Exception(f"政府开放平台请求失败: {str(e)}")
    
    return records

# ============ Coze API ============

def _coze_request(url: str, method: str = "GET", data: dict = None) -> dict:
    headers = {
        "Authorization": f"Bearer {COZE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))

def coze_chat(message: str, mode: str = "quick", conversation_id: str = None) -> dict:
    full_message = f"出方案：{message}" if mode == "plan" else message

    payload = {
        "bot_id": COZE_BOT_ID,
        "user_id": "web_user",
        "stream": False,
        "auto_save_history": True,
        "additional_messages": [{
            "role": "user",
            "content": full_message,
            "content_type": "text"
        }]
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id

    result = _coze_request(f"{COZE_BASE_URL}/v3/chat", method="POST", data=payload)
    if result.get("code") != 0:
        raise Exception(f"Coze chat创建失败: {result.get('msg', '未知错误')}")

    chat_id = result["data"]["id"]
    conv_id = result["data"]["conversation_id"]

    start_time = time.time()
    while time.time() - start_time < COZE_TIMEOUT:
        time.sleep(COZE_POLL_INTERVAL)
        status_url = f"{COZE_BASE_URL}/v3/chat/retrieve?chat_id={chat_id}&conversation_id={conv_id}"
        status_result = _coze_request(status_url)
        status = status_result.get("data", {}).get("status")

        if status == "completed":
            msg_url = f"{COZE_BASE_URL}/v3/chat/message/list?chat_id={chat_id}&conversation_id={conv_id}"
            msg_result = _coze_request(msg_url)
            answer = ""
            for msg in msg_result.get("data", []):
                if msg.get("role") == "assistant" and msg.get("type") == "answer":
                    answer = msg.get("content", "")
                    break
            if not answer:
                for msg in msg_result.get("data", []):
                    if msg.get("role") == "assistant":
                        answer = msg.get("content", "")
                        break
            return {"response": answer, "conversation_id": conv_id}

        elif status == "failed":
            err = status_result.get("data", {}).get("last_error", {})
            raise Exception(f"Coze chat失败: {err}")

    raise Exception("Coze chat超时")

# ============ API 路由 ============

@app.get("/xuequ/health")
async def health_check():
    return {"status": "healthy", "service": "深圳学位房规划助手", "version": "3.0.0", "timestamp": datetime.now().isoformat()}

@app.post("/xuequ/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = coze_chat(message=request.message, mode=request.mode, conversation_id=request.conversation_id)
        return ChatResponse(success=True, response=result["response"], mode=request.mode, timestamp=datetime.now().isoformat(), conversation_id=result["conversation_id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"智能体调用失败: {str(e)}")

@app.get("/xuequ/deals", response_model=DealResponse)
async def get_deals(zone: str = None, days: int = 30, usage: str = "住宅"):
    """获取深圳二手房成交汇总数据（来自政府开放平台）"""
    if not SZ_OPEN_APPKEY:
        raise HTTPException(status_code=500, detail="未配置SZ_OPEN_APPKEY环境变量")
    try:
        records = fetch_sz_deals(zone=zone, days=days, usage=usage)
        return DealResponse(
            success=True,
            zone=zone or "全部",
            days=days,
            data=records,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"成交数据获取失败: {str(e)}")

@app.get("/")
async def root():
    return {
        "service": "深圳学位房规划助手 API",
        "version": "3.0.0",
        "docs": "/docs",
        "health": "/xuequ/health",
        "chat": "POST /xuequ/chat",
        "deals": "GET /xuequ/deals?zone=福田&days=30&usage=住宅"
    }

if __name__ == "__main__":
    print("=" * 50)
    print("🏠 深圳学位房规划助手 API v3.0 服务启动中...")
    print("⚠️ 请确保已设置环境变量: COZE_API_TOKEN, COZE_BOT_ID, SZ_OPEN_APPKEY")
    print("=" * 50)
    uvicorn.run("main:app", host="0.0.0.0", port=8890, reload=False, log_level="info")
