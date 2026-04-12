from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, ClassVar, Dict, Iterable, List, Optional, Type
import uuid

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _ensure_rgba(image: Image.Image) -> Image.Image:
    return image.convert("RGBA") if image.mode != "RGBA" else image.copy()


def _pil_to_float_array(image: Image.Image) -> np.ndarray:
    return np.asarray(_ensure_rgba(image), dtype=np.float32) / 255.0


def _float_array_to_pil(array: np.ndarray) -> Image.Image:
    clipped = np.clip(array, 0.0, 1.0)
    return Image.fromarray((clipped * 255.0).astype(np.uint8), mode="RGBA")


def _smoothstep(edge0: float, edge1: float, value: np.ndarray) -> np.ndarray:
    if edge0 == edge1:
        return np.zeros_like(value, dtype=np.float32)
    scaled = np.clip((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return scaled * scaled * (3.0 - 2.0 * scaled)


def _rgb_to_hls_array(array: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rgb = np.clip(array[:, :, :3], 0.0, 1.0)
    red = rgb[:, :, 0]
    green = rgb[:, :, 1]
    blue = rgb[:, :, 2]

    maximum = np.max(rgb, axis=2)
    minimum = np.min(rgb, axis=2)
    delta = maximum - minimum

    lightness = (maximum + minimum) / 2.0
    saturation = np.zeros_like(lightness)
    hue = np.zeros_like(lightness)

    chroma_mask = delta > 1e-6
    if np.any(chroma_mask):
        denominator = 1.0 - np.abs(2.0 * lightness - 1.0)
        saturation[chroma_mask] = delta[chroma_mask] / np.maximum(denominator[chroma_mask], 1e-6)

        red_mask = chroma_mask & (maximum == red)
        green_mask = chroma_mask & (maximum == green)
        blue_mask = chroma_mask & (maximum == blue)

        hue[red_mask] = np.mod((green[red_mask] - blue[red_mask]) / np.maximum(delta[red_mask], 1e-6), 6.0)
        hue[green_mask] = ((blue[green_mask] - red[green_mask]) / np.maximum(delta[green_mask], 1e-6)) + 2.0
        hue[blue_mask] = ((red[blue_mask] - green[blue_mask]) / np.maximum(delta[blue_mask], 1e-6)) + 4.0
        hue = np.mod(hue / 6.0, 1.0)

    return hue.astype(np.float32), lightness.astype(np.float32), saturation.astype(np.float32)


def _hls_to_rgb_array(hue: np.ndarray, lightness: np.ndarray, saturation: np.ndarray) -> np.ndarray:
    hue = np.mod(hue, 1.0).astype(np.float32)
    lightness = np.clip(lightness, 0.0, 1.0).astype(np.float32)
    saturation = np.clip(saturation, 0.0, 1.0).astype(np.float32)

    chroma = (1.0 - np.abs(2.0 * lightness - 1.0)) * saturation
    hue_sector = hue * 6.0
    secondary = chroma * (1.0 - np.abs(np.mod(hue_sector, 2.0) - 1.0))

    red = np.zeros_like(hue, dtype=np.float32)
    green = np.zeros_like(hue, dtype=np.float32)
    blue = np.zeros_like(hue, dtype=np.float32)

    masks = [
        (hue_sector >= 0.0) & (hue_sector < 1.0),
        (hue_sector >= 1.0) & (hue_sector < 2.0),
        (hue_sector >= 2.0) & (hue_sector < 3.0),
        (hue_sector >= 3.0) & (hue_sector < 4.0),
        (hue_sector >= 4.0) & (hue_sector < 5.0),
        (hue_sector >= 5.0) & (hue_sector <= 6.0),
    ]

    red[masks[0]] = chroma[masks[0]]
    green[masks[0]] = secondary[masks[0]]

    red[masks[1]] = secondary[masks[1]]
    green[masks[1]] = chroma[masks[1]]

    green[masks[2]] = chroma[masks[2]]
    blue[masks[2]] = secondary[masks[2]]

    green[masks[3]] = secondary[masks[3]]
    blue[masks[3]] = chroma[masks[3]]

    red[masks[4]] = secondary[masks[4]]
    blue[masks[4]] = chroma[masks[4]]

    red[masks[5]] = chroma[masks[5]]
    blue[masks[5]] = secondary[masks[5]]

    match = lightness - chroma / 2.0
    rgb = np.stack((red + match, green + match, blue + match), axis=2)
    return np.clip(rgb, 0.0, 1.0).astype(np.float32)


class BlendMode(str, Enum):
    NORMAL = "normal"
    DARKEN = "darken"
    LIGHTEN = "lighten"
    MULTIPLY = "multiply"
    SCREEN = "screen"
    OVERLAY = "overlay"
    SOFT_LIGHT = "soft_light"
    ADD = "add"


class EditorTab(str, Enum):
    ADJUST = "adjust"
    LAYERS = "layers"
    MASK = "mask"
    AI = "ai"
    HISTORY = "history"
    PORTRAIT = "portrait"
    FILTER = "filter"


class AdjustmentSection(str, Enum):
    BASIC = "basic"
    WHITE_BALANCE = "white_balance"
    TONE = "tone"
    CURVES = "curves"
    HSL = "hsl"
    COLOR_EDITOR = "color_editor"
    COLOR_GRADING = "color_grading"
    DETAIL = "detail"
    LENS = "lens"
    PERSPECTIVE = "perspective"
    CALIBRATION = "calibration"


@dataclass
class WhiteBalanceParams:
    temperature: float = 6500
    tint: float = 0


@dataclass
class BasicAdjustParams:
    exposure: float = 0
    contrast: float = 0
    hue: float = 0
    saturation: float = 0
    vibrance: float = 0


@dataclass
class GeometryParams:
    distortion: float = 0
    vignette: float = 0
    vertical: float = 0
    horizontal: float = 0
    rotation: float = 0
    scale: float = 100
    offset_x: float = 0
    offset_y: float = 0


@dataclass
class ToneParams:
    exposure: float = 0
    contrast: float = 0
    brightness: float = 0
    highlights: float = 0
    shadows: float = 0
    whites: float = 0
    blacks: float = 0
    clarity: float = 0
    dehaze: float = 0


@dataclass
class CurvePoint:
    x: float
    y: float


@dataclass
class CurveParams:
    rgb_curve: List[CurvePoint] = field(default_factory=lambda: [CurvePoint(0, 0), CurvePoint(255, 255)])
    luminosity_curve: List[CurvePoint] = field(default_factory=lambda: [CurvePoint(0, 0), CurvePoint(255, 255)])
    red_curve: List[CurvePoint] = field(default_factory=lambda: [CurvePoint(0, 0), CurvePoint(255, 255)])
    green_curve: List[CurvePoint] = field(default_factory=lambda: [CurvePoint(0, 0), CurvePoint(255, 255)])
    blue_curve: List[CurvePoint] = field(default_factory=lambda: [CurvePoint(0, 0), CurvePoint(255, 255)])


@dataclass
class HSLColorParams:
    hue: float = 0
    saturation: float = 0
    luminance: float = 0


@dataclass
class HSLParams:
    hue: float = 0
    saturation: float = 0
    vibrance: float = 0
    red: HSLColorParams = field(default_factory=HSLColorParams)
    orange: HSLColorParams = field(default_factory=HSLColorParams)
    yellow: HSLColorParams = field(default_factory=HSLColorParams)
    green: HSLColorParams = field(default_factory=HSLColorParams)
    aqua: HSLColorParams = field(default_factory=HSLColorParams)
    blue: HSLColorParams = field(default_factory=HSLColorParams)
    purple: HSLColorParams = field(default_factory=HSLColorParams)
    magenta: HSLColorParams = field(default_factory=HSLColorParams)


@dataclass
class ColorGradingParams:
    shadows_hue: float = 0
    shadows_saturation: float = 0
    midtones_hue: float = 0
    midtones_saturation: float = 0
    highlights_hue: float = 0
    highlights_saturation: float = 0


@dataclass
class ColorEditorParams:
    hue: float = 0
    saturation: float = 0
    lightness: float = 0
    color_smoothness: float = 50
    luminance_smoothness: float = 50
    hue_shift: float = 0
    saturation_shift: float = 0
    luminance_shift: float = 0


@dataclass
class DetailParams:
    sharpen_amount: float = 0
    sharpen_radius: float = 1.0
    sharpen_threshold: float = 0
    luminance_noise: float = 0
    color_noise: float = 0


@dataclass
class CalibrationParams:
    red_primary_hue: float = 0
    red_primary_sat: float = 0
    green_primary_hue: float = 0
    green_primary_sat: float = 0
    blue_primary_hue: float = 0
    blue_primary_sat: float = 0


@dataclass
class AdjustmentParams:
    basic: BasicAdjustParams = field(default_factory=BasicAdjustParams)
    white_balance: WhiteBalanceParams = field(default_factory=WhiteBalanceParams)
    geometry: GeometryParams = field(default_factory=GeometryParams)
    tone: ToneParams = field(default_factory=ToneParams)
    curves: CurveParams = field(default_factory=CurveParams)
    hsl: HSLParams = field(default_factory=HSLParams)
    color_editor: ColorEditorParams = field(default_factory=ColorEditorParams)
    color_grading: ColorGradingParams = field(default_factory=ColorGradingParams)
    detail: DetailParams = field(default_factory=DetailParams)
    calibration: CalibrationParams = field(default_factory=CalibrationParams)


@dataclass
class Mask:
    image_path: Optional[str] = None
    invert: bool = False
    opacity: float = 1.0
    feather_radius: float = 0.0

    def to_pil(self, size: tuple[int, int]) -> Image.Image:
        if self.image_path:
            image = Image.open(self.image_path).convert("L")
            if image.size != size:
                image = image.resize(size, Image.Resampling.LANCZOS)
        else:
            image = Image.new("L", size, color=255)
        if self.feather_radius > 0:
            image = image.filter(ImageFilter.GaussianBlur(radius=self.feather_radius))
        if self.invert:
            image = ImageOps.invert(image)
        if self.opacity < 1.0:
            alpha = np.asarray(image, dtype=np.float32) * _clamp(self.opacity, 0.0, 1.0)
            image = Image.fromarray(alpha.astype(np.uint8), mode="L")
        return image

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["Mask"]:
        if not data:
            return None
        return cls(**data)


def composite_images(base: Image.Image, layer: Image.Image, mode: BlendMode, opacity: float, mask: Optional[Mask]) -> Image.Image:
    base_rgba = _ensure_rgba(base)
    layer_rgba = _ensure_rgba(layer).resize(base_rgba.size, Image.Resampling.LANCZOS)
    base_arr = _pil_to_float_array(base_rgba)
    layer_arr = _pil_to_float_array(layer_rgba)
    base_rgb = base_arr[..., :3]
    layer_rgb = layer_arr[..., :3]

    if mode == BlendMode.NORMAL:
        blended_rgb = layer_rgb
    elif mode == BlendMode.DARKEN:
        blended_rgb = np.minimum(base_rgb, layer_rgb)
    elif mode == BlendMode.LIGHTEN:
        blended_rgb = np.maximum(base_rgb, layer_rgb)
    elif mode == BlendMode.MULTIPLY:
        blended_rgb = base_rgb * layer_rgb
    elif mode == BlendMode.SCREEN:
        blended_rgb = 1.0 - (1.0 - base_rgb) * (1.0 - layer_rgb)
    elif mode == BlendMode.OVERLAY:
        blended_rgb = np.where(base_rgb <= 0.5, 2.0 * base_rgb * layer_rgb, 1.0 - 2.0 * (1.0 - base_rgb) * (1.0 - layer_rgb))
    elif mode == BlendMode.SOFT_LIGHT:
        blended_rgb = (1.0 - 2.0 * layer_rgb) * base_rgb * base_rgb + 2.0 * layer_rgb * base_rgb
    elif mode == BlendMode.ADD:
        blended_rgb = np.clip(base_rgb + layer_rgb, 0.0, 1.0)
    else:
        raise ValueError(f"Unsupported blend mode: {mode}")

    alpha = np.full((base_rgba.size[1], base_rgba.size[0], 1), _clamp(opacity, 0.0, 1.0), dtype=np.float32)
    if mask is not None:
        alpha *= np.asarray(mask.to_pil(base_rgba.size), dtype=np.float32)[..., None] / 255.0

    out_rgb = base_rgb * (1.0 - alpha) + blended_rgb * alpha
    out_alpha = np.maximum(base_arr[..., 3:], layer_arr[..., 3:])
    return _float_array_to_pil(np.concatenate([out_rgb, out_alpha], axis=-1))


class Malayer(ABC):
    type_name: ClassVar[str] = "base"
    default_tab: ClassVar[EditorTab] = EditorTab.LAYERS
    supported_tabs: ClassVar[tuple[EditorTab, ...]] = (EditorTab.LAYERS,)
    _registry: ClassVar[Dict[str, Type["Malayer"]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if getattr(cls, "type_name", None) and cls.type_name != "base":
            Malayer._registry[cls.type_name] = cls

    def __init__(
        self,
        name: str,
        *,
        visible: bool = True,
        locked: bool = False,
        opacity: float = 1.0,
        blend_mode: BlendMode = BlendMode.NORMAL,
        mask: Optional[Mask] = None,
        tab_id: Optional[str] = None,
        layer_id: Optional[str] = None,
    ) -> None:
        self.id = layer_id or str(uuid.uuid4())
        self.name = name
        self.visible = visible
        self.locked = locked
        self.opacity = opacity
        self.blend_mode = blend_mode
        self.mask = mask
        self.tab_id = tab_id or self.default_tab.value

    @classmethod
    def supports_tab(cls, tab: str | EditorTab) -> bool:
        tab_value = tab.value if isinstance(tab, EditorTab) else tab
        return any(item.value == tab_value for item in cls.supported_tabs)

    @classmethod
    def supported_section_names(cls) -> tuple[str, ...]:
        return ()

    def can_be_controlled_by(self, tab: str | EditorTab) -> bool:
        return self.supports_tab(tab)

    def get_control_summary(self) -> Dict[str, Any]:
        return {
            "type": self.type_name,
            "tabs": [tab.value for tab in self.supported_tabs],
            "sections": list(self.supported_section_names()),
        }

    @abstractmethod
    def apply(self, image: Image.Image, original_image: Optional[Image.Image] = None) -> Image.Image:
        raise NotImplementedError

    def render(self, image: Image.Image, original_image: Optional[Image.Image] = None) -> Image.Image:
        if not self.visible:
            return _ensure_rgba(image)
        processed = self.apply(_ensure_rgba(image), original_image=_ensure_rgba(original_image) if original_image else None)
        return composite_images(image, processed, self.blend_mode, self.opacity, self.mask)

    def _serialize_payload(self) -> Dict[str, Any]:
        return {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type_name,
            "name": self.name,
            "visible": self.visible,
            "locked": self.locked,
            "opacity": self.opacity,
            "blend_mode": self.blend_mode.value,
            "tab_id": self.tab_id,
            "supported_tabs": [tab.value for tab in self.supported_tabs],
            "mask": self.mask.to_dict() if self.mask else None,
            "payload": self._serialize_payload(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Malayer":
        layer_cls = cls._registry.get(data["type"])
        if layer_cls is None:
            raise ValueError(f"Unknown malayer type: {data['type']}")
        return layer_cls._from_dict(data)

    @classmethod
    @abstractmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "Malayer":
        raise NotImplementedError


class TabMalayer(Malayer):
    def update_params(self, mapping: Dict[str, Any]) -> None:
        for key, value in mapping.items():
            if hasattr(self, key):
                setattr(self, key, value)


class AdjustmentMalayer(TabMalayer):
    type_name = "adjustment"
    default_tab = EditorTab.ADJUST
    supported_tabs = (EditorTab.ADJUST, EditorTab.LAYERS)
    _HSL_COLOR_BANDS: ClassVar[tuple[tuple[str, float, float], ...]] = (
        ("red", 0.0, 20.0),
        ("orange", 35.0, 15.0),
        ("yellow", 65.0, 15.0),
        ("green", 120.0, 40.0),
        ("aqua", 180.0, 20.0),
        ("blue", 230.0, 30.0),
        ("purple", 280.0, 20.0),
        ("magenta", 320.0, 20.0),
    )

    def __init__(self, name: str = "Adjustment", *, params: Optional[AdjustmentParams] = None, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.params = params or AdjustmentParams()
        self._sync_basic_to_pipeline()

    @classmethod
    def supported_section_names(cls) -> tuple[str, ...]:
        return tuple(section.value for section in AdjustmentSection)

    def _sync_basic_to_pipeline(self) -> None:
        self.params.tone.exposure = self.params.basic.exposure
        self.params.tone.contrast = self.params.basic.contrast
        self.params.hsl.hue = self.params.basic.hue
        self.params.hsl.saturation = self.params.basic.saturation
        self.params.hsl.vibrance = self.params.basic.vibrance

    @staticmethod
    def _normalize_white_balance_temperature(value: Any) -> float:
        """Normalize UI white-balance temperature input to an internal Kelvin-like value.

        Current UI sends a relative slider value in ``[-100, 100]`` instead of a
        physical Kelvin temperature. The rendering pipeline, however, stores white
        balance temperature around a daylight reference of ``6500K``.

        Mapping strategy used here:

        1. Treat ``0`` as neutral daylight ``6500K``.
        2. Map one UI step to ``45K``.
        3. Therefore ``-100`` -> ``2000K`` and ``+100`` -> ``11000K``.
        4. Clamp the final result into a broader safe range ``[2000K, 50000K]`` so
           future callers may still pass absolute Kelvin values directly.

        Notes
        -----
        - This is an interaction mapping, not the white-balance algorithm itself.
        - If a caller already passes an absolute Kelvin value outside ``[-100, 100]``,
          we keep it as-is and only clamp it.
        """
        temperature = float(value)
        if -100.0 <= temperature <= 100.0:
            temperature = 6500.0 + temperature * 45.0
        return _clamp(temperature, 2000.0, 50000.0)

    @staticmethod
    def _normalize_white_balance_tint(value: Any) -> float:
        """Normalize UI tint input to the internal green/magenta correction range.

        UI exposes tint in ``[-100, 100]`` for usability, while the adjustment model
        stores tint in ``[-150, 150]``. We therefore scale the UI value by ``1.5``.

        Negative values push the image towards green; positive values push it towards
        magenta. The result is clamped to the supported internal range.
        """
        tint = float(value)
        if -100.0 <= tint <= 100.0:
            tint *= 1.5
        return _clamp(tint, -150.0, 150.0)

    def get_section_params(self, section: str | AdjustmentSection) -> Any:
        value = section.value if isinstance(section, AdjustmentSection) else section
        mapping = {
            AdjustmentSection.BASIC.value: self.params.basic,
            AdjustmentSection.WHITE_BALANCE.value: self.params.white_balance,
            "geometry": self.params.geometry,
            AdjustmentSection.TONE.value: self.params.tone,
            AdjustmentSection.CURVES.value: self.params.curves,
            AdjustmentSection.HSL.value: self.params.hsl,
            AdjustmentSection.COLOR_EDITOR.value: self.params.color_editor,
            AdjustmentSection.COLOR_GRADING.value: self.params.color_grading,
            AdjustmentSection.DETAIL.value: self.params.detail,
            AdjustmentSection.LENS.value: self.params.geometry,
            AdjustmentSection.PERSPECTIVE.value: self.params.geometry,
            AdjustmentSection.CALIBRATION.value: self.params.calibration,
        }
        if value not in mapping:
            raise KeyError(f"Unsupported adjustment section: {value}")
        return mapping[value]

    @classmethod
    def _merge_param_mapping(cls, target: Any, values: Dict[str, Any]) -> None:
        for key, value in values.items():
            if not hasattr(target, key):
                continue
            current = getattr(target, key)
            if isinstance(value, dict) and current is not None and is_dataclass(current):
                cls._merge_param_mapping(current, value)
            else:
                setattr(target, key, value)

    @staticmethod
    def _coerce_hsl_color_params(value: Any) -> HSLColorParams:
        if isinstance(value, HSLColorParams):
            return value
        if isinstance(value, dict):
            return HSLColorParams(
                hue=float(value.get("hue", 0)),
                saturation=float(value.get("saturation", 0)),
                luminance=float(value.get("luminance", 0)),
            )
        return HSLColorParams()

    def update_section(self, section: str | AdjustmentSection, **values: Any) -> None:
        section_value = section.value if isinstance(section, AdjustmentSection) else section
        normalized_values = dict(values)
        if section_value == AdjustmentSection.WHITE_BALANCE.value:
            if "temperature" in normalized_values:
                normalized_values["temperature"] = self._normalize_white_balance_temperature(
                    normalized_values["temperature"]
                )
            if "tint" in normalized_values:
                normalized_values["tint"] = self._normalize_white_balance_tint(
                    normalized_values["tint"]
                )
        elif section_value == AdjustmentSection.CURVES.value:
            normalized_values = {
                key: self._normalize_curve_points(value)
                for key, value in normalized_values.items()
            }

        target = self.get_section_params(section_value)
        self._merge_param_mapping(target, normalized_values)
        if section_value == AdjustmentSection.BASIC.value:
            self._sync_basic_to_pipeline()

    def apply(self, image: Image.Image, original_image: Optional[Image.Image] = None) -> Image.Image:
        result = _ensure_rgba(image)
        result = self._apply_white_balance(result)
        result = self._apply_tone(result)
        result = self._apply_curves(result)
        result = self._apply_hsl(result)
        result = self._apply_color_editor(result)
        result = self._apply_detail(result)
        result = self._apply_geometry(result)
        return result

    @staticmethod
    def _normalize_curve_points(points: Any) -> List[CurvePoint]:
        normalized: List[CurvePoint] = []
        if isinstance(points, list):
            for item in points:
                if isinstance(item, CurvePoint):
                    x_val = item.x
                    y_val = item.y
                elif isinstance(item, dict):
                    x_val = item.get("x")
                    y_val = item.get("y")
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    x_val, y_val = item[0], item[1]
                else:
                    continue
                try:
                    x = float(x_val)
                    y = float(y_val)
                except (TypeError, ValueError):
                    continue
                x = _clamp(x, 0.0, 255.0)
                y = _clamp(y, 0.0, 255.0)
                normalized.append(CurvePoint(x=x, y=y))

        normalized.sort(key=lambda point: point.x)
        deduped: List[CurvePoint] = []
        for point in normalized:
            if deduped and abs(deduped[-1].x - point.x) < 1e-6:
                deduped[-1] = CurvePoint(x=deduped[-1].x, y=point.y)
            else:
                deduped.append(point)

        if not deduped or deduped[0].x > 0.0:
            deduped.insert(0, CurvePoint(x=0.0, y=0.0))
        else:
            deduped[0] = CurvePoint(x=0.0, y=deduped[0].y)
        if deduped[-1].x < 255.0:
            deduped.append(CurvePoint(x=255.0, y=255.0))
        else:
            deduped[-1] = CurvePoint(x=255.0, y=deduped[-1].y)

        if len(deduped) > 16:
            deduped = deduped[:15] + [deduped[-1]]
            deduped[0] = CurvePoint(x=0.0, y=deduped[0].y)
            deduped[-1] = CurvePoint(x=255.0, y=deduped[-1].y)
        return deduped

    @staticmethod
    def _curve_tangents(points: List[CurvePoint]) -> List[float]:
        count = len(points)
        if count < 2:
            return [0.0] * count
        secants: List[float] = []
        for index in range(count - 1):
            dx = max(points[index + 1].x - points[index].x, 1e-6)
            secants.append((points[index + 1].y - points[index].y) / dx)

        tangents = [0.0] * count
        tangents[0] = secants[0]
        tangents[-1] = secants[-1]
        for index in range(1, count - 1):
            prev_secant = secants[index - 1]
            next_secant = secants[index]
            if prev_secant == 0.0 or next_secant == 0.0 or prev_secant * next_secant < 0.0:
                tangents[index] = 0.0
            else:
                tangents[index] = (prev_secant + next_secant) / 2.0

        for index, secant in enumerate(secants):
            if abs(secant) < 1e-6:
                tangents[index] = 0.0
                tangents[index + 1] = 0.0
                continue
            alpha = tangents[index] / secant
            beta = tangents[index + 1] / secant
            magnitude = alpha * alpha + beta * beta
            if magnitude > 9.0:
                scale = 3.0 / np.sqrt(magnitude)
                tangents[index] = scale * alpha * secant
                tangents[index + 1] = scale * beta * secant
        return tangents

    @classmethod
    def _curve_to_lut(cls, points: List[CurvePoint], size: int = 256) -> np.ndarray:
        normalized_points = cls._normalize_curve_points(points)
        if len(normalized_points) < 2:
            return np.linspace(0.0, 1.0, size, dtype=np.float32)

        tangents = cls._curve_tangents(normalized_points)
        xs = [point.x for point in normalized_points]
        lut = np.empty(size, dtype=np.float32)
        interval = 0
        for index in range(size):
            x = float(index)
            while interval < len(xs) - 2 and x > xs[interval + 1]:
                interval += 1
            point0 = normalized_points[interval]
            point1 = normalized_points[interval + 1]
            dx = max(point1.x - point0.x, 1e-6)
            t = _clamp((x - point0.x) / dx, 0.0, 1.0)
            h00 = 2.0 * t**3 - 3.0 * t**2 + 1.0
            h10 = t**3 - 2.0 * t**2 + t
            h01 = -2.0 * t**3 + 3.0 * t**2
            h11 = t**3 - t**2
            y = (
                h00 * point0.y
                + h10 * dx * tangents[interval]
                + h01 * point1.y
                + h11 * dx * tangents[interval + 1]
            )
            lut[index] = _clamp(y / 255.0, 0.0, 1.0)
        return lut

    @staticmethod
    def _apply_lut(channel: np.ndarray, lut: np.ndarray) -> np.ndarray:
        indices = np.clip(channel * 255.0, 0.0, 255.0)
        lo = np.floor(indices).astype(np.int16)
        hi = np.clip(lo + 1, 0, 255)
        frac = indices - lo
        return lut[lo] * (1.0 - frac) + lut[hi] * frac

    def _apply_curves(self, image: Image.Image) -> Image.Image:
        curves = self.params.curves
        alpha = image.getchannel("A")
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0

        rgb_lut = self._curve_to_lut(curves.rgb_curve)
        red_lut = self._curve_to_lut(curves.red_curve)
        green_lut = self._curve_to_lut(curves.green_curve)
        blue_lut = self._curve_to_lut(curves.blue_curve)

        for channel_index in range(3):
            rgb[..., channel_index] = self._apply_lut(rgb[..., channel_index], rgb_lut)
        rgb[..., 0] = self._apply_lut(rgb[..., 0], red_lut)
        rgb[..., 1] = self._apply_lut(rgb[..., 1], green_lut)
        rgb[..., 2] = self._apply_lut(rgb[..., 2], blue_lut)

        result = Image.fromarray((np.clip(rgb, 0.0, 1.0) * 255).astype(np.uint8), mode="RGB").convert("RGBA")
        result.putalpha(alpha)
        return result

    def _apply_white_balance(self, image: Image.Image) -> Image.Image:
        """Apply a lightweight white-balance approximation in RGB space.

        Algorithm overview
        ------------------
        This implementation is intentionally simple and fast. It does *not* perform a
        full camera-raw style white-balance transform based on sensor metadata,
        chromatic adaptation matrices, or Planckian-locus fitting. Instead, it uses a
        practical approximation based on per-channel gain scaling:

        1. Convert the image to ``RGB`` and keep alpha aside.
        2. Compute a normalized temperature offset relative to neutral daylight:

           ``temp_shift = (temperature - 6500) / 6500``

           Meaning:
           - ``temperature = 6500``  -> neutral, ``temp_shift = 0``
           - warmer image            -> positive shift
           - cooler image            -> negative shift

        3. Compute a normalized tint offset:

           ``tint_shift = tint / 150``

           Meaning:
           - negative -> greener
           - positive -> more magenta

        4. Convert these offsets into channel gains:

           - Red   gain: ``1 + temp_shift * 0.12``
           - Blue  gain: ``1 - temp_shift * 0.12``
           - Green gain: ``1 + tint_shift * 0.08``

           Interpretation:
           - warming increases red and decreases blue
           - cooling does the opposite
           - tint adjusts the green channel to simulate the green↔magenta axis

        5. Clamp the RGB result to ``[0, 255]`` and restore the original alpha.

        Why this works
        --------------
        Human perception of "warmer/cooler" is dominated by the red/blue balance, and
        tint is commonly modeled along the green/magenta axis. A multiplicative gain on
        these channels gives a visually plausible result for a photo editor preview.

        Important limitations
        ---------------------
        - The transform happens directly in display RGB, not in a linear-light space.
        - It is an approximation, not a physically accurate Kelvin-to-RGB model.
        - The coefficients ``0.12`` and ``0.08`` are tuned for moderate, stable UI
          behavior rather than scientific correctness.
        - Extreme values may clip highlights/shadows because this is a gain-based edit.
        """
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
        temp_shift = (self.params.white_balance.temperature - 6500.0) / 6500.0
        tint_shift = self.params.white_balance.tint / 150.0
        rgb[..., 0] *= 1.0 + temp_shift * 0.12
        rgb[..., 2] *= 1.0 - temp_shift * 0.12
        rgb[..., 1] *= 1.0 + tint_shift * 0.08
        out = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), mode="RGB").convert("RGBA")
        out.putalpha(image.getchannel("A"))
        return out

    def _apply_tone(self, image: Image.Image) -> Image.Image:
        tone = self.params.tone
        result = image
        if tone.exposure:
            result = ImageEnhance.Brightness(result).enhance(float(2 ** _clamp(tone.exposure, -5.0, 5.0)))
        if tone.brightness:
            result = ImageEnhance.Brightness(result).enhance(max(0.0, 1.0 + tone.brightness / 200.0))
        if tone.contrast:
            result = ImageEnhance.Contrast(result).enhance(max(0.0, 1.0 + tone.contrast / 100.0))

        alpha = result.getchannel("A")
        rgb = np.asarray(result.convert("RGB"), dtype=np.float32) / 255.0
        luminance = (
            rgb[..., 0:1] * 0.2126
            + rgb[..., 1:2] * 0.7152
            + rgb[..., 2:3] * 0.0722
        )

        def apply_tonal_region(mask: np.ndarray, amount: float, strength: float) -> None:
            nonlocal rgb
            if not amount:
                return
            scaled = _clamp(amount / 100.0, -1.0, 1.0) * strength
            if scaled >= 0:
                rgb = rgb + (1.0 - rgb) * mask * scaled
            else:
                rgb = rgb * (1.0 + mask * scaled)

        if tone.highlights:
            apply_tonal_region(_smoothstep(0.45, 1.0, luminance), tone.highlights, 0.45)
        if tone.shadows:
            apply_tonal_region(1.0 - _smoothstep(0.0, 0.55, luminance), tone.shadows, 0.55)
        if tone.whites:
            apply_tonal_region(_smoothstep(0.72, 1.0, luminance), tone.whites, 0.35)
        if tone.blacks:
            apply_tonal_region(1.0 - _smoothstep(0.0, 0.28, luminance), tone.blacks, 0.40)

        result = Image.fromarray((np.clip(rgb, 0.0, 1.0) * 255).astype(np.uint8), mode="RGB").convert("RGBA")
        result.putalpha(alpha)
        if tone.clarity:
            clarity_strength = _clamp(tone.clarity / 100.0, -1.0, 1.0)
            if clarity_strength > 0:
                detail = result.filter(ImageFilter.DETAIL)
                result = composite_images(result, detail, BlendMode.OVERLAY, clarity_strength * 0.6, None)
            else:
                softened = result.filter(ImageFilter.GaussianBlur(radius=abs(clarity_strength) * 2.4))
                result = composite_images(result, softened, BlendMode.NORMAL, abs(clarity_strength) * 0.5, None)
        if tone.dehaze:
            dehaze_strength = _clamp(tone.dehaze / 100.0, -1.0, 1.0)
            if dehaze_strength > 0:
                result = ImageEnhance.Contrast(result).enhance(1.0 + dehaze_strength * 0.55)
                result = ImageEnhance.Color(result).enhance(1.0 + dehaze_strength * 0.18)
            else:
                fog_strength = abs(dehaze_strength)
                fog_layer = Image.new("RGBA", result.size, (236, 240, 245, int(round(255 * fog_strength * 0.22))))
                result = Image.alpha_composite(result, fog_layer)
                result = ImageEnhance.Contrast(result).enhance(max(0.0, 1.0 - fog_strength * 0.22))
        return result

    def _apply_hsl(self, image: Image.Image) -> Image.Image:
        hsl = self.params.hsl
        result = image
        if hsl.saturation:
            result = ImageEnhance.Color(result).enhance(max(0.0, 1.0 + hsl.saturation / 100.0))

        arr = np.asarray(result.convert("RGB"), dtype=np.float32) / 255.0
        if hsl.vibrance:
            mean = arr.mean(axis=2, keepdims=True)
            saturation = arr.max(axis=2, keepdims=True) - arr.min(axis=2, keepdims=True)
            boost = (1.0 - saturation) * (hsl.vibrance / 100.0) * 0.5
            arr = arr + (arr - mean) * boost
        if hsl.hue:
            arr = self._apply_global_hue(arr, hsl.hue)
        arr = self._apply_selective_hsl(arr)

        result = Image.fromarray((np.clip(arr, 0.0, 1.0) * 255).astype(np.uint8), mode="RGB").convert("RGBA")
        result.putalpha(image.getchannel("A"))
        return result

    def _apply_global_hue(self, arr: np.ndarray, hue_shift: float) -> np.ndarray:
        hue, lightness, saturation = _rgb_to_hls_array(arr)
        return _hls_to_rgb_array(hue + hue_shift / 360.0, lightness, saturation)

    @staticmethod
    def _build_hsl_band_mask(hue: np.ndarray, center: float, half_width: float) -> np.ndarray:
        distance = np.abs(np.mod(hue - center + 0.5, 1.0) - 0.5)
        outer_band = max(half_width, 1e-6)
        inner_band = outer_band * 0.55
        return np.clip(1.0 - _smoothstep(inner_band, outer_band, distance), 0.0, 1.0)

    def _apply_selective_hsl(self, arr: np.ndarray) -> np.ndarray:
        adjustments: list[tuple[HSLColorParams, float, float]] = []
        for color_name, center_degrees, half_width_degrees in self._HSL_COLOR_BANDS:
            color_params = self._coerce_hsl_color_params(getattr(self.params.hsl, color_name, None))
            if any(
                abs(float(value)) > 1e-6
                for value in (color_params.hue, color_params.saturation, color_params.luminance)
            ):
                adjustments.append((color_params, center_degrees / 360.0, half_width_degrees / 360.0))

        if not adjustments:
            return arr

        hue, lightness, saturation = _rgb_to_hls_array(arr)
        hue_delta = np.zeros_like(hue)
        saturation_scale = np.ones_like(saturation)
        lightness_delta = np.zeros_like(lightness)

        for color_params, center, half_width in adjustments:
            influence = self._build_hsl_band_mask(hue, center, half_width)
            hue_delta += (float(color_params.hue) / 360.0) * influence
            saturation_scale *= np.clip(1.0 + (float(color_params.saturation) / 100.0) * influence, 0.0, 4.0)
            lightness_delta += (float(color_params.luminance) / 200.0) * influence

        return _hls_to_rgb_array(hue + hue_delta, lightness + lightness_delta, saturation * saturation_scale)

    def _apply_color_editor(self, image: Image.Image) -> Image.Image:
        color_editor = self.params.color_editor
        if not any(
            abs(float(value)) > 1e-6
            for value in (
                color_editor.hue_shift,
                color_editor.saturation_shift,
                color_editor.luminance_shift,
            )
        ):
            return image

        rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
        hue, lightness, saturation = _rgb_to_hls_array(rgb)

        target_hue = (float(color_editor.hue) % 360.0) / 360.0
        target_saturation = _clamp(float(color_editor.saturation) / 100.0, 0.0, 1.0)
        target_lightness = _clamp((float(color_editor.lightness) + 100.0) / 200.0, 0.0, 1.0)

        color_smoothness = _clamp(float(color_editor.color_smoothness) / 100.0, 0.0, 1.0)
        luminance_smoothness = _clamp(float(color_editor.luminance_smoothness) / 100.0, 0.0, 1.0)

        hue_distance = np.abs(np.mod(hue - target_hue + 0.5, 1.0) - 0.5)
        saturation_distance = np.abs(saturation - target_saturation)
        lightness_distance = np.abs(lightness - target_lightness)

        hue_band = 0.025 + color_smoothness * 0.225
        saturation_band = 0.08 + color_smoothness * 0.92
        lightness_band = 0.04 + luminance_smoothness * 0.46

        hue_weight = 1.0 - _smoothstep(0.0, hue_band, hue_distance)
        saturation_weight = 1.0 - _smoothstep(0.0, saturation_band, saturation_distance)
        lightness_weight = 1.0 - _smoothstep(0.0, lightness_band, lightness_distance)

        if target_saturation < 0.08:
            color_weight = saturation_weight
        else:
            color_weight = hue_weight * 0.72 + saturation_weight * 0.28
        influence = np.clip(color_weight * lightness_weight, 0.0, 1.0)

        shifted_hue = hue + (float(color_editor.hue_shift) / 360.0) * influence
        shifted_saturation = saturation + (float(color_editor.saturation_shift) / 100.0) * influence
        shifted_lightness = lightness + (float(color_editor.luminance_shift) / 200.0) * influence

        adjusted_rgb = _hls_to_rgb_array(shifted_hue, shifted_lightness, shifted_saturation)
        result = Image.fromarray((adjusted_rgb * 255.0).astype(np.uint8), mode="RGB").convert("RGBA")
        result.putalpha(image.getchannel("A"))
        return result

    def _apply_detail(self, image: Image.Image) -> Image.Image:
        detail = self.params.detail
        result = image
        if detail.luminance_noise > 0:
            result = result.filter(ImageFilter.GaussianBlur(radius=_clamp(detail.luminance_noise / 30.0, 0.0, 5.0)))
        if detail.sharpen_amount > 0:
            for _ in range(max(1, int(round(detail.sharpen_amount / 25.0)))):
                result = result.filter(ImageFilter.UnsharpMask(radius=detail.sharpen_radius, percent=int(detail.sharpen_amount), threshold=int(detail.sharpen_threshold)))
        return result

    def _apply_geometry(self, image: Image.Image) -> Image.Image:
        geometry = self.params.geometry
        result = image
        if geometry.rotation:
            result = result.rotate(-geometry.rotation, resample=Image.Resampling.BICUBIC, expand=False)
        if geometry.scale and geometry.scale != 100:
            width, height = result.size
            scaled_w = max(1, int(width * geometry.scale / 100.0))
            scaled_h = max(1, int(height * geometry.scale / 100.0))
            scaled = result.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            offset_x = (width - scaled_w) // 2 + int(geometry.offset_x)
            offset_y = (height - scaled_h) // 2 + int(geometry.offset_y)
            canvas.alpha_composite(scaled, (offset_x, offset_y))
            result = canvas
        return result

    def _serialize_payload(self) -> Dict[str, Any]:
        return asdict(self.params)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "AdjustmentMalayer":
        payload = data.get("payload", {})
        basic_payload = payload.get("basic", {
            "exposure": payload.get("tone", {}).get("exposure", 0),
            "contrast": payload.get("tone", {}).get("contrast", 0),
            "hue": payload.get("hsl", {}).get("hue", 0),
            "saturation": payload.get("hsl", {}).get("saturation", 0),
            "vibrance": payload.get("hsl", {}).get("vibrance", 0),
        })
        curves_payload = payload.get("curves", {})
        hsl_payload = payload.get("hsl", {})
        params = AdjustmentParams(
            basic=BasicAdjustParams(**basic_payload),
            white_balance=WhiteBalanceParams(**payload.get("white_balance", {})),
            geometry=GeometryParams(**payload.get("geometry", {})),
            tone=ToneParams(**payload.get("tone", {})),
            curves=CurveParams(
                rgb_curve=[CurvePoint(**item) for item in curves_payload.get("rgb_curve", [{"x": 0, "y": 0}, {"x": 255, "y": 255}])],
                luminosity_curve=[CurvePoint(**item) for item in curves_payload.get("luminosity_curve", [{"x": 0, "y": 0}, {"x": 255, "y": 255}])],
                red_curve=[CurvePoint(**item) for item in curves_payload.get("red_curve", [{"x": 0, "y": 0}, {"x": 255, "y": 255}])],
                green_curve=[CurvePoint(**item) for item in curves_payload.get("green_curve", [{"x": 0, "y": 0}, {"x": 255, "y": 255}])],
                blue_curve=[CurvePoint(**item) for item in curves_payload.get("blue_curve", [{"x": 0, "y": 0}, {"x": 255, "y": 255}])],
            ),
            hsl=HSLParams(
                hue=hsl_payload.get("hue", basic_payload.get("hue", 0)),
                saturation=hsl_payload.get("saturation", basic_payload.get("saturation", 0)),
                vibrance=hsl_payload.get("vibrance", basic_payload.get("vibrance", 0)),
                red=HSLColorParams(**hsl_payload.get("red", {})),
                orange=HSLColorParams(**hsl_payload.get("orange", {})),
                yellow=HSLColorParams(**hsl_payload.get("yellow", {})),
                green=HSLColorParams(**hsl_payload.get("green", {})),
                aqua=HSLColorParams(**hsl_payload.get("aqua", {})),
                blue=HSLColorParams(**hsl_payload.get("blue", {})),
                purple=HSLColorParams(**hsl_payload.get("purple", {})),
                magenta=HSLColorParams(**hsl_payload.get("magenta", {})),
            ),
            color_editor=ColorEditorParams(**payload.get("color_editor", {})),
            color_grading=ColorGradingParams(**payload.get("color_grading", {})),
            detail=DetailParams(**payload.get("detail", {})),
            calibration=CalibrationParams(**payload.get("calibration", {})),
        )
        layer = cls(
            name=data.get("name", "Adjustment"),
            params=params,
            visible=data.get("visible", True),
            locked=data.get("locked", False),
            opacity=data.get("opacity", 1.0),
            blend_mode=BlendMode(data.get("blend_mode", BlendMode.NORMAL.value)),
            mask=Mask.from_dict(data.get("mask")),
            tab_id=data.get("tab_id"),
            layer_id=data.get("id"),
        )
        layer._sync_basic_to_pipeline()
        return layer


class MaskMalayer(TabMalayer):
    type_name = "mask"
    default_tab = EditorTab.MASK
    supported_tabs = (EditorTab.MASK, EditorTab.LAYERS)

    def apply(self, image: Image.Image, original_image: Optional[Image.Image] = None) -> Image.Image:
        return image.copy()

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "MaskMalayer":
        return cls(
            name=data.get("name", "Mask"),
            visible=data.get("visible", True),
            locked=data.get("locked", False),
            opacity=data.get("opacity", 1.0),
            blend_mode=BlendMode(data.get("blend_mode", BlendMode.NORMAL.value)),
            mask=Mask.from_dict(data.get("mask")),
            tab_id=data.get("tab_id"),
            layer_id=data.get("id"),
        )


class FilterMalayer(TabMalayer):
    type_name = "filter"
    default_tab = EditorTab.FILTER
    supported_tabs = (EditorTab.FILTER, EditorTab.LAYERS)

    def __init__(self, name: str = "Filter", *, filter_name: str = "blur", intensity: float = 1.0, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self.filter_name = filter_name
        self.intensity = intensity

    def apply(self, image: Image.Image, original_image: Optional[Image.Image] = None) -> Image.Image:
        intensity = max(0.0, self.intensity)
        if self.filter_name == "blur":
            return image.filter(ImageFilter.GaussianBlur(radius=max(0.1, intensity * 3.0)))
        if self.filter_name == "sharpen":
            return image.filter(ImageFilter.UnsharpMask(radius=2, percent=int(100 + intensity * 100), threshold=3))
        if self.filter_name == "detail":
            return image.filter(ImageFilter.DETAIL)
        if self.filter_name == "emboss":
            return image.filter(ImageFilter.EMBOSS)
        if self.filter_name == "grayscale":
            gray = ImageOps.grayscale(image).convert("RGBA")
            gray.putalpha(image.getchannel("A"))
            return gray
        if self.filter_name == "sepia":
            rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
            sepia = np.empty_like(rgb)
            sepia[..., 0] = rgb[..., 0] * 0.393 + rgb[..., 1] * 0.769 + rgb[..., 2] * 0.189
            sepia[..., 1] = rgb[..., 0] * 0.349 + rgb[..., 1] * 0.686 + rgb[..., 2] * 0.168
            sepia[..., 2] = rgb[..., 0] * 0.272 + rgb[..., 1] * 0.534 + rgb[..., 2] * 0.131
            out = Image.fromarray(np.clip(sepia, 0, 255).astype(np.uint8), mode="RGB").convert("RGBA")
            out.putalpha(image.getchannel("A"))
            return out
        return image.copy()

    def _serialize_payload(self) -> Dict[str, Any]:
        return {"filter_name": self.filter_name, "intensity": self.intensity}

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> "FilterMalayer":
        payload = data.get("payload", {})
        return cls(
            name=data.get("name", "Filter"),
            filter_name=payload.get("filter_name", "blur"),
            intensity=payload.get("intensity", 1.0),
            visible=data.get("visible", True),
            locked=data.get("locked", False),
            opacity=data.get("opacity", 1.0),
            blend_mode=BlendMode(data.get("blend_mode", BlendMode.NORMAL.value)),
            mask=Mask.from_dict(data.get("mask")),
            tab_id=data.get("tab_id"),
            layer_id=data.get("id"),
        )


def filter_malayers_by_tab(malayers: Iterable[Malayer], tab: str | EditorTab) -> List[Malayer]:
    return [layer for layer in malayers if layer.can_be_controlled_by(tab)]
