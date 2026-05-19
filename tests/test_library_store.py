import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempusloom.core.library_store import LibraryStore


def _write_image(path: Path, size=(20, 12), color=(120, 120, 120)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)


def test_create_library_imports_folder_and_persists_assets(tmp_path):
    source = tmp_path / "photos"
    _write_image(source / "a.jpg", size=(32, 16))
    _write_image(source / "nested" / "b.png", size=(18, 22))
    (source / "note.txt").write_text("skip", encoding="utf-8")

    library_path = tmp_path / "Travel.tlibrary"
    store = LibraryStore.create(library_path, "Travel", initial_folder=source)

    assets = store.query_images()

    assert library_path.is_dir()
    assert (library_path / "library.sqlite").is_file()
    assert [asset.file_name for asset in assets] == ["a.jpg", "b.png"]
    assert assets[0].width == 32
    assert assets[0].height == 16

    reopened = LibraryStore.open(library_path)
    assert [asset.file_name for asset in reopened.query_images()] == ["a.jpg", "b.png"]


def test_add_folder_and_images_skip_duplicate_paths(tmp_path):
    source = tmp_path / "photos"
    extra = tmp_path / "extra"
    first = source / "a.jpg"
    second = extra / "b.png"
    _write_image(first)
    _write_image(second)

    store = LibraryStore.create(tmp_path / "Library.tlibrary", "Library", initial_folder=source)
    folder_result = store.add_folder(extra)
    image_result = store.add_images([first, second])

    assert folder_result.imported == 1
    assert image_result.imported == 0
    assert image_result.skipped == 2
    assert [asset.file_name for asset in store.query_images()] == ["a.jpg", "b.png"]


def test_rating_is_persisted_and_queryable(tmp_path):
    source = tmp_path / "photos"
    first = source / "a.jpg"
    second = source / "b.jpg"
    _write_image(first)
    _write_image(second)
    store = LibraryStore.create(tmp_path / "Library.tlibrary", "Library", initial_folder=source)

    assets = store.query_images()
    store.set_rating(assets[0].id, 4)
    store.set_rating(assets[1].id, 2)

    assert [asset.file_name for asset in store.query_images(min_rating=3)] == [assets[0].file_name]

    reopened = LibraryStore.open(tmp_path / "Library.tlibrary")
    assert reopened.get_asset(assets[0].id).rating == 4


def test_rating_filter_supports_exact_and_minimum_modes(tmp_path):
    source = tmp_path / "photos"
    for index in range(4):
        _write_image(source / f"{index}.jpg")
    store = LibraryStore.create(tmp_path / "Library.tlibrary", "Library", initial_folder=source)
    assets = store.query_images()
    for asset, rating in zip(assets, (0, 3, 3, 5)):
        store.set_rating(asset.id, rating)

    assert [asset.rating for asset in store.query_images(min_rating=3)] == [3, 3, 5]
    assert [asset.rating for asset in store.query_images(exact_rating=3)] == [3, 3]
    assert [asset.rating for asset in store.query_images(exact_rating=0)] == [0]


def test_search_and_folder_counts_support_gallery_filters(tmp_path):
    source = tmp_path / "photos"
    other = tmp_path / "other"
    _write_image(source / "sky-blue.jpg")
    _write_image(source / "portrait.jpg")
    _write_image(other / "sky-wide.png")

    store = LibraryStore.create(tmp_path / "Library.tlibrary", "Library", initial_folder=source)
    store.add_folder(other)

    assert [asset.file_name for asset in store.query_images(search="sky")] == ["sky-blue.jpg", "sky-wide.png"]
    assert store.query_images(folder_path=source)[0].folder_path == str(source.resolve())
    assert dict(store.folder_counts())[str(source.resolve())] == 2
    assert dict(store.folder_counts())[str(other.resolve())] == 1


def test_rating_filter_combines_with_search_and_folder(tmp_path):
    source = tmp_path / "photos"
    other = tmp_path / "other"
    _write_image(source / "sky-a.jpg")
    _write_image(source / "sky-b.jpg")
    _write_image(other / "sky-c.jpg")
    store = LibraryStore.create(tmp_path / "Library.tlibrary", "Library", initial_folder=source)
    store.add_folder(other)
    assets = {asset.file_name: asset for asset in store.query_images()}
    store.set_rating(assets["sky-a.jpg"].id, 4)
    store.set_rating(assets["sky-b.jpg"].id, 2)
    store.set_rating(assets["sky-c.jpg"].id, 4)

    filtered = store.query_images(search="sky", folder_path=source, exact_rating=4)

    assert [asset.file_name for asset in filtered] == ["sky-a.jpg"]


def test_missing_files_are_marked_during_query(tmp_path):
    source = tmp_path / "photos"
    image = source / "a.jpg"
    _write_image(image)
    store = LibraryStore.create(tmp_path / "Library.tlibrary", "Library", initial_folder=source)
    image.unlink()

    asset = store.query_images(include_missing=True)[0]

    assert asset.missing is True
