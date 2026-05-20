from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import sqlite3
import uuid
from typing import Iterable, Optional

from PIL import Image


SUPPORTED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
    ".bmp",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_path(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve())


@dataclass(frozen=True)
class LibraryAsset:
    id: str
    path: str
    file_name: str
    folder_path: str
    extension: str
    file_size: int
    width: Optional[int]
    height: Optional[int]
    rating: int
    missing: bool
    imported_at: str
    updated_at: str


@dataclass(frozen=True)
class ImportResult:
    scanned: int = 0
    imported: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass(frozen=True)
class LibraryProject:
    name: str
    library_path: str
    root_path: Optional[str]
    image_count: int
    cover_path: str
    cover_paths: tuple[str, ...]
    created_at: str
    updated_at: str


class LibraryStore:
    """SQLite-backed photo library project store."""

    DB_NAME = "library.sqlite"

    def __init__(self, library_path: str | Path) -> None:
        self.library_path = Path(library_path).expanduser().resolve()
        self.db_path = self._resolve_db_path(self.library_path)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    @classmethod
    def create(
        cls,
        library_path: str | Path,
        name: str,
        *,
        initial_folder: str | Path | None = None,
    ) -> "LibraryStore":
        path = Path(library_path).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        (path / "previews").mkdir(exist_ok=True)
        (path / "cache").mkdir(exist_ok=True)
        store = cls(path)
        store._upsert_project(name=name, root_path=initial_folder)
        if initial_folder is not None:
            store.add_folder(initial_folder)
        return store

    @classmethod
    def open(cls, library_path: str | Path) -> "LibraryStore":
        return cls(library_path)

    @staticmethod
    def _resolve_db_path(library_path: Path) -> Path:
        if library_path.suffix == ".sqlite":
            library_path.parent.mkdir(parents=True, exist_ok=True)
            return library_path
        library_path.mkdir(parents=True, exist_ok=True)
        return library_path / LibraryStore.DB_NAME

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS library_project (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              root_path TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS import_source (
              id TEXT PRIMARY KEY,
              source_type TEXT NOT NULL,
              path TEXT NOT NULL,
              recursive INTEGER NOT NULL DEFAULT 1,
              imported_at TEXT NOT NULL,
              image_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS image_asset (
              id TEXT PRIMARY KEY,
              path TEXT NOT NULL UNIQUE,
              file_name TEXT NOT NULL,
              folder_path TEXT NOT NULL,
              extension TEXT NOT NULL,
              file_size INTEGER,
              width INTEGER,
              height INTEGER,
              rating INTEGER NOT NULL DEFAULT 0,
              missing INTEGER NOT NULL DEFAULT 0,
              imported_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tag (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL UNIQUE,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS image_tag (
              asset_id TEXT NOT NULL,
              tag_id TEXT NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY (asset_id, tag_id),
              FOREIGN KEY (asset_id) REFERENCES image_asset(id) ON DELETE CASCADE,
              FOREIGN KEY (tag_id) REFERENCES tag(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS image_edit_state (
              asset_id TEXT PRIMARY KEY,
              snapshot_json TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (asset_id) REFERENCES image_asset(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_image_asset_rating ON image_asset(rating);
            CREATE INDEX IF NOT EXISTS idx_image_asset_folder ON image_asset(folder_path);
            CREATE INDEX IF NOT EXISTS idx_image_asset_imported_at ON image_asset(imported_at);
            CREATE INDEX IF NOT EXISTS idx_tag_name ON tag(name);
            CREATE INDEX IF NOT EXISTS idx_image_tag_tag ON image_tag(tag_id);
            """
        )
        self._conn.commit()

    def _upsert_project(self, *, name: str, root_path: str | Path | None = None) -> None:
        now = _utc_now()
        root = _normalize_path(root_path) if root_path is not None else None
        row = self._conn.execute("SELECT id FROM library_project LIMIT 1").fetchone()
        if row:
            self._conn.execute(
                "UPDATE library_project SET name = ?, root_path = ?, updated_at = ? WHERE id = ?",
                (name, root, now, row["id"]),
            )
        else:
            self._conn.execute(
                """
                INSERT INTO library_project (id, name, root_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), name, root, now, now),
            )
        self._conn.commit()

    def rename_project(self, name: str) -> None:
        clean_name = name.strip()
        if not clean_name:
            return
        row = self._conn.execute("SELECT id, root_path FROM library_project LIMIT 1").fetchone()
        if row:
            self._conn.execute(
                "UPDATE library_project SET name = ?, updated_at = ? WHERE id = ?",
                (clean_name, _utc_now(), row["id"]),
            )
            self._conn.commit()
        else:
            self._upsert_project(name=clean_name)

    def add_folder(self, folder_path: str | Path, *, recursive: bool = True) -> ImportResult:
        folder = Path(folder_path).expanduser().resolve()
        candidates = folder.rglob("*") if recursive else folder.glob("*")
        return self._import_paths(
            [path for path in candidates if path.is_file()],
            source_type="folder",
            source_path=folder,
            recursive=recursive,
        )

    def add_images(self, image_paths: Iterable[str | Path]) -> ImportResult:
        return self._import_paths(
            [Path(path).expanduser().resolve() for path in image_paths],
            source_type="file",
            source_path=None,
            recursive=False,
        )

    def _import_paths(
        self,
        paths: Iterable[Path],
        *,
        source_type: str,
        source_path: Path | None,
        recursive: bool,
    ) -> ImportResult:
        scanned = imported = skipped = failed = 0
        now = _utc_now()
        for path in sorted(paths, key=lambda item: str(item).lower()):
            if path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
                continue
            scanned += 1
            normalized = _normalize_path(path)
            if self._conn.execute("SELECT 1 FROM image_asset WHERE path = ?", (normalized,)).fetchone():
                skipped += 1
                continue
            try:
                stat = path.stat()
                width, height = self._read_dimensions(path)
                self._conn.execute(
                    """
                    INSERT INTO image_asset (
                      id, path, file_name, folder_path, extension, file_size,
                      width, height, rating, missing, imported_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        normalized,
                        path.name,
                        str(path.parent),
                        path.suffix.lower().lstrip("."),
                        int(stat.st_size),
                        width,
                        height,
                        now,
                        now,
                    ),
                )
                imported += 1
            except Exception:
                failed += 1

        source = source_path if source_path is not None else None
        self._conn.execute(
            """
            INSERT INTO import_source (id, source_type, path, recursive, imported_at, image_count)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                source_type,
                _normalize_path(source) if source is not None else "",
                1 if recursive else 0,
                now,
                imported,
            ),
        )
        self._conn.commit()
        return ImportResult(scanned=scanned, imported=imported, skipped=skipped, failed=failed)

    @staticmethod
    def _read_dimensions(path: Path) -> tuple[Optional[int], Optional[int]]:
        with Image.open(path) as image:
            return int(image.width), int(image.height)

    def query_images(
        self,
        *,
        min_rating: int = 0,
        exact_rating: int | None = None,
        search: str = "",
        include_missing: bool = False,
        folder_path: str | Path | None = None,
        tag: str | None = None,
    ) -> list[LibraryAsset]:
        self.refresh_missing_flags()
        params: list[object] = []
        if exact_rating is None:
            where = ["rating >= ?"]
            params.append(max(0, min(5, int(min_rating))))
        else:
            where = ["rating = ?"]
            params.append(max(0, min(5, int(exact_rating))))
        if not include_missing:
            where.append("missing = 0")
        if search:
            where.append("LOWER(file_name) LIKE ?")
            params.append(f"%{search.lower()}%")
        if folder_path is not None:
            where.append("folder_path = ?")
            params.append(_normalize_path(folder_path))
        if tag:
            where.append(
                """
                id IN (
                  SELECT image_tag.asset_id
                  FROM image_tag
                  INNER JOIN tag ON tag.id = image_tag.tag_id
                  WHERE tag.name = ?
                )
                """
            )
            params.append(tag.strip())
        rows = self._conn.execute(
            f"""
            SELECT * FROM image_asset
            WHERE {" AND ".join(where)}
            ORDER BY imported_at ASC, file_name ASC
            """,
            params,
        ).fetchall()
        return [self._row_to_asset(row) for row in rows]

    def get_asset_by_path(self, path: str | Path) -> Optional[LibraryAsset]:
        row = self._conn.execute(
            "SELECT * FROM image_asset WHERE path = ?",
            (_normalize_path(path),),
        ).fetchone()
        return self._row_to_asset(row) if row else None

    def get_asset(self, asset_id: str) -> Optional[LibraryAsset]:
        row = self._conn.execute("SELECT * FROM image_asset WHERE id = ?", (asset_id,)).fetchone()
        return self._row_to_asset(row) if row else None

    def set_rating(self, asset_id: str, rating: int) -> None:
        safe_rating = max(0, min(5, int(rating)))
        self._conn.execute(
            "UPDATE image_asset SET rating = ?, updated_at = ? WHERE id = ?",
            (safe_rating, _utc_now(), asset_id),
        )
        self._conn.commit()

    def save_asset_edit_state(self, asset_id: str, snapshot: dict) -> None:
        payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        now = _utc_now()
        self._conn.execute(
            """
            INSERT INTO image_edit_state (asset_id, snapshot_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET
              snapshot_json = excluded.snapshot_json,
              updated_at = excluded.updated_at
            """,
            (asset_id, payload, now),
        )
        self._conn.execute("UPDATE image_asset SET updated_at = ? WHERE id = ?", (now, asset_id))
        self._conn.commit()

    def asset_edit_state(self, asset_id: str) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT snapshot_json FROM image_edit_state WHERE asset_id = ?",
            (asset_id,),
        ).fetchone()
        if not row:
            return None
        try:
            data = json.loads(str(row["snapshot_json"]))
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def add_asset_tag(self, asset_id: str, tag: str) -> None:
        name = tag.strip()
        if not name:
            return
        now = _utc_now()
        row = self._conn.execute("SELECT id FROM tag WHERE name = ?", (name,)).fetchone()
        if row:
            tag_id = str(row["id"])
            self._conn.execute("UPDATE tag SET updated_at = ? WHERE id = ?", (now, tag_id))
        else:
            tag_id = str(uuid.uuid4())
            self._conn.execute(
                "INSERT INTO tag (id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (tag_id, name, now, now),
            )
        self._conn.execute(
            """
            INSERT OR IGNORE INTO image_tag (asset_id, tag_id, created_at)
            VALUES (?, ?, ?)
            """,
            (asset_id, tag_id, now),
        )
        self._conn.execute("UPDATE image_asset SET updated_at = ? WHERE id = ?", (now, asset_id))
        self._conn.commit()

    def remove_asset_tag(self, asset_id: str, tag: str) -> None:
        name = tag.strip()
        if not name:
            return
        self._conn.execute(
            """
            DELETE FROM image_tag
            WHERE asset_id = ?
              AND tag_id IN (SELECT id FROM tag WHERE name = ?)
            """,
            (asset_id, name),
        )
        self._conn.execute("UPDATE image_asset SET updated_at = ? WHERE id = ?", (_utc_now(), asset_id))
        self._conn.commit()

    def set_asset_tags(self, asset_id: str, tags: Iterable[str]) -> None:
        normalized: list[str] = []
        seen: set[str] = set()
        for tag in tags:
            name = tag.strip()
            if name and name not in seen:
                seen.add(name)
                normalized.append(name)
        self._conn.execute("DELETE FROM image_tag WHERE asset_id = ?", (asset_id,))
        self._conn.commit()
        for name in normalized:
            self.add_asset_tag(asset_id, name)

    def asset_tags(self, asset_id: str) -> list[str]:
        rows = self._conn.execute(
            """
            SELECT tag.name
            FROM tag
            INNER JOIN image_tag ON image_tag.tag_id = tag.id
            WHERE image_tag.asset_id = ?
            ORDER BY tag.name COLLATE NOCASE ASC
            """,
            (asset_id,),
        ).fetchall()
        return [str(row["name"]) for row in rows]

    def tag_counts(self) -> list[tuple[str, int]]:
        rows = self._conn.execute(
            """
            SELECT tag.name, COUNT(image_tag.asset_id) AS count
            FROM tag
            INNER JOIN image_tag ON image_tag.tag_id = tag.id
            INNER JOIN image_asset ON image_asset.id = image_tag.asset_id
            WHERE image_asset.missing = 0
            GROUP BY tag.id, tag.name
            ORDER BY tag.name COLLATE NOCASE ASC
            """
        ).fetchall()
        return [(str(row["name"]), int(row["count"])) for row in rows]

    def refresh_missing_flags(self) -> None:
        rows = self._conn.execute("SELECT id, path, missing FROM image_asset").fetchall()
        for row in rows:
            missing = 0 if Path(row["path"]).is_file() else 1
            if missing != int(row["missing"]):
                self._conn.execute(
                    "UPDATE image_asset SET missing = ?, updated_at = ? WHERE id = ?",
                    (missing, _utc_now(), row["id"]),
                )
        self._conn.commit()

    def folder_counts(self) -> list[tuple[str, int]]:
        rows = self._conn.execute(
            """
            SELECT folder_path, COUNT(*) AS count
            FROM image_asset
            WHERE missing = 0
            GROUP BY folder_path
            ORDER BY folder_path ASC
            """
        ).fetchall()
        return [(str(row["folder_path"]), int(row["count"])) for row in rows]

    def project_summary(self) -> LibraryProject:
        row = self._conn.execute(
            """
            SELECT name, root_path, created_at, updated_at
            FROM library_project
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ).fetchone()
        assets = self.query_images(include_missing=False)
        cover_assets = random.sample(assets, min(len(assets), 4)) if assets else []
        cover_paths = tuple(asset.path for asset in cover_assets)
        cover_path = cover_paths[0] if cover_paths else ""
        name = str(row["name"]) if row else self.library_path.stem
        root_path = str(row["root_path"]) if row and row["root_path"] else None
        created_at = str(row["created_at"]) if row else ""
        updated_at = str(row["updated_at"]) if row else ""
        return LibraryProject(
            name=name,
            library_path=str(self.library_path),
            root_path=root_path,
            image_count=len(assets),
            cover_path=cover_path,
            cover_paths=cover_paths,
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _row_to_asset(row: sqlite3.Row) -> LibraryAsset:
        return LibraryAsset(
            id=str(row["id"]),
            path=str(row["path"]),
            file_name=str(row["file_name"]),
            folder_path=str(row["folder_path"]),
            extension=str(row["extension"]),
            file_size=int(row["file_size"] or 0),
            width=int(row["width"]) if row["width"] is not None else None,
            height=int(row["height"]) if row["height"] is not None else None,
            rating=int(row["rating"]),
            missing=bool(row["missing"]),
            imported_at=str(row["imported_at"]),
            updated_at=str(row["updated_at"]),
        )


class LibraryProjectIndex:
    """SQLite index of local library projects shown on the gallery start page."""

    DB_NAME = "library-index.sqlite"

    def __init__(self, index_path: str | Path | None = None) -> None:
        self.index_path = Path(index_path).expanduser().resolve() if index_path else self.default_path()
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.index_path))
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    @staticmethod
    def default_path() -> Path:
        return Path.home() / ".tempusloom" / "gallery" / LibraryProjectIndex.DB_NAME

    def close(self) -> None:
        self._conn.close()

    def _ensure_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS library_registry (
              library_path TEXT PRIMARY KEY,
              registered_at TEXT NOT NULL,
              opened_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_library_registry_opened_at
            ON library_registry(opened_at);
            """
        )
        self._conn.commit()

    def register_library(self, library_path: str | Path) -> None:
        normalized = _normalize_path(library_path)
        now = _utc_now()
        self._conn.execute(
            """
            INSERT INTO library_registry (library_path, registered_at, opened_at)
            VALUES (?, ?, ?)
            ON CONFLICT(library_path) DO UPDATE SET opened_at = excluded.opened_at
            """,
            (normalized, now, now),
        )
        self._conn.commit()

    def unregister_library(self, library_path: str | Path) -> None:
        self._conn.execute(
            "DELETE FROM library_registry WHERE library_path = ?",
            (_normalize_path(library_path),),
        )
        self._conn.commit()

    def list_projects(self) -> list[LibraryProject]:
        rows = self._conn.execute(
            """
            SELECT library_path
            FROM library_registry
            ORDER BY opened_at DESC
            """
        ).fetchall()
        projects: list[LibraryProject] = []
        for row in rows:
            path = Path(str(row["library_path"]))
            db_path = path if path.suffix == ".sqlite" else path / LibraryStore.DB_NAME
            if not db_path.is_file():
                continue
            try:
                store = LibraryStore.open(path)
                projects.append(store.project_summary())
                store.close()
            except Exception:
                continue
        projects.sort(key=lambda project: project.created_at, reverse=True)
        return projects

    def global_tag_counts(self) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for store in self._open_registered_stores():
            try:
                for name, count in store.tag_counts():
                    counts[name] = counts.get(name, 0) + count
            finally:
                store.close()
        return sorted(counts.items(), key=lambda item: item[0].casefold())

    def query_images_by_tag(self, tag: str) -> list[LibraryAsset]:
        assets: list[LibraryAsset] = []
        for store in self._open_registered_stores():
            try:
                assets.extend(store.query_images(tag=tag))
            finally:
                store.close()
        return assets

    def add_tag_for_asset_path(self, asset_path: str | Path, tag: str) -> bool:
        normalized = _normalize_path(asset_path)
        for store in self._open_registered_stores():
            try:
                asset = store.get_asset_by_path(normalized)
                if asset:
                    store.add_asset_tag(asset.id, tag)
                    return True
            finally:
                store.close()
        return False

    def save_edit_state_for_asset_path(self, asset_path: str | Path, snapshot: dict) -> bool:
        normalized = _normalize_path(asset_path)
        for store in self._open_registered_stores():
            try:
                asset = store.get_asset_by_path(normalized)
                if asset:
                    store.save_asset_edit_state(asset.id, snapshot)
                    return True
            finally:
                store.close()
        return False

    def load_edit_state_for_asset_path(self, asset_path: str | Path) -> Optional[dict]:
        normalized = _normalize_path(asset_path)
        for store in self._open_registered_stores():
            try:
                asset = store.get_asset_by_path(normalized)
                if asset:
                    return store.asset_edit_state(asset.id)
            finally:
                store.close()
        return None

    def _open_registered_stores(self) -> list[LibraryStore]:
        rows = self._conn.execute(
            """
            SELECT library_path
            FROM library_registry
            ORDER BY opened_at DESC
            """
        ).fetchall()
        stores: list[LibraryStore] = []
        for row in rows:
            path = Path(str(row["library_path"]))
            db_path = path if path.suffix == ".sqlite" else path / LibraryStore.DB_NAME
            if not db_path.is_file():
                continue
            try:
                stores.append(LibraryStore.open(path))
            except Exception:
                continue
        return stores
