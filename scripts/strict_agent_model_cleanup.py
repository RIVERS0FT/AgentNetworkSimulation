#!/usr/bin/env python3
from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEXT_EXTENSIONS = {
    ".py", ".md", ".json", ".yml", ".yaml", ".txt", ".toml", ".ini", ".cfg", ".js", ".ts", ".tsx", ".css", ".html"
}
FORBIDDEN = (
    "extra_meta",
    "_extra_meta",
    '"action_space"',
    "'action_space'",
    "skill_execution_mode",
    "claudecode",
)


def iter_text_files():
    ignored_dirs = {".git", ".venv", "node_modules", "__pycache__"}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored_dirs for part in path.parts):
            continue
        if path == pathlib.Path(__file__).resolve():
            continue
        if path.suffix.lower() in TEXT_EXTENSIONS:
            yield path


def replace_legacy_backend_aliases() -> None:
    for path in iter_text_files():
        text = path.read_text(encoding="utf-8")
        updated = text.replace("claudecode", "claude-code")
        if updated != text:
            path.write_text(updated, encoding="utf-8", newline="\n")


def patch_backend_validation() -> None:
    path = ROOT / "agent_network" / "api" / "simulations.py"
    text = path.read_text(encoding="utf-8")
    old = '''    if backend == "claude-code":
        return backend
    if backend == "brain":
        raise ValueError(f"Scene '{scene_name}' role '{role_id}' uses removed backend 'brain'.")
    if backend == "claude-code":
        raise ValueError(
            f"Scene '{scene_name}' role '{role_id}' uses removed backend alias 'claude-code'; "
            "use 'claude-code'."
        )
    if backend not in {"openclaw", "claude-code"}:
        raise ValueError(f"Scene '{scene_name}' role '{role_id}' uses unsupported backend '{backend}'.")
    return backend
'''
    if old in text:
        new = '''    if backend == "brain":
        raise ValueError(f"Scene '{scene_name}' role '{role_id}' uses removed backend 'brain'.")
    if backend not in {"openclaw", "claude-code"}:
        raise ValueError(f"Scene '{scene_name}' role '{role_id}' uses unsupported backend '{backend}'.")
    return backend
'''
        text = text.replace(old, new, 1)
    # Also handle the pre-replacement form, for idempotence when run manually.
    old_original = '''    if backend == "brain":
        raise ValueError(f"Scene '{scene_name}' role '{role_id}' uses removed backend 'brain'.")
    if backend == "claudecode":
        raise ValueError(
            f"Scene '{scene_name}' role '{role_id}' uses removed backend alias 'claudecode'; "
            "use 'claude-code'."
        )
    if backend not in {"openclaw", "claude-code"}:
        raise ValueError(f"Scene '{scene_name}' role '{role_id}' uses unsupported backend '{backend}'.")
    return backend
'''
    if old_original in text:
        new = '''    if backend == "brain":
        raise ValueError(f"Scene '{scene_name}' role '{role_id}' uses removed backend 'brain'.")
    if backend not in {"openclaw", "claude-code"}:
        raise ValueError(f"Scene '{scene_name}' role '{role_id}' uses unsupported backend '{backend}'.")
    return backend
'''
        text = text.replace(old_original, new, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_scene_tests() -> None:
    path = ROOT / "tests" / "test_scene_building_boundary.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '''def test_scene_building_rejects_removed_claude-code_backend(tmp_path, monkeypatch):
    _write_scene(tmp_path, backend="claude-code")
    monkeypatch.setattr(simulations, "_SCENES_DIR", tmp_path)

    with pytest.raises(ValueError) as exc:
        simulations._build_scene_from_folder("demo_scene")

    assert "removed backend alias 'claude-code'" in str(exc.value)


''',
        "",
    )
    text = text.replace(
        '''def test_scene_building_rejects_removed_claudecode_backend(tmp_path, monkeypatch):
    _write_scene(tmp_path, backend="claudecode")
    monkeypatch.setattr(simulations, "_SCENES_DIR", tmp_path)

    with pytest.raises(ValueError) as exc:
        simulations._build_scene_from_folder("demo_scene")

    assert "removed backend alias 'claudecode'" in str(exc.value)


''',
        "",
    )
    if "def test_scene_building_accepts_claude_code_backend" not in text:
        marker = "\ndef test_scene_building_rejects_removed_brain_backend"
        insert = '''

def test_scene_building_accepts_claude_code_backend(tmp_path, monkeypatch):
    _write_scene(tmp_path, backend="claude-code")
    monkeypatch.setattr(simulations, "_SCENES_DIR", tmp_path)

    scene_def = simulations._build_scene_from_folder("demo_scene")

    assert scene_def.agents[0].backend == "claude-code"
'''
        if marker not in text:
            raise RuntimeError("Cannot locate scene backend test insertion point")
        text = text.replace(marker, insert + marker, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def validate_no_forbidden_tokens() -> None:
    hits = []
    for path in iter_text_files():
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            if token in text:
                hits.append(f"{path.relative_to(ROOT)}: {token}")
    if hits:
        raise SystemExit("Forbidden compatibility tokens remain:\n" + "\n".join(hits))


def main() -> None:
    replace_legacy_backend_aliases()
    patch_backend_validation()
    patch_scene_tests()
    validate_no_forbidden_tokens()
    print("strict agent model cleanup complete")


if __name__ == "__main__":
    main()
