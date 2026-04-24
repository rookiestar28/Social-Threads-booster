import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = REPO_ROOT / "knowledge" / "platform_api_policy.json"


REQUIRED_PLATFORMS = {
    "threads",
    "instagram",
    "facebook_pages",
    "youtube",
    "tiktok",
    "x",
    "linkedin",
    "reddit",
    "bluesky",
    "mastodon",
    "pinterest",
}


class PlatformApiPolicyTests(unittest.TestCase):
    def load_policy(self) -> dict:
        return json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def test_policy_contains_required_platforms(self) -> None:
        policy = self.load_policy()
        self.assertEqual(set(policy["platforms"]), REQUIRED_PLATFORMS)

    def test_platform_rows_have_required_shape(self) -> None:
        policy = self.load_policy()
        capability_vocabulary = set(policy["capability_vocabulary"])
        status_vocabulary = set(policy["status_vocabulary"])

        for platform_key, row in policy["platforms"].items():
            with self.subTest(platform=platform_key):
                self.assertTrue(row["display_name"])
                self.assertTrue(row["auth_model"])
                self.assertTrue(row["official_docs"])
                self.assertTrue(row["account_contexts"])
                self.assertTrue(row["implementation_notes"])
                self.assertEqual(set(row["capabilities"]), capability_vocabulary)

                for capability, payload in row["capabilities"].items():
                    self.assertIn(capability, capability_vocabulary)
                    self.assertIn(payload["status"], status_vocabulary)
                    self.assertTrue(payload["gate"])

    def test_official_docs_are_https_urls(self) -> None:
        policy = self.load_policy()
        for platform_key, row in policy["platforms"].items():
            with self.subTest(platform=platform_key):
                for url in row["official_docs"]:
                    self.assertTrue(url.startswith("https://"), msg=url)

    def test_policy_requires_review_before_adapter(self) -> None:
        policy = self.load_policy()
        self.assertTrue(policy["review_required_before_adapter"])


if __name__ == "__main__":
    unittest.main()
