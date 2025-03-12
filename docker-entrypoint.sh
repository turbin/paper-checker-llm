#!/bin/bash
set -e

# 输出环境信息
echo "=== 环境信息 ==="
echo "Python 版本: $(python --version)"
echo "Node 版本: $(node --version 2>/dev/null || echo '未安装 - 前端已预构建为静态文件')"
echo "Nginx 版本: $(nginx -v 2>&1 | grep -o 'nginx/[0-9.]*')"
echo "=================="

# 确保目录存在
mkdir -p /app/backend/logs
mkdir -p /app/backend/output
mkdir -p /app/promots

# 检查前端静态文件
if [ ! -d "/app/frontend/dist" ] || [ ! -f "/app/frontend/dist/index.html" ]; then
    echo "错误: 未找到前端静态文件，请确保前端已正确构建"
    exit 1
else
    echo "前端静态文件检查通过，Nginx将提供前端服务"
fi

# 检查 .env 文件
if [ -f /app/.env ]; then
    echo "已找到 .env 文件，加载环境变量"
    # 更安全的环境变量加载方式
    while IFS= read -r line || [ -n "$line" ]; do
        # 跳过注释和空行
        [[ $line =~ ^[[:space:]]*# ]] && continue
        [[ -z $line ]] && continue
        
        # 确保行包含等号，并且有变量名
        if [[ $line == *"="* ]] && [[ $(echo "$line" | cut -d= -f1) != "" ]]; then
            # 提取变量名和值
            var_name=$(echo "$line" | cut -d= -f1)
            var_value=$(echo "$line" | cut -d= -f2-)
            
            # 导出变量
            export "$var_name=$var_value"
            echo "已加载环境变量: $var_name"
        else
            echo "警告: 跳过格式不正确的行: $line"
        fi
    done < /app/.env
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

# 检查Nginx配置
if [ ! -f /etc/nginx/conf.d/default.conf ]; then
    echo "错误: 未找到Nginx配置文件"
    exit 1
else
    echo "Nginx配置文件检查通过"
    echo "Nginx配置文件内容:"
    cat /etc/nginx/conf.d/default.conf
    
    # 检查是否有其他配置文件可能导致冲突
    echo "检查其他可能冲突的Nginx配置文件:"
    find /etc/nginx -type f -name "*.conf" | grep -v "/etc/nginx/conf.d/default.conf"
    
    # 测试Nginx配置是否有语法错误
    echo "测试Nginx配置语法:"
    nginx -t
fi

# 启动后端服务
echo "启动后端服务..."
cd /app && python -u backend/app.py &
BACKEND_PID=$!

# 等待后端服务启动
echo "等待后端服务启动..."
sleep 3

# 启动 Nginx
echo "启动 Nginx 服务(提供前端静态文件)..."
nginx -g "daemon off;" &
NGINX_PID=$!

# 捕获 SIGTERM 和 SIGINT 信号
trap "echo '正在关闭服务...'; kill $BACKEND_PID; kill $NGINX_PID; exit 0" SIGTERM SIGINT

# 输出访问信息
echo ""
echo "服务已启动!"
echo "架构说明:"
echo "- 前端: 由Nginx提供静态文件服务 (容器内端口: 80)"
echo "- 后端: Flask应用运行在0.0.0.0:5300"
echo "- Nginx: 将/api请求代理到后端服务"
echo "- 端口映射: 主机端口8080 -> 容器端口80"
echo "- 请求队列: 最大并发处理4个请求"
echo ""
echo "请通过以下地址访问应用:"
echo "http://localhost:8080 或 http://服务器IP:8080"
echo ""

# 等待任一进程结束
wait -n

# 如果有进程异常退出，则关闭所有服务
echo "检测到服务异常退出，正在关闭所有服务..."
kill $BACKEND_PID 2>/dev/null || true
kill $NGINX_PID 2>/dev/null || true
exit 1