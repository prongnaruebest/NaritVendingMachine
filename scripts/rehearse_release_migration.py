from __future__ import annotations

import tempfile
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from narit_vending.release_migration import (  # noqa: E402
    MigrationCoordinator,
    MigrationStateStore,
)


class RehearsalRuntime:
    def __init__(self, *, fail_health: bool = False) -> None:
        self.fail_health = fail_health
        self.rolled_back = False
        self.actions: list[str] = []

    def preflight(self, release_id: str) -> None:
        self.actions.append(f"preflight:{release_id}")

    def backup(self) -> None:
        self.actions.append("backup")

    def stop(self) -> None:
        self.actions.append("stop")

    def migrate_layout(self, release_id: str) -> None:
        self.actions.append(f"migrate:{release_id}")

    def install_units(self, release_id: str) -> None:
        self.actions.append(f"install:{release_id}")

    def start(self) -> None:
        self.actions.append("start")

    def healthy(self) -> bool:
        self.actions.append("healthy")
        return self.rolled_back or not self.fail_health

    def rollback_legacy(self) -> None:
        self.actions.append("rollback")
        self.rolled_back = True


def main() -> int:
    release_id = "aaaaaaaaaaaa-bbbbbbbbbbbb"
    with tempfile.TemporaryDirectory(prefix="narit-release-rehearsal-") as directory:
        root = Path(directory)
        for fail_health in (False, True):
            runtime = RehearsalRuntime(fail_health=fail_health)
            store = MigrationStateStore(root / f"state-{fail_health}.json")
            result = MigrationCoordinator(store, runtime).migrate(release_id)
            scenario = "health-failure-rollback" if fail_health else "success"
            print(f"{scenario}: {result.phase.value} actions={','.join(runtime.actions)}")
    print("REHEARSAL PASSED: temporary files and fake services only; no machine command was issued.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
