# -*- coding: utf-8 -*-
"""
engine/model_loader/model_data.py
Structures de données 3D + Moteur MagicaVoxel + Studio d'Items & Extrudeur 2D->3D (Tâche 4) :
- 13 Formes 3D Préfaites MagicaVoxel, Sculpture Booléenne & Greedy Meshing 3D
- Extrudeur Automatique Sprite 2D (16x16 / 32x32) -> Modèle 3D Voxel avec 7 Gabarits d'Items RPG
- Studio d'Icône d'Inventaire 64x64 : Angles Yaw/Pitch/Roll/Zoom, Contour Pixel-Art (Outline), Cadres de Rareté
- Propriétés complètes d'Outils/Armes Luanti (wield_scale, range, groupcaps, durabilité, projectile, soin).
"""

import base64
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from PyQt6.QtCore import QObject, pyqtSignal, Qt, QBuffer, QIODevice, QPointF, QRectF
    from PyQt6.QtGui import QImage, QColor, QPainter, QPolygonF, QPen, QBrush, QTransform
except ImportError:
    from PyQt5.QtCore import QObject, pyqtSignal, Qt, QBuffer, QIODevice, QPointF, QRectF
    from PyQt5.QtGui import QImage, QColor, QPainter, QPolygonF, QPen, QBrush, QTransform

from engine.voxel.magicavoxel_tools import MagicaShapeGenerator


FACE_NAMES = ("top", "bottom", "north", "south", "east", "west")

ITEM_2D_TEMPLATES: List[Tuple[str, str]] = [
    ("sword", "⚔️ Épée Astrale 16×16"),
    ("pickaxe", "⛏️ Pioche de Mese 16×16"),
    ("battleaxe", "🪓 Hache de Guerre 16×16"),
    ("potion", "🧪 Potion de Soin 16×16"),
    ("staff", "🪄 Bâton Élémentaire 16×16"),
    ("shield", "🛡️ Bouclier Royal 16×16"),
    ("key", "🗝️ Clé de Donjon 16×16"),
]


@dataclass
class FaceUVRect:
    face: str
    u: int
    v: int
    w: int
    h: int


@dataclass
class ModelBone:
    name: str
    parent_name: Optional[str] = None
    pivot: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    rotation: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    visible: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "parent_name": self.parent_name,
            "pivot": list(self.pivot),
            "rotation": list(self.rotation),
            "position": list(self.position),
            "visible": self.visible,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModelBone":
        return cls(
            name=d.get("name", "root"),
            parent_name=d.get("parent_name"),
            pivot=list(d.get("pivot", [0.0, 0.0, 0.0])),
            rotation=list(d.get("rotation", [0.0, 0.0, 0.0])),
            position=list(d.get("position", [0.0, 0.0, 0.0])),
            visible=bool(d.get("visible", True)),
        )


@dataclass
class ModelCube:
    cube_id: str
    name: str
    bone_name: str = "root"
    position: List[float] = field(default_factory=lambda: [-4.0, 0.0, -4.0])
    size: List[float] = field(default_factory=lambda: [8.0, 8.0, 8.0])
    pivot: List[float] = field(default_factory=lambda: [0.0, 4.0, 0.0])
    rotation: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    uv_offset: List[int] = field(default_factory=lambda: [0, 0])
    visible: bool = True
    mirror_uv: bool = False

    def get_pixel_dimensions(self) -> Tuple[int, int, int]:
        w = max(1, int(round(self.size[0])))
        h = max(1, int(round(self.size[1])))
        d = max(1, int(round(self.size[2])))
        return w, h, d

    def get_box_uv_footprint(self) -> Tuple[int, int]:
        w, h, d = self.get_pixel_dimensions()
        return (2 * d + 2 * w), (d + h)

    def get_face_uv_rects(self) -> Dict[str, FaceUVRect]:
        w, h, d = self.get_pixel_dimensions()
        u0, v0 = int(self.uv_offset[0]), int(self.uv_offset[1])
        return {
            "top":    FaceUVRect("top",    u0 + d,         v0,     w, d),
            "bottom": FaceUVRect("bottom", u0 + d + w,     v0,     w, d),
            "west":   FaceUVRect("west",   u0,             v0 + d, d, h),
            "north":  FaceUVRect("north",  u0 + d,         v0 + d, w, h),
            "east":   FaceUVRect("east",   u0 + d + w,     v0 + d, d, h),
            "south":  FaceUVRect("south",  u0 + 2 * d + w, v0 + d, w, h),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cube_id": self.cube_id,
            "name": self.name,
            "bone_name": self.bone_name,
            "position": list(self.position),
            "size": list(self.size),
            "pivot": list(self.pivot),
            "rotation": list(self.rotation),
            "uv_offset": list(self.uv_offset),
            "visible": self.visible,
            "mirror_uv": self.mirror_uv,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModelCube":
        return cls(
            cube_id=d.get("cube_id", "cube_1"),
            name=d.get("name", "Cube"),
            bone_name=d.get("bone_name", "root"),
            position=list(d.get("position", [-4.0, 0.0, -4.0])),
            size=list(d.get("size", [8.0, 8.0, 8.0])),
            pivot=list(d.get("pivot", [0.0, 4.0, 0.0])),
            rotation=list(d.get("rotation", [0.0, 0.0, 0.0])),
            uv_offset=list(d.get("uv_offset", [0, 0])),
            visible=bool(d.get("visible", True)),
            mirror_uv=bool(d.get("mirror_uv", False)),
        )


class ModelData(QObject):
    """
    Modèle 3D complet avec Bones, Cubes, Moteur Voxel MagicaVoxel, Extrudeur 2D->3D et Studio d'Icône.
    """
    modelChanged = pyqtSignal()
    textureChanged = pyqtSignal()
    selectionChanged = pyqtSignal()

    def __init__(self, category: str = "Mobs", name: str = "nouveau_modele", atlas_size: int = 64):
        super().__init__()
        self.category = category
        self.name = name
        self.atlas_width = atlas_size
        self.atlas_height = atlas_size

        self.grid_size: int = 16

        # Propriétés Gameplay & IA In-Game Luanti
        self.ai_behavior: str = "passive"
        self.max_hp: int = 20
        self.move_speed: float = 2.5
        self.attack_damage: int = 4
        self.drop_item: str = "default:mese_crystal_fragment"
        self.light_source: int = 0
        self.animate_in_game: bool = True

        # Nouveaux paramètres Tâche 4 : Studio d'Icône d'Inventaire & Calibrage Arme/Outil
        self.icon_mode: str = "3d_render"          # "3d_render" ou "2d_sprite"
        self.icon_yaw: float = -38.0
        self.icon_pitch: float = 25.0
        self.icon_roll: float = 0.0
        self.icon_zoom: float = 1.0
        self.icon_outline: bool = True
        self.icon_outline_color: str = "#0f172a"
        self.icon_rarity_bg: str = "none"          # "none", "common", "rare", "epic", "legendary"

        self.item_kind: str = "tool"               # "tool", "craftitem", "placeable_3d"
        self.wield_scale: List[float] = [1.45, 1.45, 1.25]
        self.tool_range: float = 4.5
        self.punch_interval: float = 0.65
        self.tool_uses: int = 120
        self.mine_cracky: int = 3
        self.mine_choppy: int = 2
        self.mine_snappy: int = 3
        self.mine_crumbly: int = 1
        self.item_heal_hp: int = 0
        self.item_shoot_projectile: bool = False
        self.item_hit_particles: bool = True

        self.bones: Dict[str, ModelBone] = {}
        self.cubes: List[ModelCube] = []
        self._pending_timeline_dict: Optional[Dict[str, Any]] = None

        self.selected_cube_id: Optional[str] = None
        self.selected_bone_name: Optional[str] = "root"

        self.texture_image = QImage(self.atlas_width, self.atlas_height, QImage.Format.Format_ARGB32)
        self.texture_image.fill(QColor(0, 0, 0, 0))

        self.sprite_2d_image = QImage(16, 16, QImage.Format.Format_ARGB32)
        self.sprite_2d_image.fill(QColor(0, 0, 0, 0))
        self.load_2d_sprite_template("sword")

        self._undo_stack: List[QImage] = []
        self._redo_stack: List[QImage] = []

        self.load_default_preset(category)

    # =========================================================================
    # TÂCHE 4 : GABARITS SPRITE 2D (16x16) & EXTRUDEUR 2D -> 3D VOXEL
    # =========================================================================
    def load_2d_sprite_template(self, template_key: str):
        img = QImage(16, 16, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))

        # Palettes de couleurs Pixel-Art
        pal = {
            "G": QColor("#facc15"),  # Or
            "g": QColor("#b45309"),  # Or foncé
            "W": QColor("#78350f"),  # Bois manche
            "w": QColor("#451a03"),  # Bois sombre
            "C": QColor("#38bdf8"),  # Cristal Cyan
            "c": QColor("#0284c7"),  # Cyan foncé
            "L": QColor("#e0f2fe"),  # Reflet blanc/cyan
            "S": QColor("#cbd5e1"),  # Acier clair
            "s": QColor("#64748b"),  # Acier foncé
            "R": QColor("#ef4444"),  # Rouge rubis / potion
            "r": QColor("#991b1b"),  # Rouge sombre
            "B": QColor("#2563eb"),  # Bleu royal
        }

        grids = {
            "sword": [
                ".............CL.",
                "............CLC.",
                "...........CLc..",
                "..........CLc...",
                ".........CLc....",
                "........CLc.....",
                ".......CLc......",
                "......CLc.......",
                "..GG.CLc........",
                "...GGCc.........",
                "...gGGG.........",
                "..Ww.gG.........",
                ".Ww...G.........",
                "GG..............",
                "Gg..............",
                "................",
            ],
            "pickaxe": [
                "........GGGGGG..",
                ".......GCCCCCCL.",
                "......GCccccccCL",
                ".........Ww..cCL",
                "........Ww....cC",
                ".......Ww.....cC",
                "......Ww......G.",
                ".....Ww.........",
                "....Ww..........",
                "...Ww...........",
                "..Ww............",
                ".Ww.............",
                "Gg..............",
                "................",
                "................",
                "................",
            ],
            "battleaxe": [
                "........sSSSS...",
                ".......sSCCCCS..",
                "......sSCcLLCCS.",
                "......sSCc..CCS.",
                ".......sS..WwCS.",
                "..........Ww.SS.",
                ".........Ww.....",
                "........Ww......",
                ".......Ww.......",
                "......Ww........",
                ".....Ww.........",
                "....Ww..........",
                "...Gg...........",
                "................",
                "................",
                "................",
            ],
            "potion": [
                "......GGGG......",
                ".......WW.......",
                "......sSSs......",
                "......s..s......",
                ".....s....s.....",
                "....s..LL..s....",
                "...s.LRRRRL.s...",
                "...sRRRRRRRRs...",
                "...sRRRRrrrrs...",
                "...sRRRrrrrrs...",
                "....srrrrrrs....",
                ".....ssssss.....",
                "................",
                "................",
                "................",
                "................",
            ],
            "staff": [
                "..........GGG...",
                ".........GCLLC..",
                "........GCLCCCG.",
                "........GCcccCG.",
                ".........GGGGG..",
                ".........Ww.....",
                "........Ww......",
                ".......Ww.......",
                "......Ww........",
                ".....Ww.........",
                "....Ww..........",
                "...Ww...........",
                "..Ww............",
                ".Gg.............",
                "................",
                "................",
            ],
            "shield": [
                "...GGGGGGGGGG...",
                "..GBBBBBBBBBBG..",
                "..GBBssGGssBBG..",
                "..GBsGGGGGGsBG..",
                "..GBsGCCCCGsBG..",
                "..GBsGCLLCGsBG..",
                "..GBsGCCCCGsBG..",
                "..GBsGGGGGGsBG..",
                "...GBBssssBBG...",
                "...gBBBBBBBBg...",
                "....gBBBBBBg....",
                ".....gBBBBg.....",
                "......gBBg......",
                ".......gg.......",
                "................",
                "................",
            ],
            "key": [
                ".........GGGG...",
                "........GG..GG..",
                "........G....G..",
                "........GG..GG..",
                ".........GGGG...",
                "........Gg......",
                ".......Gg.......",
                "......Gg........",
                ".....Gg.........",
                "....GgGG........",
                "...Gg..G........",
                "..GgGG..........",
                "..gg.G..........",
                "................",
                "................",
                "................",
            ],
        }

        rows = grids.get(template_key, grids["sword"])
        for y, row_str in enumerate(rows[:16]):
            for x, ch in enumerate(row_str[:16]):
                if ch in pal:
                    img.setPixelColor(x, y, pal[ch])

        self.sprite_2d_image = img

    def extrude_2d_sprite_to_3d_voxels(
        self,
        sprite: Optional[QImage] = None,
        thickness: int = 2,
        bone_name: str = "root",
    ) -> int:
        """
        Convertit chaque pixel non transparent du Sprite 2D en Voxels 3D d'épaisseur `thickness`,
        fusionne les voxels adjacents de même couleur par Greedy Meshing et génère l'atlas Box-UV !
        """
        src = sprite or self.sprite_2d_image
        if src.isNull():
            return 0

        w, h = src.width(), src.height()
        depth = max(1, min(16, int(thickness)))
        z_start = -(depth // 2)

        target_bone = bone_name if bone_name in self.bones else "root"
        if target_bone not in self.bones:
            self.bones["root"] = ModelBone("root", None, [0.0, 8.0, 0.0])
            target_bone = "root"

        voxel_map: Dict[Tuple[int, int, int], str] = {}
        for py in range(h):
            for px in range(w):
                col = src.pixelColor(px, py)
                if col.alpha() > 20:
                    vx = px - (w // 2)
                    vy = (h - 1 - py)
                    hex_c = col.name()
                    for dz in range(depth):
                        voxel_map[(vx, vy, z_start + dz)] = hex_c

        if not voxel_map:
            return 0

        # Supprime tous les anciens cubes des autres bones si c'est un Item pour repartir sur l'extrusion propre
        if self.category == "Items":
            self.cubes = []
            self.bones = {"root": ModelBone("root", None, [0.0, 8.0, 0.0])}
            target_bone = "root"

        self.rebuild_bone_cubes_from_voxel_map(target_bone, voxel_map, prefix_name="Pixel3D")
        return len(self.cubes)

    # =========================================================================
    # MOTEUR 3D VOXEL "MAGICAVOXEL" (FORMES PRÉFAITES, BOOLÉENS & GREEDY MESH)
    # =========================================================================
    def sample_cube_dominant_color(self, cube: ModelCube) -> QColor:
        rects = cube.get_face_uv_rects()
        r = rects["top"]
        u = min(self.atlas_width - 1, max(0, r.u + r.w // 2))
        v = min(self.atlas_height - 1, max(0, r.v + r.h // 2))
        col = self.texture_image.pixelColor(u, v)
        return col if col.alpha() > 0 else QColor("#38bdf8")

    def extract_bone_voxel_map(self, bone_name: str) -> Dict[Tuple[int, int, int], str]:
        voxel_map: Dict[Tuple[int, int, int], str] = {}
        for cube in self.cubes:
            if cube.bone_name != bone_name or not cube.visible:
                continue
            if any(abs(r) > 0.1 for r in cube.rotation):
                continue
            hex_col = self.sample_cube_dominant_color(cube).name()
            x0, y0, z0 = int(round(cube.position[0])), int(round(cube.position[1])), int(round(cube.position[2]))
            w, h, d = cube.get_pixel_dimensions()
            for x in range(x0, x0 + w):
                for y in range(y0, y0 + h):
                    for z in range(z0, z0 + d):
                        voxel_map[(x, y, z)] = hex_col
        return voxel_map

    def rebuild_bone_cubes_from_voxel_map(
        self,
        bone_name: str,
        voxel_map: Dict[Tuple[int, int, int], str],
        prefix_name: str = "Voxel",
    ):
        existing_colors: Dict[str, QColor] = {}
        kept_cubes: List[ModelCube] = []
        for c in self.cubes:
            if c.bone_name == bone_name and all(abs(r) <= 0.1 for r in c.rotation):
                continue
            kept_cubes.append(c)
            existing_colors[c.cube_id] = self.sample_cube_dominant_color(c)

        merged_boxes = MagicaShapeGenerator.greedy_mesh_voxels(voxel_map)
        new_cubes: List[ModelCube] = []
        new_colors: Dict[str, QColor] = {}

        for idx, (x0, y0, z0, w, h, d, hex_col) in enumerate(merged_boxes, start=1):
            cid = f"vx_{bone_name}_{idx}_{id(self) % 997}"
            piv = [x0 + w * 0.5, y0 + h * 0.5, z0 + d * 0.5]
            mc = ModelCube(
                cube_id=cid,
                name=f"{prefix_name}_{idx}",
                bone_name=bone_name,
                position=[float(x0), float(y0), float(z0)],
                size=[float(w), float(h), float(d)],
                pivot=piv,
                rotation=[0.0, 0.0, 0.0],
            )
            new_cubes.append(mc)
            new_colors[cid] = QColor(hex_col)

        self.cubes = kept_cubes + new_cubes
        self.auto_pack_uv_atlas(repaint_default_colors=False)

        for c in self.cubes:
            if c.cube_id in new_colors:
                self.fill_cube_all_faces(c, new_colors[c.cube_id], add_pixel_variation=True)
            elif c.cube_id in existing_colors:
                self.fill_cube_all_faces(c, existing_colors[c.cube_id], add_pixel_variation=True)

        if new_cubes:
            self.selected_cube_id = new_cubes[0].cube_id
        elif self.cubes:
            self.selected_cube_id = self.cubes[0].cube_id

        self.textureChanged.emit()
        self.modelChanged.emit()
        self.selectionChanged.emit()

    def apply_magicavoxel_shape(
        self,
        shape_type: str,
        center: Tuple[int, int, int],
        size_xyz: Tuple[int, int, int],
        color: QColor,
        hollow: bool = False,
        thickness: int = 1,
        axis: str = "Y",
        boolean_op: str = "add",
        sym_x: bool = False,
        sym_y: bool = False,
        sym_z: bool = False,
    ) -> int:
        target_bone = self.selected_bone_name or "root"
        if target_bone not in self.bones:
            target_bone = "root"

        raw_voxels = MagicaShapeGenerator.generate_shape_voxels(
            shape_type=shape_type,
            center=center,
            size_xyz=size_xyz,
            hollow=hollow,
            thickness=thickness,
            axis=axis,
        )
        shape_voxels = MagicaShapeGenerator.apply_symmetry_3d(
            raw_voxels, sym_x=sym_x, sym_y=sym_y, sym_z=sym_z, center=(0.0, float(center[1]), 0.0)
        )
        hex_col = color.name()

        if boolean_op == "separate":
            existing_cols = {c.cube_id: self.sample_cube_dominant_color(c) for c in self.cubes}
            vmap = {pt: hex_col for pt in shape_voxels}
            merged = MagicaShapeGenerator.greedy_mesh_voxels(vmap)
            base_idx = len(self.cubes) + 1
            added_ids = []
            for offset, (x0, y0, z0, w, h, d, _) in enumerate(merged):
                cid = f"shape_{shape_type}_{base_idx + offset}"
                mc = ModelCube(
                    cube_id=cid,
                    name=f"{shape_type.capitalize()}_{offset + 1}",
                    bone_name=target_bone,
                    position=[float(x0), float(y0), float(z0)],
                    size=[float(w), float(h), float(d)],
                    pivot=[x0 + w * 0.5, y0 + h * 0.5, z0 + d * 0.5],
                )
                self.cubes.append(mc)
                added_ids.append(cid)

            self.auto_pack_uv_atlas(repaint_default_colors=False)
            for c in self.cubes:
                if c.cube_id in added_ids:
                    self.fill_cube_all_faces(c, color, add_pixel_variation=True)
                elif c.cube_id in existing_cols:
                    self.fill_cube_all_faces(c, existing_cols[c.cube_id], add_pixel_variation=True)

            if added_ids:
                self.select_cube(added_ids[0])
            self.textureChanged.emit()
            self.modelChanged.emit()
            return len(added_ids)

        if boolean_op == "replace":
            vmap = {pt: hex_col for pt in shape_voxels}
        else:
            vmap = self.extract_bone_voxel_map(target_bone)
            if boolean_op == "carve":
                for pt in shape_voxels:
                    vmap.pop(pt, None)
            else:
                for pt in shape_voxels:
                    vmap[pt] = hex_col

        self.rebuild_bone_cubes_from_voxel_map(target_bone, vmap, prefix_name=shape_type.capitalize())
        return len(self.cubes)

    def sculpt_voxel_at(
        self,
        voxel_pos: Tuple[int, int, int],
        mode: str = "attach",
        color: QColor = QColor("#38bdf8"),
        brush_radius: int = 0,
        sym_x: bool = False,
        sym_y: bool = False,
        sym_z: bool = False,
    ):
        target_bone = self.selected_bone_name or "root"
        if target_bone not in self.bones:
            target_bone = "root"

        vx, vy, vz = int(voxel_pos[0]), int(voxel_pos[1]), int(voxel_pos[2])
        pts: Set[Tuple[int, int, int]] = set()
        r = max(0, int(brush_radius))
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    if dx * dx + dy * dy + dz * dz <= r * r + 0.5:
                        pts.add((vx + dx, vy + dy, vz + dz))

        pts = MagicaShapeGenerator.apply_symmetry_3d(pts, sym_x=sym_x, sym_y=sym_y, sym_z=sym_z)
        vmap = self.extract_bone_voxel_map(target_bone)
        hex_c = color.name()

        if mode == "erase":
            for p in pts:
                vmap.pop(p, None)
        else:
            for p in pts:
                vmap[p] = hex_c

        if vmap:
            self.rebuild_bone_cubes_from_voxel_map(target_bone, vmap, prefix_name="Voxel")

    def optimize_current_bone_greedy_mesh(self) -> Tuple[int, int]:
        target_bone = self.selected_bone_name or "root"
        before_count = sum(1 for c in self.cubes if c.bone_name == target_bone)
        vmap = self.extract_bone_voxel_map(target_bone)
        if vmap:
            self.rebuild_bone_cubes_from_voxel_map(target_bone, vmap, prefix_name="Mesh")
        after_count = sum(1 for c in self.cubes if c.bone_name == target_bone)
        return before_count, after_count

    # =========================================================================
    # PRESETS PAR CATÉGORIE
    # =========================================================================
    def load_default_preset(self, category: str):
        self.category = category
        self.bones.clear()
        self.cubes.clear()

        if category == "Mobs":
            self._build_fox_mob_preset()
        elif category == "Blocks":
            self.light_source = 10
            self._build_sculpted_block_preset()
        else:
            self.attack_damage = 6
            self.icon_yaw = -42.0
            self.icon_pitch = 22.0
            self.icon_roll = -25.0
            self.icon_zoom = 1.15
            self._build_sword_item_preset()

        self.auto_pack_uv_atlas(repaint_default_colors=True)
        if self.cubes:
            self.selected_cube_id = self.cubes[0].cube_id
            self.selected_bone_name = self.cubes[0].bone_name

        self.modelChanged.emit()
        self.textureChanged.emit()

    def _build_fox_mob_preset(self):
        self.bones["root"] = ModelBone("root", None, [0.0, 6.0, 0.0])
        self.bones["head_bone"] = ModelBone("head_bone", "root", [0.0, 9.0, 4.0])
        self.bones["tail_bone"] = ModelBone("tail_bone", "root", [0.0, 8.0, -5.0], [-18.0, 0.0, 0.0])
        self.bones["leg_fl_bone"] = ModelBone("leg_fl_bone", "root", [-2.0, 4.0, 3.0])
        self.bones["leg_fr_bone"] = ModelBone("leg_fr_bone", "root", [2.0, 4.0, 3.0])
        self.bones["leg_bl_bone"] = ModelBone("leg_bl_bone", "root", [-2.0, 4.0, -3.0])
        self.bones["leg_br_bone"] = ModelBone("leg_br_bone", "root", [2.0, 4.0, -3.0])

        self.cubes = [
            ModelCube("cube_body", "Torse", "root", [-3.0, 4.0, -5.0], [6.0, 5.0, 10.0], [0.0, 6.5, 0.0]),
            ModelCube("cube_head", "Tête", "head_bone", [-4.0, 7.0, 3.0], [8.0, 6.0, 6.0], [0.0, 10.0, 6.0]),
            ModelCube("cube_snout", "Museau", "head_bone", [-2.0, 7.0, 9.0], [4.0, 3.0, 3.0], [0.0, 8.5, 10.5]),
            ModelCube("cube_ear_l", "Oreille G", "head_bone", [-4.0, 13.0, 5.0], [2.0, 3.0, 1.0], [-3.0, 13.0, 5.5]),
            ModelCube("cube_ear_r", "Oreille D", "head_bone", [2.0, 13.0, 5.0], [2.0, 3.0, 1.0], [3.0, 13.0, 5.5]),
            ModelCube("cube_tail", "Queue", "tail_bone", [-2.0, 6.0, -11.0], [4.0, 4.0, 6.0], [0.0, 8.0, -5.0]),
            ModelCube("cube_leg_fl", "Patte Av.G", "leg_fl_bone", [-3.0, 0.0, 2.0], [2.0, 4.0, 2.0], [-2.0, 4.0, 3.0]),
            ModelCube("cube_leg_fr", "Patte Av.D", "leg_fr_bone", [1.0, 0.0, 2.0], [2.0, 4.0, 2.0], [2.0, 4.0, 3.0]),
            ModelCube("cube_leg_bl", "Patte Ar.G", "leg_bl_bone", [-3.0, 0.0, -4.0], [2.0, 4.0, 2.0], [-2.0, 4.0, -3.0]),
            ModelCube("cube_leg_br", "Patte Ar.D", "leg_br_bone", [1.0, 0.0, -4.0], [2.0, 4.0, 2.0], [2.0, 4.0, -3.0]),
        ]

    def _build_sculpted_block_preset(self):
        self.bones["root"] = ModelBone("root", None, [0.0, 0.0, 0.0])
        self.bones["crystal_bone"] = ModelBone("crystal_bone", "root", [0.0, 11.0, 0.0], [0.0, 25.0, 0.0])

        self.cubes = [
            ModelCube("cube_base", "Socle Bas", "root", [-8.0, 0.0, -8.0], [16.0, 4.0, 16.0], [0.0, 2.0, 0.0]),
            ModelCube("cube_pillar", "Pilier Central", "root", [-5.0, 4.0, -5.0], [10.0, 6.0, 10.0], [0.0, 7.0, 0.0]),
            ModelCube("cube_crystal", "Cristal Flottant", "crystal_bone", [-3.0, 10.0, -3.0], [6.0, 6.0, 6.0], [0.0, 13.0, 0.0]),
        ]

    def _build_sword_item_preset(self):
        self.bones["root"] = ModelBone("root", None, [0.0, 4.0, 0.0])
        self.bones["blade_bone"] = ModelBone("blade_bone", "root", [0.0, 7.0, 0.0])

        self.cubes = [
            ModelCube("cube_pommel", "Pommeau", "root", [-1.5, 0.0, -1.5], [3.0, 2.0, 3.0], [0.0, 1.0, 0.0]),
            ModelCube("cube_grip", "Poignée", "root", [-1.0, 2.0, -1.0], [2.0, 4.0, 2.0], [0.0, 4.0, 0.0]),
            ModelCube("cube_guard", "Garde", "root", [-4.0, 6.0, -1.5], [8.0, 2.0, 3.0], [0.0, 7.0, 0.0]),
            ModelCube("cube_blade", "Lame", "blade_bone", [-1.5, 8.0, -0.5], [3.0, 10.0, 1.0], [0.0, 13.0, 0.0]),
        ]

    # =========================================================================
    # DÉPLIAGE BOX-UV AUTOMATIQUE
    # =========================================================================
    def auto_pack_uv_atlas(self, repaint_default_colors: bool = False):
        cursor_u = 1
        cursor_v = 1
        row_max_h = 0
        needed_size = max(64, self.atlas_width)

        for cube in self.cubes:
            fw, fh = cube.get_box_uv_footprint()
            if cursor_u + fw + 1 > needed_size:
                cursor_u = 1
                cursor_v += row_max_h + 2
                row_max_h = 0
            while cursor_v + fh + 1 > needed_size or fw + 2 > needed_size:
                needed_size *= 2

            cube.uv_offset = [cursor_u, cursor_v]
            cursor_u += fw + 2
            row_max_h = max(row_max_h, fh)

        if needed_size > self.atlas_width:
            self.resize_atlas(needed_size, needed_size)

        if repaint_default_colors:
            self._fill_initial_cube_textures()
        else:
            self._ensure_all_cube_faces_opaque()

        self.textureChanged.emit()
        self.modelChanged.emit()

    def resize_atlas(self, new_w: int, new_h: int):
        new_img = QImage(new_w, new_h, QImage.Format.Format_ARGB32)
        new_img.fill(QColor(0, 0, 0, 0))
        painter = QPainter(new_img)
        painter.drawImage(0, 0, self.texture_image)
        painter.end()
        self.atlas_width = new_w
        self.atlas_height = new_h
        self.texture_image = new_img

    def _fill_initial_cube_textures(self):
        self.texture_image.fill(QColor(0, 0, 0, 0))
        palette_by_cat = {
            "Mobs": [
                QColor("#3b82f6"), QColor("#60a5fa"), QColor("#f8fafc"),
                QColor("#1d4ed8"), QColor("#1d4ed8"), QColor("#93c5fd"),
                QColor("#1e3a8a"), QColor("#1e3a8a"), QColor("#1e3a8a"), QColor("#1e3a8a"),
            ],
            "Blocks": [QColor("#475569"), QColor("#64748b"), QColor("#38bdf8")],
            "Items": [QColor("#f59e0b"), QColor("#78350f"), QColor("#eab308"), QColor("#38bdf8")],
        }
        colors = palette_by_cat.get(self.category, palette_by_cat["Mobs"])
        for idx, cube in enumerate(self.cubes):
            base_col = colors[idx % len(colors)]
            self.fill_cube_all_faces(cube, base_col, add_pixel_variation=True)

    def _ensure_all_cube_faces_opaque(self):
        for idx, cube in enumerate(self.cubes):
            rects = cube.get_face_uv_rects()
            top_r = rects["top"]
            if 0 <= top_r.u < self.atlas_width and 0 <= top_r.v < self.atlas_height:
                if self.texture_image.pixelColor(top_r.u, top_r.v).alpha() == 0:
                    default_col = QColor.fromHsv((idx * 47) % 360, 165, 215)
                    self.fill_cube_all_faces(cube, default_col, add_pixel_variation=True)

    def fill_cube_all_faces(self, cube: ModelCube, base_color: QColor, add_pixel_variation: bool = True):
        face_tint = {"top": 106, "north": 100, "south": 96, "east": 92, "west": 92, "bottom": 84}
        for fname, rect in cube.get_face_uv_rects().items():
            factor = face_tint.get(fname, 100)
            fcol = base_color.lighter(factor) if factor >= 100 else base_color.darker(200 - factor)
            for dy in range(rect.h):
                for dx in range(rect.w):
                    px, py = rect.u + dx, rect.v + dy
                    if 0 <= px < self.atlas_width and 0 <= py < self.atlas_height:
                        if add_pixel_variation and ((dx + dy * 3) % 5 == 0):
                            c = fcol.darker(106)
                        elif add_pixel_variation and ((dx * 2 + dy) % 7 == 0):
                            c = fcol.lighter(105)
                        else:
                            c = fcol
                        self.texture_image.setPixelColor(px, py, c)

    # =========================================================================
    # MATHÉMATIQUES 3D & COMPILATEUR WAVEFRONT .OBJ EXACT POUR LUANTI
    # =========================================================================
    @staticmethod
    def rotate_xyz(pt: Tuple[float, float, float], rx_deg: float, ry_deg: float, rz_deg: float) -> Tuple[float, float, float]:
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

    def transform_vertex(
        self,
        local_pt: Tuple[float, float, float],
        cube: ModelCube,
        bone_overrides: Optional[Dict[str, Tuple[List[float], List[float]]]] = None,
    ) -> Tuple[float, float, float]:
        px, py, pz = cube.pivot
        rx, ry, rz = cube.rotation
        vx, vy, vz = local_pt[0] - px, local_pt[1] - py, local_pt[2] - pz
        vx, vy, vz = self.rotate_xyz((vx, vy, vz), rx, ry, rz)
        vx, vy, vz = vx + px, vy + py, vz + pz

        visited = set()
        bname = cube.bone_name
        while bname and bname in self.bones and bname not in visited:
            visited.add(bname)
            bone = self.bones[bname]
            bpx, bpy, bpz = bone.pivot
            if bone_overrides and bname in bone_overrides:
                brx, bry, brz = bone_overrides[bname][0]
                box, boy, boz = bone_overrides[bname][1]
            else:
                brx, bry, brz = bone.rotation
                box, boy, boz = bone.position

            vx, vy, vz = vx - bpx, vy - bpy, vz - bpz
            vx, vy, vz = self.rotate_xyz((vx, vy, vz), brx, bry, brz)
            vx, vy, vz = vx + bpx + box, vy + bpy + boy, vz + bpz + boz
            bname = bone.parent_name

        return vx, vy, vz

    def get_bounding_box_in_blocks(self) -> Tuple[float, float, float, float, float, float]:
        if not self.cubes:
            return (-0.35, -0.5, -0.35, 0.35, 0.5, 0.35)
        xs, ys, zs = [], [], []
        for cube in self.cubes:
            if not cube.visible:
                continue
            x0, y0, z0 = cube.position
            w, h, d = cube.size
            for pt in [(x0, y0, z0), (x0 + w, y0 + h, z0 + d)]:
                tx, ty, tz = self.transform_vertex(pt, cube)
                xs.append(tx / 16.0)
                ys.append((ty - 8.0) / 16.0)
                zs.append(tz / 16.0)
        if not xs:
            return (-0.35, -0.5, -0.35, 0.35, 0.5, 0.35)
        return (
            round(min(xs), 3), round(min(ys), 3), round(min(zs), 3),
            round(max(xs), 3), round(max(ys), 3), round(max(zs), 3),
        )

    def export_to_obj(
        self,
        filepath: str,
        bone_overrides: Optional[Dict[str, Tuple[List[float], List[float]]]] = None,
        y_offset_px: float = -8.0,
    ):
        aw = float(max(1, self.atlas_width))
        ah = float(max(1, self.atlas_height))
        eps_u = 0.08 / aw
        eps_v = 0.08 / ah

        lines = [
            f"# Wavefront OBJ généré par Luanti Studio ({self.name})",
            f"o {self.name}",
        ]

        v_index = 1
        vt_index = 1
        vn_index = 1

        face_defs = {
            "top":    ((3, 2, 6, 7), (0.0, 1.0, 0.0)),
            "bottom": ((4, 5, 1, 0), (0.0, -1.0, 0.0)),
            "north":  ((7, 6, 5, 4), (0.0, 0.0, 1.0)),
            "south":  ((2, 3, 0, 1), (0.0, 0.0, -1.0)),
            "east":   ((6, 2, 1, 5), (1.0, 0.0, 0.0)),
            "west":   ((3, 7, 4, 0), (-1.0, 0.0, 0.0)),
        }

        for cube in self.cubes:
            if not cube.visible:
                continue
            x0, y0, z0 = cube.position
            w, h, d = cube.size
            x1, y1, z1 = x0 + w, y0 + h, z0 + d

            raw_verts = [
                (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
            ]
            t_verts = []
            for pt in raw_verts:
                tx, ty, tz = self.transform_vertex(pt, cube, bone_overrides)
                t_verts.append((tx / 16.0, (ty + y_offset_px) / 16.0, tz / 16.0))

            for vx, vy, vz in t_verts:
                lines.append(f"v {vx:.5f} {vy:.5f} {vz:.5f}")

            uv_rects = cube.get_face_uv_rects()

            for fname, (corner_ids, normal_vec) in face_defs.items():
                r = uv_rects[fname]
                u_left = (r.u / aw) + eps_u
                u_right = ((r.u + r.w) / aw) - eps_u
                v_top = 1.0 - ((r.v / ah) + eps_v)
                v_bot = 1.0 - (((r.v + r.h) / ah) - eps_v)

                lines.append(f"vt {u_left:.5f} {v_top:.5f}")
                lines.append(f"vt {u_right:.5f} {v_top:.5f}")
                lines.append(f"vt {u_right:.5f} {v_bot:.5f}")
                lines.append(f"vt {u_left:.5f} {v_bot:.5f}")
                lines.append(f"vn {normal_vec[0]:.3f} {normal_vec[1]:.3f} {normal_vec[2]:.3f}")

                i0 = v_index + corner_ids[0]
                i1 = v_index + corner_ids[1]
                i2 = v_index + corner_ids[2]
                i3 = v_index + corner_ids[3]

                t0, t1, t2, t3 = vt_index, vt_index + 1, vt_index + 2, vt_index + 3
                n_idx = vn_index

                lines.append(f"f {i0}/{t0}/{n_idx} {i1}/{t1}/{n_idx} {i2}/{t2}/{n_idx}")
                lines.append(f"f {i0}/{t0}/{n_idx} {i2}/{t2}/{n_idx} {i3}/{t3}/{n_idx}")

                vt_index += 4
                vn_index += 1

            v_index += 8

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    # =========================================================================
    # TÂCHE 4 : STUDIO D'ICÔNE D'INVENTAIRE HD (3D / 2D, ANGLES, OUTLINE, RARETÉ)
    # =========================================================================
    @staticmethod
    def _apply_pixel_art_outline(fg_img: QImage, outline_col: QColor) -> QImage:
        w, h = fg_img.width(), fg_img.height()
        out = fg_img.copy()
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if fg_img.pixelColor(x, y).alpha() < 25:
                    if (
                        fg_img.pixelColor(x + 1, y).alpha() > 90
                        or fg_img.pixelColor(x - 1, y).alpha() > 90
                        or fg_img.pixelColor(x, y + 1).alpha() > 90
                        or fg_img.pixelColor(x, y - 1).alpha() > 90
                    ):
                        out.setPixelColor(x, y, outline_col)
        return out

    def render_isometric_icon(self, icon_size: int = 64, draw_egg_badge: bool = False) -> QImage:
        """
        Génère l'icône d'inventaire 64x64 :
        - Supporte le mode Sprite 2D Pixel-Art ou le Rendu 3D Orientable (Yaw, Pitch, Roll, Zoom)
        - Applique le Contour Pixel-Art (Outline) et le Cadre de Rareté optionnel.
        """
        fg = QImage(icon_size, icon_size, QImage.Format.Format_ARGB32)
        fg.fill(QColor(0, 0, 0, 0))

        if self.icon_mode == "2d_sprite" and not draw_egg_badge and not self.sprite_2d_image.isNull():
            pad = max(4, int(icon_size * (1.0 - min(1.2, self.icon_zoom * 0.85)) * 0.5))
            target_s = max(16, icon_size - 2 * pad)
            scaled_sp = self.sprite_2d_image.scaled(
                target_s, target_s,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation
            )
            p_fg = QPainter(fg)
            ox = (icon_size - scaled_sp.width()) // 2
            oy = (icon_size - scaled_sp.height()) // 2
            p_fg.drawImage(ox, oy, scaled_sp)
            p_fg.end()
        else:
            p_fg = QPainter(fg)
            p_fg.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p_fg.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

            all_pts = []
            for cube in self.cubes:
                if not cube.visible:
                    continue
                x0, y0, z0 = cube.position
                w, h, d = cube.size
                for pt in [(x0, y0, z0), (x0 + w, y0 + h, z0 + d)]:
                    all_pts.append(self.transform_vertex(pt, cube))

            if all_pts:
                cx = sum(p[0] for p in all_pts) / len(all_pts)
                cy = sum(p[1] for p in all_pts) / len(all_pts)
                cz = sum(p[2] for p in all_pts) / len(all_pts)
                max_span = max(
                    10.0,
                    max(abs(p[0] - cx) + abs(p[1] - cy) + abs(p[2] - cz) for p in all_pts) * 1.38
                )
                zoom_mult = 1.0 if draw_egg_badge else max(0.4, self.icon_zoom)
                scale = ((icon_size * 0.80) / max_span) * zoom_mult

                yaw_d = -38.0 if draw_egg_badge else self.icon_yaw
                pitch_d = 25.0 if draw_egg_badge else self.icon_pitch
                roll_d = 0.0 if draw_egg_badge else self.icon_roll

                yaw = math.radians(yaw_d)
                pitch = math.radians(pitch_d)
                roll = math.radians(roll_d)
                cyaw, syaw = math.cos(yaw), math.sin(yaw)
                cpit, spit = math.cos(pitch), math.sin(pitch)
                crol, srol = math.cos(roll), math.sin(roll)

                def proj(pt3d):
                    x, y, z = pt3d[0] - cx, pt3d[1] - cy, pt3d[2] - cz
                    x1 = x * cyaw - z * syaw
                    z1 = x * syaw + z * cyaw
                    y2 = y * cpit - z1 * spit
                    z2 = y * spit + z1 * cpit
                    xr = x1 * crol - y2 * srol
                    yr = x1 * srol + y2 * crol
                    return (icon_size * 0.5 + xr * scale, icon_size * 0.54 - yr * scale, z2)

                face_indices = {
                    "top":    (3, 2, 6, 7),
                    "bottom": (4, 5, 1, 0),
                    "north":  (7, 6, 5, 4),
                    "south":  (2, 3, 0, 1),
                    "east":   (6, 2, 1, 5),
                    "west":   (3, 7, 4, 0),
                }
                face_light = {"top": 1.0, "north": 0.84, "south": 0.80, "east": 0.66, "west": 0.64, "bottom": 0.46}

                quads = []
                for cube in self.cubes:
                    if not cube.visible:
                        continue
                    x0, y0, z0 = cube.position
                    w, h, d = cube.size
                    x1, y1, z1 = x0 + w, y0 + h, z0 + d
                    v = [
                        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
                    ]
                    tv = [proj(self.transform_vertex(pt, cube)) for pt in v]
                    rects = cube.get_face_uv_rects()

                    for fname, (i0, i1, i2, i3) in face_indices.items():
                        r = rects[fname]
                        avg_z = (tv[i0][2] + tv[i1][2] + tv[i2][2] + tv[i3][2]) * 0.25
                        poly = QPolygonF([
                            QPointF(tv[i0][0], tv[i0][1]),
                            QPointF(tv[i1][0], tv[i1][1]),
                            QPointF(tv[i2][0], tv[i2][1]),
                            QPointF(tv[i3][0], tv[i3][1]),
                        ])
                        quads.append((avg_z, poly, r, fname))

                quads.sort(key=lambda q: q[0], reverse=True)

                for _, poly, uv_r, fname in quads:
                    sub_img = self.texture_image.copy(uv_r.u, uv_r.v, max(1, uv_r.w), max(1, uv_r.h))
                    crisp_w = max(16, uv_r.w * 8)
                    crisp_h = max(16, uv_r.h * 8)
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
                    tr = QTransform()
                    if QTransform.quadToQuad(src_poly, poly, tr):
                        p_fg.save()
                        p_fg.setTransform(tr)
                        p_fg.drawImage(0, 0, crisp_img)
                        p_fg.restore()

                    light = face_light.get(fname, 0.8)
                    shade_alpha = int(round((1.0 - light) * 195))
                    if shade_alpha > 0:
                        p_fg.setBrush(QBrush(QColor(0, 0, 0, shade_alpha)))
                        p_fg.setPen(Qt.PenStyle.NoPen)
                        p_fg.drawPolygon(poly)

            p_fg.end()

        if self.icon_outline:
            fg = self._apply_pixel_art_outline(fg, QColor(self.icon_outline_color))

        # Assemblage final (Fond de rareté ou Badge d'Oeuf + Premier plan)
        final_icon = QImage(icon_size, icon_size, QImage.Format.Format_ARGB32)
        final_icon.fill(QColor(0, 0, 0, 0))
        painter = QPainter(final_icon)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if draw_egg_badge:
            painter.setBrush(QBrush(QColor(30, 58, 138, 225)))
            painter.setPen(QPen(QColor("#60a5fa"), 2.2))
            painter.drawEllipse(5, 3, icon_size - 10, icon_size - 6)
        elif self.icon_rarity_bg != "none":
            rarity_styles = {
                "common":    (QColor(30, 41, 59, 190), QColor("#94a3b8")),
                "rare":      (QColor(23, 37, 84, 200), QColor("#38bdf8")),
                "epic":      (QColor(59, 7, 100, 200), QColor("#c084fc")),
                "legendary": (QColor(69, 26, 3, 210),  QColor("#facc15")),
            }
            bg_c, border_c = rarity_styles.get(self.icon_rarity_bg, rarity_styles["common"])
            painter.setBrush(QBrush(bg_c))
            painter.setPen(QPen(border_c, 2.2))
            painter.drawRoundedRect(QRectF(2, 2, icon_size - 4, icon_size - 4), 6, 6)

        painter.drawImage(0, 0, fg)
        painter.end()
        return final_icon

    # =========================================================================
    # OPÉRATIONS D'ÉDITION 3D (CUBES & BONES)
    # =========================================================================
    def get_selected_cube(self) -> Optional[ModelCube]:
        for c in self.cubes:
            if c.cube_id == self.selected_cube_id:
                return c
        return None

    def get_selected_bone(self) -> Optional[ModelBone]:
        if self.selected_bone_name and self.selected_bone_name in self.bones:
            return self.bones[self.selected_bone_name]
        cube = self.get_selected_cube()
        if cube and cube.bone_name in self.bones:
            return self.bones[cube.bone_name]
        return self.bones.get("root")

    def select_cube(self, cube_id: Optional[str]):
        self.selected_cube_id = cube_id
        cube = self.get_selected_cube()
        if cube:
            self.selected_bone_name = cube.bone_name
        self.selectionChanged.emit()

    def select_bone(self, bone_name: str):
        if bone_name in self.bones:
            self.selected_bone_name = bone_name
            self.selectionChanged.emit()

    def add_cube(self, name: Optional[str] = None, bone_name: Optional[str] = None) -> ModelCube:
        idx = len(self.cubes) + 1
        cid = f"cube_{idx}_{id(self) % 1000}"
        target_bone = bone_name or self.selected_bone_name or "root"
        if target_bone not in self.bones:
            target_bone = "root"

        new_cube = ModelCube(
            cube_id=cid,
            name=name or f"Cube_{idx}",
            bone_name=target_bone,
            position=[-3.0, 4.0 + (idx % 4) * 2.0, -3.0],
            size=[6.0, 6.0, 6.0],
            pivot=[0.0, 7.0, 0.0],
        )
        self.cubes.append(new_cube)
        self.auto_pack_uv_atlas(repaint_default_colors=False)
        self.select_cube(new_cube.cube_id)
        self.modelChanged.emit()
        return new_cube

    def duplicate_selected_cube(self) -> Optional[ModelCube]:
        src = self.get_selected_cube()
        if not src:
            return None
        idx = len(self.cubes) + 1
        dup = ModelCube(
            cube_id=f"cube_dup_{idx}",
            name=f"{src.name}_copie",
            bone_name=src.bone_name,
            position=[src.position[0] + 2.0, src.position[1], src.position[2]],
            size=list(src.size),
            pivot=list(src.pivot),
            rotation=list(src.rotation),
        )
        self.cubes.append(dup)
        self.auto_pack_uv_atlas(repaint_default_colors=False)
        self.select_cube(dup.cube_id)
        self.modelChanged.emit()
        return dup

    def mirror_selected_cube_x(self) -> Optional[ModelCube]:
        src = self.get_selected_cube()
        if not src:
            return None
        src.position[0] = -(src.position[0] + src.size[0])
        src.pivot[0] = -src.pivot[0]
        src.rotation[1] = -src.rotation[1]
        src.rotation[2] = -src.rotation[2]
        self.modelChanged.emit()
        return src

    def delete_selected_cube(self):
        if not self.selected_cube_id or len(self.cubes) <= 1:
            return
        self.cubes = [c for c in self.cubes if c.cube_id != self.selected_cube_id]
        self.selected_cube_id = self.cubes[0].cube_id if self.cubes else None
        self.selectionChanged.emit()
        self.modelChanged.emit()

    def add_bone(self, name: str, parent_name: Optional[str] = "root") -> ModelBone:
        clean_name = name.strip().replace(" ", "_") or f"bone_{len(self.bones) + 1}"
        if clean_name in self.bones:
            clean_name = f"{clean_name}_{len(self.bones) + 1}"
        parent = parent_name if parent_name in self.bones else "root"
        bone = ModelBone(clean_name, parent, [0.0, 8.0, 0.0])
        self.bones[clean_name] = bone
        self.selected_bone_name = clean_name
        self.modelChanged.emit()
        self.selectionChanged.emit()
        return bone

    # =========================================================================
    # PEINTURE DE TEXTURE & UNDO / REDO
    # =========================================================================
    def push_undo_snapshot(self):
        self._undo_stack.append(self.texture_image.copy())
        if len(self._undo_stack) > 40:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo_texture(self):
        if self._undo_stack:
            self._redo_stack.append(self.texture_image.copy())
            self.texture_image = self._undo_stack.pop()
            self.textureChanged.emit()

    def redo_texture(self):
        if self._redo_stack:
            self._undo_stack.append(self.texture_image.copy())
            self.texture_image = self._redo_stack.pop()
            self.textureChanged.emit()

    def paint_texel(self, u: int, v: int, color: QColor, brush_size: int = 1):
        half = max(0, (brush_size - 1) // 2)
        changed = False
        for dy in range(-half, brush_size - half):
            for dx in range(-half, brush_size - half):
                px, py = u + dx, v + dy
                if 0 <= px < self.atlas_width and 0 <= py < self.atlas_height:
                    self.texture_image.setPixelColor(px, py, color)
                    changed = True
        if changed:
            self.textureChanged.emit()

    def fill_cube_face(self, cube: ModelCube, face_name: str, color: QColor, noise_strength: int = 0):
        rects = cube.get_face_uv_rects()
        rect = rects.get(face_name)
        if not rect:
            return
        for dy in range(rect.h):
            for dx in range(rect.w):
                px, py = rect.u + dx, rect.v + dy
                if 0 <= px < self.atlas_width and 0 <= py < self.atlas_height:
                    c = QColor(color)
                    if noise_strength > 0:
                        delta = ((dx * 13 + dy * 29) % (2 * noise_strength + 1)) - noise_strength
                        c = c.lighter(100 + delta) if delta >= 0 else c.darker(100 - delta)
                    self.texture_image.setPixelColor(px, py, c)
        self.textureChanged.emit()

    # =========================================================================
    # SÉRIALISATION COMPLÈTE (.LUANTIPROJ)
    # =========================================================================
    @staticmethod
    def _qimage_to_b64(img: QImage) -> str:
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        return base64.b64encode(bytes(buf.data())).decode("ascii")

    @staticmethod
    def _b64_to_qimage(b64_str: str) -> Optional[QImage]:
        if not b64_str:
            return None
        raw_bytes = base64.b64decode(b64_str.encode("ascii"))
        img = QImage.fromData(raw_bytes, "PNG")
        return img.convertToFormat(QImage.Format.Format_ARGB32) if not img.isNull() else None

    def to_dict(self) -> Dict[str, Any]:
        tl_obj = getattr(self, "timeline_data", None)
        tl_dict = tl_obj.to_dict() if tl_obj is not None else self._pending_timeline_dict

        return {
            "category": self.category,
            "name": self.name,
            "atlas_width": self.atlas_width,
            "atlas_height": self.atlas_height,
            "grid_size": self.grid_size,
            "ai_behavior": self.ai_behavior,
            "max_hp": self.max_hp,
            "move_speed": self.move_speed,
            "attack_damage": self.attack_damage,
            "drop_item": self.drop_item,
            "light_source": self.light_source,
            "animate_in_game": self.animate_in_game,
            "icon_mode": self.icon_mode,
            "icon_yaw": self.icon_yaw,
            "icon_pitch": self.icon_pitch,
            "icon_roll": self.icon_roll,
            "icon_zoom": self.icon_zoom,
            "icon_outline": self.icon_outline,
            "icon_outline_color": self.icon_outline_color,
            "icon_rarity_bg": self.icon_rarity_bg,
            "item_kind": self.item_kind,
            "wield_scale": list(self.wield_scale),
            "tool_range": self.tool_range,
            "punch_interval": self.punch_interval,
            "tool_uses": self.tool_uses,
            "mine_cracky": self.mine_cracky,
            "mine_choppy": self.mine_choppy,
            "mine_snappy": self.mine_snappy,
            "mine_crumbly": self.mine_crumbly,
            "item_heal_hp": self.item_heal_hp,
            "item_shoot_projectile": self.item_shoot_projectile,
            "item_hit_particles": self.item_hit_particles,
            "bones": {k: b.to_dict() for k, b in self.bones.items()},
            "cubes": [c.to_dict() for c in self.cubes],
            "texture_png_b64": self._qimage_to_b64(self.texture_image),
            "sprite_2d_b64": self._qimage_to_b64(self.sprite_2d_image),
            "timeline": tl_dict,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ModelData":
        obj = cls(
            category=d.get("category", "Mobs"),
            name=d.get("name", "modele"),
            atlas_size=int(d.get("atlas_width", 64)),
        )
        obj.atlas_width = int(d.get("atlas_width", 64))
        obj.atlas_height = int(d.get("atlas_height", 64))
        obj.grid_size = int(d.get("grid_size", 16))
        obj.ai_behavior = d.get("ai_behavior", "passive")
        obj.max_hp = int(d.get("max_hp", 20))
        obj.move_speed = float(d.get("move_speed", 2.5))
        obj.attack_damage = int(d.get("attack_damage", 4))
        obj.drop_item = d.get("drop_item", "default:mese_crystal_fragment")
        obj.light_source = int(d.get("light_source", 0))
        obj.animate_in_game = bool(d.get("animate_in_game", True))

        obj.icon_mode = d.get("icon_mode", "3d_render")
        obj.icon_yaw = float(d.get("icon_yaw", -38.0))
        obj.icon_pitch = float(d.get("icon_pitch", 25.0))
        obj.icon_roll = float(d.get("icon_roll", 0.0))
        obj.icon_zoom = float(d.get("icon_zoom", 1.0))
        obj.icon_outline = bool(d.get("icon_outline", True))
        obj.icon_outline_color = d.get("icon_outline_color", "#0f172a")
        obj.icon_rarity_bg = d.get("icon_rarity_bg", "none")

        obj.item_kind = d.get("item_kind", "tool")
        obj.wield_scale = list(d.get("wield_scale", [1.45, 1.45, 1.25]))
        obj.tool_range = float(d.get("tool_range", 4.5))
        obj.punch_interval = float(d.get("punch_interval", 0.65))
        obj.tool_uses = int(d.get("tool_uses", 120))
        obj.mine_cracky = int(d.get("mine_cracky", 3))
        obj.mine_choppy = int(d.get("mine_choppy", 2))
        obj.mine_snappy = int(d.get("mine_snappy", 3))
        obj.mine_crumbly = int(d.get("mine_crumbly", 1))
        obj.item_heal_hp = int(d.get("item_heal_hp", 0))
        obj.item_shoot_projectile = bool(d.get("item_shoot_projectile", False))
        obj.item_hit_particles = bool(d.get("item_hit_particles", True))

        obj.bones = {k: ModelBone.from_dict(v) for k, v in d.get("bones", {}).items()}
        obj.cubes = [ModelCube.from_dict(c) for c in d.get("cubes", [])]

        tex_img = cls._b64_to_qimage(d.get("texture_png_b64", ""))
        if tex_img is not None:
            obj.texture_image = tex_img

        sp_img = cls._b64_to_qimage(d.get("sprite_2d_b64", ""))
        if sp_img is not None:
            obj.sprite_2d_image = sp_img

        if "timeline" in d and d["timeline"]:
            obj._pending_timeline_dict = d["timeline"]

        if obj.cubes:
            obj.selected_cube_id = obj.cubes[0].cube_id
            obj.selected_bone_name = obj.cubes[0].bone_name
        return obj