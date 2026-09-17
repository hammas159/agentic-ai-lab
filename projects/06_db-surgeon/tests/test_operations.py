"""Static classification tests, and the honest limits of pattern matching."""

from __future__ import annotations

import pytest

from dbsurgeon.operations import BLOCKING, LOSSY, REVERSIBLE, classify, classify_script
from dbsurgeon.plan import build

SCHEMA = "CREATE TABLE t (id INTEGER PRIMARY KEY, a TEXT, b INTEGER NOT NULL DEFAULT 0);"
SEED = "INSERT INTO t VALUES (1,'x',5),(2,'y',6),(3,NULL,7);"


@pytest.mark.parametrize(
    ("sql", "kind", "category"),
    [
        ("DROP TABLE users;", "drop_table", LOSSY),
        ("ALTER TABLE users DROP COLUMN nickname;", "drop_column", LOSSY),
        ("TRUNCATE TABLE users;", "truncate", LOSSY),
        ("DELETE FROM users;", "delete_all", LOSSY),
        ("UPDATE users SET a = 1;", "update", LOSSY),
        ("ALTER TABLE users RENAME COLUMN a TO b;", "rename", REVERSIBLE),
        ("ALTER TABLE users ADD COLUMN phone TEXT;", "add_column", REVERSIBLE),
        ("CREATE TABLE x (id INTEGER);", "create_table", REVERSIBLE),
        ("DROP INDEX idx_a;", "drop_index", REVERSIBLE),
        ("INSERT INTO users VALUES (1);", "insert", REVERSIBLE),
        ("CREATE INDEX idx_a ON users(a);", "create_index", BLOCKING),
        (
            "CREATE INDEX CONCURRENTLY idx_a ON users(a);",
            "create_index_concurrently",
            REVERSIBLE,
        ),
        (
            "ALTER TABLE users ADD COLUMN c TEXT NOT NULL;",
            "add_notnull_no_default",
            BLOCKING,
        ),
    ],
)
def test_statements_are_classified(sql: str, kind: str, category: str):
    op = classify(sql)
    assert op.kind == kind
    assert op.category == category


def test_add_notnull_with_a_default_is_not_blocking():
    op = classify("ALTER TABLE users ADD COLUMN c TEXT NOT NULL DEFAULT 'x';")
    assert op.kind == "add_column"
    assert op.category == REVERSIBLE


def test_targets_are_extracted():
    assert classify("DROP TABLE orders;").target == "orders"
    assert classify("CREATE INDEX idx_x ON t(a);").target == "idx_x"
    assert classify("ALTER TABLE users ADD COLUMN c TEXT;").target == "users"


def test_an_unrecognised_statement_is_unknown_not_guessed():
    op = classify("VACUUM;")
    assert op.category == "unknown"
    assert "round-trip is the authority" in op.reason


def test_a_script_classifies_every_statement():
    ops = classify_script("ALTER TABLE t ADD COLUMN c TEXT; DROP TABLE t;")
    assert [o.kind for o in ops] == ["add_column", "drop_table"]


# -- where the static rules are wrong, and the tool says so ---------------


def test_a_false_positive_is_reported_as_a_disagreement():
    """An UPDATE is flagged lossy, but this one restores the original values.

    The round-trip proves it and the disagreement is surfaced, because a
    pattern that mispredicts is a defect in this tool rather than something
    to hide behind a confident verdict.
    """
    plan = build(
        "idempotent update",
        SCHEMA,
        SEED,
        "UPDATE t SET a = LOWER(a);",
        "-- already lowercase",
    )
    assert plan.predicted_lossy
    assert plan.observed_lossy is False
    assert any("too pessimistic" in d for d in plan.disagreements)


def test_a_false_negative_is_reported_as_a_disagreement():
    """A qualified DELETE matches no lossy rule and still destroys rows."""
    plan = build(
        "qualified delete",
        SCHEMA,
        SEED,
        "DELETE FROM t WHERE b > 5;",
        "-- nothing to undo",
    )
    assert not plan.predicted_lossy
    assert plan.observed_lossy is True
    assert any("gap" in d for d in plan.disagreements)


def test_agreement_produces_no_disagreement():
    plan = build(
        "clean add",
        SCHEMA,
        SEED,
        "ALTER TABLE t ADD COLUMN c TEXT;",
        "ALTER TABLE t DROP COLUMN c;",
    )
    assert plan.disagreements == []
    assert plan.safe


def test_a_migration_that_cannot_run_is_reported_not_raised():
    plan = build("broken", SCHEMA, SEED, "ALTER TABLE nope DROP COLUMN x;", "-- none")
    assert plan.error is not None
    assert plan.verdict == "did not run"
    assert not plan.safe
