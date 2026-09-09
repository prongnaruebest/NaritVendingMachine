from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from narit_vending.release_lifecycle import ReleaseActivator, ReleaseStateStore  # noqa: E402
from narit_vending.systemd_release_runtime import SystemdReleaseRuntime  # noqa: E402
from scripts.verify_release import (  # noqa: E402
    ReleaseVerificationError,
    validate_staged_configuration,
    validate_staged_python,
    verify_staged_release,
)


CONFIRMATION = "ACTIVATE_SERVICES_WITHOUT_MOTION"


def staged_validator(machine_config: Path, hardware_config: Path, python: str):
    def validate(release_dir: Path) -> None:
        manifest_path = release_dir / "release-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        verify_staged_release(release_dir, manifest)
        validate_staged_python(release_dir)
        validate_staged_configuration(
            release_dir,
            machine_config,
            hardware_config,
            python=python,
        )

    return validate


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate or activate one staged release with rollback.")
    parser.add_argument("release_id")
    parser.add_argument("--releases-root", type=Path, required=True)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--current-link", type=Path, required=True)
    parser.add_argument("--machine-config", type=Path, required=True)
    parser.add_argument("--hardware-config", type=Path, required=True)
    parser.add_argument("--controller-service", required=True)
    parser.add_argument("--web-service", required=True)
    parser.add_argument("--live-url", default="http://127.0.0.1/health/live")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args()

    release_dir = args.releases_root.resolve() / args.release_id
    validator = staged_validator(
        args.machine_config.resolve(),
        args.hardware_config.resolve(),
        args.python,
    )
    try:
        validator(release_dir)
    except (OSError, ValueError, ReleaseVerificationError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"VALIDATED: {args.release_id}")
    print(f"candidate={release_dir}")
    print(f"current_link={args.current_link.absolute()}")
    print(f"services={args.controller_service},{args.web_service}")
    print(f"health={args.live_url}")
    if not args.execute:
        print("DRY RUN: no symlink or service was changed. Use --execute with the confirmation token to activate.")
        return 0
    if args.confirm != CONFIRMATION:
        print(f"FAILED: --execute requires --confirm {CONFIRMATION}", file=sys.stderr)
        return 2
    if os.name != "posix":
        print("FAILED: live activation is allowed only on a POSIX target host.", file=sys.stderr)
        return 2

    runtime = SystemdReleaseRuntime(
        current_link=args.current_link.absolute(),
        controller_service=args.controller_service,
        web_service=args.web_service,
        live_url=args.live_url,
        validator=validator,
    )
    activator = ReleaseActivator(
        args.releases_root.resolve(),
        ReleaseStateStore(args.state_file.resolve()),
        runtime,
    )
    try:
        state = activator.activate(args.release_id)
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"RESULT: {state.status.value} active={state.active_release}")
    print("Activation restarts services but does not issue Home, Jog, GOTO, Dispense or Demo commands.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
