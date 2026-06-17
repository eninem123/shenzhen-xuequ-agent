#!/bin/bash
# 深圳学位房规划助手 - 一键部署脚本

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "🏠 深圳学位房规划助手 部署脚本"
echo "============================================"

# 1. 安装依赖
echo "[1/6] 安装 Python 依赖..."
pip install fastapi uvicorn pydantic -q

# 2. 创建目录
echo "[2/6] 创建目录..."
mkdir -p /var/www/xuequ
mkdir -p /opt/xuequ-api

# 3. 部署前端
echo "[3/6] 部署前端页面..."
bash "$SCRIPT_DIR/sync-frontend.sh"

# 4. 部署后端
echo "[4/6] 部署后端服务..."
cp ./backend/main.py /opt/xuequ-api/

# 5. 配置 Systemd
echo "[5/6] 配置 Systemd 服务..."
cp ./xuequ-api.service /etc/systemd/system/
systemctl daemon-reload

# 6. 启动服务
echo "[6/6] 启动服务..."
systemctl enable xuequ-api
systemctl restart xuequ-api

echo ""
echo "============================================"
echo "✅ 部署完成！"
echo "============================================"
echo ""
echo "📍 服务状态："
systemctl status xuequ-api --no-pager
echo ""
echo "📍 访问地址："
echo "   前端页面：http://your-domain/xuequ/"
echo "   API文档：  http://your-domain/xuequ/api/docs"
echo ""
echo "📍 常用命令："
echo "   重启服务:  systemctl restart xuequ-api"
echo "   查看日志:  journalctl -u xuequ-api -f"
echo ""
