# 深圳学位房规划助手

为中介老婆开发的学位房咨询 Web 问答应用。

## 📁 项目结构

```
./学区房规划Agent/web/
├── index.html          # 前端页面（单文件，直接可用）
├── main.py             # 后端 API（FastAPI）
├── xuequ-api.service   # Systemd 服务配置
├── nginx.conf          # Nginx 反向代理配置
├── deploy.sh           # 一键部署脚本
└── README.md           # 本文档
```

## 🚀 快速部署

### 方式一：一键部署

```bash
cd ./学区房规划Agent/web
chmod +x deploy.sh
./deploy.sh
```

### 方式二：手动部署

#### 1. 安装依赖

```bash
pip install fastapi uvicorn pydantic
```

#### 2. 部署前端

```bash
mkdir -p /var/www/xuequ
cp index.html /var/www/xuequ/
```

#### 3. 部署后端

```bash
mkdir -p /opt/xuequ-api
cp main.py /opt/xuequ-api/
```

#### 4. 配置 Systemd

```bash
cp xuequ-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable xuequ-api
systemctl start xuequ-api
```

#### 5. 配置 Nginx

```bash
cp nginx.conf /etc/nginx/conf.d/xuequ.conf
nginx -t
systemctl reload nginx
```

## 🔧 服务管理

| 操作 | 命令 |
|------|------|
| 启动服务 | `systemctl start xuequ-api` |
| 停止服务 | `systemctl stop xuequ-api` |
| 重启服务 | `systemctl restart xuequ-api` |
| 查看状态 | `systemctl status xuequ-api` |
| 查看日志 | `journalctl -u xuequ-api -f` |

## 📡 API 接口

### 健康检查

```
GET /xuequ/health
```

响应：
```json
{
  "status": "healthy",
  "service": "深圳学位房规划助手",
  "version": "1.0.0"
}
```

### 聊天接口

```
POST /xuequ/chat
Content-Type: application/json

{
  "message": "深圳哪个区学位最好",
  "mode": "quick"  // quick: 快答模式, plan: 出方案模式
}
```

响应：
```json
{
  "success": true,
  "response": "深圳学位质量排名...",
  "mode": "quick",
  "timestamp": "2024-01-01T12:00:00"
}
```

## 📱 功能特点

### 快答模式 ⚡
- 快速响应，简洁明了
- 适合日常咨询问题
- 支持快捷问题按钮

### 出方案模式 📋
- 详细分析，结构化输出
- 包含表格、列表、引用等
- 支持一键复制/打印
- 适合给客户出方案

## 🎨 前端特性

- **深色主题**：科技感但温暖
- **移动端优先**：手机友好，大按钮
- **Markdown 渲染**：支持代码、粗体、列表等
- **两种模式**：快答 vs 方案切换
- **复制打印**：方案模式支持复制和打印

## 🔄 后续接入 Coze Bot

后端目前使用模拟数据，后续接入真实 Coze Bot API 只需修改 `main.py` 中的：

```python
async def chat(request: ChatRequest):
    # 调用 Coze Bot API
    response = await call_coze_bot(request.message, request.mode)
    return response
```

## 📝 注意事项

1. Nginx 反代路径 `/xuequ/` -> 前端静态文件
2. Nginx 反代路径 `/xuequ/api/` -> 后端 API (127.0.0.1:8890)
3. 确保服务器 80 端口可用
4. 防火墙开放 80 端口

## 🛠️ 本地测试

```bash
# 后端测试
cd /opt/xuequ-api
python3 main.py

# 前端直接浏览器打开
open index.html
```

## 📞 联系方式

有问题找老公 💪
