@echo off
setlocal enabledelayedexpansion

:: 设置颜色
set "GREEN=[92m"
set "YELLOW=[93m"
set "BLUE=[94m"
set "NC=[0m"

:: 检查conda是否已安装
where conda >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo %YELLOW%未检测到conda。请先安装Miniconda或Anaconda。%NC%
    echo 可以从以下链接下载安装：
    echo %BLUE%Miniconda: https://docs.conda.io/en/latest/miniconda.html%NC%
    echo %BLUE%Anaconda: https://www.anaconda.com/products/distribution%NC%
    pause
    exit /b 1
)

:: 设置环境名称
set "ENV_NAME=paper-checker"
set "SCRIPT_DIR=%~dp0"

:: 显示菜单
:menu
cls
echo %GREEN%论文格式检查工具 - Conda环境管理%NC%
echo ----------------------------------------
echo 1. 创建新的conda环境
echo 2. 激活conda环境
echo 3. 更新conda环境
echo 4. 删除conda环境
echo 5. 列出所有conda环境
echo 6. 启动应用（在当前环境中）
echo 0. 退出
echo ----------------------------------------
set /p choice=请选择操作 [0-6]: 

if "%choice%"=="1" goto create_env
if "%choice%"=="2" goto activate_env
if "%choice%"=="3" goto update_env
if "%choice%"=="4" goto remove_env
if "%choice%"=="5" goto list_envs
if "%choice%"=="6" goto start_app
if "%choice%"=="0" goto exit
echo %YELLOW%无效选择，请重试。%NC%
pause
goto menu

:: 创建conda环境
:create_env
echo %YELLOW%正在创建conda环境: %ENV_NAME%...%NC%
call conda env create -f "%SCRIPT_DIR%environment.yml"
if %ERRORLEVEL% equ 0 (
    echo %GREEN%环境创建成功！%NC%
    echo 可以使用以下命令激活环境：
    echo %BLUE%conda activate %ENV_NAME%%NC%
) else (
    echo %YELLOW%环境创建失败，请检查错误信息。%NC%
)
pause
goto menu

:: 激活conda环境
:activate_env
echo %YELLOW%正在激活conda环境: %ENV_NAME%...%NC%
echo 请在命令提示符中手动运行以下命令：
echo %BLUE%conda activate %ENV_NAME%%NC%
echo %YELLOW%注意：由于批处理脚本的限制，无法直接在脚本中激活环境。%NC%
echo 您可以使用以下命令打开一个新的已激活环境的命令提示符：
echo %BLUE%start cmd /k "conda activate %ENV_NAME%"%NC%
set /p activate_now=是否立即打开新的已激活环境的命令提示符？(y/n): 
if /i "%activate_now%"=="y" (
    start cmd /k "conda activate %ENV_NAME% && cd /d %SCRIPT_DIR%"
)
pause
goto menu

:: 更新conda环境
:update_env
echo %YELLOW%正在更新conda环境: %ENV_NAME%...%NC%
call conda env update -f "%SCRIPT_DIR%environment.yml" --prune
if %ERRORLEVEL% equ 0 (
    echo %GREEN%环境更新成功！%NC%
) else (
    echo %YELLOW%环境更新失败，请检查错误信息。%NC%
)
pause
goto menu

:: 删除conda环境
:remove_env
echo %YELLOW%确定要删除conda环境: %ENV_NAME% 吗？%NC%
set /p confirm=请输入 'yes' 确认删除: 
if /i "%confirm%"=="yes" (
    call conda env remove -n %ENV_NAME%
    if %ERRORLEVEL% equ 0 (
        echo %GREEN%环境删除成功！%NC%
    ) else (
        echo %YELLOW%环境删除失败，请检查错误信息。%NC%
    )
) else (
    echo %BLUE%已取消删除操作。%NC%
)
pause
goto menu

:: 列出所有conda环境
:list_envs
echo %YELLOW%所有可用的conda环境:%NC%
call conda env list
pause
goto menu

:: 启动应用
:start_app
echo %YELLOW%正在启动论文格式检查工具...%NC%
echo %YELLOW%确保您已经激活了正确的conda环境！%NC%
python "%SCRIPT_DIR%app.py"
pause
goto menu

:: 退出
:exit
echo %GREEN%感谢使用！再见！%NC%
exit /b 0 