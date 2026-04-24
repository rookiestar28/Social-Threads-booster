import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "log_redaction.py"


def load_module():
    spec = importlib.util.spec_from_file_location("log_redaction", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load log_redaction module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LogRedactionTests(unittest.TestCase):
    def test_redacts_secret_like_keys_recursively(self) -> None:
        module = load_module()
        payload = {
            "detail": "safe",
            "nested": {
                "access_token": "secret",
                "client-secret": "secret",
            },
        }

        sanitized = module.sanitize_log_value(payload)

        self.assertEqual(sanitized["nested"]["access_token"], module.REDACTED)
        self.assertEqual(sanitized["nested"]["client-secret"], module.REDACTED)
        self.assertNotEqual(sanitized["nested"]["access_token"], "secret")
        self.assertNotEqual(sanitized["nested"]["client-secret"], "secret")

    def test_redacts_sensitive_url_query_parameters(self) -> None:
        module = load_module()
        value = "https://example.test/callback?access_token=abc123&ok=1&client_secret=s3"

        sanitized = module.sanitize_log_value({"url": value})

        self.assertIn("access_token=[redacted]", sanitized["url"])
        self.assertIn("client_secret=[redacted]", sanitized["url"])
        self.assertIn("ok=1", sanitized["url"])
        self.assertNotIn("abc123", sanitized["url"])

    def test_redacts_bearer_tokens_and_truncates_long_strings(self) -> None:
        module = load_module()
        value = "Bearer abc.def.ghi " + ("x" * 400)

        sanitized = module.sanitize_log_value({"detail": value})

        self.assertIn("Bearer [redacted]", sanitized["detail"])
        self.assertIn("[truncated]", sanitized["detail"])
        self.assertLess(len(sanitized["detail"]), 280)


if __name__ == "__main__":
    unittest.main()
