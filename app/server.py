"""server.py — the demo web app: talk to the model, watch the order build live.

A small FastAPI backend around the SAME order brain the voice loop uses
(order_llm + order_state + contract). The browser handles speech-to-text (Web
Speech API) and text-to-speech (speechSynthesis) for a zero-setup demo; the
downloadable product uses the fully-local Pipecat stack (Whisper + Kokoro).

    pip install fastapi uvicorn
    ollama serve            # in another terminal, with the `drivethru` model created
    python3 app/server.py
    # open http://localhost:8000

Each browser tab is its own ordering session (its own in-memory order).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in ("app", "db", "data"):
    sys.path.insert(0, str(ROOT / p))

from fastapi import FastAPI                                   # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse      # noqa: E402
from pydantic import BaseModel                                # noqa: E402

import menu_validator                                         # noqa: E402
from order_voice import VoiceOrderBrain                       # noqa: E402

app = FastAPI(title="Drive-Thru Voice AI — demo")
WEB = ROOT / "web"
MENU = menu_validator.load_menu()
SESSIONS: dict[str, VoiceOrderBrain] = {}


def brain_for(session: str) -> VoiceOrderBrain:
    if session not in SESSIONS:
        SESSIONS[session] = VoiceOrderBrain(log=False)  # demo: don't touch live_log
    return SESSIONS[session]


class Turn(BaseModel):
    session: str
    text: str = ""


@app.get("/")
def index():
    return HTMLResponse((WEB / "index.html").read_text(encoding="utf-8"))


@app.get("/menu")
def menu():
    return JSONResponse(MENU)


@app.post("/say")
def say(turn: Turn):
    """One ordering turn: customer text in -> spoken reply + live order + AI I/O."""
    brain = brain_for(turn.session)
    spoken, snapshot, escalated = brain.handle(turn.text)
    return {
        "say": spoken,
        "order": snapshot,                       # the true order (DB) for the ticket
        "escalated": escalated,
        "ai": getattr(brain, "last_io", None),   # what the model heard + emitted
    }


@app.post("/reset")
def reset(turn: Turn):
    SESSIONS.pop(turn.session, None)
    return {"ok": True}


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"Demo on port {port}   (needs `ollama serve` + the `drivethru` model)")
    uvicorn.run(app, host="0.0.0.0", port=port)
