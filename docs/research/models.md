# Model research

Target hardware (inspected): Intel i7-12800H (20 threads), **NVIDIA RTX A2000 Laptop 8 GB VRAM**, **16 GB RAM** (about 5.7 GB free at inspection time), Linux. Python 3.14, torch 2.12, diffusers 0.40 and transformers 5.5 are already installed.

> Most sources below are blogs, community posts or mirrors of model cards. VRAM, RAM and speed figures **must be validated on the A2000** (see [roadmap](../roadmap.md), Phase 0). Items marked **(verify)** are unconfirmed.

---

## 1. Speech-to-text (English only)

| Model | English avg WER (Open ASR leaderboard, short-form) | Size / licence | Notes |
|---|---|---|---|
| Whisper large-v3 | 7.44 (RTFx ≈146) | 1.55B, MIT | Older and slower; can hallucinate on silence. large-v3-turbo ≈7.8 and drops the translate task. |
| **Parakeet TDT 0.6B v3** | **6.32–6.34** (RTFx ≈3300); LibriSpeech test-clean ≈1.9 | 0.6B, CC-BY-4.0 | Very fast, punctuation and capitalisation included, word timestamps. NeMo on NVIDIA/Linux; a q8 GGUF exists for a ggml runtime. WER rises from ≈6.3 to ≈11.7 at 0 dB SNR. Covers 25 European languages (English fine). |
| Qwen3-ASR 1.7B | 5.90 in a third-party paper (same 8-set suite); 0.6B = 6.69 | ≈2B, Apache-2.0 | Streaming and offline. No official llama.cpp support; community GGUFs for other runtimes. ≈4–5 GB at FP16 **(verify)**. |
| Cohere Transcribe (2B) | ≈5.42, reported #1 in July 2026 | Apache-2.0 | Secondary report only **(verify)**. |
| Granite Speech 4.1 2B | ≈5.33 in one catalogue | IBM | Sources conflict **(verify)**. |
| Canary-Qwen 2.5B | 5.63 | CC-BY | Earlier leader. |
| Fish Audio | — | — | **No open-weight ASR found.** Fish Speech is text-to-speech (weights CC-BY-NC-SA). "Transcribe 1" is a hosted API only. Not usable locally. |
| Gemma 4 E2B (audio encoder) | unknown | Apache-2.0 per Google card | The `mmproj` of Gemma 4 E2B/E4B contains an audio encoder, so the same model could transcribe. Quality unmeasured **(verify)**. |

**Conclusions**

- Leaderboard WER differences between the top models are small; real conversational children's-story audio (pauses, restarts, background noise) will matter more. Test on real recordings.
- **Measured decision (2026-10-11, [stt-bakeoff.md](stt-bakeoff.md)): default Whisper large-v3-turbo on the GPU; Parakeet TDT 0.6B v3 int8 on the CPU as fallback; Gemma 4 audio rejected as primary (it fabricates text in heavy noise); Qwen3-ASR not tested.** Earlier web-research recommendation, kept for the record: default Parakeet TDT 0.6B v3 (fast, tiny, permissive), accuracy alternative Qwen3-ASR 1.7B. Whisper stays as a fallback. Leaderboard order differs between sources, so check the live Open ASR Leaderboard when implementing.
- Urdu / code-switching is deferred (Whisper large-v3 reached ≈0.29 WER on Urdu and ≈0.53 on code-switched speech in a 2026 corpus paper; Parakeet v3 does not cover Urdu).

Sources:
[Open ASR Leaderboard paper](https://arxiv.org/html/2510.06961v4) ·
[Parakeet TDT 0.6B v3 card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) ·
[Qwen3-ASR vs Parakeet vs Whisper](https://soniqo.audio/benchmarks) ·
[Qwen3-ASR GGUF (transcribe.cpp)](https://huggingface.co/handy-computer/Qwen3-ASR-1.7B-gguf) ·
[Gladia: open-source STT 2026](https://www.gladia.io/blog/best-open-source-speech-to-text-models) ·
[MarkTechPost: best open ASR 2026](https://www.marktechpost.com/2026/07/23/best-open-speech-recognition-asr-models-in-2026-wer-languages-latency-and-license-compared/) ·
[Fish Speech V1 card](https://huggingface.co/fishaudio/fish-speech-1) ·
[Urdu ASR benchmark](https://arxiv.org/html/2409.11252v3)

---

## 2. Text-to-image (8 GB VRAM)

### Candidates

| Model | Size on disk (quant) | Fits 8 GB? | Licence | Character consistency tooling | Runtime |
|---|---|---|---|---|---|
| **SDXL** (+ storybook LoRA, IP-Adapter) | ≈6.9 GB fp16 | **Measured:** fp16 with the IP-Adapter encoder does not fit; with CPU offload it runs at 30 s/image but needs 11–12 GiB RAM; with an NF4-quantised UNet it runs on the GPU in 6 GiB RAM at the same speed ([image-bakeoff.md](image-bakeoff.md), section 7) | CreativeML OpenRAIL++ (check per checkpoint) | Most mature: character LoRA, IP-Adapter, ControlNet | diffusers, in-process |
| **Z-Image-Turbo** (6B, 8 steps, CFG 0) | GGUF Q4_K_M 5.02 GB, Q5_K_M 5.57, Q6_K 5.91, Q8_0 7.22 | Likely, with text encoder offload **(verify)** | Apache-2.0 | No native reference image; seed lock, LoRA, low-strength img2img | diffusers `ZImagePipeline` or ComfyUI |
| **Krea 2 Turbo** (≈12B, 8 steps) | FP8 ≈12 GiB; community GGUF Q4_0 reported ≈7.6 GB VRAM, Q4_K_M/Q5_K_M ≈8.9 GB | Barely, Q4 class with offload **(verify)** | Custom (free below roughly 50 seats; sources disagree **(verify)**) | Style-reference workflow mentioned; otherwise unknown | ComfyUI ≥0.26 + ComfyUI-GGUF |
| **FLUX.2 [klein] 4B** (distilled 4-step or base; text-to-image **and** edit) | Third-party figures conflict (≈8.4–9.2 GB at bf16, "13 GB" official). **Measured here:** the community NF4 bundle (4.83 GB download) runs entirely on the 8 GB card: 4.5 GiB weights, 6.9 GiB PyTorch peak, 7.8 GB board peak, 3.7 GiB RAM, 9.9 s per 1024² image, 19.5 s per edit, 44.6 s for a 3-reference page ([image-bakeoff.md](image-bakeoff.md)) | **Yes** (≈350 MiB spare at 1024²) | **Apache-2.0** (4B). The 9B variant is non-commercial. | Multi-reference editing (up to 4 input images) with the same weights; see section 3d | diffusers or ComfyUI |
| **Hunyuan Image 3** (80B MoE, 13B active) | W4A8 44.7 GiB | **No** — needs ≈50 GB RAM streaming | Tencent Hunyuan Community Licence (excludes EU, UK, South Korea) | n/a | ComfyUI/WanGP community ports |
| FLUX.1 schnell GGUF Q4 | ≈6.5–6.8 GB | Yes, tight with text encoder offload | Apache-2.0 | LoRAs; weaker than SDXL | ComfyUI-GGUF |

### Dropped: Qwen-Image-2.1 (including the `abenzerps` "uncensored" GGUF and Qwen-Image-Edit)

Evaluated and **not used** (decision: too heavy for the target device). Reasons recorded for the decision log:

- The pipeline is a 7B diffusion transformer plus an 8B Qwen3-VL text encoder (≈33 GB in BF16). Quantised, the transformer fits (Q4_K_M ≈4.6 GB) but the encoder needs ≈9.4 GB of **system RAM** even at int8, which is most of this machine's 16 GB.
- Edit variants reportedly need Q2/Q3 quantisation or heavy offloading on 8 GB, with visibly softer output.
- Qwen Research Licence: non-commercial.
- The `abenzerps` GGUFs have no safety checker (author's claim), need the leejet fork of ComfyUI-GGUF, and no independent 8 GB speed figures exist (5.9 s on an RTX 5090).
- Its multi-reference and typography strengths are covered more cheaply by FLUX.2 klein 4B (section 3d).

### Reddit comparison supplied by the user (Hunyuan Image 3 vs Qwen Image 2.1 vs Krea 2 Turbo)

- Author's tests were on an **RTX 3090 24 GB**, int8 convrot variants, best of 4 seeds, mostly photoreal, typography and portrait prompts. Speeds: Krea 2 Turbo 8–9 s, Qwen 16 s, Hunyuan 20–26 s.
- Ranking: 1 Krea 2 Turbo (natural detail, good styles and typography), 2 Qwen Image 2.1 (very detailed but oversharpened; weak VAE gives mushy eyes), 3 Hunyuan Image 3 (low detail, weaker typography, VAE stripe artifacts). Only Krea 2 Turbo remains a (heavy) candidate for us.
- Limits for us: single subjective reviewer, 3090 timings, no children's-illustration or consistency tests. The 17-image gallery was images only (ids such as `1-HY-QW-KR`) and could not be inspected.

### Shortlist

1. **SDXL + IP-Adapter / character LoRA** — safest default for consistency on 8 GB; no native edit capability.
2. **FLUX.2 [klein] 4B** — Apache-2.0, text-to-image plus single- and multi-reference editing in one model; could serve plates, character assets, pose derivation, repairs and page composition. **Measured to run on the A2000** (community 4-bit weights; the official bf16/GGUF weights and the quality difference are untested). Leading candidate; SDXL and Z-Image comparisons still pending.
3. **Z-Image-Turbo Q4_K_M** — commercially licensed, fast, light; consistency via seed + LoRA + img2img; no edit model released yet.
4. Optional experiment: **Krea 2 Turbo GGUF** (≈12B, tight on 8 GB, custom licence).
5. Excluded: Hunyuan Image 3, Qwen-Image-2.1, FLUX.1 Kontext [dev] (12B, non-commercial).

Sources:
[Qwen-Image-2.1 release (MarkTechPost)](https://www.marktechpost.com/2026/09/21/alibaba-qwen-releases-qwen-image-2-1/) ·
[Qwen-Image-2.1 licence catch](https://www.eesel.ai/blog/qwen-image-2-1) ·
[abenzerps GGUF repo](https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-GGUF) ·
[Z-Image-Turbo GGUF (Unsloth)](https://huggingface.co/unsloth/Z-Image-Turbo-GGUF) ·
[Z-Image Turbo review](https://saascrmreview.com/z-image-turbo-review/) ·
[Z-Image low-VRAM guide](https://zimage.run/blog/zi-166-z-image-gpu-memory-optimization-en-20260728) ·
[Krea 2 open weights (VentureBeat)](https://venturebeat.com/technology/enterprise-grade-ai-image-generation-in-2-seconds-is-here-krea-2-raw-and-turbo-available-as-open-weights-under-custom-license) ·
[Krea 2 Turbo GGUF in ComfyUI](https://www.kombitz.com/2026/06/26/how-to-use-krea-2-turbo-gguf-workflow-in-comfyui/) ·
[Krea 2 Turbo on RTX 3060 12 GB](https://smeltcore.com/recipes/krea-2-rtx-3060/) ·
[HunyuanImage-3.0 ComfyUI port](https://github.com/PedroMarinhoDev/ComfyUI-HunyuanImage3) ·
[FLUX on 6–8 GB](https://localaimaster.com/blog/run-flux-on-low-vram-gpu) ·
[IP-Adapter (diffusers)](https://huggingface.co/docs/diffusers/using-diffusers/ip_adapter) ·
[Character consistency techniques](https://dev.to/qcrao/character-consistency-in-ai-comics-3-tricks-that-beat-lora-training-for-me-3ad7)

### Character consistency approaches (ranked)

1. Character LoRA trained on 15–30 images — most reliable; one unverified test reported ≈85% facial consistency vs ≈35–40% with prompts alone.
2. IP-Adapter reference image — no training; drifts on large pose/style changes.
3. Reference-based editing (FLUX.2 klein 4B) — derive every pose and expression from one reference image; see section 3d.
4. Prompt discipline — a fixed, short identity description in every prompt (always on).
5. ControlNet — pose/composition only, does not carry identity.

Whatever the generator, every page is checked by the vision critic (section 3).

---

## 3. Language / vision model (story planning and consistency critic)

### Local models inspected (read-only, `~/models/`)

| File | Notes |
|---|---|
| `gemma_2/gemma-4-E2B-it-qat-UD-Q4_K_XL.gguf` (2.6 GB) + `mmproj-F16.gguf` (0.99 GB) + `mtp-gemma-4-E2B-it.gguf` (59 MB) | Gemma 4 **E2B**, arch `gemma4`, 35 layers, 131k context, vision (`gemma4v`) **and audio** (`gemma4a`) encoders. Folder is named `gemma_2` but holds E2B. |
| `gemma_4/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf` (4.2 GB) + mmproj + MTP | Gemma 4 **E4B**, 42 layers. Upgrade path. |
| `Sharp-Spark-X2.5-4B-Q6_K_XL.gguf` (3.4 GB) | **Dropped (decision 2026-10-09).** Custom arch `spark2_5`, text only, no public model card, imatrix data cyber/occult-themed. It loads in the installed `llama` build, but in a live test it ignored instructions and chose `build: sturdy` for "small frame" (see [verification-log.md](verification-log.md)); Gemma 4 E2B did better and can also see images. |

### Decision: Gemma 4 E4B as planner **and** vision critic (E2B as the low-VRAM fallback)

One `llama serve` process with `--mmproj` gives:

1. **StoryPlanner** — turns the transcript into uniform JSON character and environment specs plus per-page scenario and layout (image prompts are composed in code from those).
2. **ConsistencyCritic** — looks at each generated character asset and page and checks it against the character spec and the reference image (for example: "Red Riding Hood's hood must be red" and page 2 shows blue).

Measured result (2026-10-09): the first plan was E2B with E4B as the upgrade path; the 40-image evaluation made **E4B with a 1120-token image budget** the default critic (94.7% accuracy, 99% mismatch recall, 7.5% false alarms vs 91.8% / 94% / 9.2% for E2B), and E4B also kept all stated facts in planner tests (24/24 vs 22–23/24). It needs 4.5 GB VRAM (E2B: 3.1 GB). See [critic-evaluation.md](critic-evaluation.md) and [thinking-and-planner-tests.md](thinking-and-planner-tests.md).

Risks and mitigations

- The vision tower reports 224 px / patch 16 in its metadata, and at the default image-token budget small details were indeed missed; `--image-min-tokens 1120 --image-max-tokens 1120` fixed most of it. Check large attributes (colours, clothing, species) and keep questions closed.
- Small VLMs can hallucinate. Use schema-constrained JSON, low temperature, a confidence threshold and two passes.
- Reported MMMU-Pro: E2B 44.2 vs E4B 52.6 (third-party mirror of the card, **verify**); consistent with the measured critic results.
- Licence: Google's card says Apache-2.0; the GGUF's own metadata says `gemma`. Read the actual terms before shipping.

### Running it

The user runs models with `llama serve -m <file.gguf>` (the unified `llama` binary from llama.cpp, installed with `curl -LsSf https://llama.app/install.sh | sh`). Verified on the dev machine: `~/.local/bin/llama`, version 0.4.1-dev (build 11046); it loads Gemma 4 E2B with its projector and the `spark2_5` model (see [verification-log.md](verification-log.md)). The installer should download the script and let the user read it rather than piping it into `sh`, and should pin a known-good version because the script installs nightly builds. Vision needs `--mmproj <file>` and `--jinja`.

Sources:
[Gemma 4 E2B card](https://huggingface.co/google/gemma-4-E2B) ·
[Unsloth: run Gemma 4](https://unsloth.ai/docs/models/gemma-4) ·
[Unsloth Gemma 4 E2B GGUF](https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF) ·
[llama.cpp + Gemma 4 guide](https://avenchat.com/blog/run-gemma-4-with-llama-cpp) ·
[llama.app installer notes](https://jacar.es/?p=7215)

---

## 3b. Layered generation components

Characters and environments are generated as separate assets and composited (see [architecture.md, section 5.1](../architecture.md#51-layered-rendering)).

| Component | Role | Notes |
|---|---|---|
| **LayerDiffuse** (SDXL / SD1.5) | Generates transparent RGBA images directly; also has foreground/background-conditioned models for blending | Works with SDXL; ComfyUI nodes exist. Some features are SD1.5-only; sources disagree on img2img/inpainting support, so confirm the current state **(verify)**. One guide reports higher-quality transparency than removing the background afterwards. |
| **Plain background + segmenter** | Default for edit-model and non-RGBA outputs | Edit and most text-to-image models return RGB, so assets are generated on a plain background and cut out |
| **BiRefNet** | Background removal / cutout | Reported strongest open option on hair and fine edges in a single test and by a ComfyUI user (can over-correct); licence not verified here **(verify)** |
| **RMBG-2.0** (BRIA) | Background removal | CC BY-NC 4.0; commercial use needs a BRIA agreement (per model-card mirrors). Vendor claims 90% vs BiRefNet 85% are self-reported. |
| **rembg** | Runtime that loads segmentation models | Default `u2net` is notably weaker (clipped a hand in one test); pick the model explicitly |

Practical technique (from general practice, not from a single source): composite the cutout, then a low-denoise img2img pass (≈0.2–0.35) to blend edges and lighting; paint a contact shadow separately because inpainting a transparent layer does not work. Tune in spike 0.13.

Sources:
[LayerDiffuse for SDXL (ComfyUI)](https://www.runcomfy.com/comfyui-nodes/ComfyUI-layerdiffuse) ·
[Transparent images with Layer Diffusion](https://www.mybyways.com/blog/generate-transparent-images-with-layer-diffusion/) ·
[Transparent backgrounds in Stable Diffusion](https://stable-diffusion-art.com/transparent-background) ·
[BRIA RMBG 2.0 announcement](https://blog.bria.ai/brias-new-state-of-the-art-remove-background-2.0-outperforms-the-competition) ·
[Background removal in ComfyUI (BiRefNet)](https://medium.com/code-canvas/background-removal-in-comfyui-just-got-really-really-good-2a12717ff0db) ·
[Best background removal API comparison](https://aireiter.com/blog/best-background-removal-api)

---

## 3d. Image-to-image / editing models

An edit model takes one or more input images plus a text instruction. For PictureBOOK it enables: deriving a new pose or expression from a character's reference image, deriving environment variants ("same place at night"), multi-reference page composition (`ref_compose`), a harmonise pass, and **targeted repair** of a field the critic flagged (see [architecture.md, section 5.2](../architecture.md#52-edit-model-operations)).

| Model | Edit capability | Fit for 8 GB VRAM / 16 GB RAM | Licence | Verdict |
|---|---|---|---|---|
| **FLUX.2 [klein] 4B** | Same weights do text-to-image, single-reference editing and multi-reference editing (up to 4 input images). Distilled variant uses 4 steps; a base variant exists for fine-tuning and, per one forum guide, edits. | Conflicting third-party figures: ≈8.4 GB (distilled) to ≈9.2 GB (base) VRAM in ComfyUI measurements, "as little as 13 GB" in the official-style spec, GGUF Q4_K_M ≈2.6 GB (unconfirmed). Sub-second to ≈17 s per image on an RTX 5090; no A2000 data. **Verify.** | Apache-2.0 for 4B; the 9B model is non-commercial | **Leading candidate** |
| SDXL img2img / inpaint / IP-Adapter | Low-denoise img2img, inpainting, reference conditioning; no instruction-based editing | Comfortable | OpenRAIL++ | Fallback; fine for harmonise passes, weak for "change the pose" |
| FLUX.1 Kontext [dev] (12B) | Character/style/object reference with iterative edits and low drift (vendor claim) | Q4 GGUF ≈8.1 GB (third-party), T5 on CPU | FLUX.1 non-commercial; commercial via BFL licence; content filters required | Not planned: heavy and non-commercial; no pose-change tests found |
| Z-Image-Edit | Announced | — | — | **Not released** per the official repo and a June–August 2026 issue thread; do not plan around it |
| Qwen-Image-Edit / Qwen-Image-2.1 | Strong editing | Q2/Q3 or heavy offload on 8 GB, softer output; text encoder ≈9.4 GB in RAM | Non-commercial | **Dropped** (see section 2) |

Risks to measure in spike 0.14: identity retention over several derived poses, instruction-following of the distilled vs base variant, repair success rate on deliberately wrong assets, VRAM/RAM peak on the A2000, edit drift if an edit is ever applied to an edit (the design forbids it).

Sources:
[FLUX.2 klein 4B and 9B in ComfyUI](https://blog.comfy.org/p/flux2-klein-4b-fast-local-image-editing) ·
[ComfyUI FLUX.2 klein guide](https://docs.comfy.org/tutorials/flux/flux-2-klein) ·
[FLUX.2 klein 4B model card](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) ·
[FLUX.2 klein launch (VentureBeat)](https://venturebeat.com/technology/black-forest-labs-launches-open-source-flux-2-klein-to-generate-ai-images-in) ·
[FLUX.1 Kontext [dev] announcement](https://bfl.ai/blog/flux-1-kontext-dev) ·
[Z-Image repository (Edit not released)](https://github.com/Tongyi-MAI/Z-Image) ·
[Z-Image-Edit release-timeline issue](https://github.com/Tongyi-MAI/Z-Image/issues/169) ·
[Qwen-Image-Edit on low VRAM](https://localaimaster.com/blog/qwen-image-edit-local-guide)

---

## 3c. Constrained decoding (structured JSON)

Practical rules are summarised in [architecture.md, section 12](../architecture.md#design-rules-from-constrained-decoding-practice). Source: Aidan Cooper, [Structured generation with constrained decoding](https://www.aidancooper.co.uk/constrained-decoding/) (April 2024).

---

## 4. Later: music generation (not in v1)

| Model | Licence | Notes |
|---|---|---|
| ACE-Step 1.5 | Apache-2.0/MIT per listings **(verify)** | Base model reported under 4 GB VRAM; XL variants need ≥12 GB |
| MusicGen | Code MIT, **weights CC-BY-NC** | Non-commercial |
| Stable Audio Open | Stability community/non-commercial terms **(verify)** | ≈1.2B, up to 47 s |

Sources: [ACE-Step 1.5](https://github.com/ACE-Step/ACE-Step-1.5) · [MusicGen / AudioCraft](https://github.com/dotsimulate/audiocraft) · [Stable Audio Open](https://venturebeat.com/ai/stability-ai-debuts-new-stable-audio-open-for-sound-design)

---

## 5. Desktop integration notes (Tauri)

- Tauri 2 sidecars (`externalBin` plus the shell plugin) are the documented way to ship a bundled Python process on desktop. A PyInstaller sidecar adds tens of MB before models. Weights are not bundled; they are discovered in `~/models` or downloaded on first run.
- Android sidecars are not relevant (phone out of scope).

Sources: [Tauri sidecar docs](https://v2.tauri.app/develop/sidecar/) · [Tauri 2 mobile support](https://alternativeto.net/news/2024/10/tauri-2-0-enhances-cross-platform-app-development-with-mobile-support-and-improved-plugins)

---

## 6. Bake-off protocol (Phase 0)

Run the same test set against every candidate and record results in `docs/research/bakeoff-results.md`.

**Image models**

- 3 short stories, each with one recurring character plus a side character, 5 pages each, one fixed storybook style prompt.
- Per model: peak VRAM, peak system RAM, seconds per page (cold and warm), failures/OOMs.
- Consistency: Gemma critic attribute match rate per page, plus a human 1–5 score for style and character identity.
- Child-safety: run adversarial prompts and see what the moderation layer catches.

**STT**

- 10 real recordings of a parent telling a story in a normal room: quiet, TV noise, fast speech, restarts. Compare WER against hand transcripts for Parakeet, Qwen3-ASR, Whisper large-v3-turbo and Gemma-4-E2B audio.

**Critic**

- 30 images: correct pages and deliberately wrong ones (blue hood, missing hat, different hair). Report true-positive and false-positive rate per attribute, E2B vs E4B.
