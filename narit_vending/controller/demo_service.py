"""Controller-owned, bounded slot-sampling demo with persistent audit results."""

from __future__ import annotations

import csv
import io
import json
import random
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..persistence.demo_schema import DEMO_MIGRATIONS
from ..persistence.sqlite_migrations import SQLiteMigrator


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DemoSamplingService:
    def __init__(self, motion_service: Any, database_path: str | Path) -> None:
        self.motion = motion_service
        self.database_path = Path(database_path)
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._pause_requested = False
        self._config: dict[str, Any] = {}
        self._validation_hash = ""
        self._arm_token: str | None = None
        self._arm_until = 0.0
        self._state = "IDLE"
        self._session_id: str | None = None
        self._started_at: str | None = None
        self._ended_at: str | None = None
        self._current_slot: str | None = None
        self._next_slot: str | None = None
        self._cycle = 0
        self._counters = {key: 0 for key in ("requested", "attempted", "passed", "failed", "skipped", "stopped")}
        self._last_result = ""
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _init_db(self) -> None:
        self.schema_version = SQLiteMigrator(self.database_path, DEMO_MIGRATIONS).migrate()

    def _normalise(self, payload: dict[str, Any]) -> dict[str, Any]:
        slots = [str(value) for value in payload.get("slots", []) if str(value) in self.motion.controller.config.slots]
        if not slots:
            slots = sorted(self.motion.controller.config.slots, key=lambda value: int(value) if str(value).isdigit() else str(value))
        config = {
            "mode": str(payload.get("mode", "sequential")).lower(),
            "slots": slots,
            # One sample equals one slot target move. ``max_cycles`` remains
            # accepted as a legacy API alias, but no longer multiplies by the
            # number of configured slots.
            "sample_count": int(payload.get("sample_count", payload.get("max_cycles", 1)) or 0),
            "max_duration_s": float(payload.get("max_duration_s", 0) or 0),
            "dwell_s": max(0.0, float(payload.get("dwell_s", 0) or 0)),
            "speed_mm_s": float(payload.get("speed_mm_s", 5) or 5),
            "random_seed": int(payload.get("random_seed", 0) or 0),
            "stop_on_failure": bool(payload.get("stop_on_failure", True)),
            "motion_only": True,
        }
        if config["mode"] not in {"sequential", "random", "balanced", "selected"}:
            raise ValueError("mode must be sequential, random, balanced, or selected")
        if config["sample_count"] <= 0 and config["max_duration_s"] <= 0:
            raise ValueError("Demo requires sample_count or max_duration_s")
        if config["speed_mm_s"] <= 0:
            raise ValueError("speed_mm_s must be greater than zero")
        return config

    def configure(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self._state in {"STARTING", "RUNNING", "PAUSE_REQUESTED", "PAUSED", "STOPPING"}:
                return {"ok": False, "error": "Stop the active Demo before changing configuration"}
            try:
                self._config = self._normalise(payload)
            except (TypeError, ValueError) as exc:
                return {"ok": False, "error": str(exc)}
            self._state = "CONFIGURING"
            self._arm_token = None
            self._validation_hash = ""
            return {"ok": True, "configuration": dict(self._config), "state": self._state}

    def validate(self) -> dict[str, Any]:
        with self._lock:
            if not self._config:
                return {"ok": False, "error": "Configure Demo first"}
            errors = self.motion._motion_safety_errors(require_homed=True, required_axes={"x", "y", "z"})
            if not self.motion.motion_enabled:
                errors.append("Motion is disabled")
            if errors:
                return {"ok": False, "error": "; ".join(dict.fromkeys(errors))}
            self._validation_hash = json.dumps(self._config, sort_keys=True, separators=(",", ":"))
            self._state = "VALIDATED"
            return {"ok": True, "state": self._state, "configuration": dict(self._config)}

    def arm(self) -> dict[str, Any]:
        validation = self.validate()
        if not validation.get("ok"):
            return validation
        with self._lock:
            self._arm_token = uuid.uuid4().hex
            self._arm_until = time.monotonic() + 30.0
            self._state = "ARMED"
            return {"ok": True, "state": self._state, "arm_token": self._arm_token, "expires_in_s": 30}

    def start(self, arm_token: str) -> dict[str, Any]:
        with self._lock:
            if self._state != "ARMED" or arm_token != self._arm_token or time.monotonic() >= self._arm_until:
                return {"ok": False, "error": "Demo arm token is invalid or expired"}
            if self._thread and self._thread.is_alive():
                return {"ok": False, "error": "Demo is already running"}
            errors = self.motion._motion_safety_errors(require_homed=True, required_axes={"x", "y", "z"})
            if errors or not self.motion.motion_enabled:
                self._arm_token = None
                return {"ok": False, "error": "; ".join(errors or ["Motion is disabled"])}
            self._arm_token = None
            self._session_id = uuid.uuid4().hex
            self._started_at, self._ended_at = _now(), None
            self._state = "STARTING"
            self._stop.clear()
            self._pause_requested = False
            self._cycle = 0
            self._counters = {key: 0 for key in self._counters}
            requested = max(0, self._config["sample_count"])
            self._counters["requested"] = requested
            with closing(self._connect()) as db, db:
                db.execute("INSERT INTO demo_sessions(session_id,started_at,state,configuration_json,requested) VALUES(?,?,?,?,?)", (self._session_id, self._started_at, self._state, json.dumps(self._config, sort_keys=True), requested))
            self._thread = threading.Thread(target=self._run, name="demo-slot-sampling", daemon=True)
            self._thread.start()
            return {"ok": True, "session_id": self._session_id, "state": self._state}

    def _ordered_slots(self, rng: random.Random) -> list[str]:
        slots = list(self._config["slots"])
        if self._config["mode"] == "random":
            rng.shuffle(slots)
        elif self._config["mode"] == "balanced":
            with closing(self._connect()) as db, db:
                counts = {row["slot_code"]: row["count"] for row in db.execute("SELECT slot_code,COUNT(*) count FROM demo_samples GROUP BY slot_code")}
            slots.sort(key=lambda slot: (counts.get(slot, 0), slot))
        return slots

    def _sample_plan(self, rng: random.Random) -> list[str]:
        """Build the bounded list of target slots, one entry per requested move."""
        slots = list(self._config["slots"])
        count = max(0, int(self._config["sample_count"]))
        if count == 0:
            return []
        mode = self._config["mode"]
        if mode == "selected":
            return [slots[0]] * count
        if mode == "sequential":
            return [slots[index % len(slots)] for index in range(count)]
        if mode == "balanced":
            ordered = self._ordered_slots(rng)
            return [ordered[index % len(ordered)] for index in range(count)]

        # Random sampling avoids an immediate duplicate when alternatives
        # exist so each observed movement is useful for target verification.
        plan: list[str] = []
        for _ in range(count):
            candidates = [slot for slot in slots if not plan or slot != plan[-1]] or slots
            plan.append(rng.choice(candidates))
        return plan

    def _run(self) -> None:
        rng = random.Random(self._config["random_seed"])
        started = time.monotonic()
        reason = ""
        try:
            plan = self._sample_plan(rng)
            plan_index = 0
            while not self._stop.is_set():
                if self._config["sample_count"] > 0 and plan_index >= len(plan):
                    break
                if self._config["max_duration_s"] > 0 and time.monotonic() - started >= self._config["max_duration_s"]:
                    break
                if plan:
                    slot = plan[plan_index]
                    next_slot = plan[plan_index + 1] if plan_index + 1 < len(plan) else None
                    plan_index += 1
                else:
                    # Duration-only mode remains bounded by its watchdog.
                    candidates = [item for item in self._config["slots"] if item != self._current_slot] or list(self._config["slots"])
                    slot = rng.choice(candidates) if self._config["mode"] == "random" else candidates[self._cycle % len(candidates)]
                    next_slot = None
                self._cycle += 1
                self._current_slot = slot
                self._next_slot = next_slot
                self._state = "MOVING_TO_SLOT"
                sample_id, sample_started, t0 = uuid.uuid4().hex, _now(), time.monotonic()
                self._counters["attempted"] += 1
                result = self.motion.move_to_slot(slot, speed_mm_s=self._config["speed_mm_s"])
                stopped = self._stop.is_set()
                passed = bool(result.get("ok")) and not stopped
                outcome = "STOPPED" if stopped else ("PASSED" if passed else "FAILED")
                reason = str(result.get("error") or "")
                if not stopped:
                    self._counters["passed" if passed else "failed"] += 1
                self._last_result = outcome if passed or stopped else f"FAILED: {reason}"
                with closing(self._connect()) as db, db:
                    db.execute("INSERT INTO demo_samples VALUES(?,?,?,?,?,?,?,?,?)", (sample_id, self._session_id, self._cycle, slot, sample_started, _now(), round(time.monotonic()-t0, 3), outcome, reason))
                if stopped:
                    break
                if not passed and self._config["stop_on_failure"]:
                    raise RuntimeError(reason or "Slot move failed")
                if self._pause_requested:
                    self._state = "PAUSED"
                    while self._pause_requested and not self._stop.wait(0.1):
                        pass
                if self._config["dwell_s"] and self._stop.wait(self._config["dwell_s"]):
                    break
            self._state = "STOPPED" if self._stop.is_set() else "COMPLETED"
        except Exception as exc:
            reason = str(exc)
            self._state = "FAILED"
            self._last_result = f"FAILED: {reason}"
        finally:
            self._ended_at = _now()
            self._current_slot = self._next_slot = None
            with closing(self._connect()) as db, db:
                db.execute("UPDATE demo_sessions SET ended_at=?,state=?,attempted=?,passed=?,failed=?,skipped=?,stopped=?,final_reason=? WHERE session_id=?", (self._ended_at, self._state, self._counters["attempted"], self._counters["passed"], self._counters["failed"], self._counters["skipped"], self._counters["stopped"], reason, self._session_id))

    def pause(self) -> dict[str, Any]:
        with self._lock:
            if self._state not in {"STARTING", "MOVING_TO_SLOT", "RUNNING"}:
                return {"ok": False, "error": "Demo is not running"}
            self._pause_requested = True
            self._state = "PAUSE_REQUESTED"
            return {"ok": True, "state": self._state}

    def resume(self) -> dict[str, Any]:
        validation = self.validate()
        if not validation.get("ok"):
            return validation
        with self._lock:
            self._pause_requested = False
            self._state = "RUNNING"
            return {"ok": True, "state": self._state}

    def stop(self, reason: str = "Demo stopped by operator", stop_motion: bool = True) -> dict[str, Any]:
        self._stop.set()
        self._pause_requested = False
        if self._state in {"STARTING", "MOVING_TO_SLOT", "RUNNING", "PAUSE_REQUESTED", "PAUSED"}:
            self._state = "STOPPING"
            self._counters["stopped"] += 1
            self._last_result = reason
            if stop_motion:
                self.motion.stop()
        return {"ok": True, "state": self._state, "session_id": self._session_id}

    def status(self) -> dict[str, Any]:
        with self._lock:
            attempted = self._counters["attempted"]
            return {"state": self._state, "session_id": self._session_id, "started_at": self._started_at, "ended_at": self._ended_at, "cycle": self._cycle, "current_slot": self._current_slot, "next_slot": self._next_slot, "configuration": dict(self._config), "counters": dict(self._counters) | {"success_rate": round(100*self._counters["passed"]/attempted, 1) if attempted else 0.0}, "last_result": self._last_result, "pause_requested": self._pause_requested, "schema_version": self.schema_version}

    def history(self, limit: int = 50) -> list[dict[str, Any]]:
        with closing(self._connect()) as db, db:
            sessions = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM demo_sessions ORDER BY started_at DESC LIMIT ?",
                    (max(1, min(500, limit)),),
                )
            ]
            for session in sessions:
                try:
                    session["configuration"] = json.loads(session.pop("configuration_json"))
                except (TypeError, ValueError, json.JSONDecodeError):
                    session["configuration"] = {}
                    session.pop("configuration_json", None)
                session["samples"] = [
                    dict(row)
                    for row in db.execute(
                        """SELECT sample_id,cycle_no,slot_code,started_at,completed_at,
                                  duration_s,result,reason
                           FROM demo_samples WHERE session_id=? ORDER BY cycle_no""",
                        (session["session_id"],),
                    )
                ]
            return sessions

    def export_csv(self) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(("session_id", "cycle", "slot", "started_at", "completed_at", "duration_s", "result", "reason"))
        with closing(self._connect()) as db, db:
            for row in db.execute("SELECT session_id,cycle_no,slot_code,started_at,completed_at,duration_s,result,reason FROM demo_samples ORDER BY started_at"):
                writer.writerow(tuple(row))
        return output.getvalue()
