from pathlib import Path

from engine.materials.material_manager import MaterialManager
from engine.model_loader.model_data import ArticulatedModel, TrimeshModelIO
from logic.blocks.block_definitions import get_preset_workspace
from logic.generators.lua_compiler import BlocklyLuaCompiler
from validators.lua_validator import LuaValidator


def test_phase2_3d_model_hierarchy_and_exports(tmp_path: Path) -> None:
    """Vérifie la hiérarchie du modèle 3D Pig, la symétrie, l'export GLB/OBJ et la génération Nodebox Lua."""
    pig_model = ArticulatedModel.create_pig_preset()
    assert "Body" in pig_model.bones
    assert "Head" in pig_model.bones
    assert "LeftLeg" in pig_model.bones
    assert "RightLeg" in pig_model.bones
    assert len(pig_model.cubes) >= 8

    # Duplication et symétrie X
    first_uid = next(iter(pig_model.cubes.keys()))
    mirrored = pig_model.mirror_cube(first_uid, axis="x")
    assert mirrored is not None
    assert mirrored.uid in pig_model.cubes

    # Export GLB et OBJ réels via trimesh
    glb_path = TrimeshModelIO.export_model(pig_model, tmp_path / "pig.glb")
    obj_path = TrimeshModelIO.export_model(pig_model, tmp_path / "pig.obj")
    assert glb_path.exists() and glb_path.stat().st_size > 0
    assert obj_path.exists() and obj_path.stat().st_size > 0

    # Ré-importation du modèle GLB
    reimported = TrimeshModelIO.import_model(glb_path)
    assert len(reimported.cubes) > 0

    # Génération Nodebox Lua pour le Composteur
    composter = ArticulatedModel.create_composter_nodebox_preset()
    nodebox_lua = composter.to_luanti_nodebox_lua()
    assert 'drawtype = "nodebox"' in nodebox_lua
    assert 'type = "fixed"' in nodebox_lua

    # Génération de texture UV Checker avec Pillow
    mat_mgr = MaterialManager(tmp_path / "mats")
    assert (tmp_path / "mats" / "default_uv_checker.png").exists()
    assert mat_mgr.get_material("pig_pink").color_rgba == (244, 162, 184, 255)


def test_phase3_blockly_compiler_and_validator() -> None:
    """Vérifie la compilation Blockly -> Lua pour Pig, Composteur, Enderpearl et /thunder sans erreur syntaxique."""
    compiler = BlocklyLuaCompiler()

    for preset, category, ident, name in [
        ("pig", "mob", "pig", "Cochon Montable"),
        ("composter", "block", "composter", "Composteur"),
        ("enderpearl", "item", "enderpearl", "Enderpearl"),
        ("thunder", "command", "thunder", "Orage"),
    ]:
        ws = get_preset_workspace(preset)
        lua_code = compiler.compile_workspace("test_mod", category, ident, name, ws)
        issues = LuaValidator.validate_lua_code(lua_code)
        assert len(issues) == 0, f"Erreurs Lua dans {preset}: {issues}"

    # Vérification de la détection d'une clé API privée exposée
    bad_lua = 'local api_key = "secret_key_123456"\nif true then\n'
    issues = LuaValidator.validate_lua_code(bad_lua)
    assert any("Sécurité" in i.message for i in issues)
    assert any("déséquilibrés" in i.message for i in issues)