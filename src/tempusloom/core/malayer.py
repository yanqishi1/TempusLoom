from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, ClassVar, Dict, Iterable, List, Optional, Type
import colorsys
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
            AdjustmentSection.TONE.value: self.params.tone,
            AdjustmentSection.CURVES.value: self.params.curves,
            AdjustmentSection.HSL.value: self.params.hsl,
            AdjustmentSection.COLOR_GRADING.value: self.params.color_grading,
            AdjustmentSection.DETAIL.value: self.params.detail,
            AdjustmentSection.LENS.value: self.params.geometry,
            AdjustmentSection.PERSPECTIVE.value: self.params.geometry,
            AdjustmentSection.CALIBRATION.value: self.params.calibration,
        }
        if value not in mapping:
            raise KeyError(f"Unsupported adjustment section: {value}")
        return mapping[value]

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

        target = self.get_section_params(section_value)
        for key, value in normalized_values.items():
            if hasattr(target, key):
                setattr(target, key, value)
        if section_value == AdjustmentSection.BASIC.value:
            self._sync_basic_to_pipeline()

    def apply(self, image: Image.Image, original_image: Optional[Image.Image] = None) -> Image.Image:
        result = _ensure_rgba(image)
        result = self._apply_white_balance(result)
        result = self._apply_tone(result)
        result = self._apply_hsl(result)
        result = self._apply_detail(result)
        result = self._apply_geometry(result)
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
        if tone.contrast:
            result = ImageEnhance.Contrast(result).enhance(max(0.0, 1.0 + tone.contrast / 100.0))

        rgb = np.asarray(result.convert("RGB"), dtype=np.float32) / 255.0
        luminance = rgb.mean(axis=2, keepdims=True)
        if tone.highlights:
            mask = np.clip((luminance - 0.5) * 2.0, 0.0, 1.0)
            rgb *= 1.0 - mask * (tone.highlights / 100.0) * 0.35
        if tone.shadows:
            mask = np.clip((0.5 - luminance) * 2.0, 0.0, 1.0)
            rgb += (1.0 - rgb) * mask * (tone.shadows / 100.0) * 0.35
        if tone.whites:
            rgb += np.clip((luminance - 0.75) / 0.25, 0.0, 1.0) * (tone.whites / 100.0) * 0.2
        if tone.blacks:
            rgb -= np.clip((0.25 - luminance) / 0.25, 0.0, 1.0) * (tone.blacks / 100.0) * 0.2

        result = Image.fromarray((np.clip(rgb, 0.0, 1.0) * 255).astype(np.uint8), mode="RGB").convert("RGBA")
        result.putalpha(image.getchannel("A"))
        if tone.clarity > 0:
            detail = result.filter(ImageFilter.DETAIL)
            result = composite_images(result, detail, BlendMode.OVERLAY, _clamp(tone.clarity / 100.0, 0.0, 1.0) * 0.6, None)
        if tone.dehaze > 0:
            result = ImageEnhance.Contrast(result).enhance(1.0 + tone.dehaze / 180.0)
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

        result = Image.fromarray((np.clip(arr, 0.0, 1.0) * 255).astype(np.uint8), mode="RGB").convert("RGBA")
        result.putalpha(image.getchannel("A"))
        return result

    def _apply_global_hue(self, arr: np.ndarray, hue_shift: float) -> np.ndarray:
        delta = hue_shift / 360.0
        out = np.empty_like(arr)
        height, width, _ = arr.shape
        for y in range(height):
            for x in range(width):
                r, g, b = arr[y, x]
                h, l, s = colorsys.rgb_to_hls(float(r), float(g), float(b))
                out[y, x] = colorsys.hls_to_rgb((h + delta) % 1.0, l, s)
        return out

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
