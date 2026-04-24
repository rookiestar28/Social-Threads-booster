import importlib.util
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "platform_migration.py"
SCHEMA_PATH = REPO_ROOT / "scripts" / "platform_schema.py"
TRACKER_PATH = REPO_ROOT / "examples" / "tracker-example.json"
TMP_DIR = REPO_ROOT / ".tmp"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PlatformMigrationTests(unittest.TestCase):
    def test_threads_tracker_migrates_to_valid_platform_tracker(self) -> None:
        migration = load_module("platform_migration", MODULE_PATH)
        schema = load_module("platform_schema", SCHEMA_PATH)
        tracker = json.loads(TRACKER_PATH.read_text(encoding="utf-8"))

        generic = migration.migrate_threads_tracker_to_platform_tracker(tracker)

        schema.validate_platform_tracker(generic)
        self.assertEqual(generic["tracker_type"], "platform-neutral")
        self.assertEqual({post["platform"] for post in generic["posts"]}, {"threads"})
        self.assertEqual(len(generic["posts"]), len(tracker["posts"]))

    def test_migration_preserves_raw_threads_metrics_and_comments(self) -> None:
        migration = load_module("platform_migration", MODULE_PATH)
        tracker = json.loads(TRACKER_PATH.read_text(encoding="utf-8"))

        generic = migration.migrate_threads_tracker_to_platform_tracker(tracker)
        first_post = generic["posts"][0]

        self.assertEqual(first_post["metrics"]["view_count"], tracker["posts"][0]["metrics"]["views"])
        self.assertEqual(first_post["metrics"]["reaction_count"], tracker["posts"][0]["metrics"]["likes"])
        self.assertEqual(first_post["metrics"]["comment_count"], tracker["posts"][0]["metrics"]["replies"])
        self.assertEqual(first_post["platform_metadata"]["threads"]["raw"]["metrics"], tracker["posts"][0]["metrics"])
        self.assertGreater(len(first_post["comments"]), 0)
        self.assertEqual(first_post["comments"][0]["platform"], "threads")

    def test_cli_dry_run_and_write(self) -> None:
        case_dir = TMP_DIR / "platform-migration-cli"
        output = case_dir / "social_posts_tracker.json"
        try:
            case_dir.mkdir(parents=True, exist_ok=True)
            dry_run = subprocess.run(
                [
                    sys.executable,
                    "scripts/migrate_platform_tracker.py",
                    "--input",
                    str(TRACKER_PATH),
                    "--output",
                    str(output),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
            self.assertIn('"would_write": false', dry_run.stdout)
            self.assertFalse(output.exists())

            write_run = subprocess.run(
                [
                    sys.executable,
                    "scripts/migrate_platform_tracker.py",
                    "--input",
                    str(TRACKER_PATH),
                    "--output",
                    str(output),
                    "--write",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(write_run.returncode, 0, write_run.stderr)
            self.assertTrue(output.exists())
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 2)
        finally:
            if case_dir.exists():
                shutil.rmtree(case_dir)


if __name__ == "__main__":
    unittest.main()
