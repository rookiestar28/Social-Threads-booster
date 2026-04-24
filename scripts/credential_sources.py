"""
Credential source helpers that avoid printing secret values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResolvedCredential:
    value: str | None
    source: str
    warning: str | None = None

    @property
    def available(self) -> bool:
        return bool(self.value)


class CredentialSourceError(ValueError):
    pass


def read_secret_file(path: str | Path, *, label: str) -> str:
    secret_path = Path(path)
    try:
        value = secret_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise CredentialSourceError(f"{label} file not found: {secret_path}") from exc
    except OSError as exc:
        raise CredentialSourceError(f"{label} file could not be read: {secret_path}") from exc
    if not value:
        raise CredentialSourceError(f"{label} file is empty: {secret_path}")
    return value


def resolve_credential(
    *,
    label: str,
    direct_value: str | None = None,
    direct_source_name: str,
    env_var: str,
    file_path: str | None = None,
) -> ResolvedCredential:
    if direct_value:
        return ResolvedCredential(
            value=direct_value,
            source=direct_source_name,
            warning=(
                f"Warning: {label} was supplied via {direct_source_name}. "
                "Command-line secrets can leak through shell history or process listings. "
                f"Prefer ${env_var} or a token file."
            ),
        )

    if file_path:
        return ResolvedCredential(
            value=read_secret_file(file_path, label=label),
            source=f"file:{file_path}",
        )

    env_value = os.environ.get(env_var)
    if env_value:
        return ResolvedCredential(value=env_value, source=f"env:{env_var}")

    return ResolvedCredential(value=None, source="missing")
