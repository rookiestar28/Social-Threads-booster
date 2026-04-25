import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "scripts" / "youtube_adapter.py"
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


def youtube_video_payload(video_id: str = "yt_video_1") -> dict:
    return {
        "id": video_id,
        "snippet": {
            "title": "How to audit Core Web Vitals",
            "description": "A practical walkthrough",
            "publishedAt": "2026-04-04T00:00:00Z",
        },
        "statistics": {
            "viewCount": "2400",
            "likeCount": "120",
            "commentCount": "18",
        },
        "contentDetails": {"duration": "PT8M"},
    }


class FakeYouTubeDataClient:
    def __init__(self) -> None:
        self.calls = []

    def list_channel_videos(self, channel_id: str, token: str) -> list[dict]:
        self.calls.append(("list_channel_videos", channel_id))
        return [youtube_video_payload()]

    def fetch_video(self, video_id: str, token: str) -> dict:
        self.calls.append(("fetch_video", video_id))
        return youtube_video_payload(video_id)

    def fetch_comment_threads(self, video_id: str, token: str) -> list[dict]:
        self.calls.append(("fetch_comment_threads", video_id))
        return [
            {
                "id": "comment_thread_1",
                "snippet": {
                    "topLevelComment": {
                        "id": "yt_comment_1",
                        "snippet": {
                            "authorChannelId": {"value": "channel_reader"},
                            "textOriginal": "Helpful video.",
                            "publishedAt": "2026-04-04T01:00:00Z",
                            "likeCount": 3,
                        },
                    }
                },
            }
        ]


class FakeYouTubeAnalyticsClient:
    def __init__(self) -> None:
        self.calls = []

    def fetch_video_analytics(self, video_id: str, token: str) -> dict:
        self.calls.append(("fetch_video_analytics", video_id))
        return {
            "rows": [[video_id, 1600, 4]],
            "columnHeaders": [
                {"name": "video"},
                {"name": "estimatedMinutesWatched"},
                {"name": "shares"},
            ],
        }


class YouTubeAdapterTests(unittest.TestCase):
    def test_video_normalization_combines_public_stats_and_owned_analytics(self) -> None:
        youtube_adapter = load_module("youtube_adapter", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)
        platform_schema = load_module("platform_schema", SCHEMA_PATH)

        normalized = youtube_adapter.normalize_youtube_video(
            youtube_video_payload(),
            account_id="youtube:channel_1",
            analytics={
                "rows": [["yt_video_1", 1600, 4]],
                "columnHeaders": [
                    {"name": "video"},
                    {"name": "estimatedMinutesWatched"},
                    {"name": "shares"},
                ],
            },
            comments=[
                {
                    "id": "comment_thread_1",
                    "snippet": {
                        "topLevelComment": {
                            "id": "yt_comment_1",
                            "snippet": {
                                "authorChannelId": {"value": "channel_reader"},
                                "textOriginal": "Helpful video.",
                                "publishedAt": "2026-04-04T01:00:00Z",
                                "likeCount": 3,
                            },
                        }
                    },
                }
            ],
        )
        schema_post = platform_adapters.normalized_post_to_schema_post(normalized)

        platform_schema.validate_platform_tracker(platform_schema.build_platform_tracker(posts=[schema_post]))
        self.assertEqual(normalized.platform, "youtube")
        self.assertEqual(normalized.metrics.view_count, 2400)
        self.assertEqual(normalized.metrics.reaction_count, 120)
        self.assertEqual(normalized.metrics.comment_count, 18)
        self.assertEqual(normalized.metrics.share_count, 4)
        self.assertEqual(normalized.metrics.watch_time_seconds, 96000)
        self.assertEqual(normalized.comments[0].platform_comment_id, "yt_comment_1")

    def test_capabilities_reflect_split_public_and_owned_surfaces(self) -> None:
        youtube_adapter = load_module("youtube_adapter", MODULE_PATH)
        platform_adapters = load_module("platform_adapters", ADAPTERS_PATH)

        adapter = youtube_adapter.YouTubePlatformAdapter(channel_id="youtube:channel_1", token="token")
        report = adapter.capabilities()

        self.assertIsInstance(adapter, platform_adapters.PlatformAdapter)
        self.assertEqual(report.platform, "youtube")
        self.assertTrue(report.can_import_history)
        self.assertTrue(report.can_refresh_metrics)
        self.assertTrue(report.can_fetch_comments)
        self.assertFalse(report.can_publish)
        self.assertIn("watch_time_seconds", report.supported_metrics)

    def test_missing_token_fails_before_data_or_analytics_calls(self) -> None:
        youtube_adapter = load_module("youtube_adapter", MODULE_PATH)
        data_client = FakeYouTubeDataClient()
        analytics_client = FakeYouTubeAnalyticsClient()
        adapter = youtube_adapter.YouTubePlatformAdapter(
            channel_id="youtube:channel_1",
            token=None,
            data_client=data_client,
            analytics_client=analytics_client,
        )

        with self.assertRaisesRegex(youtube_adapter.YouTubeAdapterCredentialError, "YOUTUBE_OAUTH_TOKEN"):
            adapter.list_posts()

        self.assertEqual(data_client.calls, [])
        self.assertEqual(analytics_client.calls, [])

    def test_injected_clients_drive_offline_list_refresh_and_comments(self) -> None:
        youtube_adapter = load_module("youtube_adapter", MODULE_PATH)
        data_client = FakeYouTubeDataClient()
        analytics_client = FakeYouTubeAnalyticsClient()
        adapter = youtube_adapter.YouTubePlatformAdapter(
            channel_id="youtube:channel_1",
            token="token",
            data_client=data_client,
            analytics_client=analytics_client,
        )

        posts = adapter.list_posts()
        metrics = adapter.refresh_metrics("yt_video_1")
        comments = adapter.fetch_comments("yt_video_1")

        self.assertEqual(posts[0].platform_post_id, "yt_video_1")
        self.assertEqual(posts[0].metrics.watch_time_seconds, 96000)
        self.assertEqual(metrics.share_count, 4)
        self.assertEqual(comments[0].author_id, "channel_reader")
        self.assertIn(("list_channel_videos", "youtube:channel_1"), data_client.calls)
        self.assertIn(("fetch_video_analytics", "yt_video_1"), analytics_client.calls)

    def test_publish_text_is_not_available_for_youtube_adapter(self) -> None:
        youtube_adapter = load_module("youtube_adapter", MODULE_PATH)
        adapter = youtube_adapter.YouTubePlatformAdapter(channel_id="youtube:channel_1", token="token")

        result = adapter.publish("Text-only post")

        self.assertFalse(result.ok)
        self.assertEqual(result.reason, "unsupported")


if __name__ == "__main__":
    unittest.main()
