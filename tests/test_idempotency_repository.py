import tempfile
import unittest
from pathlib import Path

from narit_vending.persistence.idempotency_repository import (
    IdempotencyRecord,
    InMemoryIdempotencyRepository,
    SQLiteIdempotencyRepository,
)


class IdempotencyRepositoryTests(unittest.TestCase):
    def test_memory_repository_evicts_least_recently_used(self):
        repository = InMemoryIdempotencyRepository(capacity=2)
        for key in ("one", "two"):
            repository.put(IdempotencyRecord(key, key, {"state": "COMPLETED"}))
        repository.get("one")
        repository.put(IdempotencyRecord("three", "three", {"state": "COMPLETED"}))
        self.assertIsNotNone(repository.get("one"))
        self.assertIsNone(repository.get("two"))

    def test_sqlite_repository_survives_new_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "controller.sqlite3"
            first = SQLiteIdempotencyRepository(path)
            first.put(IdempotencyRecord("request-1", "fingerprint", {"state": "COMPLETED", "accepted": True}))
            restored = SQLiteIdempotencyRepository(path).get("request-1")
            self.assertIsNotNone(restored)
            self.assertEqual(restored.fingerprint, "fingerprint")
            self.assertEqual(restored.result["state"], "COMPLETED")

    def test_sqlite_repository_enforces_capacity(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteIdempotencyRepository(Path(directory) / "controller.sqlite3", capacity=2)
            for key in ("one", "two", "three"):
                repository.put(IdempotencyRecord(key, key, {"state": "COMPLETED"}))
            self.assertIsNone(repository.get("one"))
            self.assertIsNotNone(repository.get("two"))
            self.assertIsNotNone(repository.get("three"))


if __name__ == "__main__":
    unittest.main()
