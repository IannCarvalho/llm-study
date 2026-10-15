"""
Shared pytest fixtures / path setup for the deterministic test suite.

Two problems this file solves:

1. The modules under test import project code as a package (``from utils.X
   import Y``) and are normally run as ``python -m NN_module.file`` from the
   repository root. So the repo root must be on ``sys.path`` for ``utils`` to
   import. We insert it here (and also set ``pythonpath = .`` in pytest.ini-style
   config via :data:`ROOT`), so the suite runs the same way from any CWD.

2. The module directories are prefixed with digits (``06_evals``,
   ``12_agentic_rag`` ...), which are *not* importable with a normal
   ``import`` statement (``import 06_evals`` is a syntax error). The
   :func:`load_module` helper loads such a file by path under a clean alias,
   while leaving ``utils`` to resolve through the repo root on ``sys.path`` so
   the loaded module's own ``from utils...`` imports work.

Everything here is deterministic: no network, no LLM, no model download.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

# Repository root = parent of this tests/ directory.
ROOT = Path(__file__).resolve().parent.parent

# Guarantee the repo root is importable so ``from utils.X import Y`` resolves,
# regardless of the directory pytest was invoked from.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_module(relative_path: str, alias: str):
    """
    Load a module file by its path (relative to the repo root) under ``alias``.

    Needed because the course modules live in digit-prefixed packages
    (e.g. ``06_evals/rag_metrics.py``) that cannot be imported with a plain
    ``import`` statement. The module's internal ``from utils...`` imports still
    resolve because the repo root is on ``sys.path``.
    """
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(alias, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot build import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses / typing references resolve cleanly.
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """The repository root path, for tests that need to locate data files."""
    return ROOT
