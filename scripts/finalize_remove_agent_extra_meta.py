#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"cannot locate {label} in {path.relative_to(ROOT)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def patch_dashboard() -> None:
    path = ROOT / "web" / "public" / "dashboard.js"
    old = '''  let html = '<div class=tt-name>' + escapeHtml(agent.name || agent.agent_id) + '</div>';
  const backend = (agent.extra_meta || {}).backend || '';
  html += '<div class=tt-role>' + escapeHtml(roleLabel[agent.role] || backendLabel[backend] || agent.role) + '</div>';
  html += '<div class=tt-row><span class=lbl>ID</span><span class=val>' + escapeHtml(agent.agent_id) + '</span></div>';
  html += '<div class=tt-row><span class=lbl>状态</span><span class=val>' + escapeHtml(statusLabel[agent.status] || agent.status) + '</span></div>';
  if (agent.x !== undefined) {
    html += '<div class=tt-row><span class=lbl>坐标</span><span class=val>(' + agent.x.toFixed(0) + ', ' + agent.y.toFixed(0) + ')</span></div>';
  }
  const tasks = agent.pending_task_descs || [];
  if (tasks.length > 0) { html += '<div class=tt-section>任务</div>'; tasks.forEach((t, i) => { html += '<div class=tt-task><span class=tt-task-n>' + (i+1) + '.</span> ' + escapeHtml(t) + '</div>'; }); }
  const meta = agent.extra_meta || {};
  if (meta.core_goal) { html += '<div class=tt-section>目标</div><div class=tt-task>' + escapeHtml(meta.core_goal) + '</div>'; }
  if (meta.hidden_secret) { html += '<div class=tt-section>秘密</div><div class="tt-task tt-secret">' + escapeHtml(meta.hidden_secret) + '</div>'; }
  if (meta.action_space && meta.action_space.length) {
    html += '<div class=tt-section>行动</div><div class=tt-skills>' + meta.action_space.map(a => '<span class=tt-tag>' + escapeHtml(a) + '</span>').join('') + '</div>';
  }
'''
    new = '''  let html = '<div class=tt-name>' + escapeHtml(agent.name || agent.agent_id) + '</div>';
  const backend = agent.backend || '';
  html += '<div class=tt-role>' + escapeHtml(roleLabel[agent.role] || backendLabel[backend] || agent.role) + '</div>';
  html += '<div class=tt-row><span class=lbl>ID</span><span class=val>' + escapeHtml(agent.agent_id) + '</span></div>';
  html += '<div class=tt-row><span class=lbl>状态</span><span class=val>' + escapeHtml(statusLabel[agent.status] || agent.status) + '</span></div>';
  if (agent.x !== undefined) {
    html += '<div class=tt-row><span class=lbl>坐标</span><span class=val>(' + agent.x.toFixed(0) + ', ' + agent.y.toFixed(0) + ')</span></div>';
  }
  const tasks = agent.pending_task_descs || [];
  if (tasks.length > 0) { html += '<div class=tt-section>任务</div>'; tasks.forEach((t, i) => { html += '<div class=tt-task><span class=tt-task-n>' + (i+1) + '.</span> ' + escapeHtml(t) + '</div>'; }); }
  if (agent.core_goal) { html += '<div class=tt-section>目标</div><div class=tt-task>' + escapeHtml(agent.core_goal) + '</div>'; }
  const tools = agent.allowed_tools || [];
  if (tools.length) {
    html += '<div class=tt-section>工具</div><div class=tt-skills>' + tools.map(tool => '<span class=tt-tag>' + escapeHtml(tool) + '</span>').join('') + '</div>';
  }
'''
    replace_once(path, old, new, "Dashboard explicit Agent fields")


def patch_docs() -> None:
    for path in sorted((ROOT / "scenes").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        updated = text.replace("claudecode", "claude-code")
        updated = updated.replace("extra_meta.action_space", "AgentDef.allowed_tools")
        updated = updated.replace("extra_meta", "AgentDef 显式字段")
        updated = updated.replace("action_space", "allowed_tools")
        updated = updated.replace("skill_execution_mode", "backend-native MCP execution")
        if updated != text:
            path.write_text(updated, encoding="utf-8", newline="\n")


def validate() -> None:
    runtime_paths = [
        ROOT / "agent_network" / "scene_def.py",
        ROOT / "agent_network" / "agent_model.py",
        ROOT / "agent_network" / "container_runtime.py",
        ROOT / "agent_network" / "api" / "simulations.py",
        ROOT / "services" / "agent_server.py",
        ROOT / "web" / "public" / "dashboard.js",
    ]
    for path in runtime_paths:
        text = path.read_text(encoding="utf-8")
        for token in ("extra_meta", "_extra_meta", "skill_execution_mode", "action_space"):
            if token in text:
                raise RuntimeError(f"legacy token {token!r} remains in {path.relative_to(ROOT)}")

    for path in sorted((ROOT / "scenes").rglob("*")):
        if path.is_file() and path.suffix.lower() in {".json", ".md", ".py"}:
            if "claudecode" in path.read_text(encoding="utf-8"):
                raise RuntimeError(f"removed backend alias remains in {path.relative_to(ROOT)}")

    print("Agent metadata cleanup verified")


def main() -> None:
    patch_dashboard()
    patch_docs()
    validate()


if __name__ == "__main__":
    main()
