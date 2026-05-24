import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempusloom.core.gallery_navigation import GalleryNavigator
from tempusloom.core.gallery_navigation import gallery_add_slot_items
from tempusloom.core.gallery_navigation import gallery_tab_shows_project_browser
from tempusloom.core.gallery_navigation import neighboring_paths
from tempusloom.core.gallery_navigation import split_gallery_import_paths
from tempusloom.core.gallery_navigation import tag_filter_matches
from tempusloom.core.gallery_navigation import toggled_tag_filter


def test_gallery_navigator_tracks_selection_and_moves_left_right():
    navigator = GalleryNavigator(["a.jpg", "b.jpg", "c.jpg"])

    assert navigator.current_path == "a.jpg"

    assert navigator.select("b.jpg") == "b.jpg"
    assert navigator.next_path() == "c.jpg"
    assert navigator.next_path() == "c.jpg"
    assert navigator.previous_path() == "b.jpg"
    assert navigator.previous_path() == "a.jpg"
    assert navigator.previous_path() == "a.jpg"


def test_gallery_navigator_keeps_selection_when_paths_refresh():
    navigator = GalleryNavigator(["a.jpg", "b.jpg", "c.jpg"])
    navigator.select("b.jpg")

    navigator.set_paths(["b.jpg", "d.jpg"], preferred_path="b.jpg")

    assert navigator.current_path == "b.jpg"
    assert navigator.next_path() == "d.jpg"


def test_gallery_navigator_clears_selection_for_empty_gallery():
    navigator = GalleryNavigator(["a.jpg"])

    navigator.set_paths([])

    assert navigator.current_path == ""
    assert navigator.next_path() == ""


def test_neighboring_paths_prefetches_current_image_and_nearby_images():
    paths = ["a.jpg", "b.jpg", "c.jpg", "d.jpg", "e.jpg", "f.jpg"]

    assert neighboring_paths(paths, "c.jpg", radius=2) == ["a.jpg", "b.jpg", "c.jpg", "d.jpg", "e.jpg"]
    assert neighboring_paths(paths, "a.jpg", radius=2) == ["a.jpg", "b.jpg", "c.jpg"]
    assert neighboring_paths(paths, "f.jpg", radius=3) == ["c.jpg", "d.jpg", "e.jpg", "f.jpg"]
    assert neighboring_paths(paths, "missing.jpg", radius=2) == []


def test_gallery_tab_returns_to_project_browser():
    assert gallery_tab_shows_project_browser("图库") is True
    assert gallery_tab_shows_project_browser("最近") is False
    assert gallery_tab_shows_project_browser("收藏") is False


def test_gallery_add_slot_menu_items():
    assert gallery_add_slot_items() == ["添加图片到图库...", "添加文件夹到图库..."]


def test_split_gallery_import_paths_separates_files_and_folders(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    image = tmp_path / "image.jpg"
    image.write_bytes(b"")
    missing = tmp_path / "missing.jpg"

    files, folders = split_gallery_import_paths([image, folder, missing])

    assert files == [image]
    assert folders == [folder]


def test_tag_filter_matches_only_active_tag():
    assert tag_filter_matches([], "") is True
    assert tag_filter_matches(["人像", "精选"], "") is True
    assert tag_filter_matches(["人像", "精选"], "精选") is True
    assert tag_filter_matches(["人像"], "风景") is False


def test_toggled_tag_filter_clears_when_clicking_active_tag_again():
    assert toggled_tag_filter("落日", "人像") == "落日"
    assert toggled_tag_filter("落日", "落日") == ""
    assert toggled_tag_filter("  落日  ", "") == "落日"
