"""gen_planned.py — plan-then-render synthetic data (the good generator).

WHY this beats "ask Haiku for a whole conversation":
  - WE own the labels. The <order> diff for every turn is built and replayed
    through the real order_state, so it is ground-truth by construction — Haiku
    can NOT mislabel it (the honey-mustard->ketchup class of bug is impossible).
  - Haiku only writes the WORDS (customer line + assistant <say>) around the
    fixed plan. It is forbidden to change items/sizes/qty/mods.
  - Customer lines are rendered ASR-STYLE (lowercase, no punctuation, fillers) to
    match what Whisper actually feeds the model at inference — closes the
    train/inference gap.
  - The scenario MIX (curriculum) and PERSONA are controlled, killing mode
    collapse and over/under-representing the cases you choose.

Usage:
    python3 data/gen_planned.py --dry-run            # build + print plans, NO api calls
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 data/gen_planned.py --n 2000 --seed 11   # render with Haiku, append dataset

Output appends to data/dataset.jsonl (+ ~10% holdout), same format as before.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
for p in ("app", "db", "data"):
    sys.path.insert(0, str(ROOT / p))
import menu_validator      # noqa: E402
import order_state         # noqa: E402
from contract import SYSTEM, MENU_JSON, build_system, render_assistant_turn, render_current_order  # noqa: E402
import menu_factory      # noqa: E402  — diverse menus for menu-agnostic training
import pricing           # noqa: E402  — quote real prices in the price scenario

MODEL = "claude-haiku-4-5"   # renderer only — it never decides labels, so Haiku is ideal
OUT_DIR = ROOT / "data"

# Scenario mix (curriculum). Tune to over-/under-represent cases. Must roughly sum to 1.
SCENARIO_WEIGHTS = {
    "order":         0.10,   # plain order, maybe a light edit
    "edit_heavy":    0.12,   # 2-3 edits — the hard case
    "compound_edit": 0.05,   # "remove X and add Y" in one breath
    "multi_add":     0.05,   # orders 2-3 items in ONE breath -> multiple add ops
    "ask_size":      0.10,   # sized item ordered/resized with NO size -> ASK, then apply
    "correction":    0.06,   # "no, I said..." / "that's wrong" -> fix the AI's mistake
    "off_menu":      0.06,   # asks for an item we DON'T sell -> say no, suggest, add nothing
    "unclear":       0.06,   # garbled/cut-off speech -> ask to repeat, add nothing
    "self_correct":  0.04,   # "a coke, no wait a sprite" -> only the final item, one turn
    "make_combo":    0.03,   # "make it a combo/meal" -> swap the main for the combo
    "reopen":        0.03,   # adds more AFTER confirming -> reopen, add, reconfirm
    "query":         0.05,   # "what's in my order?" -> report it, don't change it
    "menu_q":        0.06,   # "what drinks/sides do you have?"
    "recommend":     0.05,   # "what's good / your favorite?" -> suggest, don't add
    "price":         0.05,   # "how much is X" -> quote item; deflect totals
    "clarify":       0.04,   # vague "can I get a drink" -> ASK which, don't assume
    "logistics":     0.04,   # "do you take card / where do I pay / hours" -> answer, no order change
    "chitchat":      0.03,   # small talk -> redirect
    "grumble":       0.03,   # minor grumble -> do NOT escalate
    "escalate":      0.05,   # real complaint -> escalate to a human
    "allergy":       0.02,   # allergy/safety question -> don't guess, get a team member (escalate)
    "cancel":        0.04,   # cancels the order
}

# --focus presets: reweight the mix to top up a weak area (the data flywheel).
FOCUS_PRESETS = {
    "edits":    {"edit_heavy": 0.70, "compound_edit": 0.15, "order": 0.15},
    "escalate": {"escalate": 0.55, "grumble": 0.20, "order": 0.25},
    "menu":     {"menu_q": 0.50, "chitchat": 0.20, "order": 0.30},
    "query":    {"query": 0.55, "order": 0.25, "edit_heavy": 0.20},
    # the big one: boost ALL the conversational subtopics the live model flubbed
    "convo":    {"query": 0.18, "menu_q": 0.16, "recommend": 0.16, "price": 0.12,
                 "clarify": 0.18, "compound_edit": 0.10, "order": 0.10},
    # the OOD-generalization top-up: edits/corrections/multi-add (the cases that
    # fail on unseen menus), run mostly on synthetic menus (low --real-frac).
    "generalize": {"edit_heavy": 0.24, "compound_edit": 0.12, "correction": 0.16,
                   "ask_size": 0.12, "multi_add": 0.14, "order": 0.10, "off_menu": 0.06,
                   "menu_q": 0.06},
}

PERSONAS = [
    "impatient regular, terse, mild mumbler",
    "friendly non-native speaker, polite, a little hesitant",
    "teenager ordering for friends, fast and slangy",
    "older customer, soft-spoken, a bit unsure of the menu",
    "cheerful chatty morning person",
    "distracted parent with kids talking in the background",
    "blunt no-nonsense trucker",
    "very polite, formal, says please and thank you a lot",
    "hungover and low-energy, short answers",
    "indecisive, changes their mind a lot",
    "rushed, talking fast, half-sentences",
    "laid-back surfer vibe, lots of slang",
]

CHITCHAT_TOPICS = ["how's your day going", "you a real person or a robot",
                   "happy friday", "this weather huh", "you sound cheerful today",
                   "long shift?", "whats good here"]
GRUMBLES = ["the line took forever today", "prices went up again huh",
            "y'all are slow today", "been waiting a while"]
COMPLAINTS = ["you got my order wrong the last three times",
              "i want to speak to a manager",
              "you charged my card twice and nobody fixed it",
              "there was plastic in my burger yesterday",
              "the person at the window was super rude to me",
              "my kid had an allergic reaction to the shake last time",
              "you forgot half my order last time and i'm furious"]
MENU_QS = [("drinks", "Cola, Lemon-Lime Soda, Water, and Milkshakes"),
           ("sides", "Fries, Onion Rings, and a Side Salad"),
           ("milkshake flavors", "vanilla, chocolate, or strawberry"),
           ("whole menu", "burgers, a crispy chicken sandwich, nuggets, a veggie wrap, sides, drinks, and milkshakes"),
           ("burgers", "the Classic Burger and the Double Stack")]
# phrasings the live model mishandled (treated as orders) — render variety around these
QUESTION_PHRASINGS = ["ask what {c} you have", "ask what {c} are there",
                      "ask whats on the menu", "ask what else they can add to the order"]
RECOMMEND_QS = ["what's good here", "what's your favorite", "what do you recommend",
                "what's the best thing on the menu", "im not sure what should i get",
                "whats popular"]
PRICE_QS = ["what's the cheapest thing", "how much is a combo", "what's the deal today",
            "whats the price on the nuggets", "is there a special", "how much for all that"]
VAGUE_ADDS = ["can i get a drink", "lemme get something to drink", "gimme a side",
              "i'll take a burger", "get me a combo", "something to eat", "a shake"]
OFF_MENU_ITEMS = ["a hot dog", "a taco", "a burrito", "mozzarella sticks", "a soft pretzel",
                  "a corn dog", "churros", "a slushie", "a frappuccino", "a gyro", "poutine",
                  "a quesadilla", "a smoothie", "a banana split", "boba tea"]
UNCLEAR_NOTES = ["a garbled half-sentence the mic chopped up", "mumbled and cut off, can't tell the item",
                 "background noise drowns out the words", "trails off mid-word, unintelligible",
                 "static then a couple unclear syllables"]
LOGISTICS_QS = ["do you take card", "do you take apple pay", "can i pay cash", "where do i pay",
                "what time do you close", "are you open late", "do you have a bathroom",
                "wheres the restroom", "can i use the app coupon", "is this for here or to go",
                "do you guys do refills"]
ALLERGY_QS = ["does this have nuts in it", "my kid has a peanut allergy is this okay",
              "is there dairy in this", "does the sauce have soy", "is anything cooked in peanut oil"]


def _off_menu_name(rng, menu):
    have = " ".join(spec["name"].lower() for c in ("combos", "mains", "sides", "drinks")
                    for spec in menu.get(c, {}).values())
    cands = [x for x in OFF_MENU_ITEMS if x.split()[-1] not in have]
    return rng.choice(cands or OFF_MENU_ITEMS)


def _any_item_name(rng, menu):
    names = [spec["name"] for c in ("mains", "combos", "sides", "drinks")
             for spec in menu.get(c, {}).values()]
    return rng.choice(names) if names else "the house special"


def _matching_combo(menu, main_id):
    """The combo built around a given main (so 'make it a combo' picks the right one)."""
    for cid, spec in menu.get("combos", {}).items():
        if main_id in spec.get("includes", []) or main_id in cid:
            return cid
    return None


CAT_LABEL = {"drinks": "drinks", "sides": "sides", "mains": "food"}


# ---- ground-truth ops builders (operate on the live order_state snapshot) ---

def _info(index, item):
    return index[item]


def _add_op(rng, index):
    item = rng.choice(list(index))
    info = index[item]
    size = rng.choice(info["sizes"]) if info["sizes"] else None
    mods = []
    if info["mods"] and rng.random() < 0.4:
        mods = rng.sample(info["mods"], rng.randint(1, min(2, len(info["mods"]))))
    qty = rng.choices([1, 2, 3, 4], [7, 2, 1, 1])[0]
    op = {"op": "add", "item": item, "size": size, "qty": qty, "mods": mods}
    bits = [f"{qty}x {info['name']}"]
    if size:
        bits.append(f"size {size}")
    if mods:
        bits.append("with " + ", ".join(mods))
    desc = " ".join(bits)
    return op, f"order {desc}", f"added {desc}"


def _line_label(index, l):
    """Name a line clearly (with size) so edits aren't ambiguous when items repeat."""
    name = index[l["item"]]["name"]
    return f"{l['size']} {name}" if l["size"] else name


def _edit_op(rng, index, snap):
    """Pick a random edit on an existing line. Returns (op, intent, action) or None."""
    lines = snap["lines"]
    if not lines:
        return None
    choices = ["qty", "remove"]
    if any(index[l["item"]]["sizes"] for l in lines):
        choices.append("resize")
    if any(index[l["item"]]["mods"] for l in lines):
        choices.append("mod")
    kind = rng.choice(choices)
    if kind == "resize":
        cands = [l for l in lines if index[l["item"]]["sizes"]]
        l = rng.choice(cands)
        sizes = [s for s in index[l["item"]]["sizes"] if s != l["size"]]
        new = rng.choice(sizes) if sizes else l["size"]
        name = _line_label(index, l)
        return ({"op": "modify", "line": l["line"], "size": new, "qty": None, "mods": None},
                f"change the {name} to size {new}", f"resized the {name} to {new}")
    if kind == "qty":
        l = rng.choice(lines)
        new = rng.choice([q for q in (1, 2, 3) if q != l["qty"]] or [1])
        name = _line_label(index, l)
        return ({"op": "modify", "line": l["line"], "size": None, "qty": new, "mods": None},
                f"make the {name} a quantity of {new}", f"changed the {name} to qty {new}")
    if kind == "mod":
        cands = [l for l in lines if index[l["item"]]["mods"]]
        l = rng.choice(cands)
        avail = [m for m in index[l["item"]]["mods"] if m not in l["mods"]]
        name = _line_label(index, l)
        if avail:
            new = rng.choice(avail)
            return ({"op": "modify", "line": l["line"], "size": None, "qty": None,
                     "mods": sorted(l["mods"] + [new])},
                    f"add {new} to the {name}", f"added {new} to the {name}")
        # else remove a mod
        rem = rng.choice(l["mods"])
        return ({"op": "modify", "line": l["line"], "size": None, "qty": None,
                 "mods": [m for m in l["mods"] if m != rem]},
                f"actually no {rem} on the {name}", f"removed {rem} from the {name}")
    # remove
    l = rng.choice(lines)
    name = _line_label(index, l)
    return ({"op": "remove", "line": l["line"]}, f"remove the {name}", f"removed the {name}")


def human_order(snap, index):
    if not snap["lines"]:
        return "(empty)"
    parts = []
    for l in snap["lines"]:
        s = f" ({l['size']})" if l["size"] else ""
        m = " +" + ",".join(l["mods"]) if l["mods"] else ""
        parts.append(f"{l['qty']}x {index[l['item']]['name']}{s}{m}")
    return "; ".join(parts)


# ---- build a full dialogue plan (replayed through order_state) ----------------

def build_plan(rng, index, scenario, menu):
    conn = order_state.connect(":memory:")
    turns = []

    def step(order_obj, intent, action):
        pre = order_state.get_state(conn)
        rep = order_state.apply_ops(conn, order_obj, index)
        if rep["rejected"]:
            return False
        turns.append({"pre": pre, "order_obj": order_obj, "intent": intent,
                      "action": action, "post": rep["snapshot"]})
        return True

    # optional opener
    if scenario == "menu_q":
        cats = [c for c in ("drinks", "sides", "mains") if menu.get(c)]
        cat = rng.choice(cats)
        label = CAT_LABEL[cat]
        listing = ", ".join(spec["name"] for spec in menu[cat].values())
        ask = rng.choice(QUESTION_PHRASINGS).format(c=label)
        step({"ops": [], "state": "in_progress"}, ask,
             f"ANSWER the question — list the {label}: {listing}. Emit ops []. DO NOT add anything; a question is not an order")
    elif scenario == "chitchat":
        step({"ops": [], "state": "in_progress"},
             f"small talk: {rng.choice(CHITCHAT_TOPICS)}",
             "one quick friendly line, then redirect to ordering; no order change")
    elif scenario == "grumble":
        step({"ops": [], "state": "in_progress"},
             f"minor grumble: {rng.choice(GRUMBLES)}",
             "apologize warmly and KEEP taking the order; do NOT escalate; no order change")
    elif scenario == "recommend":
        allnames = [spec["name"] for c in ("combos", "mains", "sides", "drinks")
                    for spec in menu.get(c, {}).values()]
        pick = rng.choice(allnames) if allnames else "the house special"
        step({"ops": [], "state": "in_progress"},
             f"asks for a recommendation: {rng.choice(RECOMMEND_QS)}",
             f"suggest ONE item in <say> (e.g. the {pick}); do NOT add it — wait for them to actually order")
    elif scenario == "price":
        if rng.random() < 0.7:
            items = [(iid, c) for c in ("combos", "mains", "sides", "drinks") for iid in menu.get(c, {})]
            iid, c = rng.choice(items)
            spec = menu[c][iid]
            size = rng.choice(spec["sizes"]) if spec.get("sizes") else None
            price = pricing.line_price(iid, size, [], menu)
            name = (f"{size} " if size else "") + spec["name"]
            step({"ops": [], "state": "in_progress"},
                 f"asks the price of the {name}",
                 f"quote the price from the MENU — the {name} is ${price:.2f}. Do NOT total the whole check; no order change")
        else:
            step({"ops": [], "state": "in_progress"},
                 f"asks for the total: {rng.choice(PRICE_QS)}",
                 "say you're ringing it up and the exact total shows on the screen; do NOT add up a number yourself; no order change")
    elif scenario == "clarify":
        step({"ops": [], "state": "in_progress"},
             f"a VAGUE request with no specifics: {rng.choice(VAGUE_ADDS)}",
             "the request is vague (no specific item/size) — ask what kind and what size; add NOTHING yet")
    elif scenario == "ask_size":
        # Customer names a SIZED item but omits the size. The model must ASK (ops []),
        # then apply once they answer. Two variants: a new add, or resizing a line.
        sized = [it for it in index if index[it]["sizes"]]
        if not sized:
            pass  # this menu has no sized items — fall through to a normal order
        elif rng.random() < 0.55:
            # ADD: "let me get a cola" (no size) -> "what size?" -> "large" -> add L
            item = rng.choice(sized); info = index[item]; name = info["name"]
            size = rng.choice(info["sizes"])
            step({"ops": [], "state": "in_progress"},
                 f"order a {name} but do NOT say a size",
                 f"a {name} needs a size — ASK what size; add NOTHING yet (ops [])")
            step({"ops": [{"op": "add", "item": item, "size": size, "qty": 1, "mods": []}],
                  "state": "in_progress"},
                 f"answers the size: {size}", f"now add the {size} {name}")
        else:
            # RESIZE: order a sized line, then "change its size" with no size given -> ASK -> apply
            item = rng.choice(sized); info = index[item]; name = info["name"]
            cur = rng.choice(info["sizes"])
            step({"ops": [{"op": "add", "item": item, "size": cur, "qty": 1, "mods": []}],
                  "state": "in_progress"}, f"order a {cur} {name}", f"added a {cur} {name}")
            line = order_state.get_state(conn)["lines"][-1]["line"]
            new = rng.choice([s for s in info["sizes"] if s != cur] or [cur])
            step({"ops": [], "state": "in_progress"},
                 f"wants to change the {name}'s size but does NOT say to what",
                 f"ASK what size they'd like for the {name}; change NOTHING yet (ops [])")
            step({"ops": [{"op": "modify", "line": line, "size": new, "qty": None, "mods": None}],
                  "state": "in_progress"}, f"answers the size: {new}", f"resize the {name} to {new}")
    elif scenario == "multi_add":
        # several items in ONE breath -> one turn, multiple add ops
        k = rng.randint(2, 3)
        ops, descs = [], []
        for _ in range(k):
            op, _i, action = _add_op(rng, index)
            ops.append(op)
            descs.append(action.replace("added ", "", 1))
        step({"ops": ops, "state": "in_progress"},
             "order several things in ONE breath: " + "; ".join(descs),
             "add ALL of them at once: " + "; ".join(descs))
    elif scenario == "off_menu":
        x = _off_menu_name(rng, menu)
        alt = _any_item_name(rng, menu)
        step({"ops": [], "state": "in_progress"},
             f"asks for {x} — which is NOT on this menu",
             f"we don't carry {x}; say so politely and point them to the closest thing we DO have "
             f"(e.g. the {alt}); add NOTHING (ops [])")
    elif scenario == "unclear":
        step({"ops": [], "state": "in_progress"},
             f"says {rng.choice(UNCLEAR_NOTES)}",
             "you genuinely could NOT make out what they want — politely ask them to repeat it; "
             "do NOT guess an item; add NOTHING (ops [])")
    elif scenario == "logistics":
        step({"ops": [], "state": "in_progress"},
             f"a non-order question: {rng.choice(LOGISTICS_QS)}",
             "answer briefly and naturally (e.g. card's fine, you pay at the window) then steer back to "
             "the order; this is NOT an item — ops [], no order change")
    elif scenario == "allergy":
        step({"ops": [], "state": "escalated"},
             f"an allergy/safety question: {rng.choice(ALLERGY_QS)}",
             "do NOT guess ingredients for an allergy/safety question — say you'll grab a team member who "
             "can check the ingredients for them; ESCALATE")
    elif scenario == "make_combo":
        with_combo = [(mid, _matching_combo(menu, mid)) for mid in menu.get("mains", {})]
        with_combo = [(m, c) for m, c in with_combo if c]
        if with_combo:
            mid, cid = rng.choice(with_combo)
            mname = menu["mains"][mid]["name"]
            cspec = menu["combos"][cid]
            csize = rng.choice(cspec["sizes"]) if cspec.get("sizes") else None
            step({"ops": [{"op": "add", "item": mid, "size": None, "qty": 1, "mods": []}],
                  "state": "in_progress"}, f"order a {mname}", f"added a {mname}")
            line = order_state.get_state(conn)["lines"][-1]["line"]
            step({"ops": [{"op": "remove", "line": line},
                          {"op": "add", "item": cid, "size": csize, "qty": 1, "mods": []}],
                  "state": "in_progress"},
                 f"make the {mname} a combo / meal",
                 f"swap it to the {cspec['name']}: remove the {mname} and add the combo")

    # build the order: 1-3 adds
    n_add = rng.randint(1, 3)
    for j in range(n_add):
        op, intent, action = _add_op(rng, index)
        if scenario == "self_correct" and j == 0:
            # single-turn change of mind: name another item first, then switch — only `op` is wanted
            other = _any_item_name(rng, menu)
            desc = action.replace("added ", "", 1)
            intent = f"start to order {other} then change your mind mid-sentence — you actually want {desc}"
            action = f"they switched mid-breath; only the final item — {action}"
        step({"ops": [op], "state": "in_progress"}, intent, action)

    # edits
    if scenario == "compound_edit":
        snap = order_state.get_state(conn)
        if snap["lines"]:
            l = rng.choice(snap["lines"])
            add_op, _ai, add_action = _add_op(rng, index)
            rem_name = _line_label(index, l)
            add_desc = add_action.replace("added ", "", 1)
            step({"ops": [{"op": "remove", "line": l["line"]}, add_op], "state": "in_progress"},
                 f"in one breath: remove the {rem_name} and add {add_desc}",
                 f"removed the {rem_name} and added {add_desc}")
    elif scenario == "correction":
        snap = order_state.get_state(conn)
        e = _edit_op(rng, index, snap)
        if e:
            op, intent, action = e
            step({"ops": [op], "state": "in_progress"},
                 f"insists you got it wrong — {intent} (correcting a misheard item/mod, not a new request)",
                 f"apologize briefly for the mix-up and fix it — {action}")
    else:
        n_edit = {"edit_heavy": rng.randint(2, 3)}.get(scenario, rng.choices([0, 1, 2], [4, 3, 2])[0])
        for _ in range(n_edit):
            snap = order_state.get_state(conn)
            e = _edit_op(rng, index, snap)
            if e:
                op, intent, action = e
                step({"ops": [op], "state": "in_progress"}, intent, action)

    # mid-order query — customer asks what's in their order (a common live gap)
    if scenario == "query" or (scenario in ("order", "edit_heavy", "compound_edit")
                               and rng.random() < 0.12):
        step({"ops": [], "state": "in_progress"},
             "ask what's in my order so far",
             "read back the current order from CURRENT ORDER aloud; no order change")

    # ending
    if scenario == "escalate":
        step({"ops": [], "state": "escalated"},
             f"real complaint: {rng.choice(COMPLAINTS)}",
             "briefly apologize and say you're getting a team member (ESCALATE)")
    elif scenario == "cancel":
        step({"ops": [{"op": "clear"}], "state": "cancelled"},
             "cancel the whole order", "clear the order; it's cancelled")
    elif scenario == "reopen":
        step({"ops": [], "state": "confirmed"}, "that's everything", "confirm the order")
        op, intent, action = _add_op(rng, index)
        step({"ops": [op], "state": "in_progress"},
             f"oh wait — after confirming, also {intent}", f"reopen the order and {action}")
        step({"ops": [], "state": "confirmed"}, "okay that's really everything now", "confirm again")
    else:
        step({"ops": [], "state": "confirmed"}, "that's everything", "confirm the order")

    return turns


# ---- render with Haiku (words only) ------------------------------------------

RENDER_SYSTEM = (
    "You render natural spoken language for drive-thru training dialogues. You are given a "
    "FIXED PLAN: the turns and exactly what changes on each turn are already decided. Your "
    "ONLY job is to write the words. You must NOT add, drop, or change any item, size, "
    "quantity, or modifier — the plan is ground truth. Do not introduce items not in the plan."
)


def render_prompt(plan, persona, menu_json, index):
    plan_lines = []
    for i, t in enumerate(plan, 1):
        plan_lines.append(
            f"Turn {i} | CUSTOMER intent: {t['intent']} | ASSISTANT did: {t['action']} | "
            f"order now: {human_order(t['post'], index)}")
    fmt = "\n".join(f"C{i}: ...\nA{i}: ..." for i in range(1, len(plan) + 1))
    return f"""MENU (for correct item names only — do not invent items):
{menu_json}

PERSONA for this customer: {persona}

HOW TO WRITE:
- CUSTOMER lines look like raw speech-to-text output: mostly lowercase, little or no
  punctuation, natural fillers ("uh","um","like","lemme","gimme"), occasional self-
  corrections ("wait no") and run-ons. Vary the wording hard; never sound scripted. Each
  line must clearly express that turn's intent so the order is unambiguous.
- ASSISTANT lines: a friendly but EFFICIENT worker. Short. Confirm what changed. Match the
  customer's energy with at most ONE quick personality beat, then move on. Never chit-chat
  across turns.

PLAN (actions are FIXED — render words only, one customer + one assistant line per turn):
{chr(10).join(plan_lines)}

OUTPUT EXACTLY THIS, nothing else:
{fmt}"""


def parse_render(text, n):
    cs, as_ = {}, {}
    for line in text.splitlines():
        m = re.match(r"\s*C(\d+):\s*(.*)", line)
        if m:
            cs[int(m.group(1))] = m.group(2).strip(); continue
        m = re.match(r"\s*A(\d+):\s*(.*)", line)
        if m:
            as_[int(m.group(1))] = m.group(2).strip()
    for i in range(1, n + 1):
        if not cs.get(i) or not as_.get(i):
            return None
    return cs, as_


def stitch(plan, cs, as_, system):
    msgs = [{"role": "system", "content": system}]
    for i, t in enumerate(plan, 1):
        msgs.append({"role": "user",
                     "content": render_current_order(t["pre"]) + "\n" + cs[i]})
        msgs.append({"role": "assistant",
                     "content": render_assistant_turn(as_[i], t["order_obj"])})
    return {"messages": msgs}


_INDEX = menu_validator.build_index(menu_validator.load_menu())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--dry-run", action="store_true", help="build + print plans, no API calls")
    ap.add_argument("--focus", choices=["edits", "escalate", "menu", "query", "convo", "generalize"],
                    default=None, help="reweight the scenario mix to top up a weak area")
    ap.add_argument("--real-only", action="store_true",
                    help="use ONLY the real menu (no synthetic menus) — for flywheel top-ups on our menu")
    ap.add_argument("--real-frac", type=float, default=0.30,
                    help="fraction of dialogues on the REAL menu (rest synthetic). Lower = more menu diversity.")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    mix = FOCUS_PRESETS[args.focus] if args.focus else SCENARIO_WEIGHTS
    scenarios = list(mix)
    weights = [mix[s] for s in scenarios]

    # Per-dialogue menu: ~30% the REAL menu (stay sharp on what we deploy), ~70% a
    # random synthetic menu (learn "order from whatever menu is in the prompt").
    REAL = (menu_validator.load_menu(), _INDEX, SYSTEM, MENU_JSON)

    def pick_menu():
        if args.real_only or rng.random() < args.real_frac:
            return REAL
        m = menu_factory.random_menu(rng)
        idx = menu_validator.build_index(m)
        mj = json.dumps(m, indent=2)
        return m, idx, build_system(mj), mj

    if args.dry_run:
        for _ in range(6):
            sc = rng.choices(scenarios, weights)[0]
            persona = rng.choice(PERSONAS)
            menu, index, system, mjson = pick_menu()
            theme = "REAL" if menu is REAL[0] else "synth"
            plan = build_plan(rng, index, sc, menu)
            print(f"\n===== scenario={sc} | menu={theme} | persona={persona} | {len(plan)} turns =====")
            for i, t in enumerate(plan, 1):
                print(f"  T{i} intent: {t['intent']}")
                print(f"     order_obj: {json.dumps(t['order_obj'])}")
            cs = {i: f"<customer line {i}>" for i in range(1, len(plan) + 1)}
            as_ = {i: f"<assistant say {i}>" for i in range(1, len(plan) + 1)}
            ex = stitch(plan, cs, as_, system)
            print(f"     -> {len(ex['messages'])} messages; system carries {len(system)} chars of menu+rules")
        print("\n(dry run — no API calls, no files written)")
        return

    client = anthropic.Anthropic()
    print(f"Renderer model: {MODEL} | attempting {args.n} dialogues (seed {args.seed})")
    train_f = open(OUT_DIR / "dataset.jsonl", "a", encoding="utf-8")
    hold_f = open(OUT_DIR / "dataset_holdout.jsonl", "a", encoding="utf-8")
    kept = held = discarded = 0
    for i in range(args.n):
        sc = rng.choices(scenarios, weights)[0]
        persona = rng.choice(PERSONAS)
        menu, index, system, mjson = pick_menu()
        if menu is not REAL[0]:   # mark the dataset as menu-randomized (guards reembed)
            (OUT_DIR / ".synthetic_menus_present").touch()
        plan = build_plan(rng, index, sc, menu)
        try:
            resp = client.messages.create(
                model=MODEL, max_tokens=1500,
                system=RENDER_SYSTEM,
                messages=[{"role": "user", "content": render_prompt(plan, persona, mjson, index)}])
        except anthropic.APIError as e:
            print(f"[{i}] API error: {e}", file=sys.stderr); continue
        text = next((b.text for b in resp.content if b.type == "text"), "")
        parsed = parse_render(text, len(plan))
        if parsed is None:
            discarded += 1
        else:
            ex = stitch(plan, *parsed, system)
            if i % 10 == 0:
                hold_f.write(json.dumps(ex) + "\n"); hold_f.flush(); held += 1
            else:
                train_f.write(json.dumps(ex) + "\n"); train_f.flush(); kept += 1
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{args.n}  kept={kept} held={held} discarded={discarded}")
    train_f.close(); hold_f.close()
    print(f"\nDone. added train={kept} holdout={held} discarded={discarded}")


if __name__ == "__main__":
    main()
