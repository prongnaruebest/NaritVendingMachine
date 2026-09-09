from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)
ROOT_FILES = ("README.md", "main.py", "requirements.txt")
TREE_ROOTS = ("narit_vending", "deploy")
SCRIPT_FILES = (
    "scripts/activate_release.py",
    "scripts/plan_release_migration.py",
    "scripts/rehearse_release_migration.py",
    "scripts/setup_pi.sh",
    "scripts/validate_config.py",
    "scripts/verify_release.py",
)


@dataclass(frozen=True)
class ReleaseArtifact:
    release_id: str
    archive_path: Path
    manifest_path: Path


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def release_files(root: Path) -> tuple[Path, ...]:
    candidates = [root / name for name in ROOT_FILES]
    candidates.extend(root / name for name in SCRIPT_FILES)
    for tree_name in TREE_ROOTS:
        candidates.extend(path for path in (root / tree_name).rglob("*") if path.is_file())
    files = {
        path
        for path in candidates
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    }
    return tuple(sorted(files, key=lambda path: path.relative_to(root).as_posix()))


def source_revision(root: Path) -> str:
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def worktree_is_clean(root: Path) -> bool:
    result = subprocess.run(
        ("git", "status", "--porcelain"),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return not result.stdout.strip()


def _manifest(root: Path, files: Iterable[Path], revision: str) -> dict[str, object]:
    entries = []
    for path in files:
        content = path.read_bytes()
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": len(content),
                "sha256": sha256_bytes(content),
            }
        )
    content_id = sha256_bytes(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8"))[:12]
    return {
        "schema_version": 1,
        "release_id": f"{revision[:12]}-{content_id}",
        "source_revision": revision,
        "configuration_included": False,
        "files": entries,
    }


def build_release(root: Path, output_dir: Path, revision: str) -> ReleaseArtifact:
    files = release_files(root)
    if not files:
        raise ValueError("No release files found")
    manifest = _manifest(root, files, revision)
    release_id = str(manifest["release_id"])
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"narit-vending-{release_id}.zip"
    manifest_path = output_dir / f"narit-vending-{release_id}.manifest.json"
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if relative.endswith(".sh") else 0o644) << 16
            archive.writestr(info, path.read_bytes())
        manifest_info = zipfile.ZipInfo("release-manifest.json", FIXED_ZIP_TIME)
        manifest_info.compress_type = zipfile.ZIP_DEFLATED
        manifest_info.external_attr = 0o644 << 16
        archive.writestr(manifest_info, manifest_bytes)

    manifest_path.write_bytes(manifest_bytes)
    return ReleaseArtifact(release_id, archive_path, manifest_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic code-only release artifact.")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output" / "releases")
    args = parser.parse_args()
    if not worktree_is_clean(ROOT):
        print("FAILED: release artifacts require a clean Git worktree.", file=sys.stderr)
        return 2
    artifact = build_release(ROOT, args.output_dir.resolve(), source_revision(ROOT))
    print(f"release_id={artifact.release_id}")
    print(f"archive={artifact.archive_path}")
    print(f"manifest={artifact.manifest_path}")
    print(f"archive_sha256={sha256_bytes(artifact.archive_path.read_bytes())}")
    print("Configuration is intentionally excluded; no deployment or machine command was executed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
