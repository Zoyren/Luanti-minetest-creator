from pathlib import Path
from project_manager.manager import ProjectManager
from storage.database import StudioDatabase


def test_project_creation_and_manual_code_protection(tmp_path: Path) -> None:
    """Vérifie la création d'un projet Luanti, la génération Lua et la protection contre l'écrasement manuel."""
    db = StudioDatabase(tmp_path / "test.sqlite")
    pm = ProjectManager(db)

    config, proj_dir = pm.create_project(
        parent_dir=tmp_path,
        mod_id="My Test Mod!",
        name="My Test Mod",
        description="Mod de test Phase 1",
        author="Peter",
        base_game="minetest_game",
        luanti_version="5.18.0",
    )

    assert config.mod_id == "my_test_mod"
    assert (proj_dir / "mod.conf").exists()
    assert (proj_dir / "init.lua").exists()
    assert (proj_dir / "project.lcs.json").exists()

    # Ajout d'un mob (Pig), d'un bloc (Composteur) et d'une commande (/thunder)
    pig = pm.add_element("mob", "pig", "Cochon Montable")
    composter = pm.add_element("block", "composter", "Composteur")
    thunder = pm.add_element("command", "thunder", "Orage")

    pig_lua = proj_dir / pig.generated_lua_relpath
    assert pig_lua.exists()
    assert 'core.register_entity("my_test_mod:pig"' in pig_lua.read_text(encoding="utf-8")

    # Simulation d'une modification manuelle par un développeur dans le fichier généré
    manual_code = pig_lua.read_text(encoding="utf-8") + "\n-- Modification manuelle développeur\n"
    pig_lua.write_text(manual_code, encoding="utf-8")

    # Réouverture du projet -> Doit détecter la modification manuelle et passer en 'manual_override'
    reopened = pm.open_project(proj_dir)
    reopened_pig = reopened.elements[pig.uid]
    assert reopened_pig.mode == "manual_override"

    # Tentative de régénération non forcée -> Ne doit JAMAIS écraser le code manuel
    pm._generate_element_lua_file(reopened_pig, force=False)
    assert "-- Modification manuelle développeur" in pig_lua.read_text(encoding="utf-8")

    # Test exportation ZIP
    zip_out = pm.export_mod_zip(tmp_path / "export_test.zip")
    assert zip_out.exists()