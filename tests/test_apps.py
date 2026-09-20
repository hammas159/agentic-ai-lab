"""Every app must load, expose a runner, and own a unique theme and icon."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

APP_FILES = sorted((ROOT / "apps").glob("[0-9][0-9]_*/app.py"))


def load(path: Path):
    spec = importlib.util.spec_from_file_location(f"t_{path.parent.name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_there_are_ten_apps():
    assert len(APP_FILES) == 10


@pytest.mark.parametrize("path", APP_FILES, ids=lambda p: p.parent.name)
def test_app_loads_and_is_wired(path):
    m = load(path)
    assert hasattr(m, "app"), "no FastAPI app"
    assert callable(m.runner), "no runner"
    assert isinstance(m.SLUG, str) and m.SLUG, "no SLUG"
    # Every app must define the routes the shared templates link to.
    routes = {r.path for r in m.app.routes}
    for route in ("/", "/run", "/history", "/about", "/healthz", "/job/{job_id}"):
        assert route in routes, f"{path.parent.name} is missing {route}"


def test_slugs_and_icons_are_unique():
    slugs, icons = [], []
    for path in APP_FILES:
        m = load(path)
        slugs.append(m.SLUG)
        icons.append(m.app.title)
    assert len(set(slugs)) == 10, "two apps share a theme"
    assert len(set(icons)) == 10, "two apps share a title"


@pytest.mark.parametrize("path", APP_FILES, ids=lambda p: p.parent.name)
def test_app_has_its_own_result_template(path):
    assert (path.parent / "templates" / "result.html").exists()
