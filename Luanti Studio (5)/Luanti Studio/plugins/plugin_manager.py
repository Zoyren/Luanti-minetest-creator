import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List

from shared.logger import get_logger


ALLOWED_PERMISSIONS = {"register_blockly", "register_exporter", "register_tool", "register_editor"}


@dataclass
class PluginManifest:
    """Manifeste officiel d'une extension Luanti Creator Studio (Section 16)."""

    plugin_id: str
    name: str
    version: str = "1.0.0"
    author: str = "Community"
    description: str = ""
    entry_point: str = "plugin_main.py"
    dependencies: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=lambda: ["register_blockly"])
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginManifest":
        return cls(
            plugin_id=str(data["plugin_id"]),
            name=str(data["name"]),
            version=str(data.get("version", "1.0.0")),
            author=str(data.get("author", "Community")),
            description=str(data.get("description", "")),
            entry_point=str(data.get("entry_point", "plugin_main.py")),
            dependencies=list(data.get("dependencies", [])),
            permissions=list(data.get("permissions", [])),
            enabled=bool(data.get("enabled", True)),
        )


class SandboxedPluginAPI:
    """API restreinte exposée aux plugins selon leurs permissions déclarées dans le manifeste."""

    def __init__(self, manifest: PluginManifest, manager: "PluginManager") -> None:
        self.manifest = manifest
        self._manager = manager

    def register_custom_tool(self, tool_id: str, label: str, callback: Callable) -> None:
        if "register_tool" not in self.manifest.permissions:
            raise PermissionError(f"Le plugin '{self.manifest.plugin_id}' n'a pas la permission 'register_tool'.")
        self._manager.registered_tools[tool_id] = (label, callback)

    def register_custom_exporter(self, format_ext: str, callback: Callable) -> None:
        if "register_exporter" not in self.manifest.permissions:
            raise PermissionError(f"Le plugin '{self.manifest.plugin_id}' n'a pas la permission 'register_exporter'.")
        self._manager.registered_exporters[format_ext] = callback


class PluginManager:
    """Gestionnaire d'extensions Python isolant l'exécution et validant les permissions."""

    SAFE_BUILTINS = {
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "range": range,
        "round": round,
        "set": set,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }

    def __init__(self, plugins_dir: Path) -> None:
        self.plugins_dir = plugins_dir
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger()
        self.plugins: Dict[str, PluginManifest] = {}
        self.registered_tools: Dict[str, Tuple[str, Callable]] = {}
        self.registered_exporters: Dict[str, Callable] = {}
        self._ensure_sample_plugin()

    def _ensure_sample_plugin(self) -> None:
        sample_dir = self.plugins_dir / "sample_loot_generator"
        if not sample_dir.exists():
            sample_dir.mkdir(parents=True, exist_ok=True)
            manifest = PluginManifest(
                plugin_id="sample_loot_generator",
                name="Générateur de Loot Tables & Recettes",
                version="1.0.0",
                author="LCS Core Team",
                description="Plugin exemple ajoutant un outil de génération de recettes de craft Luanti.",
                permissions=["register_tool", "register_exporter"],
            )
            (sample_dir / "plugin.json").write_text(
                json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            (sample_dir / "plugin_main.py").write_text(
                "def setup(api):\n"
                "    api.register_custom_tool('craft_recipe_helper', 'Générer Recette Craft', lambda: 'core.register_craft(...)')\n",
                encoding="utf-8",
            )

    def discover_and_load_plugins(self) -> List[PluginManifest]:
        self.plugins.clear()
        for sub in sorted(self.plugins_dir.iterdir()):
            manifest_file = sub / "plugin.json"
            if not sub.is_dir() or not manifest_file.exists():
                continue
            try:
                manifest = PluginManifest.from_dict(
                    json.loads(manifest_file.read_text(encoding="utf-8"))
                )
                # Filtrer les permissions non reconnues
                manifest.permissions = [p for p in manifest.permissions if p in ALLOWED_PERMISSIONS]
                self.plugins[manifest.plugin_id] = manifest
                if manifest.enabled:
                    self._execute_plugin_sandboxed(sub, manifest)
            except Exception as exc:
                self.logger.error(f"Erreur de chargement du plugin dans {sub}: {exc}")
        return list(self.plugins.values())

    def _execute_plugin_sandboxed(self, plugin_dir: Path, manifest: PluginManifest) -> None:
        entry = plugin_dir / manifest.entry_point
        if not entry.exists():
            return
        code = entry.read_text(encoding="utf-8")
        sandbox_globals: Dict[str, Any] = {"__builtins__": dict(self.SAFE_BUILTINS)}
        sandbox_locals: Dict[str, Any] = {}
        exec(compile(code, str(entry), "exec"), sandbox_globals, sandbox_locals)
        setup_fn = sandbox_locals.get("setup")
        if callable(setup_fn):
            api = SandboxedPluginAPI(manifest, self)
            setup_fn(api)
            self.logger.info(f"Plugin '{manifest.name}' ({manifest.version}) chargé avec succès.")