#!/usr/bin/env python3
"""finetune_mlx.py — fine-tune LOCALLY on an Apple Silicon Mac (§5, MLX path).

Local replacement for the Colab/Unsloth notebook (Unsloth is CUDA-only and will
not run on Apple Silicon). Trains a LoRA on data/dataset.jsonl with Apple's MLX,
fuses it into a standalone model, and writes an Ollama Modelfile so you can serve
it as `drivethru` — the name B2's harness calls.

Run from the repo root:
    python3 -m pip install -r train/requirements_mlx.txt
    python3 train/finetune_mlx.py

Produces:
    train/adapters/          LoRA adapter weights
    train/drivethru-fused/   fused model + Modelfile (import into Ollama)

Then:  python3 train/test_mlx.py     # quick sanity check
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data"))
from contract import SYSTEM  # noqa: E402  (frozen §7 system prompt)

MODEL = "Qwen/Qwen2.5-1.5B-Instruct"   # base model (D2)
DATA_DIR = ROOT / "train" / "mlx_data"
ADAPTER = ROOT / "train" / "adapters"
FUSED = ROOT / "train" / "drivethru-fused"


def sh(cmd: list[str]):
    print("\n$ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def prep_data():
    """MLX-LM reads a folder with train.jsonl + valid.jsonl. Our dataset.jsonl is
    already in the {"messages":[...]} chat format MLX auto-detects — just place it."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    train = ROOT / "data" / "dataset.jsonl"
    valid = ROOT / "data" / "dataset_holdout.jsonl"
    if not train.exists():
        sys.exit(f"❌ {train} not found — generate the data first (data/RUNBOOK.md).")
    shutil.copy(train, DATA_DIR / "train.jsonl")
    shutil.copy(valid if valid.exists() else train, DATA_DIR / "valid.jsonl")
    n = sum(1 for _ in open(DATA_DIR / "train.jsonl"))
    print(f"✅ prepared MLX data: {n} train examples → {DATA_DIR}")


def main():
    prep_data()
    py = sys.executable

    # 1) Train the LoRA. Memory-safe for a 16GB Mac: batch 1 + gradient
    #    checkpointing keeps peak GPU memory well under 16GB (batch 2 OOM'd).
    #    Iters cover ~1 epoch, capped — loss plateaus fast on this structured
    #    task (it was already ~0.13 by iter 150), so this is plenty and finishes
    #    in a reasonable time. Scales up from the tiny-seed mistake of 120 iters.
    n = sum(1 for _ in open(DATA_DIR / "train.jsonl"))
    iters = max(300, min(n, 1000))
    print(f"training on {n} examples → batch 1 + grad-checkpoint, {iters} iters")
    sh([py, "-m", "mlx_lm.lora",
        "--model", MODEL,
        "--train",
        "--data", str(DATA_DIR),
        "--adapter-path", str(ADAPTER),
        "--batch-size", "1",
        "--num-layers", "8",
        "--iters", str(iters),
        "--learning-rate", "2e-4",
        "--max-seq-length", "2048",
        "--grad-checkpoint"])

    # 2) Fuse the adapter into a standalone HF-format model (safetensors).
    sh([py, "-m", "mlx_lm.fuse",
        "--model", MODEL,
        "--adapter-path", str(ADAPTER),
        "--save-path", str(FUSED)])

    # 3) Write an Ollama Modelfile (FROM . → imports the safetensors in this dir).
    modelfile = (
        "FROM .\n"
        "PARAMETER temperature 0.3\n"
        'PARAMETER stop "<|im_end|>"\n'
        'TEMPLATE """{{ if .System }}<|im_start|>system\n{{ .System }}<|im_end|>\n{{ end }}'
        '{{ if .Prompt }}<|im_start|>user\n{{ .Prompt }}<|im_end|>\n{{ end }}'
        '<|im_start|>assistant\n{{ .Response }}<|im_end|>\n"""\n'
        'SYSTEM """' + SYSTEM + '"""\n'
    )
    (FUSED / "Modelfile").write_text(modelfile, encoding="utf-8")

    print("\n✅ DONE.")
    print(f"   adapters:            {ADAPTER}")
    print(f"   fused model+Modelfile: {FUSED}")
    print("\nNext:")
    print("   1) quick test:   python3 train/test_mlx.py")
    print(f"   2) serve it:     cd {FUSED} && ollama create drivethru -f Modelfile --quantize q4_K_M")
    print("      then:         ollama run drivethru 'lemme get a classic burger combo large'")


if __name__ == "__main__":
    main()
