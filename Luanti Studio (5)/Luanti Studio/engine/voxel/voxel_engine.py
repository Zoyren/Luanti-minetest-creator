# -*- coding: utf-8 -*-
"""
engine/voxel/voxel_engine.py
Moteur de Monde Voxel 3D équivalent Minetest / Luanti + Outils Géométriques MagicaVoxel :
- Catalogue étendu de +42 Blocs Minetest + Blocs 3D Custom du Studio
- Générateur des 13 Formes 3D Préfaites (Cercle, Cylindre, Sphère, Dôme, Pyramide, Cône, Tore, Arche, Escalier, Carré, Rectangle...)
- Tracé de Ligne 3D entre Pos1 et Pos2 + Symétrie Miroir X / Z en temps réel.
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    from PyQt6.QtCore import QObject, pyqtSignal
    from PyQt6.QtGui import QImage, QColor
except ImportError:
    from PyQt5.QtCore import QObject, pyqtSignal
    from PyQt5.QtGui import QImage, QColor

from engine.voxel.magicavoxel_tools import MagicaShapeGenerator


VOXEL_NEIGHBORS: Dict[str, Tuple[int, int, int]] = {
    "top":    (0, 1, 0),
    "bottom": (0, -1, 0),
    "north":  (0, 0, 1),
    "south":  (0, 0, -1),
    "east":   (1, 0, 0),
    "west":   (-1, 0, 0),
}


@dataclass
class VoxelBlockDef:
    node_name: str
    display_name: str
    category: str
    top_tex: QImage
    bottom_tex: QImage
    side_tex: QImage
    transparent: bool = False
    custom_model_data: Any = None

    def get_face_texture(self, face_name: str) -> QImage:
        if face_name == "top":
            return self.top_tex
        if face_name == "bottom":
            return self.bottom_tex
        return self.side_tex


class VoxelEngine(QObject):
    """
    Moteur de données Voxel 3D avec grande bibliothèque de blocs Minetest, support 3D Custom et formes MagicaVoxel.
    """
    worldChanged = pyqtSignal()
    paletteChanged = pyqtSignal()
    gridSizeChanged = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.voxels: Dict[Tuple[int, int, int], str] = {}
        self.block_defs: Dict[str, VoxelBlockDef] = {}

        self.grid_size: int = 32
        self.export_void_world: bool = True

        # Options de symétrie temps réel MagicaVoxel
        self.symmetry_x: bool = False
        self.symmetry_z: bool = False

        self.pos1: Optional[Tuple[int, int, int]] = None
        self.pos2: Optional[Tuple[int, int, int]] = None

        self._undo_stack: List[Dict[Tuple[int, int, int], str]] = []
        self._build_extended_minetest_palette()
        self.generate_terrain_preset("minetest_valley")

    def set_grid_size(self, new_size: int):
        self.grid_size = max(16, min(512, int(new_size)))
        self.gridSizeChanged.emit(self.grid_size)
        self.worldChanged.emit()

    # =========================================================================
    # CATALOGUE ÉTENDU DE +42 BLOCS MINETEST AVEC TEXTURES 16x16 PROCÉDURALES
    # =========================================================================
    def _build_extended_minetest_palette(self):
        dirt = self._make_noisy_16x16(QColor("#785233"), 14)
        grass_top = self._make_noisy_16x16(QColor("#4d9e34"), 12)
        grass_side = self._make_grass_side_16x16(dirt, QColor("#4d9e34"))

        dry_top = self._make_noisy_16x16(QColor("#b89c40"), 12)
        dry_side = self._make_grass_side_16x16(dirt, QColor("#b89c40"))

        snow_top = self._make_noisy_16x16(QColor("#f1f5f9"), 6)
        snow_side = self._make_grass_side_16x16(dirt, QColor("#f1f5f9"))
        ice_tex = self._make_noisy_16x16(QColor("#93c5fd"), 8)

        sand = self._make_noisy_16x16(QColor("#d9c882"), 10)
        desert_sand = self._make_noisy_16x16(QColor("#d98a4e"), 11)
        silver_sand = self._make_noisy_16x16(QColor("#cbd5e1"), 9)
        gravel = self._make_noisy_16x16(QColor("#646970"), 20)
        clay = self._make_noisy_16x16(QColor("#94a3b8"), 8)

        stone = self._make_noisy_16x16(QColor("#7d8288"), 12)
        cobble = self._make_cobble_16x16(QColor("#7c8288"), QColor("#4b5056"))
        mossycobble = self._make_cobble_16x16(QColor("#657c56"), QColor("#365327"))
        stonebrick = self._make_bricks_16x16(QColor("#7d8288"), QColor("#475569"))

        desert_stone = self._make_noisy_16x16(QColor("#9c4a38"), 12)
        desert_cobble = self._make_cobble_16x16(QColor("#9c4a38"), QColor("#632b1f"))
        desert_stonebrick = self._make_bricks_16x16(QColor("#9c4a38"), QColor("#5c261b"))
        sandstone = self._make_noisy_16x16(QColor("#d4c285"), 8)
        sandstonebrick = self._make_bricks_16x16(QColor("#d4c285"), QColor("#a39056"))
        obsidian = self._make_noisy_16x16(QColor("#171324"), 10)

        coal_ore = self._make_ore_16x16(stone, QColor("#18181b"))
        iron_ore = self._make_ore_16x16(stone, QColor("#d97706"))
        copper_ore = self._make_ore_16x16(stone, QColor("#ea580c"))
        gold_ore = self._make_ore_16x16(stone, QColor("#facc15"))
        mese_ore = self._make_ore_16x16(stone, QColor("#eab308"))
        diamond_ore = self._make_ore_16x16(stone, QColor("#38bdf8"))

        wood = self._make_planks_16x16(QColor("#a37846"))
        junglewood = self._make_planks_16x16(QColor("#734429"))
        pine_wood = self._make_planks_16x16(QColor("#c9a56b"))
        acacia_wood = self._make_planks_16x16(QColor("#b84b39"))

        tree_bark = self._make_bark_16x16(QColor("#594026"))
        tree_top = self._make_tree_rings_16x16(QColor("#b58d58"), QColor("#594026"))
        jtree_bark = self._make_bark_16x16(QColor("#3d2817"))
        ptree_bark = self._make_bark_16x16(QColor("#4a3b2c"))

        leaves = self._make_noisy_16x16(QColor("#2f6e22"), 18)
        jleaves = self._make_noisy_16x16(QColor("#1e5928"), 18)
        pine_needles = self._make_noisy_16x16(QColor("#1b4332"), 16)
        cactus_side = self._make_bark_16x16(QColor("#2e7d32"))

        brick = self._make_bricks_16x16(QColor("#9e3b33"), QColor("#cbd5e1"))
        glass = self._make_glass_16x16(QColor("#e0f2fe"))
        obs_glass = self._make_glass_16x16(QColor("#64748b"))
        meselamp = self._make_gem_block_16x16(QColor("#fef08a"))
        steelblock = self._make_gem_block_16x16(QColor("#cbd5e1"))
        copperblock = self._make_gem_block_16x16(QColor("#ea580c"))
        goldblock = self._make_gem_block_16x16(QColor("#f59e0b"))
        meseblock = self._make_gem_block_16x16(QColor("#eab308"))
        diamondblock = self._make_gem_block_16x16(QColor("#38bdf8"))
        bookshelf = self._make_bookshelf_16x16(wood)

        water = self._make_water_16x16(QColor(37, 99, 235, 195), QColor(56, 189, 248, 195))
        river_water = self._make_water_16x16(QColor(14, 165, 233, 195), QColor(125, 211, 252, 195))
        lava = self._make_water_16x16(QColor(220, 38, 38, 240), QColor(249, 115, 22, 240))

        catalog = [
            VoxelBlockDef("default:dirt_with_grass", "Herbe Minetest", "🌿 Nature & Sols", grass_top, dirt, grass_side),
            VoxelBlockDef("default:dirt_with_dry_grass", "Herbe Sèche (Savane)", "🌿 Nature & Sols", dry_top, dirt, dry_side),
            VoxelBlockDef("default:dirt_with_snow", "Terre Enneigée", "🌿 Nature & Sols", snow_top, dirt, snow_side),
            VoxelBlockDef("default:dirt", "Terre", "🌿 Nature & Sols", dirt, dirt, dirt),
            VoxelBlockDef("default:sand", "Sable", "🌿 Nature & Sols", sand, sand, sand),
            VoxelBlockDef("default:desert_sand", "Sable du Désert", "🌿 Nature & Sols", desert_sand, desert_sand, desert_sand),
            VoxelBlockDef("default:silver_sand", "Sable Argenté", "🌿 Nature & Sols", silver_sand, silver_sand, silver_sand),
            VoxelBlockDef("default:gravel", "Gravier", "🌿 Nature & Sols", gravel, gravel, gravel),
            VoxelBlockDef("default:clay", "Argile", "🌿 Nature & Sols", clay, clay, clay),
            VoxelBlockDef("default:snowblock", "Bloc de Neige", "🌿 Nature & Sols", snow_top, snow_top, snow_top),
            VoxelBlockDef("default:ice", "Glace", "🌿 Nature & Sols", ice_tex, ice_tex, ice_tex),

            VoxelBlockDef("default:stone", "Pierre", "🪨 Pierres & Minerais", stone, stone, stone),
            VoxelBlockDef("default:cobble", "Pierre Taillée (Cobble)", "🪨 Pierres & Minerais", cobble, cobble, cobble),
            VoxelBlockDef("default:mossycobble", "Cobble Moussue", "🪨 Pierres & Minerais", mossycobble, mossycobble, mossycobble),
            VoxelBlockDef("default:stonebrick", "Briques de Pierre", "🪨 Pierres & Minerais", stonebrick, stonebrick, stonebrick),
            VoxelBlockDef("default:desert_stone", "Pierre du Désert", "🪨 Pierres & Minerais", desert_stone, desert_stone, desert_stone),
            VoxelBlockDef("default:desert_cobble", "Cobble du Désert", "🪨 Pierres & Minerais", desert_cobble, desert_cobble, desert_cobble),
            VoxelBlockDef("default:desert_stonebrick", "Briques du Désert", "🪨 Pierres & Minerais", desert_stonebrick, desert_stonebrick, desert_stonebrick),
            VoxelBlockDef("default:sandstone", "Grès (Sandstone)", "🪨 Pierres & Minerais", sandstone, sandstone, sandstone),
            VoxelBlockDef("default:sandstonebrick", "Briques de Grès", "🪨 Pierres & Minerais", sandstonebrick, sandstonebrick, sandstonebrick),
            VoxelBlockDef("default:obsidian", "Obsidienne", "🪨 Pierres & Minerais", obsidian, obsidian, obsidian),
            VoxelBlockDef("default:stone_with_coal", "Minerai de Charbon", "🪨 Pierres & Minerais", coal_ore, coal_ore, coal_ore),
            VoxelBlockDef("default:stone_with_iron", "Minerai de Fer", "🪨 Pierres & Minerais", iron_ore, iron_ore, iron_ore),
            VoxelBlockDef("default:stone_with_copper", "Minerai de Cuivre", "🪨 Pierres & Minerais", copper_ore, copper_ore, copper_ore),
            VoxelBlockDef("default:stone_with_gold", "Minerai d'Or", "🪨 Pierres & Minerais", gold_ore, gold_ore, gold_ore),
            VoxelBlockDef("default:stone_with_mese", "Minerai de Mese", "🪨 Pierres & Minerais", mese_ore, mese_ore, mese_ore),
            VoxelBlockDef("default:stone_with_diamond", "Minerai de Diamant", "🪨 Pierres & Minerais", diamond_ore, diamond_ore, diamond_ore),

            VoxelBlockDef("default:wood", "Planches de Pommier", "🌲 Bois & Végétation", wood, wood, wood),
            VoxelBlockDef("default:junglewood", "Planches de Jungle", "🌲 Bois & Végétation", junglewood, junglewood, junglewood),
            VoxelBlockDef("default:pine_wood", "Planches de Pin", "🌲 Bois & Végétation", pine_wood, pine_wood, pine_wood),
            VoxelBlockDef("default:acacia_wood", "Planches d'Acacia", "🌲 Bois & Végétation", acacia_wood, acacia_wood, acacia_wood),
            VoxelBlockDef("default:tree", "Tronc de Pommier", "🌲 Bois & Végétation", tree_top, tree_top, tree_bark),
            VoxelBlockDef("default:jungletree", "Tronc de Jungle", "🌲 Bois & Végétation", tree_top, tree_top, jtree_bark),
            VoxelBlockDef("default:pine_tree", "Tronc de Pin", "🌲 Bois & Végétation", tree_top, tree_top, ptree_bark),
            VoxelBlockDef("default:leaves", "Feuillage de Pommier", "🌲 Bois & Végétation", leaves, leaves, leaves),
            VoxelBlockDef("default:jungleleaves", "Feuillage de Jungle", "🌲 Bois & Végétation", jleaves, jleaves, jleaves),
            VoxelBlockDef("default:pine_needles", "Aiguilles de Pin", "🌲 Bois & Végétation", pine_needles, pine_needles, pine_needles),
            VoxelBlockDef("default:cactus", "Cactus", "🌲 Bois & Végétation", cactus_side, cactus_side, cactus_side),

            VoxelBlockDef("default:brick", "Briques d'Argile", "🧱 Construction & Lumière", brick, brick, brick),
            VoxelBlockDef("default:bookshelf", "Bibliothèque", "🧱 Construction & Lumière", wood, wood, bookshelf),
            VoxelBlockDef("default:glass", "Verre Minetest", "🧱 Construction & Lumière", glass, glass, glass, transparent=True),
            VoxelBlockDef("default:obsidian_glass", "Verre d'Obsidienne", "🧱 Construction & Lumière", obs_glass, obs_glass, obs_glass, transparent=True),
            VoxelBlockDef("default:meselamp", "Lampe de Mese", "🧱 Construction & Lumière", meselamp, meselamp, meselamp),
            VoxelBlockDef("default:steelblock", "Bloc d'Acier", "🧱 Construction & Lumière", steelblock, steelblock, steelblock),
            VoxelBlockDef("default:copperblock", "Bloc de Cuivre", "🧱 Construction & Lumière", copperblock, copperblock, copperblock),
            VoxelBlockDef("default:goldblock", "Bloc d'Or", "🧱 Construction & Lumière", goldblock, goldblock, goldblock),
            VoxelBlockDef("default:mese", "Bloc de Mese", "🧱 Construction & Lumière", meseblock, meseblock, meseblock),
            VoxelBlockDef("default:diamondblock", "Bloc de Diamant", "🧱 Construction & Lumière", diamondblock, diamondblock, diamondblock),

            VoxelBlockDef("default:water_source", "Eau (Source)", "💧 Liquides", water, water, water, transparent=True),
            VoxelBlockDef("default:river_water_source", "Eau de Rivière", "💧 Liquides", river_water, river_water, river_water, transparent=True),
            VoxelBlockDef("default:lava_source", "Lave en Fusion", "💧 Liquides", lava, lava, lava),
        ]

        for b in catalog:
            self.block_defs[b.node_name] = b

    @staticmethod
    def _make_noisy_16x16(base: QColor, amp: int) -> QImage:
        img = QImage(16, 16, QImage.Format.Format_ARGB32)
        for y in range(16):
            for x in range(16):
                h = ((x * 37 + y * 59 + (x * y) * 13) % (2 * amp + 1)) - amp
                c = base.lighter(100 + h) if h >= 0 else base.darker(100 - h)
                img.setPixelColor(x, y, c)
        return img

    @staticmethod
    def _make_grass_side_16x16(dirt_img: QImage, grass_col: QColor) -> QImage:
        img = dirt_img.copy()
        fringe = [4, 5, 3, 4, 6, 4, 3, 5, 4, 3, 5, 6, 4, 3, 5, 4]
        for x in range(16):
            for y in range(fringe[x]):
                h = ((x * 19 + y * 31) % 17) - 8
                c = grass_col.lighter(100 + h) if h >= 0 else grass_col.darker(100 - h)
                img.setPixelColor(x, y, c)
        return img

    @staticmethod
    def _make_cobble_16x16(stone_col: QColor, mortar_col: QColor) -> QImage:
        img = QImage(16, 16, QImage.Format.Format_ARGB32)
        for y in range(16):
            for x in range(16):
                mortar = ((x + (y // 4) * 3) % 4 == 0) or (y % 4 == 0)
                if mortar:
                    c = mortar_col
                else:
                    v = ((x * 23 + y * 41) % 24) - 12
                    c = stone_col.lighter(100 + v)
                img.setPixelColor(x, y, c)
        return img

    @staticmethod
    def _make_ore_16x16(stone_img: QImage, ore_col: QColor) -> QImage:
        img = stone_img.copy()
        spots = [(3, 3), (4, 3), (3, 4), (10, 4), (11, 5), (5, 10), (6, 10), (6, 11), (12, 11), (11, 12)]
        for sx, sy in spots:
            img.setPixelColor(sx, sy, ore_col)
            if (sx + sy) % 2 == 0:
                img.setPixelColor(min(15, sx + 1), sy, ore_col.lighter(125))
        return img

    @staticmethod
    def _make_planks_16x16(base: QColor) -> QImage:
        img = QImage(16, 16, QImage.Format.Format_ARGB32)
        for y in range(16):
            for x in range(16):
                if y % 4 == 0 or (x == ((y // 4) * 7) % 16):
                    c = base.darker(135)
                else:
                    v = ((x * 11 + y * 29) % 14) - 7
                    c = base.lighter(100 + v)
                img.setPixelColor(x, y, c)
        return img

    @staticmethod
    def _make_bark_16x16(base: QColor) -> QImage:
        img = QImage(16, 16, QImage.Format.Format_ARGB32)
        for y in range(16):
            for x in range(16):
                stripe = -14 if (x % 3 == 0) else (((x * 17 + y * 7) % 14) - 7)
                c = base.lighter(100 + stripe) if stripe >= 0 else base.darker(100 - stripe)
                img.setPixelColor(x, y, c)
        return img

    @staticmethod
    def _make_tree_rings_16x16(inner: QColor, bark: QColor) -> QImage:
        img = QImage(16, 16, QImage.Format.Format_ARGB32)
        for y in range(16):
            for x in range(16):
                if x in (0, 15) or y in (0, 15):
                    c = bark
                else:
                    dist = max(abs(x - 7.5), abs(y - 7.5))
                    c = inner.darker(118) if int(dist) % 2 == 0 else inner
                img.setPixelColor(x, y, c)
        return img

    @staticmethod
    def _make_bricks_16x16(brick: QColor, mortar: QColor) -> QImage:
        img = QImage(16, 16, QImage.Format.Format_ARGB32)
        for y in range(16):
            for x in range(16):
                row = y // 4
                is_mortar = (y % 4 == 0) or ((x + row * 4) % 8 == 0)
                c = mortar if is_mortar else brick.lighter(100 + ((x * 13 + y * 19) % 12) - 6)
                img.setPixelColor(x, y, c)
        return img

    @staticmethod
    def _make_bookshelf_16x16(wood_img: QImage) -> QImage:
        img = wood_img.copy()
        book_cols = [QColor("#dc2626"), QColor("#2563eb"), QColor("#16a34a"), QColor("#d97706"), QColor("#9333ea")]
        for shelf_y in (2, 9):
            for y in range(shelf_y, shelf_y + 5):
                for x in range(1, 15):
                    bcol = book_cols[(x // 2 + shelf_y) % len(book_cols)]
                    img.setPixelColor(x, y, bcol.darker(120) if x % 2 == 0 else bcol)
        return img

    @staticmethod
    def _make_water_16x16(c1: QColor, c2: QColor) -> QImage:
        img = QImage(16, 16, QImage.Format.Format_ARGB32)
        for y in range(16):
            for x in range(16):
                img.setPixelColor(x, y, c2 if (x + y) % 5 == 0 else c1)
        return img

    @staticmethod
    def _make_glass_16x16(border: QColor) -> QImage:
        img = QImage(16, 16, QImage.Format.Format_ARGB32)
        img.fill(QColor(border.red(), border.green(), border.blue(), 42))
        for i in range(16):
            img.setPixelColor(i, 0, border)
            img.setPixelColor(i, 15, border)
            img.setPixelColor(0, i, border)
            img.setPixelColor(15, i, border)
        for k in range(3, 8):
            img.setPixelColor(k, 10 - k, border)
        return img

    @staticmethod
    def _make_gem_block_16x16(base: QColor) -> QImage:
        img = QImage(16, 16, QImage.Format.Format_ARGB32)
        for y in range(16):
            for x in range(16):
                if x in (0, 15) or y in (0, 15):
                    c = base.darker(135)
                elif x in (1, 14) or y in (1, 14):
                    c = base.lighter(135)
                else:
                    c = base.lighter(115) if (x + y) % 4 == 0 else base
                img.setPixelColor(x, y, c)
        return img

    def register_custom_studio_block(self, node_name: str, display_name: str, model_data: Any):
        icon_img = model_data.render_isometric_icon(32, draw_egg_badge=False)
        self.block_defs[node_name] = VoxelBlockDef(
            node_name=node_name,
            display_name=f"★ {display_name}",
            category="⭐ Blocs Custom du Mod",
            top_tex=icon_img,
            bottom_tex=icon_img,
            side_tex=icon_img,
            transparent=True,
            custom_model_data=model_data,
        )
        self.paletteChanged.emit()

    # =========================================================================
    # OPÉRATIONS VOXEL & HIDDEN-FACE CULLING
    # =========================================================================
    def push_undo(self):
        self._undo_stack.append(dict(self.voxels))
        if len(self._undo_stack) > 30:
            self._undo_stack.pop(0)

    def undo(self):
        if self._undo_stack:
            self.voxels = self._undo_stack.pop()
            self.worldChanged.emit()

    def set_voxel(self, x: int, y: int, z: int, node_name: Optional[str], emit_signal: bool = True):
        pts: Set[Tuple[int, int, int]] = {(int(x), int(y), int(z))}
        if self.symmetry_x or self.symmetry_z:
            pts = MagicaShapeGenerator.apply_symmetry_3d(
                pts, sym_x=self.symmetry_x, sym_y=False, sym_z=self.symmetry_z, center=(0.0, float(y), 0.0)
            )
        for px, py, pz in pts:
            if not node_name or node_name == "air":
                self.voxels.pop((px, py, pz), None)
            else:
                self.voxels[(px, py, pz)] = node_name
        if emit_signal:
            self.worldChanged.emit()

    def get_voxel(self, x: int, y: int, z: int) -> Optional[str]:
        return self.voxels.get((int(x), int(y), int(z)))

    def is_face_visible(self, x: int, y: int, z: int, face_name: str, current_node: str) -> bool:
        dx, dy, dz = VOXEL_NEIGHBORS[face_name]
        neighbor = self.voxels.get((x + dx, y + dy, z + dz))
        if neighbor is None:
            return True
        if neighbor == current_node:
            bdef = self.block_defs.get(current_node)
            if bdef and bdef.custom_model_data is not None:
                return True
            return False
        ndef = self.block_defs.get(neighbor)
        return bool(ndef and ndef.transparent)

    # =========================================================================
    # GÉNÉRATEUR DE FORMES 3D MAGICAVOXEL DANS LE MONDE VOXEL
    # =========================================================================
    def stamp_magicavoxel_shape_in_world(
        self,
        shape_type: str,
        center: Tuple[int, int, int],
        size_xyz: Tuple[int, int, int],
        node_name: Optional[str],
        hollow: bool = False,
        thickness: int = 1,
        axis: str = "Y",
    ):
        self.push_undo()
        pts = MagicaShapeGenerator.generate_shape_voxels(
            shape_type=shape_type,
            center=center,
            size_xyz=size_xyz,
            hollow=hollow,
            thickness=thickness,
            axis=axis,
        )
        for vx, vy, vz in pts:
            self.set_voxel(vx, vy, vz, node_name, emit_signal=False)
        self.worldChanged.emit()

    def worldedit_shape_between_pos1_pos2(
        self,
        shape_type: str,
        node_name: Optional[str],
        hollow: bool = False,
        thickness: int = 1,
        axis: str = "Y",
    ):
        if not self.pos1 or not self.pos2:
            return
        self.push_undo()
        if shape_type == "line":
            pts = MagicaShapeGenerator.bresenham_line_3d(self.pos1, self.pos2, radius=max(0, thickness - 1))
            for vx, vy, vz in pts:
                self.set_voxel(vx, vy, vz, node_name, emit_signal=False)
            self.worldChanged.emit()
            return

        x0, x1 = min(self.pos1[0], self.pos2[0]), max(self.pos1[0], self.pos2[0])
        y0, y1 = min(self.pos1[1], self.pos2[1]), max(self.pos1[1], self.pos2[1])
        z0, z1 = min(self.pos1[2], self.pos2[2]), max(self.pos1[2], self.pos2[2])

        sx = max(1, x1 - x0 + 1)
        sy = max(1, y1 - y0 + 1)
        sz = max(1, z1 - z0 + 1)
        cx = int(round((x0 + x1) * 0.5))
        cy = y0
        cz = int(round((z0 + z1) * 0.5))

        pts = MagicaShapeGenerator.generate_shape_voxels(
            shape_type=shape_type,
            center=(cx, cy, cz),
            size_xyz=(sx, sy, sz),
            hollow=hollow,
            thickness=thickness,
            axis=axis,
        )
        for vx, vy, vz in pts:
            self.set_voxel(vx, vy, vz, node_name, emit_signal=False)
        self.worldChanged.emit()

    # =========================================================================
    # GÉNÉRATEURS DE MONDES ADAPTÉS À LA TAILLE DE GRILLE
    # =========================================================================
    def generate_terrain_preset(self, preset_name: str):
        self.push_undo()
        self.voxels.clear()
        half = min(24, self.grid_size // 2)

        if preset_name == "empty_void":
            pass
        elif preset_name == "flat_platform":
            for x in range(-half, half):
                for z in range(-half, half):
                    self.voxels[(x, -1, z)] = "default:stone"
                    self.voxels[(x, 0, z)] = "default:dirt_with_grass"
        elif preset_name == "floating_island":
            rad = max(6, min(14, half - 2))
            for x in range(-rad, rad + 1):
                for z in range(-rad, rad + 1):
                    dist = math.sqrt(x * x + z * z)
                    if dist <= rad + 0.2:
                        depth = int(max(1, (rad * 0.8) - dist * 0.7))
                        for y in range(-depth, 0):
                            self.voxels[(x, y, z)] = "default:stone" if y < -1 else "default:dirt"
                        self.voxels[(x, 0, z)] = "default:dirt_with_grass"
            self._place_minetest_tree(0, 1, 0)
        elif preset_name == "stone_dungeon":
            r = max(5, min(12, half - 2))
            for x in range(-r, r + 1):
                for z in range(-r, r + 1):
                    self.voxels[(x, 0, z)] = "default:stonebrick"
                    if abs(x) == r or abs(z) == r:
                        for y in range(1, 5):
                            if not (z == r and abs(x) <= 1 and y <= 2):
                                self.voxels[(x, y, z)] = "default:cobble"
            self.voxels[(0, 1, 0)] = "default:goldblock"
            self.voxels[(0, 2, 0)] = "default:meselamp"
        else:
            r = max(6, min(12, half - 2))
            for x in range(-r, r + 1):
                for z in range(-r, r + 1):
                    self.voxels[(x, -2, z)] = "default:stone"
                    if 1 <= x <= 4 and 1 <= z <= 4:
                        self.voxels[(x, -1, z)] = "default:sand"
                        self.voxels[(x, 0, z)] = "default:water_source"
                    elif 0 <= x <= 5 and 0 <= z <= 5:
                        self.voxels[(x, -1, z)] = "default:dirt"
                        self.voxels[(x, 0, z)] = "default:sand"
                    else:
                        h = 1 if (x < -2 and z < -1) else 0
                        for y in range(-1, h):
                            self.voxels[(x, y, z)] = "default:dirt"
                        self.voxels[(x, h, z)] = "default:dirt_with_grass"
            self._place_minetest_tree(-3, 2, -3)

        self.worldChanged.emit()

    def _place_minetest_tree(self, tx: int, ty: int, tz: int):
        for dy in range(4):
            self.voxels[(tx, ty + dy, tz)] = "default:tree"
        for lx in range(tx - 2, tx + 3):
            for lz in range(tz - 2, tz + 3):
                for ly in range(ty + 2, ty + 5):
                    if abs(lx - tx) + abs(lz - tz) + abs(ly - (ty + 3)) <= 3:
                        if (lx, ly, lz) != (tx, ty + 2, tz) and (lx, ly, lz) != (tx, ty + 3, tz):
                            self.voxels[(lx, ly, lz)] = "default:leaves"

    # =========================================================================
    # COMMANDES WORLDEDIT (//SET, //HOLLOW, PINCEAU SPHÈRE)
    # =========================================================================
    def worldedit_fill_region(self, node_name: str, hollow_only: bool = False):
        if not self.pos1 or not self.pos2:
            return
        self.push_undo()
        x0, x1 = min(self.pos1[0], self.pos2[0]), max(self.pos1[0], self.pos2[0])
        y0, y1 = min(self.pos1[1], self.pos2[1]), max(self.pos1[1], self.pos2[1])
        z0, z1 = min(self.pos1[2], self.pos2[2]), max(self.pos1[2], self.pos2[2])

        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                for z in range(z0, z1 + 1):
                    if hollow_only and not (x in (x0, x1) or y in (y0, y1) or z in (z0, z1)):
                        continue
                    self.set_voxel(x, y, z, node_name, emit_signal=False)
        self.worldChanged.emit()

    def apply_brush_at(self, cx: int, cy: int, cz: int, node_name: Optional[str], radius: int = 0):
        self.push_undo()
        if radius <= 0:
            self.set_voxel(cx, cy, cz, node_name, emit_signal=True)
            return
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    if dx * dx + dy * dy + dz * dz <= radius * radius + 0.5:
                        self.set_voxel(cx + dx, cy + dy, cz + dz, node_name, emit_signal=False)
        self.worldChanged.emit()