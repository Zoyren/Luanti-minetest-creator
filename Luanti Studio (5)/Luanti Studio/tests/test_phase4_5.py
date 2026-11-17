from pathlib import Path

from engine.animation.timeline_data import AnimationSet
from modules.command.command_editor_widget import CommandArgSpec, CommandDefinition
from modules.command.formspec_editor_widget import FormspecDocument
from validators.lua_validator import LuaValidator


def test_phase4_animation_interpolation_and_tile_animation() -> None:
    """Vérifie l'interpolation des images clés d'animation du Pig et la génération Tile Animation Luanti."""
    anim_set = AnimationSet.create_pig_animations_preset()
    assert "idle" in anim_set.clips
    assert "walk" in anim_set.clips
    assert "run" in anim_set.clips

    walk_clip = anim_set.clips["walk"]
    # À la frame 41 -> +25°, à la frame 60 -> -25° ; au milieu (~50.5) -> proche de 0°
    mid_rot = walk_clip.evaluate_bone_rotation("LeftLeg", 50.5)
    assert -1.0 <= mid_rot[0] <= 1.0

    # Duplication d'image clé
    dup = walk_clip.duplicate_keyframe(41, 70, "LeftLeg")
    assert dup is not None and dup.frame == 70

    # Génération Lua d'une tile animée pour un Bloc
    anim_set.tile_animation_enabled = True
    tile_lua = anim_set.to_luanti_tile_animation_lua("my_mod_composter.png")
    assert 'type = "vertical_frames"' in tile_lua


def test_phase5_command_and_formspec_bdd_generation() -> None:
    """Vérifie la génération Lua de /create BDD, des arguments typés et du Formspec Builder."""
    bdd_doc = FormspecDocument.create_bdd_dialogue_preset()
    fs_lua = bdd_doc.to_luanti_formspec_lua("axion_mod")

    assert 'formspec_version[6]' in fs_lua
    assert 'core.show_formspec(player_name, "axion_mod:dialogue_bdd", fs)' in fs_lua
    assert 'core.register_on_player_receive_fields' in fs_lua

    # Validation syntaxique du code Formspec généré
    issues = LuaValidator.validate_lua_code(fs_lua)
    assert len(issues) == 0, f"Erreurs dans le code Formspec généré : {issues}"

    # Test du générateur de commande avec arguments typés et privilèges
    cmd = CommandDefinition(
        name="create",
        description="Ouvre la boîte de dialogue BDD",
        privileges=["interact"],
        arguments=[CommandArgSpec("dialog_id", "string", True)],
        opens_formspec_name="dialogue_bdd",
    )
    cmd_lua = cmd.to_luanti_lua("axion_mod")
    assert 'core.register_chatcommand("create"' in cmd_lua
    assert "<dialog_id:string>" in cmd_lua
    assert len(LuaValidator.validate_lua_code(cmd_lua)) == 0