# OpenCLAW 后端部署与验收

目标：`AGENT_BACKEND=openclaw` 必须代表容器里真实运行 OpenCLAW Gateway 与 `openclaw-sdk`。OpenCLAW 缺失、Gateway 起不来、SDK 不可导入，都应失败；不能静默退化成 direct LLM。

## 运行模式

默认 `ag-o1` 使用 self-contained OpenCLAW 模式：

```text
ag-o1 container
  -> start-openclaw-agent.sh
    -> validate openclaw-sdk import
    -> start local OpenCLAW gateway
    -> wait for gateway port
    -> start services/agent_server.py
      -> AGENT_BACKEND=openclaw
      -> OpenCLAWAdapter
```

如果确实不想跑 OpenCLAW，只想直接调用模型，请显式设置：

```yaml
AGENT_BACKEND: direct_llm
```

不要把 direct LLM 当作 OpenCLAW fallback 使用。

## 构建前置条件

### 1. Gateway npm 包

Compose 默认传入：

```bash
OPENCLAW_GATEWAY_NPM_PACKAGE=openclaw@latest
```

如果真实包名不同，启动前覆盖它：

```bash
export OPENCLAW_GATEWAY_NPM_PACKAGE='<real-openclaw-gateway-package>'
```

如果包安装后没有提供 `openclaw gateway` 命令，设置：

```bash
export OPENCLAW_GATEWAY_CMD='<real gateway start command --host 127.0.0.1 --port 18789>'
```

### 2. openclaw-sdk wheel

构建镜像前必须存在：

```text
vendor/python/openclaw_sdk-*.whl
```

缺少该 wheel 时，`docker compose build ag-o1` 会直接失败。

## 启动

```bash
docker compose build ag-o1
docker compose up -d bus srv ag-o1
```

查看日志：

```bash
docker compose logs -f ag-o1
```

期望看到：

```text
[openclaw-agent] openclaw-sdk import ok
[openclaw-agent] starting OpenCLAW gateway: ...
[openclaw-agent] gateway port is open
[openclaw-agent] starting AgentNetwork server...
```

## 一键验收

```bash
chmod +x scripts/check-openclaw-runtime.sh
./scripts/check-openclaw-runtime.sh ag-o1
```

通过时应看到：

```text
[check-openclaw] OK: strict OpenCLAW runtime checks passed.
```

## 手动验收命令

### 1. 确认容器状态

```bash
docker compose ps ag-o1
```

### 2. 确认 backend 是 OpenCLAW 且严格模式开启

```bash
docker compose exec -T ag-o1 sh -lc 'echo AGENT_BACKEND=$AGENT_BACKEND; echo AGENT_STRICT_BACKEND_SDK=$AGENT_STRICT_BACKEND_SDK'
```

期望：

```text
AGENT_BACKEND=openclaw
AGENT_STRICT_BACKEND_SDK=1
```

### 3. 确认 Gateway 命令存在

```bash
docker compose exec -T ag-o1 sh -lc 'command -v openclaw || echo "$OPENCLAW_GATEWAY_CMD"'
```

### 4. 确认 openclaw-sdk 可导入

```bash
docker compose exec -T ag-o1 python3 - <<'PY'
from openclaw_sdk import OpenClawClient
print('openclaw_sdk import ok')
print(OpenClawClient)
PY
```

### 5. 确认 Gateway 端口开放

```bash
docker compose exec -T ag-o1 python3 - <<'PY'
import os, socket
host = os.environ.get('OPENCLAW_GATEWAY_HOST', '127.0.0.1')
port = int(os.environ.get('OPENCLAW_GATEWAY_PORT', '18789'))
with socket.create_connection((host, port), timeout=3):
    print(f'gateway port open: {host}:{port}')
PY
```

### 6. 确认 Agent HTTP 状态

```bash
curl -fsS http://localhost:8000/status | python3 -m json.tool
```

期望 JSON 中有：

```json
{
  "backend": "openclaw"
}
```

### 7. 确认没有 fallback 日志

```bash
! docker compose logs --no-color ag-o1 | grep -Ei 'openclaw-direct-llm|direct_llm|fallback'
```

如果该命令返回 0，说明没有发现 direct LLM / fallback 标记。

## 常见失败

### 缺 Gateway npm 包

构建失败，提示：

```text
OPENCLAW_GATEWAY_NPM_PACKAGE is required
```

修复：

```bash
export OPENCLAW_GATEWAY_NPM_PACKAGE='<real-openclaw-gateway-package>'
docker compose build ag-o1
```

### 缺 openclaw-sdk wheel

构建失败，提示：

```text
openclaw-sdk wheel is required in vendor/python/
```

修复：把兼容当前 Python 版本的 `openclaw_sdk-*.whl` 放入 `vendor/python/` 后重新构建。

### Gateway 命令不存在

运行失败，提示：

```text
OPENCLAW_START_GATEWAY=1 but no OpenCLAW gateway command was found
```

修复：确认 npm 包确实安装了 `openclaw` CLI，或设置 `OPENCLAW_GATEWAY_CMD`。

### Gateway 端口未开放

运行失败，提示：

```text
OpenCLAW gateway did not become ready before timeout
```

修复：查看 `docker compose logs ag-o1` 中 Gateway 的实际错误，确认端口、依赖、API key 和启动命令。
