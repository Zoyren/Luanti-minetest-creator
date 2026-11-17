# -*- coding: utf-8 -*-
"""
modules/shared_subeditors/pixel_art_editor.py
Workbench 2 : Studio de Texture & Peinture 3D Directe relié au Modèle 3D.
- Vue Gauche : Modèle 3D interactif où l'on peint directement sur les faces des cubes
- Vue Droite : Canevas UV 2D affichant le dépliage des 6 faces de chaque cube
"""

from typing import Optional

try:
    from PyQt6.QtCore import Qt, QRectF, QPointF
    from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
        QPushButton, QLabel, QComboBox, QSpinBox, QCheckBox,
        QColorDialog, QFileDialog
    )
except ImportError:
    from PyQt5.QtCore import Qt, QRectF, QPointF
    from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
        QPushButton, QLabel, QComboBox, QSpinBox, QCheckBox,
        QColorDialog, QFileDialog
    )

from engine.model_loader.model_data import ModelData, ModelCube
from engine.renderer.panda_viewport import PandaViewport


FACE_SHORT_TAG = {
    "top": "HAUT",
    "bottom": "BAS",
    "north": "AVANT",
    "south": "ARRIÈRE",
    "east": "DROITE",
    "west": "GAUCHE",
}


class UVAtlas2DCanvas(QWidget):
    """
    Canevas 2D de l'Atlas de Texture avec affichage des patron Box-UV (6 faces par cube),
    zoom/pan et outils de dessin pixel-art synchronisés avec le modèle 3D.
    """

    def __init__(self, model_data: ModelData, parent_editor: "PixelArtEditor"):
        super().__init__(parent_editor)
        self.model_data = model_data
        self.editor = parent_editor
        self.setMinimumSize(360, 320)
        self.setMouseTracking(True)

        self.zoom = 7.0
        self.pan_offset = QPointF(24.0, 24.0)
        self.show_uv_overlay = True
        self.isolate_selected_cube = False

        self._dragging_pan = False
        self._painting_2d = False
        self._last_mouse = QPointF(0, 0)
        self._hover_uv = (-1, -1)

    def set_model_data(self, model_data: ModelData):
        self.model_data = model_data
        self.update()

    def _screen_to_uv(self, pos: QPointF) -> tuple[int, int]:
        u = int((pos.x() - self.pan_offset.x()) / self.zoom)
        v = int((pos.y() - self.pan_offset.y()) / self.zoom)
        return u, v

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#12141a"))

        aw = self.model_data.atlas_width
        ah = self.model_data.atlas_height
        ox, oy = self.pan_offset.x(), self.pan_offset.y()
        z = self.zoom

        # 1. Damier de transparence
        for y in range(ah):
            for x in range(aw):
                if self.isolate_selected_cube and not self._is_texel_in_selected_cube(x, y):
                    continue
                chk = QColor("#1e222d") if (x + y) % 2 == 0 else QColor("#171a22")
                painter.fillRect(QRectF(ox + x * z, oy + y * z, z, z), chk)

        # 2. Rendu des texels de l'atlas
        img = self.model_data.texture_image
        for y in range(ah):
            for x in range(aw):
                if self.isolate_selected_cube and not self._is_texel_in_selected_cube(x, y):
                    continue
                col = img.pixelColor(x, y)
                if col.alpha() > 0:
                    painter.fillRect(QRectF(ox + x * z, oy + y * z, z, z), col)

        # 3. Cadre global de l'atlas
        painter.setPen(QPen(QColor("#475569"), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(ox, oy, aw * z, ah * z))

        # 4. Superposition des 6 faces UV de chaque Cube
        if self.show_uv_overlay:
            font = QFont("Segoe UI", max(7, int(z * 0.9)), QFont.Weight.Bold)
            painter.setFont(font)

            for cube in self.model_data.cubes:
                is_sel = (cube.cube_id == self.model_data.selected_cube_id)
                if self.isolate_selected_cube and not is_sel:
                    continue

                pen_col = QColor("#facc15") if is_sel else QColor(148, 163, 184, 120)
                pen_w = 2.0 if is_sel else 1.0

                for fname, rect in cube.get_face_uv_rects().items():
                    r_scr = QRectF(ox + rect.u * z, oy + rect.v * z, rect.w * z, rect.h * z)
                    painter.setPen(QPen(pen_col, pen_w))
                    painter.drawRect(r_scr)

                    if is_sel and z >= 5.0:
                        painter.setPen(QColor("#ffffff"))
                        painter.drawText(
                            r_scr.adjusted(2, 1, -1, -1),
                            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                            FACE_SHORT_TAG.get(fname, fname)
                        )

        # 5. Surbrillance du pixel survolé en 2D
        hu, hv = self._hover_uv
        if 0 <= hu < aw and 0 <= hv < ah:
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.drawRect(QRectF(ox + hu * z, oy + hv * z, z, z))

    def _is_texel_in_selected_cube(self, u: int, v: int) -> bool:
        cube = self.model_data.get_selected_cube()
        if not cube:
            return True
        for rect in cube.get_face_uv_rects().values():
            if rect.u <= u < rect.u + rect.w and rect.v <= v < rect.v + rect.h:
                return True
        return False

    def _find_cube_and_face_at_uv(self, u: int, v: int) -> tuple[Optional[ModelCube], Optional[str]]:
        for cube in self.model_data.cubes:
            for fname, rect in cube.get_face_uv_rects().items():
                if rect.u <= u < rect.u + rect.w and rect.v <= v < rect.v + rect.h:
                    return cube, fname
        return None, None

    def mousePressEvent(self, event):
        pos = QPointF(event.pos())
        self._last_mouse = pos

        if event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self._dragging_pan = True
            return

        if event.button() == Qt.MouseButton.LeftButton:
            u, v = self._screen_to_uv(pos)
            cube, fname = self._find_cube_and_face_at_uv(u, v)
            if cube:
                self.model_data.select_cube(cube.cube_id)

            if self.editor.current_tool != "eyedropper":
                self.model_data.push_undo_snapshot()
            self._apply_2d_tool(u, v, cube, fname)
            self._painting_2d = True

    def mouseMoveEvent(self, event):
        pos = QPointF(event.pos())
        dx = pos.x() - self._last_mouse.x()
        dy = pos.y() - self._last_mouse.y()
        self._last_mouse = pos

        self._hover_uv = self._screen_to_uv(pos)

        if self._dragging_pan:
            self.pan_offset += QPointF(dx, dy)
            self.update()
        elif self._painting_2d:
            u, v = self._hover_uv
            cube, fname = self._find_cube_and_face_at_uv(u, v)
            if self.editor.current_tool not in ("bucket", "eyedropper"):
                self._apply_2d_tool(u, v, cube, fname)
        else:
            self.update()

    def mouseReleaseEvent(self, event):
        self._dragging_pan = False
        self._painting_2d = False

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 0.86
        self.zoom = max(2.0, min(28.0, self.zoom * factor))
        self.update()

    def _apply_2d_tool(self, u: int, v: int, cube: Optional[ModelCube], fname: Optional[str]):
        if not (0 <= u < self.model_data.atlas_width and 0 <= v < self.model_data.atlas_height):
            return
        tool = self.editor.current_tool
        col = self.editor.active_color
        bsize = self.editor.brush_size

        if tool == "eyedropper":
            picked = self.model_data.texture_image.pixelColor(u, v)
            self.editor.set_active_color(picked)
        elif tool == "bucket" and cube and fname:
            self.model_data.fill_cube_face(cube, fname, col, noise_strength=0)
        elif tool == "noise":
            c = QColor(col)
            delta = ((u * 19 + v * 37) % 25) - 12
            c = c.lighter(100 + delta) if delta >= 0 else c.darker(100 - delta)
            self.model_data.paint_texel(u, v, c, bsize)
        elif tool == "lighten":
            cur = self.model_data.texture_image.pixelColor(u, v)
            self.model_data.paint_texel(u, v, cur.lighter(112), bsize)
        elif tool == "darken":
            cur = self.model_data.texture_image.pixelColor(u, v)
            self.model_data.paint_texel(u, v, cur.darker(112), bsize)
        elif tool == "eraser":
            self.model_data.paint_texel(u, v, QColor(0, 0, 0, 0), bsize)
        else:
            self.model_data.paint_texel(u, v, col, bsize)


class PixelArtEditor(QWidget):
    """
    Atelier 2 : Éditeur de Texture & Peinture 3D directe synchronisé.
    """

    def __init__(self, model_data: Optional[ModelData] = None, parent=None):
        super().__init__(parent)
        self.model_data = model_data or ModelData("Mobs")
        self.current_tool = "pencil"
        self.active_color = QColor("#f59e0b")
        self.brush_size = 1

        self._build_ui()
        self._connect_signals()
        self._refresh_cube_selector()

    def set_model_data(self, model_data: ModelData):
        self.model_data = model_data
        self.viewport_3d_paint.set_model_data(model_data)
        self.canvas_2d.set_model_data(model_data)
        self._connect_signals()
        self._refresh_cube_selector()

    def _connect_signals(self):
        try:
            self.model_data.textureChanged.connect(self.canvas_2d.update)
            self.model_data.modelChanged.connect(self._refresh_cube_selector)
            self.model_data.selectionChanged.connect(self._on_selection_synced)
        except Exception:
            pass

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # =====================================================================
        # BARRE D'OUTILS SUPÉRIEURE (OUTILS DE PEINTURE 2D/3D, COULEUR, TAILLE)
        # =====================================================================
        toolbar = QFrame()
        toolbar.setProperty("class", "InspectorPanel")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(10, 6, 10, 6)

        tools = [
            ("✏️ Crayon", "pencil"),
            ("🪣 Remplir Face", "bucket"),
            ("✨ Grain Pixel-Art", "noise"),
            ("☀️ Éclaircir", "lighten"),
            ("🌙 Assombrir", "darken"),
            ("🧪 Pipette", "eyedropper"),
            ("🧽 Gomme", "eraser"),
        ]
        for label, key in tools:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, k=key: self._select_tool(k))
            tb_layout.addWidget(btn)

        tb_layout.addWidget(QLabel("Taille :"))
        self.spn_brush = QSpinBox()
        self.spn_brush.setRange(1, 6)
        self.spn_brush.valueChanged.connect(self._on_brush_size_changed)
        tb_layout.addWidget(self.spn_brush)

        self.btn_color = QPushButton("🎨 Couleur")
        self.btn_color.clicked.connect(self._pick_color_dialog)
        tb_layout.addWidget(self.btn_color)
        self._update_color_button_style()

        # Nuancier rapide Luanti
        for hex_col in ["#ef4444", "#f97316", "#facc15", "#22c55e", "#38bdf8", "#3b82f6", "#a855f7", "#f8fafc", "#475569", "#1e293b"]:
            swatch = QPushButton()
            swatch.setFixedSize(22, 22)
            swatch.setStyleSheet(f"background-color: {hex_col}; border: 1px solid #0f172a; border-radius: 3px;")
            swatch.clicked.connect(lambda checked, c=hex_col: self.set_active_color(QColor(c)))
            tb_layout.addWidget(swatch)

        tb_layout.addStretch()

        btn_undo = QPushButton("↩️ Annuler")
        btn_undo.clicked.connect(lambda: self.model_data.undo_texture())
        tb_layout.addWidget(btn_undo)

        btn_redo = QPushButton("↪️ Rétablir")
        btn_redo.clicked.connect(lambda: self.model_data.redo_texture())
        tb_layout.addWidget(btn_redo)

        btn_export = QPushButton("💾 Exporter PNG")
        btn_export.clicked.connect(self._export_png)
        tb_layout.addWidget(btn_export)

        root.addWidget(toolbar)

        # =====================================================================
        # BARRE SECONDAIRE : SÉLECTION DU CUBE & OPTIONS DE VISIBILITÉ UV
        # =====================================================================
        subbar = QFrame()
        subbar.setProperty("class", "InspectorPanel")
        sub_layout = QHBoxLayout(subbar)
        sub_layout.setContentsMargins(10, 4, 10, 4)

        sub_layout.addWidget(QLabel("🧊 Cube sélectionné (6 faces modifiables) :"))
        self.combo_cubes = QComboBox()
        self.combo_cubes.currentIndexChanged.connect(self._on_cube_combo_changed)
        sub_layout.addWidget(self.combo_cubes)

        btn_fill_cube = QPushButton("🪣 Colorier les 6 faces de ce Cube")
        btn_fill_cube.clicked.connect(self._fill_entire_selected_cube)
        sub_layout.addWidget(btn_fill_cube)

        self.chk_show_uv = QCheckBox("Afficher les cadres des 6 faces (Haut, Bas, Avant, Arrière, Gauche, Droite)")
        self.chk_show_uv.setChecked(True)
        self.chk_show_uv.toggled.connect(self._on_uv_overlay_toggled)
        sub_layout.addWidget(self.chk_show_uv)

        self.chk_isolate = QCheckBox("Isoler uniquement le cube sélectionné en 2D")
        self.chk_isolate.toggled.connect(self._on_isolate_toggled)
        sub_layout.addWidget(self.chk_isolate)

        sub_layout.addStretch()
        root.addWidget(subbar)

        # =====================================================================
        # SPLITTER CENTRAL : PEINTURE 3D DIRECTE (GAUCHE) | ATLAS UV 2D (DROITE)
        # =====================================================================
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 1. Vue 3D interactive pour peindre directement sur le modèle
        left_3d_box = QFrame()
        left_3d_box.setProperty("class", "InspectorPanel")
        l3d_layout = QVBoxLayout(left_3d_box)
        l3d_layout.setContentsMargins(6, 6, 6, 6)

        lbl_3d = QLabel("🖌️ PEINTURE SUR LE MODÈLE 3D (Clic Gauche: Peindre sur le Cube | Clic Droit: Tourner)")
        lbl_3d.setStyleSheet("font-weight: bold; color: #60a5fa;")
        l3d_layout.addWidget(lbl_3d)

        self.viewport_3d_paint = PandaViewport(self.model_data, interaction_mode="paint_3d", parent=self)
        self.viewport_3d_paint.colorPicked3D.connect(self.set_active_color)
        l3d_layout.addWidget(self.viewport_3d_paint, 1)
        splitter.addWidget(left_3d_box)

        # 2. Vue 2D de l'Atlas Box-UV (6 faces par cube)
        right_2d_box = QFrame()
        right_2d_box.setProperty("class", "InspectorPanel")
        r2d_layout = QVBoxLayout(right_2d_box)
        r2d_layout.setContentsMargins(6, 6, 6, 6)

        lbl_2d = QLabel("🗺️ PATRON BOX-UV 2D (Chaque Cube = 6 faces indépendantes | Molette: Zoom | Clic Droit: Déplacer)")
        lbl_2d.setStyleSheet("font-weight: bold; color: #93c5fd;")
        r2d_layout.addWidget(lbl_2d)

        self.canvas_2d = UVAtlas2DCanvas(self.model_data, self)
        r2d_layout.addWidget(self.canvas_2d, 1)
        splitter.addWidget(right_2d_box)

        splitter.setSizes([680, 680])
        root.addWidget(splitter, 1)

    def _select_tool(self, tool_key: str):
        self.current_tool = tool_key
        self.viewport_3d_paint.paint_tool = tool_key

    def _on_brush_size_changed(self, size: int):
        self.brush_size = size
        self.viewport_3d_paint.paint_brush_size = size

    def set_active_color(self, color: QColor):
        if color.isValid():
            self.active_color = color
            self.viewport_3d_paint.paint_color = color
            self._update_color_button_style()

    def _pick_color_dialog(self):
        col = QColorDialog.getColor(self.active_color, self, "Choisir une couleur de texture")
        if col.isValid():
            self.set_active_color(col)

    def _update_color_button_style(self):
        hex_c = self.active_color.name()
        self.btn_color.setStyleSheet(
            f"background-color: {hex_c}; color: #ffffff; font-weight: bold; border: 2px solid #f8fafc;"
        )

    def _refresh_cube_selector(self):
        self.combo_cubes.blockSignals(True)
        self.combo_cubes.clear()
        sel_idx = 0
        for idx, cube in enumerate(self.model_data.cubes):
            w, h, d = cube.get_pixel_dimensions()
            self.combo_cubes.addItem(f"{cube.name} ({w}×{h}×{d} px)", cube.cube_id)
            if cube.cube_id == self.model_data.selected_cube_id:
                sel_idx = idx
        self.combo_cubes.setCurrentIndex(sel_idx)
        self.combo_cubes.blockSignals(False)
        self.canvas_2d.update()

    def _on_cube_combo_changed(self, idx: int):
        cid = self.combo_cubes.itemData(idx)
        if cid:
            self.model_data.select_cube(cid)

    def _on_selection_synced(self):
        self._refresh_cube_selector()
        self.canvas_2d.update()
        self.viewport_3d_paint.update()

    def _fill_entire_selected_cube(self):
        cube = self.model_data.get_selected_cube()
        if cube:
            self.model_data.push_undo_snapshot()
            self.model_data.fill_cube_all_faces(cube, self.active_color, add_pixel_variation=True)
            self.model_data.textureChanged.emit()

    def _on_uv_overlay_toggled(self, checked: bool):
        self.canvas_2d.show_uv_overlay = checked
        self.canvas_2d.update()

    def _on_isolate_toggled(self, checked: bool):
        self.canvas_2d.isolate_selected_cube = checked
        self.canvas_2d.update()

    def _export_png(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter la texture PNG Luanti", f"{self.model_data.name}.png", "Images PNG (*.png)"
        )
        if path:
            self.model_data.texture_image.save(path, "PNG")