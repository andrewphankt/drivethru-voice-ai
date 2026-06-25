# Phase B Runbook — Fine-tune on Google Colab (§5)

Turns `data/dataset.jsonl` into the `drivethru` Ollama model. Free GPU, no setup
on your Mac except Ollama at the end.

## Steps
1. Go to **https://colab.research.google.com** → **File → Upload notebook** →
   pick `train/finetune_colab.ipynb` from this repo.
2. **Runtime → Change runtime type → T4 GPU** → Save.
3. Run cells top to bottom. When prompted, upload `data/dataset.jsonl`.
4. Training takes a few minutes. The last cell downloads `drivethru_model.zip`.
5. On your Mac (install Ollama first from https://ollama.com/download):
   ```bash
   mkdir -p ~/drivethru_model && cd ~/drivethru_model
   unzip ~/Downloads/drivethru_model.zip
   ollama create drivethru -f Modelfile
   ollama run drivethru 'lemme get a classic burger combo large'
   ```
6. If it emits a `<say>` + `<order>`, the loop works. Tell Claude Code
   **"model's ready"** to start B2 (the text harness).

## Notes
- With only the ~28-dialogue seed this is a **pipeline trial** — it proves
  train → export → serve works. Real accuracy comes after the Haiku bulk data
  (then re-run this notebook, maybe bump `num_train_epochs`).
- Base model: Qwen2.5-1.5B-Instruct, QLoRA via Unsloth, exported GGUF INT4 (D2/D3).
- The frozen §7 system prompt is baked into the Modelfile, so Ollama serves it
  automatically — `ollama run drivethru '<customer text>'` is all B2 needs.
