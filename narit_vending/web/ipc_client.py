"""ControllerClient — synchronous IPC client for the web process.

The web process MUST NOT import gpiozero or any motion/GPIO module.
All machine state is obtained by calling the controller process via IPC.

Connection is lazy (first use) and reconnects automatically on timeout or error.
Default timeout is 2.0 seconds.  A ControllerUnavailableError is raised when
the controller cannot be reached so Flask routes can return 503.
"""

from __future__ import annotations

import json
import logging
import socket
import threading
from typing import Any

from narit_vending.shared.commands import CommandEnvelope, CommandResult
from narit_vending.shared.ipc_protocol import (
    METHOD_CONFIG_GET,
    METHOD_CONFIG_SAVE,
    METHOD_PING,
    METHOD_SNAPSHOT,
    METHOD_SUBMIT,
    encode_request,
    ipc_address,
)
from narit_vending.shared.snapshot import MachineSnapshot

_log = logging.getLogger(__name__)

_RECV_BUFSIZE = 65536
_MAX_RECV_TRIES = 64


class ControllerUnavailableError(OSError):
    """Raised when the controller IPC socket cannot be reached."""


class ControllerClient:
    """Thread-safe synchronous IPC client.

    Creates a new socket connection for each call (simple and stateless).
    For polling-heavy workloads, a persistent connection pool could be added
    later without changing the public API.
    """

    def __init__(self, timeout: float = 2.0, addr: dict[str, Any] | None = None) -> None:
        self._timeout = timeout
        self._custom_addr = addr
        self._lock = threading.Lock()

    @property
    def _addr(self) -> dict[str, Any]:
        return self._custom_addr or ipc_address()

    # ── Public API ────────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Return True if the controller is reachable."""
        try:
            result = self._call(METHOD_PING)
            return bool(result.get("pong"))
        except ControllerUnavailableError:
            return False

    def snapshot(self) -> MachineSnapshot:
        """Fetch the current machine snapshot from the controller."""
        try:
            data = self._call(METHOD_SNAPSHOT)
            return MachineSnapshot.from_dict(data)
        except ControllerUnavailableError:
            _log.warning("Controller unreachable — returning offline snapshot")
            return MachineSnapshot.offline()

    def submit_command(self, envelope: CommandEnvelope) -> CommandResult:
        """Submit a CommandEnvelope and return the CommandResult."""
        try:
            data = self._call(METHOD_SUBMIT, envelope.to_dict())
            return CommandResult.from_dict(data)
        except ControllerUnavailableError as exc:
            return CommandResult(
                accepted=False,
                command_id=envelope.command_id,
                state="REJECTED",
                reason=f"Controller unavailable: {exc}",
            )

    def get_effective_config(self) -> dict[str, Any]:
        """Fetch the effective configuration from the controller."""
        try:
            return self._call(METHOD_CONFIG_GET)
        except ControllerUnavailableError:
            return {"error": "Controller unavailable", "ok": False}

    def save_config(self, proposed: dict[str, Any]) -> dict[str, Any]:
        """Send a proposed configuration to the controller for validation and save."""
        try:
            return self._call(METHOD_CONFIG_SAVE, {"config": proposed})
        except ControllerUnavailableError as exc:
            return {"ok": False, "error": str(exc)}

    # ── Low-level transport ────────────────────────────────────────────────────

    def _call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a JSON-RPC request and return the result dict.

        Raises ControllerUnavailableError on connection failure or timeout.
        Raises RuntimeError on JSON-RPC error response.
        """
        request_bytes = encode_request(method, params)
        addr = self._addr
        sock = None

        try:
            if addr["transport"] == "unix":
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(self._timeout)
                sock.connect(addr["path"])
            else:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self._timeout)
                sock.connect((addr["host"], addr["port"]))

            sock.sendall(request_bytes)
            # Read until newline
            buf = b""
            for _ in range(_MAX_RECV_TRIES):
                chunk = sock.recv(_RECV_BUFSIZE)
                if not chunk:
                    break
                buf += chunk
                if b"\n" in buf:
                    break
        except (OSError, socket.timeout, ConnectionRefusedError, FileNotFoundError) as exc:
            raise ControllerUnavailableError(f"Cannot connect/communicate with controller IPC: {exc}") from exc
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass

        if not buf:
            raise ControllerUnavailableError("Controller returned empty response")

        try:
            msg = json.loads(buf.split(b"\n")[0].decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ControllerUnavailableError(f"IPC response parse error: {exc}") from exc

        if "error" in msg:
            err = msg["error"]
            raise RuntimeError(f"Controller RPC error [{err.get('code')}]: {err.get('message')}")

        return msg.get("result", {})
