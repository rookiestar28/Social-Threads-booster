import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "open_network_adapters.py"
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


def bluesky_post_payload(uri: str = "at://did:plc:example/app.bsky.feed.post/1") -> dict:
    return {
        "uri": uri,
        "cid": "bafyfixture",
        "record": {"text": "Open network post", "createdAt": "2026-04-06T00:00:00Z"},
        "likeCount": 9,
        "replyCount": 2,
        "repostCount": 4,
    }


def mastodon_status_payload(status_id: str = "md_status_1") -> dict:
    return {
        "id": status_id,
        "content": "<p>Federated post about evergreen content.</p>",
        "created_at": "2026-04-07T00:00:00Z",
        "url": f"https://mastodon.social/@seo_lisa/{status_id}",
        "favourites_count": 11,
        "replies_count": 1,
        "reblogs_count": 3,
        "visibility": "public",
    }


class FakeBlueskyClient:
    def __init__(self) -> None:
        self.calls = []

    def list_actor_posts(self, actor: str, token: str) -> list[dict]:
        self.calls.append(("list_actor_posts", actor))
        return [bluesky_post_payload()]

    def fetch_post(self, uri: str, token: str) -> dict:
        self.calls.append(("fetch_post", uri))
        return bluesky_post_payload(uri)

    def fetch_replies(self, uri: str, token: str) -> list[dict]:
        self.calls.append(("fetch_replies", uri))
        return [
            {
                "uri": f"{uri}/reply/1",
                "record": {"text": "Useful ATProto note.", "createdAt": "2026-04-06T01:00:00Z"},
                "author": {"did": "did:plc:reader"},
                "likeCount": 1,
            }
        ]


class FakeMastodonClient:
    def __init__(self) -> None:
        self.calls = []

    def list_account_statuses(self, account_id: str, token: str, instance_url: str) -> list[dict]:
        self.calls.append(("list_account_statuses", account_id, instance_url))
        return [mastodon_status_payload()]

    def fetch_status(self, status_id: str, token: str, instance_url: str) -> dict:
        self.calls.append(("fetch_status", status_id, instance_url))
        return mastodon_status_payload(status_id)

    def fetch_replies(self, status_id: str, token: str, instance_url: str) -> list[dict]:
        self.calls.append(("fetch_replies", status_id, instance_url))
        return [
            {
                "id": "md_reply_1",
                "content": "<p>Good reminder.</p>",
                "created_at": "2026-04-07T01:00:00Z",
                "account": {"id": "reader"},
                "favourites_count": 2,
            }
        ]


class OpenNetworkAdaptersTests(unittest.TestCase):
    def test_bluesky_normalization_uses_atproto_identity_and_public_counts(self) -> None:
        module = load_module("open_network_adapters", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)
        platform_schema = load_module("platform_schema", SCHEMA_PATH)

        normalized = module.normalize_bluesky_post(
            bluesky_post_payload(),
            account_id="bluesky:seo-lisa.bsky.social",
            replies=[
                {
                    "uri": "at://did:reply",
                    "record": {"text": "Reply", "createdAt": "2026-04-06T01:00:00Z"},
                    "author": {"did": "did:plc:reader"},
                    "likeCount": 1,
                }
            ],
        )
        schema_post = platform_adapters.normalized_post_to_schema_post(normalized)

        platform_schema.validate_platform_tracker(platform_schema.build_platform_tracker(posts=[schema_post]))
        self.assertEqual(normalized.platform, "bluesky")
        self.assertIsNone(normalized.metrics.view_count)
        self.assertEqual(normalized.metrics.reaction_count, 9)
        self.assertEqual(normalized.metrics.comment_count, 2)
        self.assertEqual(normalized.metrics.share_count, 4)
        self.assertEqual(normalized.comments[0].author_id, "did:plc:reader")
        self.assertEqual(normalized.platform_metadata["bluesky"]["raw"]["post"]["cid"], "bafyfixture")

    def test_mastodon_normalization_keeps_instance_specific_identity(self) -> None:
        module = load_module("open_network_adapters", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)
        platform_schema = load_module("platform_schema", SCHEMA_PATH)

        normalized = module.normalize_mastodon_status(
            mastodon_status_payload(),
            account_id="mastodon:https://mastodon.social/@seo_lisa",
            instance_url="https://mastodon.social",
            replies=[
                {
                    "id": "md_reply_1",
                    "content": "<p>Good reminder.</p>",
                    "created_at": "2026-04-07T01:00:00Z",
                    "account": {"id": "reader"},
                    "favourites_count": 2,
                }
            ],
        )
        schema_post = platform_adapters.normalized_post_to_schema_post(normalized)

        platform_schema.validate_platform_tracker(platform_schema.build_platform_tracker(posts=[schema_post]))
        self.assertEqual(normalized.platform, "mastodon")
        self.assertEqual(normalized.text, "Federated post about evergreen content.")
        self.assertEqual(normalized.metrics.reaction_count, 11)
        self.assertEqual(normalized.metrics.comment_count, 1)
        self.assertEqual(normalized.metrics.share_count, 3)
        self.assertEqual(normalized.platform_metadata["mastodon"]["raw"]["instance_url"], "https://mastodon.social")

    def test_capabilities_cover_both_open_network_adapters(self) -> None:
        module = load_module("open_network_adapters", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)

        bluesky = module.BlueskyPlatformAdapter(actor="seo-lisa.bsky.social", token="token")
        mastodon = module.MastodonPlatformAdapter(
            account_id="mastodon:https://mastodon.social/@seo_lisa",
            instance_url="https://mastodon.social",
            token="token",
        )

        self.assertIsInstance(bluesky, platform_adapters.PlatformAdapter)
        self.assertIsInstance(mastodon, platform_adapters.PlatformAdapter)
        self.assertEqual(bluesky.capabilities().platform, "bluesky")
        self.assertEqual(mastodon.capabilities().platform, "mastodon")
        self.assertTrue(bluesky.capabilities().can_refresh_metrics)
        self.assertTrue(mastodon.capabilities().can_fetch_comments)

    def test_missing_tokens_fail_before_client_calls(self) -> None:
        module = load_module("open_network_adapters", MODULE_PATH)
        bluesky_client = FakeBlueskyClient()
        mastodon_client = FakeMastodonClient()

        bluesky = module.BlueskyPlatformAdapter(actor="seo-lisa.bsky.social", token=None, client=bluesky_client)
        mastodon = module.MastodonPlatformAdapter(
            account_id="mastodon:https://mastodon.social/@seo_lisa",
            instance_url="https://mastodon.social",
            token=None,
            client=mastodon_client,
        )

        with self.assertRaisesRegex(module.OpenNetworkAdapterCredentialError, "BSKY_APP_PASSWORD"):
            bluesky.list_posts()
        with self.assertRaisesRegex(module.OpenNetworkAdapterCredentialError, "MASTODON_OAUTH_TOKEN"):
            mastodon.list_posts()

        self.assertEqual(bluesky_client.calls, [])
        self.assertEqual(mastodon_client.calls, [])

    def test_injected_clients_drive_offline_paths(self) -> None:
        module = load_module("open_network_adapters", MODULE_PATH)
        bluesky_client = FakeBlueskyClient()
        mastodon_client = FakeMastodonClient()
        bluesky = module.BlueskyPlatformAdapter(actor="seo-lisa.bsky.social", token="token", client=bluesky_client)
        mastodon = module.MastodonPlatformAdapter(
            account_id="mastodon:https://mastodon.social/@seo_lisa",
            instance_url="https://mastodon.social",
            token="token",
            client=mastodon_client,
        )

        b_posts = bluesky.list_posts()
        b_metrics = bluesky.refresh_metrics("at://did:plc:example/app.bsky.feed.post/1")
        m_posts = mastodon.list_posts()
        m_comments = mastodon.fetch_comments("md_status_1")

        self.assertEqual(b_posts[0].platform_post_id, "at://did:plc:example/app.bsky.feed.post/1")
        self.assertEqual(b_metrics.share_count, 4)
        self.assertEqual(m_posts[0].platform_post_id, "md_status_1")
        self.assertEqual(m_comments[0].platform_comment_id, "md_reply_1")
        self.assertIn(("list_actor_posts", "seo-lisa.bsky.social"), bluesky_client.calls)
        self.assertIn(("list_account_statuses", "mastodon:https://mastodon.social/@seo_lisa", "https://mastodon.social"), mastodon_client.calls)


if __name__ == "__main__":
    unittest.main()
