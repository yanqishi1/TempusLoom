from __future__ import annotations

from pathlib import Path


def gallery_tab_shows_project_browser(tab: str) -> bool:
    return tab == "图库"


def gallery_add_slot_items() -> list[str]:
    return ["添加图片到图库...", "添加文件夹到图库..."]


def split_gallery_import_paths(paths) -> tuple[list[Path], list[Path]]:
    files: list[Path] = []
    folders: list[Path] = []
    for path in paths:
        item = Path(path).expanduser()
        if item.is_file():
            files.append(item)
        elif item.is_dir():
            folders.append(item)
    return files, folders


def tag_filter_matches(tags: list[str], active_tag: str) -> bool:
    if not active_tag:
        return True
    return active_tag in tags


def toggled_tag_filter(clicked_tag: str, active_tag: str) -> str:
    tag = clicked_tag.strip()
    if tag and tag == active_tag:
        return ""
    return tag


def neighboring_paths(paths: list[str], current_path: str, *, radius: int = 2) -> list[str]:
    """Return current path plus nearby paths for in-memory prefetching."""
    if current_path not in paths:
        return []
    index = paths.index(current_path)
    safe_radius = max(0, int(radius))
    start = max(0, index - safe_radius)
    end = min(len(paths), index + safe_radius + 1)
    return paths[start:end]


class GalleryNavigator:
    """Track current image selection within a gallery result set."""

    def __init__(self, paths: list[str] | None = None) -> None:
        self._paths: list[str] = []
        self._index = -1
        self.set_paths(paths or [])

    @property
    def paths(self) -> list[str]:
        return list(self._paths)

    @property
    def current_path(self) -> str:
        if 0 <= self._index < len(self._paths):
            return self._paths[self._index]
        return ""

    def set_paths(self, paths: list[str], *, preferred_path: str = "") -> str:
        self._paths = list(paths)
        if not self._paths:
            self._index = -1
            return ""
        if preferred_path in self._paths:
            self._index = self._paths.index(preferred_path)
        else:
            self._index = 0
        return self.current_path

    def select(self, path: str) -> str:
        if path in self._paths:
            self._index = self._paths.index(path)
        return self.current_path

    def next_path(self) -> str:
        if not self._paths:
            return ""
        self._index = min(self._index + 1, len(self._paths) - 1)
        return self.current_path

    def previous_path(self) -> str:
        if not self._paths:
            return ""
        self._index = max(self._index - 1, 0)
        return self.current_path
