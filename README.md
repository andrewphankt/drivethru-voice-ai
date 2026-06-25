# Drive-Thru Voice AI

A small, fine-tuned language model that takes drive-thru orders by voice, and runs fully on-device.

You speak, it understands the order, reads it back, and updates an authoritative order
database in real time. It's built to be the cheapest way to automate a pickup window —
~$0 per order, runs on a used Mac mini, and your customers' audio never leaves the building.

<!-- [DEMO SCREENSHOT PLACEHOLDER — web/index.html dashboard] -->
<!-- [LIVE DEMO LINK PLACEHOLDER] -->

## How it works

The model doesn't remember the order. Each turn it proposes a diff (`add a large fries`,
`make it a combo`), the code validates it against the menu and applies it to SQLite, and
the screen always shows the true order.

- **Model** — Qwen2.5-1.5B, LoRA fine-tuned (Apple MLX), served INT4 via Ollama
- **Voice** — Pipecat (Silero VAD + Whisper STT + Kokoro TTS), all local
- **Order logic** — menu validator + SQLite as source of truth

## Try It

**browser test:**
```bash
pip install fastapi uvicorn
ollama serve            # with the `drivethru` model loaded (see "Get the model")
python3 app/server.py
```

## Get the model

The fine-tuned model is one command:
```bash
ollama run andrewphankt/drivethru
```

## Use it for your own restaurant

Put your menu in `menu/menu.json` — or generate it from a plain item list with
`app/menu_ingest.py` (it derives ids from names, which is what the model expects). The
model reads the menu from its prompt each turn, so **one model works across menus** with
no retraining; for best results on an unusual menu, capture a few real orders and retrain
locally.

## Eval

- Order accuracy (held-out): 93%
- Multi-step edits: 84%
- Generalization to an unseen menu: 60%
- Speed: ~100 tok/s, ~1–2 s end-to-end

## Limitations

- ~1–2 s reply latency
- English only; one window per machine
- Practice project
