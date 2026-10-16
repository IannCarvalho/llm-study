"""
The documentation must only point at things that exist.

Checks every Markdown file of the repository (README.md, LLM_SETUP.md,
CONTRIBUTING.md and the .md files of each module):

- relative links ``[text](path)`` resolve to an existing file or directory;
- every ``python -m NN_module.script`` (and ``import_module("NN_module.script")``)
  maps to an existing ``NN_module/script.py``;
- every ``from utils.X import a, b`` snippet names a module of ``utils/`` and
  names that it defines at top level (read with ``ast``; nothing is imported).

A line containing ``(planned)`` is skipped: it announces code that does not
exist yet. Deterministic: no network, no imports of the documented code.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", ".pytest_cache", "data"}

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
MODULE_CMD_RE = re.compile(
    r"(?:python3?\s+-m\s+|import_module\(\s*[\"'])(\d{2}_\w+(?:\.\w+)+)"
)
FROM_UTILS_RE = re.compile(r"^\s*from\s+(utils(?:\.\w+)*)\s+import\s+([^#]+)")


def _markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts)
    )


def _lines(path: Path):
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if "(planned)" not in line:
            yield number, line


def _where(path: Path, number: int) -> str:
    return f"{path.relative_to(ROOT).as_posix()}:{number}"


def _top_level_names(module_file: Path) -> set[str]:
    tree = ast.parse(module_file.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
    if module_file.name == "__init__.py":
        names |= _lazy_exports(tree)
    return names


def _lazy_exports(tree: ast.Module) -> set[str]:
    """Names served by a package-level ``__getattr__`` mapping (utils/__init__.py)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_lazy_imports" for t in node.targets
        ):
            return set(ast.literal_eval(node.value))
    return set()


def _module_file(dotted: str) -> Path | None:
    base = ROOT.joinpath(*dotted.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.exists():
            return candidate
    return None


def test_there_is_documentation_to_check():
    assert len(_markdown_files()) >= 10


def test_relative_links_point_to_existing_paths():
    broken = []
    for md in _markdown_files():
        for number, line in _lines(md):
            for target in LINK_RE.findall(line):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                path = target.split("#", 1)[0]
                if path and not (md.parent / path).exists():
                    broken.append(f"{_where(md, number)} -> {target}")
    assert broken == [], "links to missing files:\n" + "\n".join(broken)


def test_documented_module_commands_point_to_existing_scripts():
    missing = []
    for md in _markdown_files():
        for number, line in _lines(md):
            for dotted in MODULE_CMD_RE.findall(line):
                if not ROOT.joinpath(*dotted.split(".")).with_suffix(".py").exists():
                    missing.append(f"{_where(md, number)} -> {dotted}")
    assert missing == [], "commands for missing scripts:\n" + "\n".join(missing)


def test_documented_utils_imports_exist():
    problems = []
    for md in _markdown_files():
        for number, line in _lines(md):
            match = FROM_UTILS_RE.match(line)
            if not match:
                continue
            module, imported = match.groups()
            module_file = _module_file(module)
            if module_file is None:
                problems.append(f"{_where(md, number)} -> no module {module}")
                continue
            defined = _top_level_names(module_file)
            for item in imported.strip().strip("()").split(","):
                name = item.split(" as ")[0].strip()
                if name and name != "*" and name not in defined:
                    problems.append(f"{_where(md, number)} -> {module}.{name} does not exist")
    assert problems == [], "documented imports that do not exist:\n" + "\n".join(problems)
