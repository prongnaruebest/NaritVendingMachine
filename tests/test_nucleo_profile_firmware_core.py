from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "firmware" / "nucleo_f439zi" / "profile_core"
HARNESS = ROOT / "tests" / "c_host" / "test_nucleo_profile_buffer.c"


def test_profile_buffer_core_compiles_and_runs_without_hal(tmp_path: Path):
    compiler = shutil.which("gcc")
    if compiler is None:
        pytest.skip("host GCC is unavailable")
    executable = tmp_path / "profile_buffer_test.exe"
    compile_result = subprocess.run(
        [
            compiler,
            "-std=c99",
            "-Wall",
            "-Wextra",
            "-Werror",
            f"-I{CORE}",
            str(CORE / "nucleo_profile_buffer.c"),
            str(HARNESS),
            "-o",
            str(executable),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert compile_result.returncode == 0, compile_result.stdout + compile_result.stderr
    run_result = subprocess.run(
        [str(executable)], capture_output=True, text=True, timeout=10, check=False
    )
    assert run_result.returncode == 0, run_result.stdout + run_result.stderr
    assert "host tests passed" in run_result.stdout


def test_profile_executor_compiles_and_enforces_watchdog_without_hal(tmp_path: Path):
    compiler = shutil.which("gcc")
    if compiler is None:
        pytest.skip("host GCC is unavailable")
    executable = tmp_path / "profile_executor_test.exe"
    sources = [
        CORE / "nucleo_profile_buffer.c",
        CORE / "nucleo_profile_executor.c",
        ROOT / "tests" / "c_host" / "test_nucleo_profile_executor.c",
    ]
    compile_result = subprocess.run(
        [compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", f"-I{CORE}",
         *(str(source) for source in sources), "-o", str(executable)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert compile_result.returncode == 0, compile_result.stdout + compile_result.stderr
    run_result = subprocess.run(
        [str(executable)], capture_output=True, text=True, timeout=10, check=False
    )
    assert run_result.returncode == 0, run_result.stdout + run_result.stderr
    assert "executor host tests passed" in run_result.stdout


def test_pulse_scheduler_updates_rate_without_phase_gap_and_counts_exactly(tmp_path: Path):
    compiler = shutil.which("gcc")
    if compiler is None:
        pytest.skip("host GCC is unavailable")
    executable = tmp_path / "pulse_scheduler_test.exe"
    sources = [
        CORE / "nucleo_profile_buffer.c",
        CORE / "nucleo_profile_executor.c",
        CORE / "nucleo_pulse_scheduler.c",
        ROOT / "tests" / "c_host" / "test_nucleo_pulse_scheduler.c",
    ]
    compile_result = subprocess.run(
        [compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", f"-I{CORE}",
         *(str(source) for source in sources), "-o", str(executable)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert compile_result.returncode == 0, compile_result.stdout + compile_result.stderr
    run_result = subprocess.run(
        [str(executable)], capture_output=True, text=True, timeout=10, check=False
    )
    assert run_result.returncode == 0, run_result.stdout + run_result.stderr
    assert "scheduler host tests passed" in run_result.stdout


def test_profile_core_is_not_connected_to_cubeide_build_yet():
    project_sources = (ROOT / "firmware" / "nucleo_f439zi" / "cubeide" / "Release" / "Core" / "Src" / "subdir.mk").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "nucleo_profile_buffer.c" not in project_sources
    assert "nucleo_profile_executor.c" not in project_sources
    assert "nucleo_pulse_scheduler.c" not in project_sources
