"""eval.py — B3: measure the model on the held-out set (§10).

Reports, as a markdown table:
  - order accuracy, SEPARATELY for simple-add turns vs EDIT turns (edits are hard)
  - tokens/sec on your hardware
  - (optional) naturalness of <say> via an LLM judge
  - (optional) a comparison row for an un-tuned base model

Accuracy = does the model's <order> diff match the gold diff (ops compared after
normalizing). We use teacher forcing: the held-out conversation already carries the
gold CURRENT ORDER each turn, so each turn is judged against the true trajectory.

    python3 train/eval.py
    python3 train/eval.py --base qwen2.5:1.5b        # add an untuned-base comparison row
    python3 train/eval.py --naturalness              # add LLM-judge naturalness (needs ANTHROPIC_API_KEY)

(Run after training; needs `ollama serve` up and the model pulled/created.)
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "db"))
from order_llm import parse_reply  # noqa: E402  (reuse the inference parser)
import order_state       # noqa: E402
import menu_validator    # noqa: E402

_INDEX = menu_validator.build_index(menu_validator.load_menu())

# Each holdout example embeds its OWN menu in the system prompt (menu-randomized
# training). To score a synthetic-menu turn correctly we must validate against THAT
# menu, not the real one — else its items get rejected and the score is meaningless.
_MENU_MARKER = "MENU (ids -> details):\n"
_idx_cache: dict[str, dict] = {}


def index_for_system(system_text: str) -> dict:
    if system_text not in _idx_cache:
        pos = system_text.rfind(_MENU_MARKER)
        try:
            menu = json.loads(system_text[pos + len(_MENU_MARKER):]) if pos != -1 else None
            _idx_cache[system_text] = menu_validator.build_index(menu) if menu else _INDEX
        except (json.JSONDecodeError, ValueError):
            _idx_cache[system_text] = _INDEX
    return _idx_cache[system_text]


HOLDOUT = ROOT / "data" / "dataset_holdout.jsonl"
OLLAMA_URL = "http://localhost:11434/api/chat"


def chat(model: str, messages: list[dict]) -> tuple[str, float]:
    """Return (reply_text, tokens_per_second) from Ollama."""
    body = json.dumps({"model": model, "messages": messages, "stream": False,
                       "options": {"temperature": 0.0}}).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read())
    text = data["message"]["content"]
    tps = 0.0
    if data.get("eval_count") and data.get("eval_duration"):
        tps = data["eval_count"] / (data["eval_duration"] / 1e9)
    return text, tps


def _conn_from_snapshot(snap):
    """Rebuild a DB at a given order state so we can apply a diff to it."""
    conn = order_state.connect(":memory:")
    maxline = 0
    for ln in snap["lines"]:
        conn.execute("INSERT INTO order_lines (line,item,size,qty,mods) VALUES (?,?,?,?,?)",
                     (ln["line"], ln["item"], ln["size"], ln["qty"], json.dumps(ln["mods"])))
        maxline = max(maxline, ln["line"])
    conn.execute("UPDATE order_meta SET next_line=?, state=? WHERE id=1",
                 (maxline + 1, snap["state"]))
    conn.commit()
    return conn


def _content(snap):
    """Order content as a comparable multiset (ignores line ids / formatting)."""
    return sorted((l["item"], l["size"], l["qty"], tuple(sorted(l["mods"])))
                  for l in snap["lines"])


def state_match(pre, gold_ops, pred_ops, index) -> bool:
    """Apply gold vs predicted diff to the SAME starting order; same result?
    Forgiving of JSON formatting, strict on meaning. `index` = the turn's menu."""
    g = order_state.apply_ops(_conn_from_snapshot(pre), {"ops": gold_ops}, index)["snapshot"]
    p = order_state.apply_ops(_conn_from_snapshot(pre), {"ops": pred_ops}, index)["snapshot"]
    return _content(g) == _content(p)


def is_edit(gold_ops) -> bool:
    return bool({op.get("op") for op in gold_ops} & {"modify", "remove", "clear"})


def load_all_turns() -> list:
    """List of (messages_prompt, gold_say, gold_ops, pre_snapshot) per assistant turn.
    Replays gold diffs within each conversation to get the order BEFORE each turn."""
    out = []
    for line in open(HOLDOUT):
        if not line.strip():
            continue
        msgs = json.loads(line)["messages"]
        idx = index_for_system(msgs[0]["content"]) if msgs and msgs[0]["role"] == "system" else _INDEX
        conn = order_state.connect(":memory:")
        for k in range(len(msgs)):
            if msgs[k]["role"] != "assistant":
                continue
            pre = order_state.get_state(conn)
            gold_say, gold_order = parse_reply(msgs[k]["content"])
            gold_ops = gold_order.get("ops", [])
            out.append((msgs[:k], gold_say, gold_ops, pre, idx))
            order_state.apply_ops(conn, {"ops": gold_ops}, idx)  # advance gold trajectory
    return out


def sample(turns: list, limit: int) -> list:
    """Evenly spaced subset across the whole holdout (representative, not just the start)."""
    if not limit or len(turns) <= limit:
        return turns
    stride = len(turns) / limit
    return [turns[int(i * stride)] for i in range(limit)]


def eval_model(model: str, turns: list) -> dict:
    simple_ok = simple_n = edit_ok = edit_n = 0
    tps_samples = []
    cases = []  # (gold_say, pred_say) for optional naturalness
    n = len(turns)
    for i, (prompt_msgs, gold_say, gold_ops, pre, index) in enumerate(turns, 1):
        if i % 20 == 0 or i == n:
            print(f"  {model}: {i}/{n}", flush=True)
        pred_text, tps = chat(model, prompt_msgs)
        pred_say, pred_order = parse_reply(pred_text)
        correct = state_match(pre, gold_ops, pred_order.get("ops", []), index)
        if is_edit(gold_ops):
            edit_n += 1; edit_ok += correct
        else:
            simple_n += 1; simple_ok += correct
        if tps:
            tps_samples.append(tps)
        cases.append((gold_say, pred_say))
    total_ok = simple_ok + edit_ok
    total_n = simple_n + edit_n
    return {
        "model": model,
        "simple": (simple_ok, simple_n),
        "edit": (edit_ok, edit_n),
        "overall": (total_ok, total_n),
        "tps": sum(tps_samples) / len(tps_samples) if tps_samples else 0.0,
        "cases": cases,
    }


def naturalness(cases) -> float:
    """LLM-judge the <say> replies 1-5 for natural drive-thru speech."""
    import anthropic
    client = anthropic.Anthropic()
    scores = []
    for _gold, pred in cases:
        if not pred.strip():
            scores.append(1); continue
        msg = client.messages.create(
            model="claude-haiku-4-5", max_tokens=8,
            system="Rate how natural this drive-thru worker reply sounds, 1 (robotic/broken) to 5 (natural). Reply with ONLY the digit.",
            messages=[{"role": "user", "content": pred}])
        txt = next((b.text for b in msg.content if b.type == "text"), "3").strip()
        scores.append(int(txt[0]) if txt[:1].isdigit() else 3)
    return sum(scores) / len(scores) if scores else 0.0


def pct(ok_n):
    ok, n = ok_n
    return f"{100*ok/n:.0f}% ({ok}/{n})" if n else "—"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="drivethru")
    ap.add_argument("--base", default=None, help="also eval an untuned base, e.g. qwen2.5:1.5b")
    ap.add_argument("--naturalness", action="store_true")
    ap.add_argument("--limit", type=int, default=80,
                    help="eval an evenly-spaced sample of N turns (0 = all; slow on big holdouts)")
    args = ap.parse_args()

    if not HOLDOUT.exists():
        sys.exit(f"❌ {HOLDOUT} not found — generate data first.")

    turns = sample(load_all_turns(), args.limit)
    print(f"evaluating on {len(turns)} held-out turns "
          f"({'sampled' if args.limit else 'all'})\n", flush=True)

    models = [args.model] + ([args.base] if args.base else [])
    rows = []
    for m in models:
        r = eval_model(m, turns)
        nat = f"{naturalness(r['cases']):.1f}/5" if args.naturalness else "—"
        rows.append((m, pct(r["simple"]), pct(r["edit"]), pct(r["overall"]),
                     f"{r['tps']:.0f}", nat))

    print("\n## Eval results (held-out set)\n")
    print("| Model | Simple-add acc | EDIT acc | Overall | tok/s | Naturalness |")
    print("|---|---|---|---|---|---|")
    for row in rows:
        print("| " + " | ".join(row) + " |")
    print("\n_EDIT turns = order contained modify/remove/clear; the hard case._")


if __name__ == "__main__":
    main()
