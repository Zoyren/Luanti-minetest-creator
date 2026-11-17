# -*- coding: utf-8 -*-
"""
app/main_window.py
Fenêtre principale Aérée & Anti-Débordement (Tâche A) :
- Barre supérieure séparée en 2 niveaux (Barre Projet/Actions en haut + Barre d'Onglets Workbenches en dessous)
  pour empêcher tout débordement horizontal hors de l'écran.
- Adaptation automatique à la géométrie réelle de l'écran (compatible écrans portables 1080p avec zoom 125%/150%).
- Explorateur gauche enveloppé dans un QScrollArea fluide avec espacement respirant.
- Persistance complète (Modèle 3D + Timeline + Studio Item 2D/3D + Commandes + GUI Formspec + Bonus Studio).
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QStackedWidget, QFrame,
        QListWidget, QListWidgetItem, QCheckBox, QLineEdit,
        QGroupBox, QButtonGroup, QFileDialog, QMessageBox,
        QPlainTextEdit, QFormLayout, QDockWidget, QScrollArea
    )
except ImportError:
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QGuiApplication
    from PyQt5.QtWidgets import (
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QStackedWidget, QFrame,
        QListWidget, QListWidgetItem, QCheckBox, QLineEdit,
        QGroupBox, QButtonGroup, QFileDialog, QMessageBox,
        QPlainTextEdit, QFormLayout, QDockWidget, QScrollArea
    )

from app.theme import apply_workbench_theme
from engine.model_loader.model_data import ModelData
from engine.renderer.model_editor_widget import ModelEditorWidget
from modules.shared_subeditors.pixel_art_editor import PixelArtEditor
from modules.shared_subeditors.item_icon_studio_widget import ItemIconStudioWidget
from modules.shared_subeditors.bonus_studio_widget import BonusStudioWidget
from engine.animation.animation_editor_widget import AnimationEditorWidget
from modules.command.command_editor_widget import CommandEditorWidget
from modules.command.formspec_editor_widget import FormspecEditorWidget, FormspecElement
from modules.world.world_editor_widget import WorldEditorWidget
from ide.lua_ide_widget import LuaIdeWidget
from exporters.mts_exporter import MtsExporter
from workers.test_runner import LuantiTestRunner


@dataclass
class StudioAssetItem:
    identifier: str
    display_name: str
    category: str
    in_creative_inventory: bool = True
    generate_spawn_egg: bool = True
    lua_code: str = ""
    model_data: Optional[ModelData] = field(default=None, repr=False)
    command_data: Optional[Dict[str, Any]] = field(default=None)
    formspec_data: Optional[Dict[str, Any]] = field(default=None)

    def ensure_model_data(self) -> ModelData:
        if self.model_data is None:
            clean_name = self.identifier.split(":")[-1]
            self.model_data = ModelData(category=self.category, name=clean_name)
        return self.model_data

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identifier": self.identifier,
            "display_name": self.display_name,
            "category": self.category,
            "in_creative_inventory": self.in_creative_inventory,
            "generate_spawn_egg": self.generate_spawn_egg,
            "lua_code": self.lua_code,
            "model_data": (
                self.ensure_model_data().to_dict()
                if self.category in ("Mobs", "Blocks", "Items")
                else None
            ),
            "command_data": self.command_data,
            "formspec_data": self.formspec_data,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StudioAssetItem":
        mdata_dict = d.get("model_data")
        mdata = ModelData.from_dict(mdata_dict) if mdata_dict else None
        return cls(
            identifier=d.get("identifier", "mon_mod:item"),
            display_name=d.get("display_name", "Élément"),
            category=d.get("category", "Mobs"),
            in_creative_inventory=bool(d.get("in_creative_inventory", True)),
            generate_spawn_egg=bool(d.get("generate_spawn_egg", True)),
            lua_code=d.get("lua_code", ""),
            model_data=mdata,
            command_data=d.get("command_data"),
            formspec_data=d.get("formspec_data"),
        )


# Libellés d'onglets concis et lisibles pour éviter tout débordement horizontal
WORKBENCHES_BY_CATEGORY: Dict[str, List[tuple]] = {
    "Mobs": [
        ("model_3d", "🧊 1. Modèle 3D & Voxel"),
        ("texture_paint", "🎨 2. Peinture 2D/3D"),
        ("animation", "🎬 3. Animation"),
        ("logic_blockly", "🧩 4. Blockly & Lua"),
        ("bonus_studio", "🌟 5. Spawners & Bonus"),
    ],
    "Blocks": [
        ("model_3d", "🧊 1. Modèle 3D & Voxel"),
        ("texture_paint", "🎨 2. Peinture 2D/3D"),
        ("animation", "🎬 3. Animation"),
        ("logic_blockly", "🧩 4. Blockly & Lua"),
        ("bonus_studio", "🌟 5. Crafts & Minerais"),
    ],
    "Items": [
        ("item_studio", "⚔️ 1. Icône & Extrusion 3D"),
        ("model_3d", "🧊 2. Modèle 3D & Voxel"),
        ("texture_paint", "🎨 3. Peinture 2D/3D"),
        ("animation", "🎬 4. Animation"),
        ("logic_blockly", "🧩 5. Blockly & Lua"),
        ("bonus_studio", "🍳 6. Crafts 3×3 & Bonus"),
    ],
    "Commands": [
        ("cmd_settings", "⌨️ 1. Commande & Sous-Cmd"),
        ("gui_builder", "🖼️ 2. Studio GUI Formspec"),
        ("logic_blockly", "🧩 3. Blockly & Lua"),
    ],
    "World": [
        ("voxel_world", "🌍 1. Monde Voxel & Formes 3D"),
        ("bonus_studio", "🌟 2. Minerais, Spawners & Particules"),
    ],
}


class MainWindow(QMainWindow):
    """Fenêtre principale aérée avec en-tête à 2 niveaux et cadrage automatique à l'écran."""

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.setWindowTitle("Luanti Studio — Studio 3D Modulaire & Test In-Game")
        self.setMinimumSize(1024, 620)
        apply_workbench_theme(self)

        self.mod_name = "mon_mod"
        self.current_project_path: Optional[str] = None
        self.current_category = "Mobs"
        self.current_workbench_key = "model_3d"
        self.workbench_pages: Dict[str, QWidget] = {}
        self._updating_asset_fields = False
        self._active_command_asset: Optional[StudioAssetItem] = None

        self.test_runner = LuantiTestRunner(self)
        self.test_runner.logReceived.connect(self._append_console_log)
        self.test_runner.processStateChanged.connect(self._on_luanti_process_state_changed)

        self.assets_by_category: Dict[str, List[StudioAssetItem]] = {
            "Mobs": [
                StudioAssetItem("mon_mod:renard_bleu", "Renard Chibi Bleu", "Mobs"),
                StudioAssetItem("mon_mod:golem_ancien", "Golem Ancien", "Mobs"),
            ],
            "Blocks": [
                StudioAssetItem("mon_mod:cristal_azur", "Cristal d'Azur 3D", "Blocks"),
                StudioAssetItem("mon_mod:pilier_sculpte", "Pilier Sculpté 3D", "Blocks"),
            ],
            "Items": [
                StudioAssetItem("mon_mod:lame_astrale", "Lame Astrale 3D", "Items"),
            ],
            "Commands": [
                StudioAssetItem("boutique", "Commande /boutique", "Commands"),
            ],
            "World": [
                StudioAssetItem("monde_principal", "Monde Voxel Minetest", "World"),
            ],
        }

        self._build_ui()
        self._switch_category("Mobs")
        self._fit_window_to_available_screen()

    def _fit_window_to_available_screen(self):
        """Adapte automatiquement la fenêtre à l'écran disponible pour éviter tout débordement."""
        try:
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                avail = screen.availableGeometry()
                target_w = min(1440, int(avail.width() * 0.94))
                target_h = min(860, int(avail.height() * 0.92))
                self.resize(max(1024, target_w), max(620, target_h))
                cx = avail.x() + (avail.width() - self.width()) // 2
                cy = avail.y() + (avail.height() - self.height()) // 2
                self.move(max(avail.x(), cx), max(avail.y(), cy))
                return
        except Exception:
            pass
        self.resize(1280, 740)

    def _build_ui(self):
        try:
            self.setDockOptions(
                QMainWindow.DockOption.AllowNestedDocks |
                QMainWindow.DockOption.AllowTabbedDocks |
                QMainWindow.DockOption.AnimatedDocks
            )
        except AttributeError:
            self.setDockOptions(
                QMainWindow.AllowNestedDocks |
                QMainWindow.AllowTabbedDocks |
                QMainWindow.AnimatedDocks
            )

        # 1. Dock Widget Gauche (Explorateur de Projet dans un QScrollArea fluide)
        self.left_dock = QDockWidget("📁 Explorateur de Projet", self)
        try:
            self.left_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
            self.left_dock.setFeatures(
                QDockWidget.DockWidgetFeature.DockWidgetClosable |
                QDockWidget.DockWidgetFeature.DockWidgetMovable |
                QDockWidget.DockWidgetFeature.DockWidgetFloatable
            )
            dock_area_left = Qt.DockWidgetArea.LeftDockWidgetArea
        except AttributeError:
            self.left_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
            self.left_dock.setFeatures(
                QDockWidget.DockWidgetClosable |
                QDockWidget.DockWidgetMovable |
                QDockWidget.DockWidgetFloatable
            )
            dock_area_left = Qt.LeftDockWidgetArea

        rail_scroll = QScrollArea()
        rail_scroll.setWidgetResizable(True)
        rail_scroll.setFrameShape(QFrame.Shape.NoFrame)
        rail_scroll.setMinimumWidth(215)
        rail_scroll.setMaximumWidth(275)
        rail_scroll.setWidget(self._build_left_rail())

        self.left_dock.setWidget(rail_scroll)
        self.addDockWidget(dock_area_left, self.left_dock)

        # 2. Widget Central : En-tête à 2 niveaux + Zone de travail (Workbenches)
        central_container = QWidget()
        central_layout = QVBoxLayout(central_container)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # --- NIVEAU 1 : BARRE D'EN-TÊTE PRINCIPALE (PROJET, ÉLÉMENT ACTIF & ACTIONS GLOBALES) ---
        self.main_header_bar = QFrame()
        self.main_header_bar.setObjectName("MainHeaderBar")
        header_layout = QHBoxLayout(self.main_header_bar)
        header_layout.setContentsMargins(12, 6, 12, 6)
        header_layout.setSpacing(8)

        btn_toggle_explorer = QPushButton("📁 Explorateur")
        btn_toggle_explorer.setCheckable(True)
        btn_toggle_explorer.setChecked(True)
        btn_toggle_explorer.toggled.connect(self.left_dock.setVisible)
        header_layout.addWidget(btn_toggle_explorer)

        self.lbl_active_item = QLabel("")
        self.lbl_active_item.setStyleSheet(
            "color: #60a5fa; font-weight: 700; font-size: 13px; "
            "background-color: #161d2a; border: 1px solid #28354a; border-radius: 5px; padding: 4px 12px;"
        )
        header_layout.addWidget(self.lbl_active_item)

        header_layout.addStretch(1)

        btn_save = QPushButton("💾 Sauver Projet")
        btn_save.clicked.connect(self.save_project_dialog)
        header_layout.addWidget(btn_save)

        btn_load = QPushButton("📂 Ouvrir Projet")
        btn_load.clicked.connect(self.load_project_dialog)
        header_layout.addWidget(btn_load)

        btn_export = QPushButton("🚀 Exporter Mod")
        btn_export.setObjectName("PrimaryButton")
        btn_export.clicked.connect(self._export_complete_mod_dialog)
        header_layout.addWidget(btn_export)

        self.btn_run_luanti = QPushButton("▶️ Lancer Luanti")
        self.btn_run_luanti.setStyleSheet(
            "background-color: #16a34a; color: #ffffff; font-weight: bold; "
            "padding: 6px 14px; border: 1px solid #22c55e; border-radius: 5px;"
        )
        self.btn_run_luanti.clicked.connect(self.launch_and_test_in_luanti)
        header_layout.addWidget(self.btn_run_luanti)

        self.btn_toggle_console = QPushButton("📟 Console")
        self.btn_toggle_console.setCheckable(True)
        self.btn_toggle_console.toggled.connect(lambda c: self.console_dock.setVisible(c))
        header_layout.addWidget(self.btn_toggle_console)

        central_layout.addWidget(self.main_header_bar)

        # --- NIVEAU 2 : BARRE DÉDIÉE AUX ONGLETS D'ATELIERS (WORKBENCHES) ---
        self.workbench_topbar = QFrame()
        self.workbench_topbar.setObjectName("WorkbenchTopBar")
        top_outer = QHBoxLayout(self.workbench_topbar)
        top_outer.setContentsMargins(12, 6, 12, 6)
        top_outer.setSpacing(6)

        self.workbench_topbar_layout = QHBoxLayout()
        self.workbench_topbar_layout.setSpacing(6)
        top_outer.addLayout(self.workbench_topbar_layout, 1)

        central_layout.addWidget(self.workbench_topbar)

        self.workbench_stack = QStackedWidget()
        central_layout.addWidget(self.workbench_stack, 1)

        self.setCentralWidget(central_container)

        # 3. Dock Widget Bas (Console de Logs Détachable)
        self.console_dock = QDockWidget("📟 Console de Logs Luanti", self)
        try:
            self.console_dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
            self.console_dock.setFeatures(
                QDockWidget.DockWidgetFeature.DockWidgetClosable |
                QDockWidget.DockWidgetFeature.DockWidgetMovable |
                QDockWidget.DockWidgetFeature.DockWidgetFloatable
            )
            dock_area_bottom = Qt.DockWidgetArea.BottomDockWidgetArea
        except AttributeError:
            self.console_dock.setAllowedAreas(Qt.AllDockWidgetAreas)
            self.console_dock.setFeatures(
                QDockWidget.DockWidgetClosable |
                QDockWidget.DockWidgetMovable |
                QDockWidget.DockWidgetFloatable
            )
            dock_area_bottom = Qt.BottomDockWidgetArea

        console_widget = QWidget()
        cw_layout = QVBoxLayout(console_widget)
        cw_layout.setContentsMargins(8, 8, 8, 8)
        cw_layout.setSpacing(6)

        c_head = QHBoxLayout()
        c_head.setSpacing(8)
        btn_cfg = QPushButton("⚙️ Chemin luanti.exe")
        btn_cfg.clicked.connect(self._reconfigure_luanti_exe)
        c_head.addWidget(btn_cfg)
        btn_stop = QPushButton("⏹ Stopper Luanti")
        btn_stop.clicked.connect(self.test_runner.stop_luanti)
        c_head.addWidget(btn_stop)
        btn_clr = QPushButton("🧹 Vider")
        btn_clr.clicked.connect(lambda: self.console_output.clear())
        c_head.addWidget(btn_clr)
        c_head.addStretch()
        cw_layout.addLayout(c_head)

        self.console_output = QPlainTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setStyleSheet(
            "background-color: #0b0e14; color: #93c5fd; font-family: Consolas, monospace; font-size: 11px;"
        )
        cw_layout.addWidget(self.console_output)

        self.console_dock.setWidget(console_widget)
        self.addDockWidget(dock_area_bottom, self.console_dock)
        self.console_dock.setVisible(False)

    def _build_left_rail(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("CategoryRail")
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        mod_row = QHBoxLayout()
        mod_row.setSpacing(6)
        lbl_mod = QLabel("📦 ID Mod :")
        lbl_mod.setStyleSheet("font-weight: bold; color: #93c5fd;")
        mod_row.addWidget(lbl_mod)
        self.inp_mod_name = QLineEdit(self.mod_name)
        self.inp_mod_name.textEdited.connect(self._on_mod_name_edited)
        mod_row.addWidget(self.inp_mod_name, 1)
        layout.addLayout(mod_row)

        lbl_cat = QLabel("🗂️ Catégories du Mod :")
        lbl_cat.setStyleSheet("font-weight: bold; color: #93c5fd; margin-top: 4px;")
        layout.addWidget(lbl_cat)

        self.cat_group = QButtonGroup(self)
        self.cat_group.setExclusive(True)
        self.cat_buttons: Dict[str, QPushButton] = {}

        for key, label in [
            ("Mobs", "🐺  Mobs & Entités"),
            ("Blocks", "🧱  Blocs 3D"),
            ("Items", "⚔️  Items & Armes"),
            ("Commands", "⌨️  Commandes & GUI"),
            ("World", "🌍  Monde Voxel 3D"),
        ]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("class", "CategoryButton")
            btn.clicked.connect(lambda checked, c=key: self._switch_category(c))
            self.cat_group.addButton(btn)
            self.cat_buttons[key] = btn
            layout.addWidget(btn)

        lbl_elems = QLabel("📋 Éléments de la catégorie :")
        lbl_elems.setStyleSheet("font-weight: bold; color: #93c5fd; margin-top: 4px;")
        layout.addWidget(lbl_elems)

        self.entity_list = QListWidget()
        self.entity_list.setMinimumHeight(130)
        self.entity_list.currentRowChanged.connect(self._on_entity_row_changed)
        layout.addWidget(self.entity_list, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_new = QPushButton("➕ Nouvel Élément")
        btn_new.setObjectName("PrimaryButton")
        btn_new.clicked.connect(self._create_entity)
        btn_del = QPushButton("🗑️")
        btn_del.setObjectName("DangerButton")
        btn_del.setFixedWidth(40)
        btn_del.clicked.connect(self._delete_entity)
        btn_row.addWidget(btn_new, 1)
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)

        rename_group = QGroupBox("✏️ Identité Élément")
        rg_form = QFormLayout(rename_group)
        rg_form.setContentsMargins(8, 12, 8, 8)
        rg_form.setSpacing(8)

        self.inp_asset_display = QLineEdit()
        self.inp_asset_display.textEdited.connect(self._on_asset_identity_edited)
        rg_form.addRow("Nom :", self.inp_asset_display)

        self.inp_asset_id = QLineEdit()
        self.inp_asset_id.textEdited.connect(self._on_asset_identity_edited)
        rg_form.addRow("ID :", self.inp_asset_id)

        self.chk_creative = QCheckBox("Visible Menu Créatif")
        self.chk_creative.setChecked(True)
        self.chk_creative.toggled.connect(self._save_entity_flags)
        rg_form.addRow("", self.chk_creative)

        self.chk_spawn_egg = QCheckBox("Générer Œuf de Mob")
        self.chk_spawn_egg.setChecked(True)
        self.chk_spawn_egg.toggled.connect(self._save_entity_flags)
        rg_form.addRow("", self.chk_spawn_egg)

        layout.addWidget(rename_group)
        return rail

    # =========================================================================
    # PERSISTANCE DES COMMANDES (ARGUMENTS & SOUS-COMMANDES) & GUI PAR ÉLÉMENT
    # =========================================================================
    def _save_command_gui_state_to_asset(self, asset: Optional[StudioAssetItem]):
        if not asset or asset.category != "Commands":
            return
        if "cmd_settings" in self.workbench_pages:
            cmd_w = self.workbench_pages["cmd_settings"]
            if isinstance(cmd_w, CommandEditorWidget):
                if hasattr(cmd_w, "to_dict"):
                    asset.command_data = cmd_w.to_dict()
                else:
                    asset.command_data = {
                        "name": cmd_w.inp_name.text(),
                        "params": cmd_w.inp_params.text(),
                        "desc": cmd_w.inp_desc.text(),
                        "priv_interact": cmd_w.chk_priv_interact.isChecked(),
                        "priv_shout": cmd_w.chk_priv_shout.isChecked(),
                        "priv_server": cmd_w.chk_priv_server.isChecked(),
                        "priv_teleport": cmd_w.chk_priv_teleport.isChecked(),
                        "priv_bring": cmd_w.chk_priv_bring.isChecked(),
                        "custom_priv": cmd_w.inp_custom_priv.text(),
                        "action_idx": cmd_w.combo_action.currentIndex(),
                        "feedback": cmd_w.inp_chat_feedback.text(),
                        "reward": cmd_w.inp_reward_item.text(),
                        "cooldown": cmd_w.spn_cooldown.value(),
                    }
        if "gui_builder" in self.workbench_pages:
            gui_w = self.workbench_pages["gui_builder"]
            if isinstance(gui_w, FormspecEditorWidget):
                asset.formspec_data = {
                    "formname": gui_w.formname,
                    "win_width": gui_w.win_width,
                    "win_height": gui_w.win_height,
                    "bg_texture_name": gui_w.bg_texture_name,
                    "bg_color_hex": gui_w.bg_color_hex,
                    "elements": [asdict(el) for el in gui_w.elements],
                }

    def _load_command_gui_state_from_asset(self, asset: Optional[StudioAssetItem]):
        if not asset or asset.category != "Commands":
            return
        short_cmd = asset.identifier.split(":")[-1].lstrip("/")
        if "cmd_settings" in self.workbench_pages:
            cmd_w = self.workbench_pages["cmd_settings"]
            if isinstance(cmd_w, CommandEditorWidget):
                cmd_w.linked_formspec_name = f"{self.mod_name}:{short_cmd}_gui"
                if hasattr(cmd_w, "load_from_dict"):
                    cmd_w.load_from_dict(asset.command_data or {}, default_cmd_name=short_cmd)
                else:
                    cdata = asset.command_data or {}
                    cmd_w.inp_name.setText(cdata.get("name", short_cmd))
                    cmd_w.inp_params.setText(cdata.get("params", "<onglet> [quantite]"))
                    cmd_w.inp_desc.setText(cdata.get("desc", asset.display_name))
                    cmd_w._refresh_lua_preview()

        if "gui_builder" in self.workbench_pages:
            gui_w = self.workbench_pages["gui_builder"]
            if isinstance(gui_w, FormspecEditorWidget):
                fdata = asset.formspec_data
                gui_w.formname = f"{self.mod_name}:{short_cmd}_gui"
                if fdata:
                    gui_w.win_width = float(fdata.get("win_width", 11.0))
                    gui_w.win_height = float(fdata.get("win_height", 9.5))
                    gui_w.bg_texture_name = fdata.get("bg_texture_name", "gui_bg_rpg_dark.png")
                    gui_w.bg_color_hex = fdata.get("bg_color_hex", "#1e2430")
                    valid_fields = set(FormspecElement.__dataclass_fields__.keys())
                    gui_w.elements = [
                        FormspecElement(**{k: v for k, v in el.items() if k in valid_fields})
                        for el in fdata.get("elements", [])
                    ]
                    gui_w.spn_win_w.setValue(gui_w.win_width)
                    gui_w.spn_win_h.setValue(gui_w.win_height)
                    gui_w.select_element(gui_w.elements[0] if gui_w.elements else None)
                gui_w._compile_formspec_lua()

    def _on_mod_name_edited(self, text: str):
        clean = "".join(ch for ch in text.lower().replace(" ", "_") if ch.isalnum() or ch == "_")
        if not clean:
            return
        self.mod_name = clean
        for cat_items in self.assets_by_category.values():
            for it in cat_items:
                if ":" in it.identifier:
                    _, short = it.identifier.split(":", 1)
                    it.identifier = f"{self.mod_name}:{short}"
        self._refresh_entity_list_labels()
        self._update_banner()

    def _on_asset_identity_edited(self):
        if self._updating_asset_fields:
            return
        asset = self._current_asset()
        if not asset:
            return
        new_disp = self.inp_asset_display.text().strip()
        new_id = self.inp_asset_id.text().strip().replace(" ", "_").lower()
        if new_disp:
            asset.display_name = new_disp
        if new_id:
            if ":" not in new_id and asset.category in ("Mobs", "Blocks", "Items"):
                new_id = f"{self.mod_name}:{new_id}"
            asset.identifier = new_id
            if asset.model_data:
                asset.model_data.name = new_id.split(":")[-1]
        self._refresh_entity_list_labels()
        self._update_banner()

    def _refresh_entity_list_labels(self):
        cur_row = self.entity_list.currentRow()
        self.entity_list.blockSignals(True)
        self.entity_list.clear()
        for item in self.assets_by_category.get(self.current_category, []):
            self.entity_list.addItem(QListWidgetItem(f"{item.display_name}  [{item.identifier}]"))
        if 0 <= cur_row < self.entity_list.count():
            self.entity_list.setCurrentRow(cur_row)
        self.entity_list.blockSignals(False)

    def _get_active_model_data(self) -> ModelData:
        asset = self._current_asset()
        if asset and asset.category in ("Mobs", "Blocks", "Items"):
            return asset.ensure_model_data()
        return ModelData(self.current_category)

    def _get_or_create_workbench(self, wb_key: str) -> QWidget:
        if wb_key in self.workbench_pages:
            return self.workbench_pages[wb_key]

        if wb_key == "item_studio":
            widget = ItemIconStudioWidget(model_data=self._get_active_model_data(), parent=self)
        elif wb_key == "model_3d":
            widget = ModelEditorWidget(model_data=self._get_active_model_data(), parent=self)
        elif wb_key == "texture_paint":
            widget = PixelArtEditor(model_data=self._get_active_model_data(), parent=self)
        elif wb_key == "animation":
            widget = AnimationEditorWidget(model_data=self._get_active_model_data(), parent=self)
        elif wb_key == "logic_blockly":
            widget = LuaIdeWidget(category=self.current_category, parent=self)
            widget.luaCodeChanged.connect(self._on_lua_code_changed)
        elif wb_key == "cmd_settings":
            cmd_w = CommandEditorWidget(parent=self)
            cmd_w.openGuiBuilderRequested.connect(lambda: self._activate_workbench("gui_builder"))
            widget = cmd_w
        elif wb_key == "gui_builder":
            widget = FormspecEditorWidget(parent=self)
        elif wb_key == "voxel_world":
            widget = WorldEditorWidget(parent=self)
        elif wb_key == "bonus_studio":
            widget = BonusStudioWidget(mod_name=self.mod_name, parent=self)
        else:
            widget = QLabel(f"Atelier {wb_key}")

        self.workbench_pages[wb_key] = widget
        self.workbench_stack.addWidget(widget)
        return widget

    def _sync_active_workbenches(self):
        asset = self._current_asset()
        if self.current_category in ("Mobs", "Blocks", "Items"):
            mdata = self._get_active_model_data()
            if "item_studio" in self.workbench_pages:
                witem = self.workbench_pages["item_studio"]
                if isinstance(witem, ItemIconStudioWidget):
                    witem.set_model_data(mdata)
            if "model_3d" in self.workbench_pages:
                w3d = self.workbench_pages["model_3d"]
                if isinstance(w3d, ModelEditorWidget):
                    w3d.set_model_data(mdata)
            if "texture_paint" in self.workbench_pages:
                wtex = self.workbench_pages["texture_paint"]
                if isinstance(wtex, PixelArtEditor):
                    wtex.set_model_data(mdata)
            if "animation" in self.workbench_pages:
                wanim = self.workbench_pages["animation"]
                if isinstance(wanim, AnimationEditorWidget):
                    wanim.set_model_data(mdata)

        elif self.current_category == "Commands" and asset is not None:
            if self._active_command_asset is not None and self._active_command_asset is not asset:
                self._save_command_gui_state_to_asset(self._active_command_asset)
            self._active_command_asset = asset
            self._load_command_gui_state_from_asset(asset)

        if "voxel_world" in self.workbench_pages:
            wworld = self.workbench_pages["voxel_world"]
            if isinstance(wworld, WorldEditorWidget):
                for blk in self.assets_by_category.get("Blocks", []):
                    bm = blk.ensure_model_data()
                    full_node_id = f"{self.mod_name}:{blk.identifier.split(':')[-1]}"
                    wworld.engine.register_custom_studio_block(full_node_id, blk.display_name, bm)

        if "bonus_studio" in self.workbench_pages:
            wbonus = self.workbench_pages["bonus_studio"]
            if isinstance(wbonus, BonusStudioWidget):
                wbonus.sync_project_assets(self.mod_name, self.assets_by_category)

    def _switch_category(self, category: str):
        if self.current_category == "Commands" and self._active_command_asset is not None:
            self._save_command_gui_state_to_asset(self._active_command_asset)

        self.current_category = category
        if category in self.cat_buttons:
            self.cat_buttons[category].setChecked(True)

        self._refresh_entity_list_labels()
        if self.entity_list.count() > 0:
            self.entity_list.setCurrentRow(0)
            self._on_entity_row_changed(0)

        self.chk_spawn_egg.setVisible(category == "Mobs")
        self.chk_creative.setVisible(category in ("Mobs", "Blocks", "Items"))
        self._sync_active_workbenches()

        if "logic_blockly" in self.workbench_pages:
            lua_wb = self.workbench_pages["logic_blockly"]
            if isinstance(lua_wb, LuaIdeWidget) and category in ("Mobs", "Blocks", "Items", "Commands"):
                lua_wb.set_category(category, insert_starter=True)

        self._rebuild_workbench_tabs(category)

    def _rebuild_workbench_tabs(self, category: str):
        while self.workbench_topbar_layout.count():
            child = self.workbench_topbar_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.wb_group = QButtonGroup(self)
        self.wb_group.setExclusive(True)

        workbenches = WORKBENCHES_BY_CATEGORY.get(category, [])
        first_key = None

        for idx, (wb_key, wb_label) in enumerate(workbenches):
            btn = QPushButton(wb_label)
            btn.setCheckable(True)
            btn.setProperty("class", "WorkbenchTab")
            btn.clicked.connect(lambda checked, k=wb_key: self._activate_workbench(k))
            self.wb_group.addButton(btn)
            self.workbench_topbar_layout.addWidget(btn)
            if idx == 0:
                btn.setChecked(True)
                first_key = wb_key

        self.workbench_topbar_layout.addStretch(1)
        self._update_banner()

        if first_key:
            self._activate_workbench(first_key)

    def _activate_workbench(self, wb_key: str):
        if self.current_workbench_key == "animation" and "animation" in self.workbench_pages:
            wanim = self.workbench_pages["animation"]
            if isinstance(wanim, AnimationEditorWidget) and wanim.is_playing:
                wanim.toggle_playback()

        self.current_workbench_key = wb_key
        widget = self._get_or_create_workbench(wb_key)
        self._sync_active_workbenches()
        self.workbench_stack.setCurrentWidget(widget)

        workbenches = WORKBENCHES_BY_CATEGORY.get(self.current_category, [])
        for idx, (k, _) in enumerate(workbenches):
            if k == wb_key and idx < len(self.wb_group.buttons()):
                self.wb_group.buttons()[idx].setChecked(True)

        if wb_key == "logic_blockly" and isinstance(widget, LuaIdeWidget):
            asset = self._current_asset()
            if asset and asset.lua_code.strip():
                widget.set_code(asset.lua_code)
            else:
                widget.set_category(self.current_category, insert_starter=True)

    def _current_asset(self) -> Optional[StudioAssetItem]:
        row = self.entity_list.currentRow()
        items = self.assets_by_category.get(self.current_category, [])
        if 0 <= row < len(items):
            return items[row]
        return None

    def _on_entity_row_changed(self, row: int):
        asset = self._current_asset()
        if not asset:
            return
        self._updating_asset_fields = True
        self.inp_asset_display.setText(asset.display_name)
        self.inp_asset_id.setText(asset.identifier)
        self.chk_creative.setChecked(asset.in_creative_inventory)
        self.chk_spawn_egg.setChecked(asset.generate_spawn_egg)
        self._updating_asset_fields = False
        self._sync_active_workbenches()
        self._update_banner()

    def _save_entity_flags(self):
        if self._updating_asset_fields:
            return
        asset = self._current_asset()
        if asset:
            asset.in_creative_inventory = self.chk_creative.isChecked()
            asset.generate_spawn_egg = self.chk_spawn_egg.isChecked()
            self._update_banner()

    def _on_lua_code_changed(self, lua_code: str):
        asset = self._current_asset()
        if asset:
            asset.lua_code = lua_code

    def _update_banner(self):
        asset = self._current_asset()
        if hasattr(self, "lbl_active_item") and asset:
            badge = " • Créatif ✓" if asset.in_creative_inventory else ""
            self.lbl_active_item.setText(f"🎯 Actif : {asset.display_name} ({asset.identifier}){badge}")

    def _create_entity(self):
        items = self.assets_by_category.setdefault(self.current_category, [])
        idx = len(items) + 1
        prefix = self.current_category.lower().rstrip("s")
        ident = f"{prefix}_{idx}" if self.current_category == "Commands" else f"{self.mod_name}:{prefix}_{idx}"
        items.append(
            StudioAssetItem(
                identifier=ident,
                display_name=f"Nouveau {prefix.capitalize()} {idx}",
                category=self.current_category,
            )
        )
        self._switch_category(self.current_category)
        self.entity_list.setCurrentRow(len(items) - 1)

    def _delete_entity(self):
        row = self.entity_list.currentRow()
        items = self.assets_by_category.get(self.current_category, [])
        if 0 <= row < len(items):
            del items[row]
            self._active_command_asset = None
            self._switch_category(self.current_category)

    def save_project_dialog(self):
        if self.current_category == "Commands" and self._active_command_asset is not None:
            self._save_command_gui_state_to_asset(self._active_command_asset)

        path, _ = QFileDialog.getSaveFileName(
            self, "Sauvegarder le projet", self.current_project_path or f"{self.mod_name}.luantiproj",
            "Projet Luanti Studio (*.luantiproj);;JSON (*.json)"
        )
        if not path:
            return
        self.current_project_path = path

        world_w = self._get_or_create_workbench("voxel_world")
        bonus_w = self._get_or_create_workbench("bonus_studio")
        voxels_serialized = []
        world_grid_size = 32
        export_void = True
        if isinstance(world_w, WorldEditorWidget):
            world_grid_size = world_w.engine.grid_size
            export_void = world_w.engine.export_void_world
            for (vx, vy, vz), nname in world_w.engine.voxels.items():
                voxels_serialized.append({"x": vx, "y": vy, "z": vz, "node": nname})

        bonus_dict = bonus_w.to_dict() if isinstance(bonus_w, BonusStudioWidget) else {}

        payload = {
            "version": "2.6",
            "mod_name": self.mod_name,
            "world_grid_size": world_grid_size,
            "export_void_world": export_void,
            "assets_by_category": {cat: [it.to_dict() for it in items] for cat, items in self.assets_by_category.items()},
            "voxel_world": voxels_serialized,
            "bonus_studio": bonus_dict,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        QMessageBox.information(self, "Sauvegardé", f"Projet sauvegardé avec succès :\n{path}")

    def load_project_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Ouvrir un projet", "", "Projet Luanti Studio (*.luantiproj *.json)")
        if not path or not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.current_project_path = path
            self.mod_name = data.get("mod_name", "mon_mod")
            self.inp_mod_name.setText(self.mod_name)
            self._active_command_asset = None

            loaded_assets = {}
            for cat, raw_list in data.get("assets_by_category", {}).items():
                loaded_assets[cat] = [StudioAssetItem.from_dict(it) for it in raw_list]
            if loaded_assets:
                self.assets_by_category = loaded_assets

            world_w = self._get_or_create_workbench("voxel_world")
            if isinstance(world_w, WorldEditorWidget):
                world_w.engine.set_grid_size(int(data.get("world_grid_size", 32)))
                world_w.engine.export_void_world = bool(data.get("export_void_world", True))
                world_w.chk_void_world.setChecked(world_w.engine.export_void_world)
                if "voxel_world" in data:
                    world_w.engine.voxels.clear()
                    for entry in data["voxel_world"]:
                        world_w.engine.voxels[(int(entry["x"]), int(entry["y"]), int(entry["z"]))] = entry["node"]
                    world_w.engine.worldChanged.emit()

            if "bonus_studio" in data and data["bonus_studio"]:
                bonus_w = self._get_or_create_workbench("bonus_studio")
                if isinstance(bonus_w, BonusStudioWidget):
                    bonus_w.load_from_dict(data["bonus_studio"])

            self._switch_category(self.current_category)
            QMessageBox.information(self, "Chargé", f"Projet chargé avec succès :\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Erreur", f"Impossible de charger :\n{exc}")

    def _export_to_target_folder(self, folder: str) -> str:
        if self.current_category == "Commands" and self._active_command_asset is not None:
            self._save_command_gui_state_to_asset(self._active_command_asset)

        cmd_w = self._get_or_create_workbench("cmd_settings")
        gui_w = self._get_or_create_workbench("gui_builder")
        world_w = self._get_or_create_workbench("voxel_world")
        bonus_w = self._get_or_create_workbench("bonus_studio")
        self._sync_active_workbenches()

        cmd_lua = cmd_w.generate_lua_code() if isinstance(cmd_w, CommandEditorWidget) else ""
        fs_lua = gui_w.generate_formspec_lua() if isinstance(gui_w, FormspecEditorWidget) else ""
        bonus_lua = bonus_w.generate_lua_code() if isinstance(bonus_w, BonusStudioWidget) else ""
        gui_tex = gui_w.tex_bank.textures if isinstance(gui_w, FormspecEditorWidget) else {}
        voxels = world_w.engine.voxels if isinstance(world_w, WorldEditorWidget) else {}
        void_world = world_w.engine.export_void_world if isinstance(world_w, WorldEditorWidget) else True

        combined_cmd_and_bonus_lua = f"{cmd_lua}\n\n{bonus_lua}" if bonus_lua else cmd_lua

        return MtsExporter.export_complete_luanti_mod(
            folder_path=folder,
            mod_name=self.mod_name,
            assets_by_category=self.assets_by_category,
            command_lua=combined_cmd_and_bonus_lua,
            formspec_lua=fs_lua,
            gui_textures=gui_tex,
            voxels=voxels,
            void_world=void_world,
        )

    def _export_complete_mod_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, f"Dossier d'export pour le mod '{self.mod_name}'")
        if not folder:
            return
        if os.path.basename(os.path.normpath(folder)).lower() == "mods":
            folder = os.path.join(folder, self.mod_name)
        init_path = self._export_to_target_folder(folder)
        QMessageBox.information(self, "Export Réussi", f"Mod compilé dans :\n{folder}\n• Script : {init_path}")

    def launch_and_test_in_luanti(self):
        exe = self.test_runner.ensure_executable_configured(self)
        if not exe:
            return
        try:
            self.console_dock.setVisible(True)
            self.btn_toggle_console.setChecked(True)
            world_w = self._get_or_create_workbench("voxel_world")
            void_world = world_w.engine.export_void_world if isinstance(world_w, WorldEditorWidget) else True

            target_mod_dir, test_world_dir = self.test_runner.prepare_test_world_and_mod_dir(
                self.mod_name, void_world=void_world
            )
            self._append_console_log(f"[Luanti Studio] Compilation vers {target_mod_dir}\n")
            self._export_to_target_folder(target_mod_dir)
            self._append_console_log(f"[Luanti Studio] Démarrage de Luanti...\n")
            self.test_runner.launch_luanti_with_mod(test_world_dir)
        except Exception as exc:
            QMessageBox.critical(self, "Erreur", f"Échec du lancement Luanti :\n{exc}")

    def _reconfigure_luanti_exe(self):
        self.test_runner.luanti_exe_path = ""
        self.test_runner.ensure_executable_configured(self)

    def _append_console_log(self, text: str):
        self.console_output.moveCursor(self.console_output.textCursor().MoveOperation.End)
        self.console_output.insertPlainText(text)
        self.console_output.moveCursor(self.console_output.textCursor().MoveOperation.End)

    def _on_luanti_process_state_changed(self, running: bool):
        if running:
            self.btn_run_luanti.setText("🟢 Luanti Actif (Relancer)")
        else:
            self.btn_run_luanti.setText("▶️ Lancer Luanti")


LuantiCreatorMainWindow = MainWindow