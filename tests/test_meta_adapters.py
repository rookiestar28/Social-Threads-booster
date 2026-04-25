import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "meta_adapters.py"
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


class FakeMetaGraphClient:
    def __init__(self) -> None:
        self.calls = []

    def list_instagram_media(self, account_id: str, token: str) -> list[dict]:
        self.calls.append(("list_instagram_media", account_id))
        return [
            {
                "id": "ig_media_1",
                "caption": "Carousel caption",
                "timestamp": "2026-04-02T00:00:00+00:00",
                "media_type": "CAROUSEL_ALBUM",
                "permalink": "https://instagram.com/p/ig_media_1",
                "like_count": 44,
                "comments_count": 6,
            }
        ]

    def fetch_instagram_insights(self, media_id: str, token: str) -> dict:
        self.calls.append(("fetch_instagram_insights", media_id))
        return {"views": 500, "saved": 12, "shares": 5}

    def fetch_instagram_comments(self, media_id: str, token: str) -> list[dict]:
        self.calls.append(("fetch_instagram_comments", media_id))
        return [
            {
                "id": "ig_comment_1",
                "username": "reader",
                "text": "Great carousel.",
                "timestamp": "2026-04-02T01:00:00+00:00",
                "like_count": 2,
            }
        ]

    def list_facebook_page_posts(self, page_id: str, token: str) -> list[dict]:
        self.calls.append(("list_facebook_page_posts", page_id))
        return [
            {
                "id": "fb_post_1",
                "message": "Page update",
                "created_time": "2026-04-03T00:00:00+00:00",
                "permalink_url": "https://facebook.com/page/posts/fb_post_1",
                "shares": {"count": 3},
                "reactions": {"summary": {"total_count": 20}},
                "comments": {"summary": {"total_count": 4}},
            }
        ]

    def fetch_facebook_post_insights(self, post_id: str, token: str) -> dict:
        self.calls.append(("fetch_facebook_post_insights", post_id))
        return {"post_impressions": 1000}

    def fetch_facebook_comments(self, post_id: str, token: str) -> list[dict]:
        self.calls.append(("fetch_facebook_comments", post_id))
        return [
            {
                "id": "fb_comment_1",
                "from": {"id": "user_1"},
                "message": "Useful update.",
                "created_time": "2026-04-03T01:00:00+00:00",
                "like_count": 1,
            }
        ]


class MetaAdaptersTests(unittest.TestCase):
    def test_instagram_normalization_produces_schema_valid_post(self) -> None:
        meta_adapters = load_module("meta_adapters", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)
        platform_schema = load_module("platform_schema", SCHEMA_PATH)

        normalized = meta_adapters.normalize_instagram_media(
            {
                "id": "ig_media_1",
                "caption": "Carousel caption",
                "timestamp": "2026-04-02T00:00:00+00:00",
                "media_type": "CAROUSEL_ALBUM",
                "permalink": "https://instagram.com/p/ig_media_1",
                "like_count": 44,
                "comments_count": 6,
            },
            account_id="instagram:business_1",
            insights={"views": 500, "saved": 12, "shares": 5},
            comments=[
                {
                    "id": "ig_comment_1",
                    "username": "reader",
                    "text": "Great.",
                    "timestamp": "2026-04-02T01:00:00+00:00",
                }
            ],
        )
        schema_post = platform_adapters.normalized_post_to_schema_post(normalized)

        platform_schema.validate_platform_tracker(platform_schema.build_platform_tracker(posts=[schema_post]))
        self.assertEqual(normalized.platform, "instagram")
        self.assertEqual(normalized.metrics.view_count, 500)
        self.assertEqual(normalized.metrics.reaction_count, 44)
        self.assertEqual(normalized.metrics.comment_count, 6)
        self.assertEqual(normalized.metrics.save_count, 12)
        self.assertEqual(normalized.metrics.share_count, 5)
        self.assertEqual(normalized.comments[0].platform_comment_id, "ig_comment_1")

    def test_facebook_page_normalization_produces_schema_valid_post(self) -> None:
        meta_adapters = load_module("meta_adapters", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)
        platform_schema = load_module("platform_schema", SCHEMA_PATH)

        normalized = meta_adapters.normalize_facebook_page_post(
            {
                "id": "fb_post_1",
                "message": "Page update",
                "created_time": "2026-04-03T00:00:00+00:00",
                "permalink_url": "https://facebook.com/page/posts/fb_post_1",
                "shares": {"count": 3},
                "reactions": {"summary": {"total_count": 20}},
                "comments": {"summary": {"total_count": 4}},
            },
            account_id="facebook_pages:page_1",
            insights={"post_impressions": 1000},
            comments=[
                {
                    "id": "fb_comment_1",
                    "from": {"id": "user_1"},
                    "message": "Useful.",
                    "created_time": "2026-04-03T01:00:00+00:00",
                }
            ],
        )
        schema_post = platform_adapters.normalized_post_to_schema_post(normalized)

        platform_schema.validate_platform_tracker(platform_schema.build_platform_tracker(posts=[schema_post]))
        self.assertEqual(normalized.platform, "facebook_pages")
        self.assertEqual(normalized.metrics.view_count, 1000)
        self.assertEqual(normalized.metrics.reaction_count, 20)
        self.assertEqual(normalized.metrics.comment_count, 4)
        self.assertEqual(normalized.metrics.share_count, 3)
        self.assertEqual(normalized.comments[0].author_id, "user_1")

    def test_capabilities_stay_platform_specific(self) -> None:
        meta_adapters = load_module("meta_adapters", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)

        instagram = meta_adapters.InstagramPlatformAdapter(account_id="instagram:business_1", token="token")
        facebook = meta_adapters.FacebookPagesPlatformAdapter(account_id="facebook_pages:page_1", token="token")

        self.assertIsInstance(instagram, platform_adapters.PlatformAdapter)
        self.assertIsInstance(facebook, platform_adapters.PlatformAdapter)
        self.assertEqual(instagram.capabilities().platform, "instagram")
        self.assertEqual(facebook.capabilities().platform, "facebook_pages")
        self.assertTrue(instagram.capabilities().can_import_history)
        self.assertTrue(facebook.capabilities().can_refresh_metrics)
        self.assertFalse(instagram.capabilities().can_publish)

    def test_missing_token_fails_before_graph_client_calls(self) -> None:
        meta_adapters = load_module("meta_adapters", MODULE_PATH)
        fake_client = FakeMetaGraphClient()
        adapter = meta_adapters.InstagramPlatformAdapter(
            account_id="instagram:business_1",
            token=None,
            client=fake_client,
        )

        with self.assertRaisesRegex(meta_adapters.MetaAdapterCredentialError, "META_GRAPH_API_TOKEN"):
            adapter.list_posts()

        self.assertEqual(fake_client.calls, [])

    def test_injected_clients_drive_offline_list_refresh_and_comments(self) -> None:
        meta_adapters = load_module("meta_adapters", MODULE_PATH)
        fake_client = FakeMetaGraphClient()
        instagram = meta_adapters.InstagramPlatformAdapter(
            account_id="instagram:business_1",
            token="token",
            client=fake_client,
        )
        facebook = meta_adapters.FacebookPagesPlatformAdapter(
            account_id="facebook_pages:page_1",
            token="token",
            client=fake_client,
        )

        ig_posts = instagram.list_posts()
        fb_posts = facebook.list_posts()
        ig_metrics = instagram.refresh_metrics("ig_media_1")
        fb_comments = facebook.fetch_comments("fb_post_1")

        self.assertEqual(ig_posts[0].metrics.view_count, 500)
        self.assertEqual(fb_posts[0].metrics.share_count, 3)
        self.assertEqual(ig_metrics.save_count, 12)
        self.assertEqual(fb_comments[0].platform_comment_id, "fb_comment_1")
        self.assertIn(("list_instagram_media", "instagram:business_1"), fake_client.calls)
        self.assertIn(("list_facebook_page_posts", "facebook_pages:page_1"), fake_client.calls)


if __name__ == "__main__":
    unittest.main()
