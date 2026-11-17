# -*- coding: utf-8 -*-
"""
engine/renderer/panda_viewport.py
Viewport 3D interactif avec support MagicaVoxel :
- Mode Transformation 3D (Déplacer, Taille, Tourner Bone, Pivot)
- Mode Peinture 3D Directe au texel près
- NOUVEAU : Mode Sculpture Voxel 3D (Poser Voxel, Creuser Voxel, Estampiller Forme 3D au clic sur face ou grille sol)
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
    from PyQt6.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QImage,
        QPolygonF, QTransform, QLinearGradient
    )
    from PyQt6.QtWidgets import QWidget
except ImportError:
    from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal
    from PyQt5.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QImage,
        QPolygonF, QTransform, QLinearGradient
    )
    from PyQt5.QtWidgets import QWidget

from engine.model_loader.model_data import ModelData, ModelCube, ModelBone, FaceUVRect


LUANTI_FACE_LIGHTING: Dict[str, float] = {
    "top": 1.00,
    "north": 0.82,
    "south": 0.80,
    "east": 0.64,
    "west": 0.62,
    "bottom": 0.44,
}

FACE_NORMALS_INT: Dict[str, Tuple[int, int, int]] = {
    "top":    (0, 1, 0),
    "bottom": (0, -1, 0),
    "north":  (0, 0, 1),
    "south":  (0, 0, -1),
    "east":   (1, 0, 0),
    "west":   (-1, 0, 0),
}


@dataclass
class ProjectedFaceQuad:
    cube: ModelCube
    face_name: str
    screen_poly: QPolygonF
    depth_z: float
    uv_rect: FaceUVRect
    unit_to_screen: QTransform
    screen_to_unit: QTransform
    has_inverse: bool


class PandaViewport(QWidget):
    """
    Viewport 3D temps réel pour Mobs, Blocks et Items (Transform + Paint 3D + MagicaVoxel Sculpt).
    """
    cubeClicked = pyqtSignal(str)
    texelPainted3D = pyqtSignal(int, int, str)
    colorPicked3D = pyqtSignal(QColor)
    transformDragged = pyqtSignal()
    voxelClicked3D = pyqtSignal(int, int, int, int, int, int)  # hit_vx, hit_vy, hit_vz, place_vx, place_vy, place_vz

    def __init__(self, model_data: Optional[ModelData] = None, interaction_mode: str = "transform", parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 320)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.model_data = model_data or ModelData("Mobs")
        self.interaction_mode = interaction_mode  # "transform", "paint_3d", "voxel_sculpt"
        self.transform_tool = "move"              # "move", "scale", "rotate", "pivot"
        self.preview_context = "world"            # "world", "wield", "inventory"
        self.show_bones_and_pivots = True
        self.show_wireframe = True

        # Paramètres du pinceau 3D & Voxel
        self.paint_tool = "pencil"
        self.paint_color = QColor("#38bdf8")
        self.paint_brush_size = 1

        # Caméra orbitale 3D
        self.cam_yaw = -38.0
        self.cam_pitch = 24.0
        self.cam_distance = 44.0
        self.cam_target = [0.0, 7.0, 0.0]

        self._last_mouse_pos = QPointF(0, 0)
        self._mouse_action: Optional[str] = None
        self._active_gizmo_axis: Optional[int] = None
        self._projected_faces: List[ProjectedFaceQuad] = []
        self._hovered_hit: Optional[Tuple[ProjectedFaceQuad, int, int]] = None
        self._hovered_floor_voxel: Optional[Tuple[int, int, int]] = None
        self._gizmo_screen_handles: Dict[int, QPointF] = {}

        self._bind_model_signals()

    def set_model_data(self, model_data: ModelData):
        if self.model_data is not None:
            try:
                self.model_data.modelChanged.disconnect(self.update)
                self.model_data.textureChanged.disconnect(self.update)
                self.model_data.selectionChanged.disconnect(self.update)
            except Exception:
                pass
        self.model_data = model_data
        self._bind_model_signals()
        self.update()

    def _bind_model_signals(self):
        if self.model_data:
            try:
                self.model_data.modelChanged.connect(self.update)
                self.model_data.textureChanged.connect(self.update)
                self.model_data.selectionChanged.connect(self.update)
            except Exception:
                pass

    def set_grid_size(self, grid_size: int):
        self.model_data.grid_size = max(16, int(grid_size))
        self.cam_distance = max(36.0, self.model_data.grid_size * 2.4)
        self.update()

    # =========================================================================
    # MATHÉMATIQUES 3D & HIÉRARCHIE DES BONES
    # =========================================================================
    @staticmethod
    def _rotate_xyz(pt: Tuple[float, float, float], rx_deg: float, ry_deg: float, rz_deg: float) -> Tuple[float, float, float]:
        x, y, z = pt
        if rx_deg != 0.0:
            r = math.radians(rx_deg)
            c, s = math.cos(r), math.sin(r)
            y, z = y * c - z * s, y * s + z * c
        if ry_deg != 0.0:
            r = math.radians(ry_deg)
            c, s = math.cos(r), math.sin(r)
            x, z = x * c + z * s, -x * s + z * c
        if rz_deg != 0.0:
            r = math.radians(rz_deg)
            c, s = math.cos(r), math.sin(r)
            x, y = x * c - y * s, x * s + y * c
        return x, y, z

    def _transform_vertex_by_cube_and_bones(self, local_pt: Tuple[float, float, float], cube: ModelCube) -> Tuple[float, float, float]:
        px, py, pz = cube.pivot
        rx, ry, rz = cube.rotation
        vx, vy, vz = local_pt[0] - px, local_pt[1] - py, local_pt[2] - pz
        vx, vy, vz = self._rotate_xyz((vx, vy, vz), rx, ry, rz)
        vx, vy, vz = vx + px, vy + py, vz + pz

        visited = set()
        bname = cube.bone_name
        while bname and bname in self.model_data.bones and bname not in visited:
            visited.add(bname)
            bone: ModelBone = self.model_data.bones[bname]
            bpx, bpy, bpz = bone.pivot
            brx, bry, brz = bone.rotation
            box, boy, boz = bone.position

            vx, vy, vz = vx - bpx, vy - bpy, vz - bpz
            vx, vy, vz = self._rotate_xyz((vx, vy, vz), brx, bry, brz)
            vx, vy, vz = vx + bpx + box, vy + bpy + boy, vz + bpz + boz
            bname = bone.parent_name

        if self.preview_context == "wield":
            vx, vy, vz = self._rotate_xyz((vx, vy, vz), 15.0, -35.0, -10.0)
            vx += 4.5
            vy -= 2.0

        return vx, vy, vz

    def _project_3d_to_screen(self, pt3d: Tuple[float, float, float]) -> Optional[Tuple[float, float, float]]:
        w = max(1, self.width())
        h = max(1, self.height())

        x = pt3d[0] - self.cam_target[0]
        y = pt3d[1] - self.cam_target[1]
        z = pt3d[2] - self.cam_target[2]

        yaw_r = math.radians(self.cam_yaw)
        cy, sy = math.cos(yaw_r), math.sin(yaw_r)
        x1 = x * cy - z * sy
        z1 = x * sy + z * cy

        pitch_r = math.radians(self.cam_pitch)
        cp, sp = math.cos(pitch_r), math.sin(pitch_r)
        y2 = y * cp - z1 * sp
        z2 = y * sp + z1 * cp

        cam_z = self.cam_distance - z2
        if cam_z < 1.5:
            return None

        if self.preview_context == "inventory":
            scale = min(w, h) / 26.0
            sx = w * 0.5 + x1 * scale
            sy = h * 0.55 - y2 * scale
            return sx, sy, cam_z

        fov_scale = min(w, h) * 0.92
        sx = w * 0.5 + (x1 * fov_scale) / cam_z
        sy = h * 0.54 - (y2 * fov_scale) / cam_z
        return sx, sy, cam_z

    # =========================================================================
    # RENDU PRINCIPAL DU VIEWPORT 3D
    # =========================================================================
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        bg = QLinearGradient(0, 0, 0, self.height())
        if self.preview_context == "world":
            bg.setColorAt(0.0, QColor("#162032"))
            bg.setColorAt(1.0, QColor("#0f141d"))
        elif self.preview_context == "wield":
            bg.setColorAt(0.0, QColor("#1b2838"))
            bg.setColorAt(1.0, QColor("#121822"))
        else:
            bg.setColorAt(0.0, QColor("#181a20"))
            bg.setColorAt(1.0, QColor("#101216"))
        painter.fillRect(self.rect(), bg)

        self._draw_luanti_floor_grid(painter)

        self._projected_faces.clear()
        for cube in self.model_data.cubes:
            if not cube.visible:
                continue
            bone = self.model_data.bones.get(cube.bone_name)
            if bone and not bone.visible:
                continue
            self._collect_cube_faces(cube)

        self._projected_faces.sort(key=lambda f: f.depth_z, reverse=True)

        for pface in self._projected_faces:
            self._draw_textured_luanti_face(painter, pface)

        if self.interaction_mode in ("paint_3d", "voxel_sculpt"):
            if self._hovered_hit is not None:
                self._draw_3d_hovered_texel_cursor(painter, *self._hovered_hit)
            elif self.interaction_mode == "voxel_sculpt" and self._hovered_floor_voxel is not None:
                self._draw_floor_voxel_cursor(painter, self._hovered_floor_voxel)

        if self.show_bones_and_pivots and self.interaction_mode == "transform":
            self._draw_bones_and_gizmo(painter)

        self._draw_hud_overlay(painter)

    def _draw_luanti_floor_grid(self, painter: QPainter):
        gsize = getattr(self.model_data, "grid_size", 16)
        half = gsize // 2
        step = 1 if (self.interaction_mode == "voxel_sculpt" and gsize <= 32) else (2 if gsize <= 32 else (4 if gsize <= 64 else 8))

        grid_pen = QPen(QColor(255, 255, 255, 24), 1.0)
        block_border_pen = QPen(QColor(56, 189, 248, 85), 1.2)
        outer_pen = QPen(QColor("#38bdf8"), 1.8)

        for i in range(-half, half + 1, step):
            if abs(i) == half:
                pen = outer_pen
            elif i % 8 == 0:
                pen = block_border_pen
            else:
                pen = grid_pen

            p1 = self._project_3d_to_screen((float(i), 0.0, float(-half)))
            p2 = self._project_3d_to_screen((float(i), 0.0, float(half)))
            if p1 and p2:
                painter.setPen(pen)
                painter.drawLine(QPointF(p1[0], p1[1]), QPointF(p2[0], p2[1]))

            p3 = self._project_3d_to_screen((float(-half), 0.0, float(i)))
            p4 = self._project_3d_to_screen((float(half), 0.0, float(i)))
            if p3 and p4:
                painter.setPen(pen)
                painter.drawLine(QPointF(p3[0], p3[1]), QPointF(p4[0], p4[1]))

        north_pt = self._project_3d_to_screen((0.0, 0.0, float(half + 2.5)))
        if north_pt:
            painter.setPen(QColor("#60a5fa"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            blocks_count = max(1, gsize // 16)
            painter.drawText(
                QPointF(north_pt[0] - 48, north_pt[1]),
                f"▲ AVANT (+Z) [{gsize}×{gsize}px = {blocks_count}×{blocks_count} blocs]"
            )

    def _draw_floor_voxel_cursor(self, painter: QPainter, cell: Tuple[int, int, int]):
        gx, gy, gz = cell
        c0 = self._project_3d_to_screen((float(gx), float(gy), float(gz)))
        c1 = self._project_3d_to_screen((float(gx + 1), float(gy), float(gz)))
        c2 = self._project_3d_to_screen((float(gx + 1), float(gy), float(gz + 1)))
        c3 = self._project_3d_to_screen((float(gx), float(gy), float(gz + 1)))
        if c0 and c1 and c2 and c3:
            poly = QPolygonF([
                QPointF(c0[0], c0[1]), QPointF(c1[0], c1[1]),
                QPointF(c2[0], c2[1]), QPointF(c3[0], c3[1]),
            ])
            painter.setBrush(QBrush(QColor(250, 204, 21, 90)))
            painter.setPen(QPen(QColor("#facc15"), 2.0))
            painter.drawPolygon(poly)

    def _collect_cube_faces(self, cube: ModelCube):
        x0, y0, z0 = cube.position
        w, h, d = cube.size
        x1, y1, z1 = x0 + w, y0 + h, z0 + d

        v = [
            (x0, y0, z0),
            (x1, y0, z0),
            (x1, y1, z0),
            (x0, y1, z0),
            (x0, y0, z1),
            (x1, y0, z1),
            (x1, y1, z1),
            (x0, y1, z1),
        ]
        tv = [self._transform_vertex_by_cube_and_bones(pt, cube) for pt in v]

        face_indices = {
            "top":    (3, 2, 6, 7),
            "bottom": (4, 5, 1, 0),
            "north":  (7, 6, 5, 4),
            "south":  (2, 3, 0, 1),
            "east":   (6, 2, 1, 5),
            "west":   (3, 7, 4, 0),
        }
        uv_rects = cube.get_face_uv_rects()

        for fname, (i0, i1, i2, i3) in face_indices.items():
            s0 = self._project_3d_to_screen(tv[i0])
            s1 = self._project_3d_to_screen(tv[i1])
            s2 = self._project_3d_to_screen(tv[i2])
            s3 = self._project_3d_to_screen(tv[i3])
            if not (s0 and s1 and s2 and s3):
                continue

            poly = QPolygonF([
                QPointF(s0[0], s0[1]),
                QPointF(s1[0], s1[1]),
                QPointF(s2[0], s2[1]),
                QPointF(s3[0], s3[1]),
            ])

            avg_depth = (s0[2] + s1[2] + s2[2] + s3[2]) * 0.25
            uv_r = uv_rects[fname]

            unit_poly = QPolygonF([
                QPointF(0.0, 0.0),
                QPointF(1.0, 0.0),
                QPointF(1.0, 1.0),
                QPointF(0.0, 1.0),
            ])
            unit_to_scr = QTransform()
            ok_quad = QTransform.quadToQuad(unit_poly, poly, unit_to_scr)
            if not ok_quad:
                continue
            scr_to_unit, inv_ok = unit_to_scr.inverted()

            self._projected_faces.append(
                ProjectedFaceQuad(
                    cube=cube,
                    face_name=fname,
                    screen_poly=poly,
                    depth_z=avg_depth,
                    uv_rect=uv_r,
                    unit_to_screen=unit_to_scr,
                    screen_to_unit=scr_to_unit,
                    has_inverse=inv_ok,
                )
            )

    def _draw_textured_luanti_face(self, painter: QPainter, pface: ProjectedFaceQuad):
        r = pface.uv_rect
        atlas = self.model_data.texture_image

        sub_img = atlas.copy(r.u, r.v, max(1, r.w), max(1, r.h))
        crisp_w = max(16, r.w * 16)
        crisp_h = max(16, r.h * 16)
        crisp_img = sub_img.scaled(
            crisp_w, crisp_h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation
        )

        src_poly = QPolygonF([
            QPointF(0.0, 0.0),
            QPointF(float(crisp_w), 0.0),
            QPointF(float(crisp_w), float(crisp_h)),
            QPointF(0.0, float(crisp_h)),
        ])
        tex_transform = QTransform()
        if QTransform.quadToQuad(src_poly, pface.screen_poly, tex_transform):
            painter.save()
            painter.setTransform(tex_transform)
            painter.drawImage(0, 0, crisp_img)
            painter.restore()

        light_ratio = LUANTI_FACE_LIGHTING.get(pface.face_name, 0.8)
        dark_alpha = int(round((1.0 - light_ratio) * 210))
        if dark_alpha > 0:
            painter.setBrush(QBrush(QColor(0, 0, 0, dark_alpha)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(pface.screen_poly)

        is_sel = (pface.cube.cube_id == self.model_data.selected_cube_id)
        if is_sel:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#facc15"), 1.8))
            painter.drawPolygon(pface.screen_poly)
        elif self.show_wireframe:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(15, 23, 42, 110), 0.8))
            painter.drawPolygon(pface.screen_poly)

    def _draw_3d_hovered_texel_cursor(self, painter: QPainter, pface: ProjectedFaceQuad, tx: int, ty: int):
        r = pface.uv_rect
        lx = tx - r.u
        ly = ty - r.v
        if not (0 <= lx < r.w and 0 <= ly < r.h):
            return

        u0 = lx / float(r.w)
        v0 = ly / float(r.h)
        u1 = (lx + 1) / float(r.w)
        v1 = (ly + 1) / float(r.h)

        pix_poly = QPolygonF([
            pface.unit_to_screen.map(QPointF(u0, v0)),
            pface.unit_to_screen.map(QPointF(u1, v0)),
            pface.unit_to_screen.map(QPointF(u1, v1)),
            pface.unit_to_screen.map(QPointF(u0, v1)),
        ])
        col = QColor("#facc15") if self.interaction_mode == "voxel_sculpt" else self.paint_color
        painter.setBrush(QBrush(QColor(col.red(), col.green(), col.blue(), 155)))
        painter.setPen(QPen(QColor("#ffffff"), 2.0))
        painter.drawPolygon(pix_poly)

    def _draw_bones_and_gizmo(self, painter: QPainter):
        self._gizmo_screen_handles.clear()

        for bname, bone in self.model_data.bones.items():
            s_piv = self._project_3d_to_screen(tuple(bone.pivot))
            if s_piv:
                is_active_bone = (bname == self.model_data.selected_bone_name)
                col = QColor("#38bdf8") if is_active_bone else QColor("#94a3b8")
                painter.setBrush(QBrush(col))
                painter.setPen(QPen(QColor("#0f172a"), 1.5))
                radius = 5.5 if is_active_bone else 4.0
                painter.drawEllipse(QPointF(s_piv[0], s_piv[1]), radius, radius)

        sel_cube = self.model_data.get_selected_cube()
        if not sel_cube:
            return

        if self.transform_tool in ("rotate", "pivot"):
            origin_3d = tuple(sel_cube.pivot)
        else:
            origin_3d = (
                sel_cube.position[0] + sel_cube.size[0] * 0.5,
                sel_cube.position[1] + sel_cube.size[1] * 0.5,
                sel_cube.position[2] + sel_cube.size[2] * 0.5,
            )
            origin_3d = self._transform_vertex_by_cube_and_bones(origin_3d, sel_cube)

        s_orig = self._project_3d_to_screen(origin_3d)
        if not s_orig:
            return

        axes = [
            (0, (origin_3d[0] + 4.5, origin_3d[1], origin_3d[2]), QColor("#ef4444"), "X"),
            (1, (origin_3d[0], origin_3d[1] + 4.5, origin_3d[2]), QColor("#22c55e"), "Y"),
            (2, (origin_3d[0], origin_3d[1], origin_3d[2] + 4.5), QColor("#3b82f6"), "Z"),
        ]

        for axis_idx, tip_3d, col, label in axes:
            s_tip = self._project_3d_to_screen(tip_3d)
            if not s_tip:
                continue
            p_orig = QPointF(s_orig[0], s_orig[1])
            p_tip = QPointF(s_tip[0], s_tip[1])
            self._gizmo_screen_handles[axis_idx] = p_tip

            painter.setPen(QPen(col, 2.8))
            painter.drawLine(p_orig, p_tip)
            painter.setBrush(QBrush(col))
            painter.drawEllipse(p_tip, 6.0, 6.0)
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.drawText(p_tip + QPointF(6, -4), label)

    def _draw_hud_overlay(self, painter: QPainter):
        if self.interaction_mode == "voxel_sculpt":
            mode_txt = "🧊 Mode MagicaVoxel 3D — Clic Gauche: Poser/Estampiller Voxel | Shift+Clic: Creuser Voxel | Clic Droit: Orbite"
        elif self.interaction_mode == "paint_3d":
            mode_txt = "🎨 Mode Peinture 3D Directe — Clic Gauche: Peindre sur le Cube | Clic Droit: Tourner Caméra"
        else:
            mode_txt = f"🧊 Mode 3D ({self.transform_tool.upper()}) — Clic Gauche: Sélection/Gizmo | Clic Droit: Orbite | Molette: Zoom"

        painter.setPen(QColor("#e2e8f0"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(12, 20, mode_txt)

        if self._hovered_hit is not None:
            pface, tx, ty = self._hovered_hit
            hit_v, place_v = self._compute_3d_voxel_from_face_hit(pface, tx, ty)
            info = f"Cube: {pface.cube.name} | Face: {pface.face_name.upper()} | Voxel: {hit_v} -> Pose: {place_v}"
            painter.setPen(QColor("#38bdf8"))
            painter.drawText(12, self.height() - 12, info)
        elif self._hovered_floor_voxel is not None and self.interaction_mode == "voxel_sculpt":
            painter.setPen(QColor("#facc15"))
            painter.drawText(12, self.height() - 12, f"📐 Case Grille Sol pointée : {self._hovered_floor_voxel}")

    # =========================================================================
    # CALCUL EXACT DE LA COORDONNÉE VOXEL 3D DEPUIS UNE FACE OU LA GRILLE SOL
    # =========================================================================
    @staticmethod
    def _compute_3d_voxel_from_face_hit(
        pface: ProjectedFaceQuad, tx: int, ty: int
    ) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        """
        Convertit le texel cliqué (tx, ty) sur une face de ModelCube en :
        - hit_voxel : coordonnée (vx, vy, vz) du voxel touché à l'intérieur du cube
        - place_voxel : coordonnée (px, py, pz) du voxel adjacent contre cette face
        """
        cube = pface.cube
        r = pface.uv_rect
        lx = max(0, min(r.w - 1, tx - r.u))
        ly = max(0, min(r.h - 1, ty - r.v))

        x0 = int(round(cube.position[0]))
        y0 = int(round(cube.position[1]))
        z0 = int(round(cube.position[2]))
        w, h, d = cube.get_pixel_dimensions()

        fname = pface.face_name
        if fname == "top":
            vx, vy, vz = x0 + (w - 1 - lx), y0 + h - 1, z0 + ly
        elif fname == "bottom":
            vx, vy, vz = x0 + lx, y0, z0 + (d - 1 - ly)
        elif fname == "north":
            vx, vy, vz = x0 + (w - 1 - lx), y0 + (h - 1 - ly), z0 + d - 1
        elif fname == "south":
            vx, vy, vz = x0 + lx, y0 + (h - 1 - ly), z0
        elif fname == "east":
            vx, vy, vz = x0 + w - 1, y0 + (h - 1 - ly), z0 + (d - 1 - lx)
        else:  # west
            vx, vy, vz = x0, y0 + (h - 1 - ly), z0 + lx

        nx, ny, nz = FACE_NORMALS_INT.get(fname, (0, 1, 0))
        return (vx, vy, vz), (vx + nx, vy + ny, vz + nz)

    def _raycast_floor_grid(self, pos: QPointF) -> Optional[Tuple[int, int, int]]:
        tx, _, tz = self.cam_target
        c_orig = self._project_3d_to_screen((tx, 0.0, tz))
        c_dx = self._project_3d_to_screen((tx + 1.0, 0.0, tz))
        c_dz = self._project_3d_to_screen((tx, 0.0, tz + 1.0))
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
        half = getattr(self.model_data, "grid_size", 16) // 2
        if -half <= gx < half and -half <= gz < half:
            return gx, 0, gz
        return None

    # =========================================================================
    # RAYCASTING 3D & SOURIS
    # =========================================================================
    def _raycast_screen_pos(self, pos: QPointF) -> Optional[Tuple[ProjectedFaceQuad, int, int]]:
        for pface in reversed(self._projected_faces):
            if pface.screen_poly.containsPoint(pos, Qt.FillRule.OddEvenFill) and pface.has_inverse:
                unit_pt = pface.screen_to_unit.map(pos)
                u = max(0.0, min(0.9999, unit_pt.x()))
                v = max(0.0, min(0.9999, unit_pt.y()))
                r = pface.uv_rect
                tx = r.u + int(u * r.w)
                ty = r.v + int(v * r.h)
                return pface, tx, ty
        return None

    def _find_gizmo_axis_at(self, pos: QPointF) -> Optional[int]:
        for axis_idx, handle_pt in self._gizmo_screen_handles.items():
            if (pos - handle_pt).manhattanLength() <= 16.0:
                return axis_idx
        return None

    def mousePressEvent(self, event):
        pos = QPointF(event.pos())
        self._last_mouse_pos = pos

        if event.button() == Qt.MouseButton.RightButton:
            self._mouse_action = "orbit"
            return

        if event.button() == Qt.MouseButton.MiddleButton:
            self._mouse_action = "pan"
            return

        if event.button() == Qt.MouseButton.LeftButton:
            # 1. Mode Sculpture MagicaVoxel 3D
            if self.interaction_mode == "voxel_sculpt":
                hit = self._raycast_screen_pos(pos)
                if hit is not None:
                    pface, tx, ty = hit
                    self.model_data.select_cube(pface.cube.cube_id)
                    hit_v, place_v = self._compute_3d_voxel_from_face_hit(pface, tx, ty)
                    if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                        self.model_data.sculpt_voxel_at(hit_v, mode="erase")
                    else:
                        self.voxelClicked3D.emit(
                            hit_v[0], hit_v[1], hit_v[2],
                            place_v[0], place_v[1], place_v[2]
                        )
                    return

                floor_v = self._raycast_floor_grid(pos)
                if floor_v is not None:
                    fx, fy, fz = floor_v
                    self.voxelClicked3D.emit(fx, fy, fz, fx, fy, fz)
                    return

                self._mouse_action = "orbit"
                return

            # 2. Mode Peinture 3D Directe
            if self.interaction_mode == "paint_3d":
                hit = self._raycast_screen_pos(pos)
                if hit:
                    pface, tx, ty = hit
                    self.model_data.select_cube(pface.cube.cube_id)
                    if self.paint_tool != "eyedropper":
                        self.model_data.push_undo_snapshot()
                    self._apply_3d_paint_at(pface, tx, ty)
                    self._mouse_action = "painting_3d"
                else:
                    self._mouse_action = "orbit"
                return

            # 3. Mode Transformation 3D
            axis = self._find_gizmo_axis_at(pos)
            if axis is not None:
                self._active_gizmo_axis = axis
                self._mouse_action = "drag_gizmo"
                return

            hit = self._raycast_screen_pos(pos)
            if hit:
                pface, _, _ = hit
                self.model_data.select_cube(pface.cube.cube_id)
                self.cubeClicked.emit(pface.cube.cube_id)
                self._active_gizmo_axis = 0
                self._mouse_action = "orbit"
            else:
                self._mouse_action = "orbit"

    def mouseMoveEvent(self, event):
        pos = QPointF(event.pos())
        dx = pos.x() - self._last_mouse_pos.x()
        dy = pos.y() - self._last_mouse_pos.y()
        self._last_mouse_pos = pos

        self._hovered_hit = self._raycast_screen_pos(pos)
        if self._hovered_hit is None and self.interaction_mode == "voxel_sculpt":
            self._hovered_floor_voxel = self._raycast_floor_grid(pos)
        else:
            self._hovered_floor_voxel = None

        if self._mouse_action == "orbit":
            self.cam_yaw += dx * 0.45
            self.cam_pitch = max(-85.0, min(85.0, self.cam_pitch + dy * 0.45))
            self.update()
        elif self._mouse_action == "pan":
            self.cam_target[0] -= dx * 0.05
            self.cam_target[1] += dy * 0.05
            self.update()
        elif self._mouse_action == "painting_3d" and self._hovered_hit is not None:
            pface, tx, ty = self._hovered_hit
            if self.paint_tool not in ("bucket", "eyedropper"):
                self._apply_3d_paint_at(pface, tx, ty)
        elif self._mouse_action == "drag_gizmo" and self._active_gizmo_axis is not None:
            self._apply_gizmo_delta(self._active_gizmo_axis, dx, dy)
        else:
            self.update()

    def mouseReleaseEvent(self, event):
        self._mouse_action = None
        self._active_gizmo_axis = None

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 0.88 if delta > 0 else 1.14
        self.cam_distance = max(10.0, min(320.0, self.cam_distance * factor))
        self.update()

    def _apply_gizmo_delta(self, axis: int, dx: float, dy: float):
        cube = self.model_data.get_selected_cube()
        if not cube:
            return
        step = (dx - dy) * 0.08
        if self.transform_tool == "move":
            cube.position[axis] = round((cube.position[axis] + step) * 2.0) / 2.0
        elif self.transform_tool == "scale":
            cube.size[axis] = max(1.0, round(cube.size[axis] + step))
            self.model_data.auto_pack_uv_atlas(repaint_default_colors=False)
        elif self.transform_tool == "rotate":
            bone = self.model_data.get_selected_bone()
            if bone:
                bone.rotation[axis] = round(bone.rotation[axis] + (dx - dy) * 0.6, 1)
            else:
                cube.rotation[axis] = round(cube.rotation[axis] + (dx - dy) * 0.6, 1)
        elif self.transform_tool == "pivot":
            cube.pivot[axis] = round((cube.pivot[axis] + step) * 2.0) / 2.0
            bone = self.model_data.get_selected_bone()
            if bone:
                bone.pivot[axis] = cube.pivot[axis]

        self.model_data.modelChanged.emit()
        self.transformDragged.emit()

    def _apply_3d_paint_at(self, pface: ProjectedFaceQuad, tx: int, ty: int):
        atlas = self.model_data.texture_image
        if not (0 <= tx < self.model_data.atlas_width and 0 <= ty < self.model_data.atlas_height):
            return

        if self.paint_tool == "eyedropper":
            picked = atlas.pixelColor(tx, ty)
            self.paint_color = picked
            self.colorPicked3D.emit(picked)
            return

        if self.paint_tool == "bucket":
            self.model_data.fill_cube_face(pface.cube, pface.face_name, self.paint_color, noise_strength=0)
        elif self.paint_tool == "noise":
            c = QColor(self.paint_color)
            delta = ((tx * 17 + ty * 31) % 25) - 12
            c = c.lighter(100 + delta) if delta >= 0 else c.darker(100 - delta)
            self.model_data.paint_texel(tx, ty, c, self.paint_brush_size)
        elif self.paint_tool == "lighten":
            cur = atlas.pixelColor(tx, ty)
            self.model_data.paint_texel(tx, ty, cur.lighter(112), self.paint_brush_size)
        elif self.paint_tool == "darken":
            cur = atlas.pixelColor(tx, ty)
            self.model_data.paint_texel(tx, ty, cur.darker(112), self.paint_brush_size)
        elif self.paint_tool == "eraser":
            self.model_data.paint_texel(tx, ty, QColor(0, 0, 0, 0), self.paint_brush_size)
        else:
            self.model_data.paint_texel(tx, ty, self.paint_color, self.paint_brush_size)

        self.texelPainted3D.emit(tx, ty, pface.face_name)