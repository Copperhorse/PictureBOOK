# Critic and planner experiments (2026-10-09)

Results are written up in [`docs/research/critic-evaluation.md`](../../docs/research/critic-evaluation.md) and [`docs/research/thinking-and-planner-tests.md`](../../docs/research/thinking-and-planner-tests.md). Everything here was run against `llama serve` 0.4.1-dev with the flags in `serve.sh` (copied from `~/run_goose.sh`).

## Test data

| Path | Contents |
|---|---|
| `gen_images.py`, `images/`, `manifest.json`, `contact_sheet.png` | **Set v1** (40 synthetic cartoon characters). Flawed: hair hidden under hoods or looking like a hood, tiny glasses. Kept only because `v1_*` results are cited. |
| `gen_images_v2.py`, `images_v2/`, `manifest_v2.json`, `contact_sheet_v2.png` | **Set v2** (40 images, corrected) used for all conclusions. Deterministic: regenerating gives byte-identical files. |
| `gen_pairs.py`, `images_pairs/`, `manifest_pairs.json`, `pairs_sheet.png` | 20 reference characters × 6 candidates (one control, five with exactly one changed attribute) for the reference-vs-candidate test |
| `results/*.jsonl` | Raw per-request responses of every run cited in the reports |

## Scripts

| Script | Purpose |
|---|---|
| `serve.sh <e2b\|e4b> <port> <reasoning_budget> <repeat_penalty> [log_verbosity]` | Starts `llama serve` with Gemma 4 + projector (set `EXTRA_ARGS="--image-min-tokens 1120 --image-max-tokens 1120"` for the vision budget); logs and pid go to `.run/` |
| `run_critic.py --port P --tag T --think off\|default` | Runs the 120 critic requests (40 images × 3 checklists); `DATASET=_v2` selects set v2 |
| `analyze.py <tag>…`, `table.py <tag>…` | Accuracy, mismatch recall, false alarms with Wilson intervals; comparison table |
| `run_pairs.py`, `analyze_pairs.py` | Reference-vs-candidate comparison |
| `planner_test.py`, `planner_analyze.py` | One-call vs several-call planning, thinking on/off, rule checks |
| `budget_cutoff.py` | What happens when `--reasoning-budget` is exhausted |
| `go_*.sh` | The exact run sequences used (they chain servers and runs) |

## Rerun example

```bash
cd experiments/critic_eval
EXTRA_ARGS="--image-min-tokens 1120 --image-max-tokens 1120" ./serve.sh e4b 18080 2048 1.1
DATASET=_v2 python3 run_critic.py --port 18080 --tag v2_e4b_img1120_off_rerun --think off
DATASET=_v2 python3 analyze.py v2_e4b_img1120_off_rerun
kill $(cat .run/server_18080.pid)
```

Expected for the reference run: accuracy 94.7%, mismatch recall 99.0%, false alarms 7.5%.

## Not kept

Server logs, pid files, the discarded partial thinking-on run on set v1, and the two-image smoke tests.
