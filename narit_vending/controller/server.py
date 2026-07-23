"""IPC server — asyncio JSON-RPC server for the controller process.

Listens on a Unix domain socket (Pi/Linux) or TCP localhost (Windows/dev).
Each connected client gets its own reader/writer pair; requests are dispatched
to a thread pool so blocking motion commands don't stall the event loop.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import socket
from pathlib import Path
from typing import Any, Callable

from narit_vending.shared.ipc_protocol import (
    METHOD_CMD_STATUS,
    METHOD_CONFIG_GET,
    METHOD_CONFIG_SAVE,
    METHOD_PING,
    METHOD_SNAPSHOT,
    METHOD_SUBMIT,
    RPC_INTERNAL_ERROR,
    RPC_INVALID_PARAMS,
    RPC_METHOD_NOT_FOUND,
    decode_message,
    encode_error,
    encode_response,
    ipc_address,
)

_log = logging.getLogger(__name__)

# Thread pool for blocking motion handlers (home, move etc.)
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="ctrl-ipc")


class IPCServer:
    """Asyncio IPC server wrapping the controller's command bus and snapshot."""

    def __init__(
        self,
        command_bus: Any,
        snapshot_fn: Callable[[], Any],
        config_fn: Callable[[], dict],
        save_config_fn: Callable[[dict], dict],
    ) -> None:
        self._bus = command_bus
        self._snapshot_fn = snapshot_fn
        self._config_fn = config_fn
        self._save_config_fn = save_config_fn
        self._server: asyncio.AbstractServer | None = None
        self._addr = ipc_address()

    async def start(self) -> None:
        addr = self._addr
        if addr["transport"] == "unix":
            path = addr["path"]
            # Ensure runtime directory exists
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            # Remove stale socket
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            self._server = await asyncio.start_unix_server(self._handle, path=path)
            _log.info("IPC Unix socket: %s", path)
        else:
            host, port = addr["host"], addr["port"]
            self._server = await asyncio.start_server(self._handle, host=host, port=port)
            _log.info("IPC TCP: %s:%d", host, port)

        # Signal sd_notify READY=1 if available
        _sd_notify("READY=1")

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername") or "unix"
        _log.debug("IPC client connected: %s", peer)
        try:
            while True:
                try:
                    line = await asyncio.wait_for(reader.readline(), timeout=30.0)
                except asyncio.TimeoutError:
                    _log.debug("IPC client idle timeout: %s", peer)
                    break
                if not line:
                    break
                await self._dispatch(line.strip(), writer)
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            _log.debug("IPC client disconnected: %s", peer)

    async def _dispatch(self, line: bytes, writer: asyncio.StreamWriter) -> None:
        req_id: str | None = None
        try:
            msg = decode_message(line)
            req_id = msg.get("id")
            method = str(msg.get("method", ""))
            params = dict(msg.get("params") or {})
        except Exception as exc:
            _log.warning("IPC parse error: %s", exc)
            writer.write(encode_error(-32700, "Parse error", None))
            await writer.drain()
            return

        try:
            result = await self._route(method, params)
            writer.write(encode_response(result, req_id or ""))
        except MethodNotFoundError as exc:
            writer.write(encode_error(RPC_METHOD_NOT_FOUND, str(exc), req_id))
        except InvalidParamsError as exc:
            writer.write(encode_error(RPC_INVALID_PARAMS, str(exc), req_id))
        except Exception as exc:
            _log.exception("IPC handler error for method %s: %s", method, exc)
            writer.write(encode_error(RPC_INTERNAL_ERROR, f"Internal error: {exc}", req_id))
        await writer.drain()

    async def _route(self, method: str, params: dict[str, Any]) -> Any:
        loop = asyncio.get_event_loop()

        if method == METHOD_PING:
            return {"pong": True}

        if method == METHOD_SNAPSHOT:
            snapshot = self._snapshot_fn()
            return snapshot.to_dict()

        if method == METHOD_SUBMIT:
            from narit_vending.shared.commands import CommandEnvelope
            try:
                envelope = CommandEnvelope.from_dict(params)
            except (KeyError, TypeError, ValueError) as exc:
                raise InvalidParamsError(f"Invalid CommandEnvelope: {exc}") from exc
            # Run blocking command in thread pool
            result = await loop.run_in_executor(_EXECUTOR, self._bus.submit, envelope)
            return result.to_dict()

        if method == METHOD_CMD_STATUS:
            # Future: look up command by ID from repository
            return {"status": "not_implemented"}

        if method == METHOD_CONFIG_GET:
            return await loop.run_in_executor(_EXECUTOR, self._config_fn)

        if method == METHOD_CONFIG_SAVE:
            proposed = params.get("config", {})
            return await loop.run_in_executor(_EXECUTOR, self._save_config_fn, proposed)

        raise MethodNotFoundError(f"Unknown method: {method!r}")


class MethodNotFoundError(Exception):
    pass


class InvalidParamsError(Exception):
    pass


def _sd_notify(state: str) -> None:
    """Send sd_notify message if NOTIFY_SOCKET is set (systemd Type=notify)."""
    notify_socket = os.environ.get("NOTIFY_SOCKET", "")
    if not notify_socket:
        return
    try:
        if notify_socket.startswith("@"):
            notify_socket = "\0" + notify_socket[1:]
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(notify_socket)
            sock.send(state.encode())
        _log.debug("sd_notify: %s", state)
    except Exception as exc:
        _log.warning("sd_notify failed: %s", exc)
