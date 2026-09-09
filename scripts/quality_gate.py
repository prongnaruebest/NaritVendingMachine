from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Gate:
    name: str
    command: tuple[str, ...]


def javascript_files(root: Path = ROOT) -> tuple[Path, ...]:
    return tuple(sorted((root / "narit_vending" / "static").rglob("*.js")))


def typed_python_files(root: Path = ROOT) -> tuple[str, ...]:
    files: list[Path] = []
    for package in ("domain", "shared"):
        package_root = root / "narit_vending" / package
        files.extend(path for path in package_root.glob("*.py") if path.name != "__init__.py")
    return tuple(path.relative_to(root).as_posix() for path in sorted(files))


def build_gates(*, python: str, node: str | None, full: bool) -> tuple[Gate, ...]:
    gates: list[Gate] = [
        Gate("Whitespace", ("git", "diff", "--check")),
        Gate(
            "Python syntax",
            (
                python,
                "-m",
                "compileall",
                "-q",
                "narit_vending",
                "tests",
                "scripts",
            ),
        ),
    ]
    if node:
        gates.extend(
            Gate("JavaScript syntax: " + path.name, (node, "--check", str(path)))
            for path in javascript_files()
        )
    gates.extend(
        (
            Gate(
                "Python lint",
                (
                    python,
                    "-m",
                    "ruff",
                    "check",
                    "narit_vending/domain",
                    "narit_vending/shared",
                    "narit_vending/release_lifecycle.py",
                    "narit_vending/release_migration.py",
                    "narit_vending/systemd_release_runtime.py",
                    "scripts/activate_release.py",
                    "scripts/plan_release_migration.py",
                    "scripts/rehearse_release_migration.py",
                    "scripts/build_release.py",
                    "scripts/quality_gate.py",
                    "scripts/verify_release.py",
                    "tests/test_architecture_boundaries.py",
                    "tests/test_quality_gate.py",
                    "tests/test_release_artifact.py",
                    "tests/test_release_verification.py",
                    "tests/test_release_lifecycle.py",
                    "tests/test_systemd_release_runtime.py",
                    "tests/test_release_migration_plan.py",
                    "tests/test_release_migration.py",
                    "tests/test_release_runbook.py",
                    "tests/test_operator_manual.py",
                    "tests/test_configuration_manual.py",
                ),
            ),
            Gate("Static typing", (python, "-m", "mypy", *typed_python_files())),
        )
    )
    gates.extend(
        (
            Gate("Configuration", (python, "scripts/validate_config.py")),
            Gate(
                "Dependency boundaries",
                (python, "-m", "pytest", "-q", "tests/test_architecture_boundaries.py"),
            ),
        )
    )
    if full:
        gates.append(Gate("Automated tests", (python, "-m", "pytest", "-q")))
    return tuple(gates)


def run_gate(gate: Gate) -> bool:
    print(f"\n==> {gate.name}", flush=True)
    result = subprocess.run(gate.command, cwd=ROOT, check=False)
    if result.returncode:
        print(f"FAILED: {gate.name} (exit {result.returncode})", flush=True)
        return False
    print(f"PASS: {gate.name}", flush=True)
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run read-only source quality gates without initializing machine hardware."
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip the full suite; architecture boundary tests still run.",
    )
    args = parser.parse_args(argv)

    node = shutil.which("node")
    if node is None:
        print("FAILED: JavaScript syntax gate requires Node.js.", file=sys.stderr)
        return 2
    missing_modules = [name for name in ("ruff", "mypy", "pytest") if importlib.util.find_spec(name) is None]
    if missing_modules:
        print(
            "FAILED: missing development tools: "
            + ", ".join(missing_modules)
            + ". Install requirements-dev.txt.",
            file=sys.stderr,
        )
        return 2

    gates = build_gates(python=sys.executable, node=node, full=not args.quick)
    for gate in gates:
        if not run_gate(gate):
            return 1
    print(f"\nQUALITY GATE PASSED ({len(gates)} checks)", flush=True)
    print("No server, Controller, GPIO, serial transport or motion command was started.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
