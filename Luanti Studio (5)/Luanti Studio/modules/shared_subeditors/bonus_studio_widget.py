# -*- coding: utf-8 -*-
"""
modules/shared_subeditors/bonus_studio_widget.py
Workbench Bonus Tout-en-Un (Tâche 6) :
1. 🍳 Éditeur Visuel de Recettes de Craft 3×3, Sans Forme, Fourneau (Cuisson) & Combustible
2. 🌍 Générateur de Minerais Souterrains (register_ore) & Spawners Naturels de Mobs (ABM)
3. ✨ Studio d'Effets de Particules Temps Réel avec Simulateur Animé 30 FPS & Génération Lua.
"""

import random
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

try:
    from PyQt6.QtCore import Qt, QTimer, QRectF, pyqtSignal
    from PyQt6.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QLinearGradient
    )
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter, QFrame,
        QLabel, QPushButton, QListWidget, QListWidgetItem, QComboBox,
        QSpinBox, QDoubleSpinBox, QLineEdit, QGroupBox, QFormLayout,
        QTabWidget, QPlainTextEdit, QColorDialog
    )
except ImportError:
    from PyQt5.QtCore import Qt, QTimer, QRectF, pyqtSignal
    from PyQt5.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QLinearGradient
    )
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter, QFrame,
        QLabel, QPushButton, QListWidget, QListWidgetItem, QComboBox,
        QSpinBox, QDoubleSpinBox, QLineEdit, QGroupBox, QFormLayout,
        QTabWidget, QPlainTextEdit, QColorDialog
    )


STANDARD_CRAFT_ITEMS: List[Tuple[str, str, str]] = [
    ("", "⬛ Case Vide (Air)", "#1e293b"),
    ("default:stick", "🥢 Bâton de Bois (default:stick)", "#a37846"),
    ("default:wood", "🪵 Planches de Bois (default:wood)", "#b58d58"),
    ("default:tree", "🌳 Tronc d'Arbre (default:tree)", "#594026"),
    ("default:cobble", "🪨 Pierre Taillée (default:cobble)", "#64748b"),
    ("default:stone", "⛰️ Pierre (default:stone)", "#7d8288"),
    ("default:coal_lump", "⚫ Charbon (default:coal_lump)", "#18181b"),
    ("default:steel_ingot", "🔩 Lingot d'Acier (default:steel_ingot)", "#cbd5e1"),
    ("default:copper_ingot", "🥉 Lingot de Cuivre (default:copper_ingot)", "#ea580c"),
    ("default:gold_ingot", "🪙 Lingot d'Or (default:gold_ingot)", "#facc15"),
    ("default:diamond", "💎 Diamant (default:diamond)", "#38bdf8"),
    ("default:mese_crystal", "✨ Cristal de Mese (default:mese_crystal)", "#eab308"),
    ("default:mese_crystal_fragment", "🔸 Fragment de Mese", "#fde047"),
    ("default:obsidian", "🟣 Obsidienne (default:obsidian)", "#3b0764"),
    ("default:glass", "🪟 Verre (default:glass)", "#e0f2fe"),
    ("default:sand", "🏖️ Sable (default:sand)", "#d9c882"),
    ("default:dirt", "🟫 Terre (default:dirt)", "#785233"),
    ("default:apple", "🍎 Pomme (default:apple)", "#ef4444"),
    ("default:book", "📘 Livre (default:book)", "#2563eb"),
]


@dataclass
class CraftRecipeDef:
    name: str = "recette_lame_astrale"
    recipe_type: str = "shaped"  # "shaped", "shapeless", "cooking", "fuel"
    output_item: str = "mon_mod:lame_astrale"
    output_count: int = 1
    grid: List[str] = field(default_factory=lambda: [
        "", "default:diamond", "",
        "", "default:mese_crystal", "",
        "", "default:stick", "",
    ])
    cooktime: int = 5


@dataclass
class OreGenRule:
    name: str = "filon_cristal_azur"
    ore_node: str = "mon_mod:cristal_azur"
    wherein_node: str = "default:stone"
    ore_type: str = "scatter"  # "scatter", "blob"
    scarcity_dim: int = 9      # 1 filon tous les 9x9x9 blocs
    clust_num_ores: int = 5
    clust_size: int = 3
    y_min: int = -512
    y_max: int = -16


@dataclass
class MobSpawnRule:
    name: str = "spawn_renard_bleu"
    mob_id: str = "mon_mod:renard_bleu"
    spawn_on_node: str = "default:dirt_with_grass"
    interval_sec: int = 25
    chance_inv: int = 40       # 1 chance sur 40
    min_height: int = -10
    max_height: int = 200


@dataclass
class ParticleEffectDef:
    name: str = "aura_astrale"
    target_node_or_id: str = "mon_mod:cristal_azur"
    preset_style: str = "astral_aura"
    color_hex: str = "#38bdf8"
    amount: int = 22
    duration: float = 1.5
    min_size: float = 1.5
    max_size: float = 3.8
    speed_y: float = 1.8
    spread_radius: float = 0.65
    glow: int = 14


class CraftSlotButton(QPushButton):
    """Bouton représentant une case de la grille de craft 3×3 (Clic gauche = Poser, Clic droit = Vider)."""
    rightClicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.rightClicked.emit()
            return
        super().mousePressEvent(event)


class LiveParticlePreviewWidget(QWidget):
    """Simulateur 2D/2.5D temps réel d'effets de particules Luanti à 30 FPS."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 260)
        self.effect = ParticleEffectDef()
        self._particles: List[Dict[str, float]] = []

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_particles)
        self._timer.start(35)

    def set_effect(self, effect: ParticleEffectDef):
        self.effect = effect
        self.update()

    def _tick_particles(self):
        cx = self.width() * 0.5
        cy = self.height() * 0.68
        spread_px = self.effect.spread_radius * 75.0

        spawn_rate = max(1, self.effect.amount // 8)
        for _ in range(spawn_rate):
            if len(self._particles) < 120:
                rx = (random.random() - 0.5) * 2.0 * spread_px
                ry = (random.random() - 0.5) * 24.0
                vx = (random.random() - 0.5) * 1.4
                vy = -self.effect.speed_y * (0.7 + random.random() * 0.6)
                size = self.effect.min_size + random.random() * max(0.2, self.effect.max_size - self.effect.min_size)
                self._particles.append({
                    "x": cx + rx,
                    "y": cy + ry,
                    "vx": vx,
                    "vy": vy,
                    "size": size * 3.2,
                    "alpha": 255.0,
                    "decay": 255.0 / max(10.0, self.effect.duration * 25.0),
                })

        alive = []
        for p in self._particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["alpha"] -= p["decay"]
            if p["alpha"] > 8.0:
                alive.append(p)
        self._particles = alive
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        bg = QLinearGradient(0, 0, 0, self.height())
        bg.setColorAt(0.0, QColor("#0b0f19"))
        bg.setColorAt(1.0, QColor("#162032"))
        painter.fillRect(self.rect(), bg)

        cx = self.width() * 0.5
        cy = self.height() * 0.68

        block_r = QRectF(cx - 26, cy - 16, 52, 52)
        painter.setBrush(QBrush(QColor("#1e293b")))
        painter.setPen(QPen(QColor("#60a5fa"), 2.0))
        painter.drawRoundedRect(block_r, 6, 6)

        base_col = QColor(self.effect.color_hex)
        for p in self._particles:
            alpha = max(0, min(255, int(p["alpha"])))
            s = p["size"]
            if self.effect.glow >= 8:
                glow_c = QColor(base_col.red(), base_col.green(), base_col.blue(), alpha // 3)
                painter.setBrush(QBrush(glow_c))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(QRectF(p["x"] - s * 0.9, p["y"] - s * 0.9, s * 1.8, s * 1.8))

            core_c = QColor(base_col.red(), base_col.green(), base_col.blue(), alpha)
            painter.setBrush(QBrush(core_c))
            painter.setPen(QPen(QColor(255, 255, 255, alpha // 2), 1.0))
            painter.drawRect(QRectF(p["x"] - s * 0.5, p["y"] - s * 0.5, s, s))

        painter.setPen(QColor("#93c5fd"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(
            12, 20,
            f"✨ Aperçu Temps Réel : {self.effect.name} -> Cible : {self.effect.target_node_or_id}"
        )


class BonusStudioWidget(QWidget):
    """
    Workbench Bonus Complet (Tâche 6) :
    - Onglet 1 : 🍳 Recettes de Craft 3×3 & Fourneau (shaped, shapeless, cooking, fuel)
    - Onglet 2 : 🌍 Génération Naturelle (Minerais souterrains register_ore & Spawners de Mobs ABM)
    - Onglet 3 : ✨ Studio de Particules Temps Réel (Aura de Bloc, Effet de Mob, etc.)
    """
    bonusCodeChanged = pyqtSignal(str)

    def __init__(self, mod_name: str = "mon_mod", parent=None):
        super().__init__(parent)
        self.mod_name = mod_name
        self.selected_palette_item = "default:diamond"
        self._custom_mod_items: List[Tuple[str, str, str]] = []
        self._updating_ui = False

        self.recipes: List[CraftRecipeDef] = [
            CraftRecipeDef(
                name="craft_lame_astrale",
                recipe_type="shaped",
                output_item=f"{mod_name}:lame_astrale",
                output_count=1,
                grid=[
                    "", "default:diamond", "",
                    "", "default:mese_crystal", "",
                    "", "default:stick", "",
                ],
            ),
            CraftRecipeDef(
                name="craft_cristal_azur",
                recipe_type="shaped",
                output_item=f"{mod_name}:cristal_azur",
                output_count=2,
                grid=[
                    "default:glass", "default:diamond", "default:glass",
                    "default:diamond", "default:mese_crystal", "default:diamond",
                    "default:glass", "default:diamond", "default:glass",
                ],
            ),
        ]
        self.current_recipe_idx = 0

        self.ore_rules: List[OreGenRule] = [
            OreGenRule(
                name="filon_cristal_azur",
                ore_node=f"{mod_name}:cristal_azur",
                wherein_node="default:stone",
                ore_type="scatter",
                scarcity_dim=9,
                clust_num_ores=5,
                clust_size=3,
                y_min=-512,
                y_max=-12,
            )
        ]

        self.mob_spawn_rules: List[MobSpawnRule] = [
            MobSpawnRule(
                name="apparition_renard_bleu",
                mob_id=f"{mod_name}:renard_bleu",
                spawn_on_node="default:dirt_with_grass",
                interval_sec=30,
                chance_inv=45,
                min_height=-5,
                max_height=180,
            )
        ]

        self.particle_effects: List[ParticleEffectDef] = [
            ParticleEffectDef(
                name="aura_cristal_azur",
                target_node_or_id=f"{mod_name}:cristal_azur",
                preset_style="astral_aura",
                color_hex="#38bdf8",
                amount=20,
                duration=1.6,
                min_size=1.4,
                max_size=3.5,
                speed_y=1.6,
                spread_radius=0.65,
                glow=14,
            )
        ]

        self._build_ui()
        self._refresh_ingredient_palette()
        self._refresh_recipes_list()
        self._load_recipe_into_grid(0)
        self._refresh_ores_list()
        self._refresh_spawns_list()
        self._refresh_particles_list()
        self._compile_all_bonus_lua()

    def sync_project_assets(self, mod_name: str, assets_by_category: Dict[str, list]):
        """Synchronise dynamiquement tous les Blocs, Items et Mobs créés dans le projet."""
        self.mod_name = mod_name
        custom_list: List[Tuple[str, str, str]] = []
        for blk in assets_by_category.get("Blocks", []):
            full_id = f"{mod_name}:{blk.identifier.split(':')[-1]}"
            custom_list.append((full_id, f"★ [Bloc] {blk.display_name} ({full_id})", "#38bdf8"))
        for itm in assets_by_category.get("Items", []):
            full_id = f"{mod_name}:{itm.identifier.split(':')[-1]}"
            custom_list.append((full_id, f"★ [Item] {itm.display_name} ({full_id})", "#facc15"))
        self._custom_mod_items = custom_list
        self._refresh_ingredient_palette()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recipes": [asdict(r) for r in self.recipes],
            "ore_rules": [asdict(o) for o in self.ore_rules],
            "mob_spawn_rules": [asdict(m) for m in self.mob_spawn_rules],
            "particle_effects": [asdict(p) for p in self.particle_effects],
        }

    def load_from_dict(self, data: Dict[str, Any]):
        if not data or not isinstance(data, dict):
            return
        if "recipes" in data and isinstance(data["recipes"], list):
            self.recipes = [CraftRecipeDef(**r) for r in data["recipes"]]
        if "ore_rules" in data and isinstance(data["ore_rules"], list):
            self.ore_rules = [OreGenRule(**o) for o in data["ore_rules"]]
        if "mob_spawn_rules" in data and isinstance(data["mob_spawn_rules"], list):
            self.mob_spawn_rules = [MobSpawnRule(**m) for m in data["mob_spawn_rules"]]
        if "particle_effects" in data and isinstance(data["particle_effects"], list):
            self.particle_effects = [ParticleEffectDef(**p) for p in data["particle_effects"]]

        self.current_recipe_idx = 0
        self._refresh_recipes_list()
        if self.recipes:
            self._load_recipe_into_grid(0)
        self._refresh_ores_list()
        self._refresh_spawns_list()
        self._refresh_particles_list()
        self._compile_all_bonus_lua()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # =====================================================================
        # GAUCHE / CENTRE : 3 ONGLETS BONUS (1. Craft 3x3 | 2. Minerais & Spawners | 3. Particules)
        # =====================================================================
        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(self._build_crafting_tab(), "🍳 1. Recettes de Craft 3×3 & Fourneau")
        self.main_tabs.addTab(self._build_worldgen_spawner_tab(), "🌍 2. Minerais & Spawners de Mobs")
        self.main_tabs.addTab(self._build_particles_tab(), "✨ 3. Studio de Particules Temps Réel")
        splitter.addWidget(self.main_tabs)

        # =====================================================================
        # DROITE : APERÇU DU CODE LUA BONUS GÉNÉRÉ EN DIRECT
        # =====================================================================
        right_panel = QFrame()
        right_panel.setProperty("class", "InspectorPanel")
        right_panel.setMinimumWidth(330)
        right_panel.setMaximumWidth(450)
        r_layout = QVBoxLayout(right_panel)
        r_layout.setContentsMargins(8, 8, 8, 8)
        r_layout.setSpacing(6)

        lbl_lua = QLabel("📜 Code Lua Bonus Généré (Crafts, Minerais, ABM & Particules) :")
        lbl_lua.setStyleSheet("font-weight: bold; color: #60a5fa;")
        r_layout.addWidget(lbl_lua)

        self.lua_preview = QPlainTextEdit()
        self.lua_preview.setReadOnly(True)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.lua_preview.setFont(font)
        r_layout.addWidget(self.lua_preview, 1)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([920, 380])
        root.addWidget(splitter)

    # =========================================================================
    # ONGLET 1 : ÉDITEUR VISUEL DE RECETTES DE CRAFT 3×3 & CUISSON
    # =========================================================================
    def _build_crafting_tab(self) -> QWidget:
        tab = QFrame()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        col_left = QVBoxLayout()
        col_left.setSpacing(6)

        lbl_r = QLabel("📋 Recettes de Craft du Mod :")
        lbl_r.setStyleSheet("font-weight: bold; color: #93c5fd;")
        col_left.addWidget(lbl_r)

        self.recipes_list = QListWidget()
        self.recipes_list.setMaximumHeight(130)
        self.recipes_list.currentRowChanged.connect(self._load_recipe_into_grid)
        col_left.addWidget(self.recipes_list)

        r_btn_row = QHBoxLayout()
        btn_new_r = QPushButton("➕ Nouvelle Recette")
        btn_new_r.setObjectName("PrimaryButton")
        btn_new_r.clicked.connect(self._create_new_recipe)
        btn_del_r = QPushButton("🗑️ Supprimer")
        btn_del_r.setObjectName("DangerButton")
        btn_del_r.clicked.connect(self._delete_current_recipe)
        r_btn_row.addWidget(btn_new_r)
        r_btn_row.addWidget(btn_del_r)
        col_left.addLayout(r_btn_row)

        lbl_pal = QLabel("🎒 Palette d'Ingrédients (Sélectionnez puis cliquez sur la grille 3×3) :")
        lbl_pal.setStyleSheet("font-weight: bold; color: #38bdf8; margin-top: 6px;")
        col_left.addWidget(lbl_pal)

        self.inp_search_ing = QLineEdit()
        self.inp_search_ing.setPlaceholderText("🔍 Filtrer un ingrédient (ex: diamant, bâton, or)...")
        self.inp_search_ing.textChanged.connect(self._refresh_ingredient_palette)
        col_left.addWidget(self.inp_search_ing)

        self.palette_list = QListWidget()
        self.palette_list.currentRowChanged.connect(self._on_palette_ingredient_selected)
        col_left.addWidget(self.palette_list, 1)

        layout.addLayout(col_left, 1)

        col_right = QVBoxLayout()
        col_right.setSpacing(8)

        grp_cfg = QGroupBox("⚙️ Configuration de la Recette Active")
        cfg_form = QFormLayout(grp_cfg)

        self.inp_recipe_name = QLineEdit("craft_lame_astrale")
        self.inp_recipe_name.textEdited.connect(self._on_recipe_meta_changed)
        cfg_form.addRow("Nom Recette :", self.inp_recipe_name)

        self.combo_recipe_type = QComboBox()
        self.combo_recipe_type.addItem("🔨 Grille 3×3 Ordonnée (Shaped)", "shaped")
        self.combo_recipe_type.addItem("🥣 Sans Forme (Shapeless)", "shapeless")
        self.combo_recipe_type.addItem("🔥 Cuisson au Fourneau (Cooking)", "cooking")
        self.combo_recipe_type.addItem("⛽ Combustible Fourneau (Fuel)", "fuel")
        self.combo_recipe_type.currentIndexChanged.connect(self._on_recipe_meta_changed)
        cfg_form.addRow("Type de Craft :", self.combo_recipe_type)

        out_row = QHBoxLayout()
        self.inp_output_item = QLineEdit("mon_mod:lame_astrale")
        self.inp_output_item.textEdited.connect(self._on_recipe_meta_changed)
        btn_use_sel_out = QPushButton("⬅ Prendre Ingrédient Actif")
        btn_use_sel_out.clicked.connect(self._set_output_from_palette)
        out_row.addWidget(self.inp_output_item, 1)
        out_row.addWidget(btn_use_sel_out)
        cfg_form.addRow("Objet Produit :", out_row)

        qty_row = QHBoxLayout()
        self.spn_output_qty = QSpinBox()
        self.spn_output_qty.setRange(1, 99)
        self.spn_output_qty.setValue(1)
        self.spn_output_qty.valueChanged.connect(self._on_recipe_meta_changed)
        qty_row.addWidget(QLabel("Quantité produite :"))
        qty_row.addWidget(self.spn_output_qty)

        self.spn_cooktime = QSpinBox()
        self.spn_cooktime.setRange(1, 600)
        self.spn_cooktime.setValue(5)
        self.spn_cooktime.setSuffix(" sec")
        self.spn_cooktime.valueChanged.connect(self._on_recipe_meta_changed)
        qty_row.addWidget(QLabel("Temps Fourneau :"))
        qty_row.addWidget(self.spn_cooktime)
        cfg_form.addRow("Quantité / Temps :", qty_row)

        col_right.addWidget(grp_cfg)

        grp_grid = QGroupBox("🔨 Table de Craft 3×3 Interactive (Clic Gauche = Poser | Clic Droit = Vider)")
        g_vbox = QVBoxLayout(grp_grid)

        grid_and_arrow = QHBoxLayout()
        grid_layout = QGridLayout()
        grid_layout.setSpacing(6)

        self.slot_buttons: List[CraftSlotButton] = []
        for idx in range(9):
            btn = CraftSlotButton("Vide")
            btn.setFixedSize(98, 64)
            btn.clicked.connect(lambda checked, i=idx: self._on_craft_slot_left_clicked(i))
            btn.rightClicked.connect(lambda i=idx: self._on_craft_slot_right_clicked(i))
            self.slot_buttons.append(btn)
            grid_layout.addWidget(btn, idx // 3, idx % 3)

        grid_and_arrow.addLayout(grid_layout)

        lbl_arrow = QLabel("  ➔  ")
        lbl_arrow.setStyleSheet("font-size: 26px; font-weight: bold; color: #facc15;")
        grid_and_arrow.addWidget(lbl_arrow)

        self.btn_output_preview = QPushButton("Résultat")
        self.btn_output_preview.setFixedSize(112, 82)
        self.btn_output_preview.setStyleSheet(
            "background-color: #1e293b; border: 2px solid #facc15; border-radius: 8px; "
            "color: #fde047; font-weight: bold; font-size: 11px;"
        )
        self.btn_output_preview.clicked.connect(self._set_output_from_palette)
        grid_and_arrow.addWidget(self.btn_output_preview)
        grid_and_arrow.addStretch()

        g_vbox.addLayout(grid_and_arrow)

        pat_label = QLabel("⚡ Remplir un Patron de Craft Rapide avec l'ingrédient actif :")
        pat_label.setStyleSheet("color: #93c5fd; font-weight: bold; margin-top: 4px;")
        g_vbox.addWidget(pat_label)

        pat_row = QHBoxLayout()
        pat_row.setSpacing(4)
        for plbl, pkey in [
            ("⚔️ Épée", "sword"),
            ("⛏️ Pioche", "pickaxe"),
            ("🪓 Hache", "axe"),
            ("🧱 Bloc 3×3", "block9"),
            ("⭕ Anneau", "ring8"),
            ("🧹 Vider", "clear"),
        ]:
            pb = QPushButton(plbl)
            pb.clicked.connect(lambda checked, k=pkey: self._apply_craft_pattern(k))
            pat_row.addWidget(pb)
        g_vbox.addLayout(pat_row)

        col_right.addWidget(grp_grid)
        col_right.addStretch()
        layout.addLayout(col_right, 1)
        return tab

    # =========================================================================
    # ONGLET 2 : GÉNÉRATEUR DE MINERAIS (REGISTER_ORE) & SPAWNERS DE MOBS (ABM)
    # =========================================================================
    def _build_worldgen_spawner_tab(self) -> QWidget:
        tab = QFrame()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        grp_ore = QGroupBox("💎 1. Générateur de Filons de Minerais Souterrains (register_ore)")
        ore_lay = QVBoxLayout(grp_ore)

        self.ores_list = QListWidget()
        self.ores_list.setMaximumHeight(120)
        self.ores_list.currentRowChanged.connect(self._on_ore_row_selected)
        ore_lay.addWidget(self.ores_list)

        ore_form = QFormLayout()
        self.inp_ore_node = QLineEdit(f"{self.mod_name}:cristal_azur")
        ore_form.addRow("Bloc Minerai à générer :", self.inp_ore_node)

        self.combo_ore_wherein = QComboBox()
        self.combo_ore_wherein.addItems(["default:stone", "default:desert_stone", "default:sand", "default:dirt"])
        ore_form.addRow("Roche Hôte (wherein) :", self.combo_ore_wherein)

        self.combo_ore_type = QComboBox()
        self.combo_ore_type.addItem("Scatter (Filons dispersés classiques)", "scatter")
        self.combo_ore_type.addItem("Blob (Amas sphérique dense)", "blob")
        ore_form.addRow("Type de Filon :", self.combo_ore_type)

        self_scarcity = QSpinBox()
        self_scarcity.setRange(4, 32)
        self_scarcity.setValue(9)
        self_scarcity.setSuffix(" blocs (N×N×N)")
        self.spn_ore_scarcity = self_scarcity
        ore_form.addRow("Rareté (scarcity) :", self.spn_ore_scarcity)

        self.spn_ore_num = QSpinBox()
        self.spn_ore_num.setRange(1, 32)
        self.spn_ore_num.setValue(5)
        ore_form.addRow("Blocs par filon :", self.spn_ore_num)

        y_row = QHBoxLayout()
        self.spn_ore_ymin = QSpinBox()
        self.spn_ore_ymin.setRange(-31000, 500)
        self.spn_ore_ymin.setValue(-512)
        self.spn_ore_ymax = QSpinBox()
        self.spn_ore_ymax.setRange(-31000, 500)
        self.spn_ore_ymax.setValue(-12)
        y_row.addWidget(QLabel("Min Y:"))
        y_row.addWidget(self.spn_ore_ymin)
        y_row.addWidget(QLabel("Max Y:"))
        y_row.addWidget(self.spn_ore_ymax)
        ore_form.addRow("Profondeur (Altitude) :", y_row)

        ore_lay.addLayout(ore_form)

        ore_btns = QHBoxLayout()
        btn_add_ore = QPushButton("➕ Ajouter Filon Minerai")
        btn_add_ore.setObjectName("PrimaryButton")
        btn_add_ore.clicked.connect(self._add_ore_rule)
        btn_upd_ore = QPushButton("✏️ Mettre à jour")
        btn_upd_ore.clicked.connect(self._update_ore_rule)
        btn_del_ore = QPushButton("🗑️ Supprimer")
        btn_del_ore.setObjectName("DangerButton")
        btn_del_ore.clicked.connect(self._delete_ore_rule)
        ore_btns.addWidget(btn_add_ore)
        ore_btns.addWidget(btn_upd_ore)
        ore_btns.addWidget(btn_del_ore)
        ore_lay.addLayout(ore_btns)
        ore_lay.addStretch()

        layout.addWidget(grp_ore, 1)

        grp_mob = QGroupBox("🐺 2. Apparition Naturelle des Mobs dans le Monde (ABM Spawner)")
        mob_lay = QVBoxLayout(grp_mob)

        self.spawns_list = QListWidget()
        self.spawns_list.setMaximumHeight(120)
        self.spawns_list.currentRowChanged.connect(self._on_spawn_row_selected)
        mob_lay.addWidget(self.spawns_list)

        mob_form = QFormLayout()
        self.inp_spawn_mob = QLineEdit(f"{self.mod_name}:renard_bleu")
        mob_form.addRow("ID du Mob à faire apparaître :", self.inp_spawn_mob)

        self.combo_spawn_node = QComboBox()
        self.combo_spawn_node.addItems([
            "default:dirt_with_grass",
            "default:stone",
            "default:sand",
            "default:snowblock",
            "default:dirt_with_dry_grass",
        ])
        mob_form.addRow("Bloc de Sol d'apparition :", self.combo_spawn_node)

        self.spn_spawn_interval = QSpinBox()
        self.spn_spawn_interval.setRange(5, 600)
        self.spn_spawn_interval.setValue(30)
        self.spn_spawn_interval.setSuffix(" sec")
        mob_form.addRow("Intervalle ABM :", self.spn_spawn_interval)

        self.spn_spawn_chance = QSpinBox()
        self.spn_spawn_chance.setRange(1, 5000)
        self.spn_spawn_chance.setValue(45)
        mob_form.addRow("Probabilité (1 chance sur N) :", self.spn_spawn_chance)

        my_row = QHBoxLayout()
        self.spn_spawn_ymin = QSpinBox()
        self.spn_spawn_ymin.setRange(-31000, 1000)
        self.spn_spawn_ymin.setValue(-5)
        self.spn_spawn_ymax = QSpinBox()
        self.spn_spawn_ymax.setRange(-31000, 1000)
        self.spn_spawn_ymax.setValue(180)
        my_row.addWidget(QLabel("Min Y:"))
        my_row.addWidget(self.spn_spawn_ymin)
        my_row.addWidget(QLabel("Max Y:"))
        my_row.addWidget(self.spn_spawn_ymax)
        mob_form.addRow("Altitude d'apparition :", my_row)

        mob_lay.addLayout(mob_form)

        mob_btns = QHBoxLayout()
        btn_add_sp = QPushButton("➕ Ajouter Spawner Mob")
        btn_add_sp.setObjectName("PrimaryButton")
        btn_add_sp.clicked.connect(self._add_spawn_rule)
        btn_upd_sp = QPushButton("✏️ Mettre à jour")
        btn_upd_sp.clicked.connect(self._update_spawn_rule)
        btn_del_sp = QPushButton("🗑️ Supprimer")
        btn_del_sp.setObjectName("DangerButton")
        btn_del_sp.clicked.connect(self._delete_spawn_rule)
        mob_btns.addWidget(btn_add_sp)
        mob_btns.addWidget(btn_upd_sp)
        mob_btns.addWidget(btn_del_sp)
        mob_lay.addLayout(mob_btns)
        mob_lay.addStretch()

        layout.addWidget(grp_mob, 1)
        return tab

    # =========================================================================
    # ONGLET 3 : STUDIO D'EFFETS DE PARTICULES TEMPS RÉEL
    # =========================================================================
    def _build_particles_tab(self) -> QWidget:
        tab = QFrame()
        layout = QHBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        left_box = QGroupBox("✨ Paramètres de l'Émetteur de Particules (ABM / Bloc / Entité)")
        l_lay = QVBoxLayout(left_box)

        self.particles_list = QListWidget()
        self.particles_list.setMaximumHeight(105)
        self.particles_list.currentRowChanged.connect(self._on_particle_row_selected)
        l_lay.addWidget(self.particles_list)

        p_form = QFormLayout()
        self.inp_part_name = QLineEdit("aura_cristal_azur")
        p_form.addRow("Nom de l'effet :", self.inp_part_name)

        self.inp_part_target = QLineEdit(f"{self.mod_name}:cristal_azur")
        p_form.addRow("Bloc / Nœud émetteur :", self.inp_part_target)

        preset_row = QHBoxLayout()
        for lbl, col_h, spd, glw in [
            ("💠 Aura Bleue", "#38bdf8", 1.6, 14),
            ("🔥 Flammes", "#f97316", 2.4, 14),
            ("💜 Portail", "#c084fc", 1.2, 13),
            ("💨 Fumée", "#94a3b8", 1.9, 0),
        ]:
            b = QPushButton(lbl)
            b.clicked.connect(lambda checked, c=col_h, s=spd, g=glw: self._apply_particle_preset(c, s, g))
            preset_row.addWidget(b)
        p_form.addRow("Preset Rapide :", preset_row)

        self.btn_part_color = QPushButton("🎨 Couleur Particule (#38bdf8)")
        self.btn_part_color.setStyleSheet("background-color: #38bdf8; color: #0f172a; font-weight: bold;")
        self.btn_part_color.clicked.connect(self._pick_particle_color)
        p_form.addRow("Couleur :", self.btn_part_color)

        self.spn_part_amount = QSpinBox()
        self.spn_part_amount.setRange(4, 120)
        self.spn_part_amount.setValue(22)
        self.spn_part_amount.valueChanged.connect(self._on_particle_live_edited)
        p_form.addRow("Quantité (amount) :", self.spn_part_amount)

        self.spn_part_speed = QDoubleSpinBox()
        self.spn_part_speed.setRange(-5.0, 8.0)
        self.spn_part_speed.setSingleStep(0.2)
        self.spn_part_speed.setValue(1.6)
        self.spn_part_speed.valueChanged.connect(self._on_particle_live_edited)
        p_form.addRow("Vitesse Verticale Y :", self.spn_part_speed)

        self.spn_part_spread = QDoubleSpinBox()
        self.spn_part_spread.setRange(0.1, 3.0)
        self.spn_part_spread.setSingleStep(0.1)
        self.spn_part_spread.setValue(0.65)
        self.spn_part_spread.valueChanged.connect(self._on_particle_live_edited)
        p_form.addRow("Rayon de dispersion :", self.spn_part_spread)

        self.spn_part_glow = QSpinBox()
        self.spn_part_glow.setRange(0, 14)
        self.spn_part_glow.setValue(14)
        self.spn_part_glow.valueChanged.connect(self._on_particle_live_edited)
        p_form.addRow("Luminosité (Glow 0-14) :", self.spn_part_glow)

        l_lay.addLayout(p_form)

        p_btns = QHBoxLayout()
        btn_add_p = QPushButton("➕ Ajouter Effet")
        btn_add_p.setObjectName("PrimaryButton")
        btn_add_p.clicked.connect(self._add_particle_effect)
        btn_del_p = QPushButton("🗑️ Supprimer")
        btn_del_p.setObjectName("DangerButton")
        btn_del_p.clicked.connect(self._delete_particle_effect)
        p_btns.addWidget(btn_add_p)
        p_btns.addWidget(btn_del_p)
        l_lay.addLayout(p_btns)
        l_lay.addStretch()

        layout.addWidget(left_box, 1)

        right_box = QGroupBox("🎬 Simulateur Temps Réel des Particules (30 FPS)")
        r_lay = QVBoxLayout(right_box)
        self.particle_canvas = LiveParticlePreviewWidget(self)
        r_lay.addWidget(self.particle_canvas, 1)
        layout.addWidget(right_box, 1)

        return tab

    # =========================================================================
    # LOGIQUE : RECETTES DE CRAFT 3×3
    # =========================================================================
    def _refresh_ingredient_palette(self):
        search_q = self.inp_search_ing.text().strip().lower() if hasattr(self, "inp_search_ing") else ""
        self.palette_list.blockSignals(True)
        self.palette_list.clear()

        all_items = self._custom_mod_items + STANDARD_CRAFT_ITEMS
        for item_id, label, hex_col in all_items:
            if search_q and (search_q not in label.lower() and search_q not in item_id.lower()):
                continue
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, item_id)
            it.setForeground(QBrush(QColor(hex_col if item_id else "#94a3b8")))
            self.palette_list.addItem(it)

        self.palette_list.blockSignals(False)

    def _on_palette_ingredient_selected(self, row: int):
        it = self.palette_list.item(row)
        if it is not None:
            self.selected_palette_item = it.data(Qt.ItemDataRole.UserRole)

    def _refresh_recipes_list(self):
        self.recipes_list.blockSignals(True)
        self.recipes_list.clear()
        for r in self.recipes:
            self.recipes_list.addItem(QListWidgetItem(f"[{r.recipe_type}] {r.name}  ➔  {r.output_item} x{r.output_count}"))
        if 0 <= self.current_recipe_idx < len(self.recipes):
            self.recipes_list.setCurrentRow(self.current_recipe_idx)
        self.recipes_list.blockSignals(False)

    def _current_recipe(self) -> Optional[CraftRecipeDef]:
        if 0 <= self.current_recipe_idx < len(self.recipes):
            return self.recipes[self.current_recipe_idx]
        return None

    def _load_recipe_into_grid(self, row: int):
        if not (0 <= row < len(self.recipes)):
            return
        self.current_recipe_idx = row
        r = self.recipes[row]
        self._updating_ui = True
        self.inp_recipe_name.setText(r.name)
        for i in range(self.combo_recipe_type.count()):
            if self.combo_recipe_type.itemData(i) == r.recipe_type:
                self.combo_recipe_type.setCurrentIndex(i)
                break
        self.inp_output_item.setText(r.output_item)
        self.spn_output_qty.setValue(r.output_count)
        self.spn_cooktime.setValue(r.cooktime)
        self._updating_ui = False
        self._refresh_grid_buttons_ui()

    def _refresh_grid_buttons_ui(self):
        r = self._current_recipe()
        if not r:
            return
        while len(r.grid) < 9:
            r.grid.append("")
        for idx, btn in enumerate(self.slot_buttons):
            val = r.grid[idx]
            if not val:
                btn.setText("⬛\nVide")
                btn.setStyleSheet("background-color: #11151e; color: #64748b; border: 1px dashed #334155; font-size: 11px;")
            else:
                short = val.split(":")[-1]
                btn.setText(f"🧩\n{short[:12]}")
                btn.setToolTip(val)
                btn.setStyleSheet(
                    "background-color: #1e293b; color: #38bdf8; border: 2px solid #2563eb; font-weight: bold; font-size: 11px;"
                )
        short_out = r.output_item.split(":")[-1]
        self.btn_output_preview.setText(f"🎁 Résultat :\n{short_out}\nx{r.output_count}")

    def _on_craft_slot_left_clicked(self, slot_idx: int):
        r = self._current_recipe()
        if not r:
            return
        r.grid[slot_idx] = self.selected_palette_item
        self._refresh_grid_buttons_ui()
        self._compile_all_bonus_lua()

    def _on_craft_slot_right_clicked(self, slot_idx: int):
        r = self._current_recipe()
        if not r:
            return
        r.grid[slot_idx] = ""
        self._refresh_grid_buttons_ui()
        self._compile_all_bonus_lua()

    def _set_output_from_palette(self):
        if self.selected_palette_item:
            self.inp_output_item.setText(self.selected_palette_item)
            self._on_recipe_meta_changed()

    def _apply_craft_pattern(self, pattern_key: str):
        r = self._current_recipe()
        if not r:
            return
        ing = self.selected_palette_item or "default:diamond"
        stick = "default:stick"
        if pattern_key == "clear":
            r.grid = [""] * 9
        elif pattern_key == "sword":
            r.grid = ["", ing, "", "", ing, "", "", stick, ""]
        elif pattern_key == "pickaxe":
            r.grid = [ing, ing, ing, "", stick, "", "", stick, ""]
        elif pattern_key == "axe":
            r.grid = [ing, ing, "", ing, stick, "", "", stick, ""]
        elif pattern_key == "block9":
            r.grid = [ing] * 9
        elif pattern_key == "ring8":
            r.grid = [ing, ing, ing, ing, "", ing, ing, ing, ing]
        self._refresh_grid_buttons_ui()
        self._compile_all_bonus_lua()

    def _on_recipe_meta_changed(self):
        if self._updating_ui:
            return
        r = self._current_recipe()
        if not r:
            return
        r.name = self.inp_recipe_name.text().strip() or r.name
        r.recipe_type = self.combo_recipe_type.currentData() or "shaped"
        r.output_item = self.inp_output_item.text().strip() or f"{self.mod_name}:item"
        r.output_count = self.spn_output_qty.value()
        r.cooktime = self.spn_cooktime.value()
        self._refresh_recipes_list()
        self._refresh_grid_buttons_ui()
        self._compile_all_bonus_lua()

    def _create_new_recipe(self):
        idx = len(self.recipes) + 1
        self.recipes.append(
            CraftRecipeDef(
                name=f"recette_{idx}",
                recipe_type="shaped",
                output_item=f"{self.mod_name}:item_{idx}",
                output_count=1,
            )
        )
        self.current_recipe_idx = len(self.recipes) - 1
        self._refresh_recipes_list()
        self._load_recipe_into_grid(self.current_recipe_idx)
        self._compile_all_bonus_lua()

    def _delete_current_recipe(self):
        if len(self.recipes) <= 1:
            return
        if 0 <= self.current_recipe_idx < len(self.recipes):
            del self.recipes[self.current_recipe_idx]
            self.current_recipe_idx = max(0, self.current_recipe_idx - 1)
            self._refresh_recipes_list()
            self._load_recipe_into_grid(self.current_recipe_idx)
            self._compile_all_bonus_lua()

    # =========================================================================
    # LOGIQUE : MINERAIS SOUTERRAINS & SPAWNERS DE MOBS
    # =========================================================================
    def _refresh_ores_list(self):
        self.ores_list.blockSignals(True)
        self.ores_list.clear()
        for o in self.ore_rules:
            self.ores_list.addItem(
                QListWidgetItem(f"💎 {o.ore_node} dans {o.wherein_node} (Y: {o.y_min}..{o.y_max}, Rareté: {o.scarcity_dim}³)")
            )
        self.ores_list.blockSignals(False)

    def _on_ore_row_selected(self, row: int):
        if 0 <= row < len(self.ore_rules):
            o = self.ore_rules[row]
            self.inp_ore_node.setText(o.ore_node)
            self.combo_ore_wherein.setCurrentText(o.wherein_node)
            self.spn_ore_scarcity.setValue(o.scarcity_dim)
            self.spn_ore_num.setValue(o.clust_num_ores)
            self.spn_ore_ymin.setValue(o.y_min)
            self.spn_ore_ymax.setValue(o.y_max)

    def _add_ore_rule(self):
        node = self.inp_ore_node.text().strip() or f"{self.mod_name}:cristal_azur"
        self.ore_rules.append(
            OreGenRule(
                name=f"ore_{len(self.ore_rules)+1}",
                ore_node=node,
                wherein_node=self.combo_ore_wherein.currentText(),
                ore_type=self.combo_ore_type.currentData() or "scatter",
                scarcity_dim=self.spn_ore_scarcity.value(),
                clust_num_ores=self.spn_ore_num.value(),
                clust_size=3,
                y_min=min(self.spn_ore_ymin.value(), self.spn_ore_ymax.value()),
                y_max=max(self.spn_ore_ymin.value(), self.spn_ore_ymax.value()),
            )
        )
        self._refresh_ores_list()
        self._compile_all_bonus_lua()

    def _update_ore_rule(self):
        row = self.ores_list.currentRow()
        if 0 <= row < len(self.ore_rules):
            o = self.ore_rules[row]
            o.ore_node = self.inp_ore_node.text().strip() or o.ore_node
            o.wherein_node = self.combo_ore_wherein.currentText()
            o.ore_type = self.combo_ore_type.currentData() or "scatter"
            o.scarcity_dim = self.spn_ore_scarcity.value()
            o.clust_num_ores = self.spn_ore_num.value()
            o.y_min = min(self.spn_ore_ymin.value(), self.spn_ore_ymax.value())
            o.y_max = max(self.spn_ore_ymin.value(), self.spn_ore_ymax.value())
            self._refresh_ores_list()
            self._compile_all_bonus_lua()

    def _delete_ore_rule(self):
        row = self.ores_list.currentRow()
        if 0 <= row < len(self.ore_rules):
            del self.ore_rules[row]
            self._refresh_ores_list()
            self._compile_all_bonus_lua()

    def _refresh_spawns_list(self):
        self.spawns_list.blockSignals(True)
        self.spawns_list.clear()
        for m in self.mob_spawn_rules:
            self.spawns_list.addItem(
                QListWidgetItem(f"🐺 {m.mob_id} sur {m.spawn_on_node} (Toutes les {m.interval_sec}s, 1/{m.chance_inv})")
            )
        self.spawns_list.blockSignals(False)

    def _on_spawn_row_selected(self, row: int):
        if 0 <= row < len(self.mob_spawn_rules):
            m = self.mob_spawn_rules[row]
            self.inp_spawn_mob.setText(m.mob_id)
            self.combo_spawn_node.setCurrentText(m.spawn_on_node)
            self.spn_spawn_interval.setValue(m.interval_sec)
            self.spn_spawn_chance.setValue(m.chance_inv)
            self.spn_spawn_ymin.setValue(m.min_height)
            self.spn_spawn_ymax.setValue(m.max_height)

    def _add_spawn_rule(self):
        mob_id = self.inp_spawn_mob.text().strip() or f"{self.mod_name}:renard_bleu"
        self.mob_spawn_rules.append(
            MobSpawnRule(
                name=f"spawn_{len(self.mob_spawn_rules)+1}",
                mob_id=mob_id,
                spawn_on_node=self.combo_spawn_node.currentText(),
                interval_sec=self.spn_spawn_interval.value(),
                chance_inv=self.spn_spawn_chance.value(),
                min_height=min(self.spn_spawn_ymin.value(), self.spn_spawn_ymax.value()),
                max_height=max(self.spn_spawn_ymin.value(), self.spn_spawn_ymax.value()),
            )
        )
        self._refresh_spawns_list()
        self._compile_all_bonus_lua()

    def _update_spawn_rule(self):
        row = self.spawns_list.currentRow()
        if 0 <= row < len(self.mob_spawn_rules):
            m = self.mob_spawn_rules[row]
            m.mob_id = self.inp_spawn_mob.text().strip() or m.mob_id
            m.spawn_on_node = self.combo_spawn_node.currentText()
            m.interval_sec = self.spn_spawn_interval.value()
            m.chance_inv = self.spn_spawn_chance.value()
            m.min_height = min(self.spn_spawn_ymin.value(), self.spn_spawn_ymax.value())
            m.max_height = max(self.spn_spawn_ymin.value(), self.spn_spawn_ymax.value())
            self._refresh_spawns_list()
            self._compile_all_bonus_lua()

    def _delete_spawn_rule(self):
        row = self.spawns_list.currentRow()
        if 0 <= row < len(self.mob_spawn_rules):
            del self.mob_spawn_rules[row]
            self._refresh_spawns_list()
            self._compile_all_bonus_lua()

    # =========================================================================
    # LOGIQUE : STUDIO DE PARTICULES TEMPS RÉEL
    # =========================================================================
    def _refresh_particles_list(self):
        self.particles_list.blockSignals(True)
        self.particles_list.clear()
        for p in self.particle_effects:
            self.particles_list.addItem(
                QListWidgetItem(f"✨ {p.name} -> {p.target_node_or_id} ({p.color_hex}, {p.amount} part.)")
            )
        if self.particle_effects:
            self.particles_list.setCurrentRow(0)
            self.particle_canvas.set_effect(self.particle_effects[0])
        self.particles_list.blockSignals(False)

    def _current_particle(self) -> Optional[ParticleEffectDef]:
        row = self.particles_list.currentRow()
        if 0 <= row < len(self.particle_effects):
            return self.particle_effects[row]
        return self.particle_effects[0] if self.particle_effects else None

    def _on_particle_row_selected(self, row: int):
        if 0 <= row < len(self.particle_effects):
            p = self.particle_effects[row]
            self._updating_ui = True
            self.inp_part_name.setText(p.name)
            self.inp_part_target.setText(p.target_node_or_id)
            self.btn_part_color.setText(f"🎨 Couleur Particule ({p.color_hex})")
            self.btn_part_color.setStyleSheet(
                f"background-color: {p.color_hex}; color: #0f172a; font-weight: bold;"
            )
            self.spn_part_amount.setValue(p.amount)
            self.spn_part_speed.setValue(p.speed_y)
            self.spn_part_spread.setValue(p.spread_radius)
            self.spn_part_glow.setValue(p.glow)
            self._updating_ui = False
            self.particle_canvas.set_effect(p)

    def _apply_particle_preset(self, col_hex: str, speed_y: float, glow: int):
        p = self._current_particle()
        if not p:
            return
        p.color_hex = col_hex
        p.speed_y = speed_y
        p.glow = glow
        self._on_particle_row_selected(self.particles_list.currentRow())
        self._compile_all_bonus_lua()

    def _pick_particle_color(self):
        p = self._current_particle()
        if not p:
            return
        col = QColorDialog.getColor(QColor(p.color_hex), self, "Couleur des Particules")
        if col.isValid():
            p.color_hex = col.name()
            self.btn_part_color.setText(f"🎨 Couleur Particule ({p.color_hex})")
            self.btn_part_color.setStyleSheet(
                f"background-color: {p.color_hex}; color: #ffffff; font-weight: bold;"
            )
            self.particle_canvas.set_effect(p)
            self._refresh_particles_list()
            self._compile_all_bonus_lua()

    def _on_particle_live_edited(self):
        if self._updating_ui:
            return
        p = self._current_particle()
        if not p:
            return
        p.name = self.inp_part_name.text().strip() or p.name
        p.target_node_or_id = self.inp_part_target.text().strip() or p.target_node_or_id
        p.amount = self.spn_part_amount.value()
        p.speed_y = self.spn_part_speed.value()
        p.spread_radius = self.spn_part_spread.value()
        p.glow = self.spn_part_glow.value()
        self.particle_canvas.set_effect(p)
        self._compile_all_bonus_lua()

    def _add_particle_effect(self):
        idx = len(self.particle_effects) + 1
        self.particle_effects.append(
            ParticleEffectDef(
                name=f"effet_particule_{idx}",
                target_node_or_id=self.inp_part_target.text().strip() or f"{self.mod_name}:cristal_azur",
                color_hex="#38bdf8",
                amount=self.spn_part_amount.value(),
                speed_y=self.spn_part_speed.value(),
                spread_radius=self.spn_part_spread.value(),
                glow=self.spn_part_glow.value(),
            )
        )
        self._refresh_particles_list()
        self._compile_all_bonus_lua()

    def _delete_particle_effect(self):
        row = self.particles_list.currentRow()
        if 0 <= row < len(self.particle_effects):
            del self.particle_effects[row]
            self._refresh_particles_list()
            self._compile_all_bonus_lua()

    # =========================================================================
    # COMPILATEUR LUA COMPLET (CRAFTS + MINERAIS + SPAWNERS + PARTICULES)
    # =========================================================================
    def generate_lua_code(self) -> str:
        lines = [
            "-- ============================================================================",
            "-- MODULE BONUS LUANTI STUDIO : CRAFTS 3x3, MINERAIS, SPAWNERS & PARTICULES",
            "-- ============================================================================",
        ]

        if self.recipes:
            lines.append("\n-- 1. RECETTES DE CRAFT (Grille 3x3, Shapeless, Fourneau & Carburant)")
            for r in self.recipes:
                out_str = f"{r.output_item} {r.output_count}" if r.output_count > 1 else r.output_item
                if r.recipe_type == "shaped":
                    g = (r.grid + [""] * 9)[:9]
                    lines.extend([
                        "minetest.register_craft({",
                        f'    output = "{out_str}",',
                        "    recipe = {",
                        f'        {{"{g[0]}", "{g[1]}", "{g[2]}"}},',
                        f'        {{"{g[3]}", "{g[4]}", "{g[5]}"}},',
                        f'        {{"{g[6]}", "{g[7]}", "{g[8]}"}},',
                        "    },",
                        "})",
                    ])
                elif r.recipe_type == "shapeless":
                    non_empty = [f'"{it}"' for it in r.grid if it.strip()]
                    if non_empty:
                        lines.extend([
                            "minetest.register_craft({",
                            '    type = "shapeless",',
                            f'    output = "{out_str}",',
                            f"    recipe = {{{', '.join(non_empty)}}},",
                            "})",
                        ])
                elif r.recipe_type == "cooking":
                    first_ing = next((it for it in r.grid if it.strip()), "default:cobble")
                    lines.extend([
                        "minetest.register_craft({",
                        '    type = "cooking",',
                        f'    output = "{out_str}",',
                        f'    recipe = "{first_ing}",',
                        f"    cooktime = {r.cooktime},",
                        "})",
                    ])
                elif r.recipe_type == "fuel":
                    first_ing = next((it for it in r.grid if it.strip()), r.output_item)
                    lines.extend([
                        "minetest.register_craft({",
                        '    type = "fuel",',
                        f'    recipe = "{first_ing}",',
                        f"    burntime = {r.cooktime},",
                        "})",
                    ])

        if self.ore_rules:
            lines.append("\n-- 2. GÉNÉRATION NATURELLE DE MINERAIS SOUTERRAINS (register_ore)")
            for o in self.ore_rules:
                sc = max(4, o.scarcity_dim)
                lines.extend([
                    "minetest.register_ore({",
                    f'    ore_type = "{o.ore_type}",',
                    f'    ore = "{o.ore_node}",',
                    f'    wherein = "{o.wherein_node}",',
                    f"    clust_scarcity = {sc} * {sc} * {sc},",
                    f"    clust_num_ores = {o.clust_num_ores},",
                    f"    clust_size = {o.clust_size},",
                    f"    y_min = {o.y_min},",
                    f"    y_max = {o.y_max},",
                    "})",
                ])

        if self.mob_spawn_rules:
            lines.append("\n-- 3. APPARITION NATURELLE DES MOBS DANS LE MONDE (ABM)")
            for m in self.mob_spawn_rules:
                lines.extend([
                    "minetest.register_abm({",
                    f'    label = "Spawn {m.mob_id}",',
                    f'    nodenames = {{"{m.spawn_on_node}"}},',
                    '    neighbors = {"air"},',
                    f"    interval = {m.interval_sec},",
                    f"    chance = {m.chance_inv},",
                    "    catch_up = false,",
                    "    action = function(pos, node)",
                    f"        if pos.y < {m.min_height} or pos.y > {m.max_height} then return end",
                    "        local above = {x = pos.x, y = pos.y + 1, z = pos.z}",
                    "        local n_above = minetest.get_node_or_nil(above)",
                    '        if n_above and n_above.name == "air" then',
                    "            local count = 0",
                    "            for _, obj in ipairs(minetest.get_objects_inside_radius(pos, 24)) do",
                    "                local ent = obj:get_luaentity()",
                    f'                if ent and ent.name == "{m.mob_id}" then count = count + 1 end',
                    "            end",
                    "            if count < 4 then",
                    f'                minetest.add_entity({{x = pos.x, y = pos.y + 1.2, z = pos.z}}, "{m.mob_id}")',
                    "            end",
                    "        end",
                    "    end,",
                    "})",
                ])

        if self.particle_effects:
            lines.append("\n-- 4. ÉMETTEURS DE PARTICULES AMBIANTES (ABM Particle Spawners)")
            for p in self.particle_effects:
                r = p.spread_radius
                lines.extend([
                    "minetest.register_abm({",
                    f'    label = "Particules {p.name}",',
                    f'    nodenames = {{"{p.target_node_or_id}"}},',
                    "    interval = 2,",
                    "    chance = 1,",
                    "    catch_up = false,",
                    "    action = function(pos)",
                    "        minetest.add_particlespawner({",
                    f"            amount = {p.amount},",
                    f"            time = {p.duration:.1f},",
                    f"            minpos = {{x = pos.x - {r:.2f}, y = pos.y - 0.2, z = pos.z - {r:.2f}}},",
                    f"            maxpos = {{x = pos.x + {r:.2f}, y = pos.y + 0.8, z = pos.z + {r:.2f}}},",
                    f"            minvel = {{x = -0.3, y = {p.speed_y * 0.6:.2f}, z = -0.3}},",
                    f"            maxvel = {{x = 0.3, y = {p.speed_y * 1.2:.2f}, z = 0.3}},",
                    f"            minsize = {p.min_size:.1f},",
                    f"            maxsize = {p.max_size:.1f},",
                    f"            glow = {p.glow},",
                    f'            texture = "default_mese_crystal_fragment.png^[colorize:{p.color_hex}:200",',
                    "        })",
                    "    end,",
                    "})",
                ])

        return "\n".join(lines)

    def _compile_all_bonus_lua(self):
        code = self.generate_lua_code()
        if hasattr(self, "lua_preview"):
            self.lua_preview.setPlainText(code)
        self.bonusCodeChanged.emit(code)