# Verification log

What has actually been checked on the development machine (as opposed to read from the web). Dated 2026-10-09. Everything not listed here is still **(verify)**.

## 1. Machine

| Item | Result |
|---|---|
| CPU / RAM | i7-12800H (20 threads), 15 GiB total. During testing 7–8 GiB was already in use by other programs, leaving about 7 GiB available. **RAM headroom is a real constraint** (see decisions in the roadmap). |
| GPU | NVIDIA RTX A2000 Laptop, 8192 MiB, driver 615.71.09, CUDA 13.0, 0 MiB in use when idle |
| Disk | 267 GB free |
| Rust / Node | rustc 1.99.0, cargo 1.99.0, node 26.10.0, npm 12.2.0 |
| uv | 0.12.5 at `~/.local/bin/uv` |
| Python | 3.14.6 (miniconda). torch 2.12.1+cu130 imports and sees the GPU on this Python, so cp314 CUDA wheels exist for torch. Other backends (NeMo, etc.) are untested on 3.14. |
| diffusers | 0.40.0 has `ZImagePipeline`, `Flux2KleinPipeline` (its `__call__` takes `image: list[PIL.Image]`, so multi-reference/edit is available), `Flux2Pipeline`, `FluxKontextPipeline`, `StableDiffusionXLPipeline`, `StableDiffusionXLImg2ImgPipeline` |
| Tauri system packages | **Missing:** `webkit2gtk-4.1` (required by Tauri 2 on Linux) and `patchelf`. Present: gtk3, libsoup3, librsvg, openssl. Installing them needs `sudo pacman -S webkit2gtk-4.1 patchelf` (not run). |
| Already in the Hugging Face cache | `Qwen/Qwen3-ASR-0.6B`, `kyutai/pocket-tts` (TTS), `openbmb/MiniCPM5-2B`, embedding/other small models. No image-generation weights are downloaded yet. |

## 2. llama.cpp (`llama` binary)

- Found at `~/.local/bin/llama`: **version 0.4.1-dev, build 11046** (earlier docs said it was not on `PATH`; that was wrong because only `llama-server`, `llama-cli` and `ollama` were searched). Commands: `serve`, `cli`, `update`, `download`, `version`, `licenses`.
- `llama serve` flags present: `--mmproj`, `--jinja`, `--json-schema`, `--grammar`, `--reasoning`, `--reasoning-budget`, `--image-min/max-tokens`, `--api-key`, `--parallel`, `-ngl`, `-c`, `--host`, `--port`.
- **Gemma 4 E2B + mmproj loads and serves** (`-ngl 99 -c 8192`): about 2.7 GB VRAM (model, projector and KV cache), about 1.3–2.5 GB resident RAM, generation about 93 tokens/s, prompt processing 80–800 tokens/s. One image costs about 125 prompt tokens.
- **`Sharp-Spark-X2.5-4B` (`spark2_5`) also loads** in this build (tested CPU-only).
- Startup warnings worth knowing: the server binds with CORS open and no API key unless `--api-key` is given (we must set one and bind to `127.0.0.1`); audio input is marked experimental.

## 3. Structured output with llama-server (Gemma 4 E2B)

| Test | Result |
|---|---|
| `response_format` = `json_schema` on a text-only request with a nested schema (`outfit[]` array of objects, enums, `maxLength`) | Valid JSON, keys in schema order, 2.8 s for 162 tokens |
| `response_format` together with an **image** input (`--mmproj`) | Works. Critic schema returned valid JSON in about 1.9 s. This closes the "does the grammar work with `--mmproj`?" question for this build and model. |
| Critic smoke test on two images (I drew them myself with PIL: one crude cartoon figure, hood RGB (200,30,40) vs (40,70,200); expected "red") | Red image: `observed: red, match: true`. Blue image: `observed: blue, match: false`. Absence check for eyewear correct on both. Only two trivial images, so this was a smoke test of the plumbing, not accuracy data. The real evaluation (40 images, 600 checks per condition) is in [critic-evaluation.md](critic-evaluation.md). |
| **Thinking mode (first, flawed conclusion)** | The first runs used `max_tokens` 500–900; Gemma 4 E2B thinks by default and the reasoning used up the budget, leaving `content` empty or truncated. I wrongly concluded that thinking has to be disabled. **Superseded** by [thinking-and-planner-tests.md](thinking-and-planner-tests.md): with `--reasoning-budget 2048` and `max_tokens` 8192, structured output is valid in every call with thinking on, and an exhausted budget is cut off cleanly. Thinking is off by default only because it costs 2.7–2.8× time for no clear gain. |
| Unbounded schema parts | An `inferred_fields: array of free strings` ran to the token limit and produced truncated, unparseable JSON. Fixed by an enum for the allowed values, `maxItems`, and `maxLength` on every string. **Every string needs `maxLength`, every array `maxItems`, and open lists should be enums.** |
| Planner behaviour (one story, thinking off) | Good: sensible concrete values (brown hair, fair skin, deep blue robe) once the prompt said to invent visual details; `build: slight`, `height_relative: short` from "small frame and stature". **Weak:** `inferred_fields` listed only `build` and `height_relative`, although hair, skin and outfit were also invented. The model's self-report of what it invented is unreliable, so `inferred_fields` is computed in code (see class.md). |
| Spark planner, same prompt, CPU | 18 s; ignored the instruction to avoid `None` for hair/skin/outfit colour and chose `build: sturdy` for "small frame". Gemma E2B followed the instructions better in this single test. |
| **Full plan in one call** (nested pydantic schema with `$defs`, 5 pages) | Parsed and valid in about 13 s (about 1000 tokens), with and without added `maxLength`/`maxItems`. **But the content broke the rules a grammar cannot express:** one environment defined, three others referenced; `layout: []` on every page although the prince is in most; `effects` on every page; `render_mode: layered` on pages that had effects; page 5 `story_text` garbled; generic scenarios ("Describing the nature of the mages"); `inferred_fields` nonsense; species "Mage". Conclusion: split planning into several calls with enum-restricted names and let code compute or correct the rest (class.md, section 3). |
| Token probabilities | `logprobs` are returned. The values are **before** grammar masking (the grammar-forbidden token `"` had the highest probability), so confidence must be renormalised over the allowed tokens: `p(true) / (p(true) + p(false))`. In the test this gave about 1.0 (red) and about 0.97 (blue). |

## 4. Documents

| Check | Result |
|---|---|
| SQLite schema in `class.md` executes in SQLite with foreign keys on | OK, 15 tables |
| Internal links and anchors in all docs | 0 broken |
| JSON examples in `examples/mock-run.md` | All parse |
| Mock-run plan validated against pydantic models built from the enums in `class.md` (cross-references and the "effects ⇒ not `layered`" rule included) | Passes; the generated JSON Schema is about 5 KB with `$defs`/`$ref`, which llama.cpp must handle (spike 0.8: confirm nested `$ref` works, else flatten) |

## 5. Later results (same day)

All scripts, images and raw results of these tests: [`experiments/critic_eval/`](../../experiments/critic_eval/README.md).

- **Critic evaluation (40 synthetic images, 600 checks per condition):** best configuration is Gemma 4 E4B with a 1120-token image budget, thinking off: accuracy 94.7%, mismatch recall 99.0%, false alarms 7.5%, 5.8 s per call, 4.5 GB VRAM. Details, the flawed first image set and caveats in [critic-evaluation.md](critic-evaluation.md).
- **Thinking and planner shape:** [thinking-and-planner-tests.md](thinking-and-planner-tests.md).
- **llguidance (PyPI 1.9.1, MIT):** verdict "not needed now"; see the row in architecture.md section 12. The installed `llama` 0.4.1-dev appears to use llama.cpp's native GBNF engine.
- **Hardware figure to remember:** RAM was 7–8 GiB in use by other programs during all tests.

## 5b. Network and downloads (measured 2026-10-10)

- Internet to Hugging Face and Cloudflare measured **about 0.9 MB/s (about 7 Mbps)** with the downloader paused. The official klein files (11 GB, mostly an 8 GB text encoder) would take about 3.3 hours and the whole planned bake-off (about 40 GB) about 12 hours. This is why the first image test uses the community pre-quantised bundle `hlhc/FLUX.2-klein-4B-bnb-4bit` (4.8 GB, about 1.5 hours; Apache-2.0, safetensors only, no custom code). The official files remain resumable for a later quality comparison.
- Any user of the finished app faces the same first-run download problem for model weights: the app must show size and ETA, resume interrupted downloads, and work with the smallest viable model set first.
- Hugging Face is reachable and the account is logged in; none of the candidate repos are gated (klein 4B, SDXL, Z-Image-Turbo, IP-Adapter, BiRefNet). BiRefNet is MIT-licensed.

## 5c. STT bake-off (2026-10-11)

Whisper large-v3-turbo, Parakeet TDT 0.6B v3 (ONNX int8 on the CPU: the installed onnxruntime has no GPU provider) and Gemma 4 E4B/E2B audio through `llama serve` all ran on this machine; results in [stt-bakeoff.md](stt-bakeoff.md). `pocket-tts` 2.1.0 is installed with cached English models and was used to generate the synthetic test speech. The laptop's digital microphone is ALSA card 1 (`DMIC16kHz`, device 7) if live recording is needed.

## 5d. Tauri skeleton and system state (2026-10-11)

- Tauri 2 builds and runs here after `sudo pacman -S --needed webkit2gtk-4.1 patchelf` (webkit2gtk 2.54.1). The crates.io "latest" for `tauri` is a 3.0 alpha; the project pins the stable 2.x line. The official generator `create-tauri-app` 4.7.5 (template `svelte-ts`) produces SvelteKit with `adapter-static`; the generated `Cargo.toml` uses edition 2024, the workspace uses 2021.
- Debug builds started with `./target/debug/picturebook` need the Vite dev server running (`npm run dev`) because they load the dev URL; `npm run tauri dev` does both but its process tree died when started from a non-interactive shell, so launch with `setsid` when scripting.
- **System drift to know about:** after the package upgrade the NVIDIA userspace libraries are 615.78.08 while the loaded kernel module is 615.71.09, so `nvidia-smi` fails with "Driver/library version mismatch" until a reboot (the installed kernel is also newer than the running one). PyTorch's `torch.cuda.is_available()` still returned True. Measurement scripts that sample `nvidia-smi` (the GPU peak sampler in the experiments) report 0 until then. The sidecar's `/health` returns `gpu: null` instead of failing.
- Network and download speed are unchanged at about 0.9 MB/s; the Rust dependency fetch (all platform crates) took about 25 minutes, npm install about 1 minute.

## 5e. uv environment with torch (2026-10-11)
`sidecar/.venv` now holds torch 2.12.1+cu130 and the other pinned pipeline packages ([architecture.md](../architecture.md), section 9). `torch.cuda.is_available()` is true on the RTX A2000. Regression against the miniconda environment: identical pixels for the same seed, same peak memory, same transcript, stage times within 10%. This closes the "do CUDA wheels resolve on Python 3.14" question from spike 0.10.

## 5f. Phase 2 thin slice (2026-10-11)
- **Automated:** 24 script tests (no GPU), 36 sidecar tests (fake stage scripts: progress, failure, cancel with grandchild kill, one job at a time, path safety), 32 Rust tests (library rename/move/corrupt/duplicate/symlink cases, settings, job rules, real-sidecar job tests with refusals and cancel), `svelte-check` 0 errors and 0 warnings.
- **Real GPU job through the sidecar runner:** a 3-sentence story, 3 pages, PDF, 355 s.
- **In the real window** (the app ran in its own Xwayland display, `import` captured that display only, input sent with XTEST; the data folder was a scratch folder): typed a story, generation with live stages, automatic move to the review, title adopted from the plan, Redraw page 3 and page 2 (old drawing kept, thumbnail, Undo enabled, notes re-made), folder renamed on disk and found again, deleted picture shown as placeholder, broken folder listed and deleted from the UI, interrupted book after a kill, Settings with GPU info.
- **Release-style build** (`cargo build --features tauri/custom-protocol`, embedded frontend, real CSP): pictures load.
- **Kill test:** SIGKILL of the app during a generation: no sidecar, stage or `llama serve` left after 8 s, GPU 0 MiB.
- **Found and fixed on the way:** `<img>` could not load `asset://` in WebKitGTK (fetch + blob instead); computer notes of an old drawing were still shown after a redraw (notes now carry a picture signature); the progress bar went backwards when an optional stage appeared (now monotonic); dropdowns were unreadable (`color-scheme`).

## 5g. Second milestone, steps 1 and 2 (2026-10-11)
- **Tests:** 36 script tests (incl. step mapping, seeds, asset-file selection, slug cases shared with Rust), 88 sidecar tests (diagnostics every branch, plan editing validation and invalidation, step endpoint, parity of the sidecar's copies with the scripts), 39 Rust tests (plan summary, slug parity, planned status, job rules, real-sidecar edit and diagnostics), `svelte-check` clean.
- **In the real window** (isolated display, scratch data folders): Setup screen on the real machine (10 ok) and on an empty models folder (3 blockers, exact commands); the whole approval flow with a new story; single-character redraw; SIGKILL of the app during the characters job.
- **Found on the way:** the test temp folder is on a RAM disk with 8 GB free, which the disk check correctly flagged (made free space injectable for tests).

## 5h. Recording (2026-10-11)
- **Automated:** 15 JS tests (`npm run test:js`: WAV header and sizes, clipping, 5 device rates resampled to exactly 16 kHz, pause, chunking), 6 Rust audio tests (every truncation of a header, unsupported formats, length limits, ffmpeg conversion of stereo 44.1 kHz AAC and of garbage), 2 script tests (recording deleted only after a usable transcript, symlinks untouched), 6 diagnostics tests for the microphone line. Totals now: 94 sidecar, 38 script, 45 Rust, 15 JS.
- **In the app window:** the spike granted the microphone in 28 ms and captured 3 s (peak 0.09, room noise); the Record screen showed the live level meter and timer, the pulsing stop button and Pause/Finish; after Finish it showed the length (0:28), a working player, title, style and pages; the microphone stream was gone (0 source outputs) after each recording. A prepared 23 s speech file sent through `create_book_from_recording`: stored as `audio.wav` (736 KB), transcribed by Whisper correctly, planned ("The Lost Kite"), and `audio.wav` was **deleted** afterwards.
- **A slip to be honest about:** the real microphone was opened three times in total during testing (the 3 s spike, and two recordings of about 28 s and 5 s while I tried to route the app to a virtual sound card with `PULSE_SOURCE`, then `PIPEWIRE_NODE`, which this WebKit ignores). It records room noise only; the audio stayed in the app's memory and was discarded with "Record again" without ever being saved or transcribed. I stopped trying routing tricks after the second.
- **Not verified:** a real spoken recording through the Record screen end to end (would need the user's voice), recording longer than a minute, the 15-minute limit in the window, and Pause/Continue by hand (Pause is covered by the worklet test only).

## 5i. Code review before the showcase work (2026-10-12)
Method: `cargo clippy --all-targets`, `ruff` (undefined names, bugs, unused code) on `scripts/` and the sidecar, a read of the places where jobs, processes and the recorder interact, then hands-on probing of the suspicious paths.
- **Found and fixed (real bug): silence or noise became a made-up book.** Whisper turns silence into "Thank you." and noise into "."; the planner then invented a whole story ("A Simple Exchange"). `rules.story_problem` now stops with a plain message (too short, known Whisper phantom phrases, one word repeated) in `transcribe.py`, `from_text.py` and `plan.py`. Tested with silent and noisy WAV files and with all 21 demo stories (all pass the gate).
- **Fixed:** the recorder called its 15-minute "limit" callback on every later audio chunk (repeated messages and stop calls); it now fires once.
- **Fixed:** `preexec_fn` in the sidecar (documented as unsafe in a threaded process) is gone. The scripts now ask the kernel themselves (`common.die_with_parent`, with a check that the starting sidecar is still alive). Test: SIGKILL of the starter ends the job.
- **Fixed:** `critic.py assets` crashed on a character without candidate pictures; it now skips with a message.
- **Fixed:** finished jobs were kept forever in the sidecar; the last 50 are kept.
- **Fixed:** clippy "too many arguments" (`start_step` now takes a `StepRequest`); `run_all.py --steps plan` no longer prints a PDF path that does not exist.
- Re-run after the fixes: 61 script tests, 95 sidecar tests, 45 Rust tests, 15 JS tests, `svelte-check` 0 errors, clippy clean, and a real `run_all.py --steps plan` on a demo story (59 s, exit 0, 0 MiB VRAM afterwards).
- **Known and left alone (low impact, see limitations):** picture cache in the UI can revoke an image that is still on screen after 160 pictures; every command rescans the library (fine for dozens of books, slow for hundreds); after a full reload of the window the live progress of a running job is not shown until it ends; the llama port is fixed (18090); changing the library folder needs a restart; packaging is untested.

## 6. Still unverified (needs spikes)

- Any image model: nothing is downloaded. FLUX.2 klein 4B component sizes: Qwen3-4B text encoder is 7.49 GiB in bf16 (4.49 GiB int8); the transformer is roughly 8 GB in bf16; a community FP8 build reports a peak of about 7.8 GB VRAM with CPU offload on a 4090. The 8 GB A2000 will need FP8/offload and enough system RAM for the encoder.
- Speech-to-text candidates (Parakeet needs NeMo; Qwen3-ASR-0.6B is already cached locally; Gemma audio is flagged experimental by llama.cpp).
- Segmenter quality and licences, LayerDiffuse, edit-instruction behaviour, critic accuracy on real generated images, Gemma E4B comparison.
- Whether the full nested plan schema (with `$defs`) is accepted by `llama serve` as one request.
