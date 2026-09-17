"""Control tests, and the property that makes the audit worth reading:
a control may only pass when something was actually observed.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from auditor.controls import (
    CONTROLS,
    FAIL,
    INCONCLUSIVE,
    NOT_APPLICABLE,
    PASS,
    declared_deps_are_used,
    imports_are_declared,
    readme_limits,
    run_all,
)
from auditor.evidence import Evidence, collect
from auditor.report import Audit, RepoAudit, audit_folder


def write(root: Path, rel: str, body: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")


def make(tmp_path: Path, name: str = "demo", **files: str) -> Evidence:
    root = tmp_path / name
    for rel, body in files.items():
        write(root, rel.replace("__", "/"), body)
    return collect(root)


# -- no inferred compliance ----------------------------------------------


def test_a_missing_readme_is_inconclusive_not_a_pass(tmp_path: Path):
    """Nothing was observed, so nothing may be asserted."""
    ev = make(tmp_path, **{"a.py": "x = 1\n"})
    assert readme_limits(ev).status == INCONCLUSIVE


def test_a_missing_pyproject_makes_dependency_controls_not_applicable(tmp_path: Path):
    ev = make(tmp_path, **{"a.py": "import httpx\n"})
    assert declared_deps_are_used(ev).status == NOT_APPLICABLE
    assert imports_are_declared(ev).status == NOT_APPLICABLE


def test_no_control_ever_passes_on_a_missing_directory(tmp_path: Path):
    ev = collect(tmp_path / "nope")
    statuses = {r.status for r in run_all(ev)}
    assert PASS not in statuses


def test_every_control_returns_a_detail(tmp_path: Path):
    ev = make(tmp_path, **{"a.py": "x = 1\n"})
    for result in run_all(ev):
        assert result.detail, f"{result.control} returned no detail"


def test_every_declared_control_is_run(tmp_path: Path):
    ev = make(tmp_path, **{"a.py": "x = 1\n"})
    assert {r.control for r in run_all(ev)} == {c.id for c in CONTROLS}


# -- dependency controls -------------------------------------------------


PYPROJECT = """
[project]
name = "demo"
dependencies = [{deps}]
"""


def test_an_unused_declared_dependency_fails(tmp_path: Path):
    ev = make(
        tmp_path,
        **{
            "pyproject.toml": PYPROJECT.format(deps='"httpx", "rich"'),
            "src__demo__a.py": "import httpx\n",
        },
    )
    result = declared_deps_are_used(ev)
    assert result.status == FAIL
    assert "rich" in result.detail


def test_an_undeclared_import_fails(tmp_path: Path):
    ev = make(
        tmp_path,
        **{
            "pyproject.toml": PYPROJECT.format(deps='"httpx"'),
            "src__demo__a.py": "import httpx\nimport streamlit\n",
        },
    )
    result = imports_are_declared(ev)
    assert result.status == FAIL
    assert "streamlit" in result.detail


def test_the_repos_own_package_is_not_an_undeclared_import(tmp_path: Path):
    ev = make(
        tmp_path,
        **{
            "pyproject.toml": PYPROJECT.format(deps=""),
            "src__demo__a.py": "def f(): pass\n",
            "src__demo__b.py": "from demo.a import f\n",
        },
    )
    assert imports_are_declared(ev).status == PASS


@pytest.mark.parametrize(
    ("module", "declared"),
    [
        ("cv2", "opencv-python-headless"),
        ("cv2", "opencv-python"),
        ("skimage", "scikit-image"),
        ("sklearn", "scikit-learn"),
        ("yaml", "PyYAML"),
        ("psycopg_pool", "psycopg"),
    ],
)
def test_distribution_aliases_are_understood(tmp_path: Path, module: str, declared: str):
    """`cv2` comes from several distributions; any of them satisfies the import."""
    ev = make(
        tmp_path,
        name=f"demo_{module}_{declared}".replace("-", "_"),
        **{
            "pyproject.toml": PYPROJECT.format(deps=f'"{declared}"'),
            "src__demo__a.py": f"import {module}\n",
        },
    )
    assert imports_are_declared(ev).status == PASS


def test_the_standard_library_is_never_an_undeclared_import(tmp_path: Path):
    """A hand-written stdlib list scored this control 0% across 30 repos."""
    ev = make(
        tmp_path,
        **{
            "pyproject.toml": PYPROJECT.format(deps=""),
            "src__demo__a.py": (
                "import tomllib\nimport graphlib\nimport zoneinfo\n"
                "import dataclasses\nimport statistics\n"
            ),
        },
    )
    assert imports_are_declared(ev).status == PASS


# -- the rate cannot be inflated -----------------------------------------


def test_inconclusive_results_are_excluded_from_the_rate():
    """Counting unmeasured controls as passes is how an audit reports 90%
    having measured a third of what it claimed."""
    from auditor.controls import Result

    repo = RepoAudit(
        "x",
        [
            Result("a", PASS, "d"),
            Result("b", FAIL, "d"),
            Result("c", INCONCLUSIVE, "d"),
            Result("d", NOT_APPLICABLE, "d"),
        ],
    )
    assert len(repo.counted) == 2
    assert repo.rate == 0.5


def test_an_empty_audit_reports_zero_not_one():
    assert Audit().rate == 0.0


def test_folder_audit_skips_non_projects(tmp_path: Path):
    (tmp_path / "empty").mkdir()
    write(tmp_path, "real/README.md", "# real\n\n" + "word " * 60)
    audit = audit_folder(tmp_path)
    assert [r.name for r in audit.repos] == ["real"]
