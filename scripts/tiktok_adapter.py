#!/usr/bin/env python3
"""
TikTok adapter with conservative product-specific operation boundaries.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
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
except ImportError:  # pragma: no cover
    requests = None


POLICY_PATH = REPO_ROOT / "knowledge" / "platform_api_policy.json"
TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"


class TikTokAdapterCredentialError(ValueError):
    """Raised when TikTok adapter operations need credentials."""


class TikTokAdapterCapabilityError(ValueError):
    """Raised when TikTok adapter operations need product access confirmation."""


class TikTokClient(Protocol):
    def list_videos(self, account_id: str, token: str) -> list[dict]:
        ...

    def fetch_video(self, video_id: str, token: str) -> dict:
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


def _timestamp_to_iso(value: Any) -> str:
    number = _to_number(value)
    if number is not None:
        seconds = number / 1000 if number > 10_000_000_000 else number
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
    if isinstance(value, str):
        return value
    return ""


def _video_id(video: dict[str, Any]) -> str:
    return str(video.get("id") or video.get("video_id") or "").strip()


def _video_text(video: dict[str, Any]) -> str:
    parts = [str(video.get(key) or "").strip() for key in ("title", "video_description", "description", "caption")]
    return "\n\n".join(part for part in parts if part)


def tiktok_metrics(video: dict[str, Any]) -> NormalizedMetrics:
    return NormalizedMetrics(
        view_count=_to_number(video.get("view_count") or video.get("views")),
        reaction_count=_to_number(video.get("like_count") or video.get("likes")),
        comment_count=_to_number(video.get("comment_count") or video.get("comments")),
        share_count=_to_number(video.get("share_count") or video.get("shares")),
    )


def normalize_tiktok_video(
    video: dict[str, Any],
    *,
    account_id: str,
    product_surface: str,
) -> NormalizedPost:
    video_id = _video_id(video)
    if not video_id:
        raise ValueError("TikTok video id is required")
    author = video.get("username") or video.get("author") or video.get("creator_id")
    return NormalizedPost(
        platform="tiktok",
        account_id=account_id,
        platform_post_id=video_id,
        canonical_post_id=f"tiktok:{account_id}:{video_id}",
        text=_video_text(video),
        created_at=_timestamp_to_iso(video.get("create_time") or video.get("created_at") or video.get("createdAt")),
        content_format="video",
        url=video.get("share_url") or video.get("embed_link") or video.get("url"),
        metrics=tiktok_metrics(video),
        comments=[],
        source={"type": "adapter", "data_completeness": "partial"},
        platform_metadata={
            "tiktok": {
                "product_surface": product_surface,
                "author": author,
                "media": {
                    "cover_image_url": video.get("cover_image_url") or video.get("cover_url"),
                    "duration": _to_number(video.get("duration")),
                },
                "raw": {"video": dict(video)},
            }
        },
    )


@dataclass(frozen=True)
class RequestsTikTokClient:
    """Thin TikTok Display API client for optional live smoke paths."""

    fields: tuple[str, ...] = (
        "id",
        "title",
        "video_description",
        "create_time",
        "share_url",
        "cover_image_url",
        "duration",
        "view_count",
        "like_count",
        "comment_count",
        "share_count",
    )

    def _post(self, path: str, *, token: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests package is required for live TikTok API calls")
        resp = requests.post(
            f"{TIKTOK_API_BASE}/{path.lstrip('/')}",
            params={"fields": ",".join(self.fields)},
            json=body or {},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def list_videos(self, account_id: str, token: str) -> list[dict]:
        payload = self._post("video/list/", token=token, body={"max_count": 20})
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        return list(data.get("videos") or [])

    def fetch_video(self, video_id: str, token: str) -> dict:
        payload = self._post("video/query/", token=token, body={"filters": {"video_ids": [video_id]}})
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        videos = data.get("videos") or []
        if not videos:
            raise KeyError(f"TikTok video not found: {video_id}")
        return dict(videos[0])


class TikTokPlatformAdapter:
    platform = "tiktok"

    def __init__(
        self,
        *,
        account_id: str,
        product_surface: str = "display_api",
        token: str | None = None,
        token_file: str | None = None,
        access_confirmed: bool = False,
        client: TikTokClient | None = None,
        policy_path: str | Path = POLICY_PATH,
    ) -> None:
        self.account_id = account_id
        self.product_surface = product_surface
        self._token = token
        self._token_file = token_file
        self._access_confirmed = access_confirmed
        self._client = client or RequestsTikTokClient()
        self._policy_path = Path(policy_path)

    def _resolve_token(self) -> str:
        try:
            source = resolve_credential(
                label="TikTok access token",
                direct_value=self._token,
                direct_source_name="TikTokPlatformAdapter(token=...)",
                env_var="TIKTOK_ACCESS_TOKEN",
                file_path=self._token_file,
            )
        except CredentialSourceError as exc:
            raise TikTokAdapterCredentialError(str(exc)) from exc
        if not source.value:
            raise TikTokAdapterCredentialError(
                "missing TikTok access token; set TIKTOK_ACCESS_TOKEN or pass token_file"
            )
        return source.value

    def _authorize_operation(self) -> str:
        token = self._resolve_token()
        if not self._access_confirmed:
            raise TikTokAdapterCapabilityError(
                "TikTok operation is product-specific; pass access_confirmed=True after verifying approved product access"
            )
        return token

    def capabilities(self) -> CapabilityReport:
        registry = CapabilityRegistry.from_policy_file(self._policy_path)
        read_posts = registry.decide("tiktok", "read_posts")
        read_comments = registry.decide("tiktok", "read_comments")
        refresh = registry.decide("tiktok", "refresh_snapshots")
        insights = registry.decide("tiktok", "read_owned_insights")
        publish = registry.decide("tiktok", "publish_media")
        return CapabilityReport(
            platform="tiktok",
            can_import_history=False,
            can_refresh_metrics=False,
            can_fetch_comments=False,
            can_publish=False,
            supported_metrics=("view_count", "reaction_count", "comment_count", "share_count"),
            auth_required=True,
            notes=(
                f"product surface: {self.product_surface}",
                f"read_posts: {read_posts.status.replace('_', '-')} ({read_posts.gate})",
                f"read_comments: {read_comments.status.replace('_', '-')} ({read_comments.gate})",
                f"refresh_snapshots: {refresh.status.replace('_', '-')} ({refresh.gate})",
                f"owned_insights: {insights.status.replace('_', '-')} ({insights.gate})",
                f"publish_media: {publish.status.replace('_', '-')} ({publish.gate})",
            ),
        )

    def list_posts(self) -> list[NormalizedPost]:
        token = self._authorize_operation()
        return [
            normalize_tiktok_video(video, account_id=self.account_id, product_surface=self.product_surface)
            for video in self._client.list_videos(self.account_id, token)
            if isinstance(video, dict)
        ]

    def refresh_metrics(self, platform_post_id: str) -> NormalizedMetrics:
        token = self._authorize_operation()
        return tiktok_metrics(self._client.fetch_video(platform_post_id, token))

    def fetch_comments(self, platform_post_id: str) -> list[NormalizedComment]:
        return []

    def publish(self, text: str, **kwargs: Any) -> PublishResult:
        decision = CapabilityRegistry.from_policy_file(self._policy_path).decide("tiktok", "publish_media")
        return PublishResult(ok=False, platform="tiktok", reason="review_required", detail=decision.gate)


__all__ = [
    "RequestsTikTokClient",
    "TikTokAdapterCapabilityError",
    "TikTokAdapterCredentialError",
    "TikTokClient",
    "TikTokPlatformAdapter",
    "normalize_tiktok_video",
    "tiktok_metrics",
]
