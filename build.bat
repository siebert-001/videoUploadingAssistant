@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   光厂视频上架助手 - 单文件 exe 打包
echo   （本机 Google Chrome，无自带 Chromium）
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] 创建虚拟环境...
    python -m venv .venv
    call .venv\Scripts\pip install -r requirements.txt -q
)

call .venv\Scripts\activate

echo [2/3] 安装打包依赖...
pip install pyinstaller -q

echo [3/3] PyInstaller 单文件编译（约 2~5 分钟）...
python -m PyInstaller build.spec --noconfirm --clean
if errorlevel 1 (
    echo 打包失败。
    pause
    exit /b 1
)

echo.
echo ========================================
echo   打包完成
echo   文件: dist\光厂视频上架助手.exe
echo   要求: 已安装 Google Chrome
echo   说明: 首次启动略慢（需解压临时文件）
echo   登录: 首次登录后生成 login.json（与 exe 同目录）
echo ========================================
pause
