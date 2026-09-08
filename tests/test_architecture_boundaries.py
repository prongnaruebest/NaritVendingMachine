from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_domain_has_no_framework_hardware_or_persistence_dependencies() -> None:
    forbidden_roots = {"flask", "gpiozero", "serial", "pymodbus", "sqlite3"}
    for path in (ROOT / "narit_vending" / "domain").glob("*.py"):
        imported = imported_modules(path)
        assert not ({name.split(".", 1)[0] for name in imported} & forbidden_roots), path


def test_deployed_web_layer_does_not_import_hardware_owners() -> None:
    forbidden = {
        "narit_vending.motion",
        "narit_vending.nucleo",
        "narit_vending.iriv_io",
        "narit_vending.picontrol_io",
        "gpiozero",
    }
    for path in (ROOT / "narit_vending" / "web").rglob("*.py"):
        assert not (imported_modules(path) & forbidden), path


def test_legacy_motion_imports_still_resolve_to_domain_errors() -> None:
    from narit_vending.domain.errors import MotionError as DomainMotionError
    from narit_vending.motion import MotionError as LegacyMotionError

    assert LegacyMotionError is DomainMotionError


def test_web_hardware_config_loader_is_dependency_neutral() -> None:
    web_main = (ROOT / "narit_vending" / "web" / "__main__.py").read_text(encoding="utf-8")
    assert "from narit_vending.config_foundation import load_hardware_payload" in web_main
    assert "from narit_vending.motion import load_hardware_config" not in web_main
