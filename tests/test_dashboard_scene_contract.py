from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_scene_selector_uses_scene_list_item_contract():
    source = (ROOT / "web" / "public" / "dashboard.js").read_text(
        encoding="utf-8"
    )
    start = source.index("async function loadSceneList()")
    end = source.index("function onSceneSelect()", start)
    selector_source = source[start:end]

    assert "s.scene_key" in selector_source
    assert "s.title" in selector_source
    assert "s.name" not in selector_source
    assert "s.format" not in selector_source


def test_dashboard_cachebuster_includes_scene_selector_fix():
    html = (ROOT / "web" / "public" / "dashboard.html").read_text(
        encoding="utf-8"
    )

    assert '/static/dashboard.js?v=13' in html
