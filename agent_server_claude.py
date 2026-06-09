#!/usr/bin/env python3
"""
Agent 容器运行时 — Claude Code 后端

每个 Agent 运行在独立 Docker 容器中。
决策流程: 构建 prompt → subprocess claude -p --print → 解析 Action → 执行

环境变量:
  AGENT_ID / AGENT_ROLE / AGENT_NAME / PORT
  MESSAGE_BUS_URL / SERVER_URL
  AGENT_CORE_GOAL / AGENT_HIDDEN_SECRET / AGENT_ACTION_SPACE / AGENT_INITIAL_ASSETS
  AGENT_SYSTEM_PROMPT (from scene background_rules)
  ANTHROPIC_API_KEY (Claude Code 会从环境变量读取)
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime, timezone
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uvicorn
import requests

from agent_network.comm import RemoteBus

# ── Agent 身份 ──
AGENT_ID = os.environ.get("AGENT_ID", "agent-001")
AGENT_ROLE = os.environ.get("AGENT_ROLE", "generic")
AGENT_NAME = os.environ.get("AGENT_NAME", AGENT_ID)
AGENT_PORT = int(os.environ.get("PORT", "8000"))
MESSAGE_BUS = os.environ.get("MESSAGE_BUS_URL", "http://localhost:9000")
SERVER_URL = os.environ.get("SERVER_URL", "http://localhost:8000")

AGENT_CORE_GOAL = os.environ.get("AGENT_CORE_GOAL", "")
AGENT_HIDDEN_SECRET = os.environ.get("AGENT_HIDDEN_SECRET", "")
AGENT_ACTION_SPACE = json.loads(os.environ.get("AGENT_ACTION_SPACE", "[]"))
AGENT_INITIAL_ASSETS = json.loads(os.environ.get("AGENT_INITIAL_ASSETS", "{}"))
AGENT_SYSTEM_PROMPT = os.environ.get("AGENT_SYSTEM_PROMPT", "")
LOG_COLLECTOR_URL = os.environ.get("LOG_COLLECTOR_URL", "")
PACKET_MONITOR_URL = os.environ.get("PACKET_MONITOR_URL", "")

# ── 通信层 ──
comm = RemoteBus(message_bus_url=MESSAGE_BUS, server_url=SERVER_URL)

# ── FastAPI ──
app = FastAPI(title=f"Agent {AGENT_NAME} (Claude Code)")

turn = 0
last_action: Dict[str, Any] = {}
inbox: list = []


def _log_agent(event: str, detail: str, **kw):
    """结构化动作日志上报"""
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    try:
        requests.post(f"{SERVER_URL}/api/logs/agent", json={
            "agent_id": AGENT_ID, "agent_name": AGENT_NAME,
            "event": event, "detail": detail,
            "timestamp": timestamp,
            "from_agent": AGENT_ID,
            "to_agent": kw.get("target", kw.get("to", "")),
            "action": kw.get("action_type", event),
            "action_status": kw.get("status", "success"),
            "details": kw or {},
        }, timeout=2)
    except Exception:
        pass


def _call_claude_code(prompt: str) -> str:
    """Call Claude Code CLI in print mode (non-interactive)."""
    env = os.environ.copy()
    # Ensure Claude Code doesn't try interactive mode
    result = subprocess.run(
        ["claude", "-p", prompt, "--print", "--output-format", "text"],
        capture_output=True, text=True, timeout=120,
        cwd="/app", env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude Code failed (exit {result.returncode}): {result.stderr[:500]}")
    return result.stdout.strip()


def _build_prompt(inbox_msgs: list, context: dict = None) -> str:
    """Build the prompt for Claude Code."""
    context = context or {}
    known = context.get("known_agents", [])
    known_list = "\n".join(
        f"  - {a.get('name', a.get('agent_id', '?'))} ({a.get('role', '?')}) agent_id={a.get('agent_id', '?')}"
        for a in known) if known else "  none"

    inbox_text = "（空）"
    if inbox_msgs:
        inbox_text = "\n".join(
            f"  [{msg.get('from', '?')}]: {msg.get('content', '')}"
            for msg in inbox_msgs[-5:]
        )

    actions_text = ", ".join(AGENT_ACTION_SPACE) if AGENT_ACTION_SPACE else "send_message, wait"

    system = AGENT_SYSTEM_PROMPT or "你是一个仿真场景中的角色，根据你的身份和目标做出决策。"

    return f"""{system}

## 你的身份
- 名字: {AGENT_NAME}
- 角色: {AGENT_ROLE}
- 核心目标: {AGENT_CORE_GOAL or '完成场景任务'}
- 隐藏秘密: {AGENT_HIDDEN_SECRET or '无'}
- 可用行动: {actions_text}
- 初始资产: {json.dumps(AGENT_INITIAL_ASSETS, ensure_ascii=False) if AGENT_INITIAL_ASSETS else '无'}

## 当前回合: {turn}
## 已知其它 Agent:
{known_list}

## 收件箱:
{inbox_text}

## 指令
做出本轮决策。用 JSON 回复（只输出 JSON）：
```json
{{"reasoning": "推理", "action": "send_message|broadcast|wait", "target": "目标agent_id", "content": "内容"}}
```
注意: target 必须用 agent_id（如 role_a），不是中文名。"""


def _parse_response(text: str) -> dict:
    """Parse JSON action from Claude Code response."""
    json_match = re.search(r'\{[\s\S]*"action"[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    return {"reasoning": "parse error", "action": "wait", "target": "", "content": text[:200]}


# ── HTTP API ──

class MessageIn(BaseModel):
    from_id: str
    from_name: str = ""
    content: str
    type: str = "message"


class DecideRequest(BaseModel):
    context: Dict[str, Any] = {}


@app.get("/status")
async def status():
    return {
        "agent_id": AGENT_ID, "name": AGENT_NAME, "role": AGENT_ROLE,
        "backend": "claude-code", "turn": turn,
        "inbox_size": len(inbox), "core_goal": AGENT_CORE_GOAL or None,
        "hidden_secret": AGENT_HIDDEN_SECRET or None,
        "action_space": AGENT_ACTION_SPACE, "initial_assets": AGENT_INITIAL_ASSETS,
        "last_action": last_action,
    }


@app.post("/message")
async def receive_message(msg: MessageIn):
    inbox.append({"from": msg.from_name or msg.from_id, "content": msg.content, "type": msg.type})
    if len(inbox) > 50:
        inbox.pop(0)
    return {"received": True, "inbox_size": len(inbox)}


@app.post("/decide")
async def decide(req: DecideRequest = None):
    global turn, last_action
    turn += 1
    ctx = req.context if req else {}
    ctx["round"] = turn

    try:
        prompt = _build_prompt(inbox, ctx)
        response = _call_claude_code(prompt)
        action = _parse_response(response)
        last_action = action
        act_type = action.get('action', 'unknown')
        act_target = action.get('target', '')
        _log_agent("decide", f"{act_type} → {act_target}",
                   action_type=act_type, target=act_target, status="decided")
    except Exception as e:
        action = {"reasoning": str(e), "action": "wait", "target": "", "content": ""}
        last_action = action

    return {
        "agent_id": AGENT_ID, "agent_name": AGENT_NAME,
        "turn": turn, "backend": "claude-code",
        "type": action.get("action", "wait"),
        "target": action.get("target", ""),
        "content": action.get("content", ""),
        "reasoning": action.get("reasoning", ""),
    }


@app.post("/act")
async def act():
    global last_action
    if not last_action:
        return {"status": "no_decision_yet"}

    action_type = last_action.get("action", "wait")
    action_target = last_action.get("target", "")
    action_content = last_action.get("content", "")
    result: Dict[str, Any] = {"action": last_action}

    # 结构化动作日志
    _log_agent("act", f"{action_type} → {action_target}: {action_content[:100]}",
               action_type=action_type, target=action_target,
               content=action_content[:300], status="executing")

    if action_type in ("send_message", "broadcast"):
        try:
            if action_type == "send_message":
                comm.send(AGENT_ID, AGENT_NAME, action_target, action_content)
            else:
                comm.broadcast(AGENT_ID, AGENT_NAME, action_content)
            result["relayed"] = True
            _log_agent("act", f"{action_type} → {action_target}: 发送成功",
                       action_type=action_type, target=action_target,
                       content=action_content[:100], status="success")

            if PACKET_MONITOR_URL:
                try:
                    requests.post(f"{PACKET_MONITOR_URL}/api/packets/ingest", json={
                        "from_id": AGENT_ID, "from_name": AGENT_NAME,
                        "to": action_target if action_type == "send_message" else "broadcast",
                        "content": action_content, "type": action_type,
                        "direction": "outbound",
                    }, timeout=1)
                except Exception:
                    pass
        except Exception as e:
            result["relay_error"] = str(e)
            _log_agent("act", f"{action_type} → {action_target}: 发送失败 {e}",
                       action_type=action_type, target=action_target, status="failed")

    if LOG_COLLECTOR_URL:
        try:
            requests.post(f"{LOG_COLLECTOR_URL}/api/logs/ingest", json={
                "level": "INFO", "event": "agent_act",
                "agent_id": AGENT_ID, "agent_name": AGENT_NAME,
                "index": "logs-agent", "message": f"Act: {str(action)[:200]}",
                "details": result,
            }, timeout=1)
        except Exception:
            pass

    return result


@app.get("/inbox")
async def get_inbox():
    return {"inbox": inbox[-20:]}


@app.post("/clear")
async def clear():
    inbox.clear()
    return {"cleared": True}


if __name__ == "__main__":
    try:
        comm.register_agent(AGENT_ID, AGENT_NAME, f"http://localhost:{AGENT_PORT}")
        print(f"[Claude Agent] Registered: {AGENT_ID} @ port {AGENT_PORT}")
    except Exception as e:
        print(f"[Claude Agent] Register failed: {e}")

    print(f"[Claude Agent] {AGENT_NAME} ({AGENT_ROLE}) starting on port {AGENT_PORT}")
    print(f"[Claude Agent] Goal: {AGENT_CORE_GOAL or 'N/A'}")
    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT, log_level="info")
