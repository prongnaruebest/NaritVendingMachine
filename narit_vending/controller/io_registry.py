"""Build the authoritative UI-neutral I/O channel registry."""

from __future__ import annotations

from typing import Any


def _semantics(key: str, direction: str, detail: dict[str, Any]) -> dict[str, Any]:
    key_lower = key.lower()
    axis = key_lower[0] if key_lower[:2] in {"x_", "y_", "z_"} else None
    if key_lower == "estop":
        kind, safety_class = "safety_interlock", "safety"
    elif key_lower.endswith("_alarm"):
        kind, safety_class = "drive_alarm", "fault"
    elif key_lower.endswith("_pend"):
        kind, safety_class = "position_feedback", "advisory"
    elif "limit" in key_lower or key_lower.endswith("_home"):
        kind, safety_class = "position_switch", "motion_limit"
    elif direction == "output":
        kind, safety_class = "command_output", "control"
    else:
        kind, safety_class = "process_sensor", "process"
    position_role = None
    if key_lower.endswith("_head_limit"):
        position_role = "min"
    elif key_lower.endswith("_tail_limit"):
        position_role = "max"
    elif key_lower.endswith("_home"):
        position_role = "home"
    return {
        "kind": str(detail.get("kind", kind)),
        "safety_class": str(detail.get("safety_class", safety_class)),
        "axis": detail.get("axis", axis),
        "position_role": detail.get("position_role", position_role),
        "operation_role": detail.get("operation_role", key_lower),
    }


def _channels(source: str, status: dict[str, Any], direction: str) -> list[dict[str, Any]]:
    details_key = "input_details" if direction == "input" else "output_details"
    registry: list[dict[str, Any]] = []
    for key, raw_detail in dict(status.get(details_key, {})).items():
        detail = dict(raw_detail)
        registry.append(
            {
                "id": f"{source}:{direction}:{key}",
                "source": source,
                "direction": direction,
                "key": key,
                "label": str(detail.get("label", key)),
                "channel": detail.get("channel"),
                "address": detail.get("raw_channel"),
                "protocol_address": (
                    f"0x{0x0100 + int(detail['channel']):04X}"
                    if source == "iriv_modbus" and direction == "output" and detail.get("channel") is not None
                    else None
                ),
                "pin": detail.get("pin"),
                "active": bool(detail.get("active", detail.get("value", False))),
                "raw_value": detail.get("raw_value"),
                "active_state": detail.get("active_state"),
                "active_high": detail.get("active_high"),
                "fail_safe": bool(detail.get("fail_safe", False)),
                "commissioned": bool(detail.get("commissioned", False)),
                "settle_timeout_ms": detail.get("settle_timeout_ms"),
                "require_transition": bool(detail.get("require_transition", False)),
                "transitions": int(detail.get("transitions", 0)),
                "active_events": int(detail.get("active_events", 0)),
                "last_change_at": detail.get("last_change_at"),
                "stale": not bool(status.get("communication_ok", False)),
                **_semantics(key, direction, detail),
            }
        )
    return registry


def build_io_registry(
    iriv_status: dict[str, Any],
    picontrol_status: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return stable channel metadata and live state in display order."""
    channels = [
        *_channels("iriv_modbus", iriv_status, "input"),
        *_channels("iriv_modbus", iriv_status, "output"),
        *_channels("picontrol_local", picontrol_status, "input"),
        *_channels("picontrol_local", picontrol_status, "output"),
    ]
    return sorted(
        channels,
        key=lambda item: (
            item["source"],
            item["direction"],
            int(item["channel"]) if item["channel"] is not None else 9999,
            item["key"],
        ),
    )
