import json
import logging
import os
import asyncio
from .base import BackendAdapter, AgentContext, AgentRunResult
from .direct_llm import run_direct_llm
from agent_network.skill_md_loader import load_scene_skill_registry

try:
    from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock, ResultMessage
except ImportError:
    query = None
    ClaudeAgentOptions = None
    AssistantMessage = None
    TextBlock = None
    ResultMessage = None

logger = logging.getLogger(__name__)


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys([item for item in items if item]))


def _skill_names(agent_context: AgentContext) -> list[str]:
    names = list(getattr(agent_context, "allowed_skills", []) or [])
    if not names:
        for item in agent_context.skills or []:
            if isinstance(item, dict):
                names.append(item.get("name") or item.get("skill_name") or "")
            elif isinstance(item, str):
                names.append(item)
    return _unique(names)


def _skill_context(agent_context: AgentContext) -> list[dict]:
    scene_key = agent_context.scene_key or os.environ.get("AGENT_SCENE_KEY", "default")
    scenes_root = os.environ.get("AGENT_SCENES_ROOT", "/app/scenes")
    registry = load_scene_skill_registry(scene_key=scene_key, scenes_root=scenes_root, allowed_skills=_skill_names(agent_context))
    specs = registry.context_specs()
    if specs:
        return specs
    return [item for item in (agent_context.skills or []) if isinstance(item, dict)]


def _build_task_payload(agent_context: AgentContext) -> str:
    payload = {
        "task": agent_context.task,
        "trace_id": agent_context.trace_id,
        "scene_key": agent_context.scene_key,
        "agent": {
            "agent_id": agent_context.agent_id,
            "name": agent_context.agent_name,
            "role": agent_context.role,
            "core_goal": agent_context.core_goal,
        },
        "messages": agent_context.messages,
        "allowed_skills": _skill_names(agent_context),
        "skills": _skill_context(agent_context),
        "allowed_tools": agent_context.allowed_tools,
        "permissions": agent_context.permissions,
        "state_snapshot": agent_context.state_snapshot,
        "tick": agent_context.tick,
        "agent_directory": agent_context.agent_directory,
        "comm_matrix": agent_context.comm_matrix,
        "network_mode": "direct",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _system_prompt(agent_context: AgentContext) -> str:
    return (
        f"You are {agent_context.agent_name} ({agent_context.agent_id}).\n"
        f"Role: {agent_context.role}\n"
        f"Core Goal: {agent_context.core_goal}\n"
        f"Trace ID: {agent_context.trace_id}\n"
        "AgentNetwork uses direct Agent-to-Agent HTTP messaging. Call only exposed MCP tools."
    )


def _completed_event(agent_context: AgentContext, output_text: str, backend_name: str) -> dict:
    return {
        "event": "agent_run_completed",
        "trace_id": agent_context.trace_id,
        "actor": {"agent_id": agent_context.agent_id, "name": agent_context.agent_name, "role": agent_context.role, "backend": backend_name},
        "task": {"goal": agent_context.task, "status": "completed"},
        "action": {"type": "agent_run", "name": f"{backend_name}_run", "status": "success"},
        "content": {"content_type": "final_message", "text": output_text, "summary": output_text[:200], "size_bytes": len(output_text.encode("utf-8"))},
        "result": {"status": "success", "message": "agent run completed"},
        "metrics": {"backend": backend_name},
    }


def _claude_mcp_server(agent_context: AgentContext, skill_names: list[str]) -> dict:
    scene_key = agent_context.scene_key or os.environ.get("AGENT_SCENE_KEY", "default")
    return {
        "type": "stdio",
        "command": "python",
        "args": [
            "-m", "agent_network.mcp_server",
            "--scene", scene_key,
            "--agent-id", agent_context.agent_id,
            "--agent-name", agent_context.agent_name,
            "--allowed-skills", ",".join(skill_names),
            "--allowed-tools", ",".join(agent_context.allowed_tools),
            "--agent-directory-json", json.dumps(agent_context.agent_directory, ensure_ascii=False),
            "--comm-matrix-json", json.dumps(agent_context.comm_matrix, ensure_ascii=False),
        ],
    }


def _claude_allowed_tools(agent_context: AgentContext) -> list[str]:
    tools = list(agent_context.allowed_tools or [])
    tools.extend([f"mcp__agent_tools__{tool}" for tool in (agent_context.allowed_tools or [])])
    return _unique(tools)


def _extract_text_from_message(message) -> list[str]:
    parts: list[str] = []
    if AssistantMessage is not None and isinstance(message, AssistantMessage):
        for block in getattr(message, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(str(text))
    elif ResultMessage is not None and isinstance(message, ResultMessage):
        result = getattr(message, "result", None)
        if result:
            parts.append(str(result))
    else:
        content = getattr(message, "content", None)
        if isinstance(content, str) and content:
            parts.append(content)
    return parts


class ClaudeCodeAdapter(BackendAdapter):
    def run_agent_task(self, agent_context: AgentContext) -> AgentRunResult:
        if os.environ.get("MOCK_LLM") == "1":
            output_text = "[MOCK_LLM] Dummy response"
            return AgentRunResult(
                trace_id=agent_context.trace_id,
                agent_id=agent_context.agent_id,
                status="completed",
                final_message=output_text,
                application_events=[_completed_event(agent_context, output_text, "claude-code")],
            )

        skill_names = _skill_names(agent_context)
        system_prompt = _system_prompt(agent_context)
        current_task = _build_task_payload(agent_context)

        if not query or not ClaudeAgentOptions:
            if os.environ.get("AGENT_STRICT_BACKEND_SDK") == "1":
                return AgentRunResult(trace_id=agent_context.trace_id, agent_id=agent_context.agent_id, status="error", final_message="", error="claude-agent-sdk is not installed.")
            return run_direct_llm(agent_context, backend_name="claude-agent-direct-llm", system_prompt=system_prompt, user_payload=current_task)

        try:
            options_kwargs = {
                "system_prompt": system_prompt,
                "allowed_tools": _claude_allowed_tools(agent_context),
                "mcp_servers": {"agent_tools": _claude_mcp_server(agent_context, skill_names)},
            }
            max_turns = agent_context.max_turns or int(os.environ.get("CLAUDE_AGENT_MAX_TURNS", "1"))
            if max_turns:
                options_kwargs["max_turns"] = max_turns
            if os.environ.get("CLAUDE_AGENT_CWD"):
                options_kwargs["cwd"] = os.environ["CLAUDE_AGENT_CWD"]
            if os.environ.get("CLAUDE_AGENT_PERMISSION_MODE"):
                options_kwargs["permission_mode"] = os.environ["CLAUDE_AGENT_PERMISSION_MODE"]

            options = ClaudeAgentOptions(**options_kwargs)

            async def _run():
                text_parts: list[str] = []
                async for message in query(prompt=current_task, options=options):
                    text_parts.extend(_extract_text_from_message(message))
                return "\n".join([part for part in text_parts if part]).strip()

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                output_text = loop.run_until_complete(_run())
            finally:
                loop.close()

            return AgentRunResult(
                trace_id=agent_context.trace_id,
                agent_id=agent_context.agent_id,
                status="completed",
                final_message=output_text,
                application_events=[_completed_event(agent_context, output_text, "claude-agent-sdk")],
            )
        except Exception as e:
            return AgentRunResult(trace_id=agent_context.trace_id, agent_id=agent_context.agent_id, status="error", final_message="", error=f"Claude Agent SDK Error: {str(e)}")
