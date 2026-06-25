"""build_seed.py — validate the hand-authored seed dialogues and write the dataset.

Reuses the SAME pipeline as the API path (parse -> replay through the real DB ->
serialize), so the seed is held to the exact same §4.4 quality bar. Any dialogue
whose ops get rejected is reported and NOT written.

    python3 data/build_seed.py

Writes data/dataset.jsonl (train) + data/dataset_holdout.jsonl (~10%, never trained).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in ("app", "db", "data"):
    sys.path.insert(0, str(ROOT / p))

import menu_validator          # noqa: E402
import gen_synthetic_orders as g  # noqa: E402  (reuse parse/validate/serialize)
from seed_dialogues import DIALOGUES  # noqa: E402

OUT_DIR = ROOT / "data"


def main():
    index = menu_validator.build_index(menu_validator.load_menu())
    kept, held, bad = [], [], []

    for i, raw in enumerate(DIALOGUES):
        turns = g.parse_conversation(raw)
        if turns is None:
            bad.append((i, "did not parse")); continue
        example = g.build_example(turns, index)
        if example is None:
            bad.append((i, "rejected by DB replay")); continue
        (held if i % 10 == 0 else kept).append(example)

    with open(OUT_DIR / "dataset.jsonl", "w", encoding="utf-8") as f:
        for ex in kept:
            f.write(json.dumps(ex) + "\n")
    with open(OUT_DIR / "dataset_holdout.jsonl", "w", encoding="utf-8") as f:
        for ex in held:
            f.write(json.dumps(ex) + "\n")

    print(f"dialogues authored : {len(DIALOGUES)}")
    print(f"  -> train          : {len(kept)}  ({OUT_DIR/'dataset.jsonl'})")
    print(f"  -> holdout (~10%)  : {len(held)}  ({OUT_DIR/'dataset_holdout.jsonl'})")
    print(f"  -> REJECTED        : {len(bad)}")
    for i, why in bad:
        print(f"       dialogue #{i+1}: {why}")
    if bad:
        sys.exit(1)
    print("\nAll seed dialogues passed the DB-replay quality gate. ✅")


if __name__ == "__main__":
    main()
