"""review_live.py — turn your live test conversations into verified training data.

app/pipeline.py logs every live turn to data/live_log.jsonl. After a test session,
run this to review each turn and KEEP the ones the model got right, FIX the wrong
ones, or SKIP junk. Verified turns append to data/dataset.jsonl.

This is real-usage mining: the transcripts are EXACTLY what Whisper produces from
real speech (perfect distribution match) and YOU verify the labels — the highest-
quality training data there is. A few minutes of this beats a lot of synthetic data.

    python3 data/review_live.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in ("app", "db", "data"):
    sys.path.insert(0, str(ROOT / p))
import menu_validator      # noqa: E402
import order_state         # noqa: E402
from contract import SYSTEM, render_current_order, render_assistant_turn  # noqa: E402

LOG = ROOT / "data" / "live_log.jsonl"
OUT = ROOT / "data" / "dataset.jsonl"


def to_example(pre, transcript, say, order):
    return {"messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": render_current_order(pre) + "\n" + transcript.strip()},
        {"role": "assistant", "content": render_assistant_turn(say, order)},
    ]}


def main():
    if not LOG.exists():
        sys.exit("No data/live_log.jsonl yet — run app/pipeline.py and talk to it first.")
    records = [json.loads(l) for l in open(LOG) if l.strip()]
    if not records:
        sys.exit("live_log.jsonl is empty.")
    print(f"Reviewing {len(records)} live turns.")
    print("For each: [Enter]=keep (model was right)   e=edit   s=skip   q=quit\n")
    kept = 0
    with open(OUT, "a", encoding="utf-8") as out:
        for i, r in enumerate(records, 1):
            pre, txt, say, order = r["pre"], r["transcript"], r["say"], r["order"]
            print(f"--- turn {i}/{len(records)} ---")
            print("  CURRENT ORDER:", render_current_order(pre).replace("CURRENT ORDER: ", ""))
            print("  CUSTOMER:", txt.strip())
            print("  MODEL SAY:", say)
            print("  MODEL ORDER:", json.dumps(order))
            # Show what ACTUALLY got stored + anything the validator threw away, so a
            # model mistake (fixable) is distinguishable from a code/menu bug (not).
            if r.get("rejected"):
                print("  ⚠ REJECTED (emitted but NOT stored):", json.dumps(r["rejected"]))
            post = r.get("post")
            if post is not None:
                print("  STORED AFTER:", render_current_order(post).replace("CURRENT ORDER: ", ""))
                _ops = order.get("ops") if isinstance(order, dict) else order
                if _ops and post.get("lines") == pre.get("lines"):
                    print("  ⚠⚠ order did NOT change despite ops — likely a wrong id/line or a"
                          " CODE/menu bug, not a reply problem. Skip + flag, don't 'fix' the data.")
            ans = input("  keep[Enter] / edit[e] / skip[s] / quit[q]: ").strip().lower()
            if ans == "q":
                break
            if ans == "s":
                continue
            if ans == "e":
                raw = input('    corrected <order> JSON (blank = keep model\'s): ').strip()
                if raw:
                    try:
                        order = json.loads(raw)
                        assert isinstance(order, dict) and "ops" in order
                    except (json.JSONDecodeError, AssertionError):
                        print("    bad JSON — skipping this turn"); continue
                newsay = input("    corrected <say> text (blank = keep model's): ").strip()
                if newsay:
                    say = newsay
            out.write(json.dumps(to_example(pre, txt, say, order)) + "\n")
            out.flush()
            kept += 1
    print(f"\n✅ Kept {kept} verified examples → {OUT.name}")
    if kept and input("Clear live_log.jsonl so you don't re-review these? [y/N]: ").strip().lower() == "y":
        LOG.rename(LOG.with_suffix(".reviewed.jsonl"))
        print("   moved live_log.jsonl -> live_log.reviewed.jsonl")


if __name__ == "__main__":
    main()
