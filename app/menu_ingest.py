"""menu_ingest.py — turn a restaurant's simple item list into a valid menu.json.

The model orders best when each item's id looks like what customers SAY, because
that's what it learned across many menus. So we DERIVE every id from the item NAME
(a slug). A restaurant just lists their items; this builds the menu.json that the
model, pricing, and validator all consume — no retraining needed (Path A).

    from menu_ingest import build_menu, slug
    menu = build_menu([
        {"name": "Doro Wat", "category": "main", "mods": ["extra_spicy"], "price": 13.49},
        {"name": "Collard Greens", "category": "side", "sizes": ["S","L"],
         "prices": {"S": 3.5, "L": 5.5}},
        {"name": "Mango Juice", "category": "drink", "sizes": ["S","L"],
         "prices": {"S": 3.5, "L": 5.0}},
    ])

CLI:  python3 app/menu_ingest.py items.json menu/menu.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_BUCKET = {"combo": "combos", "main": "mains", "side": "sides", "drink": "drinks"}


def slug(name: str) -> str:
    """'Al Pastor Taco' -> 'al_pastor_taco' — a stable, word-matching id."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "item"


def build_menu(items: list[dict], sauces: list | None = None,
               mod_prices: dict | None = None, currency: str = "USD") -> dict:
    """Build a schema-valid menu.json from a flat item list. Each item needs:
        name      (str)                     — customer-facing name; id = slug(name)
        category  ('main'|'side'|'drink'|'combo')
      and any of:
        sizes     (list[str])               — omit/[] for a one-size item
        price     (float)                    — for a sizeless item
        prices    (dict size->float)         — for a sized item
        mods      (list[str])                — allowed modifications
        includes  (list[str])                — for combos (descriptive)
    """
    menu: dict = {"combos": {}, "mains": {}, "sides": {}, "drinks": {},
                  "sauces": list(sauces or []), "mod_prices": dict(mod_prices or {}),
                  "currency": currency}
    seen: set[str] = set()
    for it in items:
        bucket = _BUCKET[it["category"]]
        iid = slug(it["name"])
        if iid in seen:                       # guarantee unique ids
            n = 2
            while f"{iid}_{n}" in seen:
                n += 1
            iid = f"{iid}_{n}"
        seen.add(iid)
        spec: dict = {"name": it["name"]}
        if it.get("sizes"):
            spec["sizes"] = list(it["sizes"])
        elif bucket in ("sides", "drinks", "combos"):
            spec["sizes"] = []
        if "prices" in it:
            spec["prices"] = {k: round(float(v), 2) for k, v in it["prices"].items()}
        elif "price" in it:
            spec["price"] = round(float(it["price"]), 2)
        if it.get("mods") or bucket in ("mains", "drinks"):
            spec["mods"] = list(it.get("mods", []))
        if it.get("includes"):
            spec["includes"] = list(it["includes"])
        menu[bucket][iid] = spec
    return menu


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: python3 app/menu_ingest.py <items.json> <out menu.json>")
    src = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    items = src["items"] if isinstance(src, dict) else src
    menu = build_menu(items, sauces=(src.get("sauces") if isinstance(src, dict) else None),
                      mod_prices=(src.get("mod_prices") if isinstance(src, dict) else None))
    Path(sys.argv[2]).write_text(json.dumps(menu, indent=2), encoding="utf-8")
    n = sum(len(menu[b]) for b in ("combos", "mains", "sides", "drinks"))
    print(f"wrote {sys.argv[2]} — {n} items (ids derived from names)")


if __name__ == "__main__":
    main()
