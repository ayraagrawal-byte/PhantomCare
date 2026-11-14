from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str


TOKEN_RULES = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "openai-token": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
}
ASSIGNMENT_RULE = re.compile(
    r"(?i)\b(?:api[_-]?key|api[_-]?token|secret|password|access[_-]?key)\b"
    r"\s*[:=]\s*[\"']?([A-Za-z0-9_./+=-]{12,})"
)
PLACEHOLDERS = (
    "example",
    "placeholder",
    "synthetic",
    "changeme",
    "redacted",
    "os.environ",
    "getenv",
)
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}


def find_secrets(text: str, path: str) -> list[Finding]:
    findings: list[Finding] = []
    for number, line in enumerate(text.splitlines(), 1):
        for rule, pattern in TOKEN_RULES.items():
            if pattern.search(line):
                findings.append(Finding(path, number, rule))
        assignment = ASSIGNMENT_RULE.search(line)
        if assignment:
            value = assignment.group(1).lower()
            if not any(placeholder in value for placeholder in PLACEHOLDERS):
                findings.append(Finding(path, number, "credential-assignment"))
    return findings


def tracked_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [root / path for path in result.stdout.decode().split("\0") if path]


def scan_repository(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in tracked_files(root):
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {
            ".env.example",
            ".gitignore",
        }:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        findings.extend(find_secrets(text, path.relative_to(root).as_posix()))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan tracked text files for likely secrets.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    findings = scan_repository(args.root.resolve())
    if findings:
        for finding in findings:
            print(f"{finding.path}:{finding.line}: {finding.rule}")
        raise SystemExit(f"Found {len(findings)} possible secret(s).")
    print("Secret scan passed: no likely credentials in tracked text files.")


if __name__ == "__main__":
    main()
