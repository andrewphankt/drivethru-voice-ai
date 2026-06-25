# Phase A Runbook — Generate the training data (you run this on your Mac)

This is the offline §4/§17 work. No Claude Code needed. Follow top to bottom.

## 1. Get an Anthropic API key (one time)
1. Go to **https://console.anthropic.com** → sign in.
2. **Settings → Billing** → add a payment method and ~$10 of credit (a first
   test run costs cents; a full 12k-dialogue run on Haiku is only a few dollars).
3. **API keys → Create key** → copy it (starts with `sk-ant-...`).

## 2. Put the key in your terminal
In the SAME terminal you'll run the script from:
```bash
export ANTHROPIC_API_KEY=sk-ant-YOUR-KEY-HERE
```
(Re-run this each new terminal, or add it to your `~/.zshrc` to make it stick.)

## 3. Install the one dependency
```bash
cd /Users/andrewphan/drivethru-voice-ai
python3 -m pip install -r data/requirements.txt
```

## 4. Tiny test run first (~20 dialogues, costs pennies)
```bash
python3 data/gen_synthetic_orders.py --n 20
```
Watch the progress line: `kept=… held=… discarded=…`. Some discards are normal
(those are dialogues the generator got slightly wrong — the validator caught
them). If `kept=0`, stop and check the error messages (usually a bad/missing key).

## 5. Eyeball the data (sanity check before scaling)
```bash
head -n 1 data/dataset.jsonl | python3 -m json.tool
```
You should see a `messages` list: a system turn, then alternating user/assistant
turns where each assistant `content` is a `<say>…</say>` + `<order>…</order>`.

## 6. The real run (edit-heavy, 10k–30k — start at ~12k)
```bash
python3 data/gen_synthetic_orders.py --n 12000
```
This takes a while (it's thousands of API calls) and runs unattended. When it
finishes you'll have:
- `data/dataset.jsonl`         ← training set
- `data/dataset_holdout.jsonl` ← ~10% test set, NEVER trained on (for B3 eval)

## 7. Come back to Claude Code
Tell Claude Code the data is ready and you're moving to **Phase B (fine-tune on
Colab)**. It will hand you the Colab notebook for §5.

---
### Knobs you can change
- `--n` = how many dialogues to attempt.
- `--seed` = change it to generate a *different* batch (run twice with different
  seeds to grow the dataset; the script overwrites, so rename files between runs
  or change the seed and append manually).
- Generator model: `MODEL` near the top of `gen_synthetic_orders.py`
  (`claude-haiku-4-5`). Bump to `claude-opus-4-8` for a small high-quality
  edit-heavy batch if eval later shows edits are weak (§18).
