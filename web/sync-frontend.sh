#!/bin/bash
# 将仓库前端同步到 Nginx 静态目录（日常改页面后用这个）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
TARGET_DIR="/var/www/xuequ"

FILES=(index.html data.html)

echo "============================================"
echo "同步前端: $FRONTEND_DIR -> $TARGET_DIR"
echo "============================================"

mkdir -p "$TARGET_DIR"

for file in "${FILES[@]}"; do
  src="$FRONTEND_DIR/$file"
  dst="$TARGET_DIR/$file"
  if [[ ! -f "$src" ]]; then
    echo "跳过: $src 不存在"
    continue
  fi
  cp "$src" "$dst"
  echo "✓ $file"
done

echo ""
echo "验证:"
for file in "${FILES[@]}"; do
  if [[ -f "$TARGET_DIR/$file" ]]; then
    echo "  - $TARGET_DIR/$file ($(wc -c < "$TARGET_DIR/$file") bytes)"
  fi
done

echo ""
echo "完成。生产地址: https://www.aialter.site/xuequ/"
