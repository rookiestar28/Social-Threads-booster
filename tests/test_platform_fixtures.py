import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "platform_fixtures.py"
FIXTURE_DIR = REPO_ROOT / "examples" / "platform-fixtures"


REQUIRED_FIXTURES = {
    "threads",
    "instagram",
    "facebook_pages",
    "youtube",
    "reddit",
    "bluesky",
    "mastodon",
}


def load_module():
    spec = importlib.util.spec_from_file_location("platform_fixtures", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load platform_fixtures")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PlatformFixturesTests(unittest.TestCase):
    def test_required_fixture_files_are_present(self) -> None:
        fixtures = load_module()

        discovered = {fixture.platform for fixture in fixtures.load_fixture_corpus(FIXTURE_DIR)}

        self.assertEqual(discovered, REQUIRED_FIXTURES)

    def test_every_fixture_normalizes_to_schema_tracker(self) -> None:
        fixtures = load_module()

        tracker = fixtures.build_tracker_from_fixtures(fixtures.load_fixture_corpus(FIXTURE_DIR))

        self.assertEqual(tracker["schema_version"], 2)
        self.assertEqual({post["platform"] for post in tracker["posts"]}, REQUIRED_FIXTURES)
        self.assertGreaterEqual(len(tracker["posts"]), len(REQUIRED_FIXTURES))

    def test_every_fixture_declares_credential_missing_expectation(self) -> None:
        fixtures = load_module()

        for fixture in fixtures.load_fixture_corpus(FIXTURE_DIR):
            with self.subTest(platform=fixture.platform):
                self.assertIn("credential_missing", fixture.capability_expectations)
                expectation = fixture.capability_expectations["credential_missing"]
                self.assertFalse(expectation["ok"])
                self.assertTrue(expectation["reason"])


if __name__ == "__main__":
    unittest.main()
