import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "pinterest_adapter.py"
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


def pinterest_pin_payload(pin_id="pin_100"):
    return {
        "id": pin_id,
        "title": "Launch checklist",
        "description": "Pinterest pin about launch planning.",
        "alt_text": "Checklist graphic",
        "created_at": "2026-04-09T00:00:00Z",
        "link": "https://example.com/launch",
        "board_id": "board_1",
        "board_owner": {"username": "brand"},
        "media": {
            "media_type": "image",
            "images": {"600x": {"url": "https://i.pinimg.com/example.jpg"}},
        },
        "dominant_color": "#336699",
    }


def pinterest_analytics_payload():
    return {
        "all": {
            "IMPRESSION": 1200,
            "SAVE": 80,
            "PIN_CLICK": 55,
            "OUTBOUND_CLICK": 10,
            "ENGAGEMENT": 140,
        }
    }


class FakePinterestClient:
    def __init__(self):
        self.calls = []

    def list_pins(self, account_id, token):
        self.calls.append(("list_pins", account_id))
        return [pinterest_pin_payload()]

    def fetch_pin(self, pin_id, token):
        self.calls.append(("fetch_pin", pin_id))
        return pinterest_pin_payload(pin_id)

    def fetch_pin_analytics(self, pin_id, token):
        self.calls.append(("fetch_pin_analytics", pin_id))
        return pinterest_analytics_payload()


class PinterestAdapterTests(unittest.TestCase):
    def test_pin_normalization_maps_board_media_and_analytics(self):
        pinterest_adapter = load_module("pinterest_adapter", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)
        platform_schema = load_module("platform_schema", SCHEMA_PATH)

        normalized = pinterest_adapter.normalize_pinterest_pin(
            pinterest_pin_payload(),
            account_id="pinterest:user:brand",
            analytics=pinterest_analytics_payload(),
        )
        schema_post = platform_adapters.normalized_post_to_schema_post(normalized)

        platform_schema.validate_platform_tracker(platform_schema.build_platform_tracker(posts=[schema_post]))
        self.assertEqual(normalized.platform, "pinterest")
        self.assertEqual(normalized.metrics.view_count, 1200)
        self.assertEqual(normalized.metrics.save_count, 80)
        self.assertEqual(normalized.metrics.click_count, 65)
        self.assertEqual(normalized.metrics.reaction_count, 140)
        self.assertEqual(normalized.platform_metadata["pinterest"]["board_id"], "board_1")
        self.assertEqual(normalized.platform_metadata["pinterest"]["media"]["media_type"], "image")
        self.assertEqual(normalized.url, "https://www.pinterest.com/pin/pin_100/")

    def test_capabilities_keep_comments_and_publish_unavailable(self):
        pinterest_adapter = load_module("pinterest_adapter", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)

        adapter = pinterest_adapter.PinterestPlatformAdapter(account_id="pinterest:user:brand", token="token")
        report = adapter.capabilities()

        self.assertIsInstance(adapter, platform_adapters.PlatformAdapter)
        self.assertEqual(report.platform, "pinterest")
        self.assertTrue(report.can_import_history)
        self.assertTrue(report.can_refresh_metrics)
        self.assertFalse(report.can_fetch_comments)
        self.assertFalse(report.can_publish)
        self.assertIn("analytics", " ".join(report.notes).lower())

    def test_missing_token_fails_before_client_calls(self):
        pinterest_adapter = load_module("pinterest_adapter", MODULE_PATH)
        fake = FakePinterestClient()
        adapter = pinterest_adapter.PinterestPlatformAdapter(account_id="pinterest:user:brand", token=None, client=fake)

        with self.assertRaisesRegex(pinterest_adapter.PinterestAdapterCredentialError, "PINTEREST_ACCESS_TOKEN"):
            adapter.list_posts()

        self.assertEqual(fake.calls, [])

    def test_injected_client_drives_offline_paths(self):
        pinterest_adapter = load_module("pinterest_adapter", MODULE_PATH)
        fake = FakePinterestClient()
        adapter = pinterest_adapter.PinterestPlatformAdapter(account_id="pinterest:user:brand", token="token", client=fake)

        posts = adapter.list_posts()
        metrics = adapter.refresh_metrics("pin_100")
        comments = adapter.fetch_comments("pin_100")

        self.assertEqual(posts[0].platform_post_id, "pin_100")
        self.assertEqual(metrics.click_count, 65)
        self.assertEqual(comments, [])
        self.assertIn(("list_pins", "pinterest:user:brand"), fake.calls)


if __name__ == "__main__":
    unittest.main()
