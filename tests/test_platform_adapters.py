import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "platform_adapters.py"
SCHEMA_PATH = REPO_ROOT / "scripts" / "platform_schema.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PlatformAdaptersTests(unittest.TestCase):
    def test_normalized_post_converts_to_valid_schema_post(self) -> None:
        adapters = load_module("platform_adapters", MODULE_PATH)
        schema = load_module("platform_schema", SCHEMA_PATH)
        post = adapters.NormalizedPost(
            platform="reddit",
            account_id="reddit:u_example",
            platform_post_id="abc123",
            text="Forum post",
            created_at="2026-04-01T00:00:00+00:00",
            content_format="forum_post",
            metrics=adapters.NormalizedMetrics(reaction_count=5, comment_count=2),
            comments=[
                adapters.NormalizedComment(
                    platform="reddit",
                    account_id="reddit:u_example",
                    platform_comment_id="c1",
                    text="Comment",
                    created_at="2026-04-01T01:00:00+00:00",
                )
            ],
            platform_metadata={"reddit": {"raw": {"subreddit": "SEO"}}},
        )

        schema_post = adapters.normalized_post_to_schema_post(post)
        tracker = schema.build_platform_tracker(posts=[schema_post])

        schema.validate_platform_tracker(tracker)
        self.assertEqual(schema_post["platform"], "reddit")
        self.assertEqual(schema_post["metrics"]["reaction_count"], 5)
        self.assertEqual(schema_post["comments"][0]["platform_comment_id"], "c1")

    def test_memory_adapter_implements_common_contract(self) -> None:
        adapters = load_module("platform_adapters", MODULE_PATH)
        post = adapters.NormalizedPost(
            platform="threads",
            account_id="threads:@seo_lisa",
            platform_post_id="th_1",
            text="Threads post",
            created_at="2026-04-01T00:00:00+00:00",
            metrics=adapters.NormalizedMetrics(view_count=10),
        )
        adapter = adapters.MemoryPlatformAdapter(
            platform="threads",
            account_id="threads:@seo_lisa",
            posts=[post],
            capabilities=adapters.CapabilityReport(
                platform="threads",
                can_import_history=True,
                can_refresh_metrics=True,
                can_fetch_comments=True,
                can_publish=False,
            ),
        )

        self.assertIsInstance(adapter, adapters.PlatformAdapter)
        self.assertEqual(adapter.capabilities().platform, "threads")
        self.assertEqual(adapter.list_posts(), [post])
        self.assertEqual(adapter.refresh_metrics("th_1").view_count, 10)
        self.assertEqual(adapter.fetch_comments("th_1"), [])

    def test_read_only_publish_returns_unsupported_result(self) -> None:
        adapters = load_module("platform_adapters", MODULE_PATH)
        adapter = adapters.MemoryPlatformAdapter(
            platform="youtube",
            account_id="youtube:channel-1",
            posts=[],
            capabilities=adapters.CapabilityReport(platform="youtube", can_publish=False),
        )

        result = adapter.publish(text="Draft")

        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "unsupported")


if __name__ == "__main__":
    unittest.main()
