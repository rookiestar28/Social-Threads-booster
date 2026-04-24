import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "chrome_refresh.py"


def load_module():
    spec = importlib.util.spec_from_file_location("chrome_refresh", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load chrome_refresh module")
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


class ChromeRefreshTests(unittest.TestCase):
    def test_selector_health_maps_zero_cards_to_actionable_reasons(self) -> None:
        chrome_refresh = load_module()

        self.assertTrue(chrome_refresh.check_selector_health(2, login_wall_found=False))
        with self.assertRaisesRegex(chrome_refresh.ChromeRefreshError, "login_wall"):
            chrome_refresh.check_selector_health(0, login_wall_found=True)
        with self.assertRaisesRegex(chrome_refresh.ChromeRefreshError, "selector_health_failed"):
            chrome_refresh.check_selector_health(0, login_wall_found=False)

    def test_normalize_scraped_post_preserves_existing_metric_when_token_is_missing(self) -> None:
        chrome_refresh = load_module()
        existing = {
            "metrics": {
                "views": 500,
                "likes": 40,
                "replies": 8,
                "reposts": 2,
                "quotes": 1,
                "shares": 3,
            }
        }

        post = chrome_refresh.normalize_scraped_post(
            {
                "id": "post-1",
                "text": "Updated text",
                "created_at": "2026-04-20T10:00:00+00:00",
                "metrics": {"views": "bad", "likes": "1.2K"},
            },
            existing_post=existing,
        )

        self.assertEqual(post["metrics"]["views"], 500)
        self.assertEqual(post["metrics"]["likes"], 1200)
        self.assertEqual(post["metrics"]["replies"], 8)

    def test_merge_scraped_posts_updates_existing_inserts_new_and_sweeps_pending(self) -> None:
        chrome_refresh = load_module()
        tracker_utils = chrome_refresh.tracker_utils
        tracker = tracker_utils.build_empty_tracker(
            posts=[
                tracker_utils.build_post_record(
                    post_id="post-1",
                    text="Old text",
                    created_at="2026-04-20T10:00:00+00:00",
                    source_path="api",
                    data_completeness="full",
                    metrics={"views": 100},
                ),
                {
                    "id": "pending-1",
                    "text": "Draft text",
                    "created_at": "2026-04-21T09:00:00+00:00",
                    "pending_expires_at": "2026-04-21T10:00:00+00:00",
                    "prediction_snapshot": {"predicted_at": "2026-04-21T09:00:00+00:00"},
                    "metrics": {"views": 0, "likes": 0, "replies": 0, "reposts": 0, "quotes": 0, "shares": 0},
                    "comments": [],
                    "snapshots": [],
                    "performance_windows": {"24h": None, "72h": None, "7d": None},
                    "topics": [],
                    "source": {"import_path": "prediction", "data_completeness": "pending"},
                },
            ],
            last_updated="2026-04-20T10:00:00+00:00",
        )

        summary = chrome_refresh.merge_scraped_posts(
            tracker,
            [
                {
                    "id": "post-1",
                    "text": "Old text",
                    "created_at": "2026-04-20T10:00:00+00:00",
                    "metrics": {"views": "150", "likes": "10"},
                },
                {
                    "id": "post-2",
                    "text": "New post",
                    "created_at": "2026-04-21T12:00:00+00:00",
                    "metrics": {"views": "20"},
                },
            ],
            captured_at="2026-04-21T12:30:00+00:00",
        )

        ids = {post["id"] for post in tracker["posts"]}
        self.assertEqual(summary["updated_posts"], 1)
        self.assertEqual(summary["new_posts"], 1)
        self.assertEqual(summary["discarded_drafts"], 1)
        self.assertIn("post-2", ids)
        self.assertNotIn("pending-1", ids)
        self.assertEqual(tracker["discarded_drafts"][0]["id"], "pending-1")
        updated = next(post for post in tracker["posts"] if post["id"] == "post-1")
        self.assertEqual(updated["metrics"]["views"], 150)
        self.assertEqual(len(updated["snapshots"]), 1)


if __name__ == "__main__":
    unittest.main()
