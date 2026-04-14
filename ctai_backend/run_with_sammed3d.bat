@echo off
REM SAM-Med3D 医学影像诊断平台启动脚本
REM 确保使用 sammed3D conda 环境

echo ========================================
echo SAM-Med3D 医学影像诊断平台
echo ========================================
echo.

REM 检查 conda 是否可用
where conda >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [错误] conda 未找到，请安装 Anaconda 或 Miniconda
    pause
    exit /b 1
)

REM 检查 sammed3d 环境是否存在
conda env list | findstr /i "sammed3d" >nul
if %ERRORLEVEL% NEQ 0 (
    echo [警告] sammed3d 环境不存在，正在创建...
    conda env create -f environment.yml
    if %ERRORLEVEL% NEQ 0 (
        echo [错误] 环境创建失败
        pause
        exit /b 1
    )
)

REM 激活环境
echo [信息] 激活 sammed3d 环境...
call conda activate sammed3d

REM 检查环境
echo [信息] 当前 Python: %PYTHON%
python --version
echo.

REM 设置环境变量
set SAM3D_MODEL_PATH=D:\Study\Project\JSJDS\demo\Model\best-epoch224-loss0.7188.pth
set SAM3D_CODE_PATH=D:\Study\Github\SAM-Med3D

echo [信息] SAM3D 模型路径: %SAM3D_MODEL_PATH%
echo [信息] SAM3D 代码路径: %SAM3D_CODE_PATH%
echo.

REM 运行 Flask 应用
echo [信息] 启动 Flask 应用...
python app.py

pause
