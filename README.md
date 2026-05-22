# 深圳学位房规划智能体

基于AI Agent的深圳学位房智能规划系统，提供学区查询、积分评估、购房/租房方案定制等服务。

## 产品架构

- **对话式Agent**：基于Coze Bot，支持中介快答（极简话术）+ 客户定制方案（正式交付）
- **Web前端**：深色科技风，手机优先设计
- **Web后端**：Python FastAPI，对接Coze Bot API
- **知识库**：深圳10区学区/积分/房价/政策数据

## 目录结构

```
├── docs/                    # 文档
│   ├── Coze创建指南.md
│   └── 系统提示词.md
├── knowledge-base/          # 知识库数据
│   ├── 学区房价格速查.md
│   ├── 学区房价格速查v3.md
│   ├── 时间线与政策.md
│   └── 深圳学校梯队.md
├── web/                     # Web应用
│   ├── backend/main.py      # FastAPI后端
│   ├── frontend/index.html  # 前端页面
│   ├── deploy.sh            # 部署脚本
│   ├── nginx.conf           # Nginx配置
│   └── xuequ-api.service    # Systemd服务
└── README.md
```

## 快速开始

### 环境变量

```bash
export COZE_API_TOKEN="your_coze_pat"
export COZE_BOT_ID="your_bot_id"
```

### 部署

```bash
cd web
bash deploy.sh
```

### 本地开发

```bash
cd web/backend
pip install fastapi uvicorn pydantic
COZE_API_TOKEN=xxx COZE_BOT_ID=xxx python main.py
```

## 数据源分级

| 优先级 | 来源 | 类型 |
|--------|------|------|
| T1 | 深圳政府开放平台 | 免费API |
| T2 | 贝壳开放平台 | 商业API |
| T3 | 10区学位锁定查询 | 公开查询 |
| T4 | 社区论坛 | 非结构化 |
| T5 | 链家成交页 | 爬取 |

## License

MIT
