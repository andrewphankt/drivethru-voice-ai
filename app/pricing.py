"""pricing.py — deterministic order pricing (B0 add-on).

The model QUOTES individual item prices straight from the menu in its prompt,
but it must NEVER do arithmetic — a 1.5B can't be trusted to total a check. So
totals are computed here, in code, and shown on the kitchen screen / fed back in
the order snapshot. One source of truth for money: menu.json.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import menu_validator  # noqa: E402


def _base_price(spec: dict, size) -> float:
    """Price of one unit of an item at a given size (mods excluded)."""
    if "prices" in spec:                       # sized item: {"S":..,"M":..,"L":..}
        return float(spec["prices"].get(size, 0.0))
    return float(spec.get("price", 0.0))       # flat-price (sizeless) item


def _spec_for(menu: dict, item: str) -> dict | None:
    for cat in ("combos", "mains", "sides", "drinks"):
        if item in menu.get(cat, {}):
            return menu[cat][item]
    return None  # sauces / unknown -> free


def line_price(item: str, size, mods, menu: dict | None = None) -> float:
    """Unit price of one line (item @ size + paid mods). qty applied by caller."""
    menu = menu or menu_validator.load_menu()
    spec = _spec_for(menu, item)
    if spec is None:
        return 0.0
    price = _base_price(spec, size)
    mod_prices = menu.get("mod_prices", {})
    for m in (mods or []):
        price += float(mod_prices.get(m, 0.0))
    return round(price, 2)


def order_total(lines: list[dict], menu: dict | None = None) -> float:
    """Sum of every line's (unit price x qty). Lines are order_state snapshots."""
    menu = menu or menu_validator.load_menu()
    total = 0.0
    for ln in lines:
        total += line_price(ln["item"], ln.get("size"), ln.get("mods"), menu) * ln.get("qty", 1)
    return round(total, 2)
