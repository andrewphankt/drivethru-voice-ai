"""reembed_system.py — refresh the SYSTEM prompt in existing training data.

After a contract change (e.g. v2 -> v3 added the `escalated` state + personality
rules), the dialogues you already generated are still valid — only the system
prompt text changed. This rewrites messages[0] in every example to the current
contract.SYSTEM, so you keep your bulk data without regenerating it.

    python3 data/reembed_system.py

Then add a little escalation/personality coverage (a Haiku batch — the generator
now injects those scenarios) and retrain.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data"))
from contract import SYSTEM  # noqa: E402


def fix(path: Path):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    changed = 0
    for ex in rows:
        msgs = ex.get("messages", [])
        if msgs and msgs[0].get("role") == "system" and msgs[0]["content"] != SYSTEM:
            msgs[0]["content"] = SYSTEM
            changed += 1
    with open(path, "w", encoding="utf-8") as f:
        for ex in rows:
            f.write(json.dumps(ex) + "\n")
    return changed, len(rows)


def main():
    # SAFETY: this overwrites EVERY example's system with the real-menu SYSTEM. Once
    # menu-randomized (synthetic-menu) data exists, doing that would corrupt those
    # examples (each carries its OWN menu's system). gen_planned drops this marker the
    # first time it writes a synthetic-menu dialogue. Refuse to run if it's present.
    marker = ROOT / "data" / ".synthetic_menus_present"
    if marker.exists():
        sys.exit("ABORT: synthetic-menu data is present (.synthetic_menus_present). "
                 "reembed would overwrite per-menu system prompts. Run it only BEFORE "
                 "generating menu-randomized data, or regenerate from scratch.")
    for name in ("dataset.jsonl", "dataset_holdout.jsonl"):
        p = ROOT / "data" / name
        if p.exists():
            changed, total = fix(p)
            print(f"{name}: refreshed system prompt in {changed}/{total} examples")
        else:
            print(f"{name}: not found (skip)")


if __name__ == "__main__":
    main()
