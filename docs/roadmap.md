# Roadmap

Principle from the brief: **prove the pipeline with simple scripts before building UI.**

## Phase 0 — Spikes (answer the unknowns on the real machine)

| # | Spike | Output | Decides |
|---|---|---|---|
| 0.1 | `llama serve` check: locate/install the binary, run Gemma 4 E2B with `--mmproj --jinja`, send one text and one image request | working command lines, version | llama version to pin; whether vision works as expected |
| 0.2 | Planner comparison: Gemma E2B vs Gemma E4B on 10 transcripts, with per-page calls and enum-restricted names; schema-constrained JSON; check specs are filled consistently and names are reused verbatim. **First round done on 3 stories** ([thinking-and-planner-tests.md](research/thinking-and-planner-tests.md)); needs more stories and the `has_effects` gate | JSON validity %, spec drift | Default planner |
| 0.3 | Critic accuracy. **Done for synthetic images** (40 images, 600 checks per condition; [critic-evaluation.md](research/critic-evaluation.md)): E4B + 1120 image tokens, thinking off is best (94.7% accuracy, 99% mismatch recall, 7.5% false alarms). **Still to do:** repeat on real generated images from the image bake-off, E4B with thinking on, E2B reference comparison, hair-colour handling. Original text: ≈30 images, correct and deliberately wrong (blue hood, missing hat); E2B vs E4B; use logprobs as a confidence signal | TP/FP rate per field | Whether the critic can be trusted; thresholds |
| 0.4 | **Done on synthetic speech + 14 user clips** ([stt-bakeoff.md](research/stt-bakeoff.md)): Whisper large-v3-turbo default, Parakeet int8 CPU fallback, Gemma audio rejected; Qwen3-ASR untested; real parent/child recordings still needed. Original scope: STT bake-off: Parakeet v3, Qwen3-ASR 1.7B, Whisper large-v3-turbo, Gemma-4-E2B audio on ≈10 real recordings | WER, latency, VRAM | Default STT |
| 0.5 | Image bake-off: FLUX.2 klein 4B (generate + edit; GGUF/fp8 vs bf16), SDXL + IP-Adapter, Z-Image-Turbo Q4_K_M, optionally Krea 2 Turbo Q4 GGUF. **Klein NF4 done** ([image-bakeoff.md](research/image-bakeoff.md): runs on the A2000, 9.9 s/image, 7.8 GB peak); **SDXL + IP-Adapter done** (30 s/image, identity kept but poses ignored, weaker prompt adherence; NF4 UNet quantisation works); Z-Image and the official klein weights not yet (downloads are slow: ≈0.9 MB/s) | VRAM/RAM peak, sec/image, consistency score, human rating | Default image backend |
| 0.6 | **Done (2026-10-11)**: Tauri + Python sidecar skeleton: spawn, token auth, SSE progress, kill on normal exit and on SIGKILL of the app; runs in a real window (sidecar "ready", demo job streams 8 steps to "done"). 29 automated checks (13 Python, 4 + 6 Rust, frontend type-check and build). Packaging (PyInstaller vs shipping uv + lockfile) still open. Original text: Tauri + Python sidecar hello world: spawn, token auth, SSE, kill | skeleton | Packaging approach |
| 0.7 | Image safety: choose an NSFW/violence classifier and test it on generated pages, including the unfiltered backends. Optional text check: minimal blocklist only | chosen classifier | Image safety layer; whether the optional text check is worth shipping |
| 0.8 | Structured output: (a) `response_format` json_schema together with `--mmproj` + an image in one request; (b) two-step plan with name enums; (c) one-shot schema vs interleaved scaffold; (d) round-trip of nested `outfit[]` and `layout[]`; (e) compare with `guidance` (llama.cpp backend) on validity, speed and memory; (f) logprob-based confidence | decision on A/B/C in [architecture.md](architecture.md) section 12 | Structured-output approach |
| 0.9 | Spec design test: run CharacterSpec / EnvironmentSpec / page-layout schemas on 10 transcripts; check the composed prompts render well on each image backend and that the critic can answer every field (incl. absence checks); tune the pose and expression enums | schema revisions | Final field list and enums |
| 0.10 | **Done for this machine (2026-10-11): CUDA torch 2.12.1 and the whole pipeline stack resolve and run in the sidecar's uv environment on Python 3.14 (cp314 wheels), results identical to the miniconda setup.** Still open: packaging for other machines (wheel size about 2 GB download, 5 GB installed). Original text: uv project: `uv sync` with CUDA torch on the chosen Python version; verify every backend group resolves | working `pyproject.toml` | Python version pin, packaging option |
| 0.11 | RGBA sources: compare SDXL + LayerDiffuse and plain-background + segmenter (BiRefNet, rembg with explicit model, RMBG-2.0) on hair, fur, capes, thin accessories | cutout quality notes, licences confirmed | Asset generation method per backend |
| 0.12 | Render modes: for the same 3 stories compare `layered`, `ref_compose`, `composite_refine` and `full_scene` on character consistency (critic + human), look, and time per page | scores | Default `render_mode` and the heuristics the planner uses to pick one |
| 0.13 | Harmonise pass: tune low-denoise img2img (0.2–0.35) vs an edit-model instruction, plus the contact-shadow / colour-grade parameters in the `Compositor` | parameter defaults | Whether layered pages need a model pass, and which kind |
| 0.14 | **First round done for klein NF4** (5 pose edits keep identity; repair 2 of 2; `ref_compose` with 3 images works; accessory clause needed in the template; expression words need care). Original scope: Edit-based derivation and repair: derive 5 poses/expressions from one reference by editing (identity retention judged by the critic and a human), distilled vs base FLUX.2 klein, repair success on deliberately wrong assets (purple robe → deep blue), `ref_compose` quality with 1–3 characters | retention and repair rates, instruction templates | Whether asset derivation and repair use edit by default; which klein variant |

**Status (2026-10-10):** image bake-off stage 0–1 done for klein NF4 ([image-bakeoff.md](research/image-bakeoff.md)); network ≈0.9 MB/s limits further downloads. **Earlier status (2026-10-09):** 0.1 done ([verification-log.md](research/verification-log.md)); 0.8(a) done (grammar works with `--mmproj` and images; nested `$defs` schema accepted; thinking on is compatible; reasoning-budget cut-off is safe); 0.3 done on synthetic images ([critic-evaluation.md](research/critic-evaluation.md)); 0.2 first round done ([thinking-and-planner-tests.md](research/thinking-and-planner-tests.md)); the rest not started.

Exit criteria: a default backend chosen for each stage, measured memory budget fits 8 GB VRAM / 16 GB RAM with sequential loading, and a documented fallback per stage.

## Phase 1 — Command-line pipeline (`scripts/`)

1. `transcribe.py audio.wav → transcript.json`
2. `plan.py transcript.json → plan.json` (character specs, environment specs, page layouts)
3. `assets.py plan.json → assets/*.png` (environment plates, character pose cutouts, with critic checks)
4. `compose.py plan.json → pages/*.png` (layered / composite-refine / full-scene, with critic and retry loop)
5. `export.py → book.pdf`
6. `run_all.py` chains them and logs timings and memory

Success: a 5-page book from a spoken story, with the main character recognisably the same on every page, produced end-to-end without manual steps.

**Phase 1 closed (2026-10-11); remaining picture-quality problems are accepted and listed in [limitations.md](limitations.md).** Human-in-the-loop redraw added (`scripts/regen.py`, `review.py`, full-size review pages), pipeline made story-independent (limits scale with story length, `--pages N`, 23 unit tests without a GPU, a test that forbids story names in the scripts) and tried on a long story, Goldilocks (8 pages, 14.7 min from audio). See [research/page-defects.md](research/page-defects.md).

**Earlier status: run on four stories, 6-9 minutes each.** The main characters stay recognisable on every page in all four; one story (Boat) has composition failures (floating head, character on water) that the spec-based critic cannot see. Reference repair works; page repair is kept only when it reduces mismatches (1 kept, 2 reverted of 3). Scripts: `transcribe.py`, `plan.py`, `assets.py`, `critic.py`, `render.py`, `export.py`, `run_all.py`. Details and gaps: [research/phase1-results.md](research/phase1-results.md).

## Phase 2 — Tauri app

**Second milestone done (2026-10-11): first-run check (Setup screen), the characters approval flow (plan, edit, draw, redraw one, approve, pages) and recording a story with the microphone (webview recording, validated WAV, delete after transcription). Next: packaging, then Phase 3 polish.** 

**Thin slice done (2026-10-11):** Library, New book (typed story or audio file), Generating with live progress and Cancel, Review with Redraw / Undo / earlier drawings / PDF, Settings; books are plain folders with no index; jobs reuse the Phase 1 scripts. Verified in the real window (isolated display), in a release-style build, with 24 + 36 + 32 automated tests. **Next:** microphone recording (WebKitGTK `getUserMedia` or capture in Rust; spike first), Characters and places approval screen, packaging of the sidecar, first-run checks (llama binary, models). Details: [architecture.md](architecture.md) (Phase 2 section) and [limitations.md](limitations.md).

Original scope:

- Rust core: SQLite + migrations, job queue, scheduler, supervisor.
- Svelte UI: Library, Record, Review, Generating, Reader (muted theme from [ui-design.md](ui-design.md)).
- Move script logic into the sidecar modules defined in [architecture.md](architecture.md).

## Phase 3 — Polish and export

- PDF/PNG export, character and environment library (reuse assets across books), per-page regeneration, layout editor, first-run diagnostics, model manager UI.
- Packaging for Linux; evaluate Windows.

## Later

- Urdu / code-switching STT (Whisper large-v3 class, possible LoRA fine-tuning).
- Background music (ACE-Step 1.5, licence check first).
- Read-aloud (TTS), tablet/phone client against the same core API.
- Trained character LoRAs for returning characters.

## Open questions

1. **Commercial intent?** **Decided 2026-10-09: keep the option to ship.** Defaults are commercially usable models only; non-commercial ones (FLUX.2 klein 9B, Krea 2 Turbo, RMBG-2.0, FLUX.1 Kontext) are labelled experiments. Original question: personal use only, or might this be shared or sold? This decides whether Krea 2 Turbo (custom licence), FLUX.2 klein 9B (non-commercial) and RMBG-2.0 (CC BY-NC) are allowed or experimental only. Until answered, the docs default to commercially licensed models.
2. **llama version and install flow:** *partly resolved* — `llama` 0.4.1-dev (build 11046) is at `~/.local/bin/llama` and runs both the Gemma 4 and `spark2_5` GGUFs. Still open: pin that build or detect any compatible build, and how the app installs it for other users (download the script and show it, rather than piping it into `sh`).
3. **Sidecar packaging:** PyInstaller bundle vs shipping uv + lockfile and creating the venv on first run (leading option; CUDA wheels are large). Which Python version to pin (system is 3.14; check wheels).
4. **Style:** **Preference 2026-10-10: crayon / coloured pencil** (after the klein results; flat is cleaner for compositing, so keep it as a secondary style). Earlier decision 2026-10-09: test all three (flat/cut-paper, soft watercolour, crayon/pencil) in the image bake-off and pick from real outputs. Flat styles should composite best. Open: is there a permissively licensed storybook LoRA per style, or do we train one?
5. **Safety defaults:** image check on by default (proposed) and the optional text check off by default. Should the image check be user-disableable for filtered backends?
6. **Z-Image-Turbo encoder/VAE:** exact files and sizes. `ZImagePipeline` and `Flux2KleinPipeline` are confirmed present in the installed diffusers 0.40.0.
7. **Gemma licence:** the GGUF metadata says `gemma`; Google's card says Apache-2.0. Confirm the governing terms.
8. ~~**Sharp-Spark:**~~ **Decided 2026-10-09: dropped.** Gemma 4 E4B is planner and critic (measured better); E2B is the low-VRAM fallback.
9. **Page length and page count:** fixed 4–6 pages, or adaptive to story length? Maximum story duration to record?
10. **Reference image flow:** does the parent approve a character's first asset before pages are generated, or is it fully automatic?
11. **Export:** page size and layout for PDF (square, A5, landscape); include the story text on the page image or beside it?
12. **Spec fields:** is the `CharacterSpec`/`EnvironmentSpec` field list right? Should `outfit` stay structured items or become a simple string, and should `scenario` carry separate `action` and `emotion` fields?
13. **Default render mode:** layered by default with `ref_compose`/`full_scene` fallback (proposed), or edit-model composition first? Decided by spike 0.12.
14. **Character sheet size:** how many poses and expressions are generated up front vs on demand (cost vs reuse)?
15. **Segmenter licence:** confirm the BiRefNet weights' licence; RMBG-2.0 needs a BRIA licence for commercial use.
16. **One image model or several?** If FLUX.2 klein 4B fits and looks good, it can generate plates, derive poses, compose pages and repair; otherwise SDXL (generation, IP-Adapter) plus a separate edit model. Decided by spikes 0.5 and 0.14.
17. **Distilled vs base klein for edits:** the 4-step distilled variant is fast; the base variant may follow edit instructions better. Decided by spike 0.14.
18. **Edit instruction templates:** wording for derive / repair / compose, kept in code and versioned; tuned in spike 0.14.
19. **Critic acceptance bar:** I proposed mismatch recall ≥ 90% and false alarms ≤ 10% on hard fields. E4B with 1120 image tokens meets it except false alarms on hair colour (19%) and held item (12%). Accept, tighten, or demote those two fields to soft? (Documented default: hair and skin colour soft in spec-check mode.)
20. **Planner thinking:** off by default for speed (measured no clear gain per cost); revisit per call type in spike 0.2.
21. **Reference-comparison critic:** lower false alarms (2.8%) but misses glasses removal (70% recall) and hair changes (65%); use as the second pass for low-confidence spec checks, or as the primary check for identity? Decide after repeating on real generated images.
