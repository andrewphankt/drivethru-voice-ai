"""smoke_novel_menu.py — does the model order from a menu it has NEVER seen?

This is the Path-A generalization check. The menu below (Ethiopian) is in NONE of
the training themes — completely out of distribution. We hand a fixed set of turns
to the LOCAL model with this menu in its system prompt and check it produces the
right order DIFF (semantic, state-based — same metric as eval.py). No API money:
it only calls the local Ollama `drivethru` model.

    ollama serve            # in another terminal, if not already up
    python3 train/smoke_novel_menu.py

A high score here = the model learned the SKILL "order from whatever menu is in my
prompt", so a real restaurant can drop in açaí / original dishes with no retraining.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in ("app", "db", "data"):
    sys.path.insert(0, str(ROOT / p))
sys.path.insert(0, str(Path(__file__).resolve().parent))   # to import eval.py
import menu_validator                       # noqa: E402
from contract import build_system, render_current_order  # noqa: E402
from order_llm import parse_reply           # noqa: E402
from eval import chat, state_match          # noqa: E402  (reuse the real metric)

# A menu in NO training theme (Ethiopian) — but ids are the slug of each item NAME,
# exactly how our menu ingestion builds menu.json. That's the realistic case (the
# owner types names; we derive ids), so this tests pure menu generalization, not an
# adversarial id/word mismatch.
NOVEL_MENU = {
    "combos": {
        "veggie_combo": {"name": "Veggie Combo", "sizes": ["M", "L"],
                         "includes": ["shiro_wat", "collard_greens", "injera"], "prices": {"M": 12.99, "L": 15.99}},
    },
    "mains": {
        "doro_wat": {"name": "Doro Wat", "mods": ["extra_spicy", "mild", "add_egg"], "price": 13.49},
        "kitfo": {"name": "Kitfo", "mods": ["rare", "well_done"], "price": 14.99},
        "shiro_wat": {"name": "Shiro Wat", "mods": ["extra_spicy", "add_injera"], "price": 10.99},
        "beef_tibs": {"name": "Beef Tibs", "mods": ["extra_onion", "no_pepper"], "price": 13.99},
    },
    "sides": {
        "injera": {"name": "Injera", "sizes": [], "price": 2.5},
        "ayib_cheese": {"name": "Ayib Cheese", "sizes": [], "price": 3.0},
        "collard_greens": {"name": "Collard Greens", "sizes": ["S", "L"], "prices": {"S": 3.5, "L": 5.5}},
    },
    "drinks": {
        "ethiopian_coffee": {"name": "Ethiopian Coffee", "sizes": ["S", "M", "L"], "prices": {"S": 2.0, "M": 2.5, "L": 3.0}},
        "mango_juice": {"name": "Mango Juice", "sizes": ["S", "L"], "prices": {"S": 3.5, "L": 5.0}},
        "water": {"name": "Water", "sizes": ["M"], "prices": {"M": 0.0}},
    },
    "sauces": ["awaze", "mitmita"],
    "mod_prices": {"add_egg": 1.5, "add_injera": 2.0},
    "currency": "USD",
}
NOVEL_SYSTEM = build_system(json.dumps(NOVEL_MENU, indent=2))
NOVEL_INDEX = menu_validator.build_index(NOVEL_MENU)


def S(lines, state="in_progress"): return {"lines": lines, "state": state}
def Ln(line, item, size, qty, mods): return {"line": line, "item": item, "size": size, "qty": qty, "mods": mods}
EMPTY = S([])

# (label, pre, customer_text, gold_ops). gold_ops is the correct DIFF for that turn.
CASES = [
    ("plain add", EMPTY, "let me get a doro wat",
     [{"op": "add", "item": "doro_wat", "size": None, "qty": 1, "mods": []}]),
    ("add a mod", S([Ln(1, "doro_wat", None, 1, [])]), "can you make that one extra spicy",
     [{"op": "modify", "line": 1, "size": None, "qty": None, "mods": ["extra_spicy"]}]),
    ("menu question (no add)", EMPTY, "what sides do you guys have", []),
    ("sized add", EMPTY, "i'll do a large collard greens",
     [{"op": "add", "item": "collard_greens", "size": "L", "qty": 1, "mods": []}]),
    ("multi-item add", EMPTY, "gimme a shiro wat and a small ethiopian coffee",
     [{"op": "add", "item": "shiro_wat", "size": None, "qty": 1, "mods": []},
      {"op": "add", "item": "ethiopian_coffee", "size": "S", "qty": 1, "mods": []}]),
    ("sizeless add", S([Ln(1, "beef_tibs", None, 1, [])]), "can i add an injera",
     [{"op": "add", "item": "injera", "size": None, "qty": 1, "mods": []}]),
    ("change qty", S([Ln(1, "doro_wat", None, 1, [])]), "actually make it two",
     [{"op": "modify", "line": 1, "size": None, "qty": 2, "mods": None}]),
    ("remove", S([Ln(1, "shiro_wat", None, 1, []), Ln(2, "kitfo", None, 1, [])]), "scratch the kitfo",
     [{"op": "remove", "line": 2}]),
    ("price question (no add)", EMPTY, "how much is the kitfo", []),
    ("question is not an order", EMPTY, "do you have any beef tibs", []),
]


def main():
    print(f"Novel-menu smoke test: {len(CASES)} turns on an UNSEEN menu (Ethiopian)\n")
    ok = 0
    for label, pre, text, gold in CASES:
        msgs = [{"role": "system", "content": NOVEL_SYSTEM},
                {"role": "user", "content": render_current_order(pre) + "\n" + text}]
        try:
            reply, _ = chat("drivethru", msgs)
        except Exception as e:  # noqa: BLE001
            sys.exit(f"❌ could not reach the model ({e}). Is `ollama serve` running and `drivethru` created?")
        _say, order = parse_reply(reply)
        passed = state_match(pre, gold, order.get("ops", []), NOVEL_INDEX)
        ok += passed
        mark = "✅" if passed else "❌"
        print(f"  {mark} {label}")
        print(f"       customer: {text}")
        print(f"       model ops: {json.dumps(order.get('ops', []))}")
        if not passed:
            print(f"       expected:  {json.dumps(gold)}")
    print(f"\nGeneralization on an unseen menu: {ok}/{len(CASES)} = {100*ok/len(CASES):.0f}%")
    print("(High = the model orders from menus it never trained on. Low = needs more themes/data.)")


if __name__ == "__main__":
    main()
