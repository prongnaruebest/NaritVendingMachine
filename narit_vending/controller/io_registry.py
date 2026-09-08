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
    return {
        "kind": str(detail.get("kind", kind)),
        "safety_class": str(detail.get("safety_class", safety_class)),
        "axis": detail.get("axis", axis),
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
                "pin": detail.get("pin"),
                "active": bool(detail.get("active", detail.get("value", False))),
                "raw_value": detail.get("raw_value"),
                "active_state": detail.get("active_state"),
                "active_high": detail.get("active_high"),
                "fail_safe": bool(detail.get("fail_safe", False)),
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
