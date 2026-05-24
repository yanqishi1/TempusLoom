"""TempusLoom-native image editing tools."""

from __future__ import annotations

import uuid
from typing import Any

from .tool_register import ToolContext, ToolRegister, ToolResult, ToolSpec


def register_native_tools(register: ToolRegister) -> None:
    register.register(
        ToolSpec(
            name="get_current_image_context",
            description="Return current image metadata and current adjustment state.",
            input_schema={"type": "object", "properties": {}},
        ),
        get_current_image_context,
    )
    register.register(
        ToolSpec(
            name="apply_adjustment_preview",
            description="Apply a TempusLoom adjustment JSON payload as a preview edit.",
            input_schema={
                "type": "object",
                "properties": {
                    "payload": {"type": "object", "description": "TempusLoom adjustment JSON payload."},
                    "description": {"type": "string", "description": "Short edit description."},
                },
                "required": ["payload"],
            },
        ),
        apply_adjustment_preview,
    )
    register.register(
        ToolSpec(
            name="create_mask_layer",
            description="Create a mask layer with a mask definition and local adjustment payload.",
            input_schema={
                "type": "object",
                "properties": {
                    "mask": {"type": "object"},
                    "payload": {"type": "object"},
                    "name": {"type": "string"},
                    "opacity": {"type": "number"},
                    "blendMode": {"type": "string"},
                },
                "required": ["mask", "payload"],
            },
        ),
        create_mask_layer,
    )
    register.register(
        ToolSpec(
            name="undo_last_agent_edit",
            description="Undo the latest edit created by the agent.",
            input_schema={"type": "object", "properties": {}},
        ),
        undo_last_agent_edit,
    )


def get_current_image_context(args: dict[str, Any], context: ToolContext) -> ToolResult:
    context.check_cancelled()
    return ToolResult(
        success=True,
        data={
            "image": context.image or {},
            "current_adjust": context.current_adjust or {},
            "session_id": context.session_id,
        },
    )


def apply_adjustment_preview(args: dict[str, Any], context: ToolContext) -> ToolResult:
    context.check_cancelled()
    payload = args.get("payload")
    if not isinstance(payload, dict):
        return ToolResult(success=False, error="payload must be an object.")
    description = str(args.get("description", "Agent adjustment preview"))
    if context.apply_payload:
        edit_id = context.apply_payload(payload, description)
    else:
        edit_id = f"agent-edit-{uuid.uuid4().hex[:12]}"
    return ToolResult(success=True, data={"edit_id": edit_id, "payload": payload}, edit_id=edit_id)


def create_mask_layer(args: dict[str, Any], context: ToolContext) -> ToolResult:
    context.check_cancelled()
    mask = args.get("mask")
    payload = args.get("payload")
    if not isinstance(mask, dict):
        return ToolResult(success=False, error="mask must be an object.")
    if not isinstance(payload, dict):
        return ToolResult(success=False, error="payload must be an object.")

    layer_id = str(args.get("id") or f"agent-mask-{uuid.uuid4().hex[:8]}")
    layer = {
        "id": layer_id,
        "type": "mask",
        "name": str(args.get("name", "Agent Mask")),
        "visible": bool(args.get("visible", True)),
        "opacity": float(args.get("opacity", 1.0)),
        "blendMode": str(args.get("blendMode", "normal")),
        "mask": mask,
        "payload": payload,
    }
    adjustment_payload = {"layers": [layer]}
    if context.apply_payload:
        edit_id = context.apply_payload(adjustment_payload, layer["name"])
    else:
        edit_id = f"agent-edit-{uuid.uuid4().hex[:12]}"
    return ToolResult(
        success=True,
        data={"edit_id": edit_id, "layer": layer, "payload": adjustment_payload},
        edit_id=edit_id,
    )


def undo_last_agent_edit(args: dict[str, Any], context: ToolContext) -> ToolResult:
    context.check_cancelled()
    if context.undo_last_edit:
        ok = context.undo_last_edit()
        return ToolResult(success=bool(ok), data={"undone": bool(ok)}, error="" if ok else "Undo failed.")
    return ToolResult(success=False, error="undo_last_edit callback is not configured.")
