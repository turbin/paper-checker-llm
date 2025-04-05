#!/bin/bash
# 使用bash而不是zsh，提高兼容性

# 定义颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

# 检测是否在WSL环境中运行（改进检测逻辑）
IS_WSL=false
if grep -q "microsoft\|WSL" /proc/version 2>/dev/null || uname -r | grep -q "microsoft\|WSL"; then
    IS_WSL=true
    echo -e "${YELLOW}检测到WSL环境${NC}"
fi

# 获取当前脚本所在的目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# 显示欢迎信息
echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN}       论文格式检查工具 - 启动脚本 v1.6          ${NC}"
echo -e "${GREEN}==================================================${NC}"

# 检查conda是否安装
if ! command -v conda &> /dev/null; then
    echo -e "${RED}错误: 未找到conda命令，请先安装Miniconda或Anaconda${NC}"
    echo -e "可以从以下链接下载安装："
    echo -e "${BLUE}Miniconda: https://docs.conda.io/en/latest/miniconda.html${NC}"
    echo -e "${BLUE}Anaconda: https://www.anaconda.com/products/distribution${NC}"
    exit 1
fi

# 检查环境变量文件
if [ ! -f .env ]; then
    echo -e "${YELLOW}警告: 未找到.env文件，将使用.env.example创建${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${YELLOW}已创建.env文件，请编辑填写正确的API密钥和其他参数${NC}"
        echo -e "${YELLOW}按Enter键继续，或Ctrl+C退出以先编辑.env文件${NC}"
        read -r
    else
        echo -e "${RED}错误: 未找到.env.example文件${NC}"
        exit 1
    fi
fi

# 检查关键环境变量是否设置
source .env
if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "<your api key>" ]; then
    echo -e "${RED}错误: 请在.env文件中设置有效的OPENAI_API_KEY${NC}"
    exit 1
fi

# 检查提示词模板目录
if [ ! -d "promots" ]; then
    echo -e "${RED}错误: 未找到promots目录，请确保项目结构完整${NC}"
    exit 1
fi

# 检查虚拟环境是否存在
ENV_NAME="paper-llm-checker"
if ! conda env list | grep -q "^$ENV_NAME "; then
    echo -e "${YELLOW}创建虚拟环境 $ENV_NAME...${NC}"
    conda env create -f environment.yml
    if [ $? -ne 0 ]; then
        echo -e "${RED}创建环境失败，请检查environment.yml文件${NC}"
        exit 1
    fi
fi

# 在WSL环境中检查前端依赖的兼容性问题
check_frontend_dependencies() {
    if [ "$IS_WSL" = true ] && [ -d "$SCRIPT_DIR/frontend/node_modules" ]; then
        echo -e "${YELLOW}检查前端依赖平台兼容性...${NC}"
        cd "$SCRIPT_DIR/frontend"
        
        # 检查是否有esbuild兼容性问题
        if [ -d "node_modules/esbuild" ]; then
            if [ -d "node_modules/@esbuild/darwin-x64" ] && [ ! -d "node_modules/@esbuild/linux-x64" ]; then
                echo -e "${RED}检测到esbuild平台兼容性问题!${NC}"
                echo -e "${YELLOW}发现macOS版esbuild，但在WSL中需要Linux版本${NC}"
                return 1
            elif [ -d "node_modules/@esbuild/win32-x64" ] && [ ! -d "node_modules/@esbuild/linux-x64" ]; then
                echo -e "${RED}检测到esbuild平台兼容性问题!${NC}"
                echo -e "${YELLOW}发现Windows版esbuild，但在WSL中需要Linux版本${NC}"
                return 1
            fi
        fi
        
        cd "$SCRIPT_DIR"
    fi
    return 0
}

# 检查前端依赖目录
if [ ! -d "frontend/node_modules" ] || ! check_frontend_dependencies; then
    echo -e "${YELLOW}前端依赖不存在或存在平台兼容性问题，将重新安装...${NC}"
    
    cd "$SCRIPT_DIR/frontend"
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}错误: 未找到npm命令，请先安装Node.js${NC}"
        exit 1
    fi
    
    # 清理现有依赖和缓存
    if [ -d "node_modules" ]; then
        echo -e "${YELLOW}删除现有node_modules目录...${NC}"
        rm -rf node_modules
    fi
    
    if [ -f "package-lock.json" ]; then
        echo -e "${YELLOW}删除package-lock.json...${NC}"
        rm package-lock.json
    fi
    
    # 清除npm缓存
    npm cache clean --force
    
    # 安装依赖
    echo -e "${YELLOW}安装前端依赖...${NC}"
    npm install --no-package-lock
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}安装前端依赖失败${NC}"
        echo -e "${YELLOW}将在启动时尝试使用fix_wsl_frontend.sh脚本修复${NC}"
    fi
    
    cd "$SCRIPT_DIR"
fi

# 检查后端日志目录
mkdir -p "$SCRIPT_DIR/backend/logs"
touch "$SCRIPT_DIR/backend/logs/paper_checker.log"

# 检查端口占用
check_port() {
    if command -v lsof &> /dev/null; then
        lsof -i:"$1" > /dev/null
        return $?
    elif command -v netstat &> /dev/null; then
        netstat -tuln | grep -q ":$1 "
        return $?
    else
        # 如果没有工具可用，假设端口可用
        return 1
    fi
}

BACKEND_PORT=5300
FRONTEND_PORT=3000

if check_port $BACKEND_PORT; then
    echo -e "${RED}错误: 端口 $BACKEND_PORT 已被占用，无法启动后端服务${NC}"
    exit 1
fi

if check_port $FRONTEND_PORT; then
    echo -e "${YELLOW}警告: 端口 $FRONTEND_PORT 已被占用，前端将尝试使用其他可用端口${NC}"
fi

# 激活虚拟环境
eval "$(conda shell.bash hook)"
conda activate $ENV_NAME

if [ $? -ne 0 ]; then
    echo -e "${RED}激活环境失败${NC}"
    exit 1
fi

echo -e "${GREEN}已激活环境: $ENV_NAME${NC}"

# 启动后端服务（后台运行）
echo -e "${GREEN}启动后端服务...${NC}"
cd "$SCRIPT_DIR/backend"
pip install -r requirements.txt

# WSL环境特殊处理
if [ "$IS_WSL" = true ]; then
    echo -e "${YELLOW}WSL环境下启动后端服务，强制绑定到0.0.0.0...${NC}"
    export FLASK_RUN_HOST="0.0.0.0"
fi

python app.py &
BACKEND_PID=$!

# 等待后端服务启动
echo -e "${YELLOW}等待后端服务启动...${NC}"
sleep 3

# 检查后端是否成功启动
if ! ps -p $BACKEND_PID > /dev/null; then
    echo -e "${RED}后端服务启动失败${NC}"
    exit 1
fi

# 启动前端服务
echo -e "${GREEN}启动前端服务...${NC}"

# 检查特殊情况：在WSL中但使用CMD/PowerShell启动
if [ "$IS_WSL" = true ] && [ -n "$WINDIR" ]; then
    echo -e "${RED}警告：检测到您在Windows终端(CMD/PowerShell)中启动WSL脚本${NC}"
    echo -e "${YELLOW}推荐在WSL终端中运行此脚本，或使用fix_wsl_frontend.sh${NC}"
    sleep 2
fi

# 确认前端目录和package.json存在
if [ ! -d "$SCRIPT_DIR/frontend" ]; then
    echo -e "${RED}错误: 前端目录不存在${NC}"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

cd "$SCRIPT_DIR/frontend"

if [ ! -f "$SCRIPT_DIR/frontend/package.json" ]; then
    echo -e "${RED}错误: 前端package.json不存在${NC}"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

# WSL环境特殊处理
if [ "$IS_WSL" = true ]; then
    echo -e "${YELLOW}WSL环境下启动前端服务...${NC}"
    
    # 确认node是否可用
    if ! command -v node &> /dev/null; then
        echo -e "${RED}错误: 在WSL中找不到node命令${NC}"
        kill $BACKEND_PID 2>/dev/null
        exit 1
    fi
    
    # 设置关键环境变量
    export VITE_BASE_URL="/"
    export NODE_OPTIONS="--no-warnings --max-old-space-size=4096"
    export CHOKIDAR_USEPOLLING=true
    
    # 直接运行修复脚本而不是尝试单独启动
    cd "$SCRIPT_DIR"
    
    echo -e "${YELLOW}WSL环境下使用专用修复脚本启动前端...${NC}"
    if [ -f "$SCRIPT_DIR/fix_wsl_frontend.sh" ]; then
        bash "$SCRIPT_DIR/fix_wsl_frontend.sh" &
        FRONTEND_PID=$!
    else
        echo -e "${RED}错误: 找不到fix_wsl_frontend.sh脚本${NC}"
        cd "$SCRIPT_DIR/frontend"
        # 退回到最简单的启动方式
        echo -e "${YELLOW}尝试直接启动...${NC}"
        if [ -f "./node_modules/vite/bin/vite.js" ]; then
            node ./node_modules/vite/bin/vite.js --host 0.0.0.0 &
            FRONTEND_PID=$!
        else
            echo -e "${RED}无法找到vite.js，前端服务无法启动${NC}"
            kill $BACKEND_PID 2>/dev/null
            exit 1
        fi
    fi
else
    # 非WSL环境，正常启动
    cd "$SCRIPT_DIR/frontend"

    # 检查node_modules目录
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}未检测到node_modules目录，开始安装依赖...${NC}"
        npm install
        
        if [ $? -ne 0 ]; then
            echo -e "${RED}安装依赖失败，尝试运行修复脚本...${NC}"
            cd "$SCRIPT_DIR"
            if [ -f "./fix_frontend.sh" ]; then
                bash ./fix_frontend.sh
                cd "$SCRIPT_DIR/frontend"
            else
                echo -e "${RED}未找到修复脚本，无法继续${NC}"
                kill $BACKEND_PID 2>/dev/null
                exit 1
            fi
        fi
    fi
    
    # 使用本地node_modules中的vite启动，而不是依赖全局安装
    if [ -f "./node_modules/.bin/vite" ]; then
        echo -e "${GREEN}检测到vite命令，开始启动服务...${NC}"
        ./node_modules/.bin/vite --host &
    elif [ -f "./node_modules/vite/bin/vite.js" ]; then
        echo -e "${GREEN}检测到vite.js，开始启动服务...${NC}"
        node ./node_modules/vite/bin/vite.js --host &
    else
        # 尝试安装并启动
        echo -e "${YELLOW}未找到vite，尝试安装...${NC}"
        npm install
        
        if [ -f "./node_modules/.bin/vite" ]; then
            ./node_modules/.bin/vite --host &
        elif [ -f "./node_modules/vite/bin/vite.js" ]; then
            node ./node_modules/vite/bin/vite.js --host &
        else
            echo -e "${RED}前端服务启动失败，尝试运行修复脚本...${NC}"
            cd "$SCRIPT_DIR"
            if [ -f "./fix_frontend.sh" ]; then
                bash ./fix_frontend.sh
                cd "$SCRIPT_DIR/frontend"
                # 再次尝试启动
                if [ -f "./node_modules/.bin/vite" ]; then
                    ./node_modules/.bin/vite --host &
                elif [ -f "./node_modules/vite/bin/vite.js" ]; then
                    node ./node_modules/vite/bin/vite.js --host &
                else
                    echo -e "${RED}修复后仍无法启动前端服务${NC}"
                    kill $BACKEND_PID 2>/dev/null
                    exit 1
                fi
            else
                echo -e "${RED}未找到修复脚本，无法继续${NC}"
                kill $BACKEND_PID 2>/dev/null
                exit 1
            fi
        fi
    fi
    
    FRONTEND_PID=$!
fi

# 检查前端是否成功启动
echo -e "${YELLOW}等待前端服务启动...${NC}"
sleep 10
if ! ps -p $FRONTEND_PID > /dev/null; then
    echo -e "${RED}前端服务启动失败${NC}"
    
    # 在WSL环境中，提供更明确的指导
    if [ "$IS_WSL" = true ]; then
        echo -e "${YELLOW}在WSL环境中，建议手动启动前端：${NC}"
        echo -e "${BLUE}1. 打开WSL终端（不是Windows CMD或PowerShell）${NC}"
        echo -e "${BLUE}2. 运行：cd $SCRIPT_DIR && bash fix_wsl_frontend.sh${NC}"
        echo -e "${BLUE}3. 或直接运行：cd $SCRIPT_DIR/frontend && node ./node_modules/vite/bin/vite.js --host 0.0.0.0${NC}"
        echo -e "${BLUE}4. 如果仍有问题，尝试：cd $SCRIPT_DIR/frontend && rm -rf node_modules && npm install${NC}"
    fi
    
    # 询问是否保持后端运行
    echo -e "${YELLOW}后端服务仍在运行。是否保持后端运行？(y/n)${NC}"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        kill $BACKEND_PID 2>/dev/null
        echo -e "${GREEN}已关闭后端服务${NC}"
        exit 1
    else
        echo -e "${GREEN}保持后端服务运行...${NC}"
    fi
fi

# 获取本机IP地址（用于远程访问）
get_ip_address() {
    if [ "$IS_WSL" = true ]; then
        # WSL环境下获取Windows主机的IP
        if command -v powershell.exe &> /dev/null; then
            WINDOWS_IP=$(powershell.exe -Command "Get-NetIPAddress | Where-Object {\$_.AddressFamily -eq 'IPv4' -and \$_.PrefixOrigin -eq 'Dhcp'} | Select-Object -ExpandProperty IPAddress" | head -1 | tr -d '\r')
            if [ ! -z "$WINDOWS_IP" ]; then
                echo "$WINDOWS_IP"
                return
            fi
        fi
        # 尝试获取WSL主机IP
        WSL_IP=$(ip addr show eth0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)
        if [ ! -z "$WSL_IP" ]; then
            echo "$WSL_IP"
            return
        fi
    fi
    
    # 标准Linux环境IP获取
    if command -v ip &> /dev/null; then
        ip addr show | grep -E "inet .* global" | grep -v docker | awk '{print $2}' | cut -d/ -f1 | head -n 1
    elif command -v ifconfig &> /dev/null; then
        ifconfig | grep -E "inet .*(broadcast|netmask)" | grep -v "127.0.0.1" | awk '{print $2}' | head -n 1
    else
        echo "无法获取IP地址"
    fi
}

LOCAL_IP=$(get_ip_address)

echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN}服务启动成功!${NC}"
echo -e "${BLUE}后端服务运行在: http://localhost:$BACKEND_PORT${NC}"
echo -e "${BLUE}前端服务运行在: http://localhost:$FRONTEND_PORT${NC}"

if [ "$IS_WSL" = true ]; then
    if [ ! -z "$LOCAL_IP" ] && [ "$LOCAL_IP" != "无法获取IP地址" ]; then
        echo -e "${BLUE}Windows主机访问地址: http://$LOCAL_IP:$FRONTEND_PORT${NC}"
        echo -e "${YELLOW}注意: 在WSL环境中，Windows浏览器可能需要使用上面的地址访问${NC}"
    fi
    echo -e "${YELLOW}WSL专用提示: 如果前端无法访问，请单独运行：${NC}"
    echo -e "${YELLOW}cd $SCRIPT_DIR && bash fix_wsl_frontend.sh${NC}"
else
    if [ ! -z "$LOCAL_IP" ] && [ "$LOCAL_IP" != "无法获取IP地址" ]; then
        echo -e "${BLUE}局域网访问地址: http://$LOCAL_IP:$FRONTEND_PORT${NC}"
    fi
fi

echo -e "${YELLOW}按 Ctrl+C 停止服务${NC}"
echo -e "${GREEN}==================================================${NC}"

# 捕获SIGINT信号（Ctrl+C），清理子进程
cleanup() {
    echo -e "\n${YELLOW}正在关闭服务...${NC}"
    kill $FRONTEND_PID 2>/dev/null
    kill $BACKEND_PID 2>/dev/null
    wait $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID 2>/dev/null
    echo -e "${GREEN}服务已关闭${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# 等待子进程
wait