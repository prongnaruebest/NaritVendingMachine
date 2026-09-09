from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.build_release import build_release
from scripts.verify_release import (
    ReleaseVerificationError,
    stage_release,
    verify_release,
    verify_staged_release,
)

from .test_release_artifact import _project


def _artifact(tmp_path: Path):
    _project(tmp_path)
    return build_release(tmp_path, tmp_path / "artifacts", "c" * 40)


def test_verifier_accepts_matching_code_only_release(tmp_path: Path):
    artifact = _artifact(tmp_path)

    manifest = verify_release(artifact.archive_path, artifact.manifest_path)

    assert manifest["release_id"] == artifact.release_id
    assert manifest["configuration_included"] is False


def test_verifier_rejects_external_manifest_change(tmp_path: Path):
    artifact = _artifact(tmp_path)
    manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
    manifest["source_revision"] = "tampered"
    artifact.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ReleaseVerificationError, match="manifests differ"):
        verify_release(artifact.archive_path, artifact.manifest_path)


def test_verifier_rejects_duplicate_archive_paths(tmp_path: Path):
    artifact = _artifact(tmp_path)
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(artifact.archive_path, "a") as archive:
            archive.writestr("main.py", b"tampered")

    with pytest.raises(ReleaseVerificationError, match="duplicate paths"):
        verify_release(artifact.archive_path, artifact.manifest_path)


def test_verifier_rejects_path_traversal_before_extraction(tmp_path: Path):
    artifact = _artifact(tmp_path)
    manifest_bytes = artifact.manifest_path.read_bytes()
    unsafe_archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(unsafe_archive, "w") as archive:
        archive.writestr("../escape.py", b"unsafe")
        archive.writestr("release-manifest.json", manifest_bytes)

    with pytest.raises(ReleaseVerificationError, match="unsafe path"):
        verify_release(unsafe_archive, artifact.manifest_path)


def test_stage_release_extracts_and_reverifies_without_activation(tmp_path: Path):
    artifact = _artifact(tmp_path)
    stage_root = tmp_path / "staging"

    staged = stage_release(artifact.archive_path, artifact.manifest_path, stage_root)
    manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))

    assert staged.parent == stage_root.resolve()
    assert (staged / "release-manifest.json").is_file()
    assert not (staged / "machine_config.json").exists()
    verify_staged_release(staged, manifest)


def test_stage_release_never_overwrites_existing_release(tmp_path: Path):
    artifact = _artifact(tmp_path)
    stage_root = tmp_path / "staging"
    staged = stage_release(artifact.archive_path, artifact.manifest_path, stage_root)
    marker = staged / "operator-data.txt"
    marker.write_text("preserve", encoding="utf-8")

    with pytest.raises(ReleaseVerificationError, match="already staged"):
        stage_release(artifact.archive_path, artifact.manifest_path, stage_root)

    assert marker.read_text(encoding="utf-8") == "preserve"


def test_staged_verification_detects_post_extraction_tamper(tmp_path: Path):
    artifact = _artifact(tmp_path)
    staged = stage_release(artifact.archive_path, artifact.manifest_path, tmp_path / "staging")
    manifest = json.loads(artifact.manifest_path.read_text(encoding="utf-8"))
    (staged / "main.py").write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ReleaseVerificationError, match="Staged checksum mismatch"):
        verify_staged_release(staged, manifest)
