#!/usr/bin/env python3
"""
Platform adapter contract and normalized domain objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from platform_schema import build_platform_comment, build_platform_metrics, build_platform_post


@dataclass(frozen=True)
class NormalizedMetrics:
    view_count: int | float | None = None
    reaction_count: int | float | None = None
    comment_count: int | float | None = None
    share_count: int | float | None = None
    save_count: int | float | None = None
    click_count: int | float | None = None
    watch_time_seconds: int | float | None = None

    def to_dict(self) -> dict[str, int | float | None]:
        return build_platform_metrics(
            {
                "view_count": self.view_count,
                "reaction_count": self.reaction_count,
                "comment_count": self.comment_count,
                "share_count": self.share_count,
                "save_count": self.save_count,
                "click_count": self.click_count,
                "watch_time_seconds": self.watch_time_seconds,
            }
        )


@dataclass(frozen=True)
class NormalizedComment:
    platform: str
    account_id: str
    platform_comment_id: str
    text: str
    created_at: str
    author_id: str | None = None
    metrics: NormalizedMetrics = field(default_factory=NormalizedMetrics)
    platform_metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedPost:
    platform: str
    account_id: str
    platform_post_id: str
    text: str
    created_at: str
    canonical_post_id: str | None = None
    content_format: str = "text"
    url: str | None = None
    metrics: NormalizedMetrics = field(default_factory=NormalizedMetrics)
    comments: list[NormalizedComment] = field(default_factory=list)
    source: dict = field(default_factory=lambda: {"type": "adapter", "data_completeness": "partial"})
    platform_metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MetricSnapshot:
    platform_post_id: str
    captured_at: str
    metrics: NormalizedMetrics


@dataclass(frozen=True)
class PublishResult:
    ok: bool
    platform: str
    platform_post_id: str | None = None
    url: str | None = None
    reason: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class CapabilityReport:
    platform: str
    can_import_history: bool = False
    can_refresh_metrics: bool = False
    can_fetch_comments: bool = False
    can_publish: bool = False
    supported_metrics: tuple[str, ...] = ()
    auth_required: bool = False
    notes: tuple[str, ...] = ()


@runtime_checkable
class PlatformAdapter(Protocol):
    platform: str
    account_id: str

    def capabilities(self) -> CapabilityReport:
        ...

    def list_posts(self) -> list[NormalizedPost]:
        ...

    def refresh_metrics(self, platform_post_id: str) -> NormalizedMetrics:
        ...

    def fetch_comments(self, platform_post_id: str) -> list[NormalizedComment]:
        ...

    def publish(self, text: str, **kwargs) -> PublishResult:
        ...


def normalized_comment_to_schema_comment(comment: NormalizedComment) -> dict:
    return build_platform_comment(
        platform=comment.platform,
        account_id=comment.account_id,
        platform_comment_id=comment.platform_comment_id,
        text=comment.text,
        created_at=comment.created_at,
        author_id=comment.author_id,
        metrics=comment.metrics.to_dict(),
        platform_metadata=comment.platform_metadata,
    )


def normalized_post_to_schema_post(post: NormalizedPost) -> dict:
    return build_platform_post(
        platform=post.platform,
        account_id=post.account_id,
        platform_post_id=post.platform_post_id,
        canonical_post_id=post.canonical_post_id,
        text=post.text,
        created_at=post.created_at,
        content_format=post.content_format,
        url=post.url,
        metrics=post.metrics.to_dict(),
        comments=[normalized_comment_to_schema_comment(comment) for comment in post.comments],
        source=post.source,
        platform_metadata=post.platform_metadata,
    )


class MemoryPlatformAdapter:
    """Offline adapter test double that satisfies the platform adapter contract."""

    def __init__(
        self,
        *,
        platform: str,
        account_id: str,
        posts: list[NormalizedPost],
        capabilities: CapabilityReport | None = None,
    ) -> None:
        self.platform = platform
        self.account_id = account_id
        self._posts = list(posts)
        self._capabilities = capabilities or CapabilityReport(platform=platform)

    def capabilities(self) -> CapabilityReport:
        return self._capabilities

    def list_posts(self) -> list[NormalizedPost]:
        return list(self._posts)

    def refresh_metrics(self, platform_post_id: str) -> NormalizedMetrics:
        for post in self._posts:
            if post.platform_post_id == platform_post_id:
                return post.metrics
        raise KeyError(f"post not found: {platform_post_id}")

    def fetch_comments(self, platform_post_id: str) -> list[NormalizedComment]:
        for post in self._posts:
            if post.platform_post_id == platform_post_id:
                return list(post.comments)
        raise KeyError(f"post not found: {platform_post_id}")

    def publish(self, text: str, **kwargs) -> PublishResult:
        if not self._capabilities.can_publish:
            return PublishResult(ok=False, platform=self.platform, reason="unsupported")
        platform_post_id = kwargs.get("platform_post_id") or f"memory:{len(self._posts) + 1}"
        return PublishResult(ok=True, platform=self.platform, platform_post_id=str(platform_post_id))
