import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempusloom.ui.gallery_browser import gallery_loupe_layout_order
from tempusloom.ui.gallery_browser import gallery_loupe_uses_embedded_rating_row
from tempusloom.ui.gallery_browser import gallery_project_grid_columns
from tempusloom.ui.gallery_browser import gallery_project_reload_policy
from tempusloom.ui.gallery_browser import gallery_thumbnail_card_size
from tempusloom.ui.gallery_browser import gallery_thumbnail_frame_size
from tempusloom.ui.gallery_browser import gallery_thumbnail_grid_columns
from tempusloom.ui.gallery_browser import gallery_thumbnail_grid_spacing
from tempusloom.ui.gallery_browser import gallery_view_after_asset_reload
from tempusloom.ui.gallery_browser import gallery_widget_removal_policy
from tempusloom.ui.gallery_browser import sidebar_active_tag_for_refresh
from tempusloom.ui.gallery_browser import sidebar_item_value
from tempusloom.ui.styling import gallery_section_boundary_tokens


def test_loupe_action_bar_sits_above_filmstrip():
    assert gallery_loupe_layout_order() == ["toolbar", "view_stack", "action_bar", "filmstrip"]


def test_loupe_view_does_not_own_separate_rating_row():
    assert gallery_loupe_uses_embedded_rating_row() is False


def test_thumbnail_grid_uses_square_frames():
    width, height = gallery_thumbnail_frame_size()

    assert width == height


def test_thumbnail_cards_keep_compact_fixed_height_when_result_set_is_sparse():
    frame_width, frame_height = gallery_thumbnail_frame_size()
    card_width, card_height = gallery_thumbnail_card_size()

    assert card_width == frame_width
    assert frame_height < card_height <= frame_height + 48


def test_thumbnail_grid_uses_available_width_for_columns():
    assert gallery_thumbnail_grid_columns(652) == 3
    assert gallery_thumbnail_grid_columns(860) == 4
    assert gallery_thumbnail_grid_columns(1068) == 5


def test_project_grid_uses_available_width_for_columns():
    assert gallery_project_grid_columns(612) == 2
    assert gallery_project_grid_columns(890) == 3
    assert gallery_project_grid_columns(1168) == 4


def test_back_to_projects_reuses_loaded_project_summaries():
    assert gallery_project_reload_policy("back_button") == "reuse_loaded"
    assert gallery_project_reload_policy("startup") == "refresh_index"


def test_thumbnail_grid_uses_relaxed_spacing():
    horizontal_gap, vertical_gap = gallery_thumbnail_grid_spacing()

    assert horizontal_gap >= 28
    assert vertical_gap >= 28


def test_asset_reload_keeps_current_loupe_view():
    assert gallery_view_after_asset_reload("loupe", selected_path="image.jpg") == "loupe"
    assert gallery_view_after_asset_reload("grid", selected_path="image.jpg") == "grid"
    assert gallery_view_after_asset_reload("loupe", selected_path="") == "grid"


def test_sidebar_tag_item_value_is_tag_name_not_active_state():
    assert sidebar_item_value("夏日", active=True) == "夏日"


def test_sidebar_tag_refresh_uses_parent_active_tag_state():
    assert sidebar_active_tag_for_refresh("落日", ["落日"]) == "落日"
    assert sidebar_active_tag_for_refresh("", ["落日"]) == ""
    assert sidebar_active_tag_for_refresh("不存在", ["落日"]) == ""


def test_gallery_widget_cleanup_deletes_widgets_instead_of_detaching_them():
    assert gallery_widget_removal_policy() == "delete"


def test_gallery_sections_use_subtle_boundary_tokens():
    tokens = gallery_section_boundary_tokens()

    assert tokens["panel_border"] == "#2d2d2d"
    assert tokens["panel_alt"] == "#202020"
