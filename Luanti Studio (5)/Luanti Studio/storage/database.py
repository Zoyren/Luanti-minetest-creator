import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class StudioDatabase:
    """Base de données SQLite gérant les projets récents, la bibliothèque centrale et la protection du code."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS recent_projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mod_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    base_game TEXT NOT NULL,
                    target_version TEXT NOT NULL,
                    project_path TEXT NOT NULL UNIQUE,
                    last_opened TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS library_assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_uid TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL, -- texture, model, animation, blockly, gui, structure
                    source_project TEXT,
                    file_path TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    is_favorite INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS file_hashes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_path TEXT NOT NULL,
                    relative_file_path TEXT NOT NULL,
                    last_generated_sha256 TEXT NOT NULL,
                    is_manually_modified INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    UNIQUE(project_path, relative_file_path)
                );
                """
            )

    def upsert_recent_project(
        self,
        mod_id: str,
        name: str,
        description: str,
        base_game: str,
        target_version: str,
        project_path: Path,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        resolved = str(project_path.resolve())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO recent_projects (mod_id, name, description, base_game, target_version, project_path, last_opened)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_path) DO UPDATE SET
                    mod_id = excluded.mod_id,
                    name = excluded.name,
                    description = excluded.description,
                    base_game = excluded.base_game,
                    target_version = excluded.target_version,
                    last_opened = excluded.last_opened
                """,
                (mod_id, name, description, base_game, target_version, resolved, now),
            )

    def list_recent_projects(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM recent_projects ORDER BY last_opened DESC"
            ).fetchall()
        valid_projects: List[Dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            p = Path(data["project_path"])
            data["exists"] = (p / "project.lcs.json").exists()
            valid_projects.append(data)
        return valid_projects

    def remove_recent_project(self, project_path: Path) -> None:
        resolved = str(project_path.resolve())
        with self._connect() as conn:
            conn.execute("DELETE FROM recent_projects WHERE project_path = ?", (resolved,))

    def record_generated_file_hash(
        self, project_path: Path, relative_file_path: str, sha256_hex: str
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO file_hashes (project_path, relative_file_path, last_generated_sha256, is_manually_modified, updated_at)
                VALUES (?, ?, ?, 0, ?)
                ON CONFLICT(project_path, relative_file_path) DO UPDATE SET
                    last_generated_sha256 = excluded.last_generated_sha256,
                    is_manually_modified = 0,
                    updated_at = excluded.updated_at
                """,
                (str(project_path.resolve()), relative_file_path, sha256_hex, now),
            )

    def get_recorded_file_hash(self, project_path: Path, relative_file_path: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT last_generated_sha256 FROM file_hashes
                WHERE project_path = ? AND relative_file_path = ?
                """,
                (str(project_path.resolve()), relative_file_path),
            ).fetchone()
        return str(row["last_generated_sha256"]) if row else None