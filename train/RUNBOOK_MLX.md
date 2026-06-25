# Phase B Runbook — Fine-tune LOCALLY on your Mac with MLX (§5)

No browser, no uploads, no disconnects. Everything runs in your Terminal on the
M5. (Replaces the Colab path; Unsloth is CUDA-only and can't run on Apple Silicon.)

Run all commands from the repo root: `cd /Users/andrewphan/drivethru-voice-ai`

## 1. Install MLX (one time)
```bash
python3 -m pip install -r train/requirements_mlx.txt
```

## 2. Train + fuse (one command, a few minutes)
```bash
python3 train/finetune_mlx.py
```
It prepares the data, trains the LoRA on your M5's GPU, fuses it, and writes
`train/drivethru-fused/` with a ready Ollama `Modelfile`. Watch the loss tick down.

## 3. Quick sanity test (no Ollama needed)
```bash
python3 train/test_mlx.py
```
Look for a `<say>…</say>` and `<order>{…}</order>` in the output. Rough is fine —
you're checking the **shape**, not accuracy (only 28 seed examples).

## 4. Serve it as `drivethru` (the name B2 calls)
Install Ollama once from https://ollama.com/download (or `brew install ollama`), then:
```bash
cd train/drivethru-fused
ollama create drivethru -f Modelfile --quantize q4_K_M
ollama run drivethru 'lemme get a classic burger combo large'
```
Ollama imports the model and quantizes it to INT4 for you — no manual GGUF step.

## 5. If Ollama won't import the model (fallback)
Serve the fused model directly with MLX instead:
```bash
python3 -m mlx_lm.server --model train/drivethru-fused --port 8080
```
This exposes an OpenAI-compatible endpoint at `http://localhost:8080`. Tell Claude
Code and it will point B2's `app/order_llm.py` at this instead of Ollama. (We only
truly need GGUF/Ollama later at B4 for GBNF-constrained decoding.)

## 6. Done
When the model answers with `<say>`+`<order>`, tell Claude Code **"model's ready"**
to start **B2** (the text harness).

---
### Notes
- 16GB M5 is plenty for a 1.5B LoRA. If you ever hit a memory error, lower
  `--num-layers` to 4 or `--max-seq-length` to 1536 in `train/finetune_mlx.py`.
- This trains on the 28-dialogue **seed** — a pipeline trial. After the Haiku bulk
  data, just re-run step 2 (bump `--iters` in the script) for the real model.
- MLX-LM's CLI flags can change between versions. If `finetune_mlx.py` errors on a
  flag, run `python3 -m mlx_lm.lora --help` and paste it to Claude Code.
