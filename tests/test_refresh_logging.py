import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "refresh_logging.py"
SCRIPT_PATH = REPO_ROOT / "scripts" / "update_snapshots.py"
TRACKER_FIXTURE = REPO_ROOT / "examples" / "tracker-example.json"
TMP_DIR = REPO_ROOT / ".tmp"


def load_module():
    spec = importlib.util.spec_from_file_location("refresh_logging", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load refresh_logging module")
    module = importlib.util.module_from_spec(spec)
    scripts_dir = str(MODULE_PATH.parent)
    original_sys_path = list(sys.path)
    try:
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_sys_path
    return module


class RefreshLoggingTests(unittest.TestCase):
    def test_build_success_entry_uses_contract_shape(self) -> None:
        refresh_logging = load_module()

        entry = refresh_logging.build_refresh_success_entry(
            posts_scraped=10,
            new_posts=2,
            updated_posts=4,
            replies_added=7,
        )

        self.assertTrue(entry["ok"])
        self.assertEqual(entry["posts_scraped"], 10)
        self.assertEqual(entry["new_posts"], 2)
        self.assertEqual(entry["updated_posts"], 4)
        self.assertEqual(entry["replies_added"], 7)
        self.assertIn("ts", entry)

    def test_headless_missing_token_logs_failure_entry(self) -> None:
        case_dir = TMP_DIR / f"refresh-log-{uuid.uuid4().hex}"
        tracker_path = case_dir / "tracker.json"
        log_path = case_dir / "threads_refresh.log"

        try:
            case_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(TRACKER_FIXTURE, tracker_path)

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--tracker",
                    str(tracker_path),
                    "--headless",
                    "--log-file",
                    str(log_path),
                ],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(log_path.exists(), "headless failure did not create threads_refresh.log")

            lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertFalse(entry["ok"])
            self.assertIn(entry["reason"], {"other", "timeout", "backup_failed"})
            self.assertIn("ts", entry)
        finally:
            if case_dir.exists():
                shutil.rmtree(case_dir)


if __name__ == "__main__":
    unittest.main()
