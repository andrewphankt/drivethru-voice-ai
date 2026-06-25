"""menu_validator.py — semantic gate for order ops (CLAUDE.md §7, B0).

The GBNF grammar guarantees an <order> is well-formed JSON in the right shape.
This module guarantees it is *real*: every item, size, and mod actually exists
on menu.json. Invalid ops are reported and never applied (DB stays clean, D1).

Public API:
    load_menu(path=None)            -> menu dict
    build_index(menu)               -> {item_id: {"category","sizes","mods","name"}}
    validate_op(op, index, line_item=None) -> (ok: bool, reason: str)

`line_item` is the existing line's item id, needed to validate a `modify`'s
size/mods (those depend on which item is on that line, which lives in the DB).
"""

from __future__ import annotations

import json
from pathlib import Path

# Repo-root-relative default so callers don't hard-code paths.
_DEFAULT_MENU = Path(__file__).resolve().parent.parent / "menu" / "menu.json"

# Categories whose entries are full items keyed by id. `sauces` is handled
# separately because it is a flat list, not an id->spec map.
_ITEM_CATEGORIES = ("combos", "mains", "sides", "drinks")


def load_menu(path: str | Path | None = None) -> dict:
    with open(path or _DEFAULT_MENU, "r", encoding="utf-8") as fh:
        return json.load(fh)


def build_index(menu: dict) -> dict:
    """Flatten the menu into item_id -> capabilities for O(1) lookups."""
    index: dict[str, dict] = {}
    for category in _ITEM_CATEGORIES:
        for item_id, spec in menu.get(category, {}).items():
            index[item_id] = {
                "category": category,
                "name": spec.get("name", item_id),
                "sizes": list(spec.get("sizes", [])),  # [] => sizeless
                "mods": list(spec.get("mods", [])),     # [] => no mods allowed
            }
    # Sauces are orderable items: no size, no mods.
    for sauce in menu.get("sauces", []):
        index[sauce] = {"category": "sauces", "name": sauce, "sizes": [], "mods": []}
    return index


def _validate_size(item_id: str, size, info: dict) -> tuple[bool, str]:
    has_sizes = len(info["sizes"]) > 0
    if has_sizes:
        if size is None:
            return False, f"'{item_id}' requires a size {info['sizes']}, got none"
        if size not in info["sizes"]:
            return False, f"size '{size}' invalid for '{item_id}'; allowed {info['sizes']}"
    else:
        if size is not None:
            return False, f"'{item_id}' is sizeless but got size '{size}'"
    return True, ""


def _validate_mods(item_id: str, mods, info: dict) -> tuple[bool, str]:
    if mods is None:
        return True, ""
    if not isinstance(mods, list):
        return False, f"mods must be a list, got {type(mods).__name__}"
    for mod in mods:
        if mod not in info["mods"]:
            allowed = info["mods"] or "none"
            return False, f"mod '{mod}' invalid for '{item_id}'; allowed {allowed}"
    return True, ""


def _validate_qty(qty) -> tuple[bool, str]:
    if qty is None:
        return True, ""  # null in a modify means "unchanged"
    if not isinstance(qty, int) or isinstance(qty, bool):
        return False, f"qty must be an integer, got {qty!r}"
    if qty < 1:
        return False, f"qty must be >= 1, got {qty}"
    return True, ""


def validate_op(op: dict, index: dict, line_item: str | None = None) -> tuple[bool, str]:
    """Menu-level validation for a single op. Line *existence* (for remove/modify)
    is the DB's concern and checked in order_state.py, not here."""
    if not isinstance(op, dict):
        return False, "op is not an object"
    kind = op.get("op")

    if kind == "clear":
        return True, ""

    if kind == "add":
        item = op.get("item")
        if item not in index:
            return False, f"unknown item '{item}'"
        info = index[item]
        ok, why = _validate_size(item, op.get("size"), info)
        if not ok:
            return False, why
        ok, why = _validate_qty(op.get("qty"))
        if not ok:
            return False, why
        if op.get("qty") is None:
            return False, "add requires a qty"
        ok, why = _validate_mods(item, op.get("mods"), info)
        if not ok:
            return False, why
        return True, ""

    if kind == "remove":
        if not isinstance(op.get("line"), int) or isinstance(op.get("line"), bool):
            return False, "remove requires an integer 'line'"
        return True, ""

    if kind == "modify":
        if not isinstance(op.get("line"), int) or isinstance(op.get("line"), bool):
            return False, "modify requires an integer 'line'"
        if line_item is None:
            # Caller couldn't resolve the line to an item -> line doesn't exist.
            return False, f"modify targets line {op.get('line')} which has no item"
        info = index[line_item]
        # Only validate fields that are actually being changed (non-null).
        if op.get("size") is not None or info["sizes"]:
            ok, why = _validate_size(line_item, op.get("size"), info)
            # A modify may legitimately leave size unchanged (null) even for a
            # sized item, so only fail when a *non-null* bad size was supplied.
            if not ok and op.get("size") is not None:
                return False, why
        ok, why = _validate_qty(op.get("qty"))
        if not ok:
            return False, why
        ok, why = _validate_mods(line_item, op.get("mods"), info)
        if not ok:
            return False, why
        return True, ""

    return False, f"unknown op type {kind!r}"
