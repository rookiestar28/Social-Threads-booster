#!/usr/bin/env python3
"""
Build platform-aware routing plans for topic, draft, analyze, and predict workflows.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from platform_schema import CANONICAL_METRIC_KEYS, validate_platform_tracker


SUPPORTED_WORKFLOWS = {"topics", "draft", "analyze", "predict"}
VIDEO_FIRST_PLATFORMS = {"youtube", "tiktok"}
MEDIA_CENTRIC_PLATFORMS = {"instagram", "pinterest"}
FORUM_PLATFORMS = {"reddit"}
PROFESSIONAL_PLATFORMS = {"linkedin"}
TEXT_NATIVE_PLATFORMS = {"threads", "x", "bluesky", "mastodon", "facebook_pages"}


class PlatformWorkflowRoutingError(ValueError):
    """Raised when workflow routing cannot build a safe platform plan."""


@dataclass(frozen=True)
class PlatformRoute:
    platform: str
    account_ids: tuple[str, ...]
    post_count: int
    content_formats: tuple[str, ...]
    supported_metrics: tuple[str, ...]
    unavailable_metrics: tuple[str, ...]
    workflow_notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "account_ids": list(self.account_ids),
            "post_count": self.post_count,
            "content_formats": list(self.content_formats),
            "supported_metrics": list(self.supported_metrics),
            "unavailable_metrics": list(self.unavailable_metrics),
            "workflow_notes": list(self.workflow_notes),
        }


@dataclass(frozen=True)
class WorkflowRoutingPlan:
    workflow: str
    selected_platforms: tuple[str, ...]
    routes: tuple[PlatformRoute, ...]
    global_warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow,
            "selected_platforms": list(self.selected_platforms),
            "routes": [route.to_dict() for route in self.routes],
            "global_warnings": list(self.global_warnings),
        }


def _group_posts_by_platform(tracker: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for post in tracker.get("posts") or []:
        if not isinstance(post, dict):
            continue
        platform = str(post.get("platform") or "").strip()
        if platform:
            groups.setdefault(platform, []).append(post)
    return groups


def _select_platforms(groups: dict[str, list[dict[str, Any]]], target_platforms: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    available = set(groups)
    if target_platforms is None:
        selected = tuple(sorted(available))
    else:
        selected = tuple(dict.fromkeys(str(platform).strip() for platform in target_platforms if str(platform).strip()))
        unknown = [platform for platform in selected if platform not in available]
        if unknown:
            raise PlatformWorkflowRoutingError(f"unknown platform target(s): {', '.join(sorted(unknown))}")
    if not selected:
        raise PlatformWorkflowRoutingError("no platforms selected")
    return selected


def _metric_support(posts: list[dict[str, Any]]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    supported = []
    unavailable = []
    for metric in CANONICAL_METRIC_KEYS:
        has_value = any(
            isinstance(post.get("metrics"), dict) and post["metrics"].get(metric) is not None
            for post in posts
        )
        if has_value:
            supported.append(metric)
        else:
            unavailable.append(metric)
    return tuple(supported), tuple(unavailable)


def _platform_profile_note(platform: str, content_formats: tuple[str, ...]) -> str:
    if platform in VIDEO_FIRST_PLATFORMS or "video" in content_formats:
        return "video-first platform: preserve video format, watch-time/context notes, and avoid text-native draft assumptions"
    if platform in MEDIA_CENTRIC_PLATFORMS or any(fmt in {"image", "media"} for fmt in content_formats):
        return "media-centric platform: preserve visual/link context and avoid comment-thread assumptions"
    if platform in FORUM_PLATFORMS:
        return "forum-shaped platform: compare submission/comment dynamics separately from creator-feed posts"
    if platform in PROFESSIONAL_PLATFORMS:
        return "professional platform: keep member/organization context and professional interaction norms explicit"
    if platform in TEXT_NATIVE_PLATFORMS:
        return "text-native platform: text comparison is acceptable, but metric availability still stays platform-specific"
    return "platform profile is unknown; route conservatively and avoid cross-platform assumptions"


def _workflow_notes(workflow: str, platform: str, posts: list[dict[str, Any]], unavailable_metrics: tuple[str, ...]) -> tuple[str, ...]:
    content_formats = tuple(sorted({str(post.get("content_format") or "text") for post in posts}))
    notes = [_platform_profile_note(platform, content_formats)]
    if len(posts) < 5:
        notes.append("fewer than 5 comparable posts on this platform; treat workflow conclusions as weak")
    if unavailable_metrics:
        notes.append("missing metrics on this platform: " + ", ".join(unavailable_metrics))
    if workflow == "topics":
        notes.append("mine comments and topic freshness within this platform before comparing against other platforms")
    elif workflow == "draft":
        notes.append("apply platform-specific content format constraints before composing a draft")
    elif workflow == "analyze":
        notes.append("analyze red lines, style fit, and psychology against platform-local comparable posts first")
    elif workflow == "predict":
        notes.append("build prediction ranges from platform-local comparable posts; do not average incompatible metrics")
    return tuple(notes)


def _build_route(workflow: str, platform: str, posts: list[dict[str, Any]]) -> PlatformRoute:
    account_ids = tuple(sorted({str(post.get("account_id")) for post in posts if post.get("account_id")}))
    content_formats = tuple(sorted({str(post.get("content_format") or "text") for post in posts}))
    supported_metrics, unavailable_metrics = _metric_support(posts)
    return PlatformRoute(
        platform=platform,
        account_ids=account_ids,
        post_count=len(posts),
        content_formats=content_formats,
        supported_metrics=supported_metrics,
        unavailable_metrics=unavailable_metrics,
        workflow_notes=_workflow_notes(workflow, platform, posts, unavailable_metrics),
    )


def route_tracker_for_workflow(
    tracker: dict[str, Any],
    *,
    workflow: str,
    target_platforms: list[str] | tuple[str, ...] | None = None,
) -> WorkflowRoutingPlan:
    workflow_name = workflow.strip().lower()
    if workflow_name not in SUPPORTED_WORKFLOWS:
        raise PlatformWorkflowRoutingError(f"unsupported workflow: {workflow}")
    validate_platform_tracker(tracker)
    groups = _group_posts_by_platform(tracker)
    selected_platforms = _select_platforms(groups, target_platforms)
    routes = tuple(_build_route(workflow_name, platform, groups[platform]) for platform in selected_platforms)
    warnings = []
    if len(selected_platforms) > 1:
        warnings.append("mixed-platform selection: compare routes side-by-side; do not merge incompatible metric baselines")
    return WorkflowRoutingPlan(
        workflow=workflow_name,
        selected_platforms=selected_platforms,
        routes=routes,
        global_warnings=tuple(warnings),
    )


__all__ = [
    "PlatformRoute",
    "PlatformWorkflowRoutingError",
    "WorkflowRoutingPlan",
    "route_tracker_for_workflow",
]
