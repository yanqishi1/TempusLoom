import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from main import gallery_file_menu_items


def test_gallery_file_menu_items_replace_import_button_menu():
    assert gallery_file_menu_items() == [
        "创建图库项目...",
        "打开图库项目...",
        None,
        "添加文件夹到图库...",
        "添加图片到图库...",
        None,
        "图库设置...",
    ]
