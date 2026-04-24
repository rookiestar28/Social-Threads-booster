#!/usr/bin/env python3
"""
Load and validate platform-neutral workflow preference config.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


CONFIG_FILENAME = "social_booster_config.json"
SUPPORTED_VERSION = 1
DISCUSSION_MODES = {"fast", "discussion", "auto"}
WORKFLOW_NAMES = {"draft", "analyze", "review"}
SECRET_KEY_NAMES = {
    "access_token",
    "api_key",
    "authorization",
    "client_secret",
    "cookie",
    "password",
    "refresh_token",
    "secret",
    "token",
}

DEFAULT_PREFERENCES: dict[str, Any] = {
    "version": SUPPORTED_VERSION,
    "workflows": {
        "draft": {
            "discussion_mode": "fast",
            "research_angle_expansion": True,
        },
        "analyze": {
            "discussion_mode": "fast",
        },
        "review": {
            "discussion_mode": "fast",
        },
    },
    "platforms": {},
}


def is_secret_like_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return normalized in SECRET_KEY_NAMES or normalized.endswith("_token") or normalized.endswith("_secret")


def reject_secret_like_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            if is_secret_like_key(key_text):
                raise ValueError(f"secret-like preference key is not allowed at {path}.{key_text}")
            reject_secret_like_keys(nested, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            reject_secret_like_keys(nested, f"{path}[{index}]")


def load_json_config(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("preference config must be a JSON object")
    return data


def validate_workflow_config(workflow: str, values: Any) -> dict[str, Any]:
    if not isinstance(values, dict):
        raise ValueError(f"{workflow} workflow config must be an object")

    allowed_fields = set(DEFAULT_PREFERENCES["workflows"][workflow])
    unknown_fields = set(values) - allowed_fields
    if unknown_fields:
        names = ", ".join(sorted(unknown_fields))
        raise ValueError(f"unsupported {workflow} preference field(s): {names}")

    normalized = copy.deepcopy(DEFAULT_PREFERENCES["workflows"][workflow])
    normalized.update(values)

    mode = normalized.get("discussion_mode")
    if mode not in DISCUSSION_MODES:
        allowed = ", ".join(sorted(DISCUSSION_MODES))
        raise ValueError(f"{workflow}.discussion_mode must be one of: {allowed}")

    if workflow == "draft" and not isinstance(normalized.get("research_angle_expansion"), bool):
        raise ValueError("draft.research_angle_expansion must be a boolean")

    return normalized


def normalize_preferences(raw: dict[str, Any]) -> dict[str, Any]:
    reject_secret_like_keys(raw)

    version = raw.get("version", SUPPORTED_VERSION)
    if version != SUPPORTED_VERSION:
        raise ValueError(f"unsupported preference config version: {version}")

    unknown_top_level = set(raw) - {"version", "workflows", "platforms"}
    if unknown_top_level:
        names = ", ".join(sorted(unknown_top_level))
        raise ValueError(f"unsupported top-level preference field(s): {names}")

    workflows = raw.get("workflows", {})
    if not isinstance(workflows, dict):
        raise ValueError("workflows must be an object")

    unknown_workflows = set(workflows) - WORKFLOW_NAMES
    if unknown_workflows:
        names = ", ".join(sorted(unknown_workflows))
        raise ValueError(f"unsupported workflow preference(s): {names}")

    normalized = copy.deepcopy(DEFAULT_PREFERENCES)
    for workflow in sorted(WORKFLOW_NAMES):
        normalized["workflows"][workflow] = validate_workflow_config(
            workflow,
            workflows.get(workflow, {}),
        )

    platforms = raw.get("platforms", {})
    if not isinstance(platforms, dict):
        raise ValueError("platforms must be an object")
    normalized["platforms"] = copy.deepcopy(platforms)

    return normalized


def load_preferences(path: str | Path = CONFIG_FILENAME) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        return copy.deepcopy(DEFAULT_PREFERENCES)
    return normalize_preferences(load_json_config(config_path))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and print workflow preference config.")
    parser.add_argument("--config", default=CONFIG_FILENAME, help="Path to social_booster_config.json")
    parser.add_argument("--show", action="store_true", help="Print normalized preferences as JSON")
    args = parser.parse_args()

    try:
        config = load_preferences(args.config)
    except Exception as exc:  # noqa: BLE001 - CLI should provide concise validation errors.
        print(f"[workflow_preferences] {exc}", file=sys.stderr)
        return 1

    if args.show:
        print(json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("[workflow_preferences] config ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
