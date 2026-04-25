#!/usr/bin/env python3
"""
YouTube platform adapter with separate Data API and Analytics API clients.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from capability_registry import CapabilityRegistry
from credential_sources import CredentialSourceError, resolve_credential
from platform_adapters import CapabilityReport, NormalizedComment, NormalizedMetrics, NormalizedPost, PublishResult

try:
    import requests
except ImportError:  # pragma: no cover - dependency is installed through scripts/requirements.txt
    requests = None


POLICY_PATH = REPO_ROOT / "knowledge" / "platform_api_policy.json"
YOUTUBE_DATA_BASE = "https://www.googleapis.com/youtube/v3"
YOUTUBE_ANALYTICS_BASE = "https://youtubeanalytics.googleapis.com/v2"


class YouTubeAdapterCredentialError(ValueError):
    """Raised when YouTube adapter operations need credentials."""


class YouTubeDataClient(Protocol):
    def list_channel_videos(self, channel_id: str, token: str) -> list[dict]:
        ...

    def fetch_video(self, video_id: str, token: str) -> dict:
        ...

    def fetch_comment_threads(self, video_id: str, token: str) -> list[dict]:
        ...


class YouTubeAnalyticsClient(Protocol):
    def fetch_video_analytics(self, video_id: str, token: str) -> dict:
        ...


def _to_number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str) and value.strip():
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return None
    return None


def _first_number(*values: Any) -> int | float | None:
    for value in values:
        number = _to_number(value)
        if number is not None:
            return number
    return None


def _analytics_values(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    if "rows" not in payload:
        return dict(payload)
    rows = payload.get("rows") or []
    headers = payload.get("columnHeaders") or []
    if not rows or not headers:
        return {}
    names = [str(header.get("name") or "") for header in headers if isinstance(header, dict)]
    first_row = rows[0]
    return {name: first_row[index] for index, name in enumerate(names) if index < len(first_row)}


@dataclass(frozen=True)
class RequestsYouTubeDataClient:
    """Thin YouTube Data API client for live smoke paths."""

    def _get(self, path: str, *, token: str, params: dict[str, Any]) -> dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests package is required for live YouTube Data API calls")
        resp = requests.get(
            f"{YOUTUBE_DATA_BASE}/{path.lstrip('/')}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def list_channel_videos(self, channel_id: str, token: str) -> list[dict]:
        search = self._get(
            "search",
            token=token,
            params={"part": "id", "channelId": channel_id, "type": "video", "maxResults": 50, "order": "date"},
        )
        ids = [
            str((item.get("id") or {}).get("videoId"))
            for item in search.get("items") or []
            if isinstance(item, dict) and (item.get("id") or {}).get("videoId")
        ]
        if not ids:
            return []
        videos = self._get(
            "videos",
            token=token,
            params={"part": "snippet,statistics,contentDetails", "id": ",".join(ids), "maxResults": 50},
        )
        return list(videos.get("items") or [])

    def fetch_video(self, video_id: str, token: str) -> dict:
        payload = self._get(
            "videos",
            token=token,
            params={"part": "snippet,statistics,contentDetails", "id": video_id},
        )
        items = payload.get("items") or []
        if not items:
            raise KeyError(f"YouTube video not found: {video_id}")
        return dict(items[0])

    def fetch_comment_threads(self, video_id: str, token: str) -> list[dict]:
        payload = self._get(
            "commentThreads",
            token=token,
            params={"part": "snippet", "videoId": video_id, "maxResults": 100, "textFormat": "plainText"},
        )
        return list(payload.get("items") or [])


@dataclass(frozen=True)
class RequestsYouTubeAnalyticsClient:
    """Thin YouTube Analytics API client for owned-channel metrics."""

    def fetch_video_analytics(self, video_id: str, token: str) -> dict:
        if requests is None:
            raise RuntimeError("requests package is required for live YouTube Analytics API calls")
        resp = requests.get(
            f"{YOUTUBE_ANALYTICS_BASE}/reports",
            params={
                "ids": "channel==MINE",
                "startDate": "2006-01-01",
                "endDate": "2099-12-31",
                "metrics": "estimatedMinutesWatched,shares",
                "dimensions": "video",
                "filters": f"video=={video_id}",
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


def youtube_metrics(video: dict[str, Any], analytics: dict[str, Any] | None = None) -> NormalizedMetrics:
    stats = video.get("statistics") if isinstance(video.get("statistics"), dict) else {}
    analytics_values = _analytics_values(analytics)
    minutes_watched = _first_number(analytics_values.get("estimatedMinutesWatched"), analytics_values.get("watchTimeMinutes"))
    watch_time_seconds = minutes_watched * 60 if minutes_watched is not None else None
    return NormalizedMetrics(
        view_count=_first_number(stats.get("viewCount"), video.get("view_count")),
        reaction_count=_first_number(stats.get("likeCount"), video.get("reaction_count")),
        comment_count=_first_number(stats.get("commentCount"), video.get("comment_count")),
        share_count=_first_number(analytics_values.get("shares"), video.get("share_count")),
        watch_time_seconds=watch_time_seconds,
    )


def _top_level_comment_payload(thread: dict[str, Any]) -> dict[str, Any]:
    snippet = thread.get("snippet") if isinstance(thread.get("snippet"), dict) else {}
    top_level = snippet.get("topLevelComment") if isinstance(snippet.get("topLevelComment"), dict) else {}
    return top_level


def normalize_youtube_comment(thread: dict[str, Any], *, account_id: str, video_id: str, index: int = 0) -> NormalizedComment:
    top_level = _top_level_comment_payload(thread)
    comment_snippet = top_level.get("snippet") if isinstance(top_level.get("snippet"), dict) else {}
    comment_id = str(top_level.get("id") or thread.get("id") or f"{video_id}:comment:{index}")
    author_channel = comment_snippet.get("authorChannelId") if isinstance(comment_snippet.get("authorChannelId"), dict) else {}
    return NormalizedComment(
        platform="youtube",
        account_id=account_id,
        platform_comment_id=comment_id,
        text=str(comment_snippet.get("textOriginal") or comment_snippet.get("textDisplay") or ""),
        created_at=str(comment_snippet.get("publishedAt") or ""),
        author_id=author_channel.get("value") or comment_snippet.get("authorChannelUrl"),
        metrics=NormalizedMetrics(reaction_count=_first_number(comment_snippet.get("likeCount"))),
        platform_metadata={"youtube": {"raw": dict(thread)}},
    )


def normalize_youtube_video(
    video: dict[str, Any],
    *,
    account_id: str,
    analytics: dict[str, Any] | None = None,
    comments: list[dict[str, Any]] | None = None,
) -> NormalizedPost:
    video_id = str(video.get("id", "")).strip()
    if not video_id:
        raise ValueError("YouTube video id is required")
    snippet = video.get("snippet") if isinstance(video.get("snippet"), dict) else {}
    normalized_comments = [
        normalize_youtube_comment(comment, account_id=account_id, video_id=video_id, index=index)
        for index, comment in enumerate(comments or [])
        if isinstance(comment, dict)
    ]
    title = str(snippet.get("title") or video.get("title") or "")
    description = str(snippet.get("description") or "")
    text = title if not description else f"{title}\n\n{description}"
    return NormalizedPost(
        platform="youtube",
        account_id=account_id,
        platform_post_id=video_id,
        canonical_post_id=f"youtube:{account_id}:{video_id}",
        text=text,
        created_at=str(snippet.get("publishedAt") or video.get("created_at") or ""),
        content_format="video",
        url=f"https://www.youtube.com/watch?v={video_id}",
        metrics=youtube_metrics(video, analytics),
        comments=normalized_comments,
        source={"type": "adapter", "data_completeness": "full" if analytics is not None else "partial"},
        platform_metadata={"youtube": {"raw": {"video": dict(video), "analytics": dict(analytics or {})}}},
    )


class YouTubePlatformAdapter:
    platform = "youtube"

    def __init__(
        self,
        *,
        channel_id: str,
        token: str | None = None,
        token_file: str | None = None,
        data_client: YouTubeDataClient | None = None,
        analytics_client: YouTubeAnalyticsClient | None = None,
        policy_path: str | Path = POLICY_PATH,
    ) -> None:
        self.account_id = channel_id
        self.channel_id = channel_id
        self._token = token
        self._token_file = token_file
        self._data_client = data_client or RequestsYouTubeDataClient()
        self._analytics_client = analytics_client or RequestsYouTubeAnalyticsClient()
        self._policy_path = Path(policy_path)

    def _resolve_token(self) -> str:
        try:
            source = resolve_credential(
                label="YouTube OAuth token",
                direct_value=self._token,
                direct_source_name="YouTubePlatformAdapter(token=...)",
                env_var="YOUTUBE_OAUTH_TOKEN",
                file_path=self._token_file,
            )
        except CredentialSourceError as exc:
            raise YouTubeAdapterCredentialError(str(exc)) from exc
        if not source.value:
            raise YouTubeAdapterCredentialError(
                "missing YouTube OAuth token; set YOUTUBE_OAUTH_TOKEN or pass token_file"
            )
        return source.value

    def capabilities(self) -> CapabilityReport:
        registry = CapabilityRegistry.from_policy_file(self._policy_path)
        read_posts = registry.decide("youtube", "read_posts")
        read_comments = registry.decide("youtube", "read_comments")
        refresh = registry.decide("youtube", "refresh_snapshots")
        analytics = registry.decide("youtube", "read_owned_insights")
        publish = registry.decide("youtube", "publish_text")
        return CapabilityReport(
            platform="youtube",
            can_import_history=read_posts.allowed,
            can_refresh_metrics=refresh.allowed,
            can_fetch_comments=read_comments.allowed,
            can_publish=False,
            supported_metrics=("view_count", "reaction_count", "comment_count", "share_count", "watch_time_seconds"),
            auth_required=True,
            notes=(read_posts.gate, read_comments.gate, refresh.gate, analytics.gate, f"publish_text: {publish.status} ({publish.gate})"),
        )

    def list_posts(self) -> list[NormalizedPost]:
        token = self._resolve_token()
        posts = []
        for video in self._data_client.list_channel_videos(self.channel_id, token):
            video_id = str(video.get("id", ""))
            analytics = self._analytics_client.fetch_video_analytics(video_id, token)
            comments = self._data_client.fetch_comment_threads(video_id, token)
            posts.append(normalize_youtube_video(video, account_id=self.account_id, analytics=analytics, comments=comments))
        return posts

    def refresh_metrics(self, platform_post_id: str) -> NormalizedMetrics:
        token = self._resolve_token()
        video = self._data_client.fetch_video(platform_post_id, token)
        analytics = self._analytics_client.fetch_video_analytics(platform_post_id, token)
        return youtube_metrics(video, analytics)

    def fetch_comments(self, platform_post_id: str) -> list[NormalizedComment]:
        token = self._resolve_token()
        return [
            normalize_youtube_comment(thread, account_id=self.account_id, video_id=platform_post_id, index=index)
            for index, thread in enumerate(self._data_client.fetch_comment_threads(platform_post_id, token))
            if isinstance(thread, dict)
        ]

    def publish(self, text: str, **kwargs: Any) -> PublishResult:
        decision = CapabilityRegistry.from_policy_file(self._policy_path).decide("youtube", "publish_text")
        return PublishResult(ok=False, platform="youtube", reason="unsupported", detail=decision.gate)


__all__ = [
    "RequestsYouTubeAnalyticsClient",
    "RequestsYouTubeDataClient",
    "YouTubeAdapterCredentialError",
    "YouTubeAnalyticsClient",
    "YouTubeDataClient",
    "YouTubePlatformAdapter",
    "normalize_youtube_comment",
    "normalize_youtube_video",
    "youtube_metrics",
]
