from __future__ import annotations

from pathlib import Path


GUIDE = Path(__file__).resolve().parents[1] / "docs" / "TESTING_AND_TROUBLESHOOTING_TH.md"


def _text() -> str:
    return GUIDE.read_text(encoding="utf-8")


def test_read_only_diagnostics_are_documented_without_claiming_machine_ready():
    text = _text()
    for endpoint in ("/health/live", "/health/ready", "/api/status", "/api/io/status"):
        assert endpoint in text
    assert "ห้ามสรุปว่า hardware พร้อม" in text


def test_directional_limit_recovery_is_explicit():
    text = _text()
    assert "ห้ามคำสั่งที่วิ่งเข้า sensor มากขึ้น" in text
    assert "อนุญาตคำสั่งที่วิ่งออกจาก sensor" in text
    assert "missing-sensor watchdog" in text


def test_io_roles_cannot_be_confused():
    text = _text()
    assert 'DI0 = `X_DRIVE_ALM`, DI1 = `Y_DRIVE_ALM`' in text
    assert 'DI2 = `X_PEND`, DI3 = `Y_PEND`' in text
    assert 'DI10 = `KM1_FEEDBACK / E-Stop`' in text
    assert "PEND คือ in-position feedback; ALM คือ drive fault" in text


def test_drive_reset_is_bounded_and_does_not_auto_retry():
    text = _text()
    assert "Disable → Cut Power → ยืนยัน feedback" in text
    assert "คง Motion Disabled" in text
    assert "ห้าม reset ซ้ำอัตโนมัติ" in text


def test_known_z_hardware_safety_gap_is_not_hidden():
    text = _text()
    assert "Z/DM542 24 V ยังไม่ผ่าน safety" in text
    assert "software pulse inhibit" in text


def test_automated_verification_forbids_real_motion():
    text = _text()
    assert "fake/mock hardware เท่านั้น" in text
    assert "ไม่ได้ start server, Controller, GPIO, serial transport" in text
