"""The shadow package can send no order, and the live path never depends on it.

Read from source, not from imports: an import that only happens inside a function is
still a route to the order path (results/mission/SHADOW_RUNNER_DESIGN_2026-11-09.md §2).
"""
import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FORBIDDEN_NAMES = ("submit_order", "replace_order", "cancel_order")
FORBIDDEN_MODULES = ("quantt.session", "quantt.deploy", "quantt.collect")


def _sources(root: Path):
    return [p for p in root.rglob("*.py") if "tests" not in p.parts and "__pycache__" not in p.parts]


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_shadow_names_no_order_method_and_imports_no_runner():
    files = _sources(REPO / "shadow")
    assert files
    for p in files:
        tree = ast.parse(p.read_text())
        names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | \
                {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        assert not names & set(FORBIDDEN_NAMES), f"{p} names an order method"
        for mod in _imports(tree):
            assert not mod.startswith(FORBIDDEN_MODULES), f"{p} imports {mod}"


def test_the_live_path_never_imports_shadow_or_research():
    for root in (REPO / "quantt", REPO / "src" / "deploy"):
        for p in _sources(root):
            for mod in _imports(ast.parse(p.read_text())):
                assert not (mod == "shadow" or mod.startswith("shadow.")), f"{p} imports {mod}"
