"""
Shared redaction helpers for bounded audit logs.
"""

from __future__ import annotations

import re
from typing import Any


REDACTED = "[redacted]"
MAX_LOG_STRING_LENGTH = 240
MAX_LOG_LIST_ITEMS = 20

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

SENSITIVE_QUERY_RE = re.compile(
    r"(?i)(access_token|api_key|client_secret|password|refresh_token|token|secret)=([^&#\s]+)"
)
BEARER_RE = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")


def is_secret_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return normalized in SECRET_KEY_NAMES or normalized.endswith("_token") or normalized.endswith("_secret")


def redact_string(value: str, *, max_length: int = MAX_LOG_STRING_LENGTH) -> str:
    redacted = SENSITIVE_QUERY_RE.sub(lambda match: f"{match.group(1)}={REDACTED}", value)
    redacted = BEARER_RE.sub(f"Bearer {REDACTED}", redacted)
    if len(redacted) > max_length:
        return redacted[:max_length] + "...[truncated]"
    return redacted


def sanitize_log_value(value: Any, *, max_string_length: int = MAX_LOG_STRING_LENGTH) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            if is_secret_key(key_text):
                sanitized[key_text] = REDACTED
            else:
                sanitized[key_text] = sanitize_log_value(
                    nested,
                    max_string_length=max_string_length,
                )
        return sanitized
    if isinstance(value, list):
        return [
            sanitize_log_value(item, max_string_length=max_string_length)
            for item in value[:MAX_LOG_LIST_ITEMS]
        ]
    if isinstance(value, tuple):
        return [
            sanitize_log_value(item, max_string_length=max_string_length)
            for item in value[:MAX_LOG_LIST_ITEMS]
        ]
    if isinstance(value, str):
        return redact_string(value, max_length=max_string_length)
    return value
