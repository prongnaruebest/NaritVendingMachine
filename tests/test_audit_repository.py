import tempfile
import unittest
from pathlib import Path

from narit_vending.domain.audit import AuditEvent
from narit_vending.persistence.audit_repository import InMemoryAuditRepository, SQLiteAuditRepository


def event(number: int) -> AuditEvent:
    return AuditEvent(
        event_id=f"event-{number}", occurred_at=f"2026-01-01T00:00:0{number}+00:00",
        event_code="COMMAND_COMPLETED", correlation_id="workflow-1", command_id=f"cmd-{number}",
        category="COMMAND", severity="INFO", outcome="COMPLETED", source="http",
        message="completed", details={"number": number},
    )


class AuditRepositoryTests(unittest.TestCase):
    def test_memory_repository_is_bounded_and_newest_first(self):
        repository = InMemoryAuditRepository(capacity=2)
        for number in range(3):
            repository.append(event(number))
        self.assertEqual([item.event_id for item in repository.recent()], ["event-2", "event-1"])

    def test_sqlite_repository_persists_structured_event(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "controller.sqlite3"
            SQLiteAuditRepository(path).append(event(1))
            restored = SQLiteAuditRepository(path).recent()[0]
            self.assertEqual(restored.correlation_id, "workflow-1")
            self.assertEqual(restored.details, {"number": 1})

    def test_sqlite_repository_retention_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteAuditRepository(Path(directory) / "controller.sqlite3", capacity=2)
            for number in range(3):
                repository.append(event(number))
            self.assertEqual([item.event_id for item in repository.recent()], ["event-2", "event-1"])


if __name__ == "__main__":
    unittest.main()
