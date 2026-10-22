# Thinking mode and planner tests

Run on 2026-10-09 with `llama serve` 0.4.1-dev, flags copied from the user's `~/run_goose.sh` (`-np 1 -fa on`, q8_0 KV cache, temperature 0.6, top-p 0.95, top-k 20, `--repeat-penalty 1.1 --repeat-last-n 256`, `--jinja`, `--reasoning-budget 2048`, `-lv 4`), context 16384, `max_tokens` 8192 for a whole plan (4096 / 3072 for the smaller calls). Scripts, test data and raw responses are in [`experiments/critic_eval/`](../../experiments/critic_eval/README.md). Companion document: [critic-evaluation.md](critic-evaluation.md).

## 1. Correction to the first conclusion

The first live tests said "disable thinking for every structured call". That was **wrong as stated**. Those runs used `max_tokens` of 500–900, so the unbounded reasoning of Gemma 4 consumed the whole budget and `content` came back empty or truncated. The actual behaviour, measured now:

| Test | Result |
|---|---|
| Critic, thinking on, budget 2048, `max_tokens` 8192, 120 calls (E2B) | 120/120 finished with `stop`, 120/120 valid JSON; reasoning about 1,600 characters on average (max 2,403, about 600 tokens), never near the budget |
| Planner, thinking on, 8192 tokens: whole plan in one call, 9 runs; per-page and per-part calls, 63 calls | 100% finished with `stop` and valid, schema-conforming JSON. The longest whole-plan call used 2,817 completion tokens including reasoning, so **a story with characters, environments and page scenarios fits in 8k tokens** as the user expected |
| Budget exhausted on purpose (`--reasoning-budget 64`), 8 calls | The server logs `budget exhausted, forcing end sequence`, cuts the thinking and **still returns valid JSON** (8/8). A too-small budget loses reasoning, not structure |
| `reasoning_content` | Returned in its own field; the grammar constrains the answer (`content`), not the thinking text |

So structured output works with thinking enabled; the real questions are cost and benefit.

## 2. Does thinking improve results?

**Critic (E2B, set v2, 600 checks per condition):** no. Thinking on gave mismatch recall 79.5% vs 88.5% off, false alarms 9.5% vs 12.0%, accuracy 86.8% vs 88.2%, at 9.0 s vs 3.2 s per call. See critic-evaluation.md.

**Planner (3 stories × repeats, E2B, repeat penalty 1.1, 9 runs per condition, each plan has 5 pages):**

| Condition | Latency (whole plan) | Completion tokens | Ranges cover all sentences | Dangling env / char refs per plan | Pages with empty layout | Characters named on a page but missing from its layout (per plan) | Effects on pages left `layered` (per plan) | Stated facts kept |
|---|---|---|---|---|---|---|---|---|
| single call, thinking off | 19 s | 1349 | 1/9 | 0.0 / 0.1 | 2.0 | 4.1 | 2.7 | 34/36 |
| single call, thinking on (budget 2048) | 33 s | 2387 | 5/9 | 0.3 / 0.4 | 0.9 | 1.0 | 1.3 | 34/36 |
| several calls, thinking off | 25 s | 1599 | 9/9 (fixed by code) | 0 / 0 (enum-restricted) | 0.7 | 1.0 | 4.7 | 34/36 |
| several calls, thinking on | 67 s | 4965 | 9/9 (fixed by code) | 0 / 0 | 0.4 | 0.9 | 2.0 | 33/36 |

Smaller side runs (6 runs per cell, only single-on and multi-off): repeat penalty 1.0 instead of 1.1 made no visible difference to JSON validity or rule violations (differences are within noise; `--repeat-penalty 1.1` does **not** break structured output). Gemma 4 E4B kept all stated facts (24/24 vs 22–23/24 for E2B, which twice gave the "small, slight" prince `build: average/tall`) and left fewer characters out of layouts, at 42 s (several calls, off) and 66 s (single call, on).

What the numbers say:

- **Every configuration still broke at least one rule in nearly every plan** (rules the grammar cannot express). Code-side enforcement is mandatory whichever way thinking is set.
- **A single call with thinking on can plan a whole story within 8k tokens** and follows the layout rule far better than without thinking (empty layouts 0.9 vs 2.0 pages, missing characters 1.0 vs 4.1). But it still produced dangling references in some plans (names are not enum-restricted in one call), its sentence ranges were wrong in 4 of 9 plans, and it is slower (33 s) than the several-call flow without thinking (25 s), which has none of those two problems by construction.
- **Several calls with thinking on cost 2.7× more time for a small gain** (empty layouts 0.4 vs 0.7, effects-on-layered 2.0 vs 4.7). Not worth it by default.
- **The model spams `effects`**: in the several-call flow 80–93% of pages got effects ("light flare", "light effect") and in every such page for E2B the model left `render_mode` at `layered` (42 of 42 in one condition), ignoring the written rule. A gate such as `has_effects: boolean` before the list, plus code that sets `render_mode` itself, is needed.

## 3. Decisions taken from the data

1. Structured calls use thinking **off by default** (fast, 25 s per story with E2B), because thinking buys little for the critic and little for the planner relative to its 2.7× cost. Thinking on stays available per call (with `--reasoning-budget 2048`, `max_tokens` 8192); whether it pays off for one call type, for example only the character and environment calls (not tested separately here), is left to spike 0.2 with more stories.
2. Planning stays **several constrained calls** (characters, environments, one call per page with name enums and code-fixed sentence ranges): it removes dangling references and range errors by construction. The single-call-with-thinking variant is kept as the fast path to benchmark later, not the default.
3. **Code decides** `render_mode`, `story_text`, `inferred_fields`, and checks layout vs named characters, as in [class.md, section 3](../class.md#what-code-decides-instead-of-the-llm). Add `has_effects` as a gate field.
4. Keep `--reasoning-budget` set explicitly (2048) on the server so a runaway thought cannot consume the answer; the cut-off is safe.
5. `--repeat-penalty 1.1` from the user's script is acceptable.

## 4. Caveats

- Only three short stories, 9 runs per condition (6 for the side runs); one planner prompt; sampling at temperature 0.6, so conclusions about small differences are weak. The strong results are the qualitative ones (valid JSON under thinking, budget cut-off safe, rules broken everywhere, multi-call removes dangling references).
- The "stated facts" checks are simple keyword predicates written by me.
- E4B planner results come from 6 runs per cell.
