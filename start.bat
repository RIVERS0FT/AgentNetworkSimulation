@echo off
cd /d "%~dp0"
setlocal enabledelayedexpansion

echo =============================================
echo   AI Agent 仿真运行平台 - 一键启动
echo =============================================

REM --- 1. Build frontend if not yet built ---
if not exist "web\tactical-map\dist\index.html" (
    echo [1/4] 构建前端...
    cd web\tactical-map
    call npx vite build
    cd ..\..
    echo   前端构建完成
) else (
    echo [1/4] 前端已构建 (跳过)
)

REM --- 2. Start Message Bus ---
echo [2/4] 启动 Message Bus ^(端口 9000^)...
start "AgentNetwork-MessageBus" python message_bus.py
timeout /t 2 /nobreak > nul

REM --- 3. Start Main Server ---
echo [3/4] 启动主服务 ^(端口 8000^)...
start "AgentNetwork-Server" python server.py
timeout /t 3 /nobreak > nul

REM --- 4. Done ---
echo [4/4] 启动完成
echo.
echo   ^> 控制台:    http://localhost:8000/
echo   ^> 战术地图:  http://localhost:8000/tactical-map
echo   ^> API 文档:  http://localhost:8000/docs
echo.
echo   按任意键停止所有服务...

pause > nul

echo.
echo 正在停止服务...
taskkill /FI "WINDOWTITLE eq AgentNetwork-MessageBus" /F 2>nul
taskkill /FI "WINDOWTITLE eq AgentNetwork-Server" /F 2>nul
echo 已停止所有服务
