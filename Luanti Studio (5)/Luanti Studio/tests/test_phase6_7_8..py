from pathlib import Path

from engine.voxel.voxel_engine import SparseChunkVoxelGrid
from exporters.mts_exporter import LuantiSchematicExporter
from mod_manager.indexer import LuantiResourceIndexer
from plugins.plugin_manager import PluginManager


def test_phase6_voxel_chunks_mts_and_playable_world(tmp_path: Path) -> None:
    """Vérifie le moteur Voxel par chunks jusqu'à 600x600x256, l'export binaire .mts v4 et le monde Luanti jouable."""
    grid = SparseChunkVoxelGrid(600, 600, 256)
    assert len(grid.chunks) == 0  # Allocation paresseuse : 0 chunk en RAM à vide

    grid.push_undo()
    grid.fill_box((10, 0, 10), (14, 2, 14), "default:stone")
    assert grid.count_non_empty_voxels() == 5 * 3 * 5
    assert len(grid.chunks) == 1

    # Test remplacement et Undo/Redo
    replaced = grid.replace_nodes("default:stone", "default:brick")
    assert replaced == 75
    assert grid.get_voxel_name(12, 1, 12) == "default:brick"

    assert grid.undo() is True
    assert grid.count_non_empty_voxels() == 0
    assert grid.redo() is True
    assert grid.count_non_empty_voxels() == 75

    # Export binaire .mts v4
    mts_file = LuantiSchematicExporter.export_mts(grid, tmp_path / "tower.mts")
    assert mts_file.exists()
    raw_bytes = mts_file.read_bytes()
    assert raw_bytes.startswith(b"MTSM")

    # Export d'un monde Luanti jouable avec world.mt et worldmods/lcs_world_loader
    world_dir = LuantiSchematicExporter.export_playable_luanti_world(
        grid=grid,
        world_dir=tmp_path / "playable_world",
        world_name="TestWorld",
        base_game_id="minetest_game",
        spawn_pos=(0, 8, 0),
    )
    assert (world_dir / "world.mt").exists()
    assert (world_dir / "map_meta.txt").exists()
    assert (world_dir / "worldmods" / "lcs_world_loader" / "init.lua").exists()
    assert (world_dir / "worldmods" / "lcs_world_loader" / "schematics" / "world_structure.mts").exists()


def test_phase7_mod_indexer_and_phase8_plugins(tmp_path: Path) -> None:
    """Vérifie l'indexation automatique d'un mod externe et l'isolation du gestionnaire de plugins."""
    ext_mod = tmp_path / "custom_magic"
    ext_mod.mkdir(parents=True)
    (ext_mod / "mod.conf").write_text("name = custom_magic\ndepends = default\n", encoding="utf-8")
    (ext_mod / "init.lua").write_text(
        'core.register_node("custom_magic:rune_block", {description = "Rune"})\n'
        'core.register_craftitem("custom_magic:wand", {description = "Wand"})\n'
        'core.register_chatcommand("cast", {func = function() end})\n',
        encoding="utf-8",
    )

    manifest = LuantiResourceIndexer.index_mod_directory(ext_mod)
    assert manifest.mod_id == "custom_magic"
    assert "default" in manifest.dependencies
    ids = {r.full_id for r in manifest.resources}
    assert "custom_magic:rune_block" in ids
    assert "custom_magic:wand" in ids
    assert "cast" in ids

    # Test du gestionnaire de plugins Python isolés
    pm = PluginManager(tmp_path / "plugins")
    loaded = pm.discover_and_load_plugins()
    assert len(loaded) >= 1
    assert "craft_recipe_helper" in pm.registered_tools