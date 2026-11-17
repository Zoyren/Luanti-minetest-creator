import re
import shutil
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class IndexedResource:
    """Ressource réelle détectée lors de l'analyse d'un jeu de base ou d'un mod communautaire."""

    full_id: str          # ex: "default:stone", "default:cobble", "farming:wheat_1"
    resource_type: str    # "node" | "craftitem" | "tool" | "entity" | "command"
    mod_name: str
    category: str = "Construction"
    description: str = ""
    texture_name: str = ""
    color_rgb: Tuple[int, int, int] = (148, 163, 184)
    source_file: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ImportedModManifest:
    """Métadonnées d'un mod communautaire analysé en Mode Code Pur (Mode B)."""

    mod_id: str
    title: str
    description: str
    path: str
    enabled: bool = True
    mode: str = "pure_code"
    dependencies: List[str] = field(default_factory=list)
    optional_dependencies: List[str] = field(default_factory=list)
    resources: List[IndexedResource] = field(default_factory=list)
    textures: List[str] = field(default_factory=list)
    models: List[str] = field(default_factory=list)
    sounds: List[str] = field(default_factory=list)
    lua_files: List[str] = field(default_factory=list)


class LuantiResourceIndexer:
    """
    Analyseur statique de fichiers Lua et mod.conf pour Luanti / Minetest.
    Détecte les vrais identifiants enregistrés sans jamais inventer de blocs fictifs.
    """

    REGISTER_PATTERNS = [
        ("node", re.compile(r'(?:minetest|core)\.register_node\s*\(\s*["\']([^"\']+)["\']')),
        ("craftitem", re.compile(r'(?:minetest|core)\.register_craftitem\s*\(\s*["\']([^"\']+)["\']')),
        ("tool", re.compile(r'(?:minetest|core)\.register_tool\s*\(\s*["\']([^"\']+)["\']')),
        ("entity", re.compile(r'(?:minetest|core)\.register_entity\s*\(\s*["\']([^"\']+)["\']')),
        ("command", re.compile(r'(?:minetest|core)\.register_chatcommand\s*\(\s*["\']([^"\']+)["\']')),
    ]

    # Catalogue de référence des vrais blocs standards de Minetest Game / Mineclonia
    KNOWN_REAL_GAME_NODES: Dict[str, List[Tuple[str, str, Tuple[int, int, int]]]] = {
        "minetest_game": [
            ("default:stone", "Pierre", (125, 128, 132)),
            ("default:cobble", "Pierre taillée", (105, 108, 112)),
            ("default:dirt", "Nature", (134, 96, 67)),
            ("default:dirt_with_grass", "Nature", (92, 158, 68)),
            ("default:sand", "Nature", (218, 210, 158)),
            ("default:wood", "Bois", (168, 124, 74)),
            ("default:tree", "Bois", (112, 82, 50)),
            ("default:leaves", "Végétation", (58, 125, 52)),
            ("default:glass", "Construction", (200, 232, 245)),
            ("default:brick", "Construction", (165, 78, 68)),
            ("default:mese", "Éclairage", (235, 222, 52)),
            ("default:torch", "Éclairage", (245, 185, 66)),
            ("default:water_source", "Liquides", (42, 105, 210)),
            ("default:lava_source", "Liquides", (235, 95, 32)),
            ("default:chest", "Décoration", (158, 112, 58)),
            ("default:furnace", "Machines", (115, 115, 120)),
        ],
        "mineclonia": [
            ("mcl_core:stone", "Pierre", (125, 128, 132)),
            ("mcl_core:cobble", "Pierre", (105, 108, 112)),
            ("mcl_core:dirt", "Nature", (134, 96, 67)),
            ("mcl_core:dirt_with_grass", "Nature", (92, 158, 68)),
            ("mcl_core:wood", "Bois", (168, 124, 74)),
            ("mcl_core:glass", "Construction", (200, 232, 245)),
            ("mcl_torches:torch", "Éclairage", (245, 185, 66)),
            ("mcl_core:water_source", "Liquides", (42, 105, 210)),
        ],
    }

    @classmethod
    def classify_node_category(cls, full_id: str) -> Tuple[str, Tuple[int, int, int]]:
        lower = full_id.lower()
        if any(k in lower for k in ("stone", "cobble", "granite", "marble")):
            return "Pierre", (128, 132, 140)
        if any(k in lower for k in ("wood", "tree", "plank", "pine", "acacia", "aspen")):
            return "Bois", (164, 118, 68)
        if any(k in lower for k in ("dirt", "sand", "gravel", "clay", "snow", "ice")):
            return "Nature", (142, 108, 78)
        if any(k in lower for k in ("leaf", "leaves", "grass", "flower", "plant", "sapling")):
            return "Végétation", (72, 156, 72)
        if any(k in lower for k in ("water", "lava", "liquid", "river")):
            return "Liquides", (56, 128, 220)
        if any(k in lower for k in ("torch", "lamp", "light", "mese", "glow")):
            return "Éclairage", (245, 200, 66)
        if any(k in lower for k in ("furnace", "machine", "composter", "pipe", "gear")):
            return "Machines", (140, 150, 165)
        if any(k in lower for k in ("glass", "brick", "block", "stair", "wall")):
            return "Construction", (180, 195, 210)
        return "Décoration", (195, 145, 110)

    @classmethod
    def index_mod_directory(cls, mod_dir: Path) -> ImportedModManifest:
        """Analyse un dossier de mod Luanti et indexe ses fichiers, ses dépendances et ses IDs."""
        mod_id = mod_dir.name
        title = mod_id
        description = ""
        deps: List[str] = []
        opt_deps: List[str] = []

        conf_path = mod_dir / "mod.conf"
        if conf_path.exists():
            for line in conf_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if "=" in line:
                    k, v = [p.strip() for p in line.split("=", 1)]
                    if k == "name" and v:
                        mod_id = v
                    elif k == "title" and v:
                        title = v
                    elif k == "description":
                        description = v
                    elif k == "depends":
                        deps = [d.strip() for d in v.split(",") if d.strip()]
                    elif k == "optional_depends":
                        opt_deps = [d.strip() for d in v.split(",") if d.strip()]

        manifest = ImportedModManifest(
            mod_id=mod_id,
            title=title,
            description=description,
            path=str(mod_dir.resolve()),
            dependencies=deps,
            optional_dependencies=opt_deps,
        )

        seen_ids = set()
        for lua_file in sorted(mod_dir.rglob("*.lua")):
            rel_lua = str(lua_file.relative_to(mod_dir))
            manifest.lua_files.append(rel_lua)
            content = lua_file.read_text(encoding="utf-8", errors="ignore")

            for rtype, pattern in cls.REGISTER_PATTERNS:
                for match in pattern.finditer(content):
                    raw_id = match.group(1).lstrip(":")
                    if ":" not in raw_id and rtype != "command":
                        raw_id = f"{mod_id}:{raw_id}"
                    key = f"{rtype}:{raw_id}"
                    if key not in seen_ids:
                        seen_ids.add(key)
                        cat, rgb = cls.classify_node_category(raw_id)
                        manifest.resources.append(
                            IndexedResource(
                                full_id=raw_id,
                                resource_type=rtype,
                                mod_name=mod_id,
                                category=cat,
                                color_rgb=rgb,
                                source_file=rel_lua,
                            )
                        )

        for tex in sorted(mod_dir.rglob("*.png")):
            manifest.textures.append(tex.name)
        for mdl in sorted(mod_dir.rglob("*")):
            if mdl.suffix.lower() in (".b3d", ".obj", ".glb", ".gltf"):
                manifest.models.append(mdl.name)
        for snd in sorted(mod_dir.rglob("*.ogg")):
            manifest.sounds.append(snd.name)

        return manifest

    @classmethod
    def index_base_game_blocks(
        cls,
        game_id: str,
        game_path: Optional[Path] = None,
        extra_manifests: Optional[List[ImportedModManifest]] = None,
    ) -> List[IndexedResource]:
        """Indexe tous les blocs disponibles dans le jeu de base sélectionné + mods importés."""
        indexed: List[IndexedResource] = []
        seen = set()

        if game_path and game_path.exists():
            mods_root = game_path / "mods"
            if mods_root.exists():
                for sub in sorted(mods_root.iterdir()):
                    if sub.is_dir():
                        man = cls.index_mod_directory(sub)
                        for res in man.resources:
                            if res.resource_type == "node" and res.full_id not in seen:
                                seen.add(res.full_id)
                                indexed.append(res)

        # Ajout des vrais blocs standards connus si le jeu n'est pas installé physiquement
        fallback_list = cls.KNOWN_REAL_GAME_NODES.get(game_id, cls.KNOWN_REAL_GAME_NODES["minetest_game"])
        for full_id, cat, rgb in fallback_list:
            if full_id not in seen:
                seen.add(full_id)
                indexed.append(
                    IndexedResource(
                        full_id=full_id,
                        resource_type="node",
                        mod_name=full_id.split(":")[0],
                        category=cat,
                        color_rgb=rgb,
                    )
                )

        if extra_manifests:
            for man in extra_manifests:
                if not man.enabled:
                    continue
                for res in man.resources:
                    if res.resource_type == "node" and res.full_id not in seen:
                        seen.add(res.full_id)
                        res.category = "Blocs des mods communautaires"
                        indexed.append(res)

        return indexed

    @classmethod
    def import_external_mod(cls, source_path: Path, destination_mods_dir: Path) -> ImportedModManifest:
        """Importe un dossier ou une archive ZIP de mod communautaire en Mode Code Pur."""
        destination_mods_dir.mkdir(parents=True, exist_ok=True)
        if source_path.is_file() and source_path.suffix.lower() == ".zip":
            target_dir = destination_mods_dir / source_path.stem
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(source_path, "r") as zf:
                zf.extractall(target_dir)
            entries = list(target_dir.iterdir())
            if len(entries) == 1 and entries[0].is_dir():
                inner = entries[0]
                for item in inner.iterdir():
                    shutil.move(str(item), str(target_dir / item.name))
                inner.rmdir()
        elif source_path.is_dir():
            target_dir = destination_mods_dir / source_path.name
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(source_path, target_dir)
        else:
            raise ValueError(f"Format de mod non supporté : {source_path}")

        return cls.index_mod_directory(target_dir)