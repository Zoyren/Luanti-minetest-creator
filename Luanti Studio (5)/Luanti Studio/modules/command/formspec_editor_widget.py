# -*- coding: utf-8 -*-
"""
modules/command/formspec_editor_widget.py
Workbench 2 (Catégorie Commands) :
- Éditeur WYSIWYG de GUI Personnalisée Luanti (formspec_version[6])
- Correction exacte de la géométrie de l'inventaire du joueur (size=1,1 + spacing=0.25 => 8x4 = 9.75x4.75)
- Éditeur Pixel-Art intégré directement dans l'atelier GUI pour dessiner les fonds, boutons et icônes en direct.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
    from PyQt6.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QImage
    )
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
        QLabel, QPushButton, QListWidget, QListWidgetItem,
        QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox,
        QGroupBox, QFormLayout, QFileDialog,
        QColorDialog, QPlainTextEdit, QTabWidget, QInputDialog
    )
except ImportError:
    from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
    from PyQt5.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QImage
    )
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
        QLabel, QPushButton, QListWidget, QListWidgetItem,
        QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox,
        QGroupBox, QFormLayout, QFileDialog,
        QColorDialog, QPlainTextEdit, QTabWidget, QInputDialog
    )


SLOT_SIZE_V6 = 1.0
SLOT_SPACING_V6 = 0.25


def calc_inventory_formspec_span(cols: int, rows: int) -> Tuple[float, float]:
    """
    Calcule la largeur et la hauteur exactes occupées par une grille `list[...]`
    dans Luanti formspec_version[6] (1 slot = 1.0 unité, espacement inter-slot = 0.25 unité).
    Pour 8x4 slots : largeur = 8*1 + 7*0.25 = 9.75, hauteur = 4*1 + 3*0.25 = 4.75.
    """
    c = max(1, int(cols))
    r = max(1, int(rows))
    w = c * SLOT_SIZE_V6 + (c - 1) * SLOT_SPACING_V6
    h = r * SLOT_SIZE_V6 + (r - 1) * SLOT_SPACING_V6
    return w, h


@dataclass
class FormspecElement:
    """Élément visuel placé sur la GUI personnalisée Luanti."""
    elem_id: str
    elem_type: str  # "image_button", "button", "image", "label", "field", "inventory", "progressbar", "box"
    name: str
    x: float
    y: float
    w: float
    h: float
    label: str = ""
    texture_name: str = ""
    pressed_texture_name: str = ""
    color_hex: str = "#2563eb"
    inv_location: str = "current_player;main"
    inv_cols: int = 8
    inv_rows: int = 4

    def sync_inventory_dimensions(self):
        if self.elem_type == "inventory":
            self.w, self.h = calc_inventory_formspec_span(self.inv_cols, self.inv_rows)


class ProceduralGuiTextureBank:
    """
    Banque de textures Pixel-Art de la GUI (fonds 9-slice, boutons, icônes)
    modifiable en direct via l'éditeur Pixel-Art intégré.
    """

    def __init__(self):
        self.textures: Dict[str, QImage] = {}
        self.build_builtin_gui_textures()

    def build_builtin_gui_textures(self):
        self.textures["gui_bg_rpg_dark.png"] = self.make_framed_panel_texture(
            48, 48, QColor("#1e2430"), QColor("#0f131a"), QColor("#60a5fa"), QColor("#facc15")
        )
        self.textures["gui_bg_wood_chest.png"] = self.make_framed_panel_texture(
            48, 48, QColor("#5c3a21"), QColor("#3d2514"), QColor("#9a6338"), QColor("#d97706")
        )
        self.textures["gui_bg_parchment.png"] = self.make_framed_panel_texture(
            48, 48, QColor("#d6c7a1"), QColor("#b5a175"), QColor("#785c38"), QColor("#92400e")
        )
        self.textures["gui_bg_scifi_neon.png"] = self.make_framed_panel_texture(
            48, 48, QColor("#091626"), QColor("#040b14"), QColor("#06b6d4"), QColor("#22d3ee")
        )

        self.textures["btn_rpg_blue.png"] = self.make_button_texture(48, 16, QColor("#2563eb"), QColor("#93c5fd"))
        self.textures["btn_rpg_blue_pressed.png"] = self.make_button_texture(48, 16, QColor("#1e3a8a"), QColor("#60a5fa"))
        self.textures["btn_rpg_gold.png"] = self.make_button_texture(48, 16, QColor("#d97706"), QColor("#fde047"))
        self.textures["btn_rpg_emerald.png"] = self.make_button_texture(48, 16, QColor("#16a34a"), QColor("#86efac"))
        self.textures["btn_rpg_crimson.png"] = self.make_button_texture(48, 16, QColor("#dc2626"), QColor("#fca5a5"))

        self.textures["icon_coin_gold.png"] = self.make_emblem_texture(24, 24, QColor("#facc15"), QColor("#b45309"))
        self.textures["icon_crystal_gem.png"] = self.make_emblem_texture(24, 24, QColor("#38bdf8"), QColor("#0369a1"))

    @staticmethod
    def make_framed_panel_texture(w: int, h: int, fill: QColor, dark: QColor, border: QColor, corner: QColor) -> QImage:
        img = QImage(w, h, QImage.Format.Format_ARGB32)
        for y in range(h):
            for x in range(w):
                if x < 2 or x >= w - 2 or y < 2 or y >= h - 2:
                    c = border
                elif x < 4 or x >= w - 4 or y < 4 or y >= h - 4:
                    c = dark
                else:
                    c = fill.darker(104) if (x + y * 3) % 7 == 0 else fill
                if (x in (3, 4, w - 4, w - 5)) and (y in (3, 4, h - 4, h - 5)):
                    c = corner
                img.setPixelColor(x, y, c)
        return img

    @staticmethod
    def make_button_texture(w: int, h: int, base: QColor, highlight: QColor) -> QImage:
        img = QImage(w, h, QImage.Format.Format_ARGB32)
        for y in range(h):
            for x in range(w):
                if x == 0 or x == w - 1 or y == 0 or y == h - 1:
                    c = QColor("#0f172a")
                elif y == 1 or x == 1:
                    c = highlight
                elif y == h - 2 or x == w - 2:
                    c = base.darker(145)
                else:
                    c = base.lighter(106) if y < h // 2 else base
                img.setPixelColor(x, y, c)
        return img

    @staticmethod
    def make_emblem_texture(w: int, h: int, inner: QColor, outer: QColor) -> QImage:
        img = QImage(w, h, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        cx, cy = w * 0.5, h * 0.5
        for y in range(h):
            for x in range(w):
                dist = abs(x - cx) + abs(y - cy)
                if dist < w * 0.32:
                    img.setPixelColor(x, y, inner.lighter(115) if (x + y) % 3 == 0 else inner)
                elif dist < w * 0.44:
                    img.setPixelColor(x, y, outer)
        return img

    def load_external_png(self, file_path: str) -> Optional[str]:
        img = QImage(file_path)
        if img.isNull():
            return None
        tex_name = os.path.basename(file_path)
        self.textures[tex_name] = img.convertToFormat(QImage.Format.Format_ARGB32)
        return tex_name

    def create_blank_texture(self, name: str, w: int, h: int, fill_color: QColor) -> str:
        if not name.endswith(".png"):
            name += ".png"
        img = QImage(max(8, w), max(8, h), QImage.Format.Format_ARGB32)
        img.fill(fill_color)
        self.textures[name] = img
        return name


class GuiPixelArtCanvas(QWidget):
    """
    Canevas Pixel-Art intégré directement dans l'atelier GUI pour dessiner/modifier
    les textures de fond, de boutons et d'icônes avec mise à jour instantanée de la GUI.
    """
    textureModified = pyqtSignal()

    def __init__(self, tex_bank: ProceduralGuiTextureBank, parent=None):
        super().__init__(parent)
        self.tex_bank = tex_bank
        self.current_tex_name = "gui_bg_rpg_dark.png"
        self.tool = "pencil"  # "pencil", "bucket", "rect_border", "lighten", "darken", "eyedropper", "eraser"
        self.paint_color = QColor("#facc15")
        self.brush_size = 1

        self.zoom = 8.0
        self.pan = QPointF(16.0, 16.0)
        self._painting = False
        self._panning = False
        self._last_mouse = QPointF(0, 0)
        self._hover_px = (-1, -1)

        self.setMinimumSize(280, 260)
        self.setMouseTracking(True)

    def current_image(self) -> Optional[QImage]:
        return self.tex_bank.textures.get(self.current_tex_name)

    def set_texture_to_edit(self, tex_name: str):
        if tex_name in self.tex_bank.textures:
            self.current_tex_name = tex_name
            img = self.current_image()
            if img:
                fit_z = min((self.width() - 32) / max(1, img.width()), (self.height() - 32) / max(1, img.height()))
                self.zoom = max(3.0, min(18.0, fit_z))
                self.pan = QPointF(16.0, 16.0)
            self.update()

    def _screen_to_pixel(self, pos: QPointF) -> Tuple[int, int]:
        px = int((pos.x() - self.pan.x()) / self.zoom)
        py = int((pos.y() - self.pan.y()) / self.zoom)
        return px, py

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#101218"))

        img = self.current_image()
        if not img or img.isNull():
            painter.setPen(QColor("#94a3b8"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Aucune texture sélectionnée")
            return

        w, h = img.width(), img.height()
        ox, oy = self.pan.x(), self.pan.y()
        z = self.zoom

        # Damier de transparence + pixels de la texture
        for y in range(h):
            for x in range(w):
                r = QRectF(ox + x * z, oy + y * z, z, z)
                chk = QColor("#1e222d") if (x + y) % 2 == 0 else QColor("#161922")
                painter.fillRect(r, chk)
                col = img.pixelColor(x, y)
                if col.alpha() > 0:
                    painter.fillRect(r, col)

        # Grille pixel-art légère si zoom >= 5
        if z >= 5.0:
            painter.setPen(QPen(QColor(255, 255, 255, 22), 1.0))
            for x in range(w + 1):
                painter.drawLine(int(ox + x * z), int(oy), int(ox + x * z), int(oy + h * z))
            for y in range(h + 1):
                painter.drawLine(int(ox), int(oy + y * z), int(ox + w * z), int(oy + y * z))

        # Cadre extérieur
        painter.setPen(QPen(QColor("#60a5fa"), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(ox, oy, w * z, h * z))

        # Curseur survolé
        hx, hy = self._hover_px
        if 0 <= hx < w and 0 <= hy < h:
            painter.setPen(QPen(QColor("#ffffff"), 1.5))
            painter.drawRect(QRectF(ox + hx * z, oy + hy * z, z, z))

    def mousePressEvent(self, event):
        pos = QPointF(event.pos())
        self._last_mouse = pos
        if event.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self._panning = True
            return
        if event.button() == Qt.MouseButton.LeftButton:
            px, py = self._screen_to_pixel(pos)
            self._apply_tool_at(px, py)
            self._painting = True

    def mouseMoveEvent(self, event):
        pos = QPointF(event.pos())
        dx = pos.x() - self._last_mouse.x()
        dy = pos.y() - self._last_mouse.y()
        self._last_mouse = pos
        self._hover_px = self._screen_to_pixel(pos)

        if self._panning:
            self.pan += QPointF(dx, dy)
            self.update()
        elif self._painting:
            if self.tool not in ("bucket", "rect_border", "eyedropper"):
                self._apply_tool_at(*self._hover_px)
        else:
            self.update()

    def mouseReleaseEvent(self, event):
        self._painting = False
        self._panning = False

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 0.86
        self.zoom = max(2.0, min(32.0, self.zoom * factor))
        self.update()

    def _apply_tool_at(self, px: int, py: int):
        img = self.current_image()
        if not img or not (0 <= px < img.width() and 0 <= py < img.height()):
            return

        if self.tool == "eyedropper":
            self.paint_color = img.pixelColor(px, py)
            return

        if self.tool == "bucket":
            target_rgba = img.pixelColor(px, py).rgba()
            new_rgba = self.paint_color.rgba()
            if target_rgba == new_rgba:
                return
            stack = [(px, py)]
            visited = set()
            w, h = img.width(), img.height()
            while stack:
                cx, cy = stack.pop()
                if (cx, cy) in visited or not (0 <= cx < w and 0 <= cy < h):
                    continue
                if img.pixelColor(cx, cy).rgba() != target_rgba:
                    continue
                visited.add((cx, cy))
                img.setPixelColor(cx, cy, self.paint_color)
                stack.extend([(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)])

        elif self.tool == "rect_border":
            # Trace une bordure Pixel-Art propre tout autour de la texture
            w, h = img.width(), img.height()
            for x in range(w):
                img.setPixelColor(x, 0, self.paint_color)
                img.setPixelColor(x, h - 1, self.paint_color)
                if h > 4:
                    img.setPixelColor(x, 1, self.paint_color.darker(130))
                    img.setPixelColor(x, h - 2, self.paint_color.darker(130))
            for y in range(h):
                img.setPixelColor(0, y, self.paint_color)
                img.setPixelColor(w - 1, y, self.paint_color)
                if w > 4:
                    img.setPixelColor(1, y, self.paint_color.darker(130))
                    img.setPixelColor(w - 2, y, self.paint_color.darker(130))

        else:
            half = max(0, (self.brush_size - 1) // 2)
            for dy in range(-half, self.brush_size - half):
                for dx in range(-half, self.brush_size - half):
                    ux, uy = px + dx, py + dy
                    if 0 <= ux < img.width() and 0 <= uy < img.height():
                        if self.tool == "eraser":
                            img.setPixelColor(ux, uy, QColor(0, 0, 0, 0))
                        elif self.tool == "lighten":
                            img.setPixelColor(ux, uy, img.pixelColor(ux, uy).lighter(114))
                        elif self.tool == "darken":
                            img.setPixelColor(ux, uy, img.pixelColor(ux, uy).darker(114))
                        else:
                            img.setPixelColor(ux, uy, self.paint_color)

        self.update()
        self.textureModified.emit()


class FormspecCanvasWidget(QWidget):
    """
    Canevas WYSIWYG interactif reproduisant à 100% une fenêtre Luanti formspec_version[6],
    incluant l'espacement inter-slot officiel de 0.25 sur l'inventaire du joueur.
    """
    elementSelected = pyqtSignal(object)
    elementMovedOrResized = pyqtSignal()

    UNIT_PX = 48.0  # 1 unité Formspec Luanti = 48 pixels écran

    def __init__(self, editor: "FormspecEditorWidget"):
        super().__init__(editor)
        self.editor = editor
        self.setMinimumSize(540, 460)
        self.setMouseTracking(True)

        self.snap_step = 0.25
        self._drag_mode: Optional[str] = None
        self._drag_start_mouse = QPointF(0, 0)
        self._drag_orig_rect = (0.0, 0.0, 1.0, 1.0)

    def _window_origin(self) -> QPointF:
        win_w_px = self.editor.win_width * self.UNIT_PX
        win_h_px = self.editor.win_height * self.UNIT_PX
        ox = max(18.0, (self.width() - win_w_px) * 0.5)
        oy = max(24.0, (self.height() - win_h_px) * 0.5)
        return QPointF(ox, oy)

    def _element_screen_rect(self, elem: FormspecElement) -> QRectF:
        elem.sync_inventory_dimensions()
        orig = self._window_origin()
        return QRectF(
            orig.x() + elem.x * self.UNIT_PX,
            orig.y() + elem.y * self.UNIT_PX,
            elem.w * self.UNIT_PX,
            elem.h * self.UNIT_PX,
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        painter.fillRect(self.rect(), QColor("#0d1017"))

        orig = self._window_origin()
        win_w_px = self.editor.win_width * self.UNIT_PX
        win_h_px = self.editor.win_height * self.UNIT_PX
        win_rect = QRectF(orig.x(), orig.y(), win_w_px, win_h_px)

        # Texture de fond personnalisée (background9)
        bg_img = self.editor.tex_bank.textures.get(self.editor.bg_texture_name)
        if bg_img and not bg_img.isNull():
            scaled_bg = bg_img.scaled(
                max(1, int(win_w_px)), max(1, int(win_h_px)),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation
            )
            painter.drawImage(win_rect.topLeft(), scaled_bg)
        else:
            painter.fillRect(win_rect, QColor(self.editor.bg_color_hex))

        # Grille Formspec (1.0 et 0.5 unité)
        grid_pen_main = QPen(QColor(255, 255, 255, 28), 1.0)
        grid_pen_sub = QPen(QColor(255, 255, 255, 12), 1.0, Qt.PenStyle.DotLine)

        cols = int(self.editor.win_width * 2)
        rows = int(self.editor.win_height * 2)
        for c in range(1, cols):
            gx = orig.x() + c * 0.5 * self.UNIT_PX
            painter.setPen(grid_pen_main if c % 2 == 0 else grid_pen_sub)
            painter.drawLine(int(gx), int(orig.y()), int(gx), int(orig.y() + win_h_px))

        for r in range(1, rows):
            gy = orig.y() + r * 0.5 * self.UNIT_PX
            painter.setPen(grid_pen_main if r % 2 == 0 else grid_pen_sub)
            painter.drawLine(int(orig.x()), int(gy), int(orig.x() + win_w_px), int(gy))

        painter.setPen(QPen(QColor("#60a5fa"), 2.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(win_rect)

        for elem in self.editor.elements:
            self._draw_formspec_element(painter, elem)

        painter.setPen(QColor("#94a3b8"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(
            12, 18,
            f"🖼️ Fenêtre Luanti formspec_version[6] : size[{self.editor.win_width:.2f},{self.editor.win_height:.2f}] "
            f"| Fond : {self.editor.bg_texture_name}"
        )

    def _draw_formspec_element(self, painter: QPainter, elem: FormspecElement):
        r = self._element_screen_rect(elem)
        is_sel = (self.editor.selected_element is elem)

        if elem.elem_type in ("image_button", "button"):
            tex = self.editor.tex_bank.textures.get(elem.texture_name)
            if elem.elem_type == "image_button" and tex and not tex.isNull():
                scaled = tex.scaled(
                    max(1, int(r.width())), max(1, int(r.height())),
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.FastTransformation
                )
                painter.drawImage(r.topLeft(), scaled)
            else:
                painter.setBrush(QBrush(QColor(elem.color_hex)))
                painter.setPen(QPen(QColor("#e2e8f0"), 1.5))
                painter.drawRoundedRect(r, 4, 4)

            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, elem.label)

        elif elem.elem_type == "image":
            tex = self.editor.tex_bank.textures.get(elem.texture_name)
            if tex and not tex.isNull():
                scaled = tex.scaled(
                    max(1, int(r.width())), max(1, int(r.height())),
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.FastTransformation
                )
                painter.drawImage(r.topLeft(), scaled)
            else:
                painter.fillRect(r, QColor(56, 189, 248, 80))
                painter.setPen(QColor("#ffffff"))
                painter.drawText(r, Qt.AlignmentFlag.AlignCenter, f"🖼️ {elem.texture_name}")

        elif elem.elem_type == "inventory":
            # Rendu EXACT de Luanti formspec_version[6] :
            # Chaque slot = 1.0 * UNIT_PX, espacement entre deux slots = 0.25 * UNIT_PX
            cols = max(1, elem.inv_cols)
            rows = max(1, elem.inv_rows)
            slot_px = SLOT_SIZE_V6 * self.UNIT_PX
            step_px = (SLOT_SIZE_V6 + SLOT_SPACING_V6) * self.UNIT_PX

            for row in range(rows):
                for col in range(cols):
                    sx = r.x() + col * step_px
                    sy = r.y() + row * step_px
                    sr = QRectF(sx, sy, slot_px, slot_px)
                    # Style de slot d'inventaire Minetest (bord biseauté sombre + fond semi-transparent)
                    bg_col = QColor(30, 41, 59, 220) if row == 0 else QColor(15, 23, 42, 200)
                    painter.fillRect(sr, bg_col)
                    painter.setPen(QPen(QColor("#94a3b8") if row == 0 else QColor("#64748b"), 1.3))
                    painter.drawRect(sr)

        elif elem.elem_type == "field":
            painter.fillRect(r, QColor("#090d14"))
            painter.setPen(QPen(QColor("#94a3b8"), 1.4))
            painter.drawRect(r)
            painter.setPen(QColor("#cbd5e1"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(r.adjusted(8, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter, elem.label or elem.name)

        elif elem.elem_type == "progressbar":
            painter.fillRect(r, QColor("#0f172a"))
            fill_r = QRectF(r.x() + 2, r.y() + 2, (r.width() - 4) * 0.72, r.height() - 4)
            painter.fillRect(fill_r, QColor(elem.color_hex))
            painter.setPen(QPen(QColor("#e2e8f0"), 1.2))
            painter.drawRect(r)
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, elem.label or "72%")

        elif elem.elem_type == "box":
            c = QColor(elem.color_hex)
            c.setAlpha(150)
            painter.fillRect(r, c)
            painter.setPen(QPen(QColor(elem.color_hex).lighter(130), 1.5))
            painter.drawRect(r)

        elif elem.elem_type == "label":
            painter.setPen(QColor(elem.color_hex if elem.color_hex != "#2563eb" else "#f8fafc"))
            painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            painter.drawText(r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elem.label)

        if is_sel:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#facc15"), 2.2, Qt.PenStyle.DashLine))
            painter.drawRect(r.adjusted(-2, -2, 2, 2))

            handle = QRectF(r.right() - 6, r.bottom() - 6, 12, 12)
            painter.setBrush(QBrush(QColor("#facc15")))
            painter.setPen(QPen(QColor("#0f172a"), 1.2))
            painter.drawRect(handle)

    def _snap(self, val: float) -> float:
        return round(val / self.snap_step) * self.snap_step

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = QPointF(event.pos())
        self._drag_start_mouse = pos

        sel = self.editor.selected_element
        if sel is not None:
            sr = self._element_screen_rect(sel)
            handle = QRectF(sr.right() - 10, sr.bottom() - 10, 20, 20)
            if handle.contains(pos):
                self._drag_mode = "resize"
                self._drag_orig_rect = (sel.x, sel.y, sel.w, sel.h)
                return

        for elem in reversed(self.editor.elements):
            sr = self._element_screen_rect(elem)
            if sr.contains(pos):
                self.editor.select_element(elem)
                self._drag_mode = "move"
                self._drag_orig_rect = (elem.x, elem.y, elem.w, elem.h)
                self.update()
                return

        self.editor.select_element(None)
        self.update()

    def mouseMoveEvent(self, event):
        sel = self.editor.selected_element
        if not sel or not self._drag_mode:
            return

        pos = QPointF(event.pos())
        dx_units = (pos.x() - self._drag_start_mouse.x()) / self.UNIT_PX
        dy_units = (pos.y() - self._drag_start_mouse.y()) / self.UNIT_PX
        ox, oy, ow, oh = self._drag_orig_rect

        if self._drag_mode == "move":
            sel.x = max(0.0, min(self.editor.win_width - sel.w, self._snap(ox + dx_units)))
            sel.y = max(0.0, min(self.editor.win_height - sel.h, self._snap(oy + dy_units)))
        elif self._drag_mode == "resize":
            if sel.elem_type == "inventory":
                new_cols = max(1, min(16, int(round((ow + dx_units + SLOT_SPACING_V6) / (SLOT_SIZE_V6 + SLOT_SPACING_V6)))))
                new_rows = max(1, min(10, int(round((oh + dy_units + SLOT_SPACING_V6) / (SLOT_SIZE_V6 + SLOT_SPACING_V6)))))
                sel.inv_cols = new_cols
                sel.inv_rows = new_rows
                sel.sync_inventory_dimensions()
            else:
                sel.w = max(0.5, min(self.editor.win_width - sel.x, self._snap(ow + dx_units)))
                sel.h = max(0.5, min(self.editor.win_height - sel.y, self._snap(oh + dy_units)))

        self.elementMovedOrResized.emit()
        self.update()

    def mouseReleaseEvent(self, event):
        self._drag_mode = None


class FormspecEditorWidget(QWidget):
    """
    Atelier 2 (Catégorie Commands) : Créateur WYSIWYG de GUI Personnalisée
    avec Éditeur de Texture Pixel-Art intégré et géométrie d'inventaire Formspec v6 exacte.
    """
    formspecCodeChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tex_bank = ProceduralGuiTextureBank()

        self.formname = "mon_mod:boutique_gui"
        # Taille de fenêtre calibrée pour accueillir 8x4 slots (9.75 de large) avec marges symétriques de 0.625 !
        self.win_width = 11.0
        self.win_height = 9.5
        self.bg_texture_name = "gui_bg_rpg_dark.png"
        self.bg_color_hex = "#1e2430"

        self.elements: List[FormspecElement] = []
        self.selected_element: Optional[FormspecElement] = None
        self._updating_ui = False

        self._load_default_rpg_shop_gui()
        self._build_ui()
        self._refresh_texture_combos()
        self.select_element(self.elements[0] if self.elements else None)
        self._compile_formspec_lua()

    def _load_default_rpg_shop_gui(self):
        inv_w, inv_h = calc_inventory_formspec_span(8, 4)  # 9.75 x 4.75
        inv_x = round((self.win_width - inv_w) * 0.5, 3)   # 0.625 (parfaitement centré)

        self.elements = [
            FormspecElement(
                "el_banner", "box", "bandeau_haut", 0.625, 0.4, 9.75, 1.0,
                label="", color_hex="#0f172a"
            ),
            FormspecElement(
                "el_icon", "image", "icone_or", 0.85, 0.5, 0.8, 0.8,
                texture_name="icon_coin_gold.png"
            ),
            FormspecElement(
                "el_title", "label", "lbl_titre", 1.85, 0.5, 6.5, 0.8,
                label="BOUTIQUE ROYALE D'AXION", color_hex="#facc15"
            ),
            FormspecElement(
                "el_btn_buy", "image_button", "btn_acheter_epee", 0.625, 1.7, 4.7, 1.1,
                label="⚔️ Acheter Lame (5 Or)",
                texture_name="btn_rpg_gold.png",
                pressed_texture_name="btn_rpg_blue_pressed.png"
            ),
            FormspecElement(
                "el_btn_heal", "image_button", "btn_soin", 5.675, 1.7, 4.7, 1.1,
                label="❤️ Potion de Soin (2 Or)",
                texture_name="btn_rpg_emerald.png",
                pressed_texture_name="btn_rpg_blue_pressed.png"
            ),
            FormspecElement(
                "el_bar", "progressbar", "barre_xp", 0.625, 3.1, 9.75, 0.65,
                label="Niveau de Réputation : 72%", color_hex="#2563eb"
            ),
            FormspecElement(
                "el_inv", "inventory", "inv_joueur", inv_x, 4.1, inv_w, inv_h,
                inv_location="current_player;main", inv_cols=8, inv_rows=4
            ),
        ]

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # =====================================================================
        # 1. PANNEAU GAUCHE : COMPOSANTS GUI & FENÊTRE
        # =====================================================================
        left_panel = QFrame()
        left_panel.setProperty("class", "InspectorPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        grp_win = QGroupBox("🖼️ Fenêtre & Texture de Fond (background9)")
        win_form = QFormLayout(grp_win)

        size_row = QHBoxLayout()
        self.spn_win_w = QDoubleSpinBox()
        self.spn_win_w.setRange(6.0, 22.0)
        self.spn_win_w.setSingleStep(0.25)
        self.spn_win_w.setValue(self.win_width)
        self.spn_win_w.valueChanged.connect(self._on_window_settings_changed)

        self.spn_win_h = QDoubleSpinBox()
        self.spn_win_h.setRange(4.0, 18.0)
        self.spn_win_h.setSingleStep(0.25)
        self.spn_win_h.setValue(self.win_height)
        self.spn_win_h.valueChanged.connect(self._on_window_settings_changed)

        size_row.addWidget(QLabel("L:"))
        size_row.addWidget(self.spn_win_w)
        size_row.addWidget(QLabel("H:"))
        size_row.addWidget(self.spn_win_h)
        win_form.addRow("Taille GUI :", size_row)

        self.combo_bg_tex = QComboBox()
        self.combo_bg_tex.currentTextChanged.connect(self._on_bg_texture_changed)
        win_form.addRow("Texture Fond :", self.combo_bg_tex)

        btn_edit_bg = QPushButton("🖌️ Peindre ce Fond dans l'Éditeur Pixel-Art")
        btn_edit_bg.clicked.connect(lambda: self._open_texture_in_pixel_editor(self.bg_texture_name))
        win_form.addRow("", btn_edit_bg)

        left_layout.addWidget(grp_win)

        grp_add = QGroupBox("➕ Ajouter un Élément sur la GUI")
        add_layout = QVBoxLayout(grp_add)

        widget_buttons = [
            ("🔘 Bouton Texturé (image_button)", "image_button"),
            ("🖼️ Image / Icône Personnalisée (image)", "image"),
            ("🎒 Grille d'Inventaire Joueur (8×4 exact)", "inventory"),
            ("🔤 Texte / Titre (label)", "label"),
            ("⌨️ Champ de Saisie (field)", "field"),
            ("📊 Barre de Progression / Vie", "progressbar"),
            ("⬛ Cadre Décoratif Coloré (box)", "box"),
        ]
        for label, wtype in widget_buttons:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, t=wtype: self.add_new_element(t))
            add_layout.addWidget(btn)

        left_layout.addWidget(grp_add)

        left_layout.addWidget(QLabel("📋 Éléments de la GUI :"))
        self.elem_list = QListWidget()
        self.elem_list.currentRowChanged.connect(self._on_list_row_changed)
        left_layout.addWidget(self.elem_list, 1)

        btn_center_el = QPushButton("🎯 Centrer horizontalement l'élément actif")
        btn_center_el.clicked.connect(self._center_selected_element_horizontally)
        left_layout.addWidget(btn_center_el)

        btn_del = QPushButton("🗑️ Supprimer l'élément sélectionné")
        btn_del.setObjectName("DangerButton")
        btn_del.clicked.connect(self.delete_selected_element)
        left_layout.addWidget(btn_del)

        splitter.addWidget(left_panel)

        # =====================================================================
        # 2. ZONE CENTRALE : CANEVAS WYSIWYG DE LA GUI PERSONNALISÉE
        # =====================================================================
        center_panel = QFrame()
        center_panel.setProperty("class", "InspectorPanel")
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(6, 6, 6, 6)

        lbl_canvas = QLabel(
            "🖱️ Aperçu In-Game Formspec v6 Exact (Inventaire 8×4 = 9.75×4.75 unités avec espacement 0.25)"
        )
        lbl_canvas.setStyleSheet("color: #60a5fa; font-weight: bold;")
        center_layout.addWidget(lbl_canvas)

        self.canvas = FormspecCanvasWidget(self)
        self.canvas.elementMovedOrResized.connect(self._on_canvas_element_transformed)
        center_layout.addWidget(self.canvas, 1)

        splitter.addWidget(center_panel)

        # =====================================================================
        # 3. PANNEAU DROIT : ONGLETS [Éditeur Pixel-Art GUI] & [Propriétés / Lua]
        # =====================================================================
        right_tabs = QTabWidget()

        # --- ONGLET A : ÉDITEUR PIXEL-ART INTÉGRÉ POUR LES TEXTURES DE LA GUI ---
        paint_tab = QFrame()
        paint_tab.setProperty("class", "InspectorPanel")
        pt_layout = QVBoxLayout(paint_tab)
        pt_layout.setContentsMargins(8, 8, 8, 8)
        pt_layout.setSpacing(6)

        lbl_pt = QLabel("🎨 Dessinez directement les textures de votre GUI :")
        lbl_pt.setStyleSheet("font-weight: bold; color: #38bdf8;")
        pt_layout.addWidget(lbl_pt)

        tex_sel_row = QHBoxLayout()
        tex_sel_row.addWidget(QLabel("Texture active :"))
        self.combo_paint_target = QComboBox()
        self.combo_paint_target.currentTextChanged.connect(self._on_paint_target_changed)
        tex_sel_row.addWidget(self.combo_paint_target, 1)
        pt_layout.addLayout(tex_sel_row)

        new_tex_row = QHBoxLayout()
        btn_new_bg_tex = QPushButton("➕ Nouveau Fond (48×48)")
        btn_new_bg_tex.clicked.connect(lambda: self._create_new_gui_texture_dialog(48, 48, is_bg=True))
        btn_new_btn_tex = QPushButton("➕ Nouveau Bouton (48×16)")
        btn_new_btn_tex.clicked.connect(lambda: self._create_new_gui_texture_dialog(48, 16, is_bg=False))
        btn_import_png = QPushButton("📂 Importer PNG")
        btn_import_png.clicked.connect(self._import_custom_png_texture)
        new_tex_row.addWidget(btn_new_bg_tex)
        new_tex_row.addWidget(btn_new_btn_tex)
        new_tex_row.addWidget(btn_import_png)
        pt_layout.addLayout(new_tex_row)

        # Barre d'outils de dessin Pixel-Art GUI
        tools_row1 = QHBoxLayout()
        for t_lbl, t_key in [
            ("✏️ Crayon", "pencil"),
            ("🪣 Remplir", "bucket"),
            ("🖼️ Bordure", "rect_border"),
            ("☀️ +Clair", "lighten"),
            ("🌙 +Sombre", "darken"),
            ("🧪 Pipette", "eyedropper"),
            ("🧽 Gomme", "eraser"),
        ]:
            b = QPushButton(t_lbl)
            b.clicked.connect(lambda checked, k=t_key: self._set_gui_paint_tool(k))
            tools_row1.addWidget(b)
        pt_layout.addLayout(tools_row1)

        color_row = QHBoxLayout()
        self.btn_paint_col = QPushButton("🎨 Couleur Pinceau")
        self.btn_paint_col.clicked.connect(self._pick_gui_paint_color)
        color_row.addWidget(self.btn_paint_col)

        color_row.addWidget(QLabel("Taille :"))
        spn_bsize = QSpinBox()
        spn_bsize.setRange(1, 5)
        spn_bsize.valueChanged.connect(lambda v: setattr(self.pixel_canvas, "brush_size", v))
        color_row.addWidget(spn_bsize)

        for sw_hex in ["#facc15", "#38bdf8", "#2563eb", "#16a34a", "#dc2626", "#f8fafc", "#1e2430", "#0f172a"]:
            sw = QPushButton()
            sw.setFixedSize(20, 20)
            sw.setStyleSheet(f"background-color: {sw_hex}; border: 1px solid #ffffff; border-radius: 3px;")
            sw.clicked.connect(lambda checked, c=sw_hex: self._set_gui_paint_color(QColor(c)))
            color_row.addWidget(sw)
        color_row.addStretch()
        pt_layout.addLayout(color_row)

        self.pixel_canvas = GuiPixelArtCanvas(self.tex_bank, self)
        self.pixel_canvas.textureModified.connect(self._on_gui_texture_painted_live)
        pt_layout.addWidget(self.pixel_canvas, 1)

        right_tabs.addTab(paint_tab, "🎨 Éditeur Texture GUI")

        # --- ONGLET B : PROPRIÉTÉS DE L'ÉLÉMENT & CODE LUA FORMSPEC ---
        prop_tab = QFrame()
        prop_tab.setProperty("class", "InspectorPanel")
        right_layout = QVBoxLayout(prop_tab)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(8)

        grp_prop = QGroupBox("⚙️ Propriétés de l'Élément Sélectionné")
        prop_form = QFormLayout(grp_prop)

        self.inp_el_name = QLineEdit()
        self.inp_el_name.textEdited.connect(self._on_inspector_changed)
        prop_form.addRow("Identifiant (ID) :", self.inp_el_name)

        self.inp_el_label = QLineEdit()
        self.inp_el_label.textEdited.connect(self._on_inspector_changed)
        prop_form.addRow("Texte / Label :", self.inp_el_label)

        self.combo_el_tex = QComboBox()
        self.combo_el_tex.currentTextChanged.connect(self._on_inspector_changed)
        prop_form.addRow("Texture PNG :", self.combo_el_tex)

        btn_paint_this = QPushButton("🖌️ Modifier la texture de cet élément")
        btn_paint_this.clicked.connect(self._edit_selected_element_texture)
        prop_form.addRow("", btn_paint_this)

        xy_row = QHBoxLayout()
        self.spn_x = QDoubleSpinBox()
        self.spn_y = QDoubleSpinBox()
        for spn in (self.spn_x, self.spn_y):
            spn.setRange(0.0, 22.0)
            spn.setSingleStep(0.125)
            spn.setDecimals(3)
            spn.valueChanged.connect(self._on_inspector_changed)
        xy_row.addWidget(QLabel("X:"))
        xy_row.addWidget(self.spn_x)
        xy_row.addWidget(QLabel("Y:"))
        xy_row.addWidget(self.spn_y)
        prop_form.addRow("Position :", xy_row)

        wh_row = QHBoxLayout()
        self.spn_w = QDoubleSpinBox()
        self.spn_h = QDoubleSpinBox()
        for spn in (self.spn_w, self.spn_h):
            spn.setRange(0.25, 22.0)
            spn.setSingleStep(0.25)
            spn.setDecimals(2)
            spn.valueChanged.connect(self._on_inspector_changed)
        wh_row.addWidget(QLabel("L:"))
        wh_row.addWidget(self.spn_w)
        wh_row.addWidget(QLabel("H:"))
        wh_row.addWidget(self.spn_h)
        prop_form.addRow("Dimensions :", wh_row)

        btn_col = QPushButton("🎨 Choisir Couleur / Teinte")
        btn_col.clicked.connect(self._pick_element_color)
        prop_form.addRow("Couleur :", btn_col)

        right_layout.addWidget(grp_prop)

        lbl_code = QLabel("📜 Code Formspec v6 & Événements Lua générés :")
        lbl_code.setStyleSheet("font-weight: bold; color: #93c5fd;")
        right_layout.addWidget(lbl_code)

        self.lua_output = QPlainTextEdit()
        self.lua_output.setReadOnly(True)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.lua_output.setFont(font)
        right_layout.addWidget(self.lua_output, 1)

        right_tabs.addTab(prop_tab, "⚙️ Propriétés & Code Lua")
        self.right_tabs = right_tabs

        splitter.addWidget(right_tabs)
        splitter.setSizes([290, 620, 440])
        root.addWidget(splitter)

    # =========================================================================
    # GESTION DE L'ÉDITEUR PIXEL-ART INTÉGRÉ
    # =========================================================================
    def _set_gui_paint_tool(self, tool_key: str):
        self.pixel_canvas.tool = tool_key

    def _set_gui_paint_color(self, color: QColor):
        if color.isValid():
            self.pixel_canvas.paint_color = color
            self.btn_paint_col.setStyleSheet(
                f"background-color: {color.name()}; color: #ffffff; font-weight: bold;"
            )

    def _pick_gui_paint_color(self):
        col = QColorDialog.getColor(self.pixel_canvas.paint_color, self, "Couleur du pinceau GUI")
        if col.isValid():
            self._set_gui_paint_color(col)

    def _on_paint_target_changed(self, tex_name: str):
        if tex_name:
            self.pixel_canvas.set_texture_to_edit(tex_name)

    def _open_texture_in_pixel_editor(self, tex_name: str):
        if tex_name and tex_name in self.tex_bank.textures:
            self.right_tabs.setCurrentIndex(0)
            self.combo_paint_target.setCurrentText(tex_name)
            self.pixel_canvas.set_texture_to_edit(tex_name)

    def _edit_selected_element_texture(self):
        if self.selected_element and self.selected_element.texture_name:
            self._open_texture_in_pixel_editor(self.selected_element.texture_name)
        else:
            self._open_texture_in_pixel_editor(self.bg_texture_name)

    def _on_gui_texture_painted_live(self):
        """Rafraîchit instantanément l'aperçu de la GUI dès qu'un pixel est peint !"""
        self.canvas.update()

    def _create_new_gui_texture_dialog(self, w: int, h: int, is_bg: bool):
        default_name = f"gui_bg_perso_{len(self.tex_bank.textures)+1}.png" if is_bg else f"btn_perso_{len(self.tex_bank.textures)+1}.png"
        name, ok = QInputDialog.getText(self, "Nouvelle Texture GUI", "Nom du fichier PNG :", text=default_name)
        if not ok or not name.strip():
            return
        tname = self.tex_bank.create_blank_texture(name.strip(), w, h, QColor("#1e293b"))
        # Trace un cadre de départ propre
        if is_bg:
            self.tex_bank.textures[tname] = self.tex_bank.make_framed_panel_texture(
                w, h, QColor("#1e293b"), QColor("#0f172a"), QColor("#38bdf8"), QColor("#facc15")
            )
        else:
            self.tex_bank.textures[tname] = self.tex_bank.make_button_texture(w, h, QColor("#2563eb"), QColor("#93c5fd"))

        self._refresh_texture_combos()
        if is_bg:
            self.bg_texture_name = tname
            self.combo_bg_tex.setCurrentText(tname)
        elif self.selected_element:
            self.selected_element.texture_name = tname
            self.combo_el_tex.setCurrentText(tname)

        self._open_texture_in_pixel_editor(tname)
        self.canvas.update()
        self._compile_formspec_lua()

    # =========================================================================
    # SYNCHRONISATION DES LISTES ET INSPECTEURS
    # =========================================================================
    def _refresh_texture_combos(self):
        self._updating_ui = True
        tex_names = list(self.tex_bank.textures.keys())

        self.combo_bg_tex.clear()
        self.combo_bg_tex.addItems(tex_names)
        self.combo_bg_tex.setCurrentText(self.bg_texture_name)

        self.combo_paint_target.clear()
        self.combo_paint_target.addItems(tex_names)
        self.combo_paint_target.setCurrentText(self.pixel_canvas.current_tex_name)

        self.combo_el_tex.clear()
        self.combo_el_tex.addItem("")
        self.combo_el_tex.addItems(tex_names)
        if self.selected_element:
            self.combo_el_tex.setCurrentText(self.selected_element.texture_name)

        self._refresh_element_list()
        self._updating_ui = False

    def _refresh_element_list(self):
        self.elem_list.blockSignals(True)
        self.elem_list.clear()
        for el in self.elements:
            self.elem_list.addItem(QListWidgetItem(f"[{el.elem_type}] {el.name} ({el.label or el.texture_name})"))
        if self.selected_element and self.selected_element in self.elements:
            self.elem_list.setCurrentRow(self.elements.index(self.selected_element))
        self.elem_list.blockSignals(False)

    def select_element(self, elem: Optional[FormspecElement]):
        self.selected_element = elem
        self._updating_ui = True
        if elem:
            elem.sync_inventory_dimensions()
            self.inp_el_name.setText(elem.name)
            self.inp_el_label.setText(elem.label)
            self.combo_el_tex.setCurrentText(elem.texture_name)
            self.spn_x.setValue(elem.x)
            self.spn_y.setValue(elem.y)
            self.spn_w.setValue(elem.w)
            self.spn_h.setValue(elem.h)
            if elem.texture_name and elem.texture_name in self.tex_bank.textures:
                self.combo_paint_target.setCurrentText(elem.texture_name)
                self.pixel_canvas.set_texture_to_edit(elem.texture_name)
        self._refresh_element_list()
        self._updating_ui = False
        self.canvas.update()

    def _center_selected_element_horizontally(self):
        if not self.selected_element:
            return
        self.selected_element.sync_inventory_dimensions()
        if self.win_width < self.selected_element.w + 0.5:
            self.win_width = round(self.selected_element.w + 1.25, 2)
            self.spn_win_w.setValue(self.win_width)
        self.selected_element.x = round((self.win_width - self.selected_element.w) * 0.5, 3)
        self.select_element(self.selected_element)
        self._compile_formspec_lua()

    def _on_list_row_changed(self, row: int):
        if 0 <= row < len(self.elements):
            self.select_element(self.elements[row])

    def _on_canvas_element_transformed(self):
        self.select_element(self.selected_element)
        self._compile_formspec_lua()

    def _on_window_settings_changed(self):
        if self._updating_ui:
            return
        self.win_width = self.spn_win_w.value()
        self.win_height = self.spn_win_h.value()
        self.canvas.update()
        self._compile_formspec_lua()

    def _on_bg_texture_changed(self, tex_name: str):
        if self._updating_ui or not tex_name:
            return
        self.bg_texture_name = tex_name
        self.combo_paint_target.setCurrentText(tex_name)
        self.pixel_canvas.set_texture_to_edit(tex_name)
        self.canvas.update()
        self._compile_formspec_lua()

    def _on_inspector_changed(self):
        if self._updating_ui or not self.selected_element:
            return
        el = self.selected_element
        el.name = self.inp_el_name.text().strip() or el.name
        el.label = self.inp_el_label.text()
        el.texture_name = self.combo_el_tex.currentText()
        el.x = self.spn_x.value()
        el.y = self.spn_y.value()
        if el.elem_type != "inventory":
            el.w = self.spn_w.value()
            el.h = self.spn_h.value()
        self._refresh_element_list()
        self.canvas.update()
        self._compile_formspec_lua()

    def _pick_element_color(self):
        if not self.selected_element:
            return
        col = QColorDialog.getColor(QColor(self.selected_element.color_hex), self, "Couleur de l'élément")
        if col.isValid():
            self.selected_element.color_hex = col.name()
            self.canvas.update()
            self._compile_formspec_lua()

    def add_new_element(self, elem_type: str):
        idx = len(self.elements) + 1
        if elem_type == "image_button":
            el = FormspecElement(
                f"el_{idx}", "image_button", f"btn_custom_{idx}", 1.0, 1.5, 3.5, 1.0,
                label=f"Bouton {idx}", texture_name="btn_rpg_blue.png", pressed_texture_name="btn_rpg_blue_pressed.png"
            )
        elif elem_type == "image":
            el = FormspecElement(
                f"el_{idx}", "image", f"img_{idx}", 1.0, 1.0, 1.5, 1.5,
                texture_name="icon_crystal_gem.png"
            )
        elif elem_type == "inventory":
            inv_w, inv_h = calc_inventory_formspec_span(8, 4)
            if self.win_width < inv_w + 1.0:
                self.win_width = 11.0
                self.spn_win_w.setValue(self.win_width)
            inv_x = round((self.win_width - inv_w) * 0.5, 3)
            el = FormspecElement(
                f"el_{idx}", "inventory", f"inv_{idx}", inv_x, 4.1, inv_w, inv_h,
                inv_location="current_player;main", inv_cols=8, inv_rows=4
            )
        elif elem_type == "field":
            el = FormspecElement(
                f"el_{idx}", "field", f"champ_{idx}", 1.0, 2.0, 4.0, 0.8,
                label="Valeur par défaut"
            )
        elif elem_type == "progressbar":
            el = FormspecElement(
                f"el_{idx}", "progressbar", f"bar_{idx}", 1.0, 2.5, 5.0, 0.6,
                label="Progression 72%", color_hex="#16a34a"
            )
        elif elem_type == "box":
            el = FormspecElement(
                f"el_{idx}", "box", f"cadre_{idx}", 0.5, 0.5, 4.0, 2.0,
                color_hex="#1e293b"
            )
        else:
            el = FormspecElement(
                f"el_{idx}", "label", f"texte_{idx}", 1.0, 1.0, 4.0, 0.6,
                label=f"Nouveau Texte {idx}", color_hex="#f8fafc"
            )

        self.elements.append(el)
        self.select_element(el)
        self._compile_formspec_lua()

    def delete_selected_element(self):
        if self.selected_element and self.selected_element in self.elements:
            self.elements.remove(self.selected_element)
            self.select_element(self.elements[0] if self.elements else None)
            self._compile_formspec_lua()

    def _import_custom_png_texture(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer une texture PNG pour la GUI", "", "Images PNG (*.png)"
        )
        if path:
            tex_name = self.tex_bank.load_external_png(path)
            if tex_name:
                self._refresh_texture_combos()
                self._open_texture_in_pixel_editor(tex_name)
                self.canvas.update()
                self._compile_formspec_lua()

    def generate_formspec_lua(self) -> str:
        """
        Génère le code Lua formspec_version[6] avec `style_type[list;size=1,1;spacing=0.25,0.25]`
        pour garantir un alignement d'inventaire 100% identique entre l'éditeur et le jeu.
        """
        fs_parts = [
            "formspec_version[6]",
            f"size[{self.win_width:.2f},{self.win_height:.2f}]",
            "style_type[list;size=1,1;spacing=0.25,0.25]",
        ]
        if self.bg_texture_name:
            fs_parts.append(
                f"background9[0,0;{self.win_width:.2f},{self.win_height:.2f};{self.bg_texture_name};false;8]"
            )

        button_ids = []
        for el in self.elements:
            lbl = el.label.replace("]", "\\]").replace(";", "\\;")
            if el.elem_type == "image_button":
                tex = el.texture_name or "btn_rpg_blue.png"
                ptex = el.pressed_texture_name or tex
                fs_parts.append(
                    f"image_button[{el.x:.2f},{el.y:.2f};{el.w:.2f},{el.h:.2f};{tex};{el.name};{lbl};false;false;{ptex}]"
                )
                button_ids.append(el.name)
            elif el.elem_type == "button":
                fs_parts.append(f"button[{el.x:.2f},{el.y:.2f};{el.w:.2f},{el.h:.2f};{el.name};{lbl}]")
                button_ids.append(el.name)
            elif el.elem_type == "image":
                tex = el.texture_name or "icon_crystal_gem.png"
                fs_parts.append(f"image[{el.x:.2f},{el.y:.2f};{el.w:.2f},{el.h:.2f};{tex}]")
            elif el.elem_type == "inventory":
                loc = el.inv_location if ";" in el.inv_location else "current_player;main"
                fs_parts.append(
                    f"list[{loc};{el.x:.3f},{el.y:.3f};{el.inv_cols},{el.inv_rows};]"
                )
            elif el.elem_type == "field":
                fs_parts.append(f"field[{el.x:.2f},{el.y:.2f};{el.w:.2f},{el.h:.2f};{el.name};;{lbl}]")
            elif el.elem_type == "progressbar":
                fs_parts.append(
                    f"box[{el.x:.2f},{el.y:.2f};{el.w:.2f},{el.h:.2f};#0f172a]"
                    f"box[{el.x:.2f},{el.y:.2f};{el.w * 0.72:.2f},{el.h:.2f};{el.color_hex}]"
                    f"label[{el.x + 0.25:.2f},{el.y + el.h * 0.5:.2f};{lbl}]"
                )
            elif el.elem_type == "box":
                fs_parts.append(f"box[{el.x:.2f},{el.y:.2f};{el.w:.2f},{el.h:.2f};{el.color_hex}]")
            elif el.elem_type == "label":
                fs_parts.append(f"label[{el.x:.2f},{el.y + 0.35:.2f};{lbl}]")

        joined_fs = "\n    .. ".join(f'"{part}"' for part in fs_parts)
        lines = [
            "-- GUI Personnalisée (formspec_version[6]) générée par Luanti Studio",
            f"custom_formspec_string = {joined_fs}\n",
            "minetest.register_on_player_receive_fields(function(player, formname, fields)",
            f'    if formname ~= "{self.formname}" then return end',
            "    local pname = player:get_player_name()",
        ]
        for bid in button_ids:
            lines.extend([
                f'    if fields["{bid}"] then',
                f'        minetest.chat_send_player(pname, "[GUI] Action déclenchée : {bid}")',
                "    end",
            ])
        lines.append("end)")
        return "\n".join(lines)

    def _compile_formspec_lua(self):
        code = self.generate_formspec_lua()
        self.lua_output.setPlainText(code)
        self.formspecCodeChanged.emit(code)