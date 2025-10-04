@echo off
chcp 65001 >nul
title Bilibili视频字幕下载与总结工具

echo ================================================================================
echo Bilibili视频字幕下载与总结工具
echo ================================================================================
echo.
echo 正在启动Web服务...
echo.

python start_web.py

if %errorlevel% neq 0 (
    echo.
    echo ================================================================================
    echo 启动失败！
    echo ================================================================================
    echo.
    echo 可能的原因：
    echo 1. 未安装Python或Python未添加到PATH
    echo 2. 缺少依赖包
    echo.
    echo 解决方法：
    echo 1. 安装Python 3.8或更高版本
    echo 2. 运行: pip install -r requirements.txt
    echo 3. 或使用打包版本（无需Python环境）
    echo.
    pause
    exit /b 1
)

