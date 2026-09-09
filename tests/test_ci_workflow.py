from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "quality-gates.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_quality_workflow_uses_locked_development_dependencies():
    text = _workflow_text()

    assert "requirements-dev.txt" in text
    assert "python scripts/quality_gate.py" in text
    assert 'python-version: "3.12"' in text
    assert 'node-version: "22"' in text


def test_quality_workflow_has_read_only_permissions_and_no_machine_actions():
    text = _workflow_text().lower()

    assert "permissions:\n  contents: read" in text
    forbidden = ("deploy", "ssh", "systemctl", "gpio", "serial", "/api/motion")
    assert not any(token in text for token in forbidden)


def test_quality_workflow_is_bounded_and_cancels_stale_runs():
    text = _workflow_text()

    assert "timeout-minutes: 15" in text
    assert "cancel-in-progress: true" in text
