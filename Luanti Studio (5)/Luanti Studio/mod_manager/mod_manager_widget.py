from pathlib import Path
from typing import Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.settings import AppSettings
from mod_manager.indexer import ImportedModManifest, LuantiResourceIndexer


class ModManagerWidget(QWidget):
    """
    Module 10 — Gestionnaire de Mods Communautaires avec indexation automatique des IDs
    et protection stricte en Mode Code Pur (Mode B).
    """

    def __init__(
        self,
        settings: AppSettings,
        on_open_file_in_ide: Optional[Callable[[Path], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.on_open_file_in_ide = on_open_file_in_ide
        self.external_mods_dir = self.settings.data_dir / "imported_mods"
        self.external_mods_dir.mkdir(parents=True, exist_ok=True)
        self.manifests: Dict[str, ImportedModManifest] = {}

        self._build_ui()
        self.scan_imported_mods()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        top_bar = QHBoxLayout()
        title = QLabel("GESTIONNAIRE DE MODS COMMUNAUTAIRES (Indexation Automatique & Mode Code Pur)")
        title.setStyleSheet("font-size: 16px; font-weight: 800; color: #00E5FF;")

        btn_import_zip = QPushButton("+ Importer Archive .ZIP")
        btn_import_zip.setProperty("primary", True)
        btn_import_zip.clicked.connect(self._import_zip)

        btn_import_dir = QPushButton("+ Importer Dossier de Mod")
        btn_import_dir.clicked.connect(self._import_folder)

        btn_toggle = QPushButton("Activer / Désactiver")
        btn_toggle.clicked.connect(self._toggle_selected_mod)

        btn_del = QPushButton("Supprimer Mod")
        btn_del.setProperty("danger", True)
        btn_del.clicked.connect(self._delete_selected_mod)

        top_bar.addWidget(title)
        top_bar.addStretch(1)
        top_bar.addWidget(btn_import_zip)
        top_bar.addWidget(btn_import_dir)
        top_bar.addWidget(btn_toggle)
        top_bar.addWidget(btn_del)
        layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Tableau des mods importés
        mods_box = QGroupBox("Mods Externes Indexés (Mode B : Code Pur Non-Converti en Blockly)")
        mods_vbox = QVBoxLayout(mods_box)
        self.mods_table = QTableWidget(0, 5)
        self.mods_table.setHorizontalHeaderLabels(["Mod ID", "Statut", "Dépendances", "Ressources Détectées", "Mode"])
        self.mods_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.mods_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.mods_table.itemSelectionChanged.connect(self._on_mod_selected)
        mods_vbox.addWidget(self.mods_table)
        splitter.addWidget(mods_box)

        # Détails des ressources et fichiers Lua du mod sélectionné
        details_box = QGroupBox("Ressources Indexées (Nodes, Items, Entités, Commandes) & Fichiers Lua")
        det_vbox = QVBoxLayout(details_box)
        self.res_tree = QTreeWidget()
        self.res_tree.setHeaderLabels(["Identifiant / Fichier", "Type", "Source"])
        self.res_tree.itemDoubleClicked.connect(self._on_resource_double_clicked)
        det_vbox.addWidget(self.res_tree)

        self.code_preview = QPlainTextEdit()
        self.code_preview.setReadOnly(True)
        self.code_preview.setMaximumHeight(180)
        det_vbox.addWidget(self.code_preview)

        splitter.addWidget(details_box)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, stretch=1)

    def scan_imported_mods(self) -> None:
        self.manifests.clear()
        for sub in sorted(self.external_mods_dir.iterdir()):
            if sub.is_dir():
                man = LuantiResourceIndexer.index_mod_directory(sub)
                self.manifests[man.mod_id] = man
        self._refresh_table()

    def _refresh_table(self) -> None:
        self.mods_table.setRowCount(0)
        for row, man in enumerate(self.manifests.values()):
            self.mods_table.insertRow(row)
            vals = [
                man.mod_id,
                "Actif" if man.enabled else "Désactivé",
                ", ".join(man.dependencies) or "Aucune",
                f"{len(man.resources)} IDs, {len(man.textures)} PNG, {len(man.models)} 3D",
                "Mode B (Code Pur)",
            ]
            for col, text in enumerate(vals):
                it = QTableWidgetItem(text)
                it.setData(Qt.ItemDataRole.UserRole, man.mod_id)
                self.mods_table.setItem(row, col, it)

    def _get_selected_manifest(self) -> Optional[ImportedModManifest]:
        items = self.mods_table.selectedItems()
        if not items:
            return None
        mod_id = str(items[0].data(Qt.ItemDataRole.UserRole))
        return self.manifests.get(mod_id)

    def _on_mod_selected(self) -> None:
        man = self._get_selected_manifest()
        self.res_tree.clear()
        if not man:
            return

        res_root = QTreeWidgetItem(["Identifiants Luanti détectés", f"{len(man.resources)}", ""])
        self.res_tree.addTopLevelItem(res_root)
        for res in man.resources:
            child = QTreeWidgetItem([res.full_id, res.resource_type, res.source_file])
            child.setData(0, Qt.ItemDataRole.UserRole, str(Path(man.path) / res.source_file))
            res_root.addChild(child)

        files_root = QTreeWidgetItem(["Scripts Lua du mod", f"{len(man.lua_files)}", ""])
        self.res_tree.addTopLevelItem(files_root)
        for rel_lua in man.lua_files:
            f_item = QTreeWidgetItem([rel_lua, "Script Lua", man.mod_id])
            f_item.setData(0, Qt.ItemDataRole.UserRole, str(Path(man.path) / rel_lua))
            files_root.addChild(f_item)

        self.res_tree.expandAll()

    def _on_resource_double_clicked(self, item: QTreeWidgetItem) -> None:
        raw_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not raw_path:
            return
        fpath = Path(str(raw_path))
        if fpath.exists() and fpath.is_file():
            self.code_preview.setPlainText(fpath.read_text(encoding="utf-8", errors="replace"))
            if self.on_open_file_in_ide:
                self.on_open_file_in_ide(fpath)

    def _import_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importer un mod ZIP", "", "Archives ZIP (*.zip)")
        if not path:
            return
        try:
            man = LuantiResourceIndexer.import_external_mod(Path(path), self.external_mods_dir)
            self.manifests[man.mod_id] = man
            self._refresh_table()
        except Exception as exc:
            QMessageBox.critical(self, "Erreur d'importation", str(exc))

    def _import_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier d'un mod Luanti")
        if not chosen:
            return
        try:
            man = LuantiResourceIndexer.import_external_mod(Path(chosen), self.external_mods_dir)
            self.manifests[man.mod_id] = man
            self._refresh_table()
        except Exception as exc:
            QMessageBox.critical(self, "Erreur d'importation", str(exc))

    def _toggle_selected_mod(self) -> None:
        man = self._get_selected_manifest()
        if man:
            man.enabled = not man.enabled
            self._refresh_table()

    def _delete_selected_mod(self) -> None:
        man = self._get_selected_manifest()
        if not man:
            return
        import shutil
        mod_path = Path(man.path)
        if mod_path.exists():
            shutil.rmtree(mod_path)
        self.manifests.pop(man.mod_id, None)
        self._refresh_table()
        self.res_tree.clear()