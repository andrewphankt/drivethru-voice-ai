"""gen_synthetic_orders.py — HUMAN runbook §4 / §17 (you run this on your Mac).

Generates synthetic drive-thru dialogues with Claude Haiku, validates every
<order> by REPLAYING it through the real DB (db/order_state.py) + validator,
and writes clean training data to data/dataset.jsonl (+ a 10% holdout set).

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...        # your key (see the runbook)
    python3 data/gen_synthetic_orders.py --n 50          # tiny test run first
    python3 data/gen_synthetic_orders.py --n 12000       # the real run later

Each output line is ONE dialogue as a chat conversation:
    {"messages": [ {system}, {user}, {assistant}, {user}, {assistant}, ... ]}
The assistant turns are the training targets (<say>+<order>); Unsloth trains
loss on assistant turns only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "db"))
sys.path.insert(0, str(ROOT / "data"))

import menu_validator      # noqa: E402
import order_state         # noqa: E402
from contract import SYSTEM, MENU_JSON, render_assistant_turn, render_current_order  # noqa: E402

MODEL = "claude-haiku-4-5"   # the generator (your choice). Swap if needed.
OUT_DIR = ROOT / "data"

# ---- deterministic-ish sampling without Math.random (index-seeded) ----------
# We vary the injected order/edits per dialogue so the generator writes variety.
import random  # noqa: E402  (stdlib random is fine here; this is offline tooling)


def sample_order(index: dict, rng: random.Random) -> list[dict]:
    """Pick 1–4 realistic line items honoring menu size/mod rules."""
    ids = list(index.keys())
    n = rng.randint(1, 4)
    order = []
    for _ in range(n):
        item = rng.choice(ids)
        info = index[item]
        size = rng.choice(info["sizes"]) if info["sizes"] else None
        mods = []
        if info["mods"] and rng.random() < 0.4:
            k = rng.randint(1, min(2, len(info["mods"])))
            mods = rng.sample(info["mods"], k)
        order.append({"item": item, "size": size, "qty": rng.randint(1, 3), "mods": mods})
    return order


def describe_order(order: list[dict], index: dict) -> str:
    lines = []
    for o in order:
        name = index[o["item"]]["name"]
        bits = [f'{o["qty"]}x {name}']
        if o["size"]:
            bits.append(f'size {o["size"]}')
        if o["mods"]:
            bits.append("mods: " + ", ".join(o["mods"]))
        lines.append(" — ".join(bits))
    return "\n".join(f"  - {ln}" for ln in lines)


def sample_edits(order: list[dict], index: dict, rng: random.Random) -> list[str]:
    """0–3 natural-language edits, biased toward >=1 (edits are the hard case)."""
    if not order:
        return []
    k = rng.choices([0, 1, 2, 3], weights=[1, 4, 3, 2])[0]
    edits = []
    for _ in range(k):
        o = rng.choice(order)
        name = index[o["item"]]["name"]
        choices = ["change_qty", "remove"]
        if index[o["item"]]["sizes"]:
            choices.append("resize")
        if index[o["item"]]["mods"]:
            choices.append("add_mod")
        kind = rng.choice(choices)
        if kind == "resize":
            edits.append(f'resize the {name} to {rng.choice(index[o["item"]]["sizes"])}')
        elif kind == "change_qty":
            edits.append(f'change the {name} quantity to {rng.randint(1, 3)}')
        elif kind == "remove":
            edits.append(f'remove the {name}')
        elif kind == "add_mod":
            edits.append(f'add "{rng.choice(index[o["item"]]["mods"])}" to the {name}')
    return edits


def sample_scenario(rng: random.Random) -> str:
    """~25% of dialogues get a personality/complaint flavor for coverage."""
    roll = rng.random()
    if roll < 0.10:
        return ("The customer OPENS with small talk (e.g. 'how's your day', 'you a robot?'); the "
                "assistant gives ONE quick friendly line, redirects, then takes the order normally.")
    if roll < 0.20:
        return ("Mid-conversation the customer makes a REAL complaint (a wrong order before, wants a "
                "manager, a billing issue, rude staff, or a safety/allergy concern). The assistant "
                "apologizes briefly and sets state 'escalated' to fetch a team member.")
    if roll < 0.25:
        return ("The customer has a MINOR grumble (a short wait, prices). The assistant apologizes "
                "warmly and KEEPS taking the order — does NOT escalate.")
    return "(none — a normal order)"


GEN_PROMPT = """You are generating training data for a drive-thru order assistant. Produce ONE realistic multi-turn conversation between a CUSTOMER and the ASSISTANT.

TARGET final order for this dialogue:
{order_desc}

Edits to weave in mid-conversation (the customer changes their mind):
{edits_desc}

SPECIAL SCENARIO for this dialogue (if any):
{scenario}

REQUIREMENTS:
- 3–8 turns. Natural, casual customer speech: slang ("lemme get", "gimme", "I'll do"), fillers ("uhh", "actually wait"), changes of mind, sometimes multi-item turns.
- EVERY assistant turn MUST be EXACTLY this format and nothing else:
  <say>natural spoken reply</say>
  <order>{{"ops":[...],"state":"in_progress|confirmed|cancelled|escalated"}}</order>
- The <order> is a DIFF (only what changed this turn), never the whole order restated. Use the "op" discriminator key. In a modify, null means "leave that field unchanged".
- ops: add{{item,size,qty,mods}} | modify{{line,size,qty,mods}} | remove{{line}} | clear | [] (for greetings / pure talk).
- "line" numbers refer to the order line created by an earlier add, counting 1,2,3… in the order items were added.
- Only use items/sizes/mods from the menu. Confirm the order verbally near the end and set state "confirmed".
- Do NOT add items the customer didn't ask for.
- PERSONALITY: the assistant may match the customer's vibe with ONE short, friendly/quirky line, then immediately steer back to ordering. Keep it brief; never chit-chat across multiple turns. Pure-talk turns use ops [].
- COMPLAINTS: if the customer makes a REAL complaint (wrong/bad order, rude treatment, wants a manager, billing error, safety/allergy), the assistant briefly apologizes, says it's getting a team member, and sets state "escalated". For a MINOR grumble (short wait, prices), just apologize and keep ordering — do NOT escalate.
- Output ONLY the conversation as alternating "CUSTOMER:" lines and assistant turns. No commentary, no markdown fences."""


# ---- parsing the generated conversation -------------------------------------
_TURN_RE = re.compile(
    r"CUSTOMER:\s*(?P<cust>.+?)(?=\n*(?:CUSTOMER:|<say>)|\Z)"
    r"|<say>(?P<say>.*?)</say>\s*<order>(?P<order>.*?)</order>",
    re.DOTALL,
)


def parse_conversation(text: str) -> list[dict] | None:
    """Return an ordered list of {'role','content'[, 'order']} turns, or None."""
    turns = []
    for m in _TURN_RE.finditer(text):
        if m.group("cust") is not None:
            content = m.group("cust").strip()
            if content:
                turns.append({"role": "user", "content": content})
        else:
            raw = m.group("order").strip()
            try:
                order_obj = json.loads(raw)
            except json.JSONDecodeError:
                return None
            if isinstance(order_obj, list):           # model emitted bare ops array
                order_obj = {"ops": order_obj, "state": "in_progress"}
            if not isinstance(order_obj, dict):
                return None
            turns.append({
                "role": "assistant",
                "say": m.group("say").strip(),
                "order": order_obj,
            })
    if not turns or turns[0]["role"] != "user":
        return None
    if not any(t["role"] == "assistant" for t in turns):
        return None
    return turns


def build_example(turns: list[dict], index: dict) -> dict | None:
    """Replay the dialogue through the real DB to (a) validate every <order>
    (reject the whole dialogue on any rejected op — the §4.4 gate) and (b) inject
    the CURRENT ORDER state before each customer turn (the v2 memory fix). Returns
    the training conversation, or None if any op was invalid."""
    conn = order_state.connect(":memory:")
    msgs = [{"role": "system", "content": SYSTEM}]
    for t in turns:
        if t["role"] == "user":
            snap = order_state.get_state(conn)
            content = render_current_order(snap) + "\n" + t["content"]
            msgs.append({"role": "user", "content": content})
        else:  # assistant
            report = order_state.apply_ops(conn, t["order"], index)
            if report["rejected"]:
                return None
            msgs.append({"role": "assistant",
                         "content": render_assistant_turn(t["say"], t["order"])})
    return {"messages": msgs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50, help="dialogues to attempt")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    menu = menu_validator.load_menu()
    index = menu_validator.build_index(menu)
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    rng = random.Random(args.seed)
    print(f"Generator model: {MODEL}  |  attempting {args.n} dialogues (seed {args.seed})")

    # APPEND mode — adds to the existing seed/dataset, never overwrites it.
    def _count(p):
        return sum(1 for _ in open(p)) if p.exists() else 0
    before_train = _count(OUT_DIR / "dataset.jsonl")
    before_hold = _count(OUT_DIR / "dataset_holdout.jsonl")
    print(f"appending to existing data: {before_train} train + {before_hold} holdout lines")
    train_f = open(OUT_DIR / "dataset.jsonl", "a", encoding="utf-8")
    hold_f = open(OUT_DIR / "dataset_holdout.jsonl", "a", encoding="utf-8")
    kept = held = discarded = 0

    for i in range(args.n):
        order = sample_order(index, rng)
        edits = sample_edits(order, index, rng)
        prompt = GEN_PROMPT.format(
            order_desc=describe_order(order, index),
            edits_desc=("\n".join(f"  - {e}" for e in edits) or "  - (none)"),
            scenario=sample_scenario(rng),
        )
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=2000,
                system=[{"type": "text", "text": SYSTEM,
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as e:
            print(f"[{i}] API error: {e}; skipping", file=sys.stderr)
            continue

        text = next((b.text for b in resp.content if b.type == "text"), "")
        turns = parse_conversation(text)
        example = build_example(turns, index) if turns else None
        if example is None:
            discarded += 1
        else:
            if i % 10 == 0:          # ~10% holdout, never trained on (§4.4)
                hold_f.write(json.dumps(example) + "\n"); hold_f.flush(); held += 1
            else:
                train_f.write(json.dumps(example) + "\n"); train_f.flush(); kept += 1

        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{args.n}  kept={kept} held={held} discarded={discarded}")

    train_f.close(); hold_f.close()
    print(f"\nDone this run. added: train={kept}  holdout={held}  discarded={discarded}")
    print(f"  totals now: {before_train + kept} train + {before_hold + held} holdout")
    print(f"  -> {OUT_DIR/'dataset.jsonl'}")
    print(f"  -> {OUT_DIR/'dataset_holdout.jsonl'}")
    if kept == 0:
        print("WARNING: 0 kept — check the printed errors / your API key.")


if __name__ == "__main__":
    main()
