import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempusloom.core.gallery_navigation import GalleryNavigator
from tempusloom.core.gallery_navigation import gallery_tab_shows_project_browser
from tempusloom.core.gallery_navigation import neighboring_paths


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
