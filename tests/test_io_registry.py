from narit_vending.controller.io_registry import build_io_registry
from narit_vending.shared.snapshot import MachineSnapshot


def test_registry_describes_iriv_and_picontrol_channels() -> None:
    iriv = {
        "communication_ok": True,
        "input_details": {
            "estop": {
                "channel": 10,
                "raw_channel": "DI10",
                "label": "KM1_FEEDBACK / E-Stop",
                "active": False,
                "raw_value": True,
                "active_state": False,
                "fail_safe": True,
            }
        },
        "output_details": {},
    }
    picontrol = {
        "communication_ok": True,
        "input_details": {
            "x_pend": {
                "channel": 2,
                "raw_channel": "DI2",
                "pin": 27,
                "label": "X_PEND",
                "active": True,
                "raw_value": True,
                "active_state": True,
            }
        },
        "output_details": {},
    }

    channels = build_io_registry(iriv, picontrol)
    estop = next(item for item in channels if item["key"] == "estop")
    pend = next(item for item in channels if item["key"] == "x_pend")

    assert estop["id"] == "iriv_modbus:input:estop"
    assert estop["safety_class"] == "safety"
    assert estop["fail_safe"] is True
    assert pend["source"] == "picontrol_local"
    assert pend["kind"] == "position_feedback"
    assert pend["safety_class"] == "advisory"
    assert pend["axis"] == "x"


def test_registry_marks_channels_stale_when_source_is_offline() -> None:
    channels = build_io_registry(
        {"communication_ok": False, "input_details": {"door": {"channel": 1}}},
        {},
    )
    assert channels[0]["stale"] is True


def test_snapshot_round_trip_preserves_registry() -> None:
    offline = MachineSnapshot.offline()
    payload = offline.to_dict()
    payload["io_registry"] = [{"id": "iriv_modbus:input:estop", "active": False}]
    restored = MachineSnapshot.from_dict(payload)
    assert restored.io_registry == [{"id": "iriv_modbus:input:estop", "active": False}]
