# Page defects: what the pipeline missed, what can detect it, what prevents it (2026-10-11)

The four Phase 1 books (Arcania, Mira, Fox, Boat) were reviewed by the user and found to contain defects the spec-based page critic never saw. Page numbers below are **story pages** (the PDF counts the title page as page 1).

| Defect | Where | Why the critic missed it |
|---|---|---|
| Extra (third) hand | Arcania p3, Mira p1, p2 | the critic never counts anything |
| Three-legged duck | Boat p5 | same |
| Duplicate character (second hedgehog; floating head plus a second boy) | Fox p3, Boat p5 | same |
| Child sitting on open water | Boat p2 | no physical-plausibility check |
| Two fishing rods; two kites; the kite string never snaps | Boat, Mira | **root cause is in the plan**, see below |
| Hairstyle changed (ponytail) | Mira p4 | hair check only looked at colour |

All code, labels and raw results: [`experiments/page_defects/`](../../experiments/page_defects/).

## 1. Root cause found in the planner (fixed in code, not yet re-run end to end)
The planner listed carried objects ("red kite", "fishing rod") as `key_objects` of the **environment**, so the background plate already contained a kite in the sky (and a rod on the lake). Every page then showed that kite plus the one the character held, and the kite could never "snap" because it was painted into the background. Fixes in `scripts/plan.py` and `common.py`: carried objects are removed from environment `key_objects` by code (word overlap with every character's accessories, headwear, eyewear, outfit); the plate prompt says "no people, no characters, no animals, no kites or other carried objects"; each layout item has a `placement` (names a solid thing from the setting, against floating); each page has `must_show` (facts the picture must show, put into the render prompt); `CharacterSpec.hair_style` is an enum.

## 2. Labelled test set
20 existing pages and 28 fresh renders (7 flagged pages x 4 seeds), labelled from the user's report plus my own review at 700 px (so small details can be missed; ambiguous images are marked `uncertain` or `disputed` and excluded from the scores). Counts of positives are small: **3 extra-hand, 1 extra-leg, 6 duplicate-character, 7 floating, 7 duplicate-object, 4 missing-event, 3 hair-changed**. Treat every percentage below as indicative.

## 3. Gemma 4 E4B (current critic model) as page-defect detector
One constrained call per page (image budget 1120, thinking off), answers as enums; counts are compared with the same character's reference image. `analyze2.py`, results in `experiments/page_defects/results/v2_crops.jsonl`.

| Defect | Positives | Recall (full image) | False alarms | Recall with per-character crop | False alarms (crop) |
|---|---|---|---|---|---|
| Extra hand | 3 | 0% | 0% | 0% | 0% |
| Extra leg | 1 | 100% | 4% | 0% | 0% |
| Duplicate character | 6 | 17% | 5% | 17% | 5% |
| Floating / unsupported | 7 | 86% | 10% | 86% | 16% |
| Duplicate object | 7 | 71% | 0% | 71% | 0% |
| Missing event (`must_show`) | 4 | 75% | 0% | 75% | 0% |
| Hair style changed (enum vs reference) | 3 | 33% | 25% | 67% | 7% |

The model's own written evidence on the three-hand pages says "two arms, two hands", so the failure is in perception, not in the answer format. Thinking mode (v1 detector, 4 images) was about 2.5 minutes per image and was dropped. An earlier version of my probability extraction read the JSON key token instead of the value token, so v1 confidences were meaningless; v2 reads the value token.

## 4. Prevention at generation time (klein 4B NF4, same seeds)
| Variant | Result |
|---|---|
| Baseline (4 steps) | about half of the hard pages have at least one defect; defects follow the seed |
| "Each character has exactly two arms, two hands, two legs and appears exactly once" added to the prompt | almost no change (same seed gives nearly the same picture with the same defects) |
| One character at a time (plate + first character, then edit in the next) | **worse**: identity drifts (the boy became an old man in Boat p5, the hedgehog turned realistic), more duplicates |
| 8 steps instead of 4 | same compositions and same defects as 4 steps, twice the time; not adopted |

## 5. Stronger vision models: search results (sources: 2026 papers and model cards)
- **No model is good at this task zero-shot, closed or open.** AGIDefect-4K (ACM MM 2026, arXiv 2608.20713): zero-shot detection AUC 0.23-0.38 for nearly every model (Claude Sonnet 4.6 0.30, GPT-4o 0.31, Qwen3-VL-235B 0.29, Qwen3.5-Plus 397B 0.34), best Gemini 3.1 Pro 0.49 (0.5 is chance). AnomReason (arXiv 2510.10231): best open model Qwen2.5-VL-72B 0.46 SemAP; a LoRA-tuned 7B model 0.52.
- **Fine-tuning works, modestly:** AGIDA (Qwen3-VL-4B + LoRA on the public AGIDefect-4K, 3,200 training images) reaches AUC 0.65 (zero-shot 4B: 0.30). The data are photoreal, not children's crayon pictures.
- **Best small models for plain counting / hallucination (PRISM-VLM, arXiv 2609.27395, 42 compact VLMs):** counting axis Qwen3.5-9B 0.664, Qwen3.5-4B 0.646, Qwen3-VL-8B 0.618, Qwen3-VL-4B 0.585, **Gemma 4 E4B 0.548** (25th-27th of 42 overall). Qwen3.5 model card: CountBench 97.2 (9B), 96.3 (4B).
- **Ruled out for this machine (8 GB VRAM, about 7 GB free RAM):** Qwen3.6 and 3.8 vision models (27B and larger), Gemma 4 26B-A4B (16.9 GB) and 31B, Gemma 4 12B (7.1 GB plus context), Molmo2 (no llama.cpp support string in the installed binary). Purpose-built detectors (RichHF, LEGION, ImageDoctor): no confirmed released weights.
- Verified file sizes: Qwen3.5-4B Q4_K_M 2.74 GB + mmproj 0.67 GB; Qwen3.5-9B Q4_K_M 5.68 GB + mmproj 0.92 GB.

## 6. Regenerating (human-in-the-loop), measured
Decision (user, 2026-10-11): do not rely on automatic detection; the human looks at the pages and asks for a redraw of the wrong ones (`scripts/regen.py <run> 2,4`, old pictures kept, `--undo`). Evidence from 54 labelled renders of 7 flagged pages (8 seeds each, `labels_fresh*.json`):
- Random defects vanish on a new seed: extra hand 1 of 54 renders, duplicate figure 4 of 8 on one page and 0 elsewhere, hair change 3 of 15. Redraw cost about 30 s per page (45 s with two characters, 20 s with four at reduced size) plus load time.
- **Systematic** defects do not vanish: Boat p2 child on water 6 of 8 seeds, Mira p4 string never snapping 6 of 7, two kites 4 of 8. Cause was the plan, see section 1.
- **Pages with 3-4 characters stay wrong for several redraws.** Goldilocks (4 characters, 8 pages): pages 5, 6 and 8 each needed 3-5 redraws and I called two of them "fixed" from a thumbnail sheet; at full size the user found two Papa Bears, an extra leg, a bear ear on the girl, and a bear merged into a sofa. Lesson: judge a redraw at full size (`review_pages/`, `compare/`), never from the thumbnail sheet.
- **Feature mixing between references** (girl with bear ears, Mama Bear drawn as a girl, second Papa Bear) is the main failure of group pages. Naming each character's species and forbidding mixing in the prompt ("Image 3 is Papa Bear, a bear ... never mix features ...") fixed Goldilocks being asleep in the bed (4 of 4 tries vs 0 of 3) and gave her human ears (3 of 4 vs 0 of 4); it did **not** fix the bear count (3 to 5 bears in most tries). Four references at 448 px each on the 8 GB card (peak 6.9 GiB, measured) are the likely limit.

## 7. Re-run of the four stories with the planner fixes (`runs/v2_*`, first look from thumbnails)
- Mira: one kite per page, same braids on every page (hair style enum works), right places; **still wrong:** the string never snaps on p4 (the image model ignores "string is broken"), the fisherman does not hold up the kite on p5.
- Boat: child sits in the boat on pages 2-5 (was on water); **still wrong:** the grandfather stands/runs on the water on pages 1 and 4, two rods in the boy's hands on p4, the grandfather is missing on p5.
- Fox: second hedgehog gone; the lantern is carried on p1 before it is found on p3.
- Arcania: story reads clearly; hands not yet checked at full size.
Ideas not yet tried: state `must_show` as what the eye sees ("the kite is far away with no line to the girl"), list characters missing from a page as a hint, a 3-character cap or a split of large groups.

## 8. Decisions so far
- Do not rely on automatic detection of extra hands or legs. They are listed for review per book and are the main argument for **layered rendering** (one character per generation, cut out, composited) as the structural fix; spike 0.11/0.12 in the roadmap.
- Retry loop (new seed per failing page) only for defect types that pass the gate (about 80% recall, about 15% false alarms): floating, duplicate object, missing event and hair style are borderline on E4B; duplicate characters pending the Qwen3.5-4B test.
- Qwen3.5-4B tested as detector on the same 76 labelled pages (Q4_K_M + F16 projector, thinking off, same prompts, results in `experiments/page_defects/results/*_q35.jsonl`). **No gain, Gemma 4 E4B stays the page checker.**

| Defect | Positives | Gemma 4 E4B recall / false alarms | Qwen3.5-4B recall / false alarms |
|---|---|---|---|
| Extra hand, list every hand | 3 | 0% / 1% | 0% / 3% |
| Duplicate character, list every figure | 8 | 75% / 4% | 75% / 4% |
| Duplicate character, plain count | 8 | 12% / 6% | 12% / 7% |
| Floating character | 10 | 90% / 14-20% | 60-70% / 0-2% |
| Duplicate object | 10 | 70% / 0% | 80% / 6% |
| Hair style changed (crop) | 4 | 75% / 5% | 100% / 3% |
| Missing story event | 7 | 57% / 0% | **0%** / 4% |

It fails on extra hands exactly like Gemma and every model in the 2026 benchmarks, matches Gemma on duplicates (the "list every figure" prompt is what works, not the model), loses the missing-event check, and is better only on hair style (4 cases). The 9B was not downloaded because the 4B showed no gain. Extra hands and legs remain a job for the human reviewer. `PB_VLM=qwen35_4b` selects it in `scripts/common.py`.
