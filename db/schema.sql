-- SQLite schema for the authoritative drive-thru order (CLAUDE.md D1).
-- The DB — not the model's memory — is the canonical order. The model only
-- proposes diffs; order_state.py applies validated ops to these tables.

-- One row per order line. `line` is a STABLE id assigned at add time and never
-- reused, so cross-turn edits ("make line 2 a large") stay unambiguous even
-- after removals leave gaps.
CREATE TABLE IF NOT EXISTS order_lines (
    line INTEGER PRIMARY KEY,
    item TEXT    NOT NULL,
    size TEXT,                         -- NULL for sizeless items
    qty  INTEGER NOT NULL DEFAULT 1 CHECK (qty >= 1),
    mods TEXT    NOT NULL DEFAULT '[]' -- JSON array of mod strings
);

-- Single-row table holding order-level state + the next line id to hand out.
CREATE TABLE IF NOT EXISTS order_meta (
    id        INTEGER PRIMARY KEY CHECK (id = 1),
    state     TEXT    NOT NULL DEFAULT 'in_progress',
    next_line INTEGER NOT NULL DEFAULT 1
);

INSERT OR IGNORE INTO order_meta (id, state, next_line) VALUES (1, 'in_progress', 1);
