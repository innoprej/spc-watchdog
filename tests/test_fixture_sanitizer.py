"""Adversarially lock the intentionally narrow replay-sanitization boundary."""

from __future__ import annotations

from spc_watchdog.fixture_sanitizer import sanitize


def test_sanitizer_removes_paths_bare_usernames_and_credential_values() -> None:
    payload = {
        "message": "Ada Example read C:\\Users\\Ada Example\\factory.db",
        "token": "top-secret",
        "nested": {
            "api_key": "sk-should-not-survive",
            "detail": "authorization=Bearer-secret for ADA EXAMPLE",
        },
        "evidence": {"id": "tool-life-s2-002", "cycle_count": 9980},
    }

    sanitized = sanitize(payload, usernames=("Ada Example",))

    assert sanitized["token"] == "[REDACTED]"
    assert sanitized["nested"]["api_key"] == "[REDACTED]"
    assert "Ada Example" not in str(sanitized)
    assert "factory.db" not in str(sanitized)
    assert "Bearer-secret" not in str(sanitized)
    assert sanitized["evidence"] == {
        "id": "tool-life-s2-002",
        "cycle_count": 9980,
    }
