# -*- coding: utf-8 -*-
"""
engine/renderer/model_editor_widget.py
Workbench 1 Haute Visibilité + Studio 3D Voxel MagicaVoxel intégré :
- Onglet 1 : 🧊 Pose & Géométrie (Position, Taille, Pivot, Rotations)
- Onglet 2 : 🔮 Voxel & Formes (13 Formes Préfaites MagicaVoxel, Booléens Ajouter/Creuser, Symétrie X/Y/Z, Greedy Mesh)
- Onglet 3 : 🧠 IA & Gameplay (Comportement Mob, PV, Vitesse, Dégâts, Luminosité)
"""

from typing import Optional

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
        QTreeWidget, QTreeWidgetItem, QPushButton, QLabel,
        QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox,
        QGroupBox, QLineEdit, QInputDialog, QColorDialog,
        QFormLayout, QScrollArea, QTabWidget, QButtonGroup
    )
except ImportError:
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QColor
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
        QTreeWidget, QTreeWidgetItem, QPushButton, QLabel,
        QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox,
        QGroupBox, QLineEdit, QInputDialog, QColorDialog,
        QFormLayout, QScrollArea, QTabWidget, QButtonGroup
    )

from engine.model_loader.model_data import ModelData
from engine.renderer.panda_viewport import PandaViewport
from engine.voxel.magicavoxel_tools import MAGICAVOXEL_SHAPES


GRID_OPTIONS = [
    ("16×16 px (1 Bloc - Standard)", 16),
    ("32×32 px (2×2 Blocs - Grand Mob)", 32),
    ("64×64 px (4×4 Blocs - Boss Géant)", 64),
    ("128×128 px (8×8 Blocs - Titan)", 128),
]

AI_BEHAVIOR_OPTIONS = [
    ("🐾 Passif (Marche, saute & fuit)", "passive"),
    ("⚔️ Hostile (Poursuit & attaque)", "hostile"),
    ("🐕 Compagnon (Suit le joueur)", "follower"),
    ("🗿 Statique / PNJ (Reste sur place)", "static"),
]


class ModelEditorWidget(QWidget):
    """
    Atelier 1 : Modélisation 3D par Cubes/Bones + Studio Voxel MagicaVoxel (13 Formes Préfaites).
    """

    def __init__(self, model_data: Optional[ModelData] = None, parent=None):
        super().__init__(parent)
        self.model_data: Optional[ModelData] = None
        self._updating_ui = False
        self.voxel_color = QColor("#38bdf8")
        self._build_ui()
        self.set_model_data(model_data or ModelData("Mobs"))

    def set_model_data(self, model_data: ModelData):
        if self.model_data is not None:
            try:
                self.model_data.selectionChanged.disconnect(self._on_model_selection_changed)
                self.model_data.modelChanged.disconnect(self._refresh_inspector_from_selection)
            except Exception:
                pass

        self.model_data = model_data
        self.viewport.set_model_data(model_data)
        self._connect_signals()
        self._refresh_hierarchy_tree()
        self._refresh_inspector_from_selection()

    def _connect_signals(self):
        if self.model_data is not None:
            try:
                self.model_data.selectionChanged.connect(self._on_model_selection_changed)
                self.model_data.modelChanged.connect(self._refresh_inspector_from_selection)
            except Exception:
                pass

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # =====================================================================
        # 1. PANNEAU GAUCHE : HIÉRARCHIE BONES & CUBES + PRESETS
        # =====================================================================
        left_panel = QFrame()
        left_panel.setProperty("class", "InspectorPanel")
        left_panel.setMinimumWidth(235)
        left_panel.setMaximumWidth(315)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

        lbl_preset = QLabel("📦 Gabarit 3D rapide :")
        lbl_preset.setStyleSheet("font-weight: bold; color: #93c5fd;")
        left_layout.addWidget(lbl_preset)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)
        for label, cat in [("🐺 Mob", "Mobs"), ("🧱 Bloc", "Blocks"), ("⚔️ Item", "Items")]:
            b = QPushButton(label)
            b.clicked.connect(lambda checked, c=cat: self._load_preset(c))
            preset_row.addWidget(b)
        left_layout.addLayout(preset_row)

        lbl_tree = QLabel("🦴 Hiérarchie Bones & Cubes :")
        lbl_tree.setStyleSheet("font-weight: bold; color: #93c5fd; margin-top: 4px;")
        left_layout.addWidget(lbl_tree)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Élément 3D", "Dimensions"])
        self.tree.itemClicked.connect(self._on_tree_item_clicked)
        left_layout.addWidget(self.tree, 1)

        row1 = QHBoxLayout()
        row1.setSpacing(4)
        btn_add_cube = QPushButton("➕ Cube")
        btn_add_cube.setObjectName("PrimaryButton")
        btn_add_cube.clicked.connect(self._on_add_cube)

        btn_dup_cube = QPushButton("📄 Copier")
        btn_dup_cube.clicked.connect(self._on_dup_cube)

        btn_mirror = QPushButton("🪞 Miroir X")
        btn_mirror.clicked.connect(lambda: self.model_data.mirror_selected_cube_x() if self.model_data else None)

        row1.addWidget(btn_add_cube)
        row1.addWidget(btn_dup_cube)
        row1.addWidget(btn_mirror)
        left_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(4)
        btn_add_bone = QPushButton("🦴 + Bone")
        btn_add_bone.clicked.connect(self._on_add_bone)

        btn_del_cube = QPushButton("🗑️ Supprimer")
        btn_del_cube.setObjectName("DangerButton")
        btn_del_cube.clicked.connect(self._on_del_cube)

        row2.addWidget(btn_add_bone)
        row2.addWidget(btn_del_cube)
        left_layout.addLayout(row2)

        splitter.addWidget(left_panel)

        # =====================================================================
        # 2. ZONE CENTRALE : BARRE D'OUTILS 2 LIGNES + VIEWPORT 3D PRIORITAIRE
        # =====================================================================
        center_panel = QFrame()
        center_panel.setProperty("class", "InspectorPanel")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(6, 6, 6, 6)
        center_layout.setSpacing(6)

        toolbar_row1 = QHBoxLayout()
        toolbar_row1.setSpacing(4)
        toolbar_row1.addWidget(QLabel("🎯 Outil :"))

        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tool_buttons = {}

        for idx, (lbl, t_key) in enumerate([
            ("✥ Déplacer [G]", "move"),
            ("⤢ Taille [S]", "scale"),
            ("↻ Tourner [R]", "rotate"),
            ("📍 Pivot [P]", "pivot"),
        ]):
            btn = QPushButton(lbl)
            btn.setCheckable(True)
            if idx == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked, k=t_key: self._set_transform_tool(k))
            self.tool_group.addButton(btn)
            self.tool_buttons[t_key] = btn
            toolbar_row1.addWidget(btn)

        self.btn_voxel_mode = QPushButton("🔮 Sculpter Voxel [V]")
        self.btn_voxel_mode.setCheckable(True)
        self.btn_voxel_mode.toggled.connect(self._on_voxel_mode_toggled)
        self.tool_group.addButton(self.btn_voxel_mode)
        toolbar_row1.addWidget(self.btn_voxel_mode)

        self.btn_quick_paint = QPushButton("🖌️ Peindre 3D [B]")
        self.btn_quick_paint.setCheckable(True)
        self.btn_quick_paint.toggled.connect(self._on_quick_paint_toggled)
        self.tool_group.addButton(self.btn_quick_paint)
        toolbar_row1.addWidget(self.btn_quick_paint)

        toolbar_row1.addStretch()

        self.chk_show_bones = QCheckBox("Pivots")
        self.chk_show_bones.setChecked(True)
        self.chk_show_bones.toggled.connect(self._on_toggle_bones_visibility)
        toolbar_row1.addWidget(self.chk_show_bones)

        self.chk_wireframe = QCheckBox("Arêtes")
        self.chk_wireframe.setChecked(True)
        self.chk_wireframe.toggled.connect(self._on_toggle_wireframe)
        toolbar_row1.addWidget(self.chk_wireframe)

        center_layout.addLayout(toolbar_row1)

        toolbar_row2 = QHBoxLayout()
        toolbar_row2.setSpacing(6)

        toolbar_row2.addWidget(QLabel("📐 Grille :"))
        self.combo_grid = QComboBox()
        for label, gval in GRID_OPTIONS:
            self.combo_grid.addItem(label, gval)
        self.combo_grid.currentIndexChanged.connect(self._on_grid_size_changed)
        toolbar_row2.addWidget(self.combo_grid)

        toolbar_row2.addWidget(QLabel("👁️ Aperçu :"))
        self.combo_context = QComboBox()
        self.combo_context.addItems([
            "🌍 Monde Luanti (Grille & Ombrage)",
            "🤚 Main 1re Personne (Wield View)",
            "🎒 Icône Menu Créatif (Isométrique)",
        ])
        self.combo_context.currentIndexChanged.connect(self._on_preview_context_changed)
        toolbar_row2.addWidget(self.combo_context)

        toolbar_row2.addStretch()

        btn_reset_cam = QPushButton("🎥 Recadrer Caméra")
        btn_reset_cam.clicked.connect(self._reset_camera_view)
        toolbar_row2.addWidget(btn_reset_cam)

        center_layout.addLayout(toolbar_row2)

        self.viewport = PandaViewport(ModelData("Mobs"), interaction_mode="transform", parent=self)
        self.viewport.transformDragged.connect(self._refresh_inspector_from_selection)
        self.viewport.voxelClicked3D.connect(self._on_viewport_voxel_clicked)
        center_layout.addWidget(self.viewport, 1)

        splitter.addWidget(center_panel)

        # =====================================================================
        # 3. PANNEAU DROIT : 3 ONGLETS (1. Géométrie | 2. MagicaVoxel | 3. IA)
        # =====================================================================
        self.right_tabs = QTabWidget()
        self.right_tabs.setMinimumWidth(315)
        self.right_tabs.setMaximumWidth(405)

        # --- ONGLET 1 : POSE, DIMENSIONS & PIVOT ---
        tab_geom_scroll = QScrollArea()
        tab_geom_scroll.setWidgetResizable(True)
        tab_geom_scroll.setFrameShape(QFrame.Shape.NoFrame)

        geom_panel = QFrame()
        geom_layout = QVBoxLayout(geom_panel)
        geom_layout.setContentsMargins(8, 8, 8, 8)
        geom_layout.setSpacing(8)

        grp_ident = QGroupBox("🧊 Cube Sélectionné & Bone Parent")
        ident_form = QFormLayout(grp_ident)
        ident_form.setContentsMargins(8, 8, 8, 8)
        ident_form.setSpacing(6)

        self.inp_cube_name = QLineEdit()
        self.inp_cube_name.textEdited.connect(self._on_cube_name_edited)
        ident_form.addRow("Nom :", self.inp_cube_name)

        self.combo_parent_bone = QComboBox()
        self.combo_parent_bone.currentTextChanged.connect(self._on_cube_bone_changed)
        ident_form.addRow("Bone :", self.combo_parent_bone)

        geom_layout.addWidget(grp_ident)

        self.spn_pos = self._create_xyz_group(geom_layout, "📍 Position du Cube (X, Y, Z px)", -512.0, 512.0, 0.5)
        self.spn_size = self._create_xyz_group(geom_layout, "📐 Taille du Cube (W, H, D px)", 1.0, 256.0, 1.0)
        self.spn_pivot = self._create_xyz_group(geom_layout, "🎯 Point de Pivot (PX, PY, PZ)", -512.0, 512.0, 0.5)

        btn_center_piv = QPushButton("🎯 Centrer le Pivot sur ce Cube")
        btn_center_piv.clicked.connect(self._center_pivot_on_selected_cube)
        geom_layout.addWidget(btn_center_piv)

        self.spn_bone_rot = self._create_xyz_group(geom_layout, "🦴 Rotation du Bone (RX°, RY°, RZ°)", -180.0, 180.0, 5.0)
        self.spn_cube_rot = self._create_xyz_group(geom_layout, "🔄 Rotation du Cube (RX°, RY°, RZ°)", -180.0, 180.0, 5.0)

        btn_reset_rot = QPushButton("🔄 Remettre les Rotations à 0°")
        btn_reset_rot.clicked.connect(self._reset_selected_rotations)
        geom_layout.addWidget(btn_reset_rot)

        geom_layout.addStretch()
        tab_geom_scroll.setWidget(geom_panel)
        self.right_tabs.addTab(tab_geom_scroll, "🧊 Géométrie")

        # --- ONGLET 2 : STUDIO 3D VOXEL & FORMES PRÉFAITES (MAGICAVOXEL) ---
        tab_voxel_scroll = QScrollArea()
        tab_voxel_scroll.setWidgetResizable(True)
        tab_voxel_scroll.setFrameShape(QFrame.Shape.NoFrame)

        voxel_panel = QFrame()
        voxel_layout = QVBoxLayout(voxel_panel)
        voxel_layout.setContentsMargins(8, 8, 8, 8)
        voxel_layout.setSpacing(8)

        grp_vshape = QGroupBox("🔮 Générateur de Formes 3D (MagicaVoxel)")
        vs_form = QFormLayout(grp_vshape)
        vs_form.setContentsMargins(8, 10, 8, 10)
        vs_form.setSpacing(6)

        self.combo_mv_shape = QComboBox()
        for skey, slbl in MAGICAVOXEL_SHAPES:
            self.combo_mv_shape.addItem(slbl, skey)
        vs_form.addRow("Forme 3D :", self.combo_mv_shape)

        # Dimensions X, Y, Z de la forme
        sz_row = QHBoxLayout()
        self.spn_mv_sx = QSpinBox()
        self.spn_mv_sy = QSpinBox()
        self.spn_mv_sz = QSpinBox()
        for spn, val in [(self.spn_mv_sx, 8), (self.spn_mv_sy, 8), (self.spn_mv_sz, 8)]:
            spn.setRange(1, 128)
            spn.setValue(val)
        sz_row.addWidget(QLabel("L:"))
        sz_row.addWidget(self.spn_mv_sx)
        sz_row.addWidget(QLabel("H:"))
        sz_row.addWidget(self.spn_mv_sy)
        sz_row.addWidget(QLabel("P:"))
        sz_row.addWidget(self.spn_mv_sz)
        vs_form.addRow("Taille (X,Y,Z) :", sz_row)

        # Position centre CX, CY, CZ
        pos_row = QHBoxLayout()
        self.spn_mv_cx = QSpinBox()
        self.spn_mv_cy = QSpinBox()
        self.spn_mv_cz = QSpinBox()
        for spn, val in [(self.spn_mv_cx, 0), (self.spn_mv_cy, 0), (self.spn_mv_cz, 0)]:
            spn.setRange(-128, 128)
            spn.setValue(val)
        pos_row.addWidget(QLabel("X:"))
        pos_row.addWidget(self.spn_mv_cx)
        pos_row.addWidget(QLabel("Y:"))
        pos_row.addWidget(self.spn_mv_cy)
        pos_row.addWidget(QLabel("Z:"))
        pos_row.addWidget(self.spn_mv_cz)
        vs_form.addRow("Centre (X,Y,Z) :", pos_row)

        # Orientation + Creux + Épaisseur
        opt_row = QHBoxLayout()
        self.combo_mv_axis = QComboBox()
        self.combo_mv_axis.addItems(["Axe Y (Vertical)", "Axe X (Horizontal)", "Axe Z (Profondeur)"])
        opt_row.addWidget(self.combo_mv_axis, 1)

        self.chk_mv_hollow = QCheckBox("Creux")
        opt_row.addWidget(self.chk_mv_hollow)

        self.spn_mv_thick = QSpinBox()
        self.spn_mv_thick.setRange(1, 16)
        self.spn_mv_thick.setValue(1)
        self.spn_mv_thick.setToolTip("Épaisseur de la paroi si Creux est activé")
        opt_row.addWidget(self.spn_mv_thick)
        vs_form.addRow("Axe & Paroi :", opt_row)

        # Opération Booléenne
        self.combo_mv_bool = QComboBox()
        self.combo_mv_bool.addItem("➕ Ajouter / Fusionner au Bone (Union Voxel)", "add")
        self.combo_mv_bool.addItem("⛏️ Creuser / Soustraire dans les Cubes (Booléen)", "carve")
        self.combo_mv_bool.addItem("🧩 Créer comme Pièce 3D Indépendante", "separate")
        self.combo_mv_bool.addItem("🔄 Remplacer le Bone Actif par cette Forme", "replace")
        vs_form.addRow("Mode Booléen :", self.combo_mv_bool)

        # Couleur Voxel
        col_row = QHBoxLayout()
        self.btn_mv_color = QPushButton("🎨 Choisir Couleur Voxel")
        self.btn_mv_color.setStyleSheet("background-color: #38bdf8; color: #0f172a; font-weight: bold;")
        self.btn_mv_color.clicked.connect(self._pick_voxel_color)
        col_row.addWidget(self.btn_mv_color, 1)
        vs_form.addRow("Couleur :", col_row)

        btn_spawn_shape = QPushButton("✨ Générer la Forme 3D Maintenant")
        btn_spawn_shape.setObjectName("PrimaryButton")
        btn_spawn_shape.clicked.connect(self._on_generate_magicavoxel_shape)
        vs_form.addRow("", btn_spawn_shape)

        voxel_layout.addWidget(grp_vshape)

        # Sculpture Interactive au Clic & Symétrie Miroir X / Y / Z
        grp_sculpt = QGroupBox("🖌️ Sculpture Voxel au Clic & Symétrie Miroir")
        sc_layout = QVBoxLayout(grp_sculpt)
        sc_layout.setContentsMargins(8, 10, 8, 10)
        sc_layout.setSpacing(6)

        self.combo_click_action = QComboBox()
        self.combo_click_action.addItem("➕ Poser Voxel au Clic (Attach)", "attach")
        self.combo_click_action.addItem("⛏️ Creuser / Gommer Voxel au Clic (Erase)", "erase")
        self.combo_click_action.addItem("🔮 Estampiller la Forme 3D Choisie au Clic", "stamp_shape")
        sc_layout.addWidget(self.combo_click_action)

        rad_row = QHBoxLayout()
        rad_row.addWidget(QLabel("Rayon Pinceau Voxel :"))
        self.spn_sculpt_radius = QSpinBox()
        self.spn_sculpt_radius.setRange(0, 6)
        self.spn_sculpt_radius.setValue(0)
        rad_row.addWidget(self.spn_sculpt_radius)
        sc_layout.addLayout(rad_row)

        sym_row = QHBoxLayout()
        sym_row.addWidget(QLabel("🪞 Symétrie :"))
        self.chk_sym_x = QCheckBox("Miroir X")
        self.chk_sym_y = QCheckBox("Miroir Y")
        self.chk_sym_z = QCheckBox("Miroir Z")
        sym_row.addWidget(self.chk_sym_x)
        sym_row.addWidget(self.chk_sym_y)
        sym_row.addWidget(self.chk_sym_z)
        sc_layout.addLayout(sym_row)

        btn_activate_sculpt = QPushButton("🎯 Activer le Mode Sculpture Voxel dans la Vue 3D [V]")
        btn_activate_sculpt.clicked.connect(lambda: self.btn_voxel_mode.setChecked(True))
        sc_layout.addWidget(btn_activate_sculpt)

        btn_greedy = QPushButton("⚡ Optimiser le Maillage (Greedy Meshing)")
        btn_greedy.clicked.connect(self._on_optimize_greedy_mesh)
        sc_layout.addWidget(btn_greedy)

        self.lbl_voxel_status = QLabel("Astuce : En mode [V], Shift+Clic Gauche creuse directement un voxel.")
        self.lbl_voxel_status.setWordWrap(True)
        self.lbl_voxel_status.setStyleSheet("color: #93c5fd; font-size: 11px;")
        sc_layout.addWidget(self.lbl_voxel_status)

        voxel_layout.addWidget(grp_sculpt)
        voxel_layout.addStretch()
        tab_voxel_scroll.setWidget(voxel_panel)
        self.right_tabs.addTab(tab_voxel_scroll, "🔮 Voxel & Formes")

        # --- ONGLET 3 : IA & PROPRIÉTÉS GAMEPLAY IN-GAME ---
        tab_ai_scroll = QScrollArea()
        tab_ai_scroll.setWidgetResizable(True)
        tab_ai_scroll.setFrameShape(QFrame.Shape.NoFrame)

        ai_panel = QFrame()
        ai_layout = QVBoxLayout(ai_panel)
        ai_layout.setContentsMargins(8, 8, 8, 8)
        ai_layout.setSpacing(8)

        self.grp_gameplay = QGroupBox("🧠 Intelligence Artificielle & Stats Luanti")
        gp_form = QFormLayout(self.grp_gameplay)
        gp_form.setContentsMargins(8, 10, 8, 10)
        gp_form.setSpacing(8)

        self.combo_ai = QComboBox()
        for lbl, key in AI_BEHAVIOR_OPTIONS:
            self.combo_ai.addItem(lbl, key)
        self.combo_ai.currentIndexChanged.connect(self._on_gameplay_settings_changed)
        gp_form.addRow("IA du Mob :", self.combo_ai)

        self.spn_hp = QSpinBox()
        self.spn_hp.setRange(1, 5000)
        self.spn_hp.setValue(20)
        self.spn_hp.valueChanged.connect(self._on_gameplay_settings_changed)
        gp_form.addRow("Points de Vie (PV) :", self.spn_hp)

        self.spn_speed = QDoubleSpinBox()
        self.spn_speed.setRange(0.5, 25.0)
        self.spn_speed.setSingleStep(0.5)
        self.spn_speed.setValue(2.5)
        self.spn_speed.valueChanged.connect(self._on_gameplay_settings_changed)
        gp_form.addRow("Vitesse Marche :", self.spn_speed)

        self.spn_damage = QSpinBox()
        self.spn_damage.setRange(1, 500)
        self.spn_damage.setValue(4)
        self.spn_damage.valueChanged.connect(self._on_gameplay_settings_changed)
        gp_form.addRow("Dégâts (Mob / Arme) :", self.spn_damage)

        self.inp_drop = QLineEdit("default:mese_crystal_fragment")
        self.inp_drop.textEdited.connect(self._on_gameplay_settings_changed)
        gp_form.addRow("Butin (Drop) :", self.inp_drop)

        self.spn_light = QSpinBox()
        self.spn_light.setRange(0, 14)
        self.spn_light.setValue(0)
        self.spn_light.valueChanged.connect(self._on_gameplay_settings_changed)
        gp_form.addRow("Lumière Bloc (0-14) :", self.spn_light)

        self.chk_anim_ingame = QCheckBox("Jouer l'animation Timeline en jeu")
        self.chk_anim_ingame.setChecked(True)
        self.chk_anim_ingame.toggled.connect(self._on_gameplay_settings_changed)
        gp_form.addRow("", self.chk_anim_ingame)

        ai_layout.addWidget(self.grp_gameplay)
        ai_layout.addStretch()
        tab_ai_scroll.setWidget(ai_panel)
        self.right_tabs.addTab(tab_ai_scroll, "🧠 IA & Stats")

        splitter.addWidget(self.right_tabs)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([245, 810, 335])

        root.addWidget(splitter)

    def _create_xyz_group(self, parent_layout: QVBoxLayout, title: str, min_v: float, max_v: float, step: float):
        grp = QGroupBox(title)
        layout = QHBoxLayout(grp)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        spins = []
        for axis_lbl, color, obj_name in [
            ("X", "#ef4444", "AxisX"),
            ("Y", "#22c55e", "AxisY"),
            ("Z", "#3b82f6", "AxisZ"),
        ]:
            lbl = QLabel(axis_lbl)
            lbl.setStyleSheet(f"color: {color}; font-weight: 800;")
            spn = QDoubleSpinBox()
            spn.setObjectName(obj_name)
            spn.setRange(min_v, max_v)
            spn.setSingleStep(step)
            spn.setDecimals(1)
            spn.valueChanged.connect(self._on_inspector_values_changed)
            layout.addWidget(lbl)
            layout.addWidget(spn, 1)
            spins.append(spn)
        parent_layout.addWidget(grp)
        return spins

    # =========================================================================
    # ACTIONS MAGICAVOXEL 3D (FORMES PRÉFAITES, SCULPTURE AU CLIC, GREEDY MESH)
    # =========================================================================
    def _pick_voxel_color(self):
        col = QColorDialog.getColor(self.voxel_color, self, "Couleur de la Forme / du Voxel")
        if col.isValid():
            self.voxel_color = col
            self.viewport.paint_color = col
            self.btn_mv_color.setStyleSheet(
                f"background-color: {col.name()}; color: #ffffff; font-weight: bold;"
            )

    def _selected_mv_axis(self) -> str:
        idx = self.combo_mv_axis.currentIndex()
        return "X" if idx == 1 else ("Z" if idx == 2 else "Y")

    def _on_generate_magicavoxel_shape(self, center_override: Optional[Tuple[int, int, int]] = None):
        if not self.model_data:
            return
        shape_type = self.combo_mv_shape.currentData() or "cube"
        sx = self.spn_mv_sx.value()
        sy = self.spn_mv_sy.value()
        sz = self.spn_mv_sz.value()
        center = center_override or (self.spn_mv_cx.value(), self.spn_mv_cy.value(), self.spn_mv_cz.value())
        hollow = self.chk_mv_hollow.isChecked()
        thick = self.spn_mv_thick.value()
        axis = self._selected_mv_axis()
        bool_op = self.combo_mv_bool.currentData() or "add"

        count = self.model_data.apply_magicavoxel_shape(
            shape_type=shape_type,
            center=center,
            size_xyz=(sx, sy, sz),
            color=self.voxel_color,
            hollow=hollow,
            thickness=thick,
            axis=axis,
            boolean_op=bool_op,
            sym_x=self.chk_sym_x.isChecked(),
            sym_y=self.chk_sym_y.isChecked(),
            sym_z=self.chk_sym_z.isChecked(),
        )
        self._refresh_hierarchy_tree()
        self._refresh_inspector_from_selection()
        self.lbl_voxel_status.setText(
            f"✅ Forme '{shape_type}' appliquée ({bool_op}) -> {count} cubes optimisés par Greedy Meshing."
        )

    def _on_viewport_voxel_clicked(self, hit_x: int, hit_y: int, hit_z: int, place_x: int, place_y: int, place_z: int):
        if not self.model_data:
            return
        act = self.combo_click_action.currentData() or "attach"
        if act == "stamp_shape":
            self._on_generate_magicavoxel_shape(center_override=(place_x, place_y, place_z))
        elif act == "erase":
            self.model_data.sculpt_voxel_at(
                (hit_x, hit_y, hit_z),
                mode="erase",
                color=self.voxel_color,
                brush_radius=self.spn_sculpt_radius.value(),
                sym_x=self.chk_sym_x.isChecked(),
                sym_y=self.chk_sym_y.isChecked(),
                sym_z=self.chk_sym_z.isChecked(),
            )
            self._refresh_hierarchy_tree()
        else:
            self.model_data.sculpt_voxel_at(
                (place_x, place_y, place_z),
                mode="attach",
                color=self.voxel_color,
                brush_radius=self.spn_sculpt_radius.value(),
                sym_x=self.chk_sym_x.isChecked(),
                sym_y=self.chk_sym_y.isChecked(),
                sym_z=self.chk_sym_z.isChecked(),
            )
            self._refresh_hierarchy_tree()

    def _on_optimize_greedy_mesh(self):
        if not self.model_data:
            return
        before, after = self.model_data.optimize_current_bone_greedy_mesh()
        self._refresh_hierarchy_tree()
        self.lbl_voxel_status.setText(f"⚡ Greedy Meshing : {before} cubes fusionnés en {after} cubes optimaux !")

    def _on_voxel_mode_toggled(self, checked: bool):
        if checked:
            self.viewport.interaction_mode = "voxel_sculpt"
            self.right_tabs.setCurrentIndex(1)
        else:
            self.viewport.interaction_mode = "transform"
        self.viewport.update()

    # =========================================================================
    # RACCOURCIS CLAVIER & OUTILS DE TRANSFORMATION 3D
    # =========================================================================
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_G:
            self._set_transform_tool("move")
        elif key == Qt.Key.Key_S:
            self._set_transform_tool("scale")
        elif key == Qt.Key.Key_R:
            self._set_transform_tool("rotate")
        elif key == Qt.Key.Key_P:
            self._set_transform_tool("pivot")
        elif key == Qt.Key.Key_V:
            self.btn_voxel_mode.setChecked(not self.btn_voxel_mode.isChecked())
        elif key == Qt.Key.Key_B:
            self.btn_quick_paint.setChecked(not self.btn_quick_paint.isChecked())
        else:
            super().keyPressEvent(event)

    def _refresh_hierarchy_tree(self):
        if not self.model_data:
            return
        self._updating_ui = True
        self.tree.clear()
        self.combo_parent_bone.clear()

        bone_items = {}
        for bname, bone in self.model_data.bones.items():
            self.combo_parent_bone.addItem(bname)
            item = QTreeWidgetItem([f"🦴 {bname}", "Bone"])
            item.setData(0, Qt.ItemDataRole.UserRole, ("bone", bname))
            bone_items[bname] = item

        for bname, bone in self.model_data.bones.items():
            item = bone_items[bname]
            if bone.parent_name and bone.parent_name in bone_items:
                bone_items[bone.parent_name].addChild(item)
            else:
                self.tree.addTopLevelItem(item)

        for cube in self.model_data.cubes:
            w, h, d = cube.get_pixel_dimensions()
            c_item = QTreeWidgetItem([f"🧊 {cube.name}", f"{w}×{h}×{d}px"])
            c_item.setData(0, Qt.ItemDataRole.UserRole, ("cube", cube.cube_id))
            parent_bone_item = bone_items.get(cube.bone_name)
            if parent_bone_item:
                parent_bone_item.addChild(c_item)
            else:
                self.tree.addTopLevelItem(c_item)
            if cube.cube_id == self.model_data.selected_cube_id:
                c_item.setSelected(True)

        self.tree.expandAll()
        self._updating_ui = False

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, col: int):
        if not self.model_data:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, ident = data
        if kind == "cube":
            self.model_data.select_cube(ident)
        elif kind == "bone":
            self.model_data.select_bone(ident)

    def _on_model_selection_changed(self):
        self._refresh_hierarchy_tree()
        self._refresh_inspector_from_selection()

    def _refresh_inspector_from_selection(self):
        if not self.model_data:
            return
        self._updating_ui = True
        cube = self.model_data.get_selected_cube()
        bone = self.model_data.get_selected_bone()

        if cube:
            self.inp_cube_name.setText(cube.name)
            self.combo_parent_bone.setCurrentText(cube.bone_name)
            for i in range(3):
                self.spn_pos[i].setValue(cube.position[i])
                self.spn_size[i].setValue(cube.size[i])
                self.spn_pivot[i].setValue(cube.pivot[i])
                self.spn_cube_rot[i].setValue(cube.rotation[i])

        if bone:
            for i in range(3):
                self.spn_bone_rot[i].setValue(bone.rotation[i])

        for idx, (_, gval) in enumerate(GRID_OPTIONS):
            if gval == self.model_data.grid_size:
                self.combo_grid.setCurrentIndex(idx)
                break

        for idx, (_, aikey) in enumerate(AI_BEHAVIOR_OPTIONS):
            if aikey == self.model_data.ai_behavior:
                self.combo_ai.setCurrentIndex(idx)
                break

        self.spn_hp.setValue(self.model_data.max_hp)
        self.spn_speed.setValue(self.model_data.move_speed)
        self.spn_damage.setValue(self.model_data.attack_damage)
        self.inp_drop.setText(self.model_data.drop_item)
        self.spn_light.setValue(self.model_data.light_source)
        self.chk_anim_ingame.setChecked(self.model_data.animate_in_game)

        self._updating_ui = False

    def _on_inspector_values_changed(self):
        if self._updating_ui or not self.model_data:
            return
        cube = self.model_data.get_selected_cube()
        bone = self.model_data.get_selected_bone()

        if cube:
            size_changed = False
            for i in range(3):
                cube.position[i] = self.spn_pos[i].value()
                new_s = self.spn_size[i].value()
                if int(round(new_s)) != int(round(cube.size[i])):
                    size_changed = True
                cube.size[i] = new_s
                cube.pivot[i] = self.spn_pivot[i].value()
                cube.rotation[i] = self.spn_cube_rot[i].value()

            if size_changed:
                self.model_data.auto_pack_uv_atlas(repaint_default_colors=False)

        if bone:
            for i in range(3):
                bone.rotation[i] = self.spn_bone_rot[i].value()

        self.model_data.modelChanged.emit()

    def _reset_selected_rotations(self):
        if not self.model_data:
            return
        cube = self.model_data.get_selected_cube()
        bone = self.model_data.get_selected_bone()
        if cube:
            cube.rotation = [0.0, 0.0, 0.0]
        if bone:
            bone.rotation = [0.0, 0.0, 0.0]
        self._refresh_inspector_from_selection()
        self.model_data.modelChanged.emit()

    def _on_gameplay_settings_changed(self):
        if self._updating_ui or not self.model_data:
            return
        self.model_data.ai_behavior = self.combo_ai.currentData() or "passive"
        self.model_data.max_hp = self.spn_hp.value()
        self.model_data.move_speed = self.spn_speed.value()
        self.model_data.attack_damage = self.spn_damage.value()
        self.model_data.drop_item = self.inp_drop.text().strip() or "default:mese_crystal_fragment"
        self.model_data.light_source = self.spn_light.value()
        self.model_data.animate_in_game = self.chk_anim_ingame.isChecked()

    def _on_grid_size_changed(self, idx: int):
        if self._updating_ui:
            return
        gval = self.combo_grid.itemData(idx)
        if gval:
            self.viewport.set_grid_size(int(gval))

    def _on_cube_name_edited(self, text: str):
        if not self.model_data:
            return
        cube = self.model_data.get_selected_cube()
        if cube and text.strip():
            cube.name = text.strip()
            self._refresh_hierarchy_tree()
            self.model_data.modelChanged.emit()

    def _on_cube_bone_changed(self, bone_name: str):
        if self._updating_ui or not bone_name or not self.model_data:
            return
        cube = self.model_data.get_selected_cube()
        if cube and bone_name in self.model_data.bones:
            cube.bone_name = bone_name
            self.model_data.selected_bone_name = bone_name
            self._refresh_hierarchy_tree()
            self.model_data.modelChanged.emit()

    def _center_pivot_on_selected_cube(self):
        if not self.model_data:
            return
        cube = self.model_data.get_selected_cube()
        if not cube:
            return
        for i in range(3):
            cube.pivot[i] = cube.position[i] + cube.size[i] * 0.5
        bone = self.model_data.get_selected_bone()
        if bone:
            bone.pivot = list(cube.pivot)
        self._refresh_inspector_from_selection()
        self.model_data.modelChanged.emit()

    def _set_transform_tool(self, tool_key: str):
        if tool_key in self.tool_buttons:
            self.tool_buttons[tool_key].setChecked(True)
        self.viewport.interaction_mode = "transform"
        self.viewport.transform_tool = tool_key
        self.viewport.update()

    def _on_quick_paint_toggled(self, checked: bool):
        if checked:
            col = QColorDialog.getColor(self.viewport.paint_color, self, "Choisir la couleur du pinceau 3D")
            if col.isValid():
                self.viewport.paint_color = col
            self.viewport.interaction_mode = "paint_3d"
        else:
            self.viewport.interaction_mode = "transform"
        self.viewport.update()

    def _on_toggle_bones_visibility(self, checked: bool):
        self.viewport.show_bones_and_pivots = checked
        self.viewport.update()

    def _on_toggle_wireframe(self, checked: bool):
        self.viewport.show_wireframe = checked
        self.viewport.update()

    def _reset_camera_view(self):
        self.viewport.cam_yaw = -38.0
        self.viewport.cam_pitch = 24.0
        gsize = self.model_data.grid_size if self.model_data else 16
        self.viewport.cam_distance = max(38.0, gsize * 2.4)
        self.viewport.cam_target = [0.0, 7.0, 0.0]
        self.viewport.update()

    def _on_preview_context_changed(self, idx: int):
        contexts = ["world", "wield", "inventory"]
        self.viewport.preview_context = contexts[idx] if 0 <= idx < len(contexts) else "world"
        self.viewport.update()

    def _load_preset(self, category: str):
        if self.model_data:
            self.model_data.load_default_preset(category)
            self._refresh_hierarchy_tree()
            self._refresh_inspector_from_selection()

    def _on_add_cube(self):
        if self.model_data:
            self.model_data.add_cube()
            self._refresh_hierarchy_tree()
            self._refresh_inspector_from_selection()

    def _on_dup_cube(self):
        if self.model_data:
            self.model_data.duplicate_selected_cube()
            self._refresh_hierarchy_tree()
            self._refresh_inspector_from_selection()

    def _on_del_cube(self):
        if self.model_data:
            self.model_data.delete_selected_cube()
            self._refresh_hierarchy_tree()
            self._refresh_inspector_from_selection()

    def _on_add_bone(self):
        if not self.model_data:
            return
        name, ok = QInputDialog.getText(self, "Nouveau Bone", "Nom du Bone (ex: bras_droit, aile_gauche) :")
        if ok and name.strip():
            self.model_data.add_bone(name.strip(), self.model_data.selected_bone_name)
            self._refresh_hierarchy_tree()
            self._refresh_inspector_from_selection()