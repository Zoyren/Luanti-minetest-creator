import os
import platform
from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import QSettings


class AppSettings:
    """Gestionnaire central des préférences utilisateur et de la détection de Luanti."""

    ORGANIZATION = "LuantiCreatorStudio"
    APPLICATION = "StudioDesktop"

    def __init__(self) -> None:
        self._settings = QSettings(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            self.ORGANIZATION,
            self.APPLICATION,
        )
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        default_workspace = Path.home() / "LuantiCreatorProjects"
        default_workspace.mkdir(parents=True, exist_ok=True)

        if not self._settings.value("workspace/default_dir"):
            self._settings.setValue("workspace/default_dir", str(default_workspace))

        if not self._settings.value("luanti/executable_path"):
            detected = self.auto_detect_luanti_executable()
            if detected:
                self._settings.setValue("luanti/executable_path", str(detected))

        if not self._settings.value("luanti/target_version"):
            self._settings.setValue("luanti/target_version", "5.18.0")

        if not self._settings.value("luanti/default_base_game"):
            self._settings.setValue("luanti/default_base_game", "minetest_game")

    @property
    def data_dir(self) -> Path:
        path = Path.home() / ".luanti_creator_studio"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def default_projects_dir(self) -> Path:
        val = str(self._settings.value("workspace/default_dir", ""))
        path = Path(val) if val else (Path.home() / "LuantiCreatorProjects")
        path.mkdir(parents=True, exist_ok=True)
        return path

    @default_projects_dir.setter
    def default_projects_dir(self, path: Path) -> None:
        self._settings.setValue("workspace/default_dir", str(path))

    @property
    def luanti_executable(self) -> str:
        return str(self._settings.value("luanti/executable_path", ""))

    @luanti_executable.setter
    def luanti_executable(self, path: str) -> None:
        self._settings.setValue("luanti/executable_path", path)

    @property
    def target_luanti_version(self) -> str:
        return str(self._settings.value("luanti/target_version", "5.18.0"))

    @target_luanti_version.setter
    def target_luanti_version(self, version: str) -> None:
        self._settings.setValue("luanti/target_version", version)

    @property
    def auto_save_interval_sec(self) -> int:
        return int(self._settings.value("editor/autosave_sec", 60))

    @auto_save_interval_sec.setter
    def auto_save_interval_sec(self, seconds: int) -> None:
        self._settings.setValue("editor/autosave_sec", max(10, seconds))

    def auto_detect_luanti_executable(self) -> Optional[Path]:
        """Détecte automatiquement une installation locale de Luanti / Minetest."""
        candidates: List[Path] = []
        cwd = Path.cwd()

        # Recherche dans le dossier courant (ex: luanti-5.18.0-win64/bin/luanti.exe)
        for pattern in ["luanti*/bin/luanti.exe", "luanti*/bin/luanti", "minetest*/bin/minetest.exe"]:
            candidates.extend(cwd.glob(pattern))
            candidates.extend(cwd.parent.glob(pattern))

        if platform.system() == "Windows":
            local_app = Path(os.environ.get("LOCALAPPDATA", ""))
            prog_files = Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
            candidates.extend([
                local_app / "Luanti" / "bin" / "luanti.exe",
                local_app / "Minetest" / "bin" / "minetest.exe",
                prog_files / "Luanti" / "bin" / "luanti.exe",
                Path.home() / "Desktop" / "luanti-5.18.0-win64" / "bin" / "luanti.exe",
            ])
        else:
            candidates.extend([
                Path("/usr/bin/luanti"),
                Path("/usr/local/bin/luanti"),
                Path("/usr/bin/minetest"),
                Path("/usr/games/luanti"),
                Path("/usr/games/minetest"),
            ])

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        return None

    def detect_installed_base_games(self) -> List[Dict[str, str]]:
        """Scanne les dossiers Luanti pour lister les jeux de base réellement installés."""
        games: List[Dict[str, str]] = []
        seen_ids = set()

        search_roots: List[Path] = []
        if self.luanti_executable:
            exe_path = Path(self.luanti_executable)
            if exe_path.exists():
                # Structure portable : luanti-x.x/bin/luanti.exe -> luanti-x.x/games
                search_roots.append(exe_path.parent.parent / "games")

        search_roots.extend([
            Path.home() / ".minetest" / "games",
            Path.home() / ".local" / "share" / "luanti" / "games",
            Path.home() / ".local" / "share" / "minetest" / "games",
            Path("/usr/share/luanti/games"),
            Path("/usr/share/minetest/games"),
        ])

        for root in search_roots:
            if not root.exists():
                continue
            for game_dir in root.iterdir():
                if not game_dir.is_dir():
                    continue
                conf_file = game_dir / "game.conf"
                game_id = game_dir.name
                game_name = game_id
                if conf_file.exists():
                    try:
                        for line in conf_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                            if line.strip().startswith("name") and "=" in line:
                                game_name = line.split("=", 1)[1].strip()
                    except Exception:
                        pass
                if game_id not in seen_ids:
                    seen_ids.add(game_id)
                    games.append({
                        "id": game_id,
                        "name": f"{game_name} ({game_id})",
                        "path": str(game_dir.resolve()),
                    })

        # Toujours proposer les profils standards même si non détectés sur disque
        defaults = [
            ("minetest_game", "Luanti / Minetest Game (minetest_game)"),
            ("mineclonia", "Mineclonia (mineclonia)"),
            ("devtest", "Development Test (devtest)"),
        ]
        for gid, gname in defaults:
            if gid not in seen_ids:
                games.append({"id": gid, "name": gname, "path": ""})

        return games