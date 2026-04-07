from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from PIL import Image

from .malayer import AdjustmentMalayer, EditorTab, Malayer, filter_malayers_by_tab


@dataclass
class TLImage:
    image_path: str
    malayers: List[Malayer] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = None
    rating: int = 0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.name is None:
            self.name = Path(self.image_path).stem

    @classmethod
    def open(cls, image_path: str) -> "TLImage":
        return cls(
            image_path=image_path,
            malayers=[AdjustmentMalayer(name="基础调整", tab_id="adjust")],
        )

    def load_image(self) -> Image.Image:
        return Image.open(self.image_path).convert("RGBA")

    def add_malayer(self, malayer: Malayer, index: Optional[int] = None) -> None:
        if index is None:
            self.malayers.append(malayer)
            return
        self.malayers.insert(index, malayer)

    def remove_malayer(self, layer_id: str) -> Malayer:
        for index, malayer in enumerate(self.malayers):
            if malayer.id == layer_id:
                return self.malayers.pop(index)
        raise KeyError(f"Malayer not found: {layer_id}")

    def move_malayer(self, layer_id: str, target_index: int) -> None:
        layer = self.remove_malayer(layer_id)
        safe_index = max(0, min(target_index, len(self.malayers)))
        self.malayers.insert(safe_index, layer)

    def get_malayer(self, layer_id: str) -> Optional[Malayer]:
        return next((malayer for malayer in self.malayers if malayer.id == layer_id), None)

    def get_malayers_for_tab(self, tab: str | EditorTab) -> List[Malayer]:
        return filter_malayers_by_tab(self.malayers, tab)

    def get_primary_malayer_for_tab(self, tab: str | EditorTab) -> Optional[Malayer]:
        layers = self.get_malayers_for_tab(tab)
        return layers[0] if layers else None

    def render(self) -> Image.Image:
        original = self.load_image()
        composed = original.copy()
        for malayer in self.malayers:
            composed = malayer.render(composed, original_image=original)
        return composed

    def render_to_path(self, output_path: str, *, format: Optional[str] = None) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        image = self.render()
        save_image = image.convert("RGB") if output.suffix.lower() in {".jpg", ".jpeg"} else image
        save_image.save(output, format=format)
        return str(output)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "image_path": self.image_path,
            "rating": self.rating,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
            "malayers": [layer.to_dict() for layer in self.malayers],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TLImage":
        return cls(
            image_path=data["image_path"],
            malayers=[Malayer.from_dict(item) for item in data.get("malayers", [])],
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name"),
            rating=data.get("rating", 0),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )
