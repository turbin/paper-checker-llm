#!/bin/bash
# 简单的esbuild平台兼容性修复脚本

# 定义颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN}   esbuild WSL平台兼容性修复脚本   ${NC}"
echo -e "${GREEN}==================================================${NC}"

# 获取当前脚本所在的目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/frontend"

echo -e "${YELLOW}开始修复esbuild平台兼容性问题...${NC}"

# 删除现有node_modules目录
echo -e "${YELLOW}1. 删除node_modules目录...${NC}"
rm -rf node_modules

# 删除package-lock.json
echo -e "${YELLOW}2. 删除package-lock.json...${NC}"
if [ -f "package-lock.json" ]; then
    rm package-lock.json
fi

# 清除npm缓存
echo -e "${YELLOW}3. 清除npm缓存...${NC}"
npm cache clean --force

# 重新安装依赖
echo -e "${YELLOW}4. 安装依赖(为Linux平台)...${NC}"
npm install --no-package-lock

# 验证安装
echo -e "${YELLOW}5. 验证安装结果...${NC}"
if [ -d "node_modules/@esbuild/linux-x64" ]; then
    echo -e "${GREEN}成功: 已安装Linux版本的esbuild${NC}"
    echo -e "${GREEN}修复完成！${NC}"
else
    echo -e "${RED}安装失败, 尝试单独安装esbuild...${NC}"
    npm install @esbuild/linux-x64
    
    if [ -d "node_modules/@esbuild/linux-x64" ]; then
        echo -e "${GREEN}修复成功！${NC}"
    else
        echo -e "${RED}修复失败. 请尝试以下命令:${NC}"
        echo -e "${YELLOW}cd $SCRIPT_DIR/frontend && npm install esbuild --force${NC}"
    fi
fi

echo -e "${GREEN}==================================================${NC}"
echo -e "${YELLOW}现在可以尝试运行:${NC}"
echo -e "${BLUE}cd $SCRIPT_DIR && bash fix_wsl_frontend.sh${NC}"
echo -e "${GREEN}==================================================${NC}" 