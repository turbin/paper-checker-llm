FROM node:18.20.7-bullseye AS frontend-builder

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
# 复制前端public目录（用于错误页面）
COPY --from=frontend-builder /app/frontend/public /app/frontend/public

# 复制后端代码
COPY backend/ /app/backend/
COPY promots/ /app/promots/

# 不复制本地.env文件，而是创建一个空的.env文件
# 实际的.env文件应在运行时通过卷挂载提供
RUN touch /app/.env

# 安装后端依赖
RUN pip install --no-cache-dir -r backend/requirements.txt

# 复制 Nginx 配置文件
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制启动脚本
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# 创建必要的目录
RUN mkdir -p /app/backend/logs /app/backend/output

# 暴露端口
EXPOSE 80

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 注意：.env文件应在构建时通过--build-arg或在运行时通过-v挂载到容器中
# 例如: docker run -v $(pwd)/.env:/app/.env ...

# 使用docker-entrypoint.sh作为入口点
ENTRYPOINT ["/app/docker-entrypoint.sh"]
# 默认无参数启动
CMD []