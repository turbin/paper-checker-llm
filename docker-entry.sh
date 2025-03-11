#!/bin/bash
set -e

# 输出环境信息
echo "=== 环境信息 ==="
echo "Python 版本: $(python --version)"
echo "Node 版本: $(node --version 2>/dev/null || echo '未安装')"
echo "Nginx 版本: $(nginx -v 2>&1 | grep -o 'nginx/[0-9.]*')"
echo "=================="

# 确保目录存在
mkdir -p /app/backend/logs
mkdir -p /app/backend/output
mkdir -p /app/promots

# 检查 .env 文件
if [ -f /app/.env ]; then
    echo "已找到 .env 文件，加载环境变量"
    export $(grep -v '^#' /app/.env | xargs)
else
    echo "警告: 未找到 .env 文件，使用默认环境变量"
fi

# 检查 API 密钥
if [ -z "$OPENAI_API_KEY" ]; then
    echo "警告: 未设置 OPENAI_API_KEY 环境变量"
fi

# 检查模板文件
if [ ! -f /app/promots/sunshine.ruler ] || [ ! -f /app/promots/xmu.ruler ]; then
    echo "错误: 缺少必要的模板文件"
    exit 1
fi

# 启动后端服务
echo "启动后端服务..."
cd /app && python -u backend/app.py &
BACKEND_PID=$!

# 等待后端服务启动
echo "等待后端服务启动..."
sleep 3

# 启动 Nginx
echo "启动 Nginx 服务..."
nginx -g "daemon off;" &
NGINX_PID=$!

# 捕获 SIGTERM 和 SIGINT 信号
trap "echo '正在关闭服务...'; kill $BACKEND_PID; kill $NGINX_PID; exit 0" SIGTERM SIGINT

# 等待任一进程结束
wait -n

# 如果有进程异常退出，则关闭所有服务
echo "检测到服务异常退出，正在关闭所有服务..."
kill $BACKEND_PID 2>/dev/null || true
kill $NGINX_PID 2>/dev/null || true
exit 1 