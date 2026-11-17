import hashlib
import hmac
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("META_ACCESS_TOKEN", "test-token")
os.environ.setdefault("META_VERIFY_TOKEN", "test-verify")
os.environ.setdefault("IG_ACCOUNT_ID", "test-account")

import main


class BotRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_file = main.DB_FILE
        self.old_secret = main.META_APP_SECRET
        main.DB_FILE = Path(self.temp_dir.name) / "test.sqlite3"
        main.init_db()

    def tearDown(self):
        main.DB_FILE = self.old_db_file
        main.META_APP_SECRET = self.old_secret
        self.temp_dir.cleanup()

    def test_digital_root(self):
        self.assertEqual(main.digital_root(28), 1)
        self.assertEqual(main.digital_root(999), 9)

    def test_date_parser_keeps_supported_formats(self):
        self.assertEqual(main.parse_birth_date("28"), (1, None))
        self.assertEqual(main.parse_birth_date("31.05.2001"), (4, 3))
        self.assertIsNotNone(main.parse_birth_date("29.02.2000"))

    def test_date_parser_rejects_impossible_calendar_dates(self):
        self.assertIsNone(main.parse_birth_date("31.02.2001"))
        self.assertIsNone(main.parse_birth_date("29.02.1900"))
        self.assertIsNone(main.parse_birth_date("31.04"))
        self.assertIsNone(main.parse_birth_date("00.12.2000"))

    def test_signature_validation(self):
        body = b'{"object":"instagram","entry":[]}'
        secret = "unit-test-secret"
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        self.assertTrue(main.is_valid_meta_signature(body, "sha256=" + digest, secret))
        self.assertFalse(main.is_valid_meta_signature(body, "sha256=bad", secret))
        self.assertFalse(main.is_valid_meta_signature(body, digest, secret))
        self.assertFalse(main.is_valid_meta_signature(body, "sha256=" + digest, ""))

    def test_webhook_rejects_invalid_signature_when_secret_configured(self):
        main.META_APP_SECRET = "unit-test-secret"
        response = main.app.test_client().post(
            "/webhook",
            data=b'{"object":"instagram","entry":[]}',
            content_type="application/json",
            headers={"X-Hub-Signature-256": "sha256=invalid"},
        )
        self.assertEqual(response.status_code, 403)

    def test_webhook_accepts_valid_signature_when_secret_configured(self):
        main.META_APP_SECRET = "unit-test-secret"
        body = b'{"object":"instagram","entry":[]}'
        digest = hmac.new(b"unit-test-secret", body, hashlib.sha256).hexdigest()
        response = main.app.test_client().post(
            "/webhook",
            data=body,
            content_type="application/json",
            headers={"X-Hub-Signature-256": "sha256=" + digest},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"EVENT_RECEIVED")


if __name__ == "__main__":
    unittest.main()
