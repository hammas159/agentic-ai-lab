"""Platform tests. No Kafka, no Redis, no model, no dataset."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps._platform import themes  # noqa: E402
from apps._platform.base import Field, _coerce  # noqa: E402
from apps._platform.cache import gen_key  # noqa: E402

# --- themes --------------------------------------------------------------------------


def test_ten_themes_exist():
    assert len(themes.all_themes()) == 10


def test_every_theme_has_a_distinct_accent():
    accents = [t.accent for t in themes.all_themes()]
    assert len(set(accents)) == 10, "two apps share an accent colour"


def test_every_theme_has_a_distinct_background():
    bgs = [t.bg for t in themes.all_themes()]
    assert len(set(bgs)) == 10


def test_both_modes_are_represented():
    modes = {t.mode for t in themes.all_themes()}
    assert modes == {"dark", "light"}


def test_css_vars_cover_every_token_the_layout_uses():
    css = themes.get("localizer").css_vars()
    for token in (
        "--bg",
        "--surface",
        "--border",
        "--text",
        "--muted",
        "--accent",
        "--good",
        "--bad",
        "--font-mono",
        "--radius",
    ):
        assert token in css, f"{token} missing from css_vars"


def test_unknown_theme_is_rejected():
    import pytest

    with pytest.raises(KeyError, match="unknown theme"):
        themes.get("nope")


# --- generation cache keys -----------------------------------------------------------


def test_cache_key_is_stable():
    a = gen_key("m", "prompt", 0.0, None)
    b = gen_key("m", "prompt", 0.0, None)
    assert a == b


def test_cache_key_separates_temperature_and_seed():
    base = gen_key("m", "p", 0.0, None)
    assert gen_key("m", "p", 0.7, None) != base
    assert gen_key("m", "p", 0.0, 1) != base
    assert gen_key("m2", "p", 0.0, None) != base


# --- form coercion -------------------------------------------------------------------


def test_number_field_clamps_to_range():
    f = Field("limit", "Limit", kind="number", default=10, min=5, max=50)
    assert _coerce("999", f) == 50
    assert _coerce("1", f) == 5
    assert _coerce("20", f) == 20


def test_number_field_falls_back_on_garbage():
    f = Field("limit", "Limit", kind="number", default=10, min=1, max=50)
    assert _coerce("not a number", f) == 10
    assert _coerce(None, f) == 10


def test_text_field_passes_through():
    f = Field("issue", "Issue", kind="textarea", default="")
    assert _coerce("  some text  ", f) == "  some text  "
