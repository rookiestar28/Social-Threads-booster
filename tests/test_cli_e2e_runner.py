import importlib.util
import json
import shutil
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "run_cli_e2e.py"
TMP_DIR = REPO_ROOT / ".tmp"


def load_module():
    spec = importlib.util.spec_from_file_location("run_cli_e2e", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load run_cli_e2e module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CliE2ERunnerTests(unittest.TestCase):
    def test_parse_export_fixture_is_written_under_tmp(self) -> None:
        runner = load_module()
        case_dir = TMP_DIR / "cli-e2e-runner-fixture"

        try:
            fixture = runner.write_parse_export_fixture(case_dir)

            self.assertTrue(fixture.exists())
            self.assertTrue(fixture.is_relative_to(TMP_DIR))
            payload = json.loads(fixture.read_text(encoding="utf-8"))
            self.assertIn("threads_media", payload)
        finally:
            if case_dir.exists():
                shutil.rmtree(case_dir)

    def test_assert_file_contains_raises_for_missing_content(self) -> None:
        runner = load_module()
        case_dir = TMP_DIR / "cli-e2e-runner-assert"
        target = case_dir / "artifact.md"

        try:
            case_dir.mkdir(parents=True, exist_ok=True)
            target.write_text("# Different Heading\n", encoding="utf-8")

            with self.assertRaisesRegex(runner.E2EFailure, "expected text"):
                runner.assert_file_contains(target, "# Expected Heading")
        finally:
            if case_dir.exists():
                shutil.rmtree(case_dir)

    def test_run_command_reports_nonzero_exit(self) -> None:
        runner = load_module()
        result = subprocess.CompletedProcess(args=["fake"], returncode=7, stdout="", stderr="boom")

        with self.assertRaisesRegex(runner.E2EFailure, "exit code 7"):
            runner.assert_command_ok("failing step", result)


if __name__ == "__main__":
    unittest.main()
