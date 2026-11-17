# -*- coding: utf-8 -*-
"""
workers/test_runner.py
Lanceur stable de Luanti avec gestion du Working Directory et des flux de logs.
"""

import json
import os
from typing import Optional

try:
    from PyQt6.QtCore import QObject, QProcess, pyqtSignal
    from PyQt6.QtWidgets import QFileDialog, QMessageBox
except ImportError:
    from PyQt5.QtCore import QObject, QProcess, pyqtSignal
    from PyQt5.QtWidgets import QFileDialog, QMessageBox


CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".luanti_studio_settings.json")


class LuantiTestRunner(QObject):
    logReceived = pyqtSignal(str)
    processStateChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process: Optional[QProcess] = None
        self.luanti_exe_path: str = self._load_saved_exe_path()

    def _load_saved_exe_path(self) -> str:
        if os.path.isfile(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    exe = data.get("luanti_exe_path", "")
                    if exe and os.path.isfile(exe):
                        return exe
            except Exception:
                pass
        return self._auto_detect_luanti_executable()

    def _save_exe_path(self, path: str):
        self.luanti_exe_path = path
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"luanti_exe_path": path}, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def _auto_detect_luanti_executable() -> str:
        user_home = os.path.expanduser("~")
        candidates = [
            r"C:\Program Files\Luanti\bin\luanti.exe",
            r"C:\Program Files\Minetest\bin\minetest.exe",
            r"C:\Luanti\bin\luanti.exe",
            r"C:\Minetest\bin\minetest.exe",
            os.path.join(user_home, "Downloads", "luanti", "bin", "luanti.exe"),
            os.path.join(user_home, "Desktop", "luanti", "bin", "luanti.exe"),
            r"F:\Download\luanti\bin\luanti.exe",
            r"F:\Download\minetest\bin\minetest.exe",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return ""

    def ensure_executable_configured(self, parent_widget=None) -> Optional[str]:
        if self.luanti_exe_path and os.path.isfile(self.luanti_exe_path):
            return self.luanti_exe_path

        exe_path, _ = QFileDialog.getOpenFileName(
            parent_widget,
            "Sélectionner luanti.exe ou minetest.exe",
            "",
            "Exécutable Luanti / Minetest (luanti.exe minetest.exe);;Tous les fichiers (*)",
        )
        if exe_path and os.path.isfile(exe_path):
            self._save_exe_path(exe_path)
            return exe_path
        return None

    def get_luanti_root_dir(self) -> Optional[str]:
        if not self.luanti_exe_path or not os.path.isfile(self.luanti_exe_path):
            return None
        bin_dir = os.path.dirname(os.path.abspath(self.luanti_exe_path))
        return os.path.dirname(bin_dir)

    def prepare_test_world_and_mod_dir(self, mod_name: str, void_world: bool = True) -> Tuple[str, str]:
        root_dir = self.get_luanti_root_dir()
        if not root_dir:
            raise RuntimeError("Dossier racine Luanti introuvable.")

        mods_dir = os.path.join(root_dir, "mods")
        worlds_dir = os.path.join(root_dir, "worlds")
        os.makedirs(mods_dir, exist_ok=True)
        os.makedirs(worlds_dir, exist_ok=True)

        target_mod_dir = os.path.join(mods_dir, mod_name)
        test_world_dir = os.path.join(worlds_dir, "LuantiStudio_TestWorld")
        os.makedirs(target_mod_dir, exist_ok=True)
        os.makedirs(test_world_dir, exist_ok=True)

        world_mt_path = os.path.join(test_world_dir, "world.mt")
        existing_lines = {}
        if os.path.isfile(world_mt_path):
            with open(world_mt_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.split("=", 1)
                        existing_lines[k.strip()] = v.strip()

        existing_lines["gameid"] = existing_lines.get("gameid", "minetest")
        existing_lines["backend"] = "sqlite3"
        existing_lines["creative_mode"] = "true"
        existing_lines["enable_damage"] = "true"
        existing_lines[f"load_mod_{mod_name}"] = "true"

        with open(world_mt_path, "w", encoding="utf-8") as f:
            for k, v in existing_lines.items():
                f.write(f"{k} = {v}\n")

        return target_mod_dir, test_world_dir

    def launch_and_detach(self, test_world_dir: str):
        """Lance Luanti de manière isolée dans son dossier bin/ pour éviter les crashs de contexte."""
        bin_dir = os.path.dirname(os.path.abspath(self.luanti_exe_path))
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()

        self.process = QProcess(self)
        self.process.setWorkingDirectory(bin_dir)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._on_ready_read)
        self.process.finished.connect(lambda code, status: self.processStateChanged.emit(False))

        args = ["--world", test_world_dir, "--go", "--name", "Creator"]
        self.logReceived.emit(f"[Luanti Studio] Lancement depuis {bin_dir}...\n")
        self.process.start(self.luanti_exe_path, args)
        self.processStateChanged.emit(True)

    def launch_luanti_with_mod(self, test_world_dir: str):
        self.launch_and_detach(test_world_dir)

    def stop_luanti(self):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()

    def _on_ready_read(self):
        if not self.process:
            return
        data = self.process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        if data:
            self.logReceived.emit(data)