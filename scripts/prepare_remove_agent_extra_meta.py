#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "services" / "agent_server.py"
text = path.read_text(encoding="utf-8")
for line in (
    '        "action_space": AGENT_ACTION_SPACE,\n',
    '        "initial_assets": AGENT_INITIAL_ASSETS,\n',
):
    if line not in text:
        raise RuntimeError(f"cannot locate legacy status field: {line.strip()}")
    text = text.replace(line, "", 1)
path.write_text(text, encoding="utf-8", newline="\n")
