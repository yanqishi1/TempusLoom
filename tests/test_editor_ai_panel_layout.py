import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempusloom.ui.editor_window import editor_side_panel_order
from tempusloom.ui.editor_window import editor_section_boundary_tokens
from tempusloom.ui.editor_window import editor_adjust_section_chrome
from tempusloom.ui.editor_window import editor_tool_shortcuts
from tempusloom.ui.editor_window import editor_tool_sidebar_chrome
from tempusloom.ui.editor_window import editor_tool_sidebar_tools


def test_ai_chat_column_sits_before_adjustment_panel():
    assert editor_side_panel_order(ai_visible=True) == ["ai_chat", "right_panel"]
    assert editor_side_panel_order(ai_visible=False) == ["right_panel"]


def test_editor_sections_use_subtle_boundary_tokens():
    tokens = editor_section_boundary_tokens()

    assert tokens["panel_border"] == "#2d2d2d"
    assert tokens["panel_alt"] == "#202020"


def test_adjust_sections_do_not_use_left_rail_chrome():
    chrome = editor_adjust_section_chrome()

    assert chrome["collapse_arrow"] is True
    assert chrome["content_left_rail"] is False


def test_editor_tool_sidebar_removes_unused_retouch_tools():
    tools = editor_tool_sidebar_tools()

    assert tools == ["mouse-pointer", "crop", "type", "pipette"]
    assert "pen-tool" not in tools
    assert "paintbrush" not in tools
    assert "eraser" not in tools
    assert "wand-2" not in tools
    assert "stamp" not in tools


def test_editor_tool_shortcuts_only_target_visible_tools():
    shortcuts = editor_tool_shortcuts()

    assert shortcuts == {
        "V": "mouse-pointer",
        "C": "crop",
        "T": "type",
        "I": "pipette",
    }


def test_editor_tool_sidebar_has_right_boundary_line():
    chrome = editor_tool_sidebar_chrome()

    assert chrome["border_right"] == "1px solid #2d2d2d"
