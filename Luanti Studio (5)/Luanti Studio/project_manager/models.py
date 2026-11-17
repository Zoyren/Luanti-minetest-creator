from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List


VALID_ELEMENT_CATEGORIES = ("mob", "block", "item", "command", "gui", "world")


@dataclass
class ElementMetadata:
    """Représente un élément créatif du projet (Mob, Bloc, Item, Commande, GUI ou Structure)."""

    uid: str
    identifier: str          # ex: "pig", "composter", "enderpearl", "thunder"
    display_name: str        # ex: "Cochon Montable", "Composteur"
    category: str            # mob | block | item | command | gui | world
    mode: str = "visual"     # "visual" (Mode A) ou "pure_code" / "manual_override" (Mode B)
    textures: Dict[str, str] = field(default_factory=dict)
    model_path: str = ""
    animations: List[Dict[str, Any]] = field(default_factory=list)
    blockly_workspace_json: Dict[str, Any] = field(default_factory=dict)
    properties: Dict[str, Any] = field(default_factory=dict)
    generated_lua_relpath: str = ""
    custom_lua_relpath: str = ""
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ElementMetadata":
        return cls(**data)


@dataclass
class CompatibilityProfile:
    """Profil de compatibilité contrôlant la génération de code Lua."""

    luanti_version: str = "5.18.0"
    base_game: str = "minetest_game"
    mob_api: str = "native_entities"  # native_entities | mobs_redo | creatura
    dependencies: List[str] = field(default_factory=lambda: ["default"])
    optional_dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompatibilityProfile":
        return cls(**data)


@dataclass
class ProjectConfig:
    """Configuration complète d'un projet Luanti Creator Studio."""

    mod_id: str
    name: str
    description: str
    author: str = "Creator"
    version: str = "0.1.0"
    compatibility: CompatibilityProfile = field(default_factory=CompatibilityProfile)
    elements: Dict[str, ElementMetadata] = field(default_factory=dict)
    imported_mods: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mod_id": self.mod_id,
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "compatibility": self.compatibility.to_dict(),
            "elements": {uid: el.to_dict() for uid, el in self.elements.items()},
            "imported_mods": self.imported_mods,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectConfig":
        comp = CompatibilityProfile.from_dict(data.get("compatibility", {}))
        raw_elements = data.get("elements", {})
        elements = {
            uid: ElementMetadata.from_dict(el_data)
            for uid, el_data in raw_elements.items()
        }
        return cls(
            mod_id=data["mod_id"],
            name=data["name"],
            description=data.get("description", ""),
            author=data.get("author", "Creator"),
            version=data.get("version", "0.1.0"),
            compatibility=comp,
            elements=elements,
            imported_mods=data.get("imported_mods", []),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )