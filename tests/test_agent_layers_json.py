import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tempusloom.agent.color_agent import AgentRequestContext, TempusLoomColorAgent
from tempusloom.core.tl_image import TLImage


def _write_base_image(path: Path, color=(96, 96, 96, 255)) -> None:
    Image.new("RGBA", (24, 24), color).save(path)


def _write_gradient_image(path: Path) -> None:
    image = Image.new("RGBA", (24, 24))
    for x in range(24):
        value = int(40 + x * 8)
        for y in range(24):
            image.putpixel((x, y), (value, value, value, 255))
    image.save(path)


def test_open_from_json_uses_layers_array_as_render_stack(tmp_path):
    image_path = tmp_path / "base.png"
    _write_base_image(image_path)

    tl_image = TLImage.open_from_json(
        {
            "imagePath": str(image_path),
            "layers": [
                {
                    "id": "base",
                    "type": "adjustment",
                    "name": "Base",
                    "payload": {"basic": {"exposure": 0.2}},
                },
                {
                    "id": "left-mask",
                    "type": "mask",
                    "name": "Left brighten",
                    "mask": {
                        "type": "linear",
                        "start": {"x": 0.0, "y": 0.0},
                        "end": {"x": 1.0, "y": 0.0},
                    },
                    "payload": {"tone": {"brightness": 70}},
                },
            ],
        }
    )

    assert [layer.id for layer in tl_image.malayers] == ["base", "left-mask"]
    assert [layer.type_name for layer in tl_image.malayers] == ["adjustment", "mask"]


def test_layers_array_order_controls_composited_render_order(tmp_path):
    image_path = tmp_path / "gradient.png"
    _write_gradient_image(image_path)

    brighten_layer = {
        "id": "brighten",
        "type": "mask",
        "name": "Brighten",
        "mask": {"type": "full"},
        "payload": {"tone": {"brightness": 80}},
    }
    contrast_layer = {
        "id": "contrast",
        "type": "mask",
        "name": "Contrast",
        "mask": {"type": "full"},
        "payload": {"tone": {"contrast": 80}},
    }

    first = TLImage.open_from_json(
        {"imagePath": str(image_path), "layers": [brighten_layer, contrast_layer]}
    ).render_image()
    second = TLImage.open_from_json(
        {"imagePath": str(image_path), "layers": [contrast_layer, brighten_layer]}
    ).render_image()

    assert first.tobytes() != second.tobytes()


def test_agent_payload_parser_preserves_layers_and_mask_roots():
    raw_text = json.dumps(
        {
            "adjust": {"tone": {"contrast": 12}},
            "mask": {"type": "radial", "center": {"x": 0.5, "y": 0.5}},
            "layers": [
                {
                    "id": "subject",
                    "type": "mask",
                    "mask": {"type": "radial", "radius": 0.35},
                    "payload": {"colorGrading": {"midtonesHue": 35}},
                }
            ],
            "meta": {"styleName": "局部暖调"},
        }
    )

    payload = TempusLoomColorAgent._parse_adjustment_payload(raw_text)

    assert "layers" in payload
    assert "mask" in payload
    assert payload["layers"][0]["id"] == "subject"


def test_agent_payload_parser_does_not_wrap_layers_only_response_as_adjust():
    raw_text = json.dumps(
        {
            "layers": [
                {
                    "id": "subject",
                    "type": "mask",
                    "mask": {"type": "radial", "radius": 0.35},
                    "payload": {"tone": {"brightness": 10}},
                }
            ]
        }
    )

    payload = TempusLoomColorAgent._parse_adjustment_payload(raw_text)

    assert "layers" in payload
    assert "adjust" not in payload


def test_apply_ai_response_payload_creates_json_layers(tmp_path):
    image_path = tmp_path / "base.png"
    _write_base_image(image_path)
    tl_image = TLImage.open(str(image_path))

    response_payload = {
        "adjust": {"tone": {"contrast": 8}},
        "layers": [
            {
                "id": "global-adjust",
                "type": "adjustment",
                "name": "Global",
                "payload": {"tone": {"brightness": 8}},
            },
            {
                "id": "subject-mask",
                "type": "mask",
                "name": "Subject",
                "mask": {
                    "type": "radial",
                    "center": {"x": 0.5, "y": 0.5},
                    "radius": {"x": 0.35, "y": 0.35},
                    "feather": 0.6,
                },
                "payload": {"colorGrading": {"midtonesHue": 42, "midtonesSaturation": 20}},
            },
        ],
    }

    tl_image.apply_agent_json_payload(response_payload)

    assert [layer.id for layer in tl_image.malayers] == ["global-adjust", "subject-mask"]
    assert tl_image.malayers[1].mask is not None
    assert tl_image.malayers[1].mask.mask_type == "radial"


def test_agent_layer_payload_accepts_camel_case_color_grading_luminance(tmp_path):
    image_path = tmp_path / "base.png"
    _write_base_image(image_path)
    tl_image = TLImage.open(str(image_path))

    tl_image.apply_agent_json_payload(
        {
            "layers": [
                {
                    "id": "subject-mask",
                    "type": "mask",
                    "mask": {"type": "full"},
                    "payload": {
                        "colorGrading": {
                            "shadowsLuminance": -12,
                            "midtonesLuminance": 8,
                            "highlightsLuminance": 5,
                        }
                    },
                }
            ]
        }
    )

    grading = tl_image.malayers[0].params.color_grading
    assert grading.shadows_luminance == -12
    assert grading.midtones_luminance == 8
    assert grading.highlights_luminance == 5


def test_agent_user_prompt_guides_sky_request_to_linear_mask_layer():
    prompt = TempusLoomColorAgent._build_user_prompt(
        AgentRequestContext(
            image={"width": 1200, "height": 800, "byte_size": 1024, "mime_type": "image/jpeg"},
            style_prompt="希望天空蓝一点，并且地面保持正常的曝光",
            current_adjust={"adjust": {}, "layers": []},
            image_name="landscape.jpg",
        )
    )

    assert "线性渐变蒙版" in prompt
    assert '"type": "linear"' in prompt
    assert "只作用于天空" in prompt
    assert "地面保持正常曝光" in prompt
    assert '"payload"' in prompt


def test_sky_linear_mask_agent_payload_creates_local_sky_adjustment(tmp_path):
    image_path = tmp_path / "base.png"
    _write_base_image(image_path)
    tl_image = TLImage.open(str(image_path))

    tl_image.apply_agent_json_payload(
        {
            "layers": [
                {
                    "id": "sky-blue-linear-mask",
                    "type": "mask",
                    "name": "天空蓝色增强",
                    "mask": {
                        "type": "linear",
                        "start": {"x": 0.5, "y": 0.0},
                        "end": {"x": 0.5, "y": 0.55},
                        "featherRadius": 8,
                    },
                    "payload": {
                        "hsl": {
                            "blue": {"saturation": 24, "luminance": -4},
                            "aqua": {"saturation": 12, "hue": -4},
                        },
                        "tone": {"highlights": -8},
                    },
                }
            ],
            "meta": {"styleName": "天空蓝色增强"},
        }
    )

    layer = tl_image.malayers[0]
    assert layer.type_name == "mask"
    assert layer.mask.mask_type == "linear"
    assert layer.mask.start_y == 0.0
    assert layer.mask.end_y == 0.55
    assert layer.params.hsl.blue.saturation == 24
    assert layer.params.tone.exposure == 0
    assert layer.params.tone.brightness == 0


def test_preview_mask_layer_adjustment_persists_into_render_pipeline_for_image_masks(tmp_path):
    image_path = tmp_path / "base.png"
    mask_path = tmp_path / "mask.png"
    _write_base_image(image_path, color=(96, 96, 96, 255))
    Image.new("L", (24, 24), 255).save(mask_path)

    tl_image = TLImage.open(str(image_path))
    layer = tl_image.add_mask_layer(
        {
            "type": "image",
            "name": "Portrait Mask",
            "image_path": str(mask_path),
            "opacity": 1.0,
            "invert": False,
        }
    )

    before = tl_image.render_image()
    tl_image.preview_mask_layer_adjustment(layer.id, "tone", {"brightness": 80})
    after = tl_image.render_image()

    assert before.tobytes() != after.tobytes()
    layer_state = next(
        item for item in tl_image.edit_state["layers"]
        if item.get("id") == layer.id
    )
    assert layer_state["payload"]["tone"]["brightness"] == 80


def test_preview_mask_layer_exposure_survives_layer_rebuild_for_image_masks(tmp_path):
    image_path = tmp_path / "base.png"
    mask_path = tmp_path / "mask.png"
    _write_base_image(image_path, color=(96, 96, 96, 255))
    Image.new("L", (24, 24), 255).save(mask_path)

    tl_image = TLImage.open(str(image_path))
    layer = tl_image.add_mask_layer(
        {
            "type": "image",
            "name": "Portrait Mask",
            "image_path": str(mask_path),
            "opacity": 1.0,
            "invert": False,
        }
    )

    before = tl_image.render_image()
    tl_image.preview_mask_layer_adjustment(layer.id, "tone", {"exposure": 1.0})
    after = tl_image.render_image()
    rebuilt_layer = tl_image.get_malayer(layer.id)

    assert rebuilt_layer.params.tone.exposure == 1.0
    assert before.tobytes() != after.tobytes()


def test_remove_mask_layer_removes_bound_adjustment_payload(tmp_path):
    image_path = tmp_path / "base.png"
    mask_path = tmp_path / "mask.png"
    _write_base_image(image_path, color=(96, 96, 96, 255))
    Image.new("L", (24, 24), 255).save(mask_path)

    tl_image = TLImage.open(str(image_path))
    layer = tl_image.add_mask_layer(
        {
            "type": "image",
            "name": "Portrait Mask",
            "image_path": str(mask_path),
            "opacity": 1.0,
            "invert": False,
        },
        adjustment={"tone": {"brightness": 80}},
    )

    removed = tl_image.remove_malayer(layer.id)

    assert removed.id == layer.id
    assert tl_image.get_malayer(layer.id) is None
    assert all(item.get("id") != layer.id for item in tl_image.edit_state.get("layers", []))
