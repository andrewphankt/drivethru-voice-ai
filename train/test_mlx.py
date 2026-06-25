#!/usr/bin/env python3
"""test_mlx.py — quick local sanity check of the fine-tuned MLX model.

Loads train/drivethru-fused and asks it an order. You're checking the SHAPE:
does it emit a <say>...</say> and an <order>{...}</order>? With only the seed
it will be rough — that's expected; accuracy comes with the bulk data.

    python3 train/test_mlx.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data"))
from contract import SYSTEM  # noqa: E402

from mlx_lm import load, generate  # noqa: E402

FUSED = ROOT / "train" / "drivethru-fused"
if not FUSED.exists():
    sys.exit("❌ train/drivethru-fused not found — run train/finetune_mlx.py first.")

model, tokenizer = load(str(FUSED))

for customer in [
    "lemme get a classic burger combo large",
    "uhh a double stack burger no onion and a medium fries",
]:
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": customer}]
    prompt = tokenizer.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
    print(f"\n=== CUSTOMER: {customer} ===")
    generate(model, tokenizer, prompt=prompt, max_tokens=160, verbose=True)
