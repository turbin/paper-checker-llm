# 第一阶段：构建前端
FROM node:18-slim as frontend-build

# 设置工作目录
WORKDIR /app

# 复制前端项目文件
COPY frontend/package*.json ./

# 安装依赖
RUN npm install

# 复制其他源代码
COPY frontend .

# 构建应用
RUN npm run build

# 第二阶段：设置Python环境并配置Nginx
FROM python:3.9-slim

# 安装Nginx
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制后端项目文件
COPY backend /app
COPY promots /app/promots

# 安装Python依赖和调试工具
RUN pip install -r requirements.txt debugpy

# 复制前端构建产物
COPY --from=frontend-build /app/dist /usr/share/nginx/html

# 配置Nginx
RUN echo '\
server { \
    listen 80; \
    location / { \
        root /usr/share/nginx/html; \
        try_files $uri $uri/ /index.html; \
    } \
    location /api { \
        proxy_pass http://localhost:7860; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
    } \
}' > /etc/nginx/conf.d/default.conf

# 创建启动脚本
RUN echo '\
#!/bin/bash\
nginx\
python -m debugpy --listen 0.0.0.0:5678 --wait-for-client app.py' > /app/start.sh && chmod +x /app/start.sh

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 80 7860 5678

# 启动服务
CMD ["/app/start.sh"]