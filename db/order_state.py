"""order_state.py — apply order diffs to the authoritative SQLite DB (D1, B0).

Flow per turn: the model emits {"ops":[...], "state":...}. We validate each op
against the menu (menu_validator) AND against current DB reality (does the line
exist?), apply only the valid ones, reject the rest with a reason, then return a
report. The DB after this call is the single source of truth the UI/kitchen show.

Convention for `modify`: a null field means "leave unchanged"; a non-null field
replaces the line's current value (mods replace wholesale, not merge).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
import menu_validator  # noqa: E402
import pricing         # noqa: E402

_SCHEMA = Path(__file__).resolve().parent / "schema.sql"
_VALID_STATES = ("in_progress", "confirmed", "cancelled", "escalated")


def connect(db_path: str = ":memory:") -> sqlite3.Connection:
    """Open a connection and ensure the schema exists."""
    # check_same_thread=False: the voice pipeline runs the model+DB on a worker
    # thread (so audio doesn't stall). Access is serial (one awaited turn at a
    # time), so cross-thread use of this single connection is safe.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
    conn.commit()
    return conn


def _line_item(conn: sqlite3.Connection, line: int) -> str | None:
    row = conn.execute("SELECT item FROM order_lines WHERE line = ?", (line,)).fetchone()
    return row["item"] if row else None


def get_state(conn: sqlite3.Connection) -> dict:
    """Canonical order snapshot — exactly what the kitchen/UI render."""
    lines = [
        {"line": r["line"], "item": r["item"], "size": r["size"],
         "qty": r["qty"], "mods": json.loads(r["mods"])}
        for r in conn.execute("SELECT * FROM order_lines ORDER BY line")
    ]
    meta = conn.execute("SELECT state FROM order_meta WHERE id = 1").fetchone()
    # `total` is computed in code (not by the model) — see pricing.py. Additive:
    # render_current_order ignores it, so trained CURRENT ORDER text is unchanged.
    return {"lines": lines, "state": meta["state"], "total": pricing.order_total(lines)}


def _apply_add(conn: sqlite3.Connection, op: dict) -> int:
    meta = conn.execute("SELECT next_line FROM order_meta WHERE id = 1").fetchone()
    line = meta["next_line"]
    conn.execute(
        "INSERT INTO order_lines (line, item, size, qty, mods) VALUES (?, ?, ?, ?, ?)",
        (line, op["item"], op.get("size"), op.get("qty", 1),
         json.dumps(op.get("mods") or [])),
    )
    conn.execute("UPDATE order_meta SET next_line = ? WHERE id = 1", (line + 1,))
    return line


def _apply_modify(conn: sqlite3.Connection, op: dict) -> None:
    sets, params = [], []
    if op.get("size") is not None:
        sets.append("size = ?"); params.append(op["size"])
    if op.get("qty") is not None:
        sets.append("qty = ?"); params.append(op["qty"])
    if op.get("mods") is not None:
        sets.append("mods = ?"); params.append(json.dumps(op["mods"]))
    if not sets:
        return  # nothing to change
    params.append(op["line"])
    conn.execute(f"UPDATE order_lines SET {', '.join(sets)} WHERE line = ?", params)


def apply_ops(conn: sqlite3.Connection, order: dict, index: dict) -> dict:
    """Validate + apply a model-emitted order object. Returns a report:
        {"applied": [...ops...], "rejected": [{"op":..., "reason":...}], "state": <str>}
    Invalid ops are skipped, never applied. The whole call is one transaction.
    """
    # Defensive: a model may emit a bare ops list, or junk. Coerce to the dict shape.
    if isinstance(order, list):
        order = {"ops": order}
    elif not isinstance(order, dict):
        order = {"ops": []}

    applied, rejected = [], []
    for op in order.get("ops", []):
        kind = op.get("op") if isinstance(op, dict) else None

        # Resolve line->item for remove/modify so we can check existence + (for
        # modify) validate fields against the actual item on that line.
        line_item = None
        if kind in ("remove", "modify"):
            line_item = _line_item(conn, op.get("line"))
            if line_item is None:
                rejected.append({"op": op, "reason": f"no such line {op.get('line')}"})
                continue

        ok, reason = menu_validator.validate_op(op, index, line_item=line_item)
        if not ok:
            rejected.append({"op": op, "reason": reason})
            continue

        if kind == "add":
            _apply_add(conn, op)
        elif kind == "modify":
            _apply_modify(conn, op)
        elif kind == "remove":
            conn.execute("DELETE FROM order_lines WHERE line = ?", (op["line"],))
        elif kind == "clear":
            conn.execute("DELETE FROM order_lines")
        applied.append(op)

    # Order-level state. "escalated" is a TRANSIENT event (fire a human handoff),
    # NOT a persisted state — if we saved it, the next CURRENT ORDER line would show
    # [escalated], the model would echo it, and escalation would stick forever. So we
    # persist in_progress and surface a one-shot `escalated` flag in the report.
    new_state = order.get("state")
    escalated = (new_state == "escalated")
    if escalated:
        conn.execute("UPDATE order_meta SET state = 'in_progress' WHERE id = 1")
    elif new_state in _VALID_STATES:
        conn.execute("UPDATE order_meta SET state = ? WHERE id = 1", (new_state,))
    elif new_state is not None:
        rejected.append({"op": {"state": new_state}, "reason": f"invalid state '{new_state}'"})

    conn.commit()
    report = get_state(conn)
    return {"applied": applied, "rejected": rejected, "state": report["state"],
            "snapshot": report, "escalated": escalated}
