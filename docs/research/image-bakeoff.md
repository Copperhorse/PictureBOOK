# Image bake-off, stages 0–2: FLUX.2 klein 4B and SDXL on the RTX A2000

Run on 2026-10-10 on the dev machine (RTX A2000 Laptop 8 GB, 15 GiB RAM). Scripts, prompts, images and raw measurements: [`experiments/image_bakeoff/`](../../experiments/image_bakeoff/README.md). Companion: [critic-evaluation.md](critic-evaluation.md).

**Scope done so far:** FLUX.2 klein 4B (community pre-quantised 4-bit bundle, sections 1–6) and SDXL base 1.0 fp16 with IP-Adapter Plus (section 7). **Not done:** Z-Image-Turbo, the official bf16/GGUF klein weights, SDXL with ControlNet or a storybook LoRA, segmentation and layered compositing. The user has seen the klein images and prefers the crayon style.

## 1. What was tested

- **Model:** [`hlhc/FLUX.2-klein-4B-bnb-4bit`](https://huggingface.co/hlhc/FLUX.2-klein-4B-bnb-4bit), a community upload (Apache-2.0, safetensors only) of the official FLUX.2-klein-4B (distilled, 4 steps) quantised with bitsandbytes NF4: text encoder 2.65 GB, transformer 2.0 GB, VAE 0.17 GB (4.83 GB download). Chosen because the connection to Hugging Face measures about 0.9 MB/s: the official files (11 GB) would have taken about 3.3 hours, this bundle took 1 h 50 min. The official weights were not compared, so any quality loss from 4-bit quantisation is unmeasured.
- **Setup:** whole pipeline on the GPU (`pipe.to("cuda")`), bf16 compute, 4 steps, guidance 1.0, `diffusers` 0.40 `Flux2KleinPipeline`, 1024×1024 unless noted. Each run was started under `systemd-run --scope -p MemoryMax=11G -p MemorySwapMax=0` so a memory blow-up could not freeze the desktop (it never triggered).
- **Content:** the Arcania story from the [mock run](../examples/mock-run.md): the prince and the mage (specs from the mock-run JSON), two environments, prompts composed by a small prototype `PromptComposer` in three styles (flat cut-paper, soft watercolour, crayon/pencil). 44 images in total (7 in the feasibility stage, 37 in the full suite).
- **Tasks:** character reference (3 styles × 3 seeds), environment plates (3 styles × 2 seeds, plus the courtyard), full scene for page 4 (3 styles × 2 seeds), pose/expression derivation by **editing the reference** (two instruction templates), targeted repair (recolour the robe), and `ref_compose` (courtyard plate + prince reference + mage reference in one call) against the same page from text only.
- **Scoring:** the Gemma 4 E4B critic (1120 image tokens, thinking off) checked every character image against the spec (true values and deliberately wrong values) and compared edited images with the reference. I also looked at every image myself; those judgments are labelled "my view".

## 2. Does it run on the A2000? Yes, with little headroom

| Measurement | Result |
|---|---|
| Weights on the GPU | 4.5 GiB |
| Peak PyTorch allocation (1024², any task) | 6.9 GiB |
| Peak GPU memory as seen by `nvidia-smi` (includes the CUDA context) | 7,842 MiB of 8,192 MiB (about 350 MiB spare) |
| Peak process RAM | 3.7 GiB |
| Load time (from the local cache) | about 2 s |
| Text-to-image 1024², 4 steps | 9.9 s each (24 images, cold and warm identical) |
| Text-to-image 768² | 5.9 s (peak 5.85 GiB PyTorch, 7,066 MiB `nvidia-smi`) |
| Single-reference edit 1024² | 19.5 s (12 images) |
| Two-reference call | 30.9 s; three-reference `ref_compose` 44.6 s |
| Out-of-memory errors | none in 44 generations; the CPU-offload mode was not needed and not tested |

Consequences: no llama server can run at the same time (consistent with the sequential-loading design); 768 px is the fallback if memory is ever tight; a 5-page story needs roughly 2 plates, 2 character references, 3–5 pose edits and 2–3 composed pages, about 4–6 minutes of generation, plus a few seconds per critic check.

## 3. Quality (my view, not a user rating)

- **Styles:** the flat cut-paper style is the cleanest and most consistent. Watercolour and crayon are attractive but busier. Two of the nine character references (one watercolour, one crayon) contain a hallucinated caption ("Setch Price"); a distilled model at guidance 1.0 takes no negative prompt, so the prompt needs a positive instruction such as "no text or lettering".
- **Environments:** all three styles produce usable, rich backgrounds with the requested elements (floating islands, crystals, stone bridge; rune circle and arches). The prompt's "no people" was respected in every plate.
- **Different seeds give different characters** (hair, robe cut, how the stick is held), as expected: consistency has to come from editing one chosen reference, not from re-prompting.
- **Text-only full scenes drift in identity:** the prince's robe sometimes has a hood or a white skirt, the stick varies. The critic flagged a hood in two of six scenes where the spec says no headwear.
- **Pose derivation by editing works well.** The edited characters keep the face, hair, robe colours and proportions; sitting, walking, waving, a raised stick and a standing pose were all convincing. Weak points: the "determined" expression renders as angry and "shy" as sad; the first template did not mention the stick and it vanished in 4 of 5 edits.
- **Targeted repair works:** "change the robe colour from deep blue to red / purple, keep everything else exactly the same" recoloured the robe and kept face, pose, stick and shadow (2 of 2).
- **`ref_compose` works:** with the courtyard plate and both references, the page keeps the plate exactly and both characters look like their references, with the prince visibly shorter than the mage. The text-only version of the same page (`compose_p3_textonly.png`) gave different-looking characters: the mage lost his reference hat and staff and gained a shoulder strap, which the user noticed on first viewing.
- **User style preference (2026-10-10): crayon / coloured pencil.**

## 4. Critic on real generated images

| Check | Result |
|---|---|
| Spec check, true values (22 images × 5 attributes) | 104 accepted, 6 rejected. All 6 rejections are justified by what is in the image: the stick missing in 4 pose edits made with the first template, and a hood present in 2 scenes. No clear false alarm. |
| Spec check, wrong values (blonde, pointed hat, round glasses, basket, wrong robe colour) | 110 of 110 rejected |
| Reference comparison, 7 first-round edits | the 4 lost sticks and the 2 recoloured robes reported as different; the raised-stick pose "all same"; nothing else flagged |
| Second round with the improved instruction template (stick named) | stick kept in 5 of 5 edits; spec check and reference comparison accepted all five attributes in all five images |

Caveats: few images; a clear flat cartoon style where the target attributes are large; the wrong values I chose are easy to tell apart; the spec was written to match what the model draws well. This supports, but does not replace, the synthetic-image evaluation: on this kind of image the critic agrees with a human look.

## 5. Findings that change the design

1. **Edit templates must name the accessories to keep.** Use "…keep the face, hair, outfit colours and proportions unchanged, and keep the small wooden stick in the hand" (template v2 in `experiments/image_bakeoff/bakeoff_common.py`). The architecture's instruction template was updated.
2. **The retry order "targeted edit first" is validated**: the repair edit recoloured exactly what was asked.
3. **Expression words need care**: "determined" and "shy" map to angry and sad. Either map the enum to clearer descriptions ("focused, calm", "bashful, small smile") or review expression results in the critic.
4. **A single model can cover plates, references, pose edits, repair and multi-reference composition**, so the model list can stay short.
5. **Memory leaves no room for anything else on the GPU**, so the sequential scheduler is mandatory and 768 px should exist as a lower-memory mode.
6. **Prompt hygiene:** add "no text, no lettering, no captions" to character-sheet prompts.

## 6. What this does not settle

- SDXL + IP-Adapter and Z-Image-Turbo were not tested, so "klein is better than the alternatives" is **not** shown, only "klein works well here".
- 4-bit community weights vs the official bf16/GGUF weights: quality difference unknown.
- Layered compositing (cutouts and a `Compositor`), segmentation quality and the harmonise pass are untested; `ref_compose` already gives good pages, so layering may be less necessary.
- The user has not rated the images or styles yet. Contact sheets are in `experiments/image_bakeoff/out/` (`s1_refs.png`, `s1_plates.png`, `s1_scenes.png`, `s1_poses.png`, `s1_poses2.png`, `s1_compose.png`).
- Only one story and two characters; one seed per edit.

## 7. SDXL base 1.0 + IP-Adapter Plus (stage 2)

Downloads: SDXL fp16 components 7.0 GB and IP-Adapter Plus (ViT-H) with its 2.5 GB image encoder, 10.3 GB in total, 2 h 55 min. Official weights (fp16, safetensors). 30 steps, CFG 6, 1024², negative prompt "text, lettering, watermark, …". Files: `experiments/image_bakeoff/sdxl_suite.py`, outputs in `out/sdxl_*`, sheets `s3_sdxl_*.png`.

### Does it run, and what does quantising first change?

| Configuration | GPU | RAM peak | Time per image | Result |
|---|---|---|---|---|
| fp16 + IP-Adapter encoder, everything on the GPU | 7.3 GiB at load | – | – | **Out of memory** |
| fp16, model CPU offload (plain) | 6.0 GiB PyTorch peak, 7.6 GB board | 11.0 GiB | 30.6 s | works, but it reached the 11 GB RAM cap |
| fp16, model CPU offload, IP-Adapter | ≈6 GiB | **12.2 GiB** (killed at an 11 GB cap; ran with 12.5 GB) | 31.6 s | works only with a larger cap, too heavy for 16 GB machines |
| **UNet quantised to NF4 (bitsandbytes), no offload** | 3.6 GiB loaded (UNet 1.66 GiB), 6.6 GiB peak, 7.6 GB board | **6.0 GiB** | 30 s | works; output is near-identical to fp16 for the same seeds |
| UNet quantised to int8 | 4.7 GiB loaded | 5.9 GiB | – | **Out of memory** during decoding |
| NF4 UNet + IP-Adapter | – | – | – | **fails to load** (diffusers refuses to cast a quantised UNet when adding the adapter) |

So the user's idea of quantising first works: it removes the CPU offload and cuts RAM from 11 GiB to 6 GiB at the same speed. Practical details: the quantised pipeline needs the VAE decoded in fp32 by hand (the fp16 upcast path fails after the first image). Quantising does not shorten the download, and it cannot be combined with IP-Adapter in this diffusers version.

### Quality (my view)

- **SDXL's text encoders read only 77 tokens**, so the long prompts used for klein were truncated and the character details were lost (sheet `s2_*`). Compact prompts (55–68 tokens) were needed.
- **Even with compact prompts SDXL follows the prompt less well than klein:** backgrounds were not plain, the "flat cut-paper" style came out as a general flat illustration, the Arcania plates were attractive but lacked the floating islands and crystals, and the page-4 scenes lacked the glowing lattice. Characters carry a staff taller than the child instead of a small stick.
- **IP-Adapter keeps identity but not pose.** From one reference it produced the same face, hair and outfit in all nine images, but also copied the reference's pose and background: "sitting" and "walking" came out standing, the raised stick and a wave worked only partly. Pose control would need ControlNet, which was not tested.
- **Speed:** SDXL needs about 30 s per image against 9.9 s for klein (text-to-image) and 19.5 s for a klein edit that actually changes the pose.

### Critic on the SDXL images

Refs (6 images, compact prompts): 1 of 30 true values rejected (held item), 0 of 30 wrong values accepted. IP-Adapter poses (9 images): 3 of 45 true values rejected (a hood, two held items), 0 of 45 wrong values accepted. Reference comparison: 1 hood difference flagged in 8 pairs; the others "all same", which is accurate because IP-Adapter reproduces the reference closely.

### Conclusion of stages 1–2

For this project klein is the better backend on this hardware: 3× faster, much better prompt adherence, real editing (pose change, repair, multi-reference composition) and one model for every task. SDXL's remaining advantages (LoRAs, ControlNet, ecosystem) were not tested and are not needed unless klein's style or licence becomes a problem. If SDXL is ever used, quantise the UNet to NF4 and use compact prompts.
