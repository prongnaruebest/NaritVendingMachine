from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.package_g491_firmware import CAPABILITIES, package_firmware, sha256_file


def _build_outputs(root: Path) -> Path:
    build_dir = root / "Release"
    build_dir.mkdir()
    (build_dir / "Motion_NaritVending.bin").write_bytes(b"binary-image")
    (build_dir / "Motion_NaritVending.elf").write_bytes(b"elf-image")
    return build_dir


def test_packages_protocol_v4_artifact_with_checksums(tmp_path: Path) -> None:
    build_dir = _build_outputs(tmp_path)

    artifact = package_firmware(build_dir, tmp_path / "artifacts", "a" * 40)
    manifest = json.loads((artifact / "firmware-manifest.json").read_text(encoding="utf-8"))

    assert artifact.name == "v4-aaaaaaaaaaaa"
    assert manifest["board"] == "NUCLEO-G491RE"
    assert manifest["protocol_version"] == 4
    assert manifest["capabilities"] == list(CAPABILITIES)
    assert manifest["flash_performed"] is False
    for entry in manifest["files"]:
        packaged = artifact / entry["path"]
        assert packaged.stat().st_size == entry["size"]
        assert sha256_file(packaged) == entry["sha256"]


def test_rejects_missing_build_output(tmp_path: Path) -> None:
    build_dir = _build_outputs(tmp_path)
    (build_dir / "Motion_NaritVending.bin").unlink()

    with pytest.raises(ValueError, match="missing or empty"):
        package_firmware(build_dir, tmp_path / "artifacts", "b" * 40)


def test_never_overwrites_existing_artifact(tmp_path: Path) -> None:
    build_dir = _build_outputs(tmp_path)
    output = tmp_path / "artifacts"
    package_firmware(build_dir, output, "c" * 40)

    with pytest.raises(ValueError, match="already exists"):
        package_firmware(build_dir, output, "c" * 40)
