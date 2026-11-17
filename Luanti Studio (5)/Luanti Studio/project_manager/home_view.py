from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.settings import AppSettings
from project_manager.manager import ProjectManager
from shared.dialogs import NewProjectDialog


class HomeView(QWidget):
    """Page d'accueil professionnelle permettant de gérer les projets Luanti Creator Studio."""

    project_opened = Signal(str)  # Émet le chemin du dossier projet ouvert

    def __init__(
        self,
        project_manager: ProjectManager,
        settings: AppSettings,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.pm = project_manager
        self.settings = settings
        self._build_ui()
        self.refresh_recent_projects()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(18)

        # Bannière d'en-tête
        header_box = QGroupBox()
        header_layout = QVBoxLayout(header_box)
        title = QLabel("LUANTI CREATOR STUDIO")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #00E5FF;")
        subtitle = QLabel(
            "Environnement visuel tout-en-un de création de Mods, Mobs, Blocs, Items, Commandes, Formspecs et Mondes 3D pour Luanti."
        )
        subtitle.setStyleSheet("color: #94A3B8; font-size: 13px;")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root_layout.addWidget(header_box)

        # Barre d'actions rapides
        actions_group = QGroupBox("Actions sur les projets")
        actions_layout = QHBoxLayout(actions_group)

        self.btn_new = QPushButton("+ Nouveau projet")
        self.btn_new.setProperty("primary", True)
        self.btn_new.clicked.connect(self.create_new_project_dialog)

        self.btn_open = QPushButton("Ouvrir un projet...")
        self.btn_open.clicked.connect(self.open_existing_project_dialog)

        self.btn_duplicate = QPushButton("Dupliquer la sélection")
        self.btn_duplicate.clicked.connect(self.duplicate_selected_project)

        self.btn_import_zip = QPushButton("Importer ZIP / Mod...")
        self.btn_import_zip.clicked.connect(self.import_zip_project_dialog)

        self.btn_export_zip = QPushButton("Exporter le projet actif (.zip)")
        self.btn_export_zip.clicked.connect(self.export_active_project_dialog)

        self.btn_delete = QPushButton("Supprimer la sélection")
        self.btn_delete.setProperty("danger", True)
        self.btn_delete.clicked.connect(self.delete_selected_project)

        for btn in (
            self.btn_new,
            self.btn_open,
            self.btn_duplicate,
            self.btn_import_zip,
            self.btn_export_zip,
            self.btn_delete,
        ):
            actions_layout.addWidget(btn)

        root_layout.addWidget(actions_group)

        # Tableau des projets récents
        recent_group = QGroupBox("Projets récents (Base SQLite locale)")
        recent_layout = QVBoxLayout(recent_group)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Nom du Projet",
            "Identifiant (mod_id)",
            "Jeu de base",
            "Version Luanti",
            "Emplacement sur disque",
            "Dernière ouverture",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._open_from_table_double_click)

        recent_layout.addWidget(self.table)
        root_layout.addWidget(recent_group, stretch=1)

    def refresh_recent_projects(self) -> None:
        projects = self.pm.db.list_recent_projects()
        self.table.setRowCount(0)
        for row_idx, proj in enumerate(projects):
            self.table.insertRow(row_idx)
            status_prefix = "" if proj["exists"] else "[Introuvable] "
            items = [
                f"{status_prefix}{proj['name']}",
                proj["mod_id"],
                proj["base_game"],
                proj["target_version"],
                proj["project_path"],
                proj["last_opened"][:19].replace("T", " "),
            ]
            for col_idx, text in enumerate(items):
                item = QTableWidgetItem(str(text))
                item.setData(Qt.ItemDataRole.UserRole, proj["project_path"])
                self.table.setItem(row_idx, col_idx, item)

    def _get_selected_project_path(self) -> Optional[Path]:
        selected = self.table.selectedItems()
        if not selected:
            return None
        raw_path = selected[0].data(Qt.ItemDataRole.UserRole)
        return Path(str(raw_path)) if raw_path else None

    def _open_from_table_double_click(self) -> None:
        path = self._get_selected_project_path()
        if path:
            self._open_project_at(path)

    def _open_project_at(self, path: Path) -> None:
        try:
            self.pm.open_project(path)
            self.refresh_recent_projects()
            self.project_opened.emit(str(path))
        except Exception as exc:
            QMessageBox.critical(self, "Erreur d'ouverture", str(exc))

    def create_new_project_dialog(self) -> None:
        dlg = NewProjectDialog(self.settings, self)
        if dlg.exec() == NewProjectDialog.DialogCode.Accepted:
            vals = dlg.get_values()
            try:
                _, proj_dir = self.pm.create_project(**vals)
                self.refresh_recent_projects()
                self.project_opened.emit(str(proj_dir))
            except Exception as exc:
                QMessageBox.critical(self, "Erreur de création", str(exc))

    def open_existing_project_dialog(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Sélectionner le dossier d'un projet Luanti Creator Studio",
            str(self.settings.default_projects_dir),
        )
        if chosen:
            self._open_project_at(Path(chosen))

    def duplicate_selected_project(self) -> None:
        source_path = self._get_selected_project_path()
        if not source_path or not source_path.exists():
            QMessageBox.information(
                self, "Sélection requise", "Sélectionnez un projet valide dans la liste pour le dupliquer."
            )
            return

        new_name, ok = QInputDialog.getText(
            self, "Dupliquer le projet", "Nouveau nom du projet :", text=f"{source_path.name}_copy"
        )
        if not ok or not new_name.strip():
            return

        try:
            _, target_dir = self.pm.duplicate_project(source_path, new_name, new_name)
            self.refresh_recent_projects()
            self.project_opened.emit(str(target_dir))
        except Exception as exc:
            QMessageBox.critical(self, "Erreur de duplication", str(exc))

    def delete_selected_project(self) -> None:
        target_path = self._get_selected_project_path()
        if not target_path:
            QMessageBox.information(
                self, "Sélection requise", "Sélectionnez un projet dans le tableau pour le supprimer."
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirmer la suppression",
            f"Voulez-vous vraiment supprimer définitivement le projet :\n{target_path} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.pm.delete_project(target_path)
                self.refresh_recent_projects()
            except Exception as exc:
                QMessageBox.critical(self, "Erreur de suppression", str(exc))

    def import_zip_project_dialog(self) -> None:
        zip_file, _ = QFileDialog.getOpenFileName(
            self,
            "Importer un projet ou mod Luanti (.zip)",
            str(self.settings.default_projects_dir),
            "Archives ZIP (*.zip)",
        )
        if not zip_file:
            return
        try:
            _, proj_dir = self.pm.import_project_from_zip(
                Path(zip_file), self.settings.default_projects_dir
            )
            self.refresh_recent_projects()
            self.project_opened.emit(str(proj_dir))
        except Exception as exc:
            QMessageBox.critical(self, "Erreur d'importation ZIP", str(exc))

    def export_active_project_dialog(self) -> None:
        if not self.pm.current_project:
            QMessageBox.information(
                self, "Aucun projet actif", "Ouvrez ou créez un projet avant de l'exporter."
            )
            return
        default_name = f"{self.pm.current_project.mod_id}.zip"
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter le mod en archive ZIP",
            str(self.settings.default_projects_dir / default_name),
            "Archive ZIP (*.zip)",
        )
        if dest:
            try:
                out = self.pm.export_mod_zip(Path(dest))
                QMessageBox.information(
                    self, "Exportation réussie", f"Archive Luanti générée avec succès :\n{out}"
                )
            except Exception as exc:
                QMessageBox.critical(self, "Erreur d'exportation", str(exc))