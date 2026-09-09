from __future__ import annotations

from pathlib import Path


DOCS = Path(__file__).resolve().parents[1] / "docs"
GUIDE = DOCS / "CONFIGURATION_AND_CALIBRATION_TH.md"


def test_configuration_guide_documents_effective_precedence_and_iriv_authority():
    text = GUIDE.read_text(encoding="utf-8")
    assert "hardware_config.iriv.json > machine_parameters.axes" in text
    assert "GET /api/config/effective" in text
    assert "ไม่ใช่ authority ของเครื่อง IRIV V1" in text


def test_configuration_guide_matches_current_iriv_axis_calibration():
    text = GUIDE.read_text(encoding="utf-8")
    assert "64.705882" in text
    assert "Z | timing belt/pulley | 1,600 | 9.0 | 160 mm" in text
    assert "pulley_teeth` ยังเป็น null" in text


def test_saved_speed_is_not_claimed_as_mechanically_proven():
    text = GUIDE.read_text(encoding="utf-8")
    assert "ห้ามตีความว่า 100 mm/s ผ่านการทดสอบแล้ว" in text
    assert "pulse-input rating ของ driver" in text


def test_guide_covers_safe_save_apply_and_rehome():
    text = GUIDE.read_text(encoding="utf-8")
    assert "SAVE TO PI" in text
    assert "restart_required=true" in text
    assert "APPLY & RESTART" in text
    assert "Home ใหม่" in text


def test_pend_remains_advisory_until_commissioned():
    text = GUIDE.read_text(encoding="utf-8")
    assert "DI2 คือ `X_PEND` และ DI3 คือ `Y_PEND`" in text
    assert "คง `commissioned=false`" in text
    assert "เปิด `commissioned=true` ทีละแกน" in text
    assert "ไม่ควร Reset Drives อัตโนมัติ" in text


def test_travel_guide_flags_historical_measurement_mismatch():
    text = (DOCS / "TRAVEL_CALIBRATION_TH.md").read_text(encoding="utf-8")
    assert "ไม่ตรงสูตรนี้" in text
    assert "ห้ามใช้บันทึก 1,600 mm เป็นหลักฐานรองรับค่า 1,700 mm" in text
