#!/bin/bash
set -e

# 定义颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # 无颜色

# 定义端口配置
BACKEND_PORT=5300
FRONTEND_PORT=5173
NGINX_PORT=8087

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 输出环境信息
echo -e "${GREEN}=== 环境信息 ===${NC}"
echo "Python 版本: $(python --version)"
echo "Node 版本: $(node --version 2>/dev/null || echo '未安装')"
echo "当前目录: $(pwd)"
echo -e "${GREEN}==================${NC}"

# 检查端口占用
check_port() {
    if command -v lsof &> /dev/null; then
        lsof -i:"$1" > /dev/null
        return $?
    elif command -v netstat &> /dev/null; then
        netstat -tuln | grep -q ":$1 "
        return $?
    else
        return 1
    fi
}

# 检查端口是否被占用
echo "检查端口占用..."
if check_port $BACKEND_PORT; then
    echo -e "${RED}错误: 端口 $BACKEND_PORT 已被占用${NC}"
    exit 1
fi

if check_port $NGINX_PORT; then
    echo -e "${RED}错误: 端口 $NGINX_PORT 已被占用${NC}"
    exit 1
fi

# 检查必要的目录
echo "检查目录结构..."
mkdir -p backend/logs
mkdir -p backend/output
mkdir -p backend/uploads
mkdir -p promots

# 检查Python依赖
echo "检查Python依赖..."
if ! command -v python &> /dev/null; then
    echo -e "${RED}错误: 未找到Python命令${NC}"
    exit 1
fi

# 检查Node.js依赖
echo "检查Node.js依赖..."
if ! command -v node &> /dev/null; then
    echo -e "${RED}错误: 未找到Node.js命令${NC}"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo -e "${RED}错误: 未找到npm命令${NC}"
    exit 1
fi

# 检查前端依赖
if [ ! -d "frontend/node_modules" ]; then
    echo "安装前端依赖..."
    cd frontend
    npm install
    cd ..
fi

# 检查 Vite 是否安装
if ! command -v vite &> /dev/null; then
    echo "安装 Vite..."
    cd frontend
    npm install vite --save-dev
    cd ..
fi

# 检查后端依赖
if [ ! -d "backend/venv" ]; then
    echo "创建并激活Python虚拟环境..."
    cd backend
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd ..
fi

# 检查环境变量文件
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}警告: 未找到 .env 文件，创建示例文件...${NC}"
    cat > .env << EOL
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://api.moonshot.cn/v1
MODEL_NAME=moonshot-v1-8k
EOL
    echo -e "${YELLOW}请编辑 .env 文件并填入正确的API密钥${NC}"
    exit 1
fi

# 检查模板文件
if [ ! -f "promots/sunshine.ruler" ] || [ ! -f "promots/xmu.ruler" ]; then
    echo -e "${RED}错误: 缺少必要的模板文件${NC}"
    exit 1
fi

# 启动后端服务
echo "启动后端服务..."
cd backend
source venv/bin/activate
export PYTHONPATH=$PYTHONPATH:$(pwd)/..
export FLASK_ENV=development
export FLASK_DEBUG=1
python -m backend.run &
BACKEND_PID=$!
cd ..

# 等待后端服务启动
echo "等待后端服务启动..."
sleep 5

# 检查后端服务是否正常运行
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}后端服务启动失败${NC}"
    exit 1
fi

# 启动前端开发服务器
echo "启动前端开发服务器..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# 捕获 SIGTERM 和 SIGINT 信号
cleanup() {
    echo -e "\n${YELLOW}正在关闭服务...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID 2>/dev/null
    wait $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}服务已关闭${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 输出访问信息
echo -e "\n${GREEN}服务已启动!${NC}"
echo -e "${GREEN}架构说明:${NC}"
echo "- 前端: 开发服务器运行在 http://localhost:$FRONTEND_PORT"
echo "- 后端: Flask应用运行在 http://localhost:$BACKEND_PORT"
echo "- Nginx: 代理服务器运行在 http://localhost:$NGINX_PORT"
echo ""
echo -e "${GREEN}请通过以下地址访问应用:${NC}"
echo "http://localhost:$NGINX_PORT"
echo ""
echo -e "${YELLOW}按 Ctrl+C 停止服务${NC}"

# 使用无限循环等待进程结束
while true; do
    if ! kill -0 $BACKEND_PID 2>/dev/null || ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo -e "${RED}检测到服务异常退出，正在关闭所有服务...${NC}"
        kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done