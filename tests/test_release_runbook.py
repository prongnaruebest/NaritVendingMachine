from __future__ import annotations

from pathlib import Path


RUNBOOK = Path(__file__).resolve().parents[1] / "docs" / "RELEASE_MIGRATION_RUNBOOK_TH.md"


def test_runbook_marks_production_migration_as_blocked_until_executor_is_complete():
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "One-time production migration — blocked gate" in text
    assert "ห้ามรัน `scripts/activate_release.py --execute`" in text
    assert "scripts/deploy_to_iriv.ps1" in text


def test_runbook_preserves_all_persistent_machine_state():
    text = RUNBOOK.read_text(encoding="utf-8")

    for required in (
        "machine_config.iriv.json",
        "hardware_config.iriv.json",
        "controller_history.sqlite3",
        "demo_results.sqlite3",
        "backups/config",
        "shared/.venv",
    ):
        assert required in text


def test_runbook_separates_health_from_motion_acceptance():
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "/health/live" in text
    assert "/health/ready" in text
    assert "อาจตอบ 503" in text
    assert "การ Home, Jog, Move Min/Max, GOTO Slot, Dispense และ Demo Sampling" in text


def test_runbook_requires_verified_recovery_inputs_before_shutdown():
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "SQLite online backup" in text
    assert "สำรอง installed systemd units" in text
    assert "ถ้าข้อใดข้อหนึ่งไม่ผ่าน ให้หยุดกระบวนการโดยไม่ stop services" in text
