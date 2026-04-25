import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "threads_adapter.py"
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


class FakeThreadsClient:
    def __init__(self) -> None:
        self.profile_calls = 0
        self.post_calls = 0
        self.insight_calls = []
        self.reply_calls = []

    def get_user_profile(self, token: str) -> dict:
        self.profile_calls += 1
        return {"id": "user_1", "username": "seo_lisa"}

    def fetch_all_threads(self, user_id: str, token: str) -> list[dict]:
        self.post_calls += 1
        self.user_id = user_id
        return [
            {
                "id": "th_1",
                "text": "Threads API post",
                "timestamp": "2026-04-01T00:00:00+00:00",
                "media_type": "TEXT",
                "permalink": "https://threads.net/@seo_lisa/post/th_1",
                "shortcode": "th_1",
                "is_reply": False,
            }
        ]

    def fetch_thread_insights(self, thread_id: str, token: str) -> dict:
        self.insight_calls.append(thread_id)
        return {"views": 100, "likes": 10, "replies": 3, "reposts": 2, "quotes": 1}

    def fetch_thread_replies(self, thread_id: str, token: str) -> list[dict]:
        self.reply_calls.append(thread_id)
        return [
            {
                "id": "reply_1",
                "username": "reader",
                "text": "Useful.",
                "timestamp": "2026-04-01T01:00:00+00:00",
            }
        ]


class ThreadsAdapterTests(unittest.TestCase):
    def test_normalizes_threads_post_to_schema_valid_platform_post(self) -> None:
        threads_adapter = load_module("threads_adapter", MODULE_PATH)
        platform_schema = load_module("platform_schema", SCHEMA_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)

        normalized = threads_adapter.normalize_threads_post(
            {
                "id": "th_1",
                "text": "Threads post",
                "timestamp": "2026-04-01T00:00:00+00:00",
                "media_type": "TEXT",
                "permalink": "https://threads.net/@seo_lisa/post/th_1",
                "shortcode": "abc",
            },
            account_id="threads:@seo_lisa",
            metrics={"views": 120, "likes": 12, "replies": 4, "reposts": 2, "quotes": 1},
            replies=[
                {
                    "id": "reply_1",
                    "username": "reader",
                    "text": "Helpful.",
                    "timestamp": "2026-04-01T01:00:00+00:00",
                }
            ],
        )

        schema_post = platform_adapters.normalized_post_to_schema_post(normalized)
        tracker = platform_schema.build_platform_tracker(posts=[schema_post])

        platform_schema.validate_platform_tracker(tracker)
        self.assertEqual(normalized.platform, "threads")
        self.assertEqual(normalized.metrics.view_count, 120)
        self.assertEqual(normalized.metrics.reaction_count, 12)
        self.assertEqual(normalized.metrics.comment_count, 4)
        self.assertEqual(normalized.metrics.share_count, 3)
        self.assertEqual(normalized.comments[0].platform_comment_id, "reply_1")
        self.assertIn("threads", normalized.platform_metadata)

    def test_capabilities_are_loaded_from_policy_without_enabling_publish(self) -> None:
        threads_adapter = load_module("threads_adapter", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)

        adapter = threads_adapter.ThreadsPlatformAdapter(account_id="threads:@seo_lisa", token="token")
        report = adapter.capabilities()

        self.assertIsInstance(adapter, platform_adapters.PlatformAdapter)
        self.assertTrue(report.can_import_history)
        self.assertTrue(report.can_refresh_metrics)
        self.assertTrue(report.can_fetch_comments)
        self.assertFalse(report.can_publish)
        self.assertIn("view_count", report.supported_metrics)

    def test_missing_token_fails_before_network_calls(self) -> None:
        threads_adapter = load_module("threads_adapter", MODULE_PATH)
        fake_client = FakeThreadsClient()
        adapter = threads_adapter.ThreadsPlatformAdapter(
            account_id="threads:@seo_lisa",
            token=None,
            client=fake_client,
        )

        with self.assertRaisesRegex(threads_adapter.ThreadsAdapterCredentialError, "THREADS_API_TOKEN"):
            adapter.list_posts()

        self.assertEqual(fake_client.profile_calls, 0)
        self.assertEqual(fake_client.post_calls, 0)

    def test_adapter_uses_injected_client_for_offline_import_refresh_and_comments(self) -> None:
        threads_adapter = load_module("threads_adapter", MODULE_PATH)
        fake_client = FakeThreadsClient()
        adapter = threads_adapter.ThreadsPlatformAdapter(
            account_id="threads:@seo_lisa",
            token="token",
            client=fake_client,
        )

        posts = adapter.list_posts()
        metrics = adapter.refresh_metrics("th_1")
        comments = adapter.fetch_comments("th_1")

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].platform_post_id, "th_1")
        self.assertEqual(posts[0].comments[0].text, "Useful.")
        self.assertEqual(metrics.share_count, 3)
        self.assertEqual(comments[0].platform_comment_id, "reply_1")
        self.assertEqual(fake_client.user_id, "user_1")

    def test_publish_remains_review_gated(self) -> None:
        threads_adapter = load_module("threads_adapter", MODULE_PATH)
        adapter = threads_adapter.ThreadsPlatformAdapter(account_id="threads:@seo_lisa", token="token")

        result = adapter.publish("Draft")

        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "review_required")


if __name__ == "__main__":
    unittest.main()
