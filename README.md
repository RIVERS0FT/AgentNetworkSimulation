# AI Agent 仿真运行平台

企业级 AI Agent 仿真、推演与编排平台。提供可编程场景、多 Agent 协作、华为智慧园区数字孪生地图。

## 快速启动

### 1. 安装依赖
```bash
pip install -r requirements.txt
cd web/tactical-map && npm install
```

### 2. 一键启动
双击 `start.bat` 或在终端运行：
```bash
start.bat
```

### 3. 访问
- 控制台: http://localhost:8000/
- 战术地图: http://localhost:8000/tactical-map
- API 文档: http://localhost:8000/docs

### 开发模式（热重载）
```bash
# 终端1: Vite HMR
cd web/tactical-map && npx vite

# 终端2: Python 后端
python server.py

# 访问 Vite 热重载: http://localhost:5173/tactical-map/
```

## 架构
- **后端**: FastAPI + Uvicorn, 消息总线, Agent 引擎 (`agent_network/`)
- **前端**: React + Vite + TailwindCSS v4 (`web/tactical-map/`)
- **Dashboard**: 原生 HTML/CSS/JS (`web/dashboard.*`)

详见 [开发文档](开发文档.md) 和 [设计系统](WebStyle.md)。
