from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


RELEASE_ID_PATTERN = re.compile(r"^[0-9a-f]{12}-[0-9a-f]{12}$")


@dataclass(frozen=True)
class ProfileLayout:
    name: str
    machine_config: str
    hardware_config: str
    controller_service: str
    web_service: str


PROFILES = {
    "iriv": ProfileLayout(
        name="iriv",
        machine_config="machine_config.iriv.json",
        hardware_config="hardware_config.iriv.json",
        controller_service="narit-vending-controller-iriv.service",
        web_service="narit-vending-web-iriv.service",
    ),
    "mockup": ProfileLayout(
        name="mockup",
        machine_config="machine_config.json",
        hardware_config="hardware_config.json",
        controller_service="narit-vending-controller.service",
        web_service="narit-vending-web.service",
    ),
}


def migration_plan(base: str | Path, release_id: str, profile: ProfileLayout) -> dict[str, object]:
    base_path = PurePosixPath(str(base).replace("\\", "/"))
    if not base_path.is_absolute():
        raise ValueError("Base directory must be absolute")
    if RELEASE_ID_PATTERN.fullmatch(release_id) is None:
        raise ValueError("Invalid release ID")
    shared = base_path / "shared"
    config = shared / "config"
    candidate = base_path / "releases" / release_id
    return {
        "schema_version": 1,
        "profile": profile.name,
        "base": str(base_path),
        "candidate": str(candidate),
        "current_link": str(base_path / "current"),
        "state_file": str(shared / "release-state.json"),
        "persistent": {
            "venv": str(shared / ".venv"),
            "machine_config": str(config / profile.machine_config),
            "hardware_config": str(config / profile.hardware_config),
            "controller_database": str(config / "controller_history.sqlite3"),
            "demo_database": str(config / "demo_results.sqlite3"),
            "configuration_backups": str(config / "backups" / "config"),
        },
        "services": {
            "controller": profile.controller_service,
            "web": profile.web_service,
            "template_directory": str(candidate / "deploy" / "release-layout"),
        },
        "preconditions": [
            "operator_outage_approval",
            "machine_idle_and_motion_disabled",
            "candidate_verified_and_staged",
            "configuration_validation_passed",
            "sqlite_online_backups_verified",
            "existing_systemd_units_backed_up",
        ],
        "ordered_phases": [
            "backup_configuration_databases_and_units",
            "stop_web_then_controller",
            "copy_persistent_files_to_shared_without_deleting_legacy_files",
            "move_venv_to_shared_and_create_legacy_venv_symlink",
            "create_current_symlink_to_verified_candidate",
            "install_release_layout_units_and_daemon_reload",
            "start_controller_then_web",
            "verify_service_activity_and_health_live",
            "record_active_release_or_restore_units_and_legacy_layout",
        ],
        "motion_commands": [],
        "automatic_home": False,
        "automatic_jog": False,
        "automatic_goto": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a read-only one-time release-layout migration plan.")
    parser.add_argument("--base", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    args = parser.parse_args()
    try:
        plan = migration_plan(args.base, args.release_id, PROFILES[args.profile])
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(plan, indent=2))
    print("DRY RUN PLAN ONLY: no files, services, configuration or machine state were changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
