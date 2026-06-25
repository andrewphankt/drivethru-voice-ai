"""test_b0.py — B0 acceptance check (CLAUDE.md §3, §16).

Feeds a sequence of diffs through the validator + DB and prints state after each.
Acceptance: valid diffs update the DB; the invalid op is rejected, not applied.
Run: python3 db/test_b0.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import menu_validator
import order_state


def show(label, report):
    snap = report["snapshot"]
    print(f"\n=== {label} ===")
    print(f"  state: {snap['state']}")
    for ln in snap["lines"]:
        print(f"  line {ln['line']}: {ln['qty']}x {ln['item']} "
              f"size={ln['size']} mods={ln['mods']}")
    if not snap["lines"]:
        print("  (order empty)")
    for r in report["rejected"]:
        print(f"  REJECTED {json.dumps(r['op'])} -> {r['reason']}")


def main():
    menu = menu_validator.load_menu()
    index = menu_validator.build_index(menu)
    conn = order_state.connect(":memory:")

    failures = []

    # Turn 1: customer orders a classic combo (M) + a large fries.
    r = order_state.apply_ops(conn, {"ops": [
        {"op": "add", "item": "combo_classic", "size": "M", "qty": 1, "mods": []},
        {"op": "add", "item": "fries", "size": "L", "qty": 1, "mods": []},
    ], "state": "in_progress"}, index)
    show("T1: add combo (M) + large fries", r)
    if len(r["snapshot"]["lines"]) != 2:
        failures.append("T1 should have 2 lines")

    # Turn 2: EDIT — make the combo a Large; add bacon is NOT valid on a combo.
    r = order_state.apply_ops(conn, {"ops": [
        {"op": "modify", "line": 1, "size": "L", "qty": None, "mods": None},
    ], "state": "in_progress"}, index)
    show("T2: edit combo -> L", r)
    if r["snapshot"]["lines"][0]["size"] != "L":
        failures.append("T2 combo should be size L")

    # Turn 3: add a shake with a valid flavor mod, and a burger with no_onion.
    r = order_state.apply_ops(conn, {"ops": [
        {"op": "add", "item": "drink_shake", "size": "M", "qty": 2, "mods": ["chocolate"]},
        {"op": "add", "item": "burger_classic", "size": None, "qty": 1, "mods": ["no_onion"]},
    ], "state": "in_progress"}, index)
    show("T3: add 2 shakes + burger no_onion", r)
    if len(r["snapshot"]["lines"]) != 4:
        failures.append("T3 should have 4 lines")

    # Turn 4: INVALID op — 'unicorn_burger' isn't on the menu. Must be rejected,
    # and the valid remove in the same turn must still apply (line 2 = fries).
    r = order_state.apply_ops(conn, {"ops": [
        {"op": "add", "item": "unicorn_burger", "size": "L", "qty": 1, "mods": []},
        {"op": "remove", "line": 2},
    ], "state": "in_progress"}, index)
    show("T4: invalid add (rejected) + remove fries", r)
    if not any("unknown item" in r2["reason"] for r2 in r["rejected"]):
        failures.append("T4 invalid item should be rejected")
    if any(ln["line"] == 2 for ln in r["snapshot"]["lines"]):
        failures.append("T4 fries (line 2) should be removed")

    # Turn 5: INVALID — bad size 'XL' on a burger (sizeless) + bad mod on combo.
    r = order_state.apply_ops(conn, {"ops": [
        {"op": "add", "item": "burger_double", "size": "XL", "qty": 1, "mods": []},
        {"op": "modify", "line": 99, "size": "L", "qty": None, "mods": None},
    ], "state": "in_progress"}, index)
    show("T5: invalid size + modify nonexistent line", r)
    if len(r["rejected"]) != 2:
        failures.append("T5 should reject both ops")

    # Turn 6: confirm the order.
    r = order_state.apply_ops(conn, {"ops": [], "state": "confirmed"}, index)
    show("T6: confirm", r)
    if r["snapshot"]["state"] != "confirmed":
        failures.append("T6 state should be confirmed")

    print("\n" + "=" * 40)
    if failures:
        print("FAIL:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("PASS — valid diffs applied, invalid ops rejected, DB is source of truth.")


if __name__ == "__main__":
    main()
