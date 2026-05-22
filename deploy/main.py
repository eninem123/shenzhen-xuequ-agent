#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""深圳学位房规划助手 - 后端API服务 v3.0"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn, json, urllib.request, urllib.parse, ssl, time, os, socket
from datetime import datetime, timedelta

# 强制IPv4
_orig = socket.getaddrinfo
def _ipv4(*a, **kw): return [x for x in _orig(*a, **kw) if x[0] == socket.AF_INET] or _orig(*a, **kw)
socket.getaddrinfo = _ipv4

COZE_API_TOKEN = os.environ.get("COZE_API_TOKEN", "")
COZE_BOT_ID = os.environ.get("COZE_BOT_ID", "")
COZE_BASE_URL = "https://api.coze.cn"
SZ_OPEN_APPKEY = os.environ.get("SZ_OPEN_APPKEY", "")
SZ_OPEN_BASE = "https://opendata.sz.gov.cn/api"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

SZ_APIS = {
    "01903516": {"name":"二手住房成交参考价","prefix":"29200","desc":"7653个小区官方参考价","key_fields":["PRJ_NAME","ZDJ","ZONE","JDNAME"],"category":"房价","core":True},
    "01903509": {"name":"二手房源信息","prefix":"29200","desc":"618375条二手房源","key_fields":["HOUSE_NAME","ZONE","BUILT_IN_AREA","LU_LOCATION"],"category":"房价"},
    "01903513": {"name":"二手房成交汇总","prefix":"29200","desc":"91848条成交汇总","key_fields":["TJ_DATE","ZONE","HOUSE_USAGE2","CJ_NUM","CJ_AREA"],"category":"成交"},
    "01903510": {"name":"一手商品房成交(按日)","prefix":"29200","desc":"119267条新房成交","key_fields":["TJ_DATE","ZONE","KS_NUM","CJ_NUM"],"category":"成交"},
    "01903511": {"name":"一手商品房按面积成交","prefix":"29200","desc":"56866条按面积统计","key_fields":["TJ_DATE","AREA_TYPE","CJ_NUM","ZONE"],"category":"成交"},
    "01903508": {"name":"商品房预售","prefix":"29200","desc":"2116条预售项目","key_fields":["PROJECTNAME","ZONE","SITEADDRESS","HOUSESUITES"],"category":"新房"},
    "01903541": {"name":"物业维修资金","prefix":"29200","desc":"566021条","key_fields":["VILLAGE_NAME","BUILD_AREA","COMPLETE_DATE"],"category":"物业"},
    "00503071": {"name":"义务教育招生入学信息","prefix":"29200","desc":"26条招生入学政策","key_fields":["DW","ZXDH","ZSWZ","BGDZ"],"category":"教育"},
    "00503607": {"name":"近年学生数统计","prefix":"29200","desc":"338条","key_fields":["NF","XXLBYJL","SL"],"category":"教育"},
    "00503608": {"name":"高中招生计划","prefix":"29200","desc":"179条","key_fields":["XXMC","XXDJ","BXXZ","JNZSJHBS","MNZSJHRS"],"category":"教育"},
    "00503609": {"name":"公办高中指标生招生计划","prefix":"29200","desc":"436条","key_fields":["NF","XXMC","ACLKSZBSJH","DLKSZBSJH"],"category":"教育"},
    "04003733": {"name":"南山区公办高中名单","prefix":"29200","desc":"6条","key_fields":["MC","BXNR","XXDM","BXDZ"],"category":"教育"},
    "03103821": {"name":"光明区GDP","prefix":"29200","desc":"7条","key_fields":["NF","DQSCZZ","ZS","DQMC"],"category":"经济"},
    "03200726": {"name":"坪山区GDP","prefix":"29200","desc":"45条","key_fields":["NF","JD","DQSCZZ","DQ"],"category":"经济"},
    "04703715": {"name":"龙华区GDP","prefix":"29200","desc":"22条","key_fields":["NF","JDLJ","DQSCZZYY","DQ"],"category":"经济"},
    "04003663": {"name":"南山企业分行业调查","prefix":"29200","desc":"9条","key_fields":["NF","工业","建筑业","批发零售","房地产","服务业"],"category":"经济"},
}

app = FastAPI(title="深圳学位房规划助手 API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def fetch_sz_api(api_id, page=1, rows=50, extra_params=None):
    if api_id not in SZ_APIS: raise ValueError(f"未注册的API: {api_id}")
    info = SZ_APIS[api_id]; pfx = info.get("prefix","29200")
    path = f"{SZ_OPEN_BASE}/{pfx}_{api_id}/1/service.xhtml" if pfx else f"{SZ_OPEN_BASE}/{api_id}/1/service.xhtml"
    params = {"appKey": SZ_OPEN_APPKEY, "page": page, "rows": rows}
    if extra_params: params.update(extra_params)
    url = f"{path}?{urllib.parse.urlencode(params)}"
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
        result = json.loads(r.read().decode("utf-8"))
    return {"api_id":api_id,"name":info["name"],"category":info["category"],"page":page,"rows":rows,"total":result.get("total",0),"data":result.get("data",[]),"key_fields":info.get("key_fields",[])}

class ChatRequest(BaseModel):
    message: str; mode: str = "quick"; conversation_id: Optional[str] = None
class ChatResponse(BaseModel):
    success: bool; response: str; mode: str; timestamp: str; conversation_id: Optional[str] = None

def _coze(url, method="GET", data=None):
    h = {"Authorization": f"Bearer {COZE_API_TOKEN}", "Content-Type": "application/json"}
    b = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=b, headers=h, method=method)
    with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def coze_chat(message, mode="quick", conversation_id=None):
    msg = f"出方案：{message}" if mode == "plan" else message
    payload = {"bot_id":COZE_BOT_ID,"user_id":"web_user","stream":False,"auto_save_history":True,"additional_messages":[{"role":"user","content":msg,"content_type":"text"}]}
    if conversation_id: payload["conversation_id"] = conversation_id
    result = _coze(f"{COZE_BASE_URL}/v3/chat", "POST", payload)
    if result.get("code") != 0: raise Exception(f"Coze失败: {result.get('msg')}")
    chat_id, conv_id = result["data"]["id"], result["data"]["conversation_id"]
    t0 = time.time()
    while time.time()-t0 < 120:
        time.sleep(3)
        s = _coze(f"{COZE_BASE_URL}/v3/chat/retrieve?chat_id={chat_id}&conversation_id={conv_id}")
        if s.get("data",{}).get("status")=="completed":
            msgs = _coze(f"{COZE_BASE_URL}/v3/chat/message/list?chat_id={chat_id}&conversation_id={conv_id}")
            for m in msgs.get("data",[]):
                if m.get("role")=="assistant" and m.get("type")=="answer": return {"response":m.get("content",""),"conversation_id":conv_id}
            for m in msgs.get("data",[]):
                if m.get("role")=="assistant": return {"response":m.get("content",""),"conversation_id":conv_id}
        elif s.get("data",{}).get("status")=="failed": raise Exception("Coze失败")
    raise Exception("Coze超时")

@app.get("/")
async def root():
    return {"service":"深圳学位房规划助手 API","version":"3.0.0","apis":len(SZ_APIS),"docs":"/docs","health":"/xuequ/health","catalog":"/xuequ/catalog","chat":"POST /xuequ/chat","szdata":"GET /xuequ/szdata/{api_id}","price_ref":"GET /xuequ/price-ref"}

@app.get("/xuequ/health")
async def health():
    ok = bool(COZE_API_TOKEN and COZE_BOT_ID and SZ_OPEN_APPKEY)
    return {"status":"healthy" if ok else "degraded","version":"3.0.0","env":{"COZE":bool(COZE_API_TOKEN),"BOT":bool(COZE_BOT_ID),"SZ":bool(SZ_OPEN_APPKEY)},"apis":len(SZ_APIS)}

@app.get("/xuequ/catalog")
async def catalog():
    cats = {}
    for aid, info in SZ_APIS.items():
        cats.setdefault(info["category"],[]).append({"api_id":aid,"name":info["name"],"desc":info["desc"],"key_fields":info.get("key_fields",[]),"core":info.get("core",False),"endpoint":f"/xuequ/szdata/{aid}"})
    return {"success":True,"total":len(SZ_APIS),"categories":cats}

@app.get("/xuequ/szdata/{api_id}")
async def get_sz(api_id:str, page:int=Query(1,ge=1), rows:int=Query(50,ge=1,le=500), zone:Optional[str]=Query(None)):
    if not SZ_OPEN_APPKEY: raise HTTPException(500,"未配置SZ_OPEN_APPKEY")
    try:
        r = fetch_sz_api(api_id, page, rows, {"ZONE":zone} if zone else None)
        return {"success":True,**r,"count":len(r["data"]),"timestamp":datetime.now().isoformat()}
    except ValueError as e: raise HTTPException(404,str(e))
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/xuequ/price-ref")
async def price_ref(zone:Optional[str]=Query(None), keyword:Optional[str]=Query(None), page:int=Query(1,ge=1), rows:int=Query(100,ge=1,le=500)):
    if not SZ_OPEN_APPKEY: raise HTTPException(500,"未配置SZ_OPEN_APPKEY")
    try:
        r = fetch_sz_api("01903516", page, rows, {"ZONE":zone} if zone else None)
        data = r["data"]
        if keyword:
            ku = keyword.upper()
            data = [d for d in data if ku in d.get("PRJ_NAME","").upper()]
        return {"success":True,"api":"01903516","name":"二手住房成交参考价","zone":zone or "全部","keyword":keyword,"total":r["total"],"filtered":len(data),"key_fields":["PRJ_NAME","ZDJ","ZONE","JDNAME"],"data":data,"timestamp":datetime.now().isoformat()}
    except Exception as e: raise HTTPException(500,str(e))

@app.get("/xuequ/deals")
async def deals(zone:Optional[str]=Query(None), days:int=Query(30,ge=1,le=365), usage:str=Query("住宅"), page:int=Query(1,ge=1), rows:int=Query(100,ge=1,le=500)):
    if not SZ_OPEN_APPKEY: raise HTTPException(500,"未配置SZ_OPEN_APPKEY")
    try:
        r = fetch_sz_api("01903513", page, rows, {"ZONE":zone} if zone else None)
        data = r["data"]
        if usage: data = [d for d in data if d.get("HOUSE_USAGE2","")==usage]
        return {"success":True,"api":"01903513","name":"二手房成交汇总","zone":zone or "全部","days":days,"usage":usage,"total":r["total"],"filtered":len(data),"data":data,"timestamp":datetime.now().isoformat()}
    except Exception as e: raise HTTPException(500,str(e))

@app.post("/xuequ/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not COZE_API_TOKEN or not COZE_BOT_ID: raise HTTPException(500,"未配置Coze")
    try:
        r = coze_chat(req.message, req.mode, req.conversation_id)
        return ChatResponse(success=True,response=r["response"],mode=req.mode,timestamp=datetime.now().isoformat(),conversation_id=r["conversation_id"])
    except Exception as e: raise HTTPException(500,str(e))

if __name__ == "__main__":
    print(f"🏠 学位房助手API v3.0 | {len(SZ_APIS)}个数据源 | 环境变量: COZE={bool(COZE_API_TOKEN)} BOT={bool(COZE_BOT_ID)} SZ={bool(SZ_OPEN_APPKEY)}")
    uvicorn.run("main:app", host="0.0.0.0", port=8890, reload=False, log_level="info")
