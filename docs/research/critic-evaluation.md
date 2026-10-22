# Critic evaluation (spike 0.3, first full run)

Question: can a small local vision model (Gemma 4 on `llama serve`) reliably say whether a generated image matches the character spec (is the hood red? are there glasses?), so that the pipeline can accept, repair or flag pages automatically? Run on 2026-10-09 on the dev machine (RTX A2000 8 GB). Raw data, images and scripts are in [`experiments/critic_eval/`](../../experiments/critic_eval/README.md) (rerun instructions there); the generator, runner and analysis are small enough to move into `sidecar/tests/critic_eval/` in Phase 1.

## 1. Where the images come from (and what was wrong with the first set)

- **All images are synthetic.** I wrote a Python/PIL generator that draws cartoon characters (robe, hair, optional hood or pointed hat, optional round glasses, optional stick or basket, flat backgrounds with distractor objects such as balloons, flowers and houses in confusable colours) and records the ground truth of every attribute in a manifest. Nothing was downloaded and no image model was used.
- **An earlier smoke test used two throw-away images** (same figure, hood red vs blue). It only proved that image + JSON schema works end to end. It is not evidence of accuracy and is not part of these results.
- **Set v1 (40 images) was flawed.** Looking at the errors showed that hair was hidden under hoods or looked like a hood, and glasses were tiny on small characters. The labels were therefore not always visible in the image. v1 results are kept below only to show the effect; **all conclusions use set v2**.
- **Set v2 (40 images, 512×512):** hood drawn as a cloth shell behind the face with the hair fringe visible, four hair styles (short, bun, long, ponytail), hat and hood colours never equal to the hair colour, larger characters. Coverage: 7 robe colours (5–6 each), 5 hair colours (8 each), headwear none/hood/pointed hat (14/14/12), glasses 19 of 40, held item none/stick/basket (13/14/13), 12 images with two characters (the second wears a colour confusable with the target's), sizes small/medium/large (14/13/13), 6 blurred and 5 noisy images.
- **Honest limitation:** flat synthetic drawings are easier than AI-generated storybook art in some ways (clean flat colours) and harder in others (crude shapes, ambiguous hair/hood). The real test comes with images from the real image models (image bake-off).

## 2. Protocol

- Each image is tested with three checklists of five attributes (robe colour, hair colour, headwear, eyewear, held item), the model answering in JSON constrained by a schema (`observed` is written before `match`): **A** all five expected values true; **B** three attributes replaced by a plausible wrong value (nearest confusable colour, a different headwear, glasses claimed when there are none, …); **C** the other two replaced. So every (image, attribute) is asked once with the true value and once with a wrong value: 600 checks per condition (400 true, 200 wrong).
- "Mismatch recall" = wrong values correctly rejected. "False alarm" = correct values wrongly rejected. 95% Wilson intervals in brackets.
- Server flags copied from the user's `~/run_goose.sh`: `-np 1 -fa on`, q8_0 KV cache, top-p 0.95, top-k 20, `--repeat-penalty 1.1 --repeat-last-n 256`, `--jinja`, `--reasoning-budget 2048`; critic requests at temperature 0, `max_tokens` 700 (thinking off) or 8192 (thinking on).

## 3. Results (set v2 unless marked)

| Condition | Accuracy | Mismatch recall | False alarms | Latency / call | Robe, hair, headwear, eyewear, held item: recall / false alarm (%) |
|---|---|---|---|---|---|
| v1 set, E2B, default image tokens (flawed set) | 83.7% (80–86) | 87.0% (82–91) | 18.0% (15–22) | 3.2 s | 100/0, 90/56, 72/12, 72/18, 100/4 |
| E2B, default image tokens, thinking off | 88.2% (85–91) | 88.5% (83–92) | 12.0% (9–16) | 3.2 s | 100/2, 88/42, 78/6, 78/5, 100/4 |
| E2B, default image tokens, **thinking on** (budget 2048) | 86.8% (84–89) | 79.5% (73–85) | 9.5% (7–13) | 9.0 s | 98/1, 57/30, 80/6, 68/6, 95/4 |
| E2B, **image tokens 1120**, thinking off | 91.8% (89–94) | 94.0% (90–97) | 9.2% (7–12) | 3.6 s | 100/0, 98/24, 88/9, 85/0, 100/14 |
| E4B, default image tokens, thinking off | 88.0% (85–90) | 92.0% (87–95) | 14.0% (11–18) | 5.3 s | 98/0, 90/40, 95/11, 78/12, 100/6 |
| **E4B, image tokens 1120, thinking off** | **94.7% (93–96)** | **99.0% (96–100)** | **7.5% (5–11)** | 5.8 s | 100/0, 98/19, 98/6, 100/0, 100/12 |

Not run: E4B with thinking on (E2B showed no benefit and the run would take about 30 minutes), E2B reference-vs-candidate pairs.

### Findings

1. **The image token budget matters more than the model size.** With the default (about 140 tokens for a 512 px image) E2B and E4B are equally mediocre (88%). Forcing `--image-min-tokens 1120 --image-max-tokens 1120` raised E2B to 91.8% and E4B to 94.7%, at a cost of about 1000 extra prompt tokens and 0.4–0.5 s. Glasses and hoods were the main beneficiaries.
2. **E4B with 1120 image tokens is the best critic tested** and meets the proposed bar (mismatch recall ≥ 90%, false alarms ≤ 10% overall) with recall of 97.5–100% on every hard field. It misses the bar on **false alarms for hair colour (19%)** and for the held item (12%).
3. **Remaining errors are partly ambiguity, not just model weakness.** Held-item false alarms are mostly background flowers close to the hand ("holding flowers"). Hair false alarms are colour-naming fuzz ("red" vs "orange", "blonde" vs "brown", "grey" vs "dark") and hair judged "not visible" under hoods. Absolute colour naming of hair or skin is unreliable; flat clothing colours are not (robe colour: 100% recall, ≤ 2% false alarms in every configuration).
4. **Thinking does not help the critic.** With budget 2048 and `max_tokens` 8192 every one of the 120 calls finished normally (`finish_reason: stop`, valid JSON, reasoning about 1,600 characters on average, never near the budget), so structured output **works with thinking on**. But accuracy did not improve (mismatch recall fell from 88.5% to 79.5%, false alarms fell from 12% to 9.5%) and latency was 2.8× higher (9.0 s vs 3.2 s). Combining the two runs (flag only if both say mismatch, or if either does) just trades recall for false alarms without beating the image-token fix.
5. **Confidence is informative once renormalised** over the two allowed answers (see architecture.md, section 12). For E4B at 1120 tokens, answers with confidence ≥ 0.99 were wrong 4% of the time versus 20–32% below that. Policy "flag a mismatch only when confidence ≥ 0.99": 94% recall, 6% false alarms; "≥ 0.9": 97% recall, 7.2% false alarms. Low-confidence answers should go to a second pass or to the parent.
6. **Reference-vs-candidate comparison (E4B, 1120 tokens, 20 base characters × 6 candidates = 600 comparisons):** drift recall **87%** (100 changed attributes), false alarms **2.8%** (1% on control pairs where only background and position changed). Robe colour, headwear and held item drift were caught 100%, hair colour only 65% and glasses removal 70%. In the missed glasses cases the model reported "round glasses" for the candidate that had none, an anchoring effect from the reference image. Comparison mode therefore has far fewer false alarms than checking against the written spec, but misses small removals; the two modes are complementary.

### What this means for the design

- Default critic: **Gemma 4 E4B with the vision projector at 1120 image tokens, thinking off, temperature 0**; E2B at 1120 tokens is the fallback when VRAM is tight (E2B at 1120: 3.1 GB VRAM measured; E4B at 1120 not measured). Both need the image budget flags, which were not in the first draft of the docs.
- Check **fields that are easy to see** (clothing colour and type, headwear, glasses, held item, species) as hard; treat **hair and skin colour** as soft, or compare to the reference image instead of naming a colour.
- Route low-confidence answers (< 0.99 after renormalising) to a second pass (the pair comparison against the reference) or to the parent instead of auto-rejecting.
- Distractor objects near hands and the same colour as the character are the main cause of false alarms in the synthetic set; expect similar issues in generated art and keep prompts for backgrounds simple.

### Caveats

- Synthetic images, one generator style, 40 base images, temperature 0, one run per condition: the intervals above are wide (roughly ±4–6 points per overall metric, wider per attribute with n = 40/80).
- The acceptance bar was proposed by me and is for the user to confirm.
- Re-run on the images produced by the real image models before trusting these numbers for the product.
