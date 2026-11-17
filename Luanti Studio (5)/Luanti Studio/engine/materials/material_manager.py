from pathlib import Path
from typing import Dict, Optional, Tuple
from PIL import Image, ImageDraw


class MaterialData:
    """Représente un matériau 3D avec texture PNG et couleur diffuse RGBA."""

    def __init__(
        self,
        name: str,
        color_rgba: Tuple[int, int, int, int] = (255, 255, 255, 255),
        texture_path: Optional[Path] = None,
    ) -> None:
        self.name = name
        self.color_rgba = color_rgba
        self.texture_path = texture_path


class MaterialManager:
    """Gère les textures Pillow et les matériaux pour le viewport 3D et les exports Luanti."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.materials: Dict[str, MaterialData] = {}
        self._create_default_materials()

    def _create_default_materials(self) -> None:
        checker_path = self.cache_dir / "default_uv_checker.png"
        if not checker_path.exists():
            self.generate_uv_checker_png(checker_path, size=64)
        self.materials["default"] = MaterialData(
            name="default",
            color_rgba=(220, 225, 235, 255),
            texture_path=checker_path,
        )
        self.materials["pig_pink"] = MaterialData(
            name="pig_pink",
            color_rgba=(244, 162, 184, 255),
            texture_path=checker_path,
        )
        self.materials["wood_oak"] = MaterialData(
            name="wood_oak",
            color_rgba=(168, 118, 62, 255),
            texture_path=checker_path,
        )
        self.materials["ender_cyan"] = MaterialData(
            name="ender_cyan",
            color_rgba=(16, 185, 165, 255),
            texture_path=checker_path,
        )

    @staticmethod
    def generate_uv_checker_png(
        output_path: Path,
        size: int = 64,
        color_a: Tuple[int, int, int, int] = (45, 52, 64, 255),
        color_b: Tuple[int, int, int, int] = (0, 184, 212, 255),
    ) -> Path:
        """Génère une texture PNG de damier UV avec Pillow pour prévisualiser l'alignement."""
        img = Image.new("RGBA", (size, size), color_a)
        draw = ImageDraw.Draw(img)
        step = max(4, size // 8)
        for y in range(0, size, step):
            for x in range(0, size, step):
                if ((x // step) + (y // step)) % 2 == 1:
                    draw.rectangle([x, y, x + step - 1, y + step - 1], fill=color_b)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path, format="PNG")
        return output_path

    def register_texture(
        self,
        name: str,
        texture_file: Path,
        color_rgba: Tuple[int, int, int, int] = (255, 255, 255, 255),
    ) -> MaterialData:
        if not texture_file.exists():
            raise FileNotFoundError(f"Texture PNG introuvable : {texture_file}")
        mat = MaterialData(name=name, color_rgba=color_rgba, texture_path=texture_file.resolve())
        self.materials[name] = mat
        return mat

    def get_material(self, name: str) -> MaterialData:
        return self.materials.get(name, self.materials["default"])