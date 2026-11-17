# -*- coding: utf-8 -*-
"""
engine/voxel/magicavoxel_tools.py
Moteur Géométrique Voxel 3D de style MagicaVoxel :
- 13 Formes 3D/2D Préfaites (Carré, Rectangle, Cube, Boîte, Cercle, Cylindre, Sphère, Dôme, Pyramide, Cône, Tore, Arche, Escalier)
- Tracé de Ligne 3D de Bresenham
- Symétrie Miroir Temps Réel sur 3 Axes (X, Y, Z)
- Opérations Booléennes (Union / Addition, Soustraction / Creusage, Remplacement)
- Algorithme de Greedy Meshing 3D (Fusion optimale de Voxels en ModelCubes Luanti)
"""

import math
from typing import Dict, List, Set, Tuple


MAGICAVOXEL_SHAPES: List[Tuple[str, str]] = [
    ("cube", "🧊 Cube 3D (Plein / Creux)"),
    ("box", "📦 Boîte / Rectangle 3D"),
    ("square", "⬛ Carré Plat 2D (Sol / Cadre)"),
    ("rect", "▭ Rectangle Plat 2D (Dalle / Cadre)"),
    ("circle", "⭕ Cercle / Disque 2D"),
    ("cylinder", "🛢️ Cylindre / Tube 3D"),
    ("sphere", "🔮 Sphère / Ellipsoïde 3D"),
    ("dome", "🕌 Dôme / Hémisphère 3D"),
    ("pyramid", "🔺 Pyramide 3D"),
    ("cone", "🍦 Cône 3D"),
    ("torus", "🍩 Tore / Anneau 3D"),
    ("arch", "🌉 Arche Architecturale 3D"),
    ("stairs", "🪜 Escalier 3D"),
]


class MagicaShapeGenerator:
    """Générateur mathématique de formes Voxel 3D et optimiseur Greedy Meshing."""

    @staticmethod
    def generate_shape_voxels(
        shape_type: str,
        center: Tuple[int, int, int],
        size_xyz: Tuple[int, int, int],
        hollow: bool = False,
        thickness: int = 1,
        axis: str = "Y",
    ) -> Set[Tuple[int, int, int]]:
        """
        Génère l'ensemble des coordonnées entières (x, y, z) composant la forme 3D demandée.
        """
        cx, cy, cz = int(round(center[0])), int(round(center[1])), int(round(center[2]))
        sx = max(1, int(round(size_xyz[0])))
        sy = max(1, int(round(size_xyz[1])))
        sz = max(1, int(round(size_xyz[2])))

        rx = sx / 2.0
        ry = sy / 2.0
        rz = sz / 2.0
        t = max(1, int(thickness))
        axis = axis.upper()
        voxels: Set[Tuple[int, int, int]] = set()

        if shape_type in ("square", "rect"):
            lx = sx
            lz = sx if shape_type == "square" else sz
            hx0 = cx - lx // 2
            hx1 = hx0 + lx - 1
            hz0 = cz - lz // 2
            hz1 = hz0 + lz - 1
            for x in range(hx0, hx1 + 1):
                for z in range(hz0, hz1 + 1):
                    if hollow:
                        if not (x - hx0 < t or hx1 - x < t or z - hz0 < t or hz1 - z < t):
                            continue
                    for dy in range(t):
                        pt = (x, cy + dy, z)
                        voxels.add(MagicaShapeGenerator._orient_point(pt, (cx, cy, cz), axis))

        elif shape_type in ("cube", "box"):
            lx = sx
            ly = sx if shape_type == "cube" else sy
            lz = sx if shape_type == "cube" else sz
            bx0, bx1 = cx - lx // 2, cx - lx // 2 + lx - 1
            by0, by1 = cy, cy + ly - 1
            bz0, bz1 = cz - lz // 2, cz - lz // 2 + lz - 1
            for x in range(bx0, bx1 + 1):
                for y in range(by0, by1 + 1):
                    for z in range(bz0, bz1 + 1):
                        if hollow:
                            on_border = (
                                x - bx0 < t or bx1 - x < t or
                                y - by0 < t or by1 - y < t or
                                z - bz0 < t or bz1 - z < t
                            )
                            if not on_border:
                                continue
                        voxels.add((x, y, z))

        elif shape_type == "circle":
            rad = max(1.0, rx)
            inner_r = max(0.0, rad - t) if hollow else -1.0
            ir = int(math.ceil(rad))
            for u in range(-ir, ir + 1):
                for v in range(-ir, ir + 1):
                    dist = math.sqrt(u * u + v * v)
                    if inner_r <= dist <= rad + 0.25:
                        for dh in range(t):
                            pt = (cx + u, cy + dh, cz + v)
                            voxels.add(MagicaShapeGenerator._orient_point(pt, (cx, cy, cz), axis))

        elif shape_type == "cylinder":
            rad_u = max(1.0, rx)
            rad_v = max(1.0, rz if sz != sx else rx)
            iu, iv = int(math.ceil(rad_u)), int(math.ceil(rad_v))
            for h in range(sy):
                for u in range(-iu, iu + 1):
                    for v in range(-iv, iv + 1):
                        norm_d = math.sqrt((u / rad_u) ** 2 + (v / rad_v) ** 2)
                        if norm_d <= 1.04:
                            if hollow:
                                in_u = max(0.5, rad_u - t)
                                in_v = max(0.5, rad_v - t)
                                if math.sqrt((u / in_u) ** 2 + (v / in_v) ** 2) < 0.96:
                                    continue
                            pt = (cx + u, cy + h, cz + v)
                            voxels.add(MagicaShapeGenerator._orient_point(pt, (cx, cy, cz), axis))

        elif shape_type in ("sphere", "dome"):
            rad_x = max(1.0, rx)
            rad_y = max(1.0, ry if sy > 1 else rx)
            rad_z = max(1.0, rz if sz > 1 else rx)
            ix, iy, iz = int(math.ceil(rad_x)), int(math.ceil(rad_y)), int(math.ceil(rad_z))
            start_dy = 0 if shape_type == "dome" else -iy
            center_y = cy if shape_type == "dome" else cy + iy
            for dx in range(-ix, ix + 1):
                for dy in range(start_dy, iy + 1):
                    for dz in range(-iz, iz + 1):
                        norm_d = math.sqrt((dx / rad_x) ** 2 + (dy / rad_y) ** 2 + (dz / rad_z) ** 2)
                        if norm_d <= 1.04:
                            if hollow:
                                in_x = max(0.5, rad_x - t)
                                in_y = max(0.5, rad_y - t)
                                in_z = max(0.5, rad_z - t)
                                if math.sqrt((dx / in_x) ** 2 + (dy / in_y) ** 2 + (dz / in_z) ** 2) < 0.96:
                                    continue
                            pt = (cx + dx, center_y + dy, cz + dz)
                            voxels.add(MagicaShapeGenerator._orient_point(pt, (cx, cy, cz), axis))

        elif shape_type == "pyramid":
            height = max(1, sy)
            half_x = max(1, sx // 2)
            half_z = max(1, sz // 2)
            for dy in range(height):
                ratio = 1.0 - (dy / float(max(1, height)))
                cur_rx = max(0, int(round(half_x * ratio)))
                cur_rz = max(0, int(round(half_z * ratio)))
                for dx in range(-cur_rx, cur_rx + 1):
                    for dz in range(-cur_rz, cur_rz + 1):
                        if hollow and dy > 0:
                            if abs(dx) <= cur_rx - t and abs(dz) <= cur_rz - t:
                                continue
                        pt = (cx + dx, cy + dy, cz + dz)
                        voxels.add(MagicaShapeGenerator._orient_point(pt, (cx, cy, cz), axis))

        elif shape_type == "cone":
            height = max(1, sy)
            base_r = max(1.0, rx)
            for dy in range(height):
                ratio = 1.0 - (dy / float(max(1, height)))
                cur_r = base_r * ratio
                ir = int(math.ceil(cur_r))
                for dx in range(-ir, ir + 1):
                    for dz in range(-ir, ir + 1):
                        dist = math.sqrt(dx * dx + dz * dz)
                        if dist <= cur_r + 0.3:
                            if hollow and dy > 0 and dist < cur_r - t:
                                continue
                            pt = (cx + dx, cy + dy, cz + dz)
                            voxels.add(MagicaShapeGenerator._orient_point(pt, (cx, cy, cz), axis))

        elif shape_type == "torus":
            major_r = max(2.0, rx)
            minor_r = max(1.0, min(major_r * 0.6, float(max(1, sy // 2))))
            bound = int(math.ceil(major_r + minor_r))
            im = int(math.ceil(minor_r))
            for dx in range(-bound, bound + 1):
                for dz in range(-bound, bound + 1):
                    ring_d = abs(math.sqrt(dx * dx + dz * dz) - major_r)
                    if ring_d <= minor_r + 0.25:
                        for dy in range(-im, im + 1):
                            dist_tube = math.sqrt(ring_d * ring_d + dy * dy)
                            if dist_tube <= minor_r + 0.25:
                                if hollow and dist_tube < minor_r - t:
                                    continue
                                pt = (cx + dx, cy + dy + im, cz + dz)
                                voxels.add(MagicaShapeGenerator._orient_point(pt, (cx, cy, cz), axis))

        elif shape_type == "arch":
            half_w = max(2, sx // 2)
            h_total = max(3, sy)
            depth = max(1, sz)
            arch_r = half_w
            pillar_h = max(1, h_total - arch_r)
            for dz in range(-(depth // 2), depth - (depth // 2)):
                for dy in range(pillar_h):
                    for w_step in range(t):
                        p1 = (cx - half_w + w_step, cy + dy, cz + dz)
                        p2 = (cx + half_w - w_step, cy + dy, cz + dz)
                        voxels.add(MagicaShapeGenerator._orient_point(p1, (cx, cy, cz), axis))
                        voxels.add(MagicaShapeGenerator._orient_point(p2, (cx, cy, cz), axis))
                for dx in range(-half_w, half_w + 1):
                    for dy in range(arch_r + 1):
                        dist = math.sqrt(dx * dx + dy * dy)
                        if arch_r - t <= dist <= arch_r + 0.45:
                            pt = (cx + dx, cy + pillar_h + dy, cz + dz)
                            voxels.add(MagicaShapeGenerator._orient_point(pt, (cx, cy, cz), axis))

        elif shape_type == "stairs":
            width = max(1, sx)
            height = max(1, sy)
            depth = max(1, sz)
            wx0 = cx - width // 2
            zz0 = cz - depth // 2
            for step_i in range(depth):
                step_h = max(1, int(round(((step_i + 1) / float(depth)) * height)))
                y_start = max(0, step_h - t) if hollow else 0
                for dy in range(y_start, step_h):
                    for dx in range(width):
                        pt = (wx0 + dx, cy + dy, zz0 + step_i)
                        voxels.add(MagicaShapeGenerator._orient_point(pt, (cx, cy, cz), axis))

        return voxels

    @staticmethod
    def _orient_point(
        pt: Tuple[int, int, int],
        origin: Tuple[int, int, int],
        axis: str,
    ) -> Tuple[int, int, int]:
        if axis == "Y":
            return pt
        ox, oy, oz = origin
        dx, dy, dz = pt[0] - ox, pt[1] - oy, pt[2] - oz
        if axis == "X":
            return (ox + dy, oy + dx, oz + dz)
        if axis == "Z":
            return (ox + dx, oy + dz, oz + dy)
        return pt

    @staticmethod
    def bresenham_line_3d(
        p1: Tuple[int, int, int],
        p2: Tuple[int, int, int],
        radius: int = 0,
    ) -> Set[Tuple[int, int, int]]:
        """Trace une ligne 3D continue entre p1 et p2 avec rayon optionnel."""
        x1, y1, z1 = int(round(p1[0])), int(round(p1[1])), int(round(p1[2]))
        x2, y2, z2 = int(round(p2[0])), int(round(p2[1])), int(round(p2[2]))
        dx, dy, dz = abs(x2 - x1), abs(y2 - y1), abs(z2 - z1)
        steps = max(1, dx, dy, dz)
        pts: Set[Tuple[int, int, int]] = set()
        for i in range(steps + 1):
            t = i / float(steps)
            cx = int(round(x1 + (x2 - x1) * t))
            cy = int(round(y1 + (y2 - y1) * t))
            cz = int(round(z1 + (z2 - z1) * t))
            if radius <= 0:
                pts.add((cx, cy, cz))
            else:
                for rx in range(-radius, radius + 1):
                    for ry in range(-radius, radius + 1):
                        for rz in range(-radius, radius + 1):
                            if rx * rx + ry * ry + rz * rz <= radius * radius + 0.5:
                                pts.add((cx + rx, cy + ry, cz + rz))
        return pts

    @staticmethod
    def apply_symmetry_3d(
        voxels: Set[Tuple[int, int, int]],
        sym_x: bool = False,
        sym_y: bool = False,
        sym_z: bool = False,
        center: Tuple[float, float, float] = (0.0, 8.0, 0.0),
    ) -> Set[Tuple[int, int, int]]:
        """Duplique les coordonnées Voxel par symétrie miroir X, Y et/ou Z."""
        result = set(voxels)
        cx, cy, cz = center
        if sym_x:
            result |= {(int(round(2 * cx - x - 1)), y, z) for (x, y, z) in list(result)}
        if sym_y:
            result |= {(x, int(round(2 * cy - y - 1)), z) for (x, y, z) in list(result)}
        if sym_z:
            result |= {(x, y, int(round(2 * cz - z - 1))) for (x, y, z) in list(result)}
        return result

    @staticmethod
    def greedy_mesh_voxels(
        voxel_colors: Dict[Tuple[int, int, int], str]
    ) -> List[Tuple[int, int, int, int, int, int, str]]:
        """
        Algorithme de Greedy Meshing 3D :
        Regroupe un dictionnaire {(x, y, z): color_hex} en une liste minimale de
        pavés 3D (x0, y0, z0, w, h, d, color_hex).
        """
        if not voxel_colors:
            return []
        remaining = dict(voxel_colors)
        merged_boxes: List[Tuple[int, int, int, int, int, int, str]] = []
        sorted_coords = sorted(remaining.keys(), key=lambda p: (p[1], p[2], p[0]))

        for start_pt in sorted_coords:
            if start_pt not in remaining:
                continue
            col = remaining[start_pt]
            x0, y0, z0 = start_pt

            # 1. Étendre sur l'axe X (Largeur W)
            w = 1
            while remaining.get((x0 + w, y0, z0)) == col:
                w += 1

            # 2. Étendre sur l'axe Z (Profondeur D)
            d = 1
            can_z = True
            while can_z:
                for ix in range(x0, x0 + w):
                    if remaining.get((ix, y0, z0 + d)) != col:
                        can_z = False
                        break
                if can_z:
                    d += 1

            # 3. Étendre sur l'axe Y (Hauteur H)
            h = 1
            can_y = True
            while can_y:
                for iz in range(z0, z0 + d):
                    for ix in range(x0, x0 + w):
                        if remaining.get((ix, y0 + h, iz)) != col:
                            can_y = False
                            break
                    if not can_y:
                        break
                if can_y:
                    h += 1

            for iy in range(y0, y0 + h):
                for iz in range(z0, z0 + d):
                    for ix in range(x0, x0 + w):
                        remaining.pop((ix, iy, iz), None)

            merged_boxes.append((x0, y0, z0, w, h, d, col))

        return merged_boxes