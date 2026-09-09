from __future__ import annotations

from pathlib import Path


DOCS = Path(__file__).resolve().parents[1] / "docs"


def _manual() -> str:
    return (DOCS / "USER_MANUAL_TH.md").read_text(encoding="utf-8")


def test_operator_manual_separates_online_authority_and_readiness():
    text = _manual()

    assert "Online` หมายถึงสื่อสารได้ ไม่ได้แปลว่าเครื่องพร้อมเคลื่อน" in text
    assert "Motion Authority Disabled" in text
    assert "Enable Motion" in text


def test_operator_manual_documents_directional_limit_recovery():
    text = _manual()

    assert "disable เฉพาะปุ่มที่เคลื่อนเข้าหา sensor" in text
    assert "ทิศตรงข้ามต้องยังใช้ถอยออกได้" in text
    assert "physical endpoint" in text


def test_operator_manual_documents_drive_reset_without_promising_fault_clear():
    text = _manual()

    assert "DI0/DI1 alarm" in text
    assert "DI10/KM1 feedback" in text
    assert "power cycle อาจไม่ล้าง fault" in text


def test_demo_manual_uses_automatic_bounded_duration():
    text = (DOCS / "DEMO_SLOT_SAMPLING_TH.md").read_text(encoding="utf-8")

    assert "คำนวณ Maximum Duration อัตโนมัติ" in text
    assert "ไม่ใช่ช่องเพิ่มความเร็ว" in text
    assert "invalidate Configure/Validate/Arm" in text


def test_operator_manual_never_describes_normal_motion_bypass():
    text = _manual()

    assert "ห้าม bypass software limits" in text
    assert "Manual Commissioning" in text
    assert "ไม่สามารถข้าม E-Stop" in text
