from __future__ import annotations

from pathlib import Path

import pytest

from scripts.plan_release_migration import PROFILES, migration_plan


RELEASE = "aaaaaaaaaaaa-bbbbbbbbbbbb"


def test_iriv_plan_separates_code_runtime_and_persistent_state():
    base = Path("/home/admin/NaritVendingV1")
    posix_base = "/home/admin/NaritVendingV1"

    plan = migration_plan(base, RELEASE, PROFILES["iriv"])

    assert plan["candidate"] == f"{posix_base}/releases/{RELEASE}"
    assert plan["current_link"] == f"{posix_base}/current"
    persistent = plan["persistent"]
    assert persistent["venv"] == f"{posix_base}/shared/.venv"
    assert persistent["machine_config"].endswith("/shared/config/machine_config.iriv.json")
    assert persistent["controller_database"].endswith("/shared/config/controller_history.sqlite3")
    assert persistent["demo_database"].endswith("/shared/config/demo_results.sqlite3")


def test_plan_requires_backups_and_never_contains_motion_actions():
    plan = migration_plan(Path("/machine"), RELEASE, PROFILES["mockup"])

    assert "sqlite_online_backups_verified" in plan["preconditions"]
    assert "existing_systemd_units_backed_up" in plan["preconditions"]
    assert plan["motion_commands"] == []
    assert plan["automatic_home"] is False
    assert plan["automatic_jog"] is False
    assert plan["automatic_goto"] is False


def test_plan_rejects_relative_base_and_unsafe_release_id():
    with pytest.raises(ValueError, match="absolute"):
        migration_plan(Path("relative"), RELEASE, PROFILES["iriv"])
    with pytest.raises(ValueError, match="release ID"):
        migration_plan(Path("/machine"), "../../unsafe", PROFILES["iriv"])


@pytest.mark.parametrize(
    ("unit_name", "base", "machine_config", "hardware_config"),
    (
        (
            "narit-vending-controller-iriv.service",
            "/home/admin/NaritVendingV1",
            "machine_config.iriv.json",
            "hardware_config.iriv.json",
        ),
        (
            "narit-vending-controller.service",
            "/home/admin/NaritVendingMOCKUP",
            "machine_config.json",
            "hardware_config.json",
        ),
    ),
)
def test_release_controller_units_use_current_code_and_shared_state(
    unit_name: str, base: str, machine_config: str, hardware_config: str
):
    root = Path(__file__).resolve().parents[1]
    unit = (root / "deploy" / "release-layout" / unit_name).read_text(encoding="utf-8")

    assert f"WorkingDirectory={base}/current" in unit
    assert f"{base}/shared/.venv/bin/python3" in unit
    assert f"--config {base}/shared/config/{machine_config}" in unit
    assert f"--hw-config {base}/shared/config/{hardware_config}" in unit
    assert f"--persistence-db {base}/shared/config/controller_history.sqlite3" in unit


def test_legacy_units_remain_unchanged_until_migration_is_explicit():
    root = Path(__file__).resolve().parents[1]
    legacy = (root / "deploy" / "narit-vending-controller-iriv.service").read_text(encoding="utf-8")

    assert "WorkingDirectory=/home/admin/NaritVendingV1\n" in legacy
    assert "/shared/" not in legacy
