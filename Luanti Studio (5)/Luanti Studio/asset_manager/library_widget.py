import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from storage.database import StudioDatabase


class AssetLibraryWidget(QWidget):
    """Module 14 — Bibliothèque centrale multi-projets (Textures, Modèles, Animations, Blockly, Structures, GUIs)."""

    CATEGORIES = [
        ("all", "Toutes les catégories"),
        ("texture", "Textures PNG"),
        ("model", "Modèles 3D (GLB / Nodebox)"),
        ("animation", "Animations"),
        ("blockly", "Comportements Blockly"),
        ("structure", "Structures Voxel (.mts)"),
        ("gui", "Interfaces Formspec"),
    ]

    def __init__(self, database: StudioDatabase, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.db = database
        self._build_ui()
        self.refresh_assets()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        top_bar = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Rechercher dans la bibliothèque centrale...")
        self.search_edit.textChanged.connect(self.refresh_assets)

        self.cat_combo = QComboBox()
        for cid, clbl in self.CATEGORIES:
            self.cat_combo.addItem(clbl, cid)
        self.cat_combo.currentIndexChanged.connect(self.refresh_assets)

        btn_add = QPushButton("+ Ajouter une Ressource à la Bibliothèque")
        btn_add.setProperty("primary", True)
        btn_add.clicked.connect(self._register_new_asset_dialog)

        top_bar.addWidget(self.search_edit, stretch=1)
        top_bar.addWidget(self.cat_combo)
        top_bar.addWidget(btn_add)
        layout.addLayout(top_bar)

        box = QGroupBox("Ressources Réutilisables Multi-Projets (Stockage SQLite)")
        vbox = QVBoxLayout(box)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Nom", "Catégorie", "Fichier", "Favori", "Date d'ajout"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        vbox.addWidget(self.table)
        layout.addWidget(box, stretch=1)

    def refresh_assets(self) -> None:
        query = self.search_edit.text().strip().lower()
        cat_filter = str(self.cat_combo.currentData())

        with self.db._connect() as conn:
            rows = conn.execute("SELECT * FROM library_assets ORDER BY created_at DESC").fetchall()

        self.table.setRowCount(0)
        for row in rows:
            name = str(row["name"])
            cat = str(row["category"])
            if query and query not in name.lower():
                continue
            if cat_filter != "all" and cat != cat_filter:
                continue
            r_idx = self.table.rowCount()
            self.table.insertRow(r_idx)
            self.table.setItem(r_idx, 0, QTableWidgetItem(name))
            self.table.setItem(r_idx, 1, QTableWidgetItem(cat))
            self.table.setItem(r_idx, 2, QTableWidgetItem(str(row["file_path"])))
            self.table.setItem(r_idx, 3, QTableWidgetItem("★ Oui" if row["is_favorite"] else "Non"))
            self.table.setItem(r_idx, 4, QTableWidgetItem(str(row["created_at"])[:19]))

    def _register_new_asset_dialog(self) -> None:
        fpath, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner une ressource à enregistrer dans la bibliothèque",
            "",
            "Toutes les ressources (*.png *.glb *.gltf *.obj *.mts *.json *.lua)",
        )
        if not fpath:
            return
        name, ok = QInputDialog.getText(self, "Nom de la ressource", "Nom :", text=Path(fpath).stem)
        if not ok or not name.strip():
            return

        ext = Path(fpath).suffix.lower()
        cat = "texture" if ext == ".png" else ("model" if ext in (".glb", ".gltf", ".obj") else ("structure" if ext == ".mts" else "blockly"))
        uid = f"asset_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        with self.db._connect() as conn:
            conn.execute(
                """
                INSERT INTO library_assets (asset_uid, name, category, source_project, file_path, metadata_json, is_favorite, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (uid, name.strip(), cat, "Global", fpath, json.dumps({"ext": ext}), now),
            )
        self.refresh_assets()
        QMessageBox.information(self, "Ressource indexée", f"'{name}' est maintenant réutilisable dans tous vos projets.")