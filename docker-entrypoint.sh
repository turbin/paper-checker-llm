#!/bin/bash

# 启动Nginx
nginx

# 启动后端服务（后台运行）
cd /app/backend
python app.py &
BACKEND_PID=$!

# 等待后端服务启动
sleep 3

# 启动前端服务
cd /app/frontend
npm run dev &
FRONTEND_PID=$!

# 捕获SIGINT信号，清理子进程
cleanup() {
    echo "正在关闭服务..."
    kill $FRONTEND_PID
    kill $BACKEND_PID
    exit 0
}

trap cleanup SIGINT

# 等待子进程
wait