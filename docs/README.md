# PictureBOOK — Documentation

PictureBOOK is a desktop app (Tauri) where a parent tells a story out loud and gets back a 4–6 page illustrated storybook. Everything runs locally on the user's machine.

Source brief: [`../picture-book.md`](../picture-book.md)

## Reading order

| # | Doc | What it answers |
|---|-----|-----------------|
| 1 | [research/models.md](research/models.md) | Which speech, image and language models can run on the target hardware, and why we picked what we picked |
| 2 | [architecture.md](architecture.md) | Processes, modules, model lifecycle, privacy/safety, project layout |
| 3 | [class.md](class.md) | Domain classes, module interfaces, SQLite schema, sidecar API contract |
| 4 | [ui-design.md](ui-design.md) | Muted visual style, screens and flow |
| 5 | [roadmap.md](roadmap.md) | Spikes, phases, open questions |
| — | [research/critic-evaluation.md](research/critic-evaluation.md) | 40-image critic evaluation: E2B vs E4B, thinking, image tokens, reference comparison |
| — | [research/thinking-and-planner-tests.md](research/thinking-and-planner-tests.md) | Thinking mode and planner shape (one call vs several) |
| — | [research/image-bakeoff.md](research/image-bakeoff.md) | Image bake-off stages 0–1: FLUX.2 klein 4B on the A2000 (feasibility, quality, edits, critic on real images) |
| — | [research/stt-bakeoff.md](research/stt-bakeoff.md) | Speech-to-text bake-off: Whisper turbo vs Parakeet vs Gemma 4 audio |
| — | [research/story-battery.md](research/story-battery.md) | Five fables and spooky tales run through the pipeline and inspected page by page |
| — | [limitations.md](limitations.md) | Known limitations of the pipeline (picture mistakes, weak spots, what the product does about them) |
| — | [research/phase1-results.md](research/phase1-results.md) | Phase 1 command-line pipeline: audio to PDF in one command, timings, gaps |
| — | [research/verification-log.md](research/verification-log.md) | What has actually been tested on this machine, and what has not |
| — | [examples/mock-run.md](examples/mock-run.md) | Hand-written end-to-end example: spoken story to every JSON output |

## Decisions so far

| Topic | Decision |
|-------|----------|
| Target | Linux desktop first (dev machine: i7-12800H, RTX A2000 8 GB VRAM, 16 GB RAM). Phone is out of scope. |
| App shell | Tauri 2 (Rust core) + Svelte + TypeScript |
| Inference | Python sidecar (managed with **uv**); LLM/vision via `llama serve` (llama.cpp) |
| Structured LLM output | JSON constrained by llama.cpp GBNF / `response_format` json_schema generated from pydantic models; `guidance` kept as a spike |
| Character / environment data | Uniform JSON specs (`CharacterSpec`, `EnvironmentSpec`) plus a free-text page `scenario`; prompts are composed from them in code |
| Speech-to-text | English only in v1. **Default: Whisper large-v3-turbo on the GPU** (1.9% WER overall, 8% at 0 dB noise, 2.1 GB VRAM). Fallback and CPU-only mode: Parakeet TDT 0.6B v3 int8 (3.9%, 0 VRAM, keeps fillers verbatim). Gemma 4 audio rejected as primary (fabricates text in heavy noise). Qwen3-ASR untested. [stt-bakeoff.md](research/stt-bakeoff.md). Swappable. |
| Story planning + consistency checking | Gemma 4 E4B (multimodal) — plans pages and looks at generated images to verify the character |
| Images | **FLUX.2 klein 4B (generate and edit) measured to run on the A2000 (community NF4 bundle: 7.8 GB peak, 9.9 s/image) and to give good results** ([image-bakeoff.md](research/image-bakeoff.md)); SDXL + IP-Adapter was tested too and is worse here (3× slower, weaker prompt adherence, no pose control; NF4-quantising its UNet works). Still untested: Z-Image-Turbo. Earlier shortlist: SDXL (+IP-Adapter/LoRA), Z-Image-Turbo; Krea 2 Turbo GGUF optional. Qwen-Image-2.1 and Hunyuan Image 3 dropped as too heavy. Final pick after a bake-off. |
| Image editing | An edit model derives character poses and environment variants from reference images, composes pages from several references, and repairs fields the critic flags (architecture section 5.2). |
| Rendering | Layered by default: reusable environment plates and RGBA character pose assets are composited per page; `ref_compose`, `composite_refine` or `full_scene` for interaction-heavy or effect pages. Default mix decided by spike 0.12. |
| Safety | Image check on by default; text check optional and off by default |
| Planner / critic model | Gemma 4 **E4B** with its vision projector via `llama serve` (E2B as the low-VRAM fallback). Critic: image budget `--image-min-tokens 1120 --image-max-tokens 1120`, thinking off, temperature 0. Planner: several constrained calls, thinking off by default. Sharp-Spark dropped. Measured in [critic-evaluation.md](research/critic-evaluation.md) and [thinking-and-planner-tests.md](research/thinking-and-planner-tests.md). |
| Art style | **Crayon / coloured-pencil preferred by the user (2026-10-10)**, after seeing flat, watercolour and crayon outputs from klein; flat remains the cleanest for compositing. Crayon prompts need "no text or lettering" (a stray caption appeared in one crayon reference). |
| Licensing posture | Keep the option to ship: commercially usable models by default |
| Next step | Remaining LLM spikes (uv skeleton, planner on more stories, STT bake-off), then the image bake-off. First critic and thinking tests are done (see the research documents). |
| Users | Parents creating books for children |
| v1 scope | Voice → 4–6 illustrated pages, character consistency, export PDF/PNG. No music, accounts or cloud. |
| UI | Muted grays/blacks, Nothing-inspired |

## Experiments

Reproducible measurements live in [`../experiments/`](../experiments/README.md): [`critic_eval/`](../experiments/critic_eval/README.md) (critic and planner tests, done) and [`image_bakeoff/`](../experiments/image_bakeoff/README.md) (klein and SDXL done) and [`stt_bakeoff/`](../experiments/stt_bakeoff/README.md) (done).

## Conventions

- Claims taken from the web are linked to a source in `research/models.md`. Anything marked **(verify)** was not confirmed from a primary source and must be measured on the target machine.
- Module boundaries follow the brief: each pipeline stage is a separate module with a simple input and output.
