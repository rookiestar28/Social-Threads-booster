import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "tiktok_adapter.py"
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


def tiktok_video_payload(video_id="tiktok_100"):
    return {
        "id": video_id,
        "title": "Launch recap",
        "video_description": "TikTok launch recap.",
        "create_time": 1775692800,
        "share_url": "https://www.tiktok.com/@brand/video/100",
        "cover_image_url": "https://example.com/cover.jpg",
        "duration": 42,
        "view_count": 1500,
        "like_count": 100,
        "comment_count": 12,
        "share_count": 6,
    }


def tiktok_research_video_payload():
    return {
        "video_id": "research_200",
        "username": "brand",
        "video_description": "Research API shaped payload.",
        "create_time": 1775692860,
        "view_count": 2000,
        "like_count": 120,
        "comment_count": 14,
        "share_count": 9,
    }


class FakeTikTokClient:
    def __init__(self):
        self.calls = []

    def list_videos(self, account_id, token):
        self.calls.append(("list_videos", account_id))
        return [tiktok_video_payload()]

    def fetch_video(self, video_id, token):
        self.calls.append(("fetch_video", video_id))
        return tiktok_video_payload(video_id)


class TikTokAdapterTests(unittest.TestCase):
    def test_video_normalization_maps_display_fields_and_metrics(self):
        tiktok_adapter = load_module("tiktok_adapter", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)
        platform_schema = load_module("platform_schema", SCHEMA_PATH)

        normalized = tiktok_adapter.normalize_tiktok_video(
            tiktok_video_payload(),
            account_id="tiktok:creator:brand",
            product_surface="display_api",
        )
        schema_post = platform_adapters.normalized_post_to_schema_post(normalized)

        platform_schema.validate_platform_tracker(platform_schema.build_platform_tracker(posts=[schema_post]))
        self.assertEqual(normalized.platform, "tiktok")
        self.assertEqual(normalized.metrics.view_count, 1500)
        self.assertEqual(normalized.metrics.reaction_count, 100)
        self.assertEqual(normalized.metrics.comment_count, 12)
        self.assertEqual(normalized.metrics.share_count, 6)
        self.assertEqual(normalized.platform_metadata["tiktok"]["product_surface"], "display_api")
        self.assertEqual(normalized.platform_metadata["tiktok"]["media"]["duration"], 42)

    def test_research_shaped_payload_keeps_surface_separate(self):
        tiktok_adapter = load_module("tiktok_adapter", MODULE_PATH)

        normalized = tiktok_adapter.normalize_tiktok_video(
            tiktok_research_video_payload(),
            account_id="tiktok:research:app",
            product_surface="research_api",
        )

        self.assertEqual(normalized.platform_post_id, "research_200")
        self.assertEqual(normalized.platform_metadata["tiktok"]["product_surface"], "research_api")
        self.assertEqual(normalized.platform_metadata["tiktok"]["author"], "brand")

    def test_capabilities_are_product_specific_and_fail_closed(self):
        tiktok_adapter = load_module("tiktok_adapter", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)

        adapter = tiktok_adapter.TikTokPlatformAdapter(account_id="tiktok:creator:brand", token="token")
        report = adapter.capabilities()

        self.assertIsInstance(adapter, platform_adapters.PlatformAdapter)
        self.assertEqual(report.platform, "tiktok")
        self.assertFalse(report.can_import_history)
        self.assertFalse(report.can_refresh_metrics)
        self.assertFalse(report.can_fetch_comments)
        self.assertFalse(report.can_publish)
        self.assertIn("product", " ".join(report.notes).lower())

    def test_missing_token_and_unconfirmed_access_fail_before_client_calls(self):
        tiktok_adapter = load_module("tiktok_adapter", MODULE_PATH)
        fake = FakeTikTokClient()
        missing = tiktok_adapter.TikTokPlatformAdapter(
            account_id="tiktok:creator:brand",
            token=None,
            access_confirmed=True,
            client=fake,
        )
        gated = tiktok_adapter.TikTokPlatformAdapter(
            account_id="tiktok:creator:brand",
            token="token",
            access_confirmed=False,
            client=fake,
        )

        with self.assertRaisesRegex(tiktok_adapter.TikTokAdapterCredentialError, "TIKTOK_ACCESS_TOKEN"):
            missing.list_posts()
        with self.assertRaisesRegex(tiktok_adapter.TikTokAdapterCapabilityError, "product"):
            gated.list_posts()

        self.assertEqual(fake.calls, [])

    def test_injected_client_drives_offline_paths_when_access_confirmed(self):
        tiktok_adapter = load_module("tiktok_adapter", MODULE_PATH)
        fake = FakeTikTokClient()
        adapter = tiktok_adapter.TikTokPlatformAdapter(
            account_id="tiktok:creator:brand",
            token="token",
            access_confirmed=True,
            client=fake,
        )

        posts = adapter.list_posts()
        metrics = adapter.refresh_metrics("tiktok_100")
        comments = adapter.fetch_comments("tiktok_100")

        self.assertEqual(posts[0].platform_post_id, "tiktok_100")
        self.assertEqual(metrics.view_count, 1500)
        self.assertEqual(comments, [])
        self.assertIn(("list_videos", "tiktok:creator:brand"), fake.calls)


if __name__ == "__main__":
    unittest.main()
