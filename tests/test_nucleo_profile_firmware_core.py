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
            str(CORE / "nucleo_sha256.c"),
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
        CORE / "nucleo_sha256.c",
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


def test_sensor_stop_supervisor_stops_axes_independently_and_fails_safe(tmp_path: Path):
    compiler = shutil.which("gcc")
    if compiler is None:
        pytest.skip("host GCC is unavailable")
    executable = tmp_path / "sensor_stop_test.exe"
    sources = [
        CORE / "nucleo_sensor_stop.c",
        ROOT / "tests" / "c_host" / "test_nucleo_sensor_stop.c",
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
    assert "sensor_stop host tests passed" in run_result.stdout


def test_pulse_scheduler_updates_rate_without_phase_gap_and_counts_exactly(tmp_path: Path):
    compiler = shutil.which("gcc")
    if compiler is None:
        pytest.skip("host GCC is unavailable")
    executable = tmp_path / "pulse_scheduler_test.exe"
    sources = [
        CORE / "nucleo_sha256.c",
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


def test_timer_adapter_computes_registers_and_updates_atomically(tmp_path: Path):
    compiler = shutil.which("gcc")
    if compiler is None:
        pytest.skip("host GCC is unavailable")
    executable = tmp_path / "timer_adapter_test.exe"
    sources = [
        CORE / "nucleo_timer_adapter.c",
        ROOT / "tests" / "c_host" / "test_nucleo_timer_adapter.c",
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
    assert "timer_adapter host tests passed" in run_result.stdout


def test_shared_tim1_compare_adapter_keeps_xy_channels_independent(tmp_path: Path):
    compiler = shutil.which("gcc")
    if compiler is None:
        pytest.skip("host GCC is unavailable")
    executable = tmp_path / "compare_adapter_test.exe"
    sources = [
        CORE / "nucleo_compare_adapter.c",
        ROOT / "tests" / "c_host" / "test_nucleo_compare_adapter.c",
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
    assert "compare_adapter host tests passed" in run_result.stdout


def test_candidate_hal_port_maps_shared_tim1_channels_without_cross_stop(tmp_path: Path):
    compiler = shutil.which("gcc")
    if compiler is None:
        pytest.skip("host GCC is unavailable")
    candidate = ROOT / "firmware" / "nucleo_f439zi" / "profile_hal_candidate"
    shim = ROOT / "tests" / "c_host" / "hal_shim"
    executable = tmp_path / "profile_hal_port_test.exe"
    sources = [
        CORE / "nucleo_compare_adapter.c",
        candidate / "nucleo_profile_hal_port.c",
        ROOT / "tests" / "c_host" / "test_nucleo_profile_hal_port.c",
    ]
    compile_result = subprocess.run(
        [compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", f"-I{shim}",
         f"-I{CORE}", f"-I{candidate}", *(str(source) for source in sources),
         "-o", str(executable)], capture_output=True, text=True, timeout=30, check=False,
    )
    assert compile_result.returncode == 0, compile_result.stdout + compile_result.stderr
    run_result = subprocess.run(
        [str(executable)], capture_output=True, text=True, timeout=10, check=False
    )
    assert run_result.returncode == 0, run_result.stdout + run_result.stderr
    assert "hal_port host tests passed" in run_result.stdout


@pytest.mark.parametrize("feature_enabled", [False, True])
def test_profile_facade_compiles_with_feature_off_and_on(tmp_path: Path, feature_enabled: bool):
    compiler = shutil.which("gcc")
    if compiler is None:
        pytest.skip("host GCC is unavailable")
    candidate = ROOT / "firmware" / "nucleo_f439zi" / "profile_hal_candidate"
    shim = ROOT / "tests" / "c_host" / "hal_shim"
    executable = tmp_path / f"profile_facade_{int(feature_enabled)}.exe"
    sources = [
        CORE / "nucleo_sha256.c", CORE / "nucleo_profile_buffer.c", CORE / "nucleo_profile_executor.c",
        CORE / "nucleo_pulse_scheduler.c", CORE / "nucleo_compare_adapter.c",
        CORE / "nucleo_sensor_stop.c",
        candidate / "nucleo_profile_hal_port.c", candidate / "nucleo_profile_facade.c",
        ROOT / "tests" / "c_host" / "test_nucleo_profile_facade.c",
    ]
    flags = [f"-DNUCLEO_XY_PROFILE_FEATURE_ENABLED={int(feature_enabled)}"]
    compile_result = subprocess.run(
        [compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", *flags,
         f"-I{shim}", f"-I{CORE}", f"-I{candidate}",
         *(str(source) for source in sources), "-o", str(executable)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert compile_result.returncode == 0, compile_result.stdout + compile_result.stderr
    run_result = subprocess.run(
        [str(executable)], capture_output=True, text=True, timeout=10, check=False
    )
    assert run_result.returncode == 0, run_result.stdout + run_result.stderr
    assert "facade host tests passed" in run_result.stdout


@pytest.mark.parametrize("feature_enabled", [False, True])
def test_profile_dispatcher_is_bounded_and_feature_gated(tmp_path: Path, feature_enabled: bool):
    compiler = shutil.which("gcc")
    if compiler is None:
        pytest.skip("host GCC is unavailable")
    candidate = ROOT / "firmware" / "nucleo_f439zi" / "profile_hal_candidate"
    shim = ROOT / "tests" / "c_host" / "hal_shim"
    # Avoid Windows installer-detection heuristics on executable names.
    executable = tmp_path / f"profile_rx_{int(feature_enabled)}.exe"
    sources = [
        CORE / "nucleo_sha256.c", CORE / "nucleo_profile_buffer.c", CORE / "nucleo_profile_executor.c",
        CORE / "nucleo_pulse_scheduler.c", CORE / "nucleo_compare_adapter.c",
        CORE / "nucleo_sensor_stop.c", candidate / "nucleo_profile_hal_port.c",
        candidate / "nucleo_profile_facade.c", candidate / "nucleo_profile_dispatcher.c",
        ROOT / "tests" / "c_host" / "test_nucleo_profile_dispatcher.c",
    ]
    compile_result = subprocess.run(
        [compiler, "-std=c99", "-Wall", "-Wextra", "-Werror",
         f"-DNUCLEO_XY_PROFILE_FEATURE_ENABLED={int(feature_enabled)}",
         f"-I{shim}", f"-I{CORE}", f"-I{candidate}",
         *(str(source) for source in sources), "-o", str(executable)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert compile_result.returncode == 0, compile_result.stdout + compile_result.stderr
    run_result = subprocess.run(
        [str(executable)], capture_output=True, text=True, timeout=10, check=False
    )
    assert run_result.returncode == 0, run_result.stdout + run_result.stderr
    assert "dispatcher host tests passed" in run_result.stdout


def test_profile_core_is_not_connected_to_cubeide_build_yet():
    project_sources = (ROOT / "firmware" / "nucleo_f439zi" / "cubeide" / "Release" / "Core" / "Src" / "subdir.mk").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "nucleo_profile_buffer.c" not in project_sources
    assert "nucleo_profile_executor.c" not in project_sources
    assert "nucleo_pulse_scheduler.c" not in project_sources
    assert "nucleo_timer_adapter.c" not in project_sources
    assert "nucleo_compare_adapter.c" not in project_sources
    assert "nucleo_profile_hal_port.c" not in project_sources
    assert "nucleo_profile_facade.c" not in project_sources
    assert "nucleo_profile_dispatcher.c" not in project_sources
    assert "nucleo_sensor_stop.c" not in project_sources
    assert "nucleo_sha256.c" not in project_sources
