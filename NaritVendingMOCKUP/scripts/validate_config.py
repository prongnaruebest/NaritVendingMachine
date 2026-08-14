from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from narit_vending.config_foundation import validate_configuration_files  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate NARIT VENDING configuration without initializing GPIO")
    parser.add_argument("--machine", default="machine_config.json")
    parser.add_argument("--hardware", default="hardware_config.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-warning", action="store_true")
    args = parser.parse_args()

    report = validate_configuration_files(args.machine, args.hardware)
    output = json.dumps(report.to_dict(), indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")
    has_warnings = any(issue.severity == "warning" for issue in report.issues)
    return 1 if not report.valid or (args.fail_on_warning and has_warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
