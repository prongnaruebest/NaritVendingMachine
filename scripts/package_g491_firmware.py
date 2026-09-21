from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "Motion_NaritVending" / "Motion_NaritVending"
DEFAULT_BUILD_DIR = PROJECT / "Release"
BOARD = "NUCLEO-G491RE"
PROTOCOL_VERSION = 4
CAPABILITIES = (
    "continuous_profile",
    "seven_segment_s_curve",
    "buffered_segments",
    "profile_sequence",
    "profile_telemetry",
    "dynamic_motion",
    # The Controller must see this capability before it may leave the
    # watchdog-safety quarantine and route X/Y moves to the dynamic planner.
    "dynamic_watchdog_heartbeat",
    "terminal_rate_config",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def package_firmware(
    build_dir: Path,
    output_root: Path,
    source_revision: str,
) -> Path:
    """Copy an already-built image into an immutable, checksummed artifact directory."""

    inputs = {
        "nucleo_g491re_protocol_v4.bin": build_dir / "Motion_NaritVending.bin",
        "nucleo_g491re_protocol_v4.elf": build_dir / "Motion_NaritVending.elf",
    }
    for path in inputs.values():
        if not path.is_file() or path.stat().st_size <= 0:
            raise ValueError(f"Firmware build output is missing or empty: {path}")
    binary = inputs["nucleo_g491re_protocol_v4.bin"]
    executable = inputs["nucleo_g491re_protocol_v4.elf"]
    if binary.stat().st_mtime_ns < executable.stat().st_mtime_ns:
        raise ValueError(
            "Firmware BIN is older than ELF; regenerate BIN from this ELF before packaging"
        )

    revision = source_revision.strip().lower()
    if len(revision) < 12 or any(character not in "0123456789abcdef" for character in revision):
        raise ValueError("source_revision must be a hexadecimal Git revision")
    artifact_dir = output_root / f"v4-{revision[:12]}"
    if artifact_dir.exists():
        raise ValueError(f"Firmware artifact already exists: {artifact_dir}")
    artifact_dir.mkdir(parents=True)

    entries: list[dict[str, object]] = []
    for destination_name, source in inputs.items():
        destination = artifact_dir / destination_name
        shutil.copyfile(source, destination)
        entries.append(
            {
                "path": destination.name,
                "size": destination.stat().st_size,
                "sha256": sha256_file(destination),
            }
        )

    manifest = {
        "schema_version": 1,
        "board": BOARD,
        "protocol_version": PROTOCOL_VERSION,
        "capabilities": list(CAPABILITIES),
        "source_revision": revision,
        "build_configuration": "Release",
        "files": entries,
        "flash_performed": False,
    }
    (artifact_dir / "firmware-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (artifact_dir / "SHA256SUMS.txt").write_text(
        "".join(f"{entry['sha256']}  {entry['path']}\n" for entry in entries),
        encoding="ascii",
    )
    return artifact_dir


def _git_output(*args: str) -> str:
    result = subprocess.run(
        ("git", *args), cwd=ROOT, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Package a built G491RE protocol-v4 image without flashing hardware."
    )
    parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD_DIR)
    parser.add_argument(
        "--output-root", type=Path, default=ROOT / "output" / "firmware"
    )
    args = parser.parse_args()
    if _git_output("status", "--porcelain"):
        print("FAILED: firmware artifacts require a clean Git worktree.", file=sys.stderr)
        return 2
    try:
        destination = package_firmware(
            args.build_dir.resolve(), args.output_root.resolve(), _git_output("rev-parse", "HEAD")
        )
    except (OSError, ValueError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"artifact={destination}")
    print(f"board={BOARD}")
    print(f"protocol={PROTOCOL_VERSION}")
    print("Firmware was packaged but not flashed; no machine command was issued.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
