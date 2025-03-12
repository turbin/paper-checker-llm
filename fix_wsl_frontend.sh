#!/bin/bash
# WSL前端修复脚本 v1.4

# 定义颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN}   WSL环境前端启动修复脚本 v1.4   ${NC}"
echo -e "${GREEN}==================================================${NC}"

# 检查是否运行在WSL中
if grep -qi microsoft /proc/version || grep -qi wsl /proc/version || uname -r | grep -qi "microsoft\|WSL"; then
    echo -e "${YELLOW}确认在WSL环境中运行${NC}"
else
    echo -e "${RED}警告: 此脚本设计用于WSL环境，但似乎您不在WSL中运行${NC}"
    echo -e "${YELLOW}如果您在Windows命令行中运行此脚本，请改用WSL终端${NC}"
    read -p "是否继续? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 检查是否在Windows CMD或PowerShell中运行WSL
if [ -n "$WINDIR" ]; then
    echo -e "${RED}警告：检测到您在Windows终端中运行WSL命令${NC}"
    echo -e "${YELLOW}这可能导致路径问题，建议在WSL终端中运行此脚本${NC}"
    sleep 2
fi

# 获取当前脚本所在的目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo -e "${YELLOW}正在WSL环境下单独启动前端服务...${NC}"

# 检查前端目录是否存在
if [ ! -d "$SCRIPT_DIR/frontend" ]; then
    echo -e "${RED}错误: 前端目录不存在${NC}"
    exit 1
fi

cd "$SCRIPT_DIR/frontend"

# 检查包管理文件是否存在
if [ ! -f "package.json" ]; then
    echo -e "${RED}错误: package.json不存在，请确认您在正确的目录中${NC}"
    exit 1
fi

# 检查npm和node是否可用
if ! command -v node &> /dev/null; then
    echo -e "${RED}错误: node命令不可用，请安装Node.js${NC}"
    echo -e "${YELLOW}WSL中安装Node.js: ${NC}"
    echo -e "${BLUE}curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash - ${NC}"
    echo -e "${BLUE}sudo apt-get install -y nodejs${NC}"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    echo -e "${RED}错误: npm命令不可用，请安装Node.js${NC}"
    exit 1
fi

# 显示Node.js版本信息
echo -e "${YELLOW}Node.js版本信息:${NC}"
node --version
npm --version

# 检查node版本是否满足要求
NODE_VERSION=$(node --version | cut -d 'v' -f 2)
NODE_MAJOR=$(echo $NODE_VERSION | cut -d '.' -f 1)
if [ $NODE_MAJOR -lt 18 ]; then
    echo -e "${RED}警告: 项目要求Node.js >= 18.0.0，当前版本为 ${NODE_VERSION}${NC}"
    echo -e "${YELLOW}尝试继续运行，但可能会出现兼容性问题${NC}"
fi

# 检查esbuild平台兼容性问题
echo -e "${YELLOW}检查esbuild平台兼容性...${NC}"
ESBUILD_PROBLEM=false
if [ -d "node_modules/esbuild" ]; then
    if [ -d "node_modules/@esbuild/darwin-x64" ] && [ ! -d "node_modules/@esbuild/linux-x64" ]; then
        echo -e "${RED}检测到esbuild平台兼容性问题!${NC}"
        echo -e "${YELLOW}发现macOS版esbuild，但缺少Linux版本${NC}"
        ESBUILD_PROBLEM=true
    elif [ -d "node_modules/@esbuild/win32-x64" ] && [ ! -d "node_modules/@esbuild/linux-x64" ]; then
        echo -e "${RED}检测到esbuild平台兼容性问题!${NC}"
        echo -e "${YELLOW}发现Windows版esbuild，但缺少Linux版本${NC}"
        ESBUILD_PROBLEM=true
    fi
fi

# 修复esbuild问题或安装依赖
if [ "$ESBUILD_PROBLEM" = true ] || [ ! -d "node_modules" ] || [ ! -d "node_modules/vite" ]; then
    echo -e "${YELLOW}需要重新安装前端依赖...${NC}"
    
    # 备份package.json
    cp package.json package.json.bak 2>/dev/null || true
    
    # 彻底删除node_modules目录（解决平台兼容性问题）
    echo -e "${YELLOW}删除现有node_modules目录...${NC}"
    rm -rf node_modules
    
    # 删除可能存在的损坏的package-lock.json
    if [ -f "package-lock.json" ]; then
        echo -e "${YELLOW}删除package-lock.json以确保重新安装...${NC}"
        rm package-lock.json
    fi
    
    # 清除npm缓存
    echo -e "${YELLOW}清除npm缓存...${NC}"
    npm cache clean --force
    
    # 尝试使用npm安装依赖
    echo -e "${YELLOW}为当前平台(linux-x64)安装依赖...${NC}"
    npm install --no-package-lock
    
    # 检查安装是否成功
    if [ ! -d "node_modules/vite" ] || [ ! -d "node_modules/@esbuild/linux-x64" ]; then
        echo -e "${YELLOW}使用--force重试安装...${NC}"
        npm install --force --no-package-lock
        
        # 再次检查
        if [ ! -d "node_modules/vite" ] || [ ! -d "node_modules/@esbuild/linux-x64" ]; then
            echo -e "${RED}依赖安装失败，尝试使用yarn安装...${NC}"
            if command -v yarn &> /dev/null; then
                yarn install
            else
                echo -e "${RED}所有安装方法均失败${NC}"
                echo -e "${YELLOW}尝试手动解决esbuild问题...${NC}"
                
                # 直接安装esbuild linux版本
                npm install @esbuild/linux-x64
                
                if [ ! -d "node_modules/@esbuild/linux-x64" ]; then
                    echo -e "${RED}无法解决esbuild平台兼容性问题${NC}"
                    exit 1
                fi
            fi
        fi
    fi
    
    echo -e "${GREEN}依赖安装完成${NC}"
fi

# 杀死可能存在的前端进程
echo -e "${YELLOW}清理可能存在的vite进程...${NC}"
pkill -f "vite" || true
sleep 2

# 设置环境变量
export VITE_HOST="0.0.0.0"
export VITE_PORT="3000"
export VITE_BASE_URL="/"
export NODE_OPTIONS="--no-warnings --max-old-space-size=4096"
export CHOKIDAR_USEPOLLING=true  # 启用轮询检测文件变化，对WSL很重要

# 备份原始vite配置
cp vite.config.js vite.config.js.bak 2>/dev/null || true

# 创建临时的简化vite配置
cat > vite.config.js.simple <<EOF
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/',
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: false,
    open: false
  }
})
EOF

echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN}准备启动vite开发服务器...${NC}"
echo -e "${YELLOW}尝试首先使用简化配置以避免问题${NC}"
echo -e "${GREEN}==================================================${NC}"

# 使用简化配置
cp vite.config.js.simple vite.config.js

# 检查是否安装了nvm并尝试使用
if [ -f "$HOME/.nvm/nvm.sh" ]; then
    echo -e "${YELLOW}检测到nvm，尝试使用...${NC}"
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm use 18 2>/dev/null || nvm use 20 2>/dev/null || true
fi

# 尝试运行vite（简单版本，最有可能成功）
echo -e "${YELLOW}方法1: 使用最简单的启动方式...${NC}"
if [ -f "./node_modules/vite/bin/vite.js" ]; then
    echo -e "${BLUE}服务启动后可以通过浏览器访问：http://localhost:3000${NC}"
    echo -e "${GREEN}正在启动，请稍候...${NC}"
    node ./node_modules/vite/bin/vite.js --host 0.0.0.0
else
    echo -e "${RED}找不到vite.js，尝试备选方法${NC}"
    # 恢复原始配置，可能对其他启动方式更好
    cp vite.config.js.bak vite.config.js 2>/dev/null || true
    
    echo -e "${YELLOW}方法2: 尝试使用npx启动...${NC}"
    echo -e "${BLUE}服务启动后可以通过浏览器访问：http://localhost:3000${NC}"
    npx vite --host 0.0.0.0
fi

# 如果上面的方法失败，这段代码会执行
echo -e "${RED}标准启动方法失败，尝试最后的备选方案${NC}"

# 使用npm脚本
echo -e "${YELLOW}方法3: 使用npm脚本...${NC}"
echo -e "${BLUE}服务启动后可以通过浏览器访问：http://localhost:3000${NC}"
npm run dev

# 如果所有方法都失败，提供诊断信息
echo -e "${RED}所有启动方法都失败。错误诊断信息:${NC}"
echo -e "${YELLOW}Node.js路径: $(which node)${NC}"
echo -e "${YELLOW}npm路径: $(which npm)${NC}"
echo -e "${YELLOW}当前目录: $(pwd)${NC}"
echo -e "${YELLOW}package.json内容:${NC}"
cat package.json | grep -A10 "scripts"
echo -e "${RED}================================${NC}"
echo -e "${RED}请尝试以下命令手动修复esbuild问题：${NC}"
echo -e "${YELLOW}cd $SCRIPT_DIR/frontend && rm -rf node_modules && npm install${NC}"
echo -e "${YELLOW}# 或者直接安装linux版本的esbuild：${NC}"
echo -e "${YELLOW}cd $SCRIPT_DIR/frontend && npm install @esbuild/linux-x64${NC}"
echo -e "${RED}================================${NC}"

# 恢复原始配置
cp vite.config.js.bak vite.config.js 2>/dev/null || true