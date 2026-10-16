"""
Static consistency checks for the lazy exports of the ``utils`` package.

``utils/__init__.py`` maps public names to submodules (``__getattr__``) and
lists them in ``__all__``. A name that points at nothing fails only on first
access and breaks ``from utils import *``. These checks read the sources with
``ast`` instead of importing them, so no optional dependency (LangChain,
sentence-transformers) is loaded.
"""

import ast
from pathlib import Path

UTILS = Path(__file__).resolve().parent.parent / "utils"


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _lazy_imports() -> dict:
    for node in ast.walk(_parse(UTILS / "__init__.py")):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_lazy_imports"
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("_lazy_imports not found in utils/__init__.py")


def _dunder_all() -> list:
    for node in _parse(UTILS / "__init__.py").body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("__all__ not found in utils/__init__.py")


def _top_level_names(module: str) -> set:
    names = set()
    for node in _parse(UTILS / f"{module}.py").body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def test_every_lazy_export_exists_in_its_submodule():
    missing = [
        f"{name} -> utils.{module}.{attr}"
        for name, (module, attr) in _lazy_imports().items()
        if attr not in _top_level_names(module)
    ]
    assert missing == []


def test_dunder_all_matches_the_lazy_exports():
    exported = _dunder_all()
    assert len(exported) == len(set(exported)), "duplicate names in __all__"
    assert set(exported) == set(_lazy_imports())
