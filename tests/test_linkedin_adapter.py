import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "linkedin_adapter.py"
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


def linkedin_post_payload(post_id="urn:li:share:100"):
    return {
        "id": post_id,
        "author": "urn:li:organization:2414183",
        "commentary": "LinkedIn update about launch metrics.",
        "createdAt": 1775606400000,
        "visibility": "PUBLIC",
        "content": {"media": {"title": "Launch post"}},
    }


def linkedin_social_metadata_payload():
    return {
        "reactionSummaries": {
            "LIKE": {"count": 8},
            "PRAISE": {"count": 2},
        },
        "commentSummary": {"totalFirstLevelComments": 3},
        "shareCount": 1,
    }


def linkedin_comment_payload(comment_id="urn:li:comment:(urn:li:share:100,1)"):
    return {
        "id": comment_id,
        "actor": "urn:li:person:abc123",
        "message": {"text": "Useful breakdown."},
        "created": {"time": 1775606460000},
        "likesSummary": {"totalLikes": 4},
    }


class FakeLinkedInClient:
    def __init__(self):
        self.calls = []

    def list_posts(self, account_id, token):
        self.calls.append(("list_posts", account_id))
        return [linkedin_post_payload()]

    def fetch_post(self, post_urn, token):
        self.calls.append(("fetch_post", post_urn))
        return linkedin_post_payload(post_urn)

    def fetch_social_metadata(self, post_urn, token):
        self.calls.append(("fetch_social_metadata", post_urn))
        return linkedin_social_metadata_payload()

    def fetch_comments(self, post_urn, token):
        self.calls.append(("fetch_comments", post_urn))
        return [linkedin_comment_payload()]


class LinkedInAdapterTests(unittest.TestCase):
    def test_post_normalization_preserves_organization_identity_and_metrics(self):
        linkedin_adapter = load_module("linkedin_adapter", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)
        platform_schema = load_module("platform_schema", SCHEMA_PATH)

        normalized = linkedin_adapter.normalize_linkedin_post(
            linkedin_post_payload(),
            account_id="linkedin:organization:2414183",
            account_type="linkedin_organization",
            social_metadata=linkedin_social_metadata_payload(),
            comments=[linkedin_comment_payload()],
        )
        schema_post = platform_adapters.normalized_post_to_schema_post(normalized)

        platform_schema.validate_platform_tracker(platform_schema.build_platform_tracker(posts=[schema_post]))
        self.assertEqual(normalized.platform, "linkedin")
        self.assertEqual(normalized.metrics.reaction_count, 10)
        self.assertEqual(normalized.metrics.comment_count, 3)
        self.assertEqual(normalized.metrics.share_count, 1)
        self.assertEqual(normalized.platform_metadata["linkedin"]["account_type"], "linkedin_organization")
        self.assertEqual(normalized.platform_metadata["linkedin"]["author"], "urn:li:organization:2414183")
        self.assertEqual(normalized.comments[0].author_id, "urn:li:person:abc123")

    def test_post_normalization_preserves_member_identity(self):
        linkedin_adapter = load_module("linkedin_adapter", MODULE_PATH)

        payload = linkedin_post_payload("urn:li:ugcPost:200") | {"author": "urn:li:person:abc123"}
        normalized = linkedin_adapter.normalize_linkedin_post(
            payload,
            account_id="linkedin:person:abc123",
            account_type="linkedin_member",
        )

        self.assertEqual(normalized.platform_metadata["linkedin"]["account_type"], "linkedin_member")
        self.assertEqual(normalized.platform_metadata["linkedin"]["author"], "urn:li:person:abc123")
        self.assertEqual(normalized.platform_post_id, "urn:li:ugcPost:200")

    def test_capabilities_are_review_gated(self):
        linkedin_adapter = load_module("linkedin_adapter", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)

        adapter = linkedin_adapter.LinkedInPlatformAdapter(account_id="linkedin:organization:2414183", token="token")
        report = adapter.capabilities()

        self.assertIsInstance(adapter, platform_adapters.PlatformAdapter)
        self.assertEqual(report.platform, "linkedin")
        self.assertFalse(report.can_import_history)
        self.assertFalse(report.can_refresh_metrics)
        self.assertFalse(report.can_fetch_comments)
        self.assertFalse(report.can_publish)
        self.assertIn("review", " ".join(report.notes).lower())

    def test_missing_token_and_unconfirmed_access_fail_before_client_calls(self):
        linkedin_adapter = load_module("linkedin_adapter", MODULE_PATH)
        fake = FakeLinkedInClient()
        missing = linkedin_adapter.LinkedInPlatformAdapter(
            account_id="linkedin:organization:2414183",
            token=None,
            access_confirmed=True,
            client=fake,
        )
        gated = linkedin_adapter.LinkedInPlatformAdapter(
            account_id="linkedin:organization:2414183",
            token="token",
            access_confirmed=False,
            client=fake,
        )

        with self.assertRaisesRegex(linkedin_adapter.LinkedInAdapterCredentialError, "LINKEDIN_ACCESS_TOKEN"):
            missing.list_posts()
        with self.assertRaisesRegex(linkedin_adapter.LinkedInAdapterCapabilityError, "review"):
            gated.list_posts()

        self.assertEqual(fake.calls, [])

    def test_injected_client_drives_offline_paths_when_access_confirmed(self):
        linkedin_adapter = load_module("linkedin_adapter", MODULE_PATH)
        fake = FakeLinkedInClient()
        adapter = linkedin_adapter.LinkedInPlatformAdapter(
            account_id="linkedin:organization:2414183",
            account_type="linkedin_organization",
            token="token",
            access_confirmed=True,
            client=fake,
        )

        posts = adapter.list_posts()
        metrics = adapter.refresh_metrics("urn:li:share:100")
        comments = adapter.fetch_comments("urn:li:share:100")

        self.assertEqual(posts[0].platform_post_id, "urn:li:share:100")
        self.assertEqual(metrics.reaction_count, 10)
        self.assertEqual(comments[0].platform_comment_id, "urn:li:comment:(urn:li:share:100,1)")
        self.assertIn(("list_posts", "linkedin:organization:2414183"), fake.calls)


if __name__ == "__main__":
    unittest.main()
