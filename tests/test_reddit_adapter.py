import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "reddit_adapter.py"
ADAPTERS_PATH = REPO_ROOT / "scripts" / "platform_adapters.py"
SCHEMA_PATH = REPO_ROOT / "scripts" / "platform_schema.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    scripts_dir = str(path.parent)
    original_sys_path = list(sys.path)
    try:
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_sys_path
    return module


def reddit_submission_payload(submission_id: str = "rd_submission_1") -> dict:
    return {
        "id": submission_id,
        "title": "What changed after your last core update recovery?",
        "selftext": "Share the exact recovery step.",
        "created_utc": 1775347200,
        "permalink": "/r/SEO/comments/rd_submission_1/example/",
        "url": "https://www.reddit.com/r/SEO/comments/rd_submission_1/example/",
        "score": 36,
        "num_comments": 14,
        "subreddit": "SEO",
    }


class FakeRedditClient:
    def __init__(self) -> None:
        self.calls = []

    def list_submissions(self, account_id: str, token: str) -> list[dict]:
        self.calls.append(("list_submissions", account_id))
        return [reddit_submission_payload()]

    def fetch_submission(self, submission_id: str, token: str) -> dict:
        self.calls.append(("fetch_submission", submission_id))
        return reddit_submission_payload(submission_id)

    def fetch_comments(self, submission_id: str, token: str) -> list[dict]:
        self.calls.append(("fetch_comments", submission_id))
        return [
            {
                "id": "rd_comment_1",
                "body": "The internal-link cleanup mattered most.",
                "created_utc": 1775350800,
                "author": "seo_reader",
                "score": 5,
                "parent_id": f"t3_{submission_id}",
            }
        ]


class RedditAdapterTests(unittest.TestCase):
    def test_submission_normalization_keeps_unavailable_metrics_null(self) -> None:
        reddit_adapter = load_module("reddit_adapter", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)
        platform_schema = load_module("platform_schema", SCHEMA_PATH)

        normalized = reddit_adapter.normalize_reddit_submission(
            reddit_submission_payload(),
            account_id="reddit:u_seo_lisa",
            comments=[
                {
                    "id": "rd_comment_1",
                    "body": "The internal-link cleanup mattered most.",
                    "created_utc": 1775350800,
                    "author": "seo_reader",
                    "score": 5,
                }
            ],
        )
        schema_post = platform_adapters.normalized_post_to_schema_post(normalized)

        platform_schema.validate_platform_tracker(platform_schema.build_platform_tracker(posts=[schema_post]))
        self.assertEqual(normalized.platform, "reddit")
        self.assertIsNone(normalized.metrics.view_count)
        self.assertIsNone(normalized.metrics.share_count)
        self.assertEqual(normalized.metrics.reaction_count, 36)
        self.assertEqual(normalized.metrics.comment_count, 14)
        self.assertEqual(normalized.comments[0].metrics.reaction_count, 5)
        self.assertEqual(normalized.platform_metadata["reddit"]["raw"]["submission"]["subreddit"], "SEO")

    def test_capabilities_do_not_invent_owned_insights(self) -> None:
        reddit_adapter = load_module("reddit_adapter", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)

        adapter = reddit_adapter.RedditPlatformAdapter(account_id="reddit:u_seo_lisa", token="token")
        report = adapter.capabilities()

        self.assertIsInstance(adapter, platform_adapters.PlatformAdapter)
        self.assertEqual(report.platform, "reddit")
        self.assertTrue(report.can_import_history)
        self.assertTrue(report.can_refresh_metrics)
        self.assertTrue(report.can_fetch_comments)
        self.assertFalse(report.can_publish)
        self.assertNotIn("view_count", report.supported_metrics)

    def test_missing_token_fails_before_client_calls(self) -> None:
        reddit_adapter = load_module("reddit_adapter", MODULE_PATH)
        fake_client = FakeRedditClient()
        adapter = reddit_adapter.RedditPlatformAdapter(
            account_id="reddit:u_seo_lisa",
            token=None,
            client=fake_client,
        )

        with self.assertRaisesRegex(reddit_adapter.RedditAdapterCredentialError, "REDDIT_OAUTH_TOKEN"):
            adapter.list_posts()

        self.assertEqual(fake_client.calls, [])

    def test_injected_client_drives_offline_list_refresh_and_comments(self) -> None:
        reddit_adapter = load_module("reddit_adapter", MODULE_PATH)
        fake_client = FakeRedditClient()
        adapter = reddit_adapter.RedditPlatformAdapter(
            account_id="reddit:u_seo_lisa",
            token="token",
            client=fake_client,
        )

        posts = adapter.list_posts()
        metrics = adapter.refresh_metrics("rd_submission_1")
        comments = adapter.fetch_comments("rd_submission_1")

        self.assertEqual(posts[0].platform_post_id, "rd_submission_1")
        self.assertEqual(posts[0].metrics.reaction_count, 36)
        self.assertEqual(metrics.comment_count, 14)
        self.assertEqual(comments[0].platform_comment_id, "rd_comment_1")
        self.assertIn(("list_submissions", "reddit:u_seo_lisa"), fake_client.calls)


if __name__ == "__main__":
    unittest.main()
