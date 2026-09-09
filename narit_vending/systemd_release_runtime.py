from __future__ import annotations

import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path


CommandRunner = Callable[[Sequence[str]], int]
HealthProbe = Callable[[str, float], bool]
CandidateValidator = Callable[[Path], None]
CurrentSwitcher = Callable[[Path, Path], None]
Sleeper = Callable[[float], None]


def run_command(command: Sequence[str]) -> int:
    return subprocess.run(tuple(command), check=False).returncode


def probe_http(url: str, timeout: float) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError):
        return False


def switch_current_symlink(current_link: Path, release_dir: Path) -> None:
    if os.name != "posix":
        raise RuntimeError("Release symlink switching is supported only on POSIX hosts")
    current_link = current_link.absolute()
    release_dir = release_dir.resolve(strict=True)
    if current_link.exists() and not current_link.is_symlink():
        raise RuntimeError(f"Current release path is not a symlink: {current_link}")
    current_link.parent.mkdir(parents=True, exist_ok=True)
    temporary = current_link.with_name(f".{current_link.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.symlink_to(release_dir, target_is_directory=True)
        os.replace(temporary, current_link)
    finally:
        if temporary.is_symlink():
            temporary.unlink()


class SystemdReleaseRuntime:
    def __init__(
        self,
        *,
        current_link: Path,
        controller_service: str,
        web_service: str,
        live_url: str,
        validator: CandidateValidator,
        command_runner: CommandRunner = run_command,
        health_probe: HealthProbe = probe_http,
        current_switcher: CurrentSwitcher = switch_current_symlink,
        sleeper: Sleeper = time.sleep,
        health_attempts: int = 10,
        health_timeout: float = 2.0,
        health_interval: float = 1.0,
    ) -> None:
        if health_attempts < 1:
            raise ValueError("health_attempts must be positive")
        self.current_link = current_link
        self.controller_service = controller_service
        self.web_service = web_service
        self.live_url = live_url
        self.validator = validator
        self.command_runner = command_runner
        self.health_probe = health_probe
        self.current_switcher = current_switcher
        self.sleeper = sleeper
        self.health_attempts = health_attempts
        self.health_timeout = health_timeout
        self.health_interval = health_interval

    def validate(self, release_dir: Path) -> None:
        self.validator(release_dir)

    def _command(self, *command: str) -> None:
        return_code = self.command_runner(command)
        if return_code:
            raise RuntimeError(f"Command failed ({return_code}): {' '.join(command)}")

    def stop(self) -> None:
        self._command("systemctl", "stop", self.web_service, self.controller_service)

    def start(self, release_dir: Path) -> None:
        self.current_switcher(self.current_link, release_dir)
        self._command("systemctl", "start", self.controller_service, self.web_service)

    def healthy(self) -> bool:
        if self.command_runner(("systemctl", "is-active", "--quiet", self.controller_service)):
            return False
        if self.command_runner(("systemctl", "is-active", "--quiet", self.web_service)):
            return False
        for attempt in range(self.health_attempts):
            if self.health_probe(self.live_url, self.health_timeout):
                return True
            if attempt + 1 < self.health_attempts:
                self.sleeper(self.health_interval)
        return False
