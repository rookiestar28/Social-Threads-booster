import importlib.util
import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "account_context.py"
SCRIPT_PATH = MODULE_PATH
TMP_DIR = REPO_ROOT / ".tmp"


def load_module():
    spec = importlib.util.spec_from_file_location("account_context", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load account_context module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AccountContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case_dir = TMP_DIR / f"account-context-{uuid.uuid4().hex}"
        self.case_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.case_dir / "accounts.json"

    def tearDown(self) -> None:
        if self.case_dir.exists():
            shutil.rmtree(self.case_dir)

    def write_config(self, payload: dict) -> None:
        self.config_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_resolves_env_credential_context_without_exposing_value(self) -> None:
        module = load_module()
        env_name = f"STB_TEST_TOKEN_{uuid.uuid4().hex.upper()}"
        os.environ[env_name] = "secret-value"
        self.addCleanup(lambda: os.environ.pop(env_name, None))
        self.write_config(
            {
                "accounts": [
                    {
                        "key": "threads_primary",
                        "platform": "threads",
                        "account_id": "user-1",
                        "account_type": "threads_user",
                        "credential_source": {"type": "env", "name": env_name},
                    }
                ]
            }
        )

        context = module.load_account_context(self.config_path, "threads_primary")

        self.assertEqual(context.platform, "threads")
        self.assertTrue(context.credential_available)
        self.assertEqual(context.credential_source_ref, env_name)
        self.assertNotIn("secret-value", json.dumps(context.__dict__))

    def test_rejects_inline_secret_fields(self) -> None:
        module = load_module()
        self.write_config(
            {
                "accounts": [
                    {
                        "key": "bad",
                        "platform": "threads",
                        "account_id": "user-1",
                        "account_type": "threads_user",
                        "access_token": "secret-value",
                        "credential_source": {"type": "env", "name": "THREADS_API_TOKEN"},
                    }
                ]
            }
        )

        with self.assertRaises(module.AccountContextError):
            module.load_account_context(self.config_path, "bad")

    def test_rejects_unsupported_credential_source_type(self) -> None:
        module = load_module()
        self.write_config(
            {
                "accounts": [
                    {
                        "key": "bad",
                        "platform": "threads",
                        "account_id": "user-1",
                        "account_type": "threads_user",
                        "credential_source": {"type": "inline", "value": "secret"},
                    }
                ]
            }
        )

        with self.assertRaises(module.AccountContextError):
            module.load_account_context(self.config_path, "bad")

    def test_missing_env_credential_is_safe_unavailable_state(self) -> None:
        module = load_module()
        self.write_config(
            {
                "accounts": [
                    {
                        "key": "threads_primary",
                        "platform": "threads",
                        "account_id": "user-1",
                        "account_type": "threads_user",
                        "credential_source": {"type": "env", "name": "STB_MISSING_TOKEN"},
                    }
                ]
            }
        )

        context = module.load_account_context(self.config_path, "threads_primary")

        self.assertFalse(context.credential_available)

    def test_cli_can_validate_example_with_missing_credential_allowed(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--config",
                str(REPO_ROOT / "examples" / "platform-accounts-example.json"),
                "--account",
                "threads_primary",
                "--allow-missing-credential",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["platform"], "threads")
        self.assertFalse(payload["credential_available"])


if __name__ == "__main__":
    unittest.main()
