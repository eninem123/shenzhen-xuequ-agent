#!/usr/bin/env python3
import socket
orig_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4(*args, **kwargs): return [x for x in orig_getaddrinfo(*args, **kwargs) if x[0] == socket.AF_INET] or orig_getaddrinfo(*args, **kwargs)
socket.getaddrinfo = getaddrinfo_ipv4
# -*- coding: utf-8 -*-
"""
深圳学位房数据慢爬器 v2.0
- 分批爬取，每天一小批，一个月跑完
- UA轮换 + 指数退避 + 请求限速
- 进度持久化（断点续爬）
- 爬完自动上传Coze知识库
- 部署: crontab -e → 0 3 * * * python3 /opt/xuequ-api/crawler.py
"""

import json, urllib.request, urllib.parse, ssl, time, os, base64, random, hashlib
from datetime import datetime, timedelta

# ============ 配置 ============
APPKEY = os.environ.get("SZ_OPEN_APPKEY", "a3fed2c23db84ad3a38ba7ec4c897352")
BASE = "https://opendata.sz.gov.cn/api"
COZE_TOKEN = os.environ.get("COZE_API_TOKEN", "")
DATASET_ID = "7642576726526804031"
PROGRESS_FILE = "/opt/xuequ-api/crawl_progress.json"
DATA_DIR = "/opt/xuequ-api/crawl_data"
LOG_FILE = "/opt/xuequ-api/crawl.log"

# 每天最多爬多少页（慢速，保护appKey）
DAILY_PAGE_LIMIT = 30  # 每天30页×500条=1.5万条，12个API约20天跑完

# UA池 - 最新Chrome/Edge/Firefox
UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]

# API列表 - 按优先级排序
API_LIST = [
    {"id": "01903516", "pfx": "29200", "name": "二手住房成交参考价", "max": 8000, "fmt": "price"},
    {"id": "00503071", "pfx": "29200", "name": "义务教育招生入学信息", "max": 100, "fmt": "enroll"},
    {"id": "00503607", "pfx": "29200", "name": "近年学生数统计", "max": 500, "fmt": "table"},
    {"id": "00503608", "pfx": "29200", "name": "高中招生计划", "max": 500, "fmt": "hs"},
    {"id": "00503609", "pfx": "29200", "name": "公办高中指标生招生计划", "max": 500, "fmt": "quota"},
    {"id": "01903509", "pfx": "29200", "name": "二手房源信息", "max": 2000, "fmt": "gen"},
    {"id": "01903513", "pfx": "29200", "name": "二手房成交汇总", "max": 1000, "fmt": "gen"},
    {"id": "01903510", "pfx": "29200", "name": "一手商品房成交按日", "max": 500, "fmt": "gen"},
    {"id": "01903508", "pfx": "29200", "name": "商品房预售", "max": 2200, "fmt": "gen"},
    {"id": "01903511", "pfx": "29200", "name": "一手商品房按面积成交", "max": 500, "fmt": "gen"},
    {"id": "04003733", "pfx": "29200", "name": "南山区公办高中名单", "max": 100, "fmt": "gen"},
    {"id": "01903541", "pfx": "29200", "name": "物业维修资金", "max": 500, "fmt": "gen"},
]


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except:
        pass


def get_random_ua():
    return random.choice(UA_POOL)


def random_delay(min_s=1.0, max_s=3.0):
    """随机延迟，模拟人类浏览间隔"""
    delay = random.uniform(min_s, max_s)
    time.sleep(delay)


def load_progress():
    """加载爬取进度"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # 初始化进度
    progress = {}
    for api in API_LIST:
        progress[api["id"]] = {
            "name": api["name"],
            "next_page": 1,
            "collected": 0,
            "total": 0,
            "done": False,
            "data_file": f"{DATA_DIR}/{api['id']}.json",
        }
    return progress


def save_progress(progress):
    """保存爬取进度"""
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def fetch_page(api_id, pfx, page, rows=500, retries=3):
    """带重试的页面拉取，指数退避"""
    url = f"{BASE}/{pfx}_{api_id}/1/service.xhtml"
    params = {"appKey": APPKEY, "page": page, "rows": rows}
    full_url = f"{url}?{urllib.parse.urlencode(params)}"

    for attempt in range(retries):
        try:
            ctx = ssl.create_default_context()
            ua = get_random_ua()
            headers = {
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            }
            req = urllib.request.Request(full_url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result
        except urllib.error.HTTPError as e:
            if e.code == 403:
                wait = (2 ** attempt) * 5 + random.uniform(0, 3)
                log(f"  ⚠️ 403 Forbidden, 等待{wait:.1f}s后重试(attempt {attempt+1}/{retries})")
                time.sleep(wait)
            elif e.code == 429:
                wait = 60 + random.uniform(0, 30)
                log(f"  ⚠️ 429 Too Many Requests, 等待{wait:.1f}s")
                time.sleep(wait)
            else:
                log(f"  ❌ HTTP {e.code}: {e.reason}")
                raise
        except Exception as e:
            wait = (2 ** attempt) * 3 + random.uniform(0, 2)
            log(f"  ⚠️ 异常: {e}, 等待{wait:.1f}s后重试")
            time.sleep(wait)

    raise Exception(f"请求失败，已重试{retries}次")


def crawl_daily():
    """每天爬取一小批"""
    os.makedirs(DATA_DIR, exist_ok=True)
    progress = load_progress()
    pages_today = 0
    any_new_data = False

    log(f"🕷️ 每日爬取开始，今日限额{DAILY_PAGE_LIMIT}页")

    for api in API_LIST:
        api_id = api["id"]
        pfx = api["pfx"]
        p = progress.get(api_id)

        if not p or p.get("done"):
            continue

        # 检查已收集的数据文件
        data_file = p.get("data_file", f"{DATA_DIR}/{api_id}.json")
        if os.path.exists(data_file):
            with open(data_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        else:
            existing = []

        max_rows = api["max"]
        if len(existing) >= max_rows:
            p["done"] = True
            p["collected"] = len(existing)
            log(f"  ✅ {api['name']} 已完成({len(existing)}条)")
            continue

        log(f"\n📡 {api['name']} ({api_id}) - 已有{len(existing)}条，目标{max_rows}")

        while pages_today < DAILY_PAGE_LIMIT:
            page = p.get("next_page", 1)
            try:
                random_delay(1.5, 4.0)  # 礼貌间隔
                result = fetch_page(api_id, pfx, page, rows=500)
                data = result.get("data", [])
                total = result.get("total", 0)

                if not data:
                    p["done"] = True
                    log(f"  🏁 无更多数据，标记完成")
                    break

                existing.extend(data)
                pages_today += 1
                p["next_page"] = page + 1
                p["collected"] = len(existing)
                p["total"] = total
                any_new_data = True

                log(f"  pg{page}: +{len(data)}条, 累计{len(existing)}/{max_rows}(total:{total})")

                # 保存数据文件
                with open(data_file, "w", encoding="utf-8") as f:
                    json.dump(existing, f, ensure_ascii=False)

                # 达到目标量
                if len(existing) >= max_rows:
                    p["done"] = True
                    log(f"  ✅ 达到目标量{max_rows}")
                    break

                # 今日配额用完
                if pages_today >= DAILY_PAGE_LIMIT:
                    log(f"  ⏸️ 今日{DAILY_PAGE_LIMIT}页配额已用，明日继续")
                    break

            except Exception as e:
                log(f"  ❌ 页{page}失败: {e}")
                break

        save_progress(progress)

        if pages_today >= DAILY_PAGE_LIMIT:
            break

    # 如果有新数据，检查是否所有API都完成
    all_done = all(progress.get(a["id"], {}).get("done", False) for a in API_LIST)

    if any_new_data:
        # 每次有新数据都重新生成知识库md
        generate_and_upload(progress)

    if all_done:
        log("🎉 所有API数据爬取完成！")
    else:
        done_count = sum(1 for a in API_LIST if progress.get(a["id"], {}).get("done"))
        log(f"📊 进度: {done_count}/{len(API_LIST)} 个API已完成, 今日爬取{pages_today}页")

    return progress


def generate_and_upload(progress):
    """生成知识库MD并上传Coze"""
    log("📝 生成知识库文档...")
    parts = [
        f"# 深圳学位房政府数据\n",
        f"> 爬取时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        f"> 数据来源: 深圳政府开放平台 opendata.sz.gov.cn\n",
    ]

    # 进度摘要
    done = sum(1 for a in API_LIST if progress.get(a["id"], {}).get("done"))
    parts.append(f"> 进度: {done}/{len(API_LIST)} 已完成\n\n---\n")

    for api in API_LIST:
        api_id = api["id"]
        p = progress.get(api_id, {})
        data_file = p.get("data_file", f"{DATA_DIR}/{api_id}.json")

        if not os.path.exists(data_file):
            parts.append(f"## {api['name']}\n\n⚠️ 待爬取\n\n---\n")
            continue

        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not data:
            parts.append(f"## {api['name']}\n\n暂无数据\n\n---\n")
            continue

        fmt = api["fmt"]
        if fmt == "price":
            parts.append(_fmt_price(data))
        elif fmt == "enroll":
            parts.append(_fmt_enroll(data))
        elif fmt == "hs":
            parts.append(_fmt_hs(data))
        elif fmt == "quota":
            parts.append(_fmt_quota(data))
        else:
            parts.append(_fmt_table(api["name"], data))
        parts.append("\n\n---\n")

    full_md = "\n".join(parts)

    # 保存本地
    md_file = f"{DATA_DIR}/knowledge_latest.md"
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(full_md)
    log(f"📄 知识库文档: {md_file} ({len(full_md)//1024}KB)")

    # 上传Coze
    if COZE_TOKEN:
        upload_coze(full_md)
    else:
        log("⚠️ 未设COZE_API_TOKEN，跳过上传")


def _fmt_price(data):
    lines = [f"## 二手住房成交参考价（政府官方）\n\n> {len(data)}个小区 | 更新: {datetime.now().strftime('%Y-%m-%d')}\n"]
    zones = {}
    for r in data:
        zones.setdefault(r.get("ZONE", "未知"), []).append(r)
    for z in sorted(zones):
        items = sorted(zones[z], key=lambda x: float(x.get("ZDJ", 0) or 0), reverse=True)
        lines.append(f"\n### {z}区（{len(items)}个小区）\n")
        lines.append("| 楼盘名 | 参考单价(元/㎡) | 街道 |")
        lines.append("|--------|----------------|------|")
        for r in items:
            lines.append(f"| {r.get('PRJ_NAME','')} | {r.get('ZDJ','')} | {r.get('JDNAME','')} |")
    return "\n".join(lines)


def _fmt_enroll(data):
    lines = [f"## 义务教育招生入学信息\n\n> {len(data)}条 | 更新: {datetime.now().strftime('%Y-%m-%d')}\n"]
    for r in data:
        lines.append(f"- **{r.get('DW','')}** 咨询:{r.get('ZXDH','')} 地址:{r.get('ZSWZ','')} 办公:{r.get('BGDZ','')}")
    return "\n".join(lines)


def _fmt_hs(data):
    lines = [f"## 高中招生计划\n\n> {len(data)}条 | 更新: {datetime.now().strftime('%Y-%m-%d')}\n"]
    lines.append("| 学校名 | 等级 | 性质 | 班数 | 人数 |")
    lines.append("|--------|------|------|------|------|")
    for r in data:
        lines.append(f"| {r.get('XXMC','')} | {r.get('XXDJ','')} | {r.get('BXXZ','')} | {r.get('JNZSJHBS','')} | {r.get('MNZSJHRS','')} |")
    return "\n".join(lines)


def _fmt_quota(data):
    lines = [f"## 公办高中指标生招生计划\n\n> {len(data)}条 | 更新: {datetime.now().strftime('%Y-%m-%d')}\n"]
    lines.append("| 年份 | 学校 | AC类指标 | D类指标 |")
    lines.append("|------|------|----------|--------|")
    for r in data:
        lines.append(f"| {r.get('NF','')} | {r.get('XXMC','')} | {r.get('ACLKSZBSJH','')} | {r.get('DLKSZBSJH','')} |")
    return "\n".join(lines)


def _fmt_table(name, data):
    lines = [f"## {name}\n\n> {len(data)}条 | 更新: {datetime.now().strftime('%Y-%m-%d')}\n"]
    if not data:
        lines.append("暂无数据\n")
        return "\n".join(lines)
    s = data[:300]
    fs = list(s[0].keys())[:6]
    lines.append("| " + " | ".join(fs) + " |")
    lines.append("| " + " | ".join(["---"] * len(fs)) + " |")
    for r in s:
        lines.append("| " + " | ".join([str(r.get(k, ""))[:50] for k in fs]) + " |")
    if len(data) > 300:
        lines.append(f"\n> 展示前300/{len(data)}条")
    return "\n".join(lines)


def upload_coze(content):
    """上传到Coze知识库"""
    log("📤 上传Coze知识库...")
    filename = f"政府数据_慢爬_{datetime.now().strftime('%Y%m%d')}.md"
    b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
    payload = {
        "dataset_id": DATASET_ID,
        "document_bases": [{"name": filename, "source_info": {"file_base64": b64, "file_type": "txt", "document_source": 0}}],
        "chunk_strategy": {"chunk_type": 0},
        "format_type": 0
    }
    headers = {"Authorization": f"Bearer {COZE_TOKEN}", "Content-Type": "application/json", "Agw-Js-Conv": "str"}
    req = urllib.request.Request(
        "https://api.coze.cn/open_api/knowledge/document/create",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=120) as r:
            res = json.loads(r.read().decode("utf-8"))
            if res.get("code") == 0:
                log(f"✅ 上传成功! {res.get('data', {})}")
            else:
                log(f"❌ 上传失败: code={res.get('code')} msg={res.get('msg')}")
    except Exception as e:
        log(f"❌ 上传异常: {e}")


if __name__ == "__main__":
    crawl_daily()
