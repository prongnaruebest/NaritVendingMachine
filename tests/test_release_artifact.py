from __future__ import annotations

import json
import zipfile
from pathlib import Path

from scripts.build_release import build_release, release_files, sha256_bytes, worktree_is_clean


def _project(root: Path) -> None:
    files = {
        "README.md": "readme\n",
        "main.py": "print('safe')\n",
        "requirements.txt": "Flask\n",
        "machine_config.json": "{\"do_not_package\": true}\n",
        "hardware_config.iriv.json": "{\"do_not_package\": true}\n",
        "narit_vending/__init__.py": "\n",
        "narit_vending/app.py": "VALUE = 1\n",
        "narit_vending/__pycache__/app.pyc": "cache",
        "deploy/service.service": "[Service]\n",
        "scripts/setup_pi.sh": "#!/bin/sh\n",
        "scripts/validate_config.py": "VALID = True\n",
        "scripts/deploy_to_iriv.ps1": "must not ship\n",
    }
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def test_release_inventory_excludes_live_configuration_cache_and_deploy_client(tmp_path: Path):
    _project(tmp_path)

    names = {path.relative_to(tmp_path).as_posix() for path in release_files(tmp_path)}

    assert "narit_vending/app.py" in names
    assert "scripts/setup_pi.sh" in names
    assert "machine_config.json" not in names
    assert "hardware_config.iriv.json" not in names
    assert "narit_vending/__pycache__/app.pyc" not in names
    assert "scripts/deploy_to_iriv.ps1" not in names


def test_release_contains_manifest_and_verified_file_hashes(tmp_path: Path):
    _project(tmp_path)
    output = tmp_path / "artifacts"

    artifact = build_release(tmp_path, output, "a" * 40)
    manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))

    assert manifest["configuration_included"] is False
    assert manifest["source_revision"] == "a" * 40
    with zipfile.ZipFile(artifact.archive_path) as archive:
        assert "release-manifest.json" in archive.namelist()
        for entry in manifest["files"]:
            assert sha256_bytes(archive.read(entry["path"])) == entry["sha256"]


def test_release_archive_is_deterministic(tmp_path: Path):
    _project(tmp_path)

    first = build_release(tmp_path, tmp_path / "first", "b" * 40)
    second = build_release(tmp_path, tmp_path / "second", "b" * 40)

    assert first.release_id == second.release_id
    assert sha256_bytes(first.archive_path.read_bytes()) == sha256_bytes(second.archive_path.read_bytes())


def test_worktree_clean_check_includes_untracked_files(tmp_path: Path):
    import subprocess

    subprocess.run(("git", "init", "-q"), cwd=tmp_path, check=True)
    assert worktree_is_clean(tmp_path)

    (tmp_path / "untracked.txt").write_text("not releasable\n", encoding="utf-8")

    assert not worktree_is_clean(tmp_path)
