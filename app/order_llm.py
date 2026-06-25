"""order_llm.py — wrap the fine-tuned model as the order brain (B2).

Calls the local Ollama model `drivethru` (the §7 system prompt is baked into its
Modelfile), then parses out the `<say>` reply and the `<order>` JSON diff.

On GBNF (§7): true grammar-constrained decoding is a llama.cpp-layer feature and
is deferred to B4 (where we control that layer). For B2 the guarantee of
correctness does NOT depend on the model emitting perfect JSON — `menu_validator`
+ `order_state` reject anything invalid before it touches the DB. This parser is
defensive so a malformed reply degrades to "no order change" instead of crashing.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data"))
from contract import SYSTEM as DEFAULT_SYSTEM  # noqa: E402  (real-menu system prompt)

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "drivethru"

_SAY = re.compile(r"<say>(.*?)</say>", re.DOTALL)
_ORDER = re.compile(r"<order>(.*?)</order>", re.DOTALL)
_BRACE = re.compile(r"\{.*\}", re.DOTALL)


def _safe_json(txt: str):
    try:
        return json.loads(txt)
    except (json.JSONDecodeError, TypeError):
        return None


def parse_reply(raw: str) -> tuple[str, dict]:
    """Extract (say, order_obj) from a raw model reply, defensively."""
    say_m = _SAY.search(raw)
    say = say_m.group(1).strip() if say_m else raw.strip()

    order = None
    order_m = _ORDER.search(raw)
    if order_m:
        order = _safe_json(order_m.group(1).strip())
    if order is None:                      # fallback: any bare {...}
        brace = _BRACE.search(raw)
        if brace:
            order = _safe_json(brace.group(0))
    if isinstance(order, list):            # model emitted a bare ops array
        order = {"ops": order}
    if not isinstance(order, dict):
        order = {}
    order.setdefault("ops", [])
    order.setdefault("state", "in_progress")
    return say, order


class OrderLLM:
    """Holds conversation history and turns customer text into (say, order)."""

    def __init__(self, model: str = MODEL, url: str = OLLAMA_URL, system: str | None = None):
        self.model = model
        self.url = url
        # Sent as the system message each turn. Defaults to the real-menu prompt;
        # pass build_system(<their menu>) to run a DIFFERENT restaurant's menu with
        # the SAME model — no Modelfile rebuild, no retraining (menu-agnostic, Path A).
        self.system = system or DEFAULT_SYSTEM
        self.history: list[dict] = []

    def _call(self, messages: list[dict]) -> str:
        body = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.3},
        }).encode()
        req = urllib.request.Request(
            self.url, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())["message"]["content"]

    def respond(self, user_text: str) -> tuple[str, dict, str]:
        self.history.append({"role": "user", "content": user_text})
        # Prepend the system (the deployed menu) so the model orders from THIS menu.
        raw = self._call([{"role": "system", "content": self.system}] + self.history)
        self.history.append({"role": "assistant", "content": raw})
        say, order = parse_reply(raw)
        return say, order, raw

    def reset(self):
        self.history = []
