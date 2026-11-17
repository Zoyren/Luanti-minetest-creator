# -*- coding: utf-8 -*-
"""
modules/shared_subeditors/item_icon_studio_widget.py
Workbench Spécialisé Items, Extrusion 2D->3D & Studio d'Icône d'Inventaire (Tâche 4) :
- Canevas Pixel-Art 2D (16x16 / 32x32) avec 7 Gabarits d'Items RPG prêts à l'emploi
- Extrudeur 2D -> 3D Voxel en 1 clic (Transforme le dessin 2D en modèle 3D Voxel d'épaisseur réglable !)
- Studio d'Icône d'Inventaire 64x64 : Rendu 3D vs Sprite 2D, Angles (Yaw/Pitch/Roll/Zoom), Contour Pixel-Art (Outline) et Rareté
- Calibrage Tenue en Main (Wield View), Capacités d'Outil/Arme (Minage, Durabilité, Portée) et Effets Spéciaux (Projectile, Soin, Pose 3D).
"""

from typing import Optional, Tuple

try:
    from PyQt6.QtCore import Qt, QRectF, QPointF
    from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QImage, QPixmap
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
        QPushButton, QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
        QCheckBox, QGroupBox, QFormLayout, QColorDialog, QFileDialog,
        QScrollArea, QTabWidget
    )
except ImportError:
    from PyQt5.QtCore import Qt, QRectF, QPointF
    from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont, QImage, QPixmap
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
        QPushButton, QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
        QCheckBox, QGroupBox, QFormLayout, QColorDialog, QFileDialog,
        QScrollArea, QTabWidget
    )

from engine.model_loader.model_data import ModelData, ITEM_2D_TEMPLATES
from engine.renderer.panda_viewport import PandaViewport


class Sprite2DPixelCanvas(QWidget):
    """
    Canevas Pixel-Art 2D dédié au dessin de Sprites d'Items (16x16 ou 32x32)
    avec symétrie diagonale/horizontale et extrusion 3D directe.
    """

    def __init__(self, model_data: ModelData, parent_studio: "ItemIconStudioWidget"):
        super().__init__(parent_studio)
        self.model_data = model_data
        self.studio = parent_studio
        self.setMinimumSize(280, 280)
        self.setMouseTracking(True)

        self.tool = "pencil"  # "pencil", "bucket", "eraser", "eyedropper", "lighten", "darken"
        self.mirror_x = False
        self._painting = False
        self._hover_px = (-1, -1)

    def set_model_data(self, model_data: ModelData):
        self.model_data = model_data
        self.update()

    def _grid_rect_and_cell(self) -> Tuple[float, float, float, int, int]:
        img = self.model_data.sprite_2d_image
        gw = max(1, img.width())
        gh = max(1, img.height())
        pad = 16.0
        avail_w = max(64.0, self.width() - 2 * pad)
        avail_h = max(64.0, self.height() - 2 * pad)
        cell = min(avail_w / gw, avail_h / gh)
        ox = (self.width() - gw * cell) * 0.5
        oy = (self.height() - gh * cell) * 0.5
        return ox, oy, cell, gw, gh

    def _screen_to_pixel(self, pos: QPointF) -> Tuple[int, int]:
        ox, oy, cell, gw, gh = self._grid_rect_and_cell()
        px = int((pos.x() - ox) // cell)
        py = int((pos.y() - oy) // cell)
        return px, py

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#10131a"))

        ox, oy, cell, gw, gh = self._grid_rect_and_cell()
        img = self.model_data.sprite_2d_image

        # 1. Damier de transparence + pixels du sprite 2D
        for y in range(gh):
            for x in range(gw):
                r = QRectF(ox + x * cell, oy + y * cell, cell, cell)
                chk = QColor("#1e2330") if (x + y) % 2 == 0 else QColor("#151922")
                painter.fillRect(r, chk)
                col = img.pixelColor(x, y)
                if col.alpha() > 0:
                    painter.fillRect(r, col)

        # 2. Grille Pixel-Art
        painter.setPen(QPen(QColor(255, 255, 255, 26), 1.0))
        for x in range(gw + 1):
            painter.drawLine(int(ox + x * cell), int(oy), int(ox + x * cell), int(oy + gh * cell))
        for y in range(gh + 1):
            painter.drawLine(int(ox), int(oy + y * cell), int(ox + gw * cell), int(oy + y * cell))

        if self.mirror_x:
            mid_x = ox + (gw * 0.5) * cell
            painter.setPen(QPen(QColor("#f43f5e"), 1.8, Qt.PenStyle.DashLine))
            painter.drawLine(int(mid_x), int(oy), int(mid_x), int(oy + gh * cell))

        # 3. Bordure extérieure
        painter.setPen(QPen(QColor("#38bdf8"), 1.8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(ox, oy, gw * cell, gh * cell))

        # 4. Curseur survolé
        hx, hy = self._hover_px
        if 0 <= hx < gw and 0 <= hy < gh:
            painter.setPen(QPen(QColor("#facc15"), 2.0))
            painter.drawRect(QRectF(ox + hx * cell, oy + hy * cell, cell, cell))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            px, py = self._screen_to_pixel(QPointF(event.pos()))
            self._apply_tool(px, py)
            self._painting = True
        elif event.button() == Qt.MouseButton.RightButton:
            px, py = self._screen_to_pixel(QPointF(event.pos()))
            self._apply_tool(px, py, force_erase=True)
            self._painting = True

    def mouseMoveEvent(self, event):
        pos = QPointF(event.pos())
        self._hover_px = self._screen_to_pixel(pos)
        if self._painting:
            if event.buttons() & Qt.MouseButton.RightButton:
                self._apply_tool(*self._hover_px, force_erase=True)
            elif self.tool not in ("bucket", "eyedropper"):
                self._apply_tool(*self._hover_px)
        self.update()

    def mouseReleaseEvent(self, event):
        self._painting = False

    def _apply_tool(self, px: int, py: int, force_erase: bool = False):
        img = self.model_data.sprite_2d_image
        gw, gh = img.width(), img.height()
        if not (0 <= px < gw and 0 <= py < gh):
            return

        if force_erase or self.tool == "eraser":
            img.setPixelColor(px, py, QColor(0, 0, 0, 0))
            if self.mirror_x:
                img.setPixelColor(gw - 1 - px, py, QColor(0, 0, 0, 0))
            self.studio.on_sprite_modified()
            self.update()
            return

        if self.tool == "eyedropper":
            c = img.pixelColor(px, py)
            if c.alpha() > 0:
                self.studio.set_paint_color(c)
            return

        if self.tool == "bucket":
            target = img.pixelColor(px, py).rgba()
            rep = self.studio.paint_color.rgba()
            if target == rep:
                return
            stack = [(px, py)]
            visited = set()
            while stack:
                cx, cy = stack.pop()
                if (cx, cy) in visited or not (0 <= cx < gw and 0 <= cy < gh):
                    continue
                if img.pixelColor(cx, cy).rgba() != target:
                    continue
                visited.add((cx, cy))
                img.setPixelColor(cx, cy, self.studio.paint_color)
                stack.extend([(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)])
        else:
            coords = [(px, py)]
            if self.mirror_x:
                coords.append((gw - 1 - px, py))
            for ux, uy in coords:
                if self.tool == "lighten":
                    cur = img.pixelColor(ux, uy)
                    if cur.alpha() > 0:
                        img.setPixelColor(ux, uy, cur.lighter(115))
                elif self.tool == "darken":
                    cur = img.pixelColor(ux, uy)
                    if cur.alpha() > 0:
                        img.setPixelColor(ux, uy, cur.darker(115))
                else:
                    img.setPixelColor(ux, uy, self.studio.paint_color)

        self.studio.on_sprite_modified()
        self.update()


class InventoryIconPreviewSlot(QWidget):
    """
    Affiche l'aperçu en direct de l'icône d'inventaire (Slot Hotbar 64x64 + Zoom HD 128x128)
    exactement comme dans l'inventaire créatif et la barre d'action de Luanti.
    """

    def __init__(self, model_data: ModelData, parent=None):
        super().__init__(parent)
        self.model_data = model_data
        self.setMinimumHeight(155)

    def set_model_data(self, model_data: ModelData):
        self.model_data = model_data
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.fillRect(self.rect(), QColor("#0d1017"))

        icon_64 = self.model_data.render_isometric_icon(64, draw_egg_badge=False)

        # 1. Grand aperçu 112x112 à gauche
        big_rect = QRectF(18, 18, 116, 116)
        painter.fillRect(big_rect, QColor("#1e293b"))
        painter.setPen(QPen(QColor("#60a5fa"), 2.0))
        painter.drawRect(big_rect)
        scaled_big = icon_64.scaled(
            104, 104,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation
        )
        painter.drawImage(QPointF(big_rect.x() + 6, big_rect.y() + 6), scaled_big)

        # 2. Vrai Slot Hotbar Luanti 64x64 à droite
        slot_rect = QRectF(158, 36, 68, 68)
        painter.fillRect(slot_rect, QColor("#334155"))
        painter.setPen(QPen(QColor("#94a3b8"), 2.0))
        painter.drawRect(slot_rect)
        painter.drawImage(QPointF(slot_rect.x() + 2, slot_rect.y() + 2), icon_64)

        painter.setPen(QColor("#e2e8f0"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(158, 28, "Slot Inventaire (64×64) :")
        painter.setPen(QColor("#38bdf8"))
        mode_lbl = "Sprite 2D Pur" if self.model_data.icon_mode == "2d_sprite" else "Rendu 3D Texturé"
        painter.drawText(158, 124, f"Mode : {mode_lbl}")


class ItemIconStudioWidget(QWidget):
    """
    Atelier Complet pour la création d'Items 2D/3D, l'Extrusion Voxel et le Studio d'Icône d'Inventaire.
    """

    def __init__(self, model_data: Optional[ModelData] = None, parent=None):
        super().__init__(parent)
        self.model_data: Optional[ModelData] = None
        self.paint_color = QColor("#38bdf8")
        self._updating_ui = False
        self._build_ui()
        self.set_model_data(model_data or ModelData("Items"))

    def set_model_data(self, model_data: ModelData):
        if self.model_data is not None:
            try:
                self.model_data.modelChanged.disconnect(self._on_model_or_texture_changed)
                self.model_data.textureChanged.disconnect(self._on_model_or_texture_changed)
            except Exception:
                pass

        self.model_data = model_data
        self.sprite_canvas.set_model_data(model_data)
        self.viewport_3d.set_model_data(model_data)
        self.icon_slot_preview.set_model_data(model_data)

        try:
            self.model_data.modelChanged.connect(self._on_model_or_texture_changed)
            self.model_data.textureChanged.connect(self._on_model_or_texture_changed)
        except Exception:
            pass

        self._sync_ui_from_model()

    def _on_model_or_texture_changed(self):
        self.icon_slot_preview.update()
        self.viewport_3d.update()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # =====================================================================
        # 1. PANNEAU GAUCHE : DESSIN SPRITE 2D + EXTRUDEUR 2D -> 3D VOXEL
        # =====================================================================
        left_panel = QFrame()
        left_panel.setProperty("class", "InspectorPanel")
        left_panel.setMinimumWidth(320)
        left_panel.setMaximumWidth(420)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

        lbl_title = QLabel("🎨 1. Sprite 2D & Extrusion 3D Automatique")
        lbl_title.setStyleSheet("font-weight: bold; color: #60a5fa; font-size: 13px;")
        left_layout.addWidget(lbl_title)

        tpl_row = QHBoxLayout()
        tpl_row.addWidget(QLabel("Gabarit 2D :"))
        self.combo_tpl = QComboBox()
        for tkey, tlabel in ITEM_2D_TEMPLATES:
            self.combo_tpl.addItem(tlabel, tkey)
        tpl_row.addWidget(self.combo_tpl, 1)

        btn_load_tpl = QPushButton("Charger")
        btn_load_tpl.clicked.connect(self._on_load_2d_template)
        tpl_row.addWidget(btn_load_tpl)
        left_layout.addLayout(tpl_row)

        tools_row = QHBoxLayout()
        tools_row.setSpacing(4)
        for lbl, key in [
            ("✏️ Crayon", "pencil"),
            ("🪣 Pot", "bucket"),
            ("☀️ +Clair", "lighten"),
            ("🌙 -Clair", "darken"),
            ("🧪 Pipette", "eyedropper"),
            ("🧽 Gomme", "eraser"),
        ]:
            b = QPushButton(lbl)
            b.clicked.connect(lambda checked, k=key: self._set_2d_tool(k))
            tools_row.addWidget(b)
        left_layout.addLayout(tools_row)

        col_row = QHBoxLayout()
        self.btn_col = QPushButton("🎨 Couleur")
        self.btn_col.clicked.connect(self._pick_color)
        col_row.addWidget(self.btn_col)
        self._update_color_btn()

        for hx in ["#38bdf8", "#facc15", "#f97316", "#ef4444", "#22c55e", "#a855f7", "#f8fafc", "#64748b", "#78350f"]:
            sw = QPushButton()
            sw.setFixedSize(20, 20)
            sw.setStyleSheet(f"background-color: {hx}; border: 1px solid #0f172a; border-radius: 3px;")
            sw.clicked.connect(lambda checked, c=hx: self.set_paint_color(QColor(c)))
            col_row.addWidget(sw)

        self.chk_mirror_2d = QCheckBox("Miroir X")
        self.chk_mirror_2d.toggled.connect(self._on_mirror_2d_toggled)
        col_row.addWidget(self.chk_mirror_2d)
        col_row.addStretch()
        left_layout.addLayout(col_row)

        self.sprite_canvas = Sprite2DPixelCanvas(ModelData("Items"), self)
        left_layout.addWidget(self.sprite_canvas, 1)

        # Boîte d'Extrusion 2D -> 3D Voxel
        grp_extrude = QGroupBox("⚡ Convertir ce Sprite 2D en Modèle 3D Voxel")
        ex_layout = QVBoxLayout(grp_extrude)
        ex_layout.setContentsMargins(8, 8, 8, 8)
        ex_layout.setSpacing(6)

        thick_row = QHBoxLayout()
        thick_row.addWidget(QLabel("Épaisseur 3D (Voxels Z) :"))
        self.spn_extrude_depth = QSpinBox()
        self.spn_extrude_depth.setRange(1, 12)
        self.spn_extrude_depth.setValue(2)
        thick_row.addWidget(self.spn_extrude_depth)

        btn_import_png = QPushButton("📂 Importer PNG 2D")
        btn_import_png.clicked.connect(self._import_sprite_png)
        thick_row.addWidget(btn_import_png)
        ex_layout.addLayout(thick_row)

        btn_extrude = QPushButton("🚀 Extruder le Sprite 2D en Modèle 3D Maintenant !")
        btn_extrude.setObjectName("PrimaryButton")
        btn_extrude.clicked.connect(self._on_extrude_2d_to_3d)
        ex_layout.addWidget(btn_extrude)

        self.lbl_extrude_info = QLabel("Chaque pixel opaque devient un voxel 3D optimisé par Greedy Meshing.")
        self.lbl_extrude_info.setStyleSheet("color: #93c5fd; font-size: 11px;")
        self.lbl_extrude_info.setWordWrap(True)
        ex_layout.addWidget(self.lbl_extrude_info)

        left_layout.addWidget(grp_extrude)
        splitter.addWidget(left_panel)

        # =====================================================================
        # 2. ZONE CENTRALE : APERÇU 3D TEMPS RÉEL (MONDE vs MAIN 1RE PERSONNE)
        # =====================================================================
        center_panel = QFrame()
        center_panel.setProperty("class", "InspectorPanel")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(6, 6, 6, 6)
        center_layout.setSpacing(6)

        vp_bar = QHBoxLayout()
        lbl_vp = QLabel("🗡️ 2. Aperçu 3D de l'Item & Tenue en Main (Wield View)")
        lbl_vp.setStyleSheet("font-weight: bold; color: #60a5fa;")
        vp_bar.addWidget(lbl_vp)
        vp_bar.addStretch()

        vp_bar.addWidget(QLabel("Mode Vue 3D :"))
        self.combo_vp_context = QComboBox()
        self.combo_vp_context.addItems([
            "🤚 Vue Main 1re Personne (Wield View)",
            "🌍 Vue Modèle 3D Complet (Grille)",
            "🎒 Vue Caméra Icône Inventaire",
        ])
        self.combo_vp_context.currentIndexChanged.connect(self._on_vp_context_changed)
        vp_bar.addWidget(self.combo_vp_context)
        center_layout.addLayout(vp_bar)

        self.viewport_3d = PandaViewport(ModelData("Items"), interaction_mode="transform", parent=self)
        self.viewport_3d.preview_context = "wield"
        center_layout.addWidget(self.viewport_3d, 1)

        splitter.addWidget(center_panel)

        # =====================================================================
        # 3. PANNEAU DROIT : STUDIO D'ICÔNE INVENTAIRE & STATS OUTIL/ARME
        # =====================================================================
        right_tabs = QTabWidget()
        right_tabs.setMinimumWidth(330)
        right_tabs.setMaximumWidth(420)

        # --- ONGLET DROIT 1 : STUDIO D'ICÔNE D'INVENTAIRE ---
        icon_scroll = QScrollArea()
        icon_scroll.setWidgetResizable(True)
        icon_scroll.setFrameShape(QFrame.Shape.NoFrame)

        icon_panel = QFrame()
        icon_layout = QVBoxLayout(icon_panel)
        icon_layout.setContentsMargins(8, 8, 8, 8)
        icon_layout.setSpacing(8)

        grp_prev = QGroupBox("🎒 Aperçu En Direct dans le Slot d'Inventaire Luanti")
        prev_lay = QVBoxLayout(grp_prev)
        self.icon_slot_preview = InventoryIconPreviewSlot(ModelData("Items"), self)
        prev_lay.addWidget(self.icon_slot_preview)
        icon_layout.addWidget(grp_prev)

        grp_icfg = QGroupBox("🎥 Réglages de l'Icône d'Inventaire")
        icfg_form = QFormLayout(grp_icfg)
        icfg_form.setSpacing(6)

        self.combo_icon_mode = QComboBox()
        self.combo_icon_mode.addItem("🧊 Rendu 3D Isométrique / Orientable", "3d_render")
        self.combo_icon_mode.addItem("🎨 Sprite 2D Pixel-Art Direct", "2d_sprite")
        self.combo_icon_mode.currentIndexChanged.connect(self._on_icon_settings_changed)
        icfg_form.addRow("Source Icône :", self.combo_icon_mode)

        # Presets d'angles caméra d'icône
        preset_ang_row = QHBoxLayout()
        for lbl, angles in [
            ("⚔️ Arme", (-42.0, 22.0, -25.0, 1.15)),
            ("🧱 Bloc Iso", (-38.0, 25.0, 0.0, 1.0)),
            ("🛡️ Face", (0.0, 8.0, 0.0, 1.1)),
        ]:
            b = QPushButton(lbl)
            b.clicked.connect(lambda checked, a=angles: self._apply_icon_angle_preset(*a))
            preset_ang_row.addWidget(b)
        icfg_form.addRow("Preset Angle :", preset_ang_row)

        self.spn_icon_yaw = QDoubleSpinBox()
        self.spn_icon_yaw.setRange(-180.0, 180.0)
        self.spn_icon_yaw.setSingleStep(5.0)
        self.spn_icon_yaw.valueChanged.connect(self._on_icon_settings_changed)
        icfg_form.addRow("Rotation Yaw (°) :", self.spn_icon_yaw)

        self.spn_icon_pitch = QDoubleSpinBox()
        self.spn_icon_pitch.setRange(-85.0, 85.0)
        self.spn_icon_pitch.setSingleStep(5.0)
        self.spn_icon_pitch.valueChanged.connect(self._on_icon_settings_changed)
        icfg_form.addRow("Inclinaison Pitch (°) :", self.spn_icon_pitch)

        self.spn_icon_roll = QDoubleSpinBox()
        self.spn_icon_roll.setRange(-180.0, 180.0)
        self.spn_icon_roll.setSingleStep(5.0)
        self.spn_icon_roll.valueChanged.connect(self._on_icon_settings_changed)
        icfg_form.addRow("Inclinaison Roll (°) :", self.spn_icon_roll)

        self.spn_icon_zoom = QDoubleSpinBox()
        self.spn_icon_zoom.setRange(0.4, 2.5)
        self.spn_icon_zoom.setSingleStep(0.05)
        self.spn_icon_zoom.setValue(1.0)
        self.spn_icon_zoom.valueChanged.connect(self._on_icon_settings_changed)
        icfg_form.addRow("Zoom Icône :", self.spn_icon_zoom)

        self.chk_icon_outline = QCheckBox("Contour Pixel-Art Automatique (Outline)")
        self.chk_icon_outline.setChecked(True)
        self.chk_icon_outline.toggled.connect(self._on_icon_settings_changed)
        icfg_form.addRow("", self.chk_icon_outline)

        self.btn_outline_col = QPushButton("Couleur du Contour (#0f172a)")
        self.btn_outline_col.clicked.connect(self._pick_outline_color)
        icfg_form.addRow("Contour :", self.btn_outline_col)

        self.combo_rarity = QComboBox()
        self.combo_rarity.addItem("Aucun fond (Transparent)", "none")
        self.combo_rarity.addItem("⚪ Commun (Cadre Ardoise)", "common")
        self.combo_rarity.addItem("🔵 Rare (Cadre Azur)", "rare")
        self.combo_rarity.addItem("🟣 Épique (Cadre Améthyste)", "epic")
        self.combo_rarity.addItem("🟡 Légendaire (Cadre Or Royal)", "legendary")
        self.combo_rarity.currentIndexChanged.connect(self._on_icon_settings_changed)
        icfg_form.addRow("Cadre Rareté :", self.combo_rarity)

        btn_export_icon = QPushButton("💾 Exporter l'Icône 64×64 en PNG")
        btn_export_icon.clicked.connect(self._export_icon_png)
        icfg_form.addRow("", btn_export_icon)

        icon_layout.addWidget(grp_icfg)
        icon_layout.addStretch()
        icon_scroll.setWidget(icon_panel)
        right_tabs.addTab(icon_scroll, "🎒 Icône Inventaire")

        # --- ONGLET DROIT 2 : TENUE EN MAIN (WIELD) & CAPACITÉS D'OUTIL/ARME ---
        wield_scroll = QScrollArea()
        wield_scroll.setWidgetResizable(True)
        wield_scroll.setFrameShape(QFrame.Shape.NoFrame)

        wield_panel = QFrame()
        wield_layout = QVBoxLayout(wield_panel)
        wield_layout.setContentsMargins(8, 8, 8, 8)
        wield_layout.setSpacing(8)

        grp_type = QGroupBox("⚔️ Type d'Item & Tenue en Main (Wield)")
        w_form = QFormLayout(grp_type)
        w_form.setSpacing(6)

        self.combo_item_kind = QComboBox()
        self.combo_item_kind.addItem("⚔️ Arme / Outil (minetest.register_tool)", "tool")
        self.combo_item_kind.addItem("🧪 Objet / Consommable (register_craftitem)", "craftitem")
        self.combo_item_kind.addItem("🏆 Arme/Objet 3D Posable au Sol (Clic Droit)", "placeable_3d")
        self.combo_item_kind.currentIndexChanged.connect(self._on_wield_tool_settings_changed)
        w_form.addRow("Type Luanti :", self.combo_item_kind)

        ws_row = QHBoxLayout()
        self.spn_ws_x = QDoubleSpinBox()
        self.spn_ws_y = QDoubleSpinBox()
        self.spn_ws_z = QDoubleSpinBox()
        for spn, val in [(self.spn_ws_x, 1.45), (self.spn_ws_y, 1.45), (self.spn_ws_z, 1.25)]:
            spn.setRange(0.2, 5.0)
            spn.setSingleStep(0.1)
            spn.setValue(val)
            spn.valueChanged.connect(self._on_wield_tool_settings_changed)
        ws_row.addWidget(QLabel("X:"))
        ws_row.addWidget(self.spn_ws_x)
        ws_row.addWidget(QLabel("Y:"))
        ws_row.addWidget(self.spn_ws_y)
        ws_row.addWidget(QLabel("Z:"))
        ws_row.addWidget(self.spn_ws_z)
        w_form.addRow("Taille Main :", ws_row)

        self.spn_range = QDoubleSpinBox()
        self.spn_range.setRange(2.0, 16.0)
        self.spn_range.setSingleStep(0.5)
        self.spn_range.setValue(4.5)
        self.spn_range.valueChanged.connect(self._on_wield_tool_settings_changed)
        w_form.addRow("Portée (blocs) :", self.spn_range)

        wield_layout.addWidget(grp_type)

        grp_caps = QGroupBox("⛏️ Capacités de Combat & Minage (tool_capabilities)")
        c_form = QFormLayout(grp_caps)
        c_form.setSpacing(6)

        self.spn_item_dmg = QSpinBox()
        self.spn_item_dmg.setRange(1, 500)
        self.spn_item_dmg.setValue(6)
        self.spn_item_dmg.valueChanged.connect(self._on_wield_tool_settings_changed)
        c_form.addRow("Dégâts (fleshy) :", self.spn_item_dmg)

        self.spn_punch_int = QDoubleSpinBox()
        self.spn_punch_int.setRange(0.1, 5.0)
        self.spn_punch_int.setSingleStep(0.05)
        self.spn_punch_int.setValue(0.65)
        self.spn_punch_int.setSuffix(" s")
        self.spn_punch_int.valueChanged.connect(self._on_wield_tool_settings_changed)
        c_form.addRow("Cadence Frappe :", self.spn_punch_int)

        self.spn_uses = QSpinBox()
        self.spn_uses.setRange(1, 10000)
        self.spn_uses.setValue(120)
        self.spn_uses.valueChanged.connect(self._on_wield_tool_settings_changed)
        c_form.addRow("Durabilité (Uses) :", self.spn_uses)

        self.spn_cracky = QSpinBox()
        self.spn_cracky.setRange(0, 3)
        self.spn_cracky.setValue(3)
        self.spn_cracky.valueChanged.connect(self._on_wield_tool_settings_changed)
        c_form.addRow("Minage Pierre (0-3) :", self.spn_cracky)

        self.spn_choppy = QSpinBox()
        self.spn_choppy.setRange(0, 3)
        self.spn_choppy.setValue(2)
        self.spn_choppy.valueChanged.connect(self._on_wield_tool_settings_changed)
        c_form.addRow("Coupe Bois (0-3) :", self.spn_choppy)

        self.spn_snappy = QSpinBox()
        self.spn_snappy.setRange(0, 3)
        self.spn_snappy.setValue(3)
        self.spn_snappy.valueChanged.connect(self._on_wield_tool_settings_changed)
        c_form.addRow("Tranchant Épée (0-3) :", self.spn_snappy)

        self.spn_crumbly = QSpinBox()
        self.spn_crumbly.setRange(0, 3)
        self.spn_crumbly.setValue(1)
        self.spn_crumbly.valueChanged.connect(self._on_wield_tool_settings_changed)
        c_form.addRow("Pelle Terre (0-3) :", self.spn_crumbly)

        wield_layout.addWidget(grp_caps)

        grp_fx = QGroupBox("✨ Pouvoirs Spéciaux (Clic Gauche / Clic Droit)")
        fx_form = QFormLayout(grp_fx)
        fx_form.setSpacing(6)

        self.spn_heal_hp = QSpinBox()
        self.spn_heal_hp.setRange(-100, 100)
        self.spn_heal_hp.setValue(0)
        self.spn_heal_hp.setSuffix(" PV")
        self.spn_heal_hp.valueChanged.connect(self._on_wield_tool_settings_changed)
        fx_form.addRow("Soin au Clic :", self.spn_heal_hp)

        self.chk_projectile = QCheckBox("⚡ Tirer un Projectile Magique au Clic Droit")
        self.chk_projectile.toggled.connect(self._on_wield_tool_settings_changed)
        fx_form.addRow("", self.chk_projectile)

        self.chk_hit_particles = QCheckBox("✨ Émettre des Particules à l'utilisation")
        self.chk_hit_particles.setChecked(True)
        self.chk_hit_particles.toggled.connect(self._on_wield_tool_settings_changed)
        fx_form.addRow("", self.chk_hit_particles)

        wield_layout.addWidget(grp_fx)
        wield_layout.addStretch()
        wield_scroll.setWidget(wield_panel)
        right_tabs.addTab(wield_scroll, "⚔️ Main & Capacités")

        splitter.addWidget(right_tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([350, 680, 360])

        root.addWidget(splitter)

    # =========================================================================
    # LOGIQUE ET SYNCHRONISATION
    # =========================================================================
    def _sync_ui_from_model(self):
        if not self.model_data:
            return
        self._updating_ui = True
        m = self.model_data

        self.combo_icon_mode.setCurrentIndex(1 if m.icon_mode == "2d_sprite" else 0)
        self.spn_icon_yaw.setValue(m.icon_yaw)
        self.spn_icon_pitch.setValue(m.icon_pitch)
        self.spn_icon_roll.setValue(m.icon_roll)
        self.spn_icon_zoom.setValue(m.icon_zoom)
        self.chk_icon_outline.setChecked(m.icon_outline)
        self.btn_outline_col.setText(f"Couleur Contour ({m.icon_outline_color})")

        for i in range(self.combo_rarity.count()):
            if self.combo_rarity.itemData(i) == m.icon_rarity_bg:
                self.combo_rarity.setCurrentIndex(i)
                break

        for i in range(self.combo_item_kind.count()):
            if self.combo_item_kind.itemData(i) == m.item_kind:
                self.combo_item_kind.setCurrentIndex(i)
                break

        self.spn_ws_x.setValue(m.wield_scale[0])
        self.spn_ws_y.setValue(m.wield_scale[1])
        self.spn_ws_z.setValue(m.wield_scale[2])
        self.spn_range.setValue(m.tool_range)
        self.spn_item_dmg.setValue(m.attack_damage)
        self.spn_punch_int.setValue(m.punch_interval)
        self.spn_uses.setValue(m.tool_uses)
        self.spn_cracky.setValue(m.mine_cracky)
        self.spn_choppy.setValue(m.mine_choppy)
        self.spn_snappy.setValue(m.mine_snappy)
        self.spn_crumbly.setValue(m.mine_crumbly)
        self.spn_heal_hp.setValue(m.item_heal_hp)
        self.chk_projectile.setChecked(m.item_shoot_projectile)
        self.chk_hit_particles.setChecked(m.item_hit_particles)

        self._updating_ui = False
        self.icon_slot_preview.update()
        self.sprite_canvas.update()

    def _set_2d_tool(self, tool_key: str):
        self.sprite_canvas.tool = tool_key

    def _on_mirror_2d_toggled(self, checked: bool):
        self.sprite_canvas.mirror_x = checked
        self.sprite_canvas.update()

    def set_paint_color(self, color: QColor):
        if color.isValid():
            self.paint_color = color
            self._update_color_btn()

    def _pick_color(self):
        col = QColorDialog.getColor(self.paint_color, self, "Couleur du Pinceau Sprite 2D")
        if col.isValid():
            self.set_paint_color(col)

    def _update_color_btn(self):
        self.btn_col.setStyleSheet(
            f"background-color: {self.paint_color.name()}; color: #ffffff; font-weight: bold;"
        )

    def on_sprite_modified(self):
        self.icon_slot_preview.update()

    def _on_load_2d_template(self):
        if not self.model_data:
            return
        tkey = self.combo_tpl.currentData() or "sword"
        self.model_data.load_2d_sprite_template(tkey)
        self.sprite_canvas.update()
        self.icon_slot_preview.update()

    def _import_sprite_png(self):
        if not self.model_data:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer un Sprite PNG 2D (16×16 ou 32×32)", "", "Images PNG (*.png)"
        )
        if path:
            img = QImage(path)
            if not img.isNull():
                w = 32 if img.width() > 20 else 16
                self.model_data.sprite_2d_image = img.scaled(
                    w, w,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.FastTransformation
                ).convertToFormat(QImage.Format.Format_ARGB32)
                self.sprite_canvas.update()
                self.icon_slot_preview.update()

    def _on_extrude_2d_to_3d(self):
        if not self.model_data:
            return
        depth = self.spn_extrude_depth.value()
        num_cubes = self.model_data.extrude_2d_sprite_to_3d_voxels(thickness=depth)
        self.lbl_extrude_info.setText(
            f"✅ Extrusion 3D réussie ! {num_cubes} cubes Voxel créés (épaisseur = {depth} voxels)."
        )
        self.viewport_3d.update()
        self.icon_slot_preview.update()

    def _on_vp_context_changed(self, idx: int):
        contexts = ["wield", "world", "inventory"]
        self.viewport_3d.preview_context = contexts[idx] if 0 <= idx < len(contexts) else "wield"
        self.viewport_3d.update()

    def _apply_icon_angle_preset(self, yaw: float, pitch: float, roll: float, zoom: float):
        if not self.model_data:
            return
        self._updating_ui = True
        self.spn_icon_yaw.setValue(yaw)
        self.spn_icon_pitch.setValue(pitch)
        self.spn_icon_roll.setValue(roll)
        self.spn_icon_zoom.setValue(zoom)
        self._updating_ui = False
        self._on_icon_settings_changed()

    def _pick_outline_color(self):
        if not self.model_data:
            return
        col = QColorDialog.getColor(QColor(self.model_data.icon_outline_color), self, "Couleur du Contour d'Icône")
        if col.isValid():
            self.model_data.icon_outline_color = col.name()
            self.btn_outline_col.setText(f"Couleur Contour ({col.name()})")
            self.icon_slot_preview.update()

    def _on_icon_settings_changed(self):
        if self._updating_ui or not self.model_data:
            return
        m = self.model_data
        m.icon_mode = self.combo_icon_mode.currentData() or "3d_render"
        m.icon_yaw = self.spn_icon_yaw.value()
        m.icon_pitch = self.spn_icon_pitch.value()
        m.icon_roll = self.spn_icon_roll.value()
        m.icon_zoom = self.spn_icon_zoom.value()
        m.icon_outline = self.chk_icon_outline.isChecked()
        m.icon_rarity_bg = self.combo_rarity.currentData() or "none"
        self.icon_slot_preview.update()

    def _on_wield_tool_settings_changed(self):
        if self._updating_ui or not self.model_data:
            return
        m = self.model_data
        m.item_kind = self.combo_item_kind.currentData() or "tool"
        m.wield_scale = [self.spn_ws_x.value(), self.spn_ws_y.value(), self.spn_ws_z.value()]
        m.tool_range = self.spn_range.value()
        m.attack_damage = self.spn_item_dmg.value()
        m.punch_interval = self.spn_punch_int.value()
        m.tool_uses = self.spn_uses.value()
        m.mine_cracky = self.spn_cracky.value()
        m.mine_choppy = self.spn_choppy.value()
        m.mine_snappy = self.spn_snappy.value()
        m.mine_crumbly = self.spn_crumbly.value()
        m.item_heal_hp = self.spn_heal_hp.value()
        m.item_shoot_projectile = self.chk_projectile.isChecked()
        m.item_hit_particles = self.chk_hit_particles.isChecked()
        self.viewport_3d.update()

    def _export_icon_png(self):
        if not self.model_data:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter l'Icône d'Inventaire 64×64", f"{self.model_data.name}_icon.png", "Images PNG (*.png)"
        )
        if path:
            self.model_data.render_isometric_icon(64, draw_egg_badge=False).save(path, "PNG")