#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
深圳学位房规划助手 - 后端API服务
FastAPI + Coze Chat API
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn
import json
import urllib.request
import ssl
import time
import os
from datetime import datetime

# ============ Coze API 配置（从环境变量读取，部署时设置） ============
COZE_API_TOKEN = os.environ.get("COZE_API_TOKEN", "")
COZE_BOT_ID = os.environ.get("COZE_BOT_ID", "")
COZE_BASE_URL = "https://api.coze.cn"
COZE_TIMEOUT = 120
COZE_POLL_INTERVAL = 3

app = FastAPI(
    title="深圳学位房规划助手 API",
    description="学位房规划助手Web后端，对接Coze智能体",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/xuequ/health")
async def health_check():
    return {"status": "healthy", "service": "深圳学位房规划助手", "version": "2.0.0", "timestamp": datetime.now().isoformat()}

@app.post("/xuequ/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        result = coze_chat(message=request.message, mode=request.mode, conversation_id=request.conversation_id)
        return ChatResponse(success=True, response=result["response"], mode=request.mode, timestamp=datetime.now().isoformat(), conversation_id=result["conversation_id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"智能体调用失败: {str(e)}")

@app.get("/")
async def root():
    return {"service": "深圳学位房规划助手 API", "version": "2.0.0", "docs": "/docs", "health": "/xuequ/health", "chat": "POST /xuequ/chat"}

if __name__ == "__main__":
    print("=" * 50)
    print("🏠 深圳学位房规划助手 API 服务启动中...")
    print("⚠️ 请确保已设置环境变量: COZE_API_TOKEN, COZE_BOT_ID")
    print("=" * 50)
    uvicorn.run("main:app", host="0.0.0.0", port=8890, reload=False, log_level="info")
