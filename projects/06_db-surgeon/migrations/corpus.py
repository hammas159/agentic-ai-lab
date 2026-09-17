"""A corpus of migration pairs that look correct in review.

Every pair here is the kind of thing that gets approved: the `down` is a
plausible inverse of the `up`, the schemas match afterwards, and nothing in
the diff looks alarming. They are written the way people write them, not
written to fail.

Used by `scripts/sweep.py` to produce the numbers in the README.
"""

from __future__ import annotations

SCHEMA = """
CREATE TABLE users (
    id       INTEGER PRIMARY KEY,
    email    TEXT NOT NULL,
    nickname TEXT,
    status   TEXT NOT NULL DEFAULT 'active',
    score    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE orders (
    id       INTEGER PRIMARY KEY,
    user_id  INTEGER NOT NULL REFERENCES users(id),
    total    REAL NOT NULL,
    note     TEXT
);
CREATE INDEX idx_orders_user ON orders(user_id);
"""

SEED = """
INSERT INTO users (id, email, nickname, status, score) VALUES
    (1, 'ann@example.com', 'ann',  'active',   10),
    (2, 'bob@example.com', 'bob',  'active',   25),
    (3, 'cat@example.com', NULL,   'disabled',  0),
    (4, 'dan@example.com', 'dan',  'active',    7);
INSERT INTO orders (id, user_id, total, note) VALUES
    (1, 1, 19.99, 'gift wrap'),
    (2, 1,  5.00, NULL),
    (3, 2, 42.50, 'express'),
    (4, 4,  8.25, NULL);
"""

# (name, up, down, what the author believed)
CASES: list[tuple[str, str, str, str]] = [
    (
        "add a nullable column",
        "ALTER TABLE users ADD COLUMN phone TEXT;",
        "ALTER TABLE users DROP COLUMN phone;",
        "reversible - nothing existed there before",
    ),
    (
        "drop an unused column",
        "ALTER TABLE users DROP COLUMN nickname;",
        "ALTER TABLE users ADD COLUMN nickname TEXT;",
        "reversible - the down recreates the column",
    ),
    (
        "rename a column",
        "ALTER TABLE users RENAME COLUMN nickname TO display_name;",
        "ALTER TABLE users RENAME COLUMN display_name TO nickname;",
        "reversible - a rename is symmetric",
    ),
    (
        "add an index",
        "CREATE INDEX idx_users_email ON users(email);",
        "DROP INDEX idx_users_email;",
        "reversible - an index is derived data",
    ),
    (
        "drop an index",
        "DROP INDEX idx_orders_user;",
        "CREATE INDEX idx_orders_user ON orders(user_id);",
        "reversible - rebuilt from the rows",
    ),
    (
        "backfill a default",
        "UPDATE users SET status = 'active' WHERE status IS NULL;",
        "UPDATE users SET status = NULL WHERE status = 'active';",
        "reversible - the down puts the NULLs back",
    ),
    (
        "normalise a value in place",
        "UPDATE users SET email = LOWER(email);",
        "-- emails were already lowercase, nothing to undo",
        "reversible - lowercasing is idempotent",
    ),
    (
        "drop a lookup table",
        "DROP TABLE orders;",
        """CREATE TABLE orders (
            id      INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            total   REAL NOT NULL,
            note    TEXT
        );""",
        "reversible - the down recreates the table",
    ),
    (
        "widen a column type",
        "ALTER TABLE users ADD COLUMN score_big INTEGER;\n"
        "UPDATE users SET score_big = score;\n"
        "ALTER TABLE users DROP COLUMN score;",
        "ALTER TABLE users ADD COLUMN score INTEGER NOT NULL DEFAULT 0;\n"
        "UPDATE users SET score = score_big;\n"
        "ALTER TABLE users DROP COLUMN score_big;",
        "reversible - the values are copied both ways",
    ),
    (
        "clear a column before removing it",
        "UPDATE orders SET note = NULL;\nALTER TABLE orders DROP COLUMN note;",
        "ALTER TABLE orders ADD COLUMN note TEXT;",
        "reversible - the column comes back",
    ),
    (
        "delete soft-deleted rows",
        "DELETE FROM users WHERE status = 'disabled';",
        "-- nothing to undo, those users were disabled",
        "reversible - only inactive rows removed",
    ),
    (
        "add a NOT NULL column with no default",
        "ALTER TABLE users ADD COLUMN country TEXT NOT NULL;",
        "ALTER TABLE users DROP COLUMN country;",
        "reversible - simple add and drop",
    ),
]
