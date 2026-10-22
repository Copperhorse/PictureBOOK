# Image bake-off (stages 0 and 1, FLUX.2 klein 4B)

Report: [`docs/research/image-bakeoff.md`](../../docs/research/image-bakeoff.md). Run 2026-10-10 on the RTX A2000 8 GB.

| File | Purpose |
|---|---|
| `bakeoff_common.py` | Specs loaded from `docs/examples/mock-run.md`, the three style prefixes, a prototype `PromptComposer` (`character_prompt`, `plate_prompt`, `scene_prompt`, `derive_pose_instruction_v2`, `repair_instruction`), RAM check, `nvidia-smi` peak sampler |
| `download_klein_4bit.py` | Downloads the community bundle `hlhc/FLUX.2-klein-4B-bnb-4bit` (4.8 GB) into the normal Hugging Face cache |
| `download_klein.py` | Official klein files (text encoder, VAE, GGUF); started and **stopped** because of the slow connection, resumable |
| `stage0_feasibility.py` | Does it run? One pipeline load, text-to-image at 1024 and 768, two edits and a two-reference call, with memory and timing |
| `klein_suite.py` | The full suite (references, plates, scenes, pose edits v1 and v2, repair, `ref_compose`); resumable; `--only` selects groups |
| `download_sdxl.py`, `sdxl_suite.py` | SDXL fp16 + IP-Adapter Plus download (10.3 GB) and test suite (`--quant nf4` quantises the UNet; run in three invocations to stay under the RAM cap; `*_longprompt` outputs show the 77-token truncation) |
| `score_klein.py` | Scores the images with the Gemma 4 E4B critic (spec check and reference comparison); needs `../critic_eval/serve.sh` running with 1120 image tokens |
| `out/` | Generated images and contact sheets (about 61 MB) |
| `results/` | Raw measurements (`stage0_bnb4.jsonl`, `klein_bnb4.jsonl`) and critic outputs (`klein_bnb4_critic_*.jsonl`) |

Run (memory-capped, as used):

```bash
cd experiments/image_bakeoff
python3 download_klein_4bit.py
systemd-run --user --scope -p MemoryMax=11G -p MemorySwapMax=0 python3 stage0_feasibility.py
systemd-run --user --scope -p MemoryMax=11G -p MemorySwapMax=0 python3 klein_suite.py --tag klein_bnb4
```

Scripts use the system Python (diffusers 0.40, torch 2.12+cu130, bitsandbytes) and are not a uv project yet. Logs of the individual runs (`*_run.log`, download logs) are kept next to the scripts.
