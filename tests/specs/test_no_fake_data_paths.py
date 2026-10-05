"""Regression guard against production fixture and silent-fallback paths."""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = (PROJECT_ROOT / "backend" / "app", PROJECT_ROOT / "jobs")
BANNED_TEXT = (
    "Mozilla/5.0",
    "tests/fixtures",
    "data/macro",
    "data/news",
    "data/announcements",
)


def production_python_files() -> list[Path]:
    return sorted(path for root in PRODUCTION_ROOTS for path in root.rglob("*.py"))


def test_production_code_has_no_fixture_or_browser_impersonation_paths() -> None:
    violations: list[str] = []
    for path in production_python_files():
        text = path.read_text(encoding="utf-8")
        for banned in BANNED_TEXT:
            if banned in text:
                violations.append(f"{path.relative_to(PROJECT_ROOT)} contains {banned!r}")

    assert violations == []


def test_production_code_has_no_use_fallback_parameter() -> None:
    violations: list[str] = []
    for path in production_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            parameters = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            if any(parameter.arg == "use_fallback" for parameter in parameters):
                violations.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")

    assert violations == []
