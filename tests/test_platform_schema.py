import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "platform_schema.py"


def load_module():
    spec = importlib.util.spec_from_file_location("platform_schema", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load platform_schema module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PlatformSchemaTests(unittest.TestCase):
    def test_build_platform_tracker_validates_five_platform_shapes(self) -> None:
        schema = load_module()
        posts = [
            schema.build_platform_post(
                platform="threads",
                account_id="threads:@seo_lisa",
                platform_post_id="th_1",
                text="Threads text post",
                created_at="2026-04-01T00:00:00+00:00",
                metrics={"view_count": 100, "reaction_count": 10, "comment_count": 2, "share_count": 1},
                platform_metadata={"threads": {"raw": {"media_type": "TEXT"}}},
            ),
            schema.build_platform_post(
                platform="youtube",
                account_id="youtube:channel-1",
                platform_post_id="video_1",
                text="Video title",
                created_at="2026-04-02T00:00:00+00:00",
                content_format="video",
                metrics={"view_count": 1000, "reaction_count": 50, "comment_count": 5},
                platform_metadata={"youtube": {"raw": {"duration": "PT3M"}}},
            ),
            schema.build_platform_post(
                platform="reddit",
                account_id="reddit:u_example",
                platform_post_id="submission_1",
                text="Forum submission",
                created_at="2026-04-03T00:00:00+00:00",
                content_format="forum_post",
                metrics={"reaction_count": 25, "comment_count": 9},
                platform_metadata={"reddit": {"raw": {"subreddit": "SEO"}}},
            ),
            schema.build_platform_post(
                platform="bluesky",
                account_id="bluesky:example.bsky.social",
                platform_post_id="at://did/post/1",
                text="Open-network post",
                created_at="2026-04-04T00:00:00+00:00",
                metrics={"reaction_count": 7, "share_count": 3, "comment_count": 1},
                platform_metadata={"bluesky": {"raw": {"uri": "at://did/post/1"}}},
            ),
            schema.build_platform_post(
                platform="linkedin",
                account_id="linkedin:org-1",
                platform_post_id="urn:li:share:1",
                text="Professional update",
                created_at="2026-04-05T00:00:00+00:00",
                metrics={"view_count": None, "reaction_count": 8, "comment_count": 2, "share_count": None},
                platform_metadata={"linkedin": {"raw": {"author_type": "organization"}}},
            ),
        ]

        tracker = schema.build_platform_tracker(accounts=[{"platform": "threads", "account_id": "threads:@seo_lisa"}], posts=posts)

        schema.validate_platform_tracker(tracker)
        self.assertEqual(tracker["schema_version"], 2)
        self.assertEqual(tracker["tracker_type"], "platform-neutral")
        self.assertEqual(len(tracker["posts"]), 5)

    def test_unavailable_metrics_remain_null(self) -> None:
        schema = load_module()

        metrics = schema.build_platform_metrics({"view_count": None, "reaction_count": 4})

        self.assertIsNone(metrics["view_count"])
        self.assertEqual(metrics["reaction_count"], 4)
        self.assertIsNone(metrics["share_count"])

    def test_validate_rejects_inline_secret_metadata(self) -> None:
        schema = load_module()
        tracker = schema.build_platform_tracker(
            posts=[
                schema.build_platform_post(
                    platform="threads",
                    account_id="threads:@seo_lisa",
                    platform_post_id="th_secret",
                    text="Bad metadata",
                    created_at="2026-04-01T00:00:00+00:00",
                    platform_metadata={"threads": {"access_token": "secret"}},
                )
            ]
        )

        with self.assertRaisesRegex(schema.PlatformTrackerValidationError, "platform_metadata"):
            schema.validate_platform_tracker(tracker)

    def test_validate_requires_platform_identity_fields(self) -> None:
        schema = load_module()
        post = schema.build_platform_post(
            platform="threads",
            account_id="threads:@seo_lisa",
            platform_post_id="th_1",
            text="Post",
            created_at="2026-04-01T00:00:00+00:00",
        )
        del post["canonical_post_id"]
        tracker = schema.build_platform_tracker(posts=[post])

        with self.assertRaisesRegex(schema.PlatformTrackerValidationError, r"posts\[0\]\.canonical_post_id"):
            schema.validate_platform_tracker(tracker)


if __name__ == "__main__":
    unittest.main()
