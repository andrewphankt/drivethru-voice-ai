"""order_voice.py — the order "brain" for the voice pipeline (B4).

Reuses the EXACT B2 pieces (order_llm + order_state + the v2 CURRENT ORDER
contract). The Pipecat audio layer (app/pipeline.py) just calls handle() with the
customer's transcribed words and speaks back the returned <say> text — all the
ordering logic lives here, where it's testable without any audio hardware.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "db"))
sys.path.insert(0, str(ROOT / "data"))

import json  # noqa: E402
import re    # noqa: E402

import menu_validator      # noqa: E402
import order_state         # noqa: E402
from order_llm import OrderLLM          # noqa: E402
from contract import render_current_order, render_assistant_turn  # noqa: E402

LIVE_LOG = ROOT / "data" / "live_log.jsonl"   # every live turn, for review_live.py

_SIZE_WORDS = {"small": "S", "sm": "S", "medium": "M", "med": "M", "regular": "M",
               "reg": "M", "large": "L", "lg": "L", "big": "L"}
_SIZE_LABEL = {"S": "Small", "M": "Medium", "L": "Large"}


def _parse_size(text: str, allowed) -> str | None:
    """Map a spoken size answer ('a large') to a size code valid for the item."""
    t = text.lower()
    for word, code in _SIZE_WORDS.items():
        if code in allowed and re.search(rf"\b{re.escape(word)}\b", t):
            return code
    return None


class VoiceOrderBrain:
    """One drive-thru session: transcribed text in → spoken reply + live DB."""

    def __init__(self, db_path: str = ":memory:", log: bool = True):
        self.index = menu_validator.build_index(menu_validator.load_menu())
        self.conn = order_state.connect(db_path)
        self.llm = OrderLLM()
        self.log = log
        self.pending = None   # item id awaiting a size (so sized items are never dropped)

    def handle(self, customer_text: str) -> tuple[str, dict, bool]:
        """Run one turn. Returns (say_to_speak, order_snapshot, escalated_flag)."""
        # If we asked for a size last turn, resolve it deterministically — the model
        # isn't always reliable at the ask->apply flow (especially for combos).
        if self.pending and self.pending in self.index:
            item = self.pending
            size = _parse_size(customer_text, self.index[item]["sizes"])
            if size:
                pre = order_state.get_state(self.conn)
                order = {"ops": [{"op": "add", "item": item, "size": size, "qty": 1, "mods": []}],
                         "state": "in_progress"}
                report = order_state.apply_ops(self.conn, order, self.index)
                name = self.index[item]["name"]
                say = f"Great — a {_SIZE_LABEL.get(size, size)} {name}. Anything else?"
                self.pending = None
                # keep the model's history consistent with what actually happened
                self.llm.history.append({"role": "user",
                    "content": render_current_order(pre) + "\n" + customer_text})
                self.llm.history.append({"role": "assistant",
                    "content": render_assistant_turn(say, order)})
                self.last_io = {"transcript": customer_text, "say": say, "order": order, "rejected": []}
                self._log(pre, customer_text, say, order, report)
                return say, report["snapshot"], report["escalated"]
            self.pending = None   # not a size answer -> fall through to normal handling

        snap = order_state.get_state(self.conn)
        prefixed = render_current_order(snap) + "\n" + customer_text
        say, order, _raw = self.llm.respond(prefixed)
        report = order_state.apply_ops(self.conn, order, self.index)

        # Never silently drop a SIZED item: if the model tried to add one without a
        # valid size, ask for it instead (this is why combos / sized drinks vanished).
        for rej in report["rejected"]:
            op = rej.get("op", {})
            item = op.get("item")
            if (op.get("op") == "add" and item in self.index
                    and self.index[item]["sizes"] and "size" in rej.get("reason", "")):
                self.pending = item
                opts = ", ".join(_SIZE_LABEL.get(s, s) for s in self.index[item]["sizes"])
                say = f"Sure — what size {self.index[item]['name']}? ({opts})"
                order = {"ops": [], "state": "in_progress"}
                # rewrite the model's last turn so its history shows the ASK, not a bad add
                if self.llm.history:
                    self.llm.history[-1] = {"role": "assistant",
                        "content": render_assistant_turn(say, order)}
                break

        self.last_io = {"transcript": customer_text, "say": say,
                        "order": order, "rejected": report["rejected"]}
        self._log(snap, customer_text, say, order, report)
        return say, report["snapshot"], report["escalated"]

    def _log(self, pre, transcript, say, order, report):
        # Real-usage capture for review_live.py (pre/post + rejected lets it tell a
        # MODEL mistake from a CODE/menu bug).
        if self.log and transcript.strip().lower() != "warmup":
            rec = {"pre": pre, "transcript": transcript, "say": say, "order": order,
                   "post": report["snapshot"], "rejected": report["rejected"]}
            with open(LIVE_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")

    def state(self) -> dict:
        return order_state.get_state(self.conn)

    def reset(self):
        self.conn = order_state.connect(":memory:")
        self.llm.reset()
        self.pending = None
