from __future__ import annotations

from pathlib import Path

from scripts.quality_gate import build_gates, javascript_files


def test_javascript_inventory_is_sorted_and_scoped_to_static_tree():
    files = javascript_files()

    assert files
    assert files == tuple(sorted(files))
    assert all(path.suffix == ".js" for path in files)
    assert all("narit_vending/static" in path.as_posix() for path in files)


def test_quick_gate_includes_required_non_hardware_checks():
    gates = build_gates(python="python", node="node", full=False)
    names = {gate.name for gate in gates}
    commands = [" ".join(gate.command) for gate in gates]

    assert "Whitespace" in names
    assert "Python syntax" in names
    assert "Configuration" in names
    assert "Dependency boundaries" in names
    assert "Automated tests" not in names
    assert any("node --check" in command for command in commands)
    forbidden_entry_points = ("main.py", "webapp.py", "deploy_to_", "systemctl", "/api/motion")
    assert not any(
        forbidden in command.lower()
        for command in commands
        for forbidden in forbidden_entry_points
    )


def test_full_gate_adds_complete_pytest_suite_last():
    gates = build_gates(python="python", node="node", full=True)

    assert gates[-1].name == "Automated tests"
    assert gates[-1].command == ("python", "-m", "pytest", "-q")


def test_gate_commands_run_from_repository_relative_inputs():
    gates = build_gates(python="python", node="node", full=False)

    for gate in gates:
        for argument in gate.command:
            if argument.endswith(".py") and argument != "tests/test_architecture_boundaries.py":
                assert not Path(argument).is_absolute()
