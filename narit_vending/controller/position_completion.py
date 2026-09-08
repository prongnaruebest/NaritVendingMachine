"""Commissioned PEND completion verification for closed-loop axes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic, sleep
from typing import Any

from ..domain.errors import PositionVerificationError


@dataclass(frozen=True)
class PositionCompletionToken:
    axis: str
    channel_key: str
    initial_transitions: int
    timeout_s: float
    require_transition: bool


class PendCompletionVerifier:
    """Verify X/Y PEND only when the channel is explicitly commissioned."""

    def __init__(self, backend: Any, *, poll_interval_s: float = 0.02) -> None:
        self._backend = backend
        self._poll_interval_s = max(0.005, float(poll_interval_s))

    def begin(self, axis: str) -> PositionCompletionToken | None:
        key = f"{axis.lower()}_pend"
        channel = self._channel(key)
        if channel is None or not bool(channel.get("commissioned", False)):
            return None
        return PositionCompletionToken(
            axis=axis.lower(),
            channel_key=key,
            initial_transitions=int(channel.get("transitions", 0)),
            timeout_s=max(0.05, float(channel.get("settle_timeout_ms", 1000)) / 1000.0),
            require_transition=bool(channel.get("require_transition", False)),
        )

    def verify(
        self,
        token: PositionCompletionToken | None,
        *,
        abort_requested: Callable[[], bool] | None = None,
    ) -> None:
        if token is None:
            return
        deadline = monotonic() + token.timeout_s
        while True:
            if abort_requested is not None and abort_requested():
                raise PositionVerificationError(f"{token.axis}: PEND verification aborted by safety stop")
            if not self._backend.communication_ok:
                raise PositionVerificationError(f"{token.axis}: PiControl communication lost while waiting for PEND")
            channel = self._channel(token.channel_key)
            if channel is None:
                raise PositionVerificationError(f"{token.axis}: commissioned PEND channel is unavailable")
            transitioned = int(channel.get("transitions", 0)) > token.initial_transitions
            if bool(channel.get("active", False)) and (transitioned or not token.require_transition):
                return
            if monotonic() >= deadline:
                requirement = "active transition" if token.require_transition else "active state"
                raise PositionVerificationError(
                    f"{token.axis}: PEND did not reach {requirement} within {token.timeout_s:.3f} seconds"
                )
            sleep(self._poll_interval_s)

    def _channel(self, key: str) -> dict[str, Any] | None:
        expected_axis = key.split("_", 1)[0].lower()
        for channel in self._backend.position_channels():
            if str(channel.get("axis", "")).lower() == expected_axis:
                return dict(channel)
        return None
