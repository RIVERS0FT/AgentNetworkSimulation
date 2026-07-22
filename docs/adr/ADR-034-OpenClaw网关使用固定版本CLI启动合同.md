# ADR-034：OpenClaw 网关使用固定版本 CLI 启动合同

- 状态：已接受并实现
- 日期：2026-07-22
- 关联需求：SR-SIM-05、SR-LOG-06
- 扩展决策：ADR-032

## 背景

项目固定使用 OpenClaw `2026.7.1-2`。实际镜像构建与容器冒烟测试发现，该版本不再接受旧命令 `openclaw gateway --host <host> --port <port>`，CLI 会立即返回 `OpenClaw does not recognize option "--host"`。启动脚本随后持续等待一个不会出现的端口，最终导致所有 OpenClaw Agent 容器分配失败，仿真以 `one or more Agent containers could not be assigned` 终止。

固定 npm 包版本但不固定对应 CLI 调用合同，仍会把不兼容问题推迟到运行时。OpenClaw 网关的启动命令必须与仓库锁定版本一起受测试约束。

## 决定

1. 内置 OpenClaw `2026.7.1-2` 网关使用前台运行命令：

   ```text
   openclaw gateway run --bind loopback --port ${OPENCLAW_GATEWAY_PORT}
   ```

2. 内置命令只支持容器内 loopback 网关，允许的 `OPENCLAW_GATEWAY_HOST` 为 `127.0.0.1` 或 `localhost`。这与 Gateway 和 Agent Server 位于同一容器、SDK 连接本地 WebSocket 的运行边界一致。
3. 非 loopback 或供应商自定义启动方式必须显式设置 `OPENCLAW_GATEWAY_CMD`；启动脚本不得猜测地址到 `--bind` 模式的映射。
4. 受版本控制的 `openclaw.json` 显式声明 `gateway.mode=local` 和 `gateway.bind=loopback`。不使用 `--allow-unconfigured` 绕过配置校验，避免将缺失或被破坏的配置静默视为可信。
5. 未找到 CLI、内置地址不受支持、配置无效、命令退出或端口超时均保持严格失败，不允许退化到 direct LLM。
6. 增加源码契约测试，固定 `gateway run`、`--bind loopback`、端口参数和本地模式配置，并禁止恢复已移除的 `--host` 或宽松启动参数。

## 影响范围与不变边界

- 影响：OpenClaw 容器启动脚本、原生能力回归测试、OpenClaw 部署指南、Agent 运行边界设计。
- 不改变：OpenClaw 与 SDK 版本、Gateway WebSocket URL、审计 Plugin、Agent API、场景模型、容器池分配策略和 A2A 通信路径。
- 本 ADR 不放宽原生能力授权或审计失败关闭规则，也不修改任何已有 ADR 正文。

## 被放弃方案

1. **继续使用 `--host` 并等待上游兼容**：放弃。锁定版本已经明确拒绝该参数，运行必然失败。
2. **不执行 `gateway run`，仅调用 `openclaw gateway`**：放弃。该命令是管理入口，不是明确的前台网关运行合同。
3. **根据任意 IP 自动推导 `--bind`**：放弃。OpenClaw 的 `--bind` 是语义模式而非原始地址，错误推导会造成暴露范围或连通性偏差。
4. **使用 `--allow-unconfigured` 绕过缺失的 `gateway.mode`**：放弃。配置缺失应通过受版本控制的显式本地模式修复，不能降低启动校验强度。
5. **Gateway 启动失败时直接调用模型**：放弃。违反 OpenClaw 严格后端和审计边界。

## 迁移、失败与回滚

- 迁移：重新构建 `agentnetwork-ag-o1` 镜像；已由旧镜像创建且无法启动的容器不得继续进入运行池。
- 失败语义：自定义非 loopback 地址未提供 `OPENCLAW_GATEWAY_CMD` 时立即失败并给出明确错误；Gateway 进程或端口异常继续由现有超时和退出逻辑处理。
- 回滚：同时回滚脚本、测试、指南、设计记录和本 ADR。不得单独恢复 `--host`，除非先升级或降级锁定版本并以实际 CLI 验证新合同。

## 实现映射

- 启动命令与失败检查：`docker/start-openclaw-agent.sh`；
- 本地 Gateway 模式：`docker/openclaw.json`；
- 镜像入口：`docker/Dockerfile.openclaw`；
- 版本锁定：`docker-compose.yml`；
- 回归测试：`tests/test_native_capabilities.py`；
- 部署与验收：`docs/guides/OpenCLAWDeployment.md`、`scripts/check-openclaw-runtime.sh`；
- 运行边界：`docs/design/AgentRuntimeBoundary.md`。

## 验证

预期执行：

```bash
python3 -m pytest tests/test_native_capabilities.py tests/test_docs_layout.py -q
node --check docker/openclaw-audit-plugin/index.mjs
docker compose config --quiet
docker compose build ag-o1
./scripts/check-openclaw-runtime.sh ag-o1
python3 scripts/check_design_traceability.py
git diff --check
```

2026-07-22 实际结果：

- `python3 -m pytest tests/test_native_capabilities.py tests/test_docs_layout.py -q`：通过，14 项测试全部通过；
- `node --check docker/openclaw-audit-plugin/index.mjs`：通过；
- `docker compose config --quiet`：通过；
- 固定版本 CLI 执行 `openclaw config validate`：通过，`docker/openclaw.json` 有效；
- `docker compose build ag-o1`：通过，镜像入口包含 `/app/start-openclaw-agent.sh`，OpenClaw SDK 2.1.0 导入校验通过；
- 隔离容器冒烟：以 `MOCK_LLM=1` 启动新镜像，Gateway 使用 `gateway run --bind loopback` 进入 `ready`，端口 `18789` 开放，Agent Server `/status` 返回 `backend=openclaw`；临时容器已停止并删除；
- `python3 scripts/check_design_traceability.py`：通过，识别到 ADR-034、ADR 索引和 AgentRuntimeBoundary 设计记录；
- `git diff --check`：通过；
- `scripts/check-openclaw-runtime.sh ag-o1` 未直接执行：该脚本要求启动长期 Compose 服务；本次使用相同镜像、环境边界、Gateway 端口和 `/status` 检查完成隔离等价验证，未调用模型。
