# B4 Runbook — Voice mode (Pipecat). Honest version: this part is iterative.

The order brain is proven. The audio wiring runs entirely on your Mac but can't
be tested without a mic, and Pipecat's API shifts between versions — so expect
1–2 rounds of "run it, paste the error, fix it." That's normal for this step.

Run everything from the repo root: `cd /Users/andrewphan/drivethru-voice-ai`

## 1. Install the voice dependencies (a few minutes; downloads some models)
```bash
python3 -m pip install -r app/requirements_voice.txt
```

## 2. Make sure the brain is being served
In one terminal, confirm Ollama + your model are up:
```bash
ollama run drivethru 'hi'      # should print a <say>/<order> reply, then exit
```
(Leave Ollama running — `ollama serve` runs in the background after install.)

## 3. Try the voice bot
```bash
python3 app/pipeline.py
```
- If it prints a local URL (e.g. http://localhost:7860), **open it in your browser, allow the microphone, and talk** — order something out loud. You'll see `CUSTOMER / SPEAK / ORDER` lines print in the terminal as you go.
- **First run is slow** — Whisper (speech-to-text) and Kokoro (the voice) download their models the first time.

## 4. If it errors (likely at least once)
Pipecat's class/import names move between versions. **Copy the full error and paste it to Claude Code** — most fixes are a one-line import or argument change. Common spots:
- An import like `from pipecat.services.whisper.stt import WhisperSTTService` may have moved.
- The `SmallWebRTCTransport` may need a small bit of signaling/UI setup to actually connect a browser.

### Reliable fallback if the transport fights us
Pipecat ships a generator that produces a known-good audio skeleton for *your*
installed version:
```bash
pipecat init quickstart      # creates a working mic->STT->LLM->TTS bot
```
Get that running first (it proves your mic/audio works), then Claude Code will
splice in the two custom pieces — `OrderProcessor` (from `app/pipeline.py`) and
pointing the LLM at your `drivethru` model. This guarantees the fragile boilerplate
matches your version while keeping your tested order logic.

## What B4 gets you (and what's still B5)
- **B4 (this):** talk to it, it talks back, the order updates. End-of-speech is
  detected by Silero VAD.
- **B5 (next):** the "respond before you finish" feel — semantic turn detection
  (SmartTurn) + preemptive generation + an on-screen latency meter. We tune that
  once B4 is flowing.
