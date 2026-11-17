# -*- coding: utf-8 -*-
"""
modules/world/world_editor_widget.py
Workbench Monde Voxel 3D Équivalent Minetest / Luanti :
- Rendu 3D fidèle des Blocs Custom créés dans le Studio (avec leurs vrais sous-cubes et textures Box-UV)
- Grille de construction extensible (16x16 jusqu'à 256x256) cliquable même en Monde Vide
- Catalogue de +42 Blocs Minetest filtrable par catégories + Recherche rapide
- Option d'export direct en Monde Vide (singlenode) avec apparition automatique sur la structure en jeu.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    from PyQt6.QtCore import Qt, QPointF, QRectF
    from PyQt6.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QImage,
        QPolygonF, QTransform, QLinearGradient, QPixmap, QIcon
    )
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
        QLabel, QPushButton, QListWidget, QListWidgetItem,
        QComboBox, QSpinBox, QGroupBox, QFileDialog, QMessageBox,
        QCheckBox, QLineEdit
    )
except ImportError:
    from PyQt5.QtCore import Qt, QPointF, QRectF
    from PyQt5.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QImage,
        QPolygonF, QTransform, QLinearGradient, QPixmap, QIcon
    )
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
        QLabel, QPushButton, QListWidget, QListWidgetItem,
        QComboBox, QSpinBox, QGroupBox, QFileDialog, QMessageBox,
        QCheckBox, QLineEdit
    )

from engine.voxel.voxel_engine import VoxelEngine, VOXEL_NEIGHBORS
from exporters.mts_exporter import MtsExporter


VOXEL_FACE_LIGHT: Dict[str, float] = {
    "top": 1.00,
    "north": 0.82,
    "south": 0.80,
    "east": 0.64,
    "west": 0.62,
    "bottom": 0.44,
}

WORLD_GRID_SIZES = [
    ("16×16 Blocs (Petit)", 16),
    ("32×32 Blocs (Moyen)", 32),
    ("64×64 Blocs (Grand)", 64),
    ("128×128 Blocs (Très Grand)", 128),
    ("256×256 Blocs (Méga Structure)", 256),
]


@dataclass
class ProjectedVoxelFace:
    pos: Tuple[int, int, int]
    face_name: str
    node_name: str
    screen_poly: QPolygonF
    depth_z: float
    custom_face_img: Optional[QImage] = None


class MinetestVoxelViewport3D(QWidget):
    """
    Viewport 3D du Monde Voxel avec :
    - Rendu des blocs standards Minetest 16x16
    - Rendu 3D exact des sous-cubes et Box-UV des Blocs Custom du Studio
    - Grille au sol cliquable pour construire même dans un Monde Vide (0 bloc)
    """

    def __init__(self, voxel_engine: VoxelEngine, editor: "WorldEditorWidget"):
        super().__init__(editor)
        self.engine = voxel_engine
        self.editor = editor
        self.setMinimumSize(640, 480)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.cam_yaw = -35.0
        self.cam_pitch = 28.0
        self.cam_distance = 22.0
        self.cam_target = [0.0, 1.0, 0.0]

        self._projected_faces: List[ProjectedVoxelFace] = []
        self._hovered_face: Optional[ProjectedVoxelFace] = None
        self._hovered_ground_cell: Optional[Tuple[int, int, int]] = None
        self._last_mouse = QPointF(0, 0)
        self._mouse_Rotate = False
        self._mouse_Pan = False

        self._crisp_tex_cache: Dict[Tuple[str, str], QImage] = {}
        self.engine.worldChanged.connect(self.update)
        self.engine.paletteChanged.connect(self._clear_tex_cache)

    def _clear_tex_cache(self):
        self._crisp_tex_cache.clear()
        self.update()

    def _get_crisp_face_image(self, node_name: str, face_name: str) -> Optional[QImage]:
        key = (node_name, face_name)
        if key in self._crisp_tex_cache:
            return self._crisp_tex_cache[key]
        bdef = self.engine.block_defs.get(node_name)
        if not bdef:
            return None
        raw = bdef.get_face_texture(face_name)
        crisp = raw.scaled(
            64, 64,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation
        )
        self._crisp_tex_cache[key] = crisp
        return crisp

    def _project_pt(self, pt: Tuple[float, float, float]) -> Optional[Tuple[float, float, float]]:
        w = max(1, self.width())
        h = max(1, self.height())
        x = pt[0] - self.cam_target[0]
        y = pt[1] - self.cam_target[1]
        z = pt[2] - self.cam_target[2]

        yaw_r = math.radians(self.cam_yaw)
        cy, sy = math.cos(yaw_r), math.sin(yaw_r)
        x1 = x * cy - z * sy
        z1 = x * sy + z * cy

        pitch_r = math.radians(self.cam_pitch)
        cp, sp = math.cos(pitch_r), math.sin(pitch_r)
        y2 = y * cp - z1 * sp
        z2 = y * sp + z1 * cp

        cam_z = self.cam_distance - z2
        if cam_z < 0.8:
            return None

        fov = min(w, h) * 0.95
        sx = w * 0.5 + (x1 * fov) / cam_z
        sy = h * 0.52 - (y2 * fov) / cam_z
        return sx, sy, cam_z

    def _draw_construction_floor_grid(self, painter: QPainter):
        """Dessine la grille de construction au sol (Y=0) de taille 16x16 jusqu'à 256x256."""
        gsize = self.engine.grid_size
        half = gsize // 2
        step = 1 if gsize <= 32 else (2 if gsize <= 64 else (4 if gsize <= 128 else 8))

        minor_pen = QPen(QColor(255, 255, 255, 28), 1.0)
        chunk_pen = QPen(QColor(56, 189, 248, 80), 1.3)
        border_pen = QPen(QColor("#facc15"), 1.8)

        for i in range(-half, half + 1, step):
            if abs(i) == half:
                pen = border_pen
            elif i % 16 == 0:
                pen = chunk_pen
            else:
                pen = minor_pen

            p1 = self._project_pt((float(i), 0.0, float(-half)))
            p2 = self._project_pt((float(i), 0.0, float(half)))
            if p1 and p2:
                painter.setPen(pen)
                painter.drawLine(QPointF(p1[0], p1[1]), QPointF(p2[0], p2[1]))

            p3 = self._project_pt((float(-half), 0.0, float(i)))
            p4 = self._project_pt((float(half), 0.0, float(i)))
            if p3 and p4:
                painter.setPen(pen)
                painter.drawLine(QPointF(p3[0], p3[1]), QPointF(p4[0], p4[1]))

        # Surbrillance de la case au sol pointée si aucun bloc n'est sous la souris
        if self._hovered_face is None and self._hovered_ground_cell is not None:
            gx, gy, gz = self._hovered_ground_cell
            c0 = self._project_pt((gx, gy, gz))
            c1 = self._project_pt((gx + 1, gy, gz))
            c2 = self._project_pt((gx + 1, gy, gz + 1))
            c3 = self._project_pt((gx, gy, gz + 1))
            if c0 and c1 and c2 and c3:
                poly = QPolygonF([
                    QPointF(c0[0], c0[1]), QPointF(c1[0], c1[1]),
                    QPointF(c2[0], c2[1]), QPointF(c3[0], c3[1]),
                ])
                painter.setBrush(QBrush(QColor(56, 189, 248, 75)))
                painter.setPen(QPen(QColor("#38bdf8"), 2.0))
                painter.drawPolygon(poly)

    def _collect_custom_3d_block_faces(self, vx: int, vy: int, vz: int, node_name: str, mdata):
        """
        Génère les vraies faces 3D de chaque sous-cube d'un Bloc Custom créé dans le Studio
        pour qu'il ait exactement la même forme et la même texture Box-UV dans le Monde Voxel !
        """
        face_indices = {
            "top":    (3, 2, 6, 7),
            "bottom": (4, 5, 1, 0),
            "north":  (7, 6, 5, 4),
            "south":  (2, 3, 0, 1),
            "east":   (6, 2, 1, 5),
            "west":   (3, 7, 4, 0),
        }
        atlas = mdata.texture_image

        for cube in mdata.cubes:
            if not cube.visible:
                continue
            x0, y0, z0 = cube.position
            w, h, d = cube.size
            x1, y1, z1 = x0 + w, y0 + h, z0 + d
            raw_v = [
                (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
            ]
            # Conversion de l'espace studio (-8..+8, 0..16, -8..+8) vers la case Voxel (vx..vx+1, vy..vy+1, vz..vz+1)
            world_v = []
            for pt in raw_v:
                tx, ty, tz = mdata.transform_vertex(pt, cube)
                wx = vx + 0.5 + (tx / 16.0)
                wy = vy + (ty / 16.0)
                wz = vz + 0.5 + (tz / 16.0)
                world_v.append((wx, wy, wz))

            uv_rects = cube.get_face_uv_rects()
            for fname, (i0, i1, i2, i3) in face_indices.items():
                s0 = self._project_pt(world_v[i0])
                s1 = self._project_pt(world_v[i1])
                s2 = self._project_pt(world_v[i2])
                s3 = self._project_pt(world_v[i3])
                if not (s0 and s1 and s2 and s3):
                    continue

                poly = QPolygonF([
                    QPointF(s0[0], s0[1]), QPointF(s1[0], s1[1]),
                    QPointF(s2[0], s2[1]), QPointF(s3[0], s3[1]),
                ])
                avg_z = (s0[2] + s1[2] + s2[2] + s3[2]) * 0.25
                r = uv_rects[fname]
                sub_img = atlas.copy(r.u, r.v, max(1, r.w), max(1, r.h)).scaled(
                    64, 64,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.FastTransformation
                )
                self._projected_faces.append(
                    ProjectedVoxelFace(
                        pos=(vx, vy, vz),
                        face_name=fname,
                        node_name=node_name,
                        screen_poly=poly,
                        depth_z=avg_z,
                        custom_face_img=sub_img,
                    )
                )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        # Ciel Minetest
        sky = QLinearGradient(0, 0, 0, self.height())
        if self.engine.export_void_world:
            sky.setColorAt(0.0, QColor("#172554"))
            sky.setColorAt(0.65, QColor("#1e3a8a"))
            sky.setColorAt(1.0, QColor("#0f172a"))
        else:
            sky.setColorAt(0.0, QColor("#3b82f6"))
            sky.setColorAt(0.65, QColor("#93c5fd"))
            sky.setColorAt(1.0, QColor("#1e293b"))
        painter.fillRect(self.rect(), sky)

        # Grille au sol
        self._draw_construction_floor_grid(painter)

        # Collecte des faces Voxel (Blocs standards 1x1x1 + Vrais Blocs 3D Custom)
        self._projected_faces.clear()

        face_vertices_local = {
            "top":    ((0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)),
            "bottom": ((0, 0, 1), (1, 0, 1), (1, 0, 0), (0, 0, 0)),
            "north":  ((0, 1, 1), (1, 1, 1), (1, 0, 1), (0, 0, 1)),
            "south":  ((1, 1, 0), (0, 1, 0), (0, 0, 0), (1, 0, 0)),
            "east":   ((1, 1, 1), (1, 1, 0), (1, 0, 0), (1, 0, 1)),
            "west":   ((0, 1, 0), (0, 1, 1), (0, 0, 1), (0, 0, 0)),
        }

        for (vx, vy, vz), node_name in self.engine.voxels.items():
            bdef = self.engine.block_defs.get(node_name)
            if bdef and bdef.custom_model_data is not None:
                self._collect_custom_3d_block_faces(vx, vy, vz, node_name, bdef.custom_model_data)
                continue

            for fname, corners in face_vertices_local.items():
                if not self.engine.is_face_visible(vx, vy, vz, fname, node_name):
                    continue
                pts_scr = []
                depths = []
                valid = True
                for dx, dy, dz in corners:
                    pr = self._project_pt((vx + dx, vy + dy, vz + dz))
                    if pr is None:
                        valid = False
                        break
                    pts_scr.append(QPointF(pr[0], pr[1]))
                    depths.append(pr[2])
                if not valid:
                    continue

                poly = QPolygonF(pts_scr)
                avg_z = sum(depths) * 0.25
                self._projected_faces.append(
                    ProjectedVoxelFace((vx, vy, vz), fname, node_name, poly, avg_z)
                )

        self._projected_faces.sort(key=lambda f: f.depth_z, reverse=True)

        src_quad = QPolygonF([
            QPointF(0.0, 0.0), QPointF(64.0, 0.0),
            QPointF(64.0, 64.0), QPointF(0.0, 64.0)
        ])

        for pface in self._projected_faces:
            crisp_img = pface.custom_face_img or self._get_crisp_face_image(pface.node_name, pface.face_name)
            if crisp_img:
                tr = QTransform()
                if QTransform.quadToQuad(src_quad, pface.screen_poly, tr):
                    painter.save()
                    painter.setTransform(tr)
                    painter.drawImage(0, 0, crisp_img)
                    painter.restore()

            light = VOXEL_FACE_LIGHT.get(pface.face_name, 0.8)
            shade_alpha = int(round((1.0 - light) * 205))
            if shade_alpha > 0:
                painter.setBrush(QBrush(QColor(0, 0, 0, shade_alpha)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawPolygon(pface.screen_poly)

            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(0, 0, 0, 45), 0.7))
            painter.drawPolygon(pface.screen_poly)

        if self._hovered_face is not None:
            self._draw_minetest_selection_box(painter, self._hovered_face)

        if self.engine.pos1:
            self._draw_voxel_wirebox(painter, self.engine.pos1, QColor("#ef4444"), "POS 1")
        if self.engine.pos2:
            self._draw_voxel_wirebox(painter, self.engine.pos2, QColor("#3b82f6"), "POS 2")

        self._draw_minetest_hud(painter)

    def _draw_minetest_selection_box(self, painter: QPainter, hface: ProjectedVoxelFace):
        painter.setBrush(QBrush(QColor(255, 255, 255, 55)))
        painter.setPen(QPen(QColor("#000000"), 2.4))
        painter.drawPolygon(hface.screen_poly)
        self._draw_voxel_wirebox(painter, hface.pos, QColor("#000000"), None)

    def _draw_voxel_wirebox(self, painter: QPainter, pos: Tuple[int, int, int], color: QColor, tag: Optional[str]):
        vx, vy, vz = pos
        corners = [
            (vx, vy, vz), (vx + 1, vy, vz), (vx + 1, vy + 1, vz), (vx, vy + 1, vz),
            (vx, vy, vz + 1), (vx + 1, vy, vz + 1), (vx + 1, vy + 1, vz + 1), (vx, vy + 1, vz + 1),
        ]
        proj = [self._project_pt(c) for c in corners]
        if any(p is None for p in proj):
            return

        edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),
            (4, 5), (5, 6), (6, 7), (7, 4),
            (0, 4), (1, 5), (2, 6), (3, 7),
        ]
        painter.setPen(QPen(color, 2.0))
        for i0, i1 in edges:
            painter.drawLine(QPointF(proj[i0][0], proj[i0][1]), QPointF(proj[i1][0], proj[i1][1]))

        if tag and proj[2]:
            painter.setPen(color)
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.drawText(QPointF(proj[2][0] + 4, proj[2][1] - 4), tag)

    def _draw_minetest_hud(self, painter: QPainter):
        cx, cy = self.width() // 2, self.height() // 2
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1.8))
        painter.drawLine(cx - 8, cy, cx + 8, cy)
        painter.drawLine(cx, cy - 8, cx, cy + 8)

        hud_rect = QRectF(10, 10, self.width() - 20, 32)
        painter.fillRect(hud_rect, QColor(15, 23, 42, 185))
        painter.setPen(QColor("#f8fafc"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(
            hud_rect.adjusted(10, 0, -10, 0),
            Qt.AlignmentFlag.AlignVCenter,
            f"🌍 Grille : {self.engine.grid_size}×{self.engine.grid_size} | Clic Gauche = Poser | "
            f"Shift+Clic Gauche = Casser | Clic Droit = Tourner | ZQSD/WASD + Espace/C = Voler"
        )

        if self._hovered_face:
            hx, hy, hz = self._hovered_face.pos
            dx, dy, dz = VOXEL_NEIGHBORS[self._hovered_face.face_name]
            px, py, pz = hx + dx, hy + dy, hz + dz
            status = (
                f"🎯 Bloc visé : {self._hovered_face.node_name} ({hx}, {hy}, {hz}) "
                f"-> Pose à ({px}, {py}, {pz}) | Total Blocs : {len(self.engine.voxels)}"
            )
        elif self._hovered_ground_cell:
            gx, gy, gz = self._hovered_ground_cell
            status = f"📐 Case Grille Sol pointée : ({gx}, {gy}, {gz}) — Cliquez pour poser le premier bloc | Total Blocs : {len(self.engine.voxels)}"
        else:
            status = f"Total Blocs dans la structure : {len(self.engine.voxels)}"

        bar_b = QRectF(10, self.height() - 34, 720, 26)
        painter.fillRect(bar_b, QColor(15, 23, 42, 195))
        painter.setPen(QColor("#38bdf8"))
        painter.drawText(bar_b.adjusted(10, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter, status)

    # =========================================================================
    # RAYCAST SUR LES BLOCS ET SUR LA GRILLE AU SOL (MÊME EN MONDE VIDE)
    # =========================================================================
    def _raycast_at(self, pos: QPointF) -> Optional[ProjectedVoxelFace]:
        for pface in reversed(self._projected_faces):
            if pface.screen_poly.containsPoint(pos, Qt.FillRule.OddEvenFill):
                return pface
        return None

    def _raycast_ground_grid(self, pos: QPointF) -> Optional[Tuple[int, int, int]]:
        """Trouve la case (gx, 0, gz) sur le plan Y=0 sous le curseur de la souris."""
        p0 = self._project_pt((0.0, 0.0, 0.0))
        px = self._project_pt((1.0, 0.0, 0.0))
        pz = self._project_pt((0.0, 0.0, 1.0))
        if not (p0 and px and pz):
            return None

        # Résolution du système linéaire 2x2 dans le plan écran autour de la cible caméra
        tx, ty, tz = self.cam_target
        c_orig = self._project_pt((tx, 0.0, tz))
        c_dx = self._project_pt((tx + 1.0, 0.0, tz))
        c_dz = self._project_pt((tx, 0.0, tz + 1.0))
        if not (c_orig and c_dx and c_dz):
            return None

        ux, uy = c_dx[0] - c_orig[0], c_dx[1] - c_orig[1]
        vx, vy = c_dz[0] - c_orig[0], c_dz[1] - c_orig[1]
        det = ux * vy - uy * vx
        if abs(det) < 1e-4:
            return None

        rx, ry = pos.x() - c_orig[0], pos.y() - c_orig[1]
        alpha = (rx * vy - ry * vx) / det
        beta = (ux * ry - uy * rx) / det

        gx = int(math.floor(tx + alpha))
        gz = int(math.floor(tz + beta))
        half = self.engine.grid_size // 2
        if -half <= gx < half and -half <= gz < half:
            return gx, 0, gz
        return None

    def mousePressEvent(self, event):
        self.setFocus()
        pos = QPointF(event.pos())
        self._last_mouse = pos

        if event.button() == Qt.MouseButton.RightButton:
            self._mouse_Rotate = True
            return

        if event.button() == Qt.MouseButton.MiddleButton:
            hit = self._raycast_at(pos)
            if hit:
                self.editor.select_node_in_palette(hit.node_name)
            else:
                self._mouse_Pan = True
            return

        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._raycast_at(pos)
            if hit is not None:
                hx, hy, hz = hit.pos
                dx, dy, dz = VOXEL_NEIGHBORS[hit.face_name]
                place_pos = (hx + dx, hy + dy, hz + dz)

                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    self.engine.apply_brush_at(hx, hy, hz, None, self.editor.brush_radius)
                    self._hovered_face = None
                    return

                mode = self.editor.interaction_tool
                if mode == "place":
                    self.engine.apply_brush_at(
                        place_pos[0], place_pos[1], place_pos[2],
                        self.editor.selected_node, self.editor.brush_radius
                    )
                elif mode == "dig":
                    self.engine.apply_brush_at(hx, hy, hz, None, self.editor.brush_radius)
                elif mode == "replace":
                    self.engine.apply_brush_at(hx, hy, hz, self.editor.selected_node, self.editor.brush_radius)
                elif mode == "pos1":
                    self.engine.pos1 = hit.pos
                    self.editor.update_pos_labels()
                    self.update()
                elif mode == "pos2":
                    self.engine.pos2 = hit.pos
                    self.editor.update_pos_labels()
                    self.update()
                return

            # Si aucun bloc n'est touché, on teste la grille au sol Y=0 (permet de construire dans un Monde Vide !)
            ground_cell = self._raycast_ground_grid(pos)
            if ground_cell is not None and self.editor.interaction_tool == "place":
                gx, gy, gz = ground_cell
                self.engine.apply_brush_at(gx, gy, gz, self.editor.selected_node, self.editor.brush_radius)
                return

            self._mouse_Rotate = True

    def mouseMoveEvent(self, event):
        pos = QPointF(event.pos())
        dx = pos.x() - self._last_mouse.x()
        dy = pos.y() - self._last_mouse.y()
        self._last_mouse = pos

        if self._mouse_Rotate:
            self.cam_yaw += dx * 0.45
            self.cam_pitch = max(-85.0, min(85.0, self.cam_pitch + dy * 0.45))
            self.update()
        elif self._mouse_Pan:
            self.cam_target[0] -= dx * 0.05
            self.cam_target[1] += dy * 0.05
            self.update()
        else:
            self._hovered_face = self._raycast_at(pos)
            if self._hovered_face is None:
                self._hovered_ground_cell = self._raycast_ground_grid(pos)
            else:
                self._hovered_ground_cell = None
            self.update()

    def mouseReleaseEvent(self, event):
        self._mouse_Rotate = False
        self._mouse_Pan = False

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 0.88 if delta > 0 else 1.14
        self.cam_distance = max(4.0, min(260.0, self.cam_distance * factor))
        self.update()

    def keyPressEvent(self, event):
        step = 1.0
        yaw_r = math.radians(self.cam_yaw)
        fx, fz = math.sin(yaw_r), math.cos(yaw_r)
        rx, rz = math.cos(yaw_r), -math.sin(yaw_r)

        key = event.key()
        if key in (Qt.Key.Key_Z, Qt.Key.Key_W, Qt.Key.Key_Up):
            self.cam_target[0] += fx * step
            self.cam_target[2] += fz * step
        elif key in (Qt.Key.Key_S, Qt.Key.Key_Down):
            self.cam_target[0] -= fx * step
            self.cam_target[2] -= fz * step
        elif key in (Qt.Key.Key_Q, Qt.Key.Key_A, Qt.Key.Key_Left):
            self.cam_target[0] -= rx * step
            self.cam_target[2] -= rz * step
        elif key in (Qt.Key.Key_D, Qt.Key.Key_Right):
            self.cam_target[0] += rx * step
            self.cam_target[2] += rz * step
        elif key == Qt.Key.Key_Space:
            self.cam_target[1] += step
        elif key == Qt.Key.Key_C:
            self.cam_target[1] -= step
        else:
            super().keyPressEvent(event)
            return
        self.update()


class WorldEditorWidget(QWidget):
    """
    Atelier Monde Voxel 3D complet :
    - Sélecteur de taille de grille (16x16 jusqu'à 256x256)
    - +42 Blocs Minetest filtrables par catégorie + Blocs 3D Custom du Studio
    - Export et Test direct en Monde Vide (singlenode) dans Luanti.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = VoxelEngine()
        self.selected_node = "default:dirt_with_grass"
        self.interaction_tool = "place"
        self.brush_radius = 0

        self._build_ui()
        self._refresh_block_palette_list()
        self.engine.paletteChanged.connect(self._refresh_block_palette_list)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # =====================================================================
        # BARRE SUPÉRIEURE : OUTILS, TAILLE DE GRILLE, MONDE VIDE & EXPORT
        # =====================================================================
        topbar = QFrame()
        topbar.setProperty("class", "InspectorPanel")
        tb_layout = QHBoxLayout(topbar)
        tb_layout.setContentsMargins(10, 6, 10, 6)

        for label, key in [
            ("🧱 Poser", "place"),
            ("⛏️ Casser", "dig"),
            ("🔄 Remplacer", "replace"),
            ("🚩 Pos 1", "pos1"),
            ("🏁 Pos 2", "pos2"),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, k=key: self._set_tool(k))
            tb_layout.addWidget(btn)

        tb_layout.addWidget(QLabel("Pinceau :"))
        self.spn_radius = QSpinBox()
        self.spn_radius.setRange(0, 4)
        self.spn_radius.valueChanged.connect(self._on_radius_changed)
        tb_layout.addWidget(self.spn_radius)

        # Sélecteur de Taille de Grille (jusqu'à 256x256 pour les très grandes structures)
        tb_layout.addWidget(QLabel("📐 Grille :"))
        self.combo_grid_size = QComboBox()
        for lbl, gval in WORLD_GRID_SIZES:
            self.combo_grid_size.addItem(lbl, gval)
        self.combo_grid_size.setCurrentIndex(1)  # 32x32 par défaut
        self.combo_grid_size.currentIndexChanged.connect(self._on_grid_size_changed)
        tb_layout.addWidget(self.combo_grid_size)

        tb_layout.addWidget(QLabel("🌍 Terrain :"))
        self.combo_preset = QComboBox()
        self.combo_preset.addItems([
            "Vallée Minetest (Herbe + Arbre + Eau)",
            "🌌 Monde Vide (Construire sur la grille)",
            "Plateforme Plate",
            "Île Flottante Minetest",
            "Donjon en Pierre & Or",
        ])
        self.combo_preset.currentIndexChanged.connect(self._on_preset_selected)
        tb_layout.addWidget(self.combo_preset)

        self.chk_void_world = QCheckBox("🌌 Exporter en Monde Vide (Singlenode) + Auto-Spawn In-Game")
        self.chk_void_world.setChecked(True)
        self.chk_void_world.setStyleSheet("color: #38bdf8; font-weight: bold;")
        self.chk_void_world.toggled.connect(self._on_void_world_toggled)
        tb_layout.addWidget(self.chk_void_world)

        tb_layout.addStretch()

        btn_undo = QPushButton("↩️ Annuler")
        btn_undo.clicked.connect(self.engine.undo)
        tb_layout.addWidget(btn_undo)

        btn_export_mts = QPushButton("💾 Exporter (.mts)")
        btn_export_mts.setObjectName("PrimaryButton")
        btn_export_mts.clicked.connect(self._export_world_schematic)
        tb_layout.addWidget(btn_export_mts)

        root.addWidget(topbar)

        # =====================================================================
        # ZONE CENTRALE : CATALOGUE DE +42 BLOCS + VIEWPORT VOXEL 3D
        # =====================================================================
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = QFrame()
        left_panel.setProperty("class", "InspectorPanel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

        lbl_cat = QLabel("🗂️ Filtrer par Catégorie de Blocs :")
        lbl_cat.setStyleSheet("font-weight: bold; color: #93c5fd;")
        left_layout.addWidget(lbl_cat)

        self.combo_cat_filter = QComboBox()
        self.combo_cat_filter.addItems([
            "Toutes les catégories (+42 blocs)",
            "⭐ Blocs Custom du Mod",
            "🌿 Nature & Sols",
            "🪨 Pierres & Minerais",
            "🌲 Bois & Végétation",
            "🧱 Construction & Lumière",
            "💧 Liquides",
        ])
        self.combo_cat_filter.currentIndexChanged.connect(self._refresh_block_palette_list)
        left_layout.addWidget(self.combo_cat_filter)

        self.inp_search_block = QLineEdit()
        self.inp_search_block.setPlaceholderText("🔍 Rechercher un bloc (ex: or, verre, bois, mese)...")
        self.inp_search_block.textChanged.connect(self._refresh_block_palette_list)
        left_layout.addWidget(self.inp_search_block)

        self.palette_list = QListWidget()
        self.palette_list.currentRowChanged.connect(self._on_palette_row_changed)
        left_layout.addWidget(self.palette_list, 1)

        grp_we = QGroupBox("🪄 Commandes WorldEdit (Pos1 ↔ Pos2)")
        we_layout = QVBoxLayout(grp_we)

        self.lbl_pos12 = QLabel("Pos1: Non défini | Pos2: Non défini")
        self.lbl_pos12.setStyleSheet("color: #facc15; font-size: 11px;")
        we_layout.addWidget(self.lbl_pos12)

        btn_we_set = QPushButton("📦 //set (Remplir avec le bloc actif)")
        btn_we_set.clicked.connect(lambda: self.engine.worldedit_fill_region(self.selected_node, hollow_only=False))
        we_layout.addWidget(btn_we_set)

        btn_we_hollow = QPushButton("🏰 //hollow (Murs / Boîte creuse)")
        btn_we_hollow.clicked.connect(lambda: self.engine.worldedit_fill_region(self.selected_node, hollow_only=True))
        we_layout.addWidget(btn_we_hollow)

        btn_we_air = QPushButton("🧨 //set air (Vider la zone)")
        btn_we_air.setObjectName("DangerButton")
        btn_we_air.clicked.connect(lambda: self.engine.worldedit_fill_region("air", hollow_only=False))
        we_layout.addWidget(btn_we_air)

        left_layout.addWidget(grp_we)
        splitter.addWidget(left_panel)

        # Viewport 3D + Hotbar
        right_container = QFrame()
        right_container.setProperty("class", "InspectorPanel")
        rc_layout = QVBoxLayout(right_container)
        rc_layout.setContentsMargins(6, 6, 6, 6)
        rc_layout.setSpacing(6)

        self.viewport = MinetestVoxelViewport3D(self.engine, self)
        rc_layout.addWidget(self.viewport, 1)

        self.hotbar_frame = QFrame()
        self.hotbar_frame.setStyleSheet("background-color: #0f131a; border: 1px solid #334155; border-radius: 6px;")
        self.hotbar_layout = QHBoxLayout(self.hotbar_frame)
        self.hotbar_layout.setContentsMargins(8, 4, 8, 4)
        rc_layout.addWidget(self.hotbar_frame)

        splitter.addWidget(right_container)
        splitter.setSizes([310, 1020])
        root.addWidget(splitter, 1)

    def _refresh_block_palette_list(self):
        self.palette_list.blockSignals(True)
        self.palette_list.clear()

        while self.hotbar_layout.count():
            child = self.hotbar_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.hotbar_layout.addWidget(QLabel("🎒 Hotbar :"))

        cat_filter = self.combo_cat_filter.currentText()
        search_txt = self.inp_search_block.text().strip().lower()

        # Place toujours les Blocs Custom du Mod en haut de la liste
        sorted_defs = sorted(
            self.engine.block_defs.values(),
            key=lambda b: (0 if b.custom_model_data is not None else 1, b.category, b.display_name)
        )

        hb_count = 0
        for bdef in sorted_defs:
            if not cat_filter.startswith("Toutes") and bdef.category != cat_filter:
                continue
            if search_txt and (search_txt not in bdef.display_name.lower() and search_txt not in bdef.node_name.lower()):
                continue

            icon_pix = QPixmap.fromImage(
                bdef.side_tex.scaled(28, 28, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
            )
            item = QListWidgetItem(QIcon(icon_pix), f"{bdef.display_name}\n[{bdef.node_name}]")
            item.setData(Qt.ItemDataRole.UserRole, bdef.node_name)
            self.palette_list.addItem(item)

            if hb_count < 9:
                hb_btn = QPushButton(bdef.display_name.replace("★ ", "")[:12])
                hb_btn.setIcon(QIcon(icon_pix))
                hb_btn.clicked.connect(lambda checked, n=bdef.node_name: self.select_node_in_palette(n))
                self.hotbar_layout.addWidget(hb_btn)
                hb_count += 1

        self.hotbar_layout.addStretch()
        self.palette_list.blockSignals(False)
        self.select_node_in_palette(self.selected_node)

    def select_node_in_palette(self, node_name: str):
        if node_name not in self.engine.block_defs:
            return
        self.selected_node = node_name
        for i in range(self.palette_list.count()):
            it = self.palette_list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == node_name:
                self.palette_list.setCurrentRow(i)
                break

    def _on_palette_row_changed(self, row: int):
        it = self.palette_list.item(row)
        if it:
            self.selected_node = it.data(Qt.ItemDataRole.UserRole)
            if self.interaction_tool in ("dig", "pos1", "pos2"):
                self.interaction_tool = "place"

    def _set_tool(self, tool_key: str):
        self.interaction_tool = tool_key

    def _on_radius_changed(self, val: int):
        self.brush_radius = val

    def _on_grid_size_changed(self, idx: int):
        gval = self.combo_grid_size.itemData(idx)
        if gval:
            self.engine.set_grid_size(int(gval))
            self.viewport.cam_distance = max(18.0, gval * 0.75)
            self.viewport.update()

    def _on_void_world_toggled(self, checked: bool):
        self.engine.export_void_world = checked
        self.viewport.update()

    def update_pos_labels(self):
        p1 = str(self.engine.pos1) if self.engine.pos1 else "Non défini"
        p2 = str(self.engine.pos2) if self.engine.pos2 else "Non défini"
        self.lbl_pos12.setText(f"Pos1: {p1}  |  Pos2: {p2}")

    def _on_preset_selected(self, idx: int):
        presets = ["minetest_valley", "empty_void", "flat_platform", "floating_island", "stone_dungeon"]
        if 0 <= idx < len(presets):
            self.engine.generate_terrain_preset(presets[idx])

    def _export_world_schematic(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter le monde Voxel en Schématique Luanti (.mts)",
            "structure_luanti.mts", "Minetest Schematic (*.mts)"
        )
        if path:
            exporter = MtsExporter()
            exporter.export_voxels_to_mts(self.engine.voxels, path)
            lua_path = path.rsplit(".", 1)[0] + "_place.lua"
            exporter.export_voxels_to_lua_script(self.engine.voxels, lua_path)
            QMessageBox.information(
                self, "Export réussi",
                f"Structure Voxel exportée avec succès :\n• Binaire MTS : {path}\n• Script Lua : {lua_path}"
            )