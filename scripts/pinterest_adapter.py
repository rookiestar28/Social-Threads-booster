#!/usr/bin/env python3
"""
Pinterest platform adapter for owned Pin and board-shaped data.
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
except ImportError:  # pragma: no cover
    requests = None


POLICY_PATH = REPO_ROOT / "knowledge" / "platform_api_policy.json"
PINTEREST_API_BASE = "https://api.pinterest.com/v5"


class PinterestAdapterCredentialError(ValueError):
    """Raised when Pinterest adapter operations need credentials."""


class PinterestClient(Protocol):
    def list_pins(self, account_id: str, token: str) -> list[dict]:
        ...

    def fetch_pin(self, pin_id: str, token: str) -> dict:
        ...

    def fetch_pin_analytics(self, pin_id: str, token: str) -> dict:
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


def _metric(payload: dict[str, Any], *names: str) -> int | float | None:
    for name in names:
        number = _to_number(payload.get(name))
        if number is not None:
            return number
    return None


def _analytics_bucket(analytics: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(analytics, dict):
        return {}
    if isinstance(analytics.get("all"), dict):
        return dict(analytics["all"])
    if isinstance(analytics.get("summary_metrics"), dict):
        return dict(analytics["summary_metrics"])
    return dict(analytics)


def _pin_text(pin: dict[str, Any]) -> str:
    parts = [str(pin.get(key) or "").strip() for key in ("title", "description", "alt_text")]
    return "\n\n".join(part for part in parts if part)


def _pin_media(pin: dict[str, Any]) -> dict[str, Any]:
    media = pin.get("media") if isinstance(pin.get("media"), dict) else {}
    images = media.get("images") if isinstance(media.get("images"), dict) else {}
    image_url = None
    for value in images.values():
        if isinstance(value, dict) and value.get("url"):
            image_url = value.get("url")
            break
    return {
        "media_type": media.get("media_type") or media.get("type"),
        "url": media.get("url") or image_url,
    }


def pinterest_metrics(analytics: dict[str, Any] | None) -> NormalizedMetrics:
    bucket = _analytics_bucket(analytics)
    pin_click = _metric(bucket, "PIN_CLICK", "PIN_CLICKS", "pin_click")
    outbound_click = _metric(bucket, "OUTBOUND_CLICK", "OUTBOUND_CLICKS", "outbound_click")
    click_count = None
    if pin_click is not None or outbound_click is not None:
        click_count = (pin_click or 0) + (outbound_click or 0)
    return NormalizedMetrics(
        view_count=_metric(bucket, "IMPRESSION", "IMPRESSIONS", "impression"),
        reaction_count=_metric(bucket, "ENGAGEMENT", "ENGAGEMENTS", "engagement"),
        save_count=_metric(bucket, "SAVE", "SAVES", "save"),
        click_count=click_count,
    )


def normalize_pinterest_pin(
    pin: dict[str, Any],
    *,
    account_id: str,
    analytics: dict[str, Any] | None = None,
) -> NormalizedPost:
    pin_id = str(pin.get("id") or "").strip()
    if not pin_id:
        raise ValueError("Pinterest pin id is required")
    media = _pin_media(pin)
    return NormalizedPost(
        platform="pinterest",
        account_id=account_id,
        platform_post_id=pin_id,
        canonical_post_id=f"pinterest:{account_id}:{pin_id}",
        text=_pin_text(pin),
        created_at=str(pin.get("created_at") or pin.get("createdAt") or ""),
        content_format=str(media.get("media_type") or "media"),
        url=pin.get("url") or f"https://www.pinterest.com/pin/{pin_id}/",
        metrics=pinterest_metrics(analytics),
        comments=[],
        source={"type": "adapter", "data_completeness": "full" if analytics is not None else "partial"},
        platform_metadata={
            "pinterest": {
                "board_id": pin.get("board_id") or pin.get("board", {}).get("id") if isinstance(pin.get("board"), dict) else pin.get("board_id"),
                "board_owner": pin.get("board_owner"),
                "dominant_color": pin.get("dominant_color"),
                "media": media,
                "raw": {"pin": dict(pin), "analytics": dict(analytics or {})},
            }
        },
    )


@dataclass(frozen=True)
class RequestsPinterestClient:
    """Thin Pinterest API v5 client for optional live smoke paths."""

    def _get(self, path: str, *, token: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if requests is None:
            raise RuntimeError("requests package is required for live Pinterest API calls")
        resp = requests.get(
            f"{PINTEREST_API_BASE}/{path.lstrip('/')}",
            params=params or {},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def list_pins(self, account_id: str, token: str) -> list[dict]:
        payload = self._get("pins", token=token, params={"page_size": 100})
        return list(payload.get("items") or [])

    def fetch_pin(self, pin_id: str, token: str) -> dict:
        return self._get(f"pins/{pin_id}", token=token)

    def fetch_pin_analytics(self, pin_id: str, token: str) -> dict:
        return self._get(f"pins/{pin_id}/analytics", token=token)


class PinterestPlatformAdapter:
    platform = "pinterest"

    def __init__(
        self,
        *,
        account_id: str,
        token: str | None = None,
        token_file: str | None = None,
        client: PinterestClient | None = None,
        policy_path: str | Path = POLICY_PATH,
    ) -> None:
        self.account_id = account_id
        self._token = token
        self._token_file = token_file
        self._client = client or RequestsPinterestClient()
        self._policy_path = Path(policy_path)

    def _resolve_token(self) -> str:
        try:
            source = resolve_credential(
                label="Pinterest access token",
                direct_value=self._token,
                direct_source_name="PinterestPlatformAdapter(token=...)",
                env_var="PINTEREST_ACCESS_TOKEN",
                file_path=self._token_file,
            )
        except CredentialSourceError as exc:
            raise PinterestAdapterCredentialError(str(exc)) from exc
        if not source.value:
            raise PinterestAdapterCredentialError(
                "missing Pinterest access token; set PINTEREST_ACCESS_TOKEN or pass token_file"
            )
        return source.value

    def capabilities(self) -> CapabilityReport:
        registry = CapabilityRegistry.from_policy_file(self._policy_path)
        read_posts = registry.decide("pinterest", "read_posts")
        read_comments = registry.decide("pinterest", "read_comments")
        refresh = registry.decide("pinterest", "refresh_snapshots")
        insights = registry.decide("pinterest", "read_owned_insights")
        publish = registry.decide("pinterest", "publish_text")
        return CapabilityReport(
            platform="pinterest",
            can_import_history=read_posts.allowed,
            can_refresh_metrics=refresh.allowed,
            can_fetch_comments=False,
            can_publish=False,
            supported_metrics=("view_count", "reaction_count", "save_count", "click_count"),
            auth_required=True,
            notes=(
                f"read_posts: {read_posts.status.replace('_', '-')} ({read_posts.gate})",
                f"read_comments: {read_comments.status.replace('_', '-')} ({read_comments.gate})",
                f"refresh_snapshots: {refresh.status.replace('_', '-')} ({refresh.gate})",
                f"analytics: {insights.status.replace('_', '-')} ({insights.gate})",
                f"publish_text: {publish.status.replace('_', '-')} ({publish.gate})",
            ),
        )

    def list_posts(self) -> list[NormalizedPost]:
        token = self._resolve_token()
        posts = []
        for pin in self._client.list_pins(self.account_id, token):
            pin_id = str(pin.get("id") or "")
            analytics = self._client.fetch_pin_analytics(pin_id, token)
            posts.append(normalize_pinterest_pin(pin, account_id=self.account_id, analytics=analytics))
        return posts

    def refresh_metrics(self, platform_post_id: str) -> NormalizedMetrics:
        token = self._resolve_token()
        return pinterest_metrics(self._client.fetch_pin_analytics(platform_post_id, token))

    def fetch_comments(self, platform_post_id: str) -> list[NormalizedComment]:
        return []

    def publish(self, text: str, **kwargs: Any) -> PublishResult:
        decision = CapabilityRegistry.from_policy_file(self._policy_path).decide("pinterest", "publish_text")
        return PublishResult(ok=False, platform="pinterest", reason="unsupported", detail=decision.gate)


__all__ = [
    "PinterestAdapterCredentialError",
    "PinterestClient",
    "PinterestPlatformAdapter",
    "RequestsPinterestClient",
    "normalize_pinterest_pin",
    "pinterest_metrics",
]
