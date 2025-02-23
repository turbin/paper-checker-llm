#!/bin/zsh

# 检查conda是否安装
if ! command -v conda &> /dev/null; then
    echo "错误: 未找到conda命令，请先安装Miniconda或Anaconda"
    exit 1
fi

# 检查虚拟环境是否存在
if ! conda env list | grep -q "^paper-llm-checker "; then
    echo "创建虚拟环境 paper-llm-checker..."
    conda env create -f environment.yml
fi

# 激活虚拟环境
eval "$(conda shell.bash hook)"
conda activate paper-llm-checker

# 启动后端服务（后台运行）
cd backend
pip install -r requirements.txt
python app.py &
BACKEND_PID=$!

# 等待后端服务启动
sleep 3

# 启动前端服务
cd ../frontend
npm install
npm run dev &
FRONTEND_PID=$!

# 捕获SIGINT信号（Ctrl+C），清理子进程
cleanup() {
    echo "正在关闭服务..."
    kill $FRONTEND_PID
    kill $BACKEND_PID
    exit 0
}

trap cleanup SIGINT

# 等待子进程
wait