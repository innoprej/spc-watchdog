"""Remove only paths, usernames, and credentials from replay artifacts."""

from __future__ import annotations

import getpass
import os
import re
from typing import Any, Iterable

ABSOLUTE_PATH = re.compile(
    r'(?i)(?:[a-z]:[\\/](?:[^\\/:*?"<>|\r\n]+[\\/])*'
    r'[^\\/:*?"<>|\r\n\s]+|/(?:home|users)/[^\s"\']+)'
)
CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?i)(api[_-]?key|authorization|bearer|password|secret|credential|token)"
    r"\s*[:=]\s*[^\s,}\"]+"
)
CREDENTIAL_KEY = re.compile(
    r"(?i)^(?:api[_-]?key|authorization|bearer|password|secret|credential|token|"
    r"access[_-]?token|refresh[_-]?token)$"
)


def local_usernames() -> tuple[str, ...]:
    """Return non-empty local identity strings that must not enter fixtures."""

    candidates = (getpass.getuser(), os.environ.get("USERNAME"), os.environ.get("USER"))
    return tuple(dict.fromkeys(value for value in candidates if value))


def sanitize(value: Any, *, usernames: Iterable[str] | None = None) -> Any:
    """Recursively sanitize the narrow committed-run scope without rewriting evidence."""

    identities = tuple(usernames) if usernames is not None else local_usernames()
    if isinstance(value, str):
        result = CREDENTIAL_ASSIGNMENT.sub(r"\1=[REDACTED]", value)
        for username in identities:
            result = re.sub(re.escape(username), "[SANITIZED_USERNAME]", result, flags=re.I)
        result = ABSOLUTE_PATH.sub("[SANITIZED_PATH]", result)
        return result
    if isinstance(value, list):
        return [sanitize(child, usernames=identities) for child in value]
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if CREDENTIAL_KEY.fullmatch(str(key))
                else sanitize(child, usernames=identities)
            )
            for key, child in value.items()
        }
    return value
