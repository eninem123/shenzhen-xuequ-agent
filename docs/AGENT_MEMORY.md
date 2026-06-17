# Agent 记忆：深圳学位房网站部署

> 给爱马仕 / Cursor / 其他 Agent 用。服务器上完整版见：  
> `/root/.openclaw/workspace/shared/爱马仕记忆_学位房网站.md`

## 关键路径

| 项目 | 路径 |
|------|------|
| 生产 | https://www.aialter.site/xuequ/ |
| 数据大盘 | https://www.aialter.site/xuequ/data.html |
| 楼盘库 | https://www.aialter.site/xuequ/properties.html |
| 本地仓库 | `/opt/xuequ-api/shenzhen-xuequ-agent` |
| 前端源码 | `web/frontend/`（**唯一编辑入口**） |
| Nginx 目录 | `/var/www/xuequ/`（**勿直接改**） |
| 同步脚本 | `web/sync-frontend.sh` |

## 部署铁律

```bash
# 1. 改源码
vim web/frontend/index.html      # 主站
vim web/frontend/data.html       # 数据大盘
vim web/frontend/properties.html # 楼盘库

# 2. 同步到 Nginx
cd web && bash sync-frontend.sh

# 3. 提交 GitHub
git add web/frontend/
git commit -m "说明"
git push
```

**禁止**：只改 `/var/www/xuequ/*.html` 不进仓库；或只 push 不跑 `sync-frontend.sh`。

## 同步范围

`sync-frontend.sh` 同步三个文件：`index.html`、`data.html`、`properties.html`

## 2026-06-17 变更摘要

- `data.html`：全局状态、错误重试、指标联动、移动端优化（不增数据）
- 新增 `sync-frontend.sh` 统一前端部署
- `properties.html` 入库并纳入同步

相关提交：`7c63a25`、`c070f4f`、`1a21699`

## 常见坑

- CDN `cdn.jsdelivr.net` 国内被墙 → echarts/marked 用 `/static/` 本地托管
- nginx HTTPS 配置改 `/etc/nginx/sites-enabled/aialter`
- HTML 属性内有双引号时用单引号包裹属性值
