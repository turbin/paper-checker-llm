#!/bin/bash

# 设置错误时退出
set -e

echo "=== 开始构建和启动服务 ==="

# 检查是否安装了必要的工具
command -v docker >/dev/null 2>&1 || { echo "需要安装 Docker 但未安装。请先安装 Docker。"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo "需要安装 Docker Compose 但未安装。请先安装 Docker Compose。"; exit 1; }

# 检查.env文件是否存在
if [ ! -f .env ]; then
    echo "警告: .env 文件不存在，将使用 .env.example 作为模板"
    cp .env.example .env
    echo "请编辑 .env 文件，设置必要的环境变量"
    exit 1
fi

# 停止并删除现有容器
echo "停止并删除现有容器..."
docker compose down

# 重新构建镜像
echo "重新构建镜像..."
docker build -t paper-checker:latest .

# 启动容器
echo "启动容器..."
docker compose up -d

# 等待容器启动
echo "等待容器启动..."
sleep 5

# 检查容器状态
echo "检查容器状态..."
docker ps

# 显示容器日志
echo "显示容器日志..."
docker logs paper-checker

echo "=== 构建和启动完成 ==="
echo "请通过以下地址访问应用:"
echo "http://localhost:8080 或 http://服务器IP:8080" 