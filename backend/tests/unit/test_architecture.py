"""The layering rules of ADR-0001, enforced by reading imports."""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[2] / "src" / "duckgambit"

DOMAIN_ALLOWED_THIRD_PARTY = {"chess", "chess.pgn"}
DOMAIN_FORBIDDEN_STDLIB = {
    "asyncio", "datetime", "http", "logging", "os", "pathlib", "socket", "sqlite3",
    "subprocess", "threading", "time", "urllib", "uuid",
}  # fmt: skip
STDLIB_ALLOWED = {
    "__future__", "collections", "collections.abc", "dataclasses", "enum", "hashlib", "json",
    "math", "random", "re", "typing",
}  # fmt: skip

LAYER_MAY_IMPORT = {
    "domain": {"domain"},
    "services": {"domain", "services"},
    "adapters": {"domain", "services", "adapters", "settings"},
}


def imports_of(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def files(layer: str) -> list[Path]:
    return sorted((PACKAGE / layer).rglob("*.py"))


@pytest.mark.parametrize("path", files("domain"), ids=lambda p: p.name)
def test_domain_is_pure(path):
    for module in imports_of(path):
        top = module.split(".")[0]
        if top == "duckgambit":
            assert module.split(".")[1] == "domain", f"{path.name} imports {module}"
        elif top == "chess":
            assert module in DOMAIN_ALLOWED_THIRD_PARTY, f"{path.name} imports {module}"
        else:
            assert top not in DOMAIN_FORBIDDEN_STDLIB, f"{path.name} imports {module}"
            assert module in STDLIB_ALLOWED or top in STDLIB_ALLOWED, (
                f"{path.name} imports {module}: add it to the allow-list only if it does no I/O"
            )


@pytest.mark.parametrize("layer", sorted(LAYER_MAY_IMPORT))
def test_dependencies_point_inward(layer):
    for path in files(layer):
        for module in imports_of(path):
            parts = module.split(".")
            if parts[0] != "duckgambit" or len(parts) < 2:
                continue
            assert parts[1] in LAYER_MAY_IMPORT[layer], (
                f"{path.relative_to(PACKAGE)} ({layer}) must not import {module}"
            )


def test_domain_never_uses_global_randomness_or_the_wall_clock():
    for path in files("domain"):
        source = path.read_text(encoding="utf-8")
        for banned in ("random.random(", "random.choice(", "random.seed(", ".now(", "time.time("):
            assert banned not in source, f"{path.name} uses {banned}"
