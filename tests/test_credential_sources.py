import os
import unittest
import uuid
from pathlib import Path
import importlib.util
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "credential_sources.py"
TMP_DIR = REPO_ROOT / ".tmp"


def load_module():
    spec = importlib.util.spec_from_file_location("credential_sources", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load credential_sources module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CredentialSourceTests(unittest.TestCase):
    def test_direct_value_returns_warning(self) -> None:
        module = load_module()
        result = module.resolve_credential(
            label="Threads API token",
            direct_value="secret",
            direct_source_name="--token",
            env_var="THREADS_API_TOKEN",
        )

        self.assertEqual(result.value, "secret")
        self.assertIn("Command-line secrets can leak", result.warning)

    def test_file_value_is_trimmed(self) -> None:
        module = load_module()
        token_path = TMP_DIR / f"token-{uuid.uuid4().hex}.txt"
        try:
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(" secret-from-file \n", encoding="utf-8")
            result = module.resolve_credential(
                label="Threads API token",
                direct_source_name="--token",
                env_var="THREADS_API_TOKEN",
                file_path=str(token_path),
            )
            self.assertEqual(result.value, "secret-from-file")
            self.assertIsNone(result.warning)
        finally:
            if token_path.exists():
                token_path.unlink()

    def test_env_value_used_when_no_direct_or_file(self) -> None:
        module = load_module()
        env_name = f"STB_TOKEN_{uuid.uuid4().hex.upper()}"
        os.environ[env_name] = "secret-from-env"
        self.addCleanup(lambda: os.environ.pop(env_name, None))

        result = module.resolve_credential(
            label="Threads API token",
            direct_source_name="--token",
            env_var=env_name,
        )

        self.assertEqual(result.value, "secret-from-env")
        self.assertEqual(result.source, f"env:{env_name}")

    def test_missing_file_raises_without_secret_value(self) -> None:
        module = load_module()
        with self.assertRaises(module.CredentialSourceError) as ctx:
            module.resolve_credential(
                label="Threads API token",
                direct_source_name="--token",
                env_var="THREADS_API_TOKEN",
                file_path=str(TMP_DIR / "missing-token.txt"),
            )
        self.assertIn("file not found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
