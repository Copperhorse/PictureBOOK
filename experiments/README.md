# Experiments

Throw-away but reproducible measurements that back the decisions in [`docs/`](../docs/README.md). Scripts here are not production code; they use the system Python (diffusers, pydantic, PIL) and the locally installed `llama` binary, and are not part of a uv project yet.

| Directory | What it measured | Report |
|---|---|---|
| [`critic_eval/`](critic_eval/README.md) | Vision critic accuracy (Gemma 4 E2B vs E4B, thinking, image tokens, reference comparison) and planner/thinking behaviour | [`docs/research/critic-evaluation.md`](../docs/research/critic-evaluation.md), [`docs/research/thinking-and-planner-tests.md`](../docs/research/thinking-and-planner-tests.md) |
| [`image_bakeoff/`](image_bakeoff/README.md) | FLUX.2 klein 4B (4-bit community bundle) on the RTX A2000: feasibility, quality, edits, critic on real images (SDXL, Z-Image, layering not yet) | [`docs/research/image-bakeoff.md`](../docs/research/image-bakeoff.md) |
| [`stt_bakeoff/`](stt_bakeoff/README.md) | Speech-to-text engines: Whisper large-v3-turbo, Parakeet TDT 0.6B v3, Gemma 4 audio | [`docs/research/stt-bakeoff.md`](../docs/research/stt-bakeoff.md) |
