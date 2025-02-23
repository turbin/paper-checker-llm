# 使用Python基础镜像
FROM python:3-slim-bullseye

#3.13.2-slim-bullseye, 3.13-slim-bullseye, 3-slim-bullseye, slim-bullseye

# 安装Node.js和Nginx
RUN apt-get update && \
    apt-get install -y curl gnupg nginx && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制前端项目文件并构建
COPY frontend/package*.json ./frontend/
WORKDIR /app/frontend
RUN npm install
COPY frontend .
RUN npm run build

# 切换回主工作目录
WORKDIR /app

# 复制后端项目文件
COPY backend /app/backend
COPY promots /app/promots

# 安装Python依赖
WORKDIR /app/backend
RUN pip install -r requirements.txt

# 复制前端构建产物到Nginx目录
RUN cp -r /app/frontend/dist/* /usr/share/nginx/html/

# 配置Nginx
RUN echo '\
server { \
    listen 80; \
    location / { \
        root /usr/share/nginx/html; \
        try_files $uri $uri/ /index.html; \
    } \
    location /api { \
        proxy_pass http://localhost:5300; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
    } \
}' > /etc/nginx/conf.d/default.conf

# 创建启动脚本
RUN echo '\
#!/bin/bash\
nginx\
cd /app/backend && python app.py' > /app/start.sh && chmod +x /app/start.sh

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 80 5300

# 启动服务
# CMD ["/app/start.sh"]