#!/usr/bin/env python3
"""
Load and validate platform account context without exposing credential values.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


FORBIDDEN_SECRET_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "client_secret",
    "api_key",
    "password",
    "secret",
}

SUPPORTED_CREDENTIAL_SOURCE_TYPES = {"env", "token_file", "external_ref"}


class AccountContextError(ValueError):
    pass


@dataclass(frozen=True)
class AccountContext:
    key: str
    platform: str
    account_id: str
    account_type: str
    display_name: str
    credential_source_type: str
    credential_source_ref: str
    credential_available: bool
    notes: tuple[str, ...] = ()


def load_json(path: str | Path) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AccountContextError(f"account config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AccountContextError(f"account config is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise AccountContextError("account config root must be a JSON object")
    return payload


def find_forbidden_secret_keys(value: Any, *, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.lower() in FORBIDDEN_SECRET_KEYS:
                found.append(path)
            found.extend(find_forbidden_secret_keys(nested, prefix=path))
    elif isinstance(value, list):
        for idx, nested in enumerate(value):
            found.extend(find_forbidden_secret_keys(nested, prefix=f"{prefix}[{idx}]"))
    return found


def credential_source_ref(source: dict[str, Any]) -> str:
    source_type = str(source.get("type") or "")
    if source_type == "env":
        return str(source.get("name") or "")
    if source_type == "token_file":
        return str(source.get("path") or "")
    if source_type == "external_ref":
        return str(source.get("ref") or "")
    return ""


def credential_available(source: dict[str, Any], *, base_dir: Path) -> bool:
    source_type = str(source.get("type") or "")
    if source_type == "env":
        name = str(source.get("name") or "")
        return bool(name and os.environ.get(name))
    if source_type == "token_file":
        raw_path = str(source.get("path") or "")
        if not raw_path:
            return False
        token_path = Path(raw_path)
        if not token_path.is_absolute():
            token_path = base_dir / token_path
        return token_path.exists()
    if source_type == "external_ref":
        return False
    return False


def validate_account_config(payload: dict[str, Any]) -> None:
    forbidden = find_forbidden_secret_keys(payload)
    if forbidden:
        raise AccountContextError(
            "account config must not contain raw secret fields: " + ", ".join(forbidden)
        )

    accounts = payload.get("accounts")
    if not isinstance(accounts, list) or not accounts:
        raise AccountContextError("account config must contain a non-empty accounts array")

    seen_keys: set[str] = set()
    for idx, account in enumerate(accounts):
        if not isinstance(account, dict):
            raise AccountContextError(f"accounts[{idx}] must be an object")
        key = str(account.get("key") or "").strip()
        if not key:
            raise AccountContextError(f"accounts[{idx}].key is required")
        if key in seen_keys:
            raise AccountContextError(f"duplicate account key: {key}")
        seen_keys.add(key)

        for field in ("platform", "account_id", "account_type"):
            if not str(account.get(field) or "").strip():
                raise AccountContextError(f"{key}.{field} is required")

        source = account.get("credential_source")
        if not isinstance(source, dict):
            raise AccountContextError(f"{key}.credential_source must be an object")
        source_type = str(source.get("type") or "")
        if source_type not in SUPPORTED_CREDENTIAL_SOURCE_TYPES:
            raise AccountContextError(f"{key}.credential_source.type is unsupported: {source_type}")
        if not credential_source_ref(source):
            raise AccountContextError(f"{key}.credential_source is missing its reference field")


def resolve_account_context(
    payload: dict[str, Any],
    account_key: str,
    *,
    config_path: str | Path,
) -> AccountContext:
    validate_account_config(payload)
    base_dir = Path(config_path).resolve().parent
    for account in payload["accounts"]:
        if account["key"] != account_key:
            continue
        source = account["credential_source"]
        return AccountContext(
            key=str(account["key"]),
            platform=str(account["platform"]),
            account_id=str(account["account_id"]),
            account_type=str(account["account_type"]),
            display_name=str(account.get("display_name") or account["key"]),
            credential_source_type=str(source["type"]),
            credential_source_ref=credential_source_ref(source),
            credential_available=credential_available(source, base_dir=base_dir),
            notes=tuple(str(note) for note in account.get("notes", []) if str(note).strip()),
        )
    raise AccountContextError(f"account key not found: {account_key}")


def load_account_context(config_path: str | Path, account_key: str) -> AccountContext:
    payload = load_json(config_path)
    return resolve_account_context(payload, account_key, config_path=config_path)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and resolve a platform account context without printing secrets.",
    )
    parser.add_argument("--config", required=True, help="Path to platform account config JSON.")
    parser.add_argument("--account", required=True, help="Account key to resolve.")
    parser.add_argument(
        "--allow-missing-credential",
        action="store_true",
        help="Exit 0 even when the credential source is currently unavailable.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        context = load_account_context(args.config, args.account)
    except AccountContextError as exc:
        print(f"Account context error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(asdict(context), ensure_ascii=False, indent=2))
    if not context.credential_available and not args.allow_missing_credential:
        print(
            "Credential source is not available. Set the referenced environment variable, "
            "create the referenced token file, or use --allow-missing-credential for validation only.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
