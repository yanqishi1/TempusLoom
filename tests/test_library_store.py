import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempusloom.core.library_store import LibraryProjectIndex, LibraryStore


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


def test_library_project_index_lists_registered_libraries_with_database_cover(tmp_path):
    first_source = tmp_path / "first-photos"
    second_source = tmp_path / "second-photos"
    first_image = first_source / "a.jpg"
    second_image = second_source / "b.jpg"
    _write_image(first_image)
    _write_image(second_image)
    first_library = LibraryStore.create(tmp_path / "First.tlibrary", "First", initial_folder=first_source)
    second_library = LibraryStore.create(tmp_path / "Second.tlibrary", "Second", initial_folder=second_source)
    index = LibraryProjectIndex(tmp_path / "library-index.sqlite")

    index.register_library(second_library.library_path)
    index.register_library(first_library.library_path)

    projects = index.list_projects()

    assert [project.name for project in projects] == ["Second", "First"]
    assert [project.image_count for project in projects] == [1, 1]
    assert {project.cover_path for project in projects} == {str(first_image.resolve()), str(second_image.resolve())}


def test_library_project_index_lists_newest_created_library_first(tmp_path):
    first_source = tmp_path / "first-photos"
    second_source = tmp_path / "second-photos"
    _write_image(first_source / "a.jpg")
    _write_image(second_source / "b.jpg")
    first_library = LibraryStore.create(tmp_path / "First.tlibrary", "First", initial_folder=first_source)
    second_library = LibraryStore.create(tmp_path / "Second.tlibrary", "Second", initial_folder=second_source)
    first_library._conn.execute("UPDATE library_project SET created_at = ?, updated_at = ?", ("2026-05-20T08:00:00+00:00", "2026-05-20T18:00:00+00:00"))
    second_library._conn.execute("UPDATE library_project SET created_at = ?, updated_at = ?", ("2026-05-20T09:00:00+00:00", "2026-05-20T10:00:00+00:00"))
    first_library._conn.commit()
    second_library._conn.commit()
    index = LibraryProjectIndex(tmp_path / "library-index.sqlite")
    index.register_library(first_library.library_path)
    index.register_library(second_library.library_path)
    index._conn.execute(
        "UPDATE library_registry SET opened_at = ? WHERE library_path = ?",
        ("2026-05-20T20:00:00+00:00", str(first_library.library_path)),
    )
    index._conn.execute(
        "UPDATE library_registry SET opened_at = ? WHERE library_path = ?",
        ("2026-05-20T19:00:00+00:00", str(second_library.library_path)),
    )
    index._conn.commit()

    projects = index.list_projects()

    assert [project.name for project in projects] == ["Second", "First"]


def test_library_project_summary_includes_dates_and_multiple_cover_paths(tmp_path):
    source = tmp_path / "photos"
    first_image = source / "a.jpg"
    second_image = source / "b.jpg"
    _write_image(first_image)
    _write_image(second_image)

    library = LibraryStore.create(tmp_path / "Library.tlibrary", "Library", initial_folder=source)
    summary = library.project_summary()

    assert summary.created_at
    assert summary.updated_at
    assert set(summary.cover_paths) == {str(first_image.resolve()), str(second_image.resolve())}
    assert summary.cover_path in summary.cover_paths


def test_library_project_index_can_forget_registered_library_without_deleting_files(tmp_path):
    source = tmp_path / "photos"
    _write_image(source / "a.jpg")
    library = LibraryStore.create(tmp_path / "Library.tlibrary", "Library", initial_folder=source)
    index = LibraryProjectIndex(tmp_path / "library-index.sqlite")
    index.register_library(library.library_path)

    index.unregister_library(library.library_path)

    assert index.list_projects() == []
    assert (library.library_path / LibraryStore.DB_NAME).is_file()


def test_library_project_can_be_renamed(tmp_path):
    source = tmp_path / "photos"
    _write_image(source / "a.jpg")
    library = LibraryStore.create(tmp_path / "Library.tlibrary", "Original", initial_folder=source)

    library.rename_project("Renamed")

    assert LibraryStore.open(library.library_path).project_summary().name == "Renamed"


def test_image_tags_are_persisted_and_queryable(tmp_path):
    source = tmp_path / "photos"
    _write_image(source / "sky.jpg")
    _write_image(source / "ground.jpg")
    store = LibraryStore.create(tmp_path / "Library.tlibrary", "Library", initial_folder=source)
    assets = {asset.file_name: asset for asset in store.query_images()}

    store.set_asset_tags(assets["sky.jpg"].id, ["天空", "精选", "天空"])

    assert store.asset_tags(assets["sky.jpg"].id) == ["天空", "精选"]
    assert [asset.file_name for asset in store.query_images(tag="天空")] == ["sky.jpg"]
    assert store.tag_counts() == [("天空", 1), ("精选", 1)]

    reopened = LibraryStore.open(tmp_path / "Library.tlibrary")
    assert reopened.asset_tags(assets["sky.jpg"].id) == ["天空", "精选"]


def test_library_project_index_queries_tags_across_registered_libraries(tmp_path):
    first_source = tmp_path / "first-photos"
    second_source = tmp_path / "second-photos"
    _write_image(first_source / "a.jpg")
    _write_image(second_source / "b.jpg")
    first_library = LibraryStore.create(tmp_path / "First.tlibrary", "First", initial_folder=first_source)
    second_library = LibraryStore.create(tmp_path / "Second.tlibrary", "Second", initial_folder=second_source)
    first_asset = first_library.query_images()[0]
    second_asset = second_library.query_images()[0]
    first_library.add_asset_tag(first_asset.id, "导出")
    second_library.add_asset_tag(second_asset.id, "导出")
    index = LibraryProjectIndex(tmp_path / "library-index.sqlite")
    index.register_library(first_library.library_path)
    index.register_library(second_library.library_path)

    assert index.global_tag_counts() == [("导出", 2)]
    assert {asset.file_name for asset in index.query_images_by_tag("导出")} == {"a.jpg", "b.jpg"}


def test_library_project_index_can_tag_asset_by_original_path_after_export(tmp_path):
    source = tmp_path / "photos"
    image = source / "a.jpg"
    _write_image(image)
    store = LibraryStore.create(tmp_path / "Library.tlibrary", "Library", initial_folder=source)
    index = LibraryProjectIndex(tmp_path / "library-index.sqlite")
    index.register_library(store.library_path)

    assert index.add_tag_for_asset_path(image, "导出") is True

    asset = LibraryStore.open(store.library_path).query_images()[0]
    assert LibraryStore.open(store.library_path).asset_tags(asset.id) == ["导出"]


def test_asset_edit_state_is_persisted_for_reopening_photo(tmp_path):
    source = tmp_path / "photos"
    image = source / "a.jpg"
    _write_image(image)
    store = LibraryStore.create(tmp_path / "Library.tlibrary", "Library", initial_folder=source)
    asset = store.query_images()[0]
    edit_state = {
        "image_path": str(image.resolve()),
        "edit_state": {
            "adjust": {
                "basic": {"exposure": 0.4, "contrast": 12},
                "hsl": {"red": {"saturation": 8}},
            },
            "layers": [
                {"id": "layer-1", "type": "adjustment", "name": "Sky", "payload": {"basic": {"temperature": -8}}},
            ],
        },
        "malayers": [],
    }

    store.save_asset_edit_state(asset.id, edit_state)

    reopened = LibraryStore.open(store.library_path)
    assert reopened.asset_edit_state(asset.id) == edit_state


def test_library_project_index_loads_and_saves_edit_state_by_asset_path(tmp_path):
    source = tmp_path / "photos"
    image = source / "a.jpg"
    _write_image(image)
    store = LibraryStore.create(tmp_path / "Library.tlibrary", "Library", initial_folder=source)
    index = LibraryProjectIndex(tmp_path / "library-index.sqlite")
    index.register_library(store.library_path)
    snapshot = {
        "image_path": str(image.resolve()),
        "edit_state": {"adjust": {"basic": {"exposure": -0.2}}},
        "malayers": [],
    }

    assert index.save_edit_state_for_asset_path(image, snapshot) is True
    assert index.load_edit_state_for_asset_path(image) == snapshot
