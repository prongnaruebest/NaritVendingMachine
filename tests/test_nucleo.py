import json
import unittest

from narit_vending.nucleo import NucleoLink


class FakeSerial:
    def __init__(self, response=None, **kwargs):
        self.response = response
        self.writes = []
        self.closed = False

    def write(self, data):
        self.writes.append(data)
        return len(data)

    def flush(self):
        return None

    def reset_input_buffer(self):
        return None

    def readline(self):
        if self.response is None:
            return b""
        response, self.response = self.response, None
        return json.dumps(response).encode("ascii") + b"\r\n"

    def close(self):
        self.closed = True


class NucleoLinkTests(unittest.TestCase):
    def config(self):
        return {"port": "test", "timeout_s": 0.05, "poll_interval_s": 0.1, "stale_after_s": 0.2}

    def test_valid_pong_marks_link_online(self):
        fake = FakeSerial({"type": "pong", "device": "NUCLEO-F439ZI", "protocol": 1, "safe": True})
        link = NucleoLink(self.config(), serial_factory=lambda **kwargs: fake)

        link._poll_once()

        self.assertTrue(link.communication_ok)
        self.assertEqual(fake.writes[-1], b"PING\n")
        self.assertTrue(link.status_payload()["safe"])

    def test_wrong_identity_is_fail_safe(self):
        fake = FakeSerial({"type": "pong", "device": "OTHER", "protocol": 1, "safe": True})
        link = NucleoLink(self.config(), serial_factory=lambda **kwargs: fake)

        link._poll_once()

        self.assertFalse(link.communication_ok)
        self.assertIn("Unexpected Nucleo identity", link.status_payload()["last_error"])

    def test_timeout_marks_alarm_active(self):
        fake = FakeSerial()
        link = NucleoLink(self.config(), serial_factory=lambda **kwargs: fake)

        link._poll_once()

        self.assertFalse(link.communication_ok)
        self.assertTrue(link.alarm_channel()["active"])


if __name__ == "__main__":
    unittest.main()
