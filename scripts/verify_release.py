from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


EMBEDDED_MANIFEST = "release-manifest.json"
REQUIRED_FILES = {
    "README.md",
    "main.py",
    "requirements.txt",
    "narit_vending/__init__.py",
    "scripts/setup_pi.sh",
    "scripts/validate_config.py",
}
RELEASE_ID_PATTERN = re.compile(r"^[0-9a-f]{12}-[0-9a-f]{12}$")


class ReleaseVerificationError(ValueError):
    pass


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _load_manifest(content: bytes, source: str) -> dict[str, Any]:
    try:
        data = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseVerificationError(f"Invalid manifest: {source}") from exc
    if not isinstance(data, dict):
        raise ReleaseVerificationError(f"Manifest must be an object: {source}")
    return data


def _safe_member_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and "\\" not in name


def _is_configuration(name: str) -> bool:
    basename = PurePosixPath(name).name.lower()
    return basename.startswith("machine_config") or basename.startswith("hardware_config")


def verify_release(archive_path: Path, manifest_path: Path) -> dict[str, Any]:
    external_bytes = manifest_path.read_bytes()
    external = _load_manifest(external_bytes, str(manifest_path))
    if external.get("schema_version") != 1:
        raise ReleaseVerificationError("Unsupported release manifest schema")
    if external.get("configuration_included") is not False:
        raise ReleaseVerificationError("Release must explicitly exclude machine configuration")

    try:
        archive = zipfile.ZipFile(archive_path)
    except zipfile.BadZipFile as exc:
        raise ReleaseVerificationError("Release archive is not a valid ZIP") from exc

    with archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ReleaseVerificationError("Release archive contains duplicate paths")
        if any(not _safe_member_name(name) for name in names):
            raise ReleaseVerificationError("Release archive contains an unsafe path")
        if EMBEDDED_MANIFEST not in names:
            raise ReleaseVerificationError("Embedded release manifest is missing")
        if archive.read(EMBEDDED_MANIFEST) != external_bytes:
            raise ReleaseVerificationError("Embedded and external manifests differ")

        entries = external.get("files")
        if not isinstance(entries, list):
            raise ReleaseVerificationError("Manifest file list is missing")
        expected_names: set[str] = set()
        for raw_entry in entries:
            if not isinstance(raw_entry, dict):
                raise ReleaseVerificationError("Manifest contains an invalid file entry")
            name = raw_entry.get("path")
            if not isinstance(name, str) or not _safe_member_name(name):
                raise ReleaseVerificationError("Manifest contains an unsafe path")
            if name in expected_names:
                raise ReleaseVerificationError("Manifest contains a duplicate path")
            expected_names.add(name)
            if _is_configuration(name):
                raise ReleaseVerificationError("Release contains machine configuration")
            try:
                content = archive.read(name)
            except KeyError as exc:
                raise ReleaseVerificationError(f"Manifest file is missing: {name}") from exc
            if raw_entry.get("size") != len(content):
                raise ReleaseVerificationError(f"Size mismatch: {name}")
            if raw_entry.get("sha256") != _sha256(content):
                raise ReleaseVerificationError(f"Checksum mismatch: {name}")

        archived_files = set(names) - {EMBEDDED_MANIFEST}
        if archived_files != expected_names:
            raise ReleaseVerificationError("Archive and manifest file inventories differ")
        missing = REQUIRED_FILES - expected_names
        if missing:
            raise ReleaseVerificationError("Required release files are missing: " + ", ".join(sorted(missing)))
    return external


def verify_staged_release(stage_dir: Path, manifest: dict[str, Any]) -> None:
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise ReleaseVerificationError("Manifest file list is missing")
    expected = {str(entry["path"]) for entry in entries}
    actual = {
        path.relative_to(stage_dir).as_posix()
        for path in stage_dir.rglob("*")
        if path.is_file() and path.name != EMBEDDED_MANIFEST
    }
    if actual != expected:
        raise ReleaseVerificationError("Staged and manifest file inventories differ")
    for entry in entries:
        path = stage_dir / str(entry["path"])
        content = path.read_bytes()
        if len(content) != entry["size"] or _sha256(content) != entry["sha256"]:
            raise ReleaseVerificationError(f"Staged checksum mismatch: {entry['path']}")


def stage_release(archive_path: Path, manifest_path: Path, staging_root: Path) -> Path:
    manifest = verify_release(archive_path, manifest_path)
    release_id = manifest.get("release_id")
    if not isinstance(release_id, str) or RELEASE_ID_PATTERN.fullmatch(release_id) is None:
        raise ReleaseVerificationError("Release ID is invalid")

    root = staging_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = root / release_id
    if destination.exists():
        raise ReleaseVerificationError(f"Release is already staged: {release_id}")
    temporary = root / f".{release_id}.preparing-{uuid.uuid4().hex}"
    temporary.mkdir()
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                target = temporary / PurePosixPath(info.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info.filename))
                target.chmod(0o755 if info.filename.endswith(".sh") else 0o644)
        verify_staged_release(temporary, manifest)
        temporary.rename(destination)
    except Exception:
        if temporary.parent == root and temporary.name.startswith(f".{release_id}.preparing-"):
            shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def validate_staged_python(stage_dir: Path) -> int:
    checked = 0
    for path in sorted(stage_dir.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        try:
            compile(source, path.relative_to(stage_dir).as_posix(), "exec")
        except (SyntaxError, UnicodeDecodeError) as exc:
            raise ReleaseVerificationError(f"Staged Python validation failed: {path.name}: {exc}") from exc
        checked += 1
    if checked == 0:
        raise ReleaseVerificationError("Staged release contains no Python source")
    return checked


def validate_staged_configuration(
    stage_dir: Path,
    machine_config: Path,
    hardware_config: Path,
    *,
    python: str = sys.executable,
) -> dict[str, Any]:
    validator = stage_dir / "scripts" / "validate_config.py"
    if not validator.is_file():
        raise ReleaseVerificationError("Staged configuration validator is missing")
    command = (
        python,
        str(validator),
        "--machine",
        str(machine_config.resolve()),
        "--hardware",
        str(hardware_config.resolve()),
    )
    result = subprocess.run(
        command,
        cwd=stage_dir,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise ReleaseVerificationError(f"Staged configuration validation failed: {detail}")
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ReleaseVerificationError("Staged configuration validator returned invalid JSON") from exc
    if not isinstance(report, dict) or report.get("valid") is not True:
        raise ReleaseVerificationError("Staged configuration report is not valid")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a release artifact without extracting or activating it.")
    parser.add_argument("archive", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--stage-root",
        type=Path,
        help="Verify, extract and re-verify under this root without activating the release.",
    )
    parser.add_argument("--machine-config", type=Path)
    parser.add_argument("--hardware-config", type=Path)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()
    if bool(args.machine_config) != bool(args.hardware_config):
        parser.error("--machine-config and --hardware-config must be supplied together")
    if args.machine_config and not args.stage_root:
        parser.error("configuration compatibility checks require --stage-root")
    try:
        archive_path = args.archive.resolve()
        manifest_path = args.manifest.resolve()
        manifest = verify_release(archive_path, manifest_path)
        staged_path = (
            stage_release(archive_path, manifest_path, args.stage_root.resolve()) if args.stage_root else None
        )
        checked_python = validate_staged_python(staged_path) if staged_path else 0
        config_report = (
            validate_staged_configuration(
                staged_path,
                args.machine_config,
                args.hardware_config,
                python=args.python,
            )
            if staged_path and args.machine_config and args.hardware_config
            else None
        )
    except (OSError, ReleaseVerificationError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"VERIFIED: {manifest['release_id']}")
    print(f"files={len(manifest['files'])}")
    if staged_path:
        print(f"staged={staged_path}")
        print(f"python_files_checked={checked_python}")
        if config_report:
            print(f"configuration_revision={config_report.get('revision', 'unknown')}")
        print("Release was staged but not activated; no service or machine command was issued.")
    else:
        print("No files were extracted, no service was restarted and no machine command was issued.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
