#!/bin/bash

# 定义颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

# 检查conda是否已安装
if ! command -v conda &> /dev/null; then
    echo -e "${YELLOW}未检测到conda。请先安装Miniconda或Anaconda。${NC}"
    echo -e "可以从以下链接下载安装："
    echo -e "${BLUE}Miniconda: https://docs.conda.io/en/latest/miniconda.html${NC}"
    echo -e "${BLUE}Anaconda: https://www.anaconda.com/products/distribution${NC}"
    exit 1
fi

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
ENV_NAME="paper-checker"

# 显示菜单
show_menu() {
    echo -e "${GREEN}论文格式检查工具 - Conda环境管理${NC}"
    echo "----------------------------------------"
    echo "1. 创建新的conda环境"
    echo "2. 激活conda环境"
    echo "3. 更新conda环境"
    echo "4. 删除conda环境"
    echo "5. 列出所有conda环境"
    echo "6. 启动应用（在当前环境中）"
    echo "0. 退出"
    echo "----------------------------------------"
    echo -n "请选择操作 [0-6]: "
}

# 创建conda环境
create_env() {
    echo -e "${YELLOW}正在创建conda环境: $ENV_NAME...${NC}"
    conda env create -f "$SCRIPT_DIR/environment.yml"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}环境创建成功！${NC}"
        echo -e "可以使用以下命令激活环境："
        echo -e "${BLUE}conda activate $ENV_NAME${NC}"
    else
        echo -e "${YELLOW}环境创建失败，请检查错误信息。${NC}"
    fi
}

# 激活conda环境
activate_env() {
    echo -e "${YELLOW}正在激活conda环境: $ENV_NAME...${NC}"
    echo -e "请在终端中手动运行以下命令："
    echo -e "${BLUE}conda activate $ENV_NAME${NC}"
    echo -e "${YELLOW}注意：由于bash脚本的限制，无法直接在脚本中激活环境。${NC}"
}

# 更新conda环境
update_env() {
    echo -e "${YELLOW}正在更新conda环境: $ENV_NAME...${NC}"
    conda env update -f "$SCRIPT_DIR/environment.yml" --prune
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}环境更新成功！${NC}"
    else
        echo -e "${YELLOW}环境更新失败，请检查错误信息。${NC}"
    fi
}

# 删除conda环境
remove_env() {
    echo -e "${YELLOW}确定要删除conda环境: $ENV_NAME 吗？${NC}"
    read -p "请输入 'yes' 确认删除: " confirm
    if [ "$confirm" = "yes" ]; then
        conda env remove -n $ENV_NAME
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}环境删除成功！${NC}"
        else
            echo -e "${YELLOW}环境删除失败，请检查错误信息。${NC}"
        fi
    else
        echo -e "${BLUE}已取消删除操作。${NC}"
    fi
}

# 列出所有conda环境
list_envs() {
    echo -e "${YELLOW}所有可用的conda环境:${NC}"
    conda env list
}

# 启动应用
start_app() {
    echo -e "${YELLOW}正在启动论文格式检查工具...${NC}"
    echo -e "${YELLOW}确保您已经激活了正确的conda环境！${NC}"
    python "$SCRIPT_DIR/app.py"
}

# 主循环
while true; do
    show_menu
    read choice
    case $choice in
        1) create_env ;;
        2) activate_env ;;
        3) update_env ;;
        4) remove_env ;;
        5) list_envs ;;
        6) start_app ;;
        0) echo -e "${GREEN}感谢使用！再见！${NC}"; exit 0 ;;
        *) echo -e "${YELLOW}无效选择，请重试。${NC}" ;;
    esac
    echo ""
    read -p "按Enter键继续..."
    clear
done 