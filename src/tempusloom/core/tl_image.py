from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import uuid

from PIL import Image
from PIL.ExifTags import TAGS
import numpy as np

from .malayer import AdjustmentMalayer, BlendMode, EditorTab, Malayer, Mask, filter_malayers_by_tab


@dataclass
class HistoryEntry:
    description: str
    snapshot: Dict[str, Any]


@dataclass
class TLImage:
    image_path: str
    malayers: List[Malayer] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = None
    rating: int = 0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    edit_state: Dict[str, Any] = field(default_factory=dict)
    _history: List[HistoryEntry] = field(default_factory=list, init=False, repr=False)
    _history_index: int = field(default=-1, init=False, repr=False)
    _full_image_cache: Optional[Image.Image] = field(default=None, init=False, repr=False)
    _preview_image_cache: Optional[Image.Image] = field(default=None, init=False, repr=False)
    _preview_image_max_dimension: Optional[int] = field(default=None, init=False, repr=False)

    _ROOT_KEY_ALIASES = {
        "imagePath": "image_path",
        "image_path": "image_path",
        "adjust": "adjust",
        "mask": "mask",
        "layers": "layers",
    }
    _ADJUST_SECTION_ALIASES = {
        "basic": "basic",
        "whiteBalance": "white_balance",
        "white_balance": "white_balance",
        "tone": "tone",
        "levels": "levels",
        "curves": "curves",
        "hsl": "hsl",
        "colorEditor": "color_editor",
        "color_editor": "color_editor",
        "colorGrading": "color_grading",
        "color_grading": "color_grading",
        "selectiveColor": "selective_color",
        "selective_color": "selective_color",
        "detail": "detail",
        "lens": "lens",
        "geometry": "geometry",
        "perspective": "perspective",
        "calibration": "calibration",
    }
    _SECTION_FIELD_ALIASES = {
        "basic": {
            "exposure": "exposure",
            "expourse": "exposure",
            "contrast": "contrast",
            "hue": "hue",
            "saturation": "saturation",
            "vibrance": "vibrance",
        },
        "white_balance": {
            "temperature": "temperature",
            "whiteBalance": "temperature",
            "white_balance": "temperature",
            "tint": "tint",
        },
        "tone": {
            "exposure": "exposure",
            "expourse": "exposure",
            "contrast": "contrast",
            "brightness": "brightness",
            "highlights": "highlights",
            "shadows": "shadows",
            "whites": "whites",
            "blacks": "blacks",
            "clarity": "clarity",
            "dehaze": "dehaze",
        },
        "curves": {
            "rgbCurve": "rgb_curve",
            "rgb_curve": "rgb_curve",
            "luminosityCurve": "luminosity_curve",
            "luminosity_curve": "luminosity_curve",
            "redCurve": "red_curve",
            "red_curve": "red_curve",
            "greenCurve": "green_curve",
            "green_curve": "green_curve",
            "blueCurve": "blue_curve",
            "blue_curve": "blue_curve",
        },
        "hsl": {
            "hue": "hue",
            "saturation": "saturation",
            "vibrance": "vibrance",
            "red": "red",
            "orange": "orange",
            "yellow": "yellow",
            "green": "green",
            "aqua": "aqua",
            "blue": "blue",
            "purple": "purple",
            "magenta": "magenta",
        },
        "color_editor": {
            "hue": "hue",
            "saturation": "saturation",
            "lightness": "lightness",
            "colorSmoothness": "color_smoothness",
            "color_smoothness": "color_smoothness",
            "luminanceSmoothness": "luminance_smoothness",
            "luminance_smoothness": "luminance_smoothness",
            "hueShift": "hue_shift",
            "hue_shift": "hue_shift",
            "saturationShift": "saturation_shift",
            "saturation_shift": "saturation_shift",
            "luminanceShift": "luminance_shift",
            "luminance_shift": "luminance_shift",
        },
        "color_grading": {
            "shadowsHue": "shadows_hue",
            "shadows_hue": "shadows_hue",
            "shadowsSaturation": "shadows_saturation",
            "shadows_saturation": "shadows_saturation",
            "midtonesHue": "midtones_hue",
            "midtones_hue": "midtones_hue",
            "midtonesSaturation": "midtones_saturation",
            "midtones_saturation": "midtones_saturation",
            "highlightsHue": "highlights_hue",
            "highlights_hue": "highlights_hue",
            "highlightsSaturation": "highlights_saturation",
            "highlights_saturation": "highlights_saturation",
        },
        "detail": {
            "sharpenAmount": "sharpen_amount",
            "sharpen_amount": "sharpen_amount",
            "sharpenRadius": "sharpen_radius",
            "sharpen_radius": "sharpen_radius",
            "sharpenThreshold": "sharpen_threshold",
            "sharpen_threshold": "sharpen_threshold",
            "luminanceNoise": "luminance_noise",
            "luminance_noise": "luminance_noise",
            "colorNoise": "color_noise",
            "color_noise": "color_noise",
            "detail": "detail",
            "mask": "mask",
            "luminanceDetail": "luminance_detail",
            "luminance_detail": "luminance_detail",
            "color": "color",
        },
        "lens": {
            "distortion": "distortion",
            "vignette": "vignette",
            "vignetteMidpoint": "vignette_midpoint",
            "vignette_midpoint": "vignette_midpoint",
            "chromaticAberration": "chromatic_aberration",
            "chromatic_aberration": "chromatic_aberration",
        },
        "geometry": {
            "distortion": "distortion",
            "vignette": "vignette",
            "vignetteMidpoint": "vignette_midpoint",
            "vignette_midpoint": "vignette_midpoint",
            "chromaticAberration": "chromatic_aberration",
            "chromatic_aberration": "chromatic_aberration",
            "vertical": "vertical",
            "horizontal": "horizontal",
            "rotation": "rotation",
            "scale": "scale",
            "offsetX": "offset_x",
            "offset_x": "offset_x",
            "offsetY": "offset_y",
            "offset_y": "offset_y",
        },
        "perspective": {
            "vertical": "vertical",
            "horizontal": "horizontal",
            "rotation": "rotation",
            "scale": "scale",
            "offsetX": "offset_x",
            "offset_x": "offset_x",
            "offsetY": "offset_y",
            "offset_y": "offset_y",
        },
        "calibration": {
            "redPrimaryHue": "red_primary_hue",
            "red_primary_hue": "red_primary_hue",
            "redPrimarySat": "red_primary_sat",
            "red_primary_sat": "red_primary_sat",
            "greenPrimaryHue": "green_primary_hue",
            "green_primary_hue": "green_primary_hue",
            "greenPrimarySat": "green_primary_sat",
            "green_primary_sat": "green_primary_sat",
            "bluePrimaryHue": "blue_primary_hue",
            "blue_primary_hue": "blue_primary_hue",
            "bluePrimarySat": "blue_primary_sat",
            "blue_primary_sat": "blue_primary_sat",
        },
    }
    _MASK_KEY_ALIASES = {
        "imagePath": "image_path",
        "image_path": "image_path",
        "invert": "invert",
        "opacity": "opacity",
        "featherRadius": "feather_radius",
        "feather_radius": "feather_radius",
    }
    _LAYER_KEY_ALIASES = {
        "id": "id",
        "name": "name",
        "visible": "visible",
        "opacity": "opacity",
        "blendMode": "blend_mode",
        "blend_mode": "blend_mode",
        "tabId": "tab_id",
        "tab_id": "tab_id",
        "mask": "mask",
    }

    def __post_init__(self) -> None:
        if self.name is None:
            self.name = Path(self.image_path).stem
        if not self.metadata:
            self.metadata = self.read_display_metadata()
        if not self.malayers:
            self.malayers = [AdjustmentMalayer(name="基础调整", tab_id="adjust")]

        if self.edit_state:
            normalized = self._normalize_edit_state_payload(self.edit_state)
            normalized["image_path"] = self.image_path
            self.edit_state = normalized
            self._sync_malayers_from_edit_state()
        else:
            self.edit_state = {}
            self._sync_state_from_malayers()

        self.reset_history("原始状态")

    @classmethod
    def open(cls, image_path: str) -> "TLImage":
        return cls(
            image_path=image_path,
            malayers=[AdjustmentMalayer(name="基础调整", tab_id="adjust")],
        )

    @classmethod
    def open_from_json(cls, payload: Dict[str, Any] | str) -> "TLImage":
        normalized = cls._normalize_edit_state_payload(payload)
        image_path = normalized.get("image_path")
        if not image_path:
            raise ValueError("JSON payload must include imagePath/image_path")
        tl_image = cls.open(image_path)
        tl_image.apply_json_payload(normalized)
        tl_image.reset_history("JSON 导入")
        return tl_image

    def _invalidate_image_caches(self) -> None:
        self._full_image_cache = None
        self._preview_image_cache = None
        self._preview_image_max_dimension = None

    def _ensure_full_image(self) -> Image.Image:
        if self._full_image_cache is None:
            self._full_image_cache = Image.open(self.image_path).convert("RGBA")
        return self._full_image_cache

    def _ensure_preview_image(self, max_dimension: Optional[int] = None) -> Image.Image:
        source = self._ensure_full_image()
        if max_dimension is None:
            return source

        safe_dimension = max(1, int(max_dimension))
        if self._preview_image_cache is None or self._preview_image_max_dimension != safe_dimension:
            width, height = source.size
            longest_edge = max(width, height)
            if longest_edge <= safe_dimension:
                preview = source.copy()
            else:
                scale = safe_dimension / float(longest_edge)
                preview = source.resize(
                    (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
                    Image.Resampling.LANCZOS,
                )
            self._preview_image_cache = preview
            self._preview_image_max_dimension = safe_dimension
        return self._preview_image_cache

    def load_image(self, *, preview: bool = False, max_dimension: Optional[int] = None) -> Image.Image:
        source = self._ensure_preview_image(max_dimension) if preview else self._ensure_full_image()
        return source.copy()

    def image_size(self) -> tuple[int, int]:
        return self._ensure_full_image().size

    def add_malayer(self, malayer: Malayer, index: Optional[int] = None) -> None:
        if index is None:
            self.malayers.append(malayer)
        else:
            self.malayers.insert(index, malayer)
        self._sync_state_from_malayers()

    def remove_malayer(self, layer_id: str) -> Malayer:
        for index, malayer in enumerate(self.malayers):
            if malayer.id == layer_id:
                removed = self.malayers.pop(index)
                self._sync_state_from_malayers()
                return removed
        raise KeyError(f"Malayer not found: {layer_id}")

    def move_malayer(self, layer_id: str, target_index: int) -> None:
        layer = self.remove_malayer(layer_id)
        safe_index = max(0, min(target_index, len(self.malayers)))
        self.malayers.insert(safe_index, layer)
        self._sync_state_from_malayers()

    def get_malayer(self, layer_id: str) -> Optional[Malayer]:
        return next((malayer for malayer in self.malayers if malayer.id == layer_id), None)

    def get_malayers_for_tab(self, tab: str | EditorTab) -> List[Malayer]:
        return filter_malayers_by_tab(self.malayers, tab)

    def get_primary_malayer_for_tab(self, tab: str | EditorTab) -> Optional[Malayer]:
        layers = self.get_malayers_for_tab(tab)
        return layers[0] if layers else None

    def render(self) -> Image.Image:
        return self.render_image(preview=False)

    def render_image(
        self,
        *,
        preview: bool = False,
        max_dimension: Optional[int] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> Image.Image:
        self._sync_malayers_from_edit_state()
        if progress_callback is not None:
            progress_callback(5, "加载原图…")
        original = self.load_image(preview=preview, max_dimension=max_dimension)
        composed = original.copy()
        total_layers = len(self.malayers)
        for index, malayer in enumerate(self.malayers):
            if progress_callback is not None:
                progress = 10 + int((index / max(total_layers, 1)) * 70)
                progress_callback(progress, f"应用图层：{malayer.name}")
            composed = malayer.render(composed, original_image=original)
        if progress_callback is not None:
            progress_callback(85, "整理图像…")
        return composed

    def render_to_path(
        self,
        output_path: str,
        *,
        format: Optional[str] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        if progress_callback is not None:
            progress_callback(0, "准备导出…")
        image = self.render_image(preview=False, progress_callback=progress_callback)
        if progress_callback is not None:
            progress_callback(90, "转换图像格式…")
        save_image = image.convert("RGB") if output.suffix.lower() in {".jpg", ".jpeg"} else image
        if progress_callback is not None:
            progress_callback(95, "写入导出文件…")
        save_image.save(output, format=format)
        if progress_callback is not None:
            progress_callback(100, "导出完成")
        return str(output)

    def apply_json_payload(
        self,
        payload: Dict[str, Any] | str,
        *,
        record_history: bool = False,
        description: Optional[str] = None,
    ) -> None:
        normalized = self._normalize_edit_state_payload(payload)
        self.edit_state = self._deep_merge_dict(self.edit_state, normalized)
        previous_path = self.image_path
        if self.edit_state.get("image_path"):
            self.image_path = str(self.edit_state["image_path"])
            if self.name is None:
                self.name = Path(self.image_path).stem
        if self.image_path != previous_path:
            self._invalidate_image_caches()
            self.metadata = self.read_display_metadata()
        self._sync_malayers_from_edit_state()
        self._sync_state_from_malayers()
        if record_history:
            self.commit_history(description or "参数调整")

    @staticmethod
    def histogram_from_image(
        image: Image.Image,
        *,
        bins: int = 128,
        sample_max_dimension: int = 512,
    ) -> Dict[str, List[float]]:
        working = image.convert("RGB")
        safe_dimension = max(1, int(sample_max_dimension))
        width, height = working.size
        longest_edge = max(width, height)
        if longest_edge > safe_dimension:
            scale = safe_dimension / float(longest_edge)
            working = working.resize(
                (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
                Image.Resampling.BILINEAR,
            )

        arr = np.asarray(working, dtype=np.uint8)
        histograms: Dict[str, List[float]] = {}
        max_value = 0.0
        bin_edges = np.linspace(0, 256, num=bins + 1, dtype=np.float32)

        for index, channel_name in enumerate(("red", "green", "blue")):
            counts, _ = np.histogram(arr[:, :, index], bins=bin_edges)
            softened = np.sqrt(counts.astype(np.float32))
            max_value = max(max_value, float(softened.max()) if softened.size else 0.0)
            histograms[channel_name] = softened.tolist()

        normalizer = max(max_value, 1.0)
        return {
            channel_name: [min(1.0, max(0.0, value / normalizer)) for value in values]
            for channel_name, values in histograms.items()
        }

    def histogram_data(
        self,
        *,
        preview: bool = True,
        max_dimension: Optional[int] = None,
        bins: int = 128,
        sample_max_dimension: int = 512,
    ) -> Dict[str, List[float]]:
        return self.histogram_from_image(
            self.render_image(preview=preview, max_dimension=max_dimension),
            bins=bins,
            sample_max_dimension=sample_max_dimension,
        )

    def read_display_metadata(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "format": Path(self.image_path).suffix.lstrip(".").upper() or "IMG",
        }
        if not self.image_path or not Path(self.image_path).is_file():
            return result

        try:
            image = Image.open(self.image_path)
            result["format"] = str(image.format or result["format"]).upper()
            raw_exif = image.getexif()
            if not raw_exif:
                return result
            exif = {TAGS.get(key, key): value for key, value in raw_exif.items()}

            iso_value = exif.get("PhotographicSensitivity", exif.get("ISOSpeedRatings"))
            if iso_value is not None:
                result["iso"] = str(iso_value)

            aperture_value = exif.get("FNumber")
            aperture_float = self._exif_number_to_float(aperture_value)
            if aperture_float is not None:
                result["aperture"] = f"F/{aperture_float:.1f}"

            focal_length_value = exif.get("FocalLength")
            focal_length_float = self._exif_number_to_float(focal_length_value)
            if focal_length_float is not None:
                result["focal_length"] = f"{focal_length_float:.0f}mm"

            exposure_time_value = exif.get("ExposureTime")
            exposure_time_float = self._exif_number_to_float(exposure_time_value)
            if exposure_time_float is not None:
                if 0 < exposure_time_float < 1:
                    result["exposure_time"] = f"1/{max(1, round(1 / exposure_time_float))}s"
                else:
                    result["exposure_time"] = f"{exposure_time_float:.1f}s"
        except Exception:
            return result

        return result

    @staticmethod
    def _exif_number_to_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            pass

        numerator = getattr(value, "numerator", None)
        denominator = getattr(value, "denominator", None)
        if numerator is not None and denominator not in {None, 0}:
            try:
                return float(numerator) / float(denominator)
            except Exception:
                return None

        if isinstance(value, tuple) and len(value) == 2 and value[1]:
            try:
                return float(value[0]) / float(value[1])
            except Exception:
                return None
        return None

    def update_adjustment(
        self,
        section: str,
        values: Dict[str, Any],
        *,
        record_history: bool = False,
        description: Optional[str] = None,
    ) -> None:
        self.apply_json_payload({"adjust": {section: values}}, record_history=record_history, description=description)

    def preview_adjustment(self, section: str, values: Dict[str, Any]) -> None:
        normalized = self._normalize_edit_state_payload({"adjust": {section: values}})
        self.edit_state = self._deep_merge_dict(self.edit_state, normalized)

    def update_mask(
        self,
        values: Dict[str, Any],
        *,
        record_history: bool = False,
        description: Optional[str] = None,
    ) -> None:
        self.apply_json_payload({"mask": values}, record_history=record_history, description=description)

    def update_layer_state(
        self,
        index: int,
        *,
        visible: Optional[bool] = None,
        opacity: Optional[float] = None,
        record_history: bool = False,
        description: Optional[str] = None,
    ) -> None:
        if index < 0 or index >= len(self.malayers):
            return
        layer = self.malayers[index]
        if visible is not None:
            layer.visible = visible
        if opacity is not None:
            layer.opacity = opacity
        self._sync_state_from_malayers()
        if record_history:
            self.commit_history(description or f"图层 {layer.name}")

    def reset_history(self, description: str = "原始状态") -> None:
        self._history = []
        self._history_index = -1
        self.commit_history(description)

    def commit_history(self, description: str) -> bool:
        snapshot = self.to_dict()
        if self._history_index >= 0 and self._history[self._history_index].snapshot == snapshot:
            return False
        if self._history_index < len(self._history) - 1:
            self._history = self._history[: self._history_index + 1]
        self._history.append(HistoryEntry(description=description, snapshot=snapshot))
        self._history_index = len(self._history) - 1
        return True

    def can_undo(self) -> bool:
        return self._history_index > 0

    def can_redo(self) -> bool:
        return 0 <= self._history_index < len(self._history) - 1

    def undo(self) -> bool:
        if not self.can_undo():
            return False
        self._history_index -= 1
        self._restore_snapshot(self._history[self._history_index].snapshot)
        return True

    def redo(self) -> bool:
        if not self.can_redo():
            return False
        self._history_index += 1
        self._restore_snapshot(self._history[self._history_index].snapshot)
        return True

    def history_entries(self) -> List[Dict[str, Any]]:
        return [
            {
                "description": item.description,
                "active": index == self._history_index,
            }
            for index, item in enumerate(self._history)
        ]

    def to_json_dict(self) -> Dict[str, Any]:
        self._sync_state_from_malayers()
        state = deepcopy(self.edit_state)
        return self._export_edit_state(state)

    def to_dict(self) -> Dict[str, Any]:
        self._sync_state_from_malayers()
        return {
            "id": self.id,
            "name": self.name,
            "image_path": self.image_path,
            "rating": self.rating,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
            "edit_state": self.to_json_dict(),
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
            edit_state=data.get("edit_state", {}),
        )

    def _restore_snapshot(self, snapshot: Dict[str, Any]) -> None:
        restored = self.from_dict(snapshot)
        self.image_path = restored.image_path
        self.malayers = restored.malayers
        self.id = restored.id
        self.name = restored.name
        self.rating = restored.rating
        self.tags = restored.tags
        self.metadata = restored.metadata
        self.edit_state = restored.edit_state

    def _sync_state_from_malayers(self) -> None:
        primary_adjustment = self.get_primary_malayer_for_tab(EditorTab.ADJUST)
        adjust_state = deepcopy(self.edit_state.get("adjust", {})) if isinstance(self.edit_state.get("adjust"), dict) else {}
        if isinstance(primary_adjustment, AdjustmentMalayer):
            payload = primary_adjustment.to_dict().get("payload", {})
            adjust_state = self._deep_merge_dict(adjust_state, payload)

        self.edit_state = {
            **{k: deepcopy(v) for k, v in self.edit_state.items() if k not in {"image_path", "adjust", "mask", "layers"}},
            "image_path": self.image_path,
            "adjust": adjust_state,
            "mask": self._build_mask_state(primary_adjustment.mask if primary_adjustment else None),
            "layers": [self._serialize_layer_state(layer) for layer in self.malayers],
        }

    def _sync_malayers_from_edit_state(self) -> None:
        primary_adjustment = self._ensure_primary_adjustment_layer()
        adjust_state = self.edit_state.get("adjust", {})
        if isinstance(adjust_state, dict):
            for section in ("basic", "white_balance", "tone", "curves", "hsl", "color_editor", "color_grading", "detail", "geometry", "calibration"):
                values = adjust_state.get(section)
                if isinstance(values, dict):
                    primary_adjustment.update_section(section, **values)

            lens_values = adjust_state.get("lens")
            if isinstance(lens_values, dict):
                primary_adjustment.update_section(
                    "geometry",
                    distortion=lens_values.get("distortion", primary_adjustment.params.geometry.distortion),
                    vignette=lens_values.get("vignette", primary_adjustment.params.geometry.vignette),
                    vignette_midpoint=lens_values.get("vignette_midpoint", primary_adjustment.params.geometry.vignette_midpoint),
                    chromatic_aberration=lens_values.get("chromatic_aberration", primary_adjustment.params.geometry.chromatic_aberration),
                )

            perspective_values = adjust_state.get("perspective")
            if isinstance(perspective_values, dict):
                primary_adjustment.update_section("geometry", **perspective_values)

        primary_adjustment.mask = Mask.from_dict(self.edit_state.get("mask"))

        layers_state = self.edit_state.get("layers")
        if isinstance(layers_state, list):
            self._apply_layers_state(layers_state)

    def _ensure_primary_adjustment_layer(self) -> AdjustmentMalayer:
        layer = self.get_primary_malayer_for_tab(EditorTab.ADJUST)
        if isinstance(layer, AdjustmentMalayer):
            return layer
        layer = AdjustmentMalayer(name="基础调整", tab_id="adjust")
        self.malayers.insert(0, layer)
        return layer

    def _apply_layers_state(self, layers_state: List[Dict[str, Any]]) -> None:
        for index, layer_state in enumerate(layers_state):
            target = None
            layer_id = layer_state.get("id")
            if layer_id:
                target = self.get_malayer(layer_id)
            if target is None and 0 <= index < len(self.malayers):
                target = self.malayers[index]
            if target is None:
                continue
            if "visible" in layer_state:
                target.visible = bool(layer_state["visible"])
            if "opacity" in layer_state:
                target.opacity = float(layer_state["opacity"])
            if "blend_mode" in layer_state:
                try:
                    target.blend_mode = BlendMode(layer_state["blend_mode"])
                except ValueError:
                    pass
            if "mask" in layer_state and layer_state["mask"] is not None:
                target.mask = Mask.from_dict(layer_state["mask"])

    def _serialize_layer_state(self, layer: Malayer) -> Dict[str, Any]:
        return {
            "id": layer.id,
            "name": layer.name,
            "type": layer.type_name,
            "visible": layer.visible,
            "opacity": layer.opacity,
            "blend_mode": layer.blend_mode.value,
            "tab_id": layer.tab_id,
            "mask": layer.mask.to_dict() if layer.mask else None,
        }

    def _build_mask_state(self, mask: Optional[Mask]) -> Dict[str, Any]:
        return mask.to_dict() if mask else {}

    @classmethod
    def _normalize_edit_state_payload(cls, payload: Dict[str, Any] | str) -> Dict[str, Any]:
        if isinstance(payload, str):
            payload = json.loads(payload)
        normalized: Dict[str, Any] = {}
        for key, value in payload.items():
            canonical_key = cls._ROOT_KEY_ALIASES.get(key, key)
            if canonical_key == "adjust" and isinstance(value, dict):
                normalized[canonical_key] = cls._normalize_adjust_payload(value)
            elif canonical_key == "mask" and isinstance(value, dict):
                normalized[canonical_key] = cls._normalize_mask_payload(value)
            elif canonical_key == "layers" and isinstance(value, list):
                normalized[canonical_key] = [cls._normalize_layer_payload(item) for item in value if isinstance(item, dict)]
            else:
                normalized[canonical_key] = deepcopy(value)
        return normalized

    @classmethod
    def _normalize_adjust_payload(cls, adjust_payload: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for key, value in adjust_payload.items():
            canonical_key = cls._ADJUST_SECTION_ALIASES.get(key)
            if canonical_key:
                if canonical_key == "white_balance" and not isinstance(value, dict):
                    section_value = {"temperature": value}
                elif isinstance(value, dict):
                    section_value = cls._normalize_section_fields(canonical_key, value)
                else:
                    section_value = deepcopy(value)
                existing = normalized.get(canonical_key, {})
                if isinstance(existing, dict) and isinstance(section_value, dict):
                    normalized[canonical_key] = cls._deep_merge_dict(existing, section_value)
                else:
                    normalized[canonical_key] = section_value
                continue

            routed_section = cls._route_adjust_value(key, value)
            if routed_section is not None:
                section_name, section_values = routed_section
                existing = normalized.get(section_name, {})
                normalized[section_name] = cls._deep_merge_dict(existing, section_values)
                continue

            normalized[key] = deepcopy(value)
        return normalized

    @classmethod
    def _normalize_section_fields(cls, section: str, values: Dict[str, Any]) -> Dict[str, Any]:
        aliases = cls._SECTION_FIELD_ALIASES.get(section, {})
        normalized: Dict[str, Any] = {}
        for key, value in values.items():
            canonical_key = aliases.get(key, key)
            if isinstance(value, dict):
                normalized[canonical_key] = cls._normalize_nested_mapping(value)
            else:
                normalized[canonical_key] = deepcopy(value)
        return normalized

    @classmethod
    def _normalize_nested_mapping(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for key, value in values.items():
            if isinstance(value, dict):
                normalized[key] = cls._normalize_nested_mapping(value)
            else:
                normalized[key] = deepcopy(value)
        return normalized

    @classmethod
    def _route_adjust_value(cls, key: str, value: Any) -> Optional[tuple[str, Dict[str, Any]]]:
        white_balance_aliases = cls._SECTION_FIELD_ALIASES["white_balance"]
        if key in white_balance_aliases:
            return "white_balance", {white_balance_aliases[key]: deepcopy(value)}

        tone_aliases = cls._SECTION_FIELD_ALIASES["tone"]
        if key in tone_aliases:
            return "tone", {tone_aliases[key]: deepcopy(value)}

        curves_aliases = cls._SECTION_FIELD_ALIASES["curves"]
        if key in curves_aliases:
            return "curves", {curves_aliases[key]: deepcopy(value)}

        basic_aliases = cls._SECTION_FIELD_ALIASES["basic"]
        if key in basic_aliases:
            return "basic", {basic_aliases[key]: deepcopy(value)}

        geometry_aliases = cls._SECTION_FIELD_ALIASES["geometry"]
        if key in geometry_aliases:
            return "geometry", {geometry_aliases[key]: deepcopy(value)}

        calibration_aliases = cls._SECTION_FIELD_ALIASES["calibration"]
        if key in calibration_aliases:
            return "calibration", {calibration_aliases[key]: deepcopy(value)}

        detail_aliases = cls._SECTION_FIELD_ALIASES["detail"]
        if key in detail_aliases:
            return "detail", {detail_aliases[key]: deepcopy(value)}

        return None

    @classmethod
    def _normalize_mask_payload(cls, mask_payload: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for key, value in mask_payload.items():
            canonical_key = cls._MASK_KEY_ALIASES.get(key, key)
            normalized[canonical_key] = deepcopy(value)
        return normalized

    @classmethod
    def _normalize_layer_payload(cls, layer_payload: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for key, value in layer_payload.items():
            canonical_key = cls._LAYER_KEY_ALIASES.get(key, key)
            if canonical_key == "mask" and isinstance(value, dict):
                normalized[canonical_key] = cls._normalize_mask_payload(value)
            else:
                normalized[canonical_key] = deepcopy(value)
        return normalized

    @classmethod
    def _deep_merge_dict(cls, base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        merged = deepcopy(base)
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = cls._deep_merge_dict(merged[key], value)
            else:
                merged[key] = deepcopy(value)
        return merged

    @classmethod
    def _export_edit_state(cls, state: Dict[str, Any]) -> Dict[str, Any]:
        exported: Dict[str, Any] = {}
        for key, value in state.items():
            if key == "image_path":
                exported["imagePath"] = deepcopy(value)
            elif key == "adjust" and isinstance(value, dict):
                exported["adjust"] = cls._export_adjust_state(value)
            elif key == "mask" and isinstance(value, dict):
                exported["mask"] = cls._export_mask_state(value)
            elif key == "layers" and isinstance(value, list):
                exported["layers"] = [cls._export_layer_state(item) for item in value if isinstance(item, dict)]
            else:
                exported[key] = deepcopy(value)
        return exported

    @classmethod
    def _export_adjust_state(cls, adjust_state: Dict[str, Any]) -> Dict[str, Any]:
        section_names = {
            "white_balance": "whiteBalance",
            "color_editor": "colorEditor",
            "color_grading": "colorGrading",
            "selective_color": "selectiveColor",
        }
        exported: Dict[str, Any] = {}
        for key, value in adjust_state.items():
            export_key = section_names.get(key, key)
            if isinstance(value, dict):
                exported[export_key] = cls._export_section_fields(key, value)
            else:
                exported[export_key] = deepcopy(value)
        return exported

    @classmethod
    def _export_section_fields(cls, section: str, values: Dict[str, Any]) -> Dict[str, Any]:
        reverse_aliases = {
            canonical: alias
            for alias, canonical in cls._SECTION_FIELD_ALIASES.get(section, {}).items()
            if alias != canonical and "_" not in alias
        }
        exported: Dict[str, Any] = {}
        for key, value in values.items():
            export_key = reverse_aliases.get(key, key)
            if isinstance(value, dict):
                exported[export_key] = cls._export_section_fields(section, value)
            else:
                exported[export_key] = deepcopy(value)
        return exported

    @classmethod
    def _export_mask_state(cls, mask_state: Dict[str, Any]) -> Dict[str, Any]:
        key_names = {
            "image_path": "imagePath",
            "feather_radius": "featherRadius",
        }
        return {key_names.get(key, key): deepcopy(value) for key, value in mask_state.items()}

    @classmethod
    def _export_layer_state(cls, layer_state: Dict[str, Any]) -> Dict[str, Any]:
        key_names = {
            "blend_mode": "blendMode",
            "tab_id": "tabId",
        }
        exported = {key_names.get(key, key): deepcopy(value) for key, value in layer_state.items() if key != "mask"}
        if isinstance(layer_state.get("mask"), dict):
            exported["mask"] = cls._export_mask_state(layer_state["mask"])
        elif "mask" in layer_state:
            exported["mask"] = deepcopy(layer_state["mask"])
        return exported
