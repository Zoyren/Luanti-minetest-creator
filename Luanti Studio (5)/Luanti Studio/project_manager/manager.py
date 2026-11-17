import hashlib
import json
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from project_manager.models import (
    CompatibilityProfile,
    ElementMetadata,
    ProjectConfig,
    VALID_ELEMENT_CATEGORIES,
)
from shared.logger import get_logger
from storage.database import StudioDatabase


class ProjectManager:
    """Orchestre la création, la sauvegarde, la protection du code manuel et l'exportation des projets."""

    PROJECT_FILENAME = "project.lcs.json"

    REQUIRED_DIRECTORIES = [
        "textures",
        "models",
        "sounds",
        "scripts",
        "entities",
        "nodes",
        "items",
        "commands",
        "gui",
        "generated",
        "custom",
        "schematics",
        ".lcs/elements",
    ]

    def __init__(self, database: StudioDatabase) -> None:
        self.db = database
        self.logger = get_logger()
        self.current_project: Optional[ProjectConfig] = None
        self.current_project_dir: Optional[Path] = None

    @staticmethod
    def sanitize_identifier(raw: str) -> str:
        """Normalise un identifiant Luanti (minuscules, chiffres et underscores uniquement)."""
        cleaned = re.sub(r"[^a-z0-9_]", "_", raw.strip().lower())
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        if not cleaned or cleaned[0].isdigit():
            cleaned = f"mod_{cleaned}" if cleaned else "my_mod"
        return cleaned

    @staticmethod
    def compute_sha256(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def create_project(
        self,
        parent_dir: Path,
        mod_id: str,
        name: str,
        description: str,
        author: str = "Creator",
        base_game: str = "minetest_game",
        luanti_version: str = "5.18.0",
        mob_api: str = "native_entities",
        dependencies: Optional[List[str]] = None,
    ) -> Tuple[ProjectConfig, Path]:
        """Crée un nouveau projet Luanti sur disque avec toute son arborescence standard."""
        safe_mod_id = self.sanitize_identifier(mod_id)
        project_dir = parent_dir / safe_mod_id

        if project_dir.exists() and any(project_dir.iterdir()):
            raise FileExistsError(f"Le dossier du projet existe déjà et n'est pas vide : {project_dir}")

        for subdir in self.REQUIRED_DIRECTORIES:
            (project_dir / subdir).mkdir(parents=True, exist_ok=True)

        deps = dependencies if dependencies is not None else (["default"] if base_game == "minetest_game" else [])
        profile = CompatibilityProfile(
            luanti_version=luanti_version,
            base_game=base_game,
            mob_api=mob_api,
            dependencies=deps,
        )

        config = ProjectConfig(
            mod_id=safe_mod_id,
            name=name.strip() or safe_mod_id,
            description=description.strip(),
            author=author.strip() or "Creator",
            compatibility=profile,
        )

        self.current_project = config
        self.current_project_dir = project_dir

        self._write_mod_conf(project_dir, config)
        self._write_readme(project_dir, config)
        self._write_custom_init_stub(project_dir, config)
        self.regenerate_master_init_lua()
        self.save_project()

        self.logger.info(f"Nouveau projet '{config.name}' ({config.mod_id}) créé dans {project_dir}")
        return config, project_dir

    def open_project(self, project_dir_or_file: Path) -> ProjectConfig:
        """Ouvre un projet existant depuis son dossier ou son fichier project.lcs.json."""
        project_dir = (
            project_dir_or_file.parent
            if project_dir_or_file.is_file()
            else project_dir_or_file
        )
        manifest_path = project_dir / self.PROJECT_FILENAME
        if not manifest_path.exists():
            raise FileNotFoundError(f"Fichier projet introuvable : {manifest_path}")

        raw_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        config = ProjectConfig.from_dict(raw_data)

        for subdir in self.REQUIRED_DIRECTORIES:
            (project_dir / subdir).mkdir(parents=True, exist_ok=True)

        self.current_project = config
        self.current_project_dir = project_dir
        self._detect_manual_code_modifications()

        self.db.upsert_recent_project(
            mod_id=config.mod_id,
            name=config.name,
            description=config.description,
            base_game=config.compatibility.base_game,
            target_version=config.compatibility.luanti_version,
            project_path=project_dir,
        )
        self.logger.info(f"Projet '{config.name}' ouvert depuis {project_dir}")
        return config

    def save_project(self) -> None:
        """Sauvegarde la configuration JSON du projet et met à jour mod.conf et SQLite."""
        if not self.current_project or not self.current_project_dir:
            raise RuntimeError("Aucun projet actif à sauvegarder.")

        self.current_project.updated_at = datetime.now(timezone.utc).isoformat()
        manifest_path = self.current_project_dir / self.PROJECT_FILENAME
        manifest_path.write_text(
            json.dumps(self.current_project.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Sauvegarde individuelle de chaque élément dans .lcs/elements/
        elements_dir = self.current_project_dir / ".lcs" / "elements"
        elements_dir.mkdir(parents=True, exist_ok=True)
        for uid, element in self.current_project.elements.items():
            el_file = elements_dir / f"{uid}.json"
            el_file.write_text(
                json.dumps(element.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        self._write_mod_conf(self.current_project_dir, self.current_project)
        self.regenerate_master_init_lua()

        self.db.upsert_recent_project(
            mod_id=self.current_project.mod_id,
            name=self.current_project.name,
            description=self.current_project.description,
            base_game=self.current_project.compatibility.base_game,
            target_version=self.current_project.compatibility.luanti_version,
            project_path=self.current_project_dir,
        )
        self.logger.info(f"Projet '{self.current_project.name}' sauvegardé avec succès.")

    def duplicate_project(self, source_dir: Path, new_mod_id: str, new_name: str) -> Tuple[ProjectConfig, Path]:
        """Duplique intégralement un projet sous un nouvel identifiant de mod."""
        safe_id = self.sanitize_identifier(new_mod_id)
        target_dir = source_dir.parent / safe_id
        if target_dir.exists():
            raise FileExistsError(f"Le dossier cible existe déjà : {target_dir}")

        shutil.copytree(source_dir, target_dir)
        config = self.open_project(target_dir)
        config.mod_id = safe_id
        config.name = new_name.strip() or safe_id
        self.save_project()
        self.logger.info(f"Projet dupliqué vers {target_dir}")
        return config, target_dir

    def delete_project(self, project_dir: Path) -> None:
        """Supprime un projet du disque et de la base SQLite des projets récents."""
        self.db.remove_recent_project(project_dir)
        if self.current_project_dir and self.current_project_dir.resolve() == project_dir.resolve():
            self.current_project = None
            self.current_project_dir = None
        if project_dir.exists():
            shutil.rmtree(project_dir)
        self.logger.info(f"Projet supprimé : {project_dir}")

    def add_element(
        self,
        category: str,
        identifier: str,
        display_name: str,
        initial_properties: Optional[dict] = None,
    ) -> ElementMetadata:
        """Crée un nouvel élément (Mob, Block, Item, Command, GUI, World) et génère son script Lua initial."""
        if not self.current_project or not self.current_project_dir:
            raise RuntimeError("Ouvrez ou créez un projet avant d'ajouter un élément.")

        if category not in VALID_ELEMENT_CATEGORIES:
            raise ValueError(f"Catégorie d'élément invalide : {category}")

        safe_ident = self.sanitize_identifier(identifier)
        for existing in self.current_project.elements.values():
            if existing.identifier == safe_ident and existing.category == category:
                raise ValueError(
                    f"Un élément '{safe_ident}' existe déjà dans la catégorie {category}."
                )

        uid = f"{category}_{safe_ident}_{uuid.uuid4().hex[:6]}"
        gen_rel = f"generated/{category}_{safe_ident}.lua"
        cust_rel = f"custom/{category}_{safe_ident}_custom.lua"

        element = ElementMetadata(
            uid=uid,
            identifier=safe_ident,
            display_name=display_name.strip() or safe_ident,
            category=category,
            mode="visual",
            properties=initial_properties or {},
            generated_lua_relpath=gen_rel,
            custom_lua_relpath=cust_rel,
        )

        self.current_project.elements[uid] = element
        self._generate_element_lua_file(element)
        self.save_project()
        self.logger.info(f"Élément [{category.upper()}] '{element.display_name}' ({safe_ident}) créé.")
        return element

    def remove_element(self, uid: str) -> None:
        """Supprime un élément du projet et nettoie son fichier généré."""
        if not self.current_project or not self.current_project_dir:
            return
        element = self.current_project.elements.pop(uid, None)
        if not element:
            return

        gen_file = self.current_project_dir / element.generated_lua_relpath
        if gen_file.exists():
            gen_file.unlink()

        el_json = self.current_project_dir / ".lcs" / "elements" / f"{uid}.json"
        if el_json.exists():
            el_json.unlink()

        self.save_project()
        self.logger.info(f"Élément '{element.display_name}' supprimé.")

    def _detect_manual_code_modifications(self) -> None:
        """Vérifie si un fichier dans generated/ a été modifié manuellement (Protection Mode B)."""
        if not self.current_project or not self.current_project_dir:
            return

        for element in self.current_project.elements.values():
            if not element.generated_lua_relpath:
                continue
            gen_path = self.current_project_dir / element.generated_lua_relpath
            if not gen_path.exists():
                continue
            recorded_hash = self.db.get_recorded_file_hash(
                self.current_project_dir, element.generated_lua_relpath
            )
            current_hash = self.compute_sha256(gen_path.read_text(encoding="utf-8"))
            if recorded_hash and current_hash != recorded_hash:
                element.mode = "manual_override"
                self.logger.warning(
                    f"Protection du code : '{element.generated_lua_relpath}' a été modifié "
                    f"manuellement. Passage en mode 'manual_override' (non écrasé)."
                )

    def _generate_element_lua_file(self, element: ElementMetadata, force: bool = False) -> None:
        """Génère le fichier Lua réel correspondant à l'élément sans écraser les modifications manuelles."""
        if not self.current_project or not self.current_project_dir:
            return

        if element.mode == "manual_override" and not force:
            self.logger.info(
                f"Régénération ignorée pour '{element.identifier}' (protégé contre l'écrasement manuel)."
            )
            return

        mod_id = self.current_project.mod_id
        full_id = f"{mod_id}:{element.identifier}"
        desc = element.display_name.replace('"', '\\"')

        lines = [
            "-- ==========================================================================",
            f"-- FICHIER GÉNÉRÉ AUTOMATIQUEMENT PAR LUANTI CREATOR STUDIO",
            f"-- Élément : {element.display_name} ({full_id}) | Catégorie : {element.category.upper()}",
            "-- NE PAS MODIFIER DIRECTEMENT SI VOUS SOUHAITEZ CONSERVER L'ÉDITION VISUELLE.",
            f"-- Pour ajouter du code manuel persistant, utilisez : {element.custom_lua_relpath}",
            "-- ==========================================================================",
            "",
        ]

        if element.category == "block":
            drawtype = element.properties.get("drawtype", "normal")
            lines.extend([
                f'core.register_node("{full_id}", {{',
                f'    description = "{desc}",',
                f'    drawtype = "{drawtype}",',
                f'    tiles = {{"{mod_id}_{element.identifier}.png"}},',
                '    groups = {cracky = 3, oddly_breakable_by_hand = 2},',
                "    on_construct = function(pos)",
                "        -- Logique visuelle Blockly (à la construction)",
                "    end,",
                "})",
            ])
        elif element.category == "item":
            lines.extend([
                f'core.register_craftitem("{full_id}", {{',
                f'    description = "{desc}",',
                f'    inventory_image = "{mod_id}_{element.identifier}.png",',
                "    on_use = function(itemstack, user, pointed_thing)",
                "        -- Logique visuelle Blockly (à l'utilisation)",
                "        return itemstack",
                "    end,",
                "})",
            ])
        elif element.category == "mob":
            hp_max = int(element.properties.get("hp_max", 20))
            lines.extend([
                f'core.register_entity("{full_id}", {{',
                "    initial_properties = {",
                f"        hp_max = {hp_max},",
                "        physical = true,",
                "        collide_with_objects = true,",
                "        collisionbox = {-0.35, -0.5, -0.35, 0.35, 0.5, 0.35},",
                '        visual = "mesh",',
                f'        mesh = "{mod_id}_{element.identifier}.b3d",',
                f'        textures = {{"{mod_id}_{element.identifier}.png"}},',
                "    },",
                "    on_activate = function(self, staticdata, dtime_s)",
                "        -- Initialisation de la créature",
                "    end,",
                "    on_rightclick = function(self, clicker)",
                "        -- Interaction joueur -> mob",
                "    end,",
                "})",
            ])
        elif element.category == "command":
            privs = element.properties.get("privs", "")
            priv_table = f"{{ {privs} = true }}" if privs else "{}"
            lines.extend([
                f'core.register_chatcommand("{element.identifier}", {{',
                '    params = "<args>",',
                f'    description = "{desc}",',
                f"    privs = {priv_table},",
                "    func = function(name, param)",
                f'        return true, "[{mod_id}] Commande /{element.identifier} exécutée."',
                "    end,",
                "})",
            ])
        elif element.category == "gui":
            lines.extend([
                f"-- Interface Formspec : {full_id}",
                f"local function get_{element.identifier}_formspec()",
                "    return table.concat({",
                '        "formspec_version[6]",',
                '        "size[10,7]",',
                f'        "label[0.5,0.6;{desc}]",',
                '        "button_exit[3.5,5.6;3,0.9;close;Fermer]",',
                "    })",
                "end",
            ])
        elif element.category == "world":
            lines.extend([
                f"-- Structure / Monde : {full_id}",
                f'-- Fichier schematic associé : schematics/{element.identifier}.mts',
            ])

        content = "\n".join(lines) + "\n"
        gen_path = self.current_project_dir / element.generated_lua_relpath
        gen_path.parent.mkdir(parents=True, exist_ok=True)
        gen_path.write_text(content, encoding="utf-8")

        self.db.record_generated_file_hash(
            self.current_project_dir,
            element.generated_lua_relpath,
            self.compute_sha256(content),
        )

    def _write_mod_conf(self, project_dir: Path, config: ProjectConfig) -> None:
        deps = ", ".join(config.compatibility.dependencies)
        opt_deps = ", ".join(config.compatibility.optional_dependencies)
        lines = [
            f"name = {config.mod_id}",
            f"title = {config.name}",
            f"description = {config.description}",
            f"author = {config.author}",
        ]
        if deps:
            lines.append(f"depends = {deps}")
        if opt_deps:
            lines.append(f"optional_depends = {opt_deps}")
        (project_dir / "mod.conf").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_readme(self, project_dir: Path, config: ProjectConfig) -> None:
        readme_path = project_dir / "README.md"
        if not readme_path.exists():
            content = (
                f"# {config.name} (`{config.mod_id}`)\n\n"
                f"{config.description}\n\n"
                f"- **Auteur** : {config.author}\n"
                f"- **Jeu de base cible** : `{config.compatibility.base_game}`\n"
                f"- **Version Luanti cible** : `{config.compatibility.luanti_version}`\n"
            )
            readme_path.write_text(content, encoding="utf-8")

    def _write_custom_init_stub(self, project_dir: Path, config: ProjectConfig) -> None:
        custom_entry = project_dir / "custom" / "custom_init.lua"
        if not custom_entry.exists():
            custom_entry.write_text(
                f"-- Scripts Lua personnalisés pour {config.name} ({config.mod_id})\n"
                "-- Ce fichier n'est JAMAIS écrasé par Luanti Creator Studio.\n",
                encoding="utf-8",
            )

    def regenerate_master_init_lua(self) -> None:
        """Génère le fichier init.lua principal qui charge generated/ puis custom/."""
        if not self.current_project or not self.current_project_dir:
            return

        mod_id = self.current_project.mod_id
        lines = [
            "-- ==========================================================================",
            f"-- {self.current_project.name} ({mod_id}) - Point d'entrée principal",
            "-- Généré par Luanti Creator Studio",
            "-- ==========================================================================",
            f'local modname = core.get_current_modname() or "{mod_id}"',
            "local modpath = core.get_modpath(modname)",
            "",
            "-- 1. Chargement des éléments visuels générés",
        ]

        for element in self.current_project.elements.values():
            if element.generated_lua_relpath and element.category != "world":
                lines.append(f'dofile(modpath .. "/{element.generated_lua_relpath}")')

        lines.extend([
            "",
            "-- 2. Chargement des scripts personnalisés (Mode Code Pur - Jamais écrasés)",
            'local custom_init = modpath .. "/custom/custom_init.lua"',
            "local f = io.open(custom_init, \"r\")",
            "if f then",
            "    f:close()",
            "    dofile(custom_init)",
            "end",
            "",
            f'core.log("action", "[" .. modname .. "] Mod chargé avec succès.")',
        ])

        (self.current_project_dir / "init.lua").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )

    def export_mod_zip(self, destination_zip: Path) -> Path:
        """Exporte le mod complet sous forme d'archive ZIP directement installable dans Luanti."""
        if not self.current_project or not self.current_project_dir:
            raise RuntimeError("Aucun projet actif à exporter.")

        self.save_project()
        destination_zip = destination_zip.with_suffix(".zip")

        with zipfile.ZipFile(destination_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in self.current_project_dir.rglob("*"):
                if file_path.is_file():
                    rel = file_path.relative_to(self.current_project_dir)
                    # Exclure les métadonnées internes de l'archive Luanti si souhaité, ou les garder
                    arcname = Path(self.current_project.mod_id) / rel
                    zf.write(file_path, arcname)

        self.logger.info(f"Mod exporté en archive ZIP : {destination_zip}")
        return destination_zip

    def import_project_from_zip(self, zip_path: Path, target_parent_dir: Path) -> Tuple[ProjectConfig, Path]:
        """Importe un projet ou un mod externe depuis une archive ZIP."""
        if not zip_path.exists():
            raise FileNotFoundError(f"Archive ZIP introuvable : {zip_path}")

        mod_stem = self.sanitize_identifier(zip_path.stem)
        extract_dir = target_parent_dir / mod_stem
        if extract_dir.exists():
            extract_dir = target_parent_dir / f"{mod_stem}_{uuid.uuid4().hex[:4]}"

        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        # Si le ZIP contenait un dossier racine unique, remonter son contenu
        entries = list(extract_dir.iterdir())
        if len(entries) == 1 and entries[0].is_dir():
            inner = entries[0]
            for item in inner.iterdir():
                shutil.move(str(item), str(extract_dir / item.name))
            inner.rmdir()

        # Si ce n'est pas encore un projet LCS, initialiser project.lcs.json en Mode Code Pur
        if not (extract_dir / self.PROJECT_FILENAME).exists():
            mod_name = extract_dir.name
            desc = "Mod communautaire importé"
            conf_file = extract_dir / "mod.conf"
            if conf_file.exists():
                for line in conf_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if "=" in line:
                        k, v = [p.strip() for p in line.split("=", 1)]
                        if k == "name":
                            mod_name = self.sanitize_identifier(v)
                        elif k == "description":
                            desc = v
            config = ProjectConfig(
                mod_id=mod_name,
                name=mod_name,
                description=desc,
            )
            for subdir in self.REQUIRED_DIRECTORIES:
                (extract_dir / subdir).mkdir(parents=True, exist_ok=True)
            (extract_dir / self.PROJECT_FILENAME).write_text(
                json.dumps(config.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        config = self.open_project(extract_dir)
        return config, extract_dir