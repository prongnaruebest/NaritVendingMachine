import serial
import json
import time
import threading
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class NucleoIOError(Exception):
    pass

class NucleoIOBackend:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.port = config.get("port", "/dev/ttyACM0")
        self.baudrate = int(config.get("baudrate", 115200))
        self.timeout_s = float(config.get("timeout_s", 0.5))
        self.poll_interval_s = float(config.get("poll_interval_s", 1.0))
        self.stale_after_s = float(config.get("stale_after_s", 2.0))
        
        self._serial: Optional[serial.Serial] = None
        self._lock = threading.RLock()
        self._connected = False
        self._last_success_monotonic: Optional[float] = None
        self._last_status: Dict[str, Any] = {}
        self._last_error = "Not connected"
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def communication_ok(self) -> bool:
        with self._lock:
            return bool(
                self._connected
                and self._last_success_monotonic is not None
                and time.monotonic() - self._last_success_monotonic <= self.stale_after_s
            )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, name="nucleo-io-poll", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.poll_interval_s * 3))
        if self._serial and self._serial.is_open:
            self._serial.close()

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            if not self._serial or not self._serial.is_open:
                try:
                    self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout_s)
                    self._serial.write(b"PING\r\n")
                    self._serial.flush()
                except serial.SerialException as exc:
                    with self._lock:
                        self._connected = False
                        self._last_error = str(exc)
                    time.sleep(self.poll_interval_s)
                    continue

            try:
                self._serial.write(b"STATUS\r\n")
                self._serial.flush()
                line = self._serial.readline().decode("utf-8").strip()
                if line:
                    data = json.loads(line)
                    now = time.monotonic()
                    with self._lock:
                        self._connected = True
                        self._last_success_monotonic = now
                        self._last_status = data
                        self._last_error = ""
                else:
                    raise NucleoIOError("Timeout reading from Nucleo")
            except (serial.SerialException, NucleoIOError, json.JSONDecodeError) as exc:
                with self._lock:
                    self._connected = False
                    self._last_error = str(exc)
                try:
                    self._serial.close()
                except Exception:
                    pass
            
            time.sleep(self.poll_interval_s)

    def status_payload(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "enabled": True,
                "communication_ok": self.communication_ok,
                "port": self.port,
                "last_error": self._last_error,
                "data": self._last_status
            }


    def move(self, axis: str, direction: int, steps: int, speed_hz: float) -> bool:
        if not self._serial or not self._serial.is_open:
            return False
        cmd = f"MOVE {axis.upper()} {int(direction)} {int(steps)} {int(speed_hz)}\r\n"
        try:
            with self._lock:
                self._serial.write(cmd.encode('utf-8'))
                self._serial.flush()
            return True
        except serial.SerialException:
            return False

