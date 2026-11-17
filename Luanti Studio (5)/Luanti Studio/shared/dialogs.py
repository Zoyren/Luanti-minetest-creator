from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.settings import AppSettings
from project_manager.manager import ProjectManager


class NewProjectDialog(QDialog):
    """Boîte de dialogue de création d'un nouveau projet Luanti Creator Studio."""

    def __init__(self, settings: AppSettings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Nouveau Projet Luanti")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Ex: Cochon & Composteur Mod")
        self.name_edit.textChanged.connect(self._auto_fill_mod_id)

        self.mod_id_edit = QLineEdit()
        self.mod_id_edit.setPlaceholderText("Ex: cochon_composteur")

        self.author_edit = QLineEdit("Creator")

        self.base_game_combo = QComboBox()
        for game in self.settings.detect_installed_base_games():
            self.base_game_combo.addItem(game["name"], game["id"])

        self.version_combo = QComboBox()
        for ver in ["5.18.0", "5.10.0", "5.9.0", "5.8.0"]:
            self.version_combo.addItem(f"Luanti {ver}", ver)

        self.mob_api_combo = QComboBox()
        self.mob_api_combo.addItem("Entités Natives Luanti (core.register_entity)", "native_entities")
        self.mob_api_combo.addItem("Mobs Redo API (mobs:register_mob)", "mobs_redo")
        self.mob_api_combo.addItem("Creatura API", "creatura")

        self.deps_edit = QLineEdit("default")
        self.deps_edit.setPlaceholderText("Dépendances séparées par des virgules (ex: default, farming)")

        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit(str(self.settings.default_projects_dir))
        browse_btn = QPushButton("Parcourir...")
        browse_btn.clicked.connect(self._browse_dir)
        dir_row.addWidget(self.dir_edit)
        dir_row.addWidget(browse_btn)

        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("Description du mod ou du jeu...")
        self.desc_edit.setMaximumHeight(80)

        form.addRow("Nom du projet :", self.name_edit)
        form.addRow("Identifiant technique (mod_id) :", self.mod_id_edit)
        form.addRow("Auteur :", self.author_edit)
        form.addRow("Jeu de base :", self.base_game_combo)
        form.addRow("Version Luanti cible :", self.version_combo)
        form.addRow("Système de Mobs :", self.mob_api_combo)
        form.addRow("Dépendances :", self.deps_edit)
        form.addRow("Dossier parent :", dir_row)
        form.addRow("Description :", self.desc_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("Créer le projet")
        ok_btn.setProperty("primary", True)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _auto_fill_mod_id(self, text: str) -> None:
        self.mod_id_edit.setText(ProjectManager.sanitize_identifier(text))

    def _browse_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Choisir le dossier des projets", self.dir_edit.text()
        )
        if chosen:
            self.dir_edit.setText(chosen)

    def _validate_and_accept(self) -> None:
        if not self.name_edit.text().strip() or not self.mod_id_edit.text().strip():
            QMessageBox.warning(self, "Champs requis", "Veuillez renseigner un nom et un identifiant de mod.")
            return
        self.accept()

    def get_values(self) -> Dict[str, object]:
        raw_deps = [d.strip() for d in self.deps_edit.text().split(",") if d.strip()]
        return {
            "parent_dir": Path(self.dir_edit.text().strip()),
            "mod_id": self.mod_id_edit.text().strip(),
            "name": self.name_edit.text().strip(),
            "description": self.desc_edit.toPlainText().strip(),
            "author": self.author_edit.text().strip(),
            "base_game": str(self.base_game_combo.currentData()),
            "luanti_version": str(self.version_combo.currentData()),
            "mob_api": str(self.mob_api_combo.currentData()),
            "dependencies": raw_deps,
        }


class NewElementDialog(QDialog):
    """Boîte de dialogue permettant d'ajouter un Mob, un Bloc, un Item, une Commande, une GUI ou un Monde."""

    CATEGORY_LABELS = [
        ("mob", "MOB — Créature / Entité 3D (ex: Pig)"),
        ("block", "BLOCK — Bloc / Node (ex: Composteur)"),
        ("item", "ITEM — Objet / Outil / Projectile (ex: Enderpearl)"),
        ("command", "COMMAND — Commande serveur (ex: /thunder)"),
        ("gui", "GUI — Interface Formspec (ex: Dialogue BDD)"),
        ("world", "WORLD — Zone / Structure 3D Voxel"),
    ]

    def __init__(
        self, default_category: str = "mob", parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Créer un nouvel élément Luanti")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.category_combo = QComboBox()
        for idx, (cat_id, label) in enumerate(self.CATEGORY_LABELS):
            self.category_combo.addItem(label, cat_id)
            if cat_id == default_category:
                self.category_combo.setCurrentIndex(idx)

        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText("Ex: Cochon Apprivoisable / Composteur / Enderpearl")
        self.display_name_edit.textChanged.connect(self._sync_identifier)

        self.identifier_edit = QLineEdit()
        self.identifier_edit.setPlaceholderText("Ex: pig / composter / enderpearl")

        form.addRow("Type d'élément :", self.category_combo)
        form.addRow("Nom d'affichage :", self.display_name_edit)
        form.addRow("Identifiant technique :", self.identifier_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("Créer l'élément")
        ok_btn.setProperty("primary", True)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _sync_identifier(self, text: str) -> None:
        self.identifier_edit.setText(ProjectManager.sanitize_identifier(text))

    def _validate(self) -> None:
        if not self.display_name_edit.text().strip() or not self.identifier_edit.text().strip():
            QMessageBox.warning(self, "Champs requis", "Veuillez indiquer un nom et un identifiant.")
            return
        self.accept()

    def get_data(self) -> Tuple[str, str, str]:
        return (
            str(self.category_combo.currentData()),
            self.identifier_edit.text().strip(),
            self.display_name_edit.text().strip(),
        )


class SettingsDialog(QDialog):
    """Boîte de dialogue de configuration globale de Luanti Creator Studio."""

    def __init__(self, settings: AppSettings, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Paramètres — Luanti Creator Studio")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        exe_row = QHBoxLayout()
        self.exe_edit = QLineEdit(self.settings.luanti_executable)
        self.exe_edit.setPlaceholderText("Chemin vers luanti.exe ou binaire luanti")
        exe_btn = QPushButton("Parcourir...")
        exe_btn.clicked.connect(self._browse_exe)
        detect_btn = QPushButton("Auto-détecter")
        detect_btn.clicked.connect(self._auto_detect)
        exe_row.addWidget(self.exe_edit)
        exe_row.addWidget(exe_btn)
        exe_row.addWidget(detect_btn)

        ws_row = QHBoxLayout()
        self.ws_edit = QLineEdit(str(self.settings.default_projects_dir))
        ws_btn = QPushButton("Parcourir...")
        ws_btn.clicked.connect(self._browse_ws)
        ws_row.addWidget(self.ws_edit)
        ws_row.addWidget(ws_btn)

        self.autosave_spin = QSpinBox()
        self.autosave_spin.setRange(10, 600)
        self.autosave_spin.setSuffix(" secondes")
        self.autosave_spin.setValue(self.settings.auto_save_interval_sec)

        form.addRow("Exécutable Luanti :", exe_row)
        form.addRow("Dossier Projets par défaut :", ws_row)
        form.addRow("Sauvegarde automatique :", self.autosave_spin)

        layout.addLayout(form)

        # Affichage des jeux détectés
        games = self.settings.detect_installed_base_games()
        games_info = ", ".join(g["id"] for g in games)
        info_label = QLabel(f"Profils de jeux disponibles : {games_info}")
        info_label.setStyleSheet("color: #38BDF8; padding-top: 6px;")
        layout.addWidget(info_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_exe(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner l'exécutable Luanti (luanti.exe / luanti)"
        )
        if path:
            self.exe_edit.setText(path)

    def _auto_detect(self) -> None:
        detected = self.settings.auto_detect_luanti_executable()
        if detected:
            self.exe_edit.setText(str(detected))
            QMessageBox.information(self, "Détection réussie", f"Exécutable trouvé :\n{detected}")
        else:
            QMessageBox.information(
                self, "Non détecté", "Aucun binaire Luanti trouvé automatiquement. Sélectionnez-le manuellement."
            )

    def _browse_ws(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Dossier des projets par défaut", self.ws_edit.text()
        )
        if chosen:
            self.ws_edit.setText(chosen)

    def _save(self) -> None:
        self.settings.luanti_executable = self.exe_edit.text().strip()
        if self.ws_edit.text().strip():
            self.settings.default_projects_dir = Path(self.ws_edit.text().strip())
        self.settings.auto_save_interval_sec = self.autosave_spin.value()
        self.accept()