import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "x_adapter.py"
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


def x_post_payload(post_id="x_post_1"):
    return {
        "id": post_id,
        "text": "X post about launch metrics.",
        "created_at": "2026-04-08T00:00:00Z",
        "author_id": "x_user_1",
        "public_metrics": {
            "impression_count": 1000,
            "like_count": 40,
            "reply_count": 5,
            "retweet_count": 3,
            "quote_count": 2,
        },
    }


class FakeXClient:
    def __init__(self):
        self.calls = []

    def list_user_posts(self, account_id, token):
        self.calls.append(("list_user_posts", account_id))
        return [x_post_payload()]

    def fetch_post(self, post_id, token):
        self.calls.append(("fetch_post", post_id))
        return x_post_payload(post_id)

    def fetch_replies(self, post_id, token):
        self.calls.append(("fetch_replies", post_id))
        return [x_post_payload("x_reply_1") | {"conversation_id": post_id}]


class XAdapterTests(unittest.TestCase):
    def test_x_post_normalization_maps_public_metrics(self):
        x_adapter = load_module("x_adapter", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)
        platform_schema = load_module("platform_schema", SCHEMA_PATH)

        normalized = x_adapter.normalize_x_post(
            x_post_payload(),
            account_id="x:user_1",
            replies=[x_post_payload("x_reply_1")],
        )
        schema_post = platform_adapters.normalized_post_to_schema_post(normalized)

        platform_schema.validate_platform_tracker(platform_schema.build_platform_tracker(posts=[schema_post]))
        self.assertEqual(normalized.metrics.view_count, 1000)
        self.assertEqual(normalized.metrics.reaction_count, 40)
        self.assertEqual(normalized.metrics.comment_count, 5)
        self.assertEqual(normalized.metrics.share_count, 5)
        self.assertEqual(normalized.comments[0].platform_comment_id, "x_reply_1")

    def test_capabilities_are_tier_gated(self):
        x_adapter = load_module("x_adapter", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)

        adapter = x_adapter.XPlatformAdapter(account_id="x:user_1", token="token")
        report = adapter.capabilities()

        self.assertIsInstance(adapter, platform_adapters.PlatformAdapter)
        self.assertEqual(report.platform, "x")
        self.assertFalse(report.can_import_history)
        self.assertFalse(report.can_refresh_metrics)
        self.assertFalse(report.can_publish)
        self.assertIn("tier-gated", " ".join(report.notes).lower())

    def test_missing_token_and_unconfirmed_tier_fail_before_client_calls(self):
        x_adapter = load_module("x_adapter", MODULE_PATH)
        fake = FakeXClient()
        missing = x_adapter.XPlatformAdapter(account_id="x:user_1", token=None, tier_confirmed=True, client=fake)
        gated = x_adapter.XPlatformAdapter(account_id="x:user_1", token="token", tier_confirmed=False, client=fake)

        with self.assertRaisesRegex(x_adapter.XAdapterCredentialError, "X_API_BEARER_TOKEN"):
            missing.list_posts()
        with self.assertRaisesRegex(x_adapter.XAdapterCapabilityError, "tier"):
            gated.list_posts()

        self.assertEqual(fake.calls, [])

    def test_injected_client_drives_offline_paths_when_tier_confirmed(self):
        x_adapter = load_module("x_adapter", MODULE_PATH)
        fake = FakeXClient()
        adapter = x_adapter.XPlatformAdapter(account_id="x:user_1", token="token", tier_confirmed=True, client=fake)

        posts = adapter.list_posts()
        metrics = adapter.refresh_metrics("x_post_1")
        comments = adapter.fetch_comments("x_post_1")

        self.assertEqual(posts[0].platform_post_id, "x_post_1")
        self.assertEqual(metrics.share_count, 5)
        self.assertEqual(comments[0].platform_comment_id, "x_reply_1")
        self.assertIn(("list_user_posts", "x:user_1"), fake.calls)


if __name__ == "__main__":
    unittest.main()
