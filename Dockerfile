FROM node:16-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.9-slim

# 安装 Nginx
RUN apt-get update && apt-get install -y nginx && apt-get clean && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制前端构建产物
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# 复制后端代码
COPY backend/ /app/backend/
COPY promots/ /app/promots/

# 安装后端依赖
RUN pip install --no-cache-dir -r backend/requirements.txt

# 复制 Nginx 配置文件
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制启动脚本
COPY docker-entry.sh /app/docker-entry.sh
RUN chmod +x /app/docker-entry.sh

# 创建必要的目录
RUN mkdir -p /app/backend/logs /app/backend/output

# 暴露端口
EXPOSE 80

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 启动服务
CMD ["/app/docker-entry.sh"]