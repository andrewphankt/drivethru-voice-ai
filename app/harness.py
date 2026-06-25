"""harness.py — B2 text CLI. Order by typing; watch the canonical DB update.

    python3 app/harness.py

Each turn prints: the model's <say>, the parsed ops, anything the validator
rejected, and the resulting DB state (the source of truth, D1).
Commands: /state  /reset  /quit
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "db"))
sys.path.insert(0, str(ROOT / "data"))

import menu_validator      # noqa: E402
import order_state         # noqa: E402
from order_llm import OrderLLM  # noqa: E402
from contract import render_current_order  # noqa: E402


def render(snap: dict) -> str:
    if not snap["lines"]:
        return "  (order empty)"
    rows = []
    for ln in snap["lines"]:
        size = f' {ln["size"]}' if ln["size"] else ""
        mods = (" [" + ", ".join(ln["mods"]) + "]") if ln["mods"] else ""
        rows.append(f'  ({ln["line"]}) {ln["qty"]}x {ln["item"]}{size}{mods}')
    return "\n".join(rows) + f'\n  state: {snap["state"]}'


def main():
    index = menu_validator.build_index(menu_validator.load_menu())
    conn = order_state.connect(":memory:")
    llm = OrderLLM()

    print("Drive-thru text harness (B2).  Commands: /state  /reset  /quit")
    print("Order something, e.g.:  lemme get a classic burger combo medium")
    while True:
        try:
            user = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user:
            continue
        if user == "/quit":
            break
        if user == "/reset":
            conn = order_state.connect(":memory:")
            llm.reset()
            print("(order + conversation reset)")
            continue
        if user == "/state":
            print(render(order_state.get_state(conn)))
            continue

        # Feed the model the authoritative order BEFORE this turn (v2 memory fix),
        # exactly as the training data is formatted.
        snap = order_state.get_state(conn)
        prefixed = render_current_order(snap) + "\n" + user
        try:
            say, order, raw = llm.respond(prefixed)
        except Exception as e:                     # noqa: BLE001
            print(f"[error talking to drivethru model: {e}]")
            print(" is `ollama` running? try: ollama run drivethru hi")
            continue

        report = order_state.apply_ops(conn, order, index)
        print(f"assistant> {say}")
        print(f"  ops: {order.get('ops')}   (state={order.get('state')})")
        for r in report["rejected"]:
            print(f"  ⚠ REJECTED {r['op']} -> {r['reason']}")
        print("  --- order now ---")
        print(render(report["snapshot"]))
        if report["escalated"]:
            print("  🔔🔔 TEAM MEMBER NEEDED — escalating to a human. 🔔🔔")


if __name__ == "__main__":
    main()
