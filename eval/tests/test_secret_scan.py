from __future__ import annotations

from pathlib import Path

from scripts.secret_scan import find_secrets, scan_repository


def test_detects_likely_credentials_without_echoing_values() -> None:
    candidate = "API" + "_TOKEN=" + "abcdefghijklmnop123456"
    findings = find_secrets(candidate, "fixture.env")

    assert len(findings) == 1
    assert findings[0].rule == "credential-assignment"
    assert "abcdefghijklmnop" not in repr(findings[0])


def test_allows_documented_placeholders() -> None:
    assert find_secrets("API_KEY=synthetic-placeholder-value", "fixture.env") == []


def test_tracked_repository_has_no_likely_secrets() -> None:
    assert scan_repository(Path.cwd()) == []
