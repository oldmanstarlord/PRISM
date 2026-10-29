"""Fail CI when secrets, generated artifacts, or local data are tracked."""

import re
import subprocess
from pathlib import Path

MAX_TRACKED_FILE_BYTES = 5 * 1024 * 1024
ALLOWED_DATA_FILES = {
    "data/raw/.gitkeep",
    "data/processed/.gitkeep",
    "data/models/.gitkeep",
    "data/evaluation/news_sentiment_label_template.csv",
}
FORBIDDEN_PARTS = {
    ".venv",
    "node_modules",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".pytest_tmp",
    "pytest_tmp",
}
SECRET_PATTERNS = {
    "private key": re.compile(r"BEGIN (?:RSA|OPENSSH|EC) PRIVATE KEY"),
    "OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "JWT-like token": re.compile(
        r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\b"
    ),
}


def tracked_files() -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files", "-z"], check=True, capture_output=True
    ).stdout.decode()
    return [Path(item) for item in output.split("\0") if item]


def main() -> None:
    violations: list[str] = []
    for path in tracked_files():
        if not path.exists():
            continue
        normalized = path.as_posix()
        if normalized == ".env" or (
            normalized.startswith(".env.") and normalized != ".env.example"
        ):
            violations.append(f"local environment file is tracked: {normalized}")
        if any(part in FORBIDDEN_PARTS for part in path.parts):
            violations.append(f"generated/dependency path is tracked: {normalized}")
        if normalized.startswith("data/") and normalized not in ALLOWED_DATA_FILES:
            violations.append(f"data artifact is tracked: {normalized}")
        if not path.is_file():
            violations.append(f"tracked path is not a regular file: {normalized}")
            continue
        if path.stat().st_size > MAX_TRACKED_FILE_BYTES:
            violations.append(f"tracked file exceeds 5 MiB: {normalized}")
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                violations.append(f"possible {label} in {normalized}")
    if violations:
        raise SystemExit("Repository policy violations:\n- " + "\n- ".join(violations))
    print("Repository policy passed: no secrets, generated artifacts, or local data tracked")


if __name__ == "__main__":
    main()
