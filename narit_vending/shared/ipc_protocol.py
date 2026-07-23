"""IPC protocol constants and helpers for JSON-RPC 2.0 over a socket.

Transport: newline-delimited JSON (each message = one line ending with \\n).
Used by both controller (server) and web (client).

Unix socket path (Pi production):
    /run/narit-vending/ctrl.sock   (created by controller at startup)

TCP fallback (Windows dev / testing):
    127.0.0.1:7379  (set NARIT_CTRL_IPC=tcp://127.0.0.1:7379)
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

# ── Transport constants ───────────────────────────────────────────────────────

UNIX_SOCKET_PATH = "/run/narit-vending/ctrl.sock"
TCP_HOST = "127.0.0.1"
TCP_PORT = 7379
ENV_IPC_KEY = "NARIT_CTRL_IPC"  # e.g. "tcp://127.0.0.1:7379" or "unix:///run/..."


def ipc_address() -> dict[str, Any]:
    """Return address info based on NARIT_CTRL_IPC env var or OS default.

    Returns a dict with keys:
        transport: "unix" | "tcp"
        path: str  (unix socket path, for unix)
        host: str  (host, for tcp)
        port: int  (port, for tcp)
    """
    raw = os.environ.get(ENV_IPC_KEY, "")
    if raw.startswith("tcp://"):
        parts = raw[6:].split(":")
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else TCP_PORT
        return {"transport": "tcp", "host": host, "port": port, "path": ""}
    if raw.startswith("unix://"):
        return {"transport": "unix", "path": raw[7:], "host": "", "port": 0}
    # Auto-detect: on Linux/Pi use Unix socket; otherwise fall back to TCP
    if os.name == "nt":  # Windows dev
        return {"transport": "tcp", "host": TCP_HOST, "port": TCP_PORT, "path": ""}
    return {"transport": "unix", "path": UNIX_SOCKET_PATH, "host": "", "port": 0}


# ── IPC Methods ───────────────────────────────────────────────────────────────

METHOD_PING = "health.ping"
METHOD_SNAPSHOT = "status.snapshot"
METHOD_SUBMIT = "command.submit"
METHOD_CMD_STATUS = "command.status"
METHOD_CONFIG_GET = "config.get_effective"
METHOD_CONFIG_SAVE = "config.save"


# ── Encoding / Decoding ───────────────────────────────────────────────────────

def encode_request(method: str, params: dict[str, Any] | None = None, req_id: str | None = None) -> bytes:
    """Encode a JSON-RPC 2.0 request to bytes (newline-terminated)."""
    msg = {
        "jsonrpc": "2.0",
        "id": req_id or uuid.uuid4().hex,
        "method": method,
        "params": params or {},
    }
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def encode_response(result: Any, req_id: str) -> bytes:
    """Encode a JSON-RPC 2.0 success response."""
    msg = {"jsonrpc": "2.0", "id": req_id, "result": result}
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def encode_error(code: int, message: str, req_id: str | None, data: Any = None) -> bytes:
    """Encode a JSON-RPC 2.0 error response."""
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    msg = {"jsonrpc": "2.0", "id": req_id, "error": error}
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


def decode_message(line: bytes) -> dict[str, Any]:
    """Decode a newline-terminated JSON-RPC message."""
    return json.loads(line.decode("utf-8").strip())


# ── JSON-RPC Error Codes ──────────────────────────────────────────────────────

RPC_PARSE_ERROR = -32700
RPC_INVALID_REQUEST = -32600
RPC_METHOD_NOT_FOUND = -32601
RPC_INVALID_PARAMS = -32602
RPC_INTERNAL_ERROR = -32603
RPC_CONTROLLER_BUSY = -32001
RPC_SAFETY_REJECTED = -32002
RPC_CONTROLLER_ERROR = -32003
