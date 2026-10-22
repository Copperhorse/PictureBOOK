# Story battery, first batch (2026-10-11)

Five of the new test stories ([scripts/demo/README.md](../../scripts/demo/README.md)) were run from the typed text with `scripts/run_all.py`, no manual step, and every page was inspected at 700 px (2x2 sheets; the same size that revealed the extra hands earlier). Output: `runs/s_*`. Times 9-12 minutes per book (`inn_raven_rest` with 8 pages: 12.4 minutes). I did not redraw anything, so these are first drawings only.

| Story | Pages | Verdict | What went wrong (checked by eye) |
|---|---|---|---|
| Dog and reflection | 6 | **weak** | the reflection is drawn as a **second real dog** sitting on the bridge (pages 2-3), not as a reflection in the water; the dog still holds the bone on page 4 after "the bone dropped"; collar colour changes (red, none, blue, red); page 6 is a different art look (the plate for "Home" is much more saturated) |
| Attic mirror | 6 | **weak** | the reflection girl is drawn as a **separate real girl** in the room (pages 1, 3, 4), a second grey girl also appears inside a wall mirror (page 4); the blue-dress girl holds a small knife-like object on page 3 that is not in the story; the blanket lies on a chest, not over the mirror (page 6) |
| Lion and mouse | 6 | **weak** | the mouse is drawn **twice** on pages 1-2 (tiny on the paw and a clothed, human-sized one beside it); the size contrast is lost by page 5 (the mouse is as tall as the lion's chest); the lion stands upright with a bare human torso on pages 4-6. The hunter on page 3 is correct (the page text says hunters came) |
| Lighthouse ship | 6 | **good** | mood, fog, stairs and the crowd of faces work and the old man is consistent; the ship has a funnel instead of torn sails; on page 5 the waving faces are in a lighthouse window instead of the ship's portholes; only a couple of wet marks on the stairs, not one per step |
| Inn at Raven's Rest | 8 | **mixed** | the change from inn to ruin and the clothes stay right across 8 pages with 4 characters; but an **extra boy sleeps in a bed** (page 4), the candle ends up in a traveller's hand after the innkeeper blew it out (page 8), the rooms never differ (no cellar door, no separate bedrooms), and the three adults look like children although the plan says adult |

## What the computer's notes did (the same pictures)
- **Useful:** attic mirror page 4 "1 extra figure(s) that are not in the plan" (true), dog page 3 "Dog may be drawn 2 times" (true), inn "candle may be visible 2-4 times" (true on pages 1, 2 and 8), "Reflection Dog may be floating" (it was sitting on the bridge rails, partly true).
- **Noise:** "page may not show: ..." appeared on 18 of 35 pages, many of them wrong (for example lion page 5: the mouse is clearly gnawing the rope); outfit mismatches for a coat that is merely a different shade of the same colour; "6 extra figures" on inn page 4 counted portraits.
- **Missed:** the knife-like object (attic page 3), the second mouse (lion pages 1-2), the extra sleeping boy was counted only as noise, adults drawn as children, the bone still in the mouth.
- **Automatic repair:** tried on 6 pages, kept on 2 (lion page 6, inn page 1), reverted on 4. Same picture as before: repair edits rarely help.

## Patterns that explain most of it
1. **A personified reflection or double is a character, so it is drawn as a second real figure.** The planner lists "Reflection Dog" and "Reflection Girl" as characters (it must, to place them), and the image model draws what it is told: a second creature. Without a mirror-specific method this will always fail on stories about reflections or twins.
2. **Anthropomorphic scale.** The plan only has `height_relative` (short/average/tall). A mouse "short" next to a lion "tall" is not small enough; the model draws both as people-sized. Extreme size differences are not representable.
3. **Whole-character references lock the pose.** The mouse reference is a standing mouse in clothes, and every use of it is that figure; a tiny mouse on a paw is drawn separately and the two coexist.
4. **One plate per place, many different rooms.** The inn is one wooden hall for the dining room, the bedrooms and the hall.
5. **Things added from the prompt**: unplanned small figures (a sleeping boy), carried objects handed to the wrong character, and an object that is meant to disappear (the bone, the blanket's position) staying.

## Decisions and next steps (not decided yet)
Run the other 11 new stories, then count how many pages per book a human would redraw; try redraw on the worst pages here to see which defects are random and which systematic (these look systematic: reflections, scale, rooms). Ideas that would not reword the story: treat a "reflection" as a visual effect on the original character instead of a second character; add `very_short` scale hints (and a "tiny" word) to the prompt for extreme size ratios; make places per room by splitting a plate into rooms when a story names several.


## Redraw experiment (same day): 13 pages x 3 redraws = 39 redraws, every attempt inspected at 700 px
Each page has four drawings (the original and three redraws, `page_NN_v1..v3.png` plus the current one). Judgement is mine, from the images; the user is the final judge.

| Page | Defect in the original | Gone in a redraw? | After 3 redraws |
|---|---|---|---|
| Dog p2, p3 | reflection is a second real dog | **no, 0 of 3 each** (the second dog sits on the bridge or in the stream every time; page 2 shows a mirrored dog only in the water, plus the second dog) | systematic |
| Dog p4 | bone still in the mouth after "dropped" | **1 of 3** (the last redraw shows the bone falling into the stream) | random |
| Attic p1, p3, p4 | reflection girl as a separate real girl | **no, 0 of 9** (she is in the room or beside the mirror every time) | systematic |
| Attic p3 | knife-like object | yes: gone in all three redraws | random |
| Attic p6 | blanket not over the mirror | **no, 0 of 3** (the blanket lies on a chest, a chair or the floor; the mirror is never covered) | systematic |
| Lion p1 | mouse drawn twice | **no, 0 of 3** (still a tiny mouse plus a clothed human-sized mouse every time) | systematic |
| Lion p2, p5 | size contrast lost, lion with a human torso | **no, 0 of 6** | systematic |
| Inn p4 | extra sleeping boy | **no, 0 of 3** (a boy sleeps in a bed in every redraw) | systematic |
| Inn p8 | candle in a traveller's hand | **no, 0 of 3** (the candle is held by a traveller or by the innkeeper at his mouth, never clearly blown out); the third traveller is a girl or a boy depending on the draw | systematic |
| Lighthouse p5 | faces in a lighthouse window, not the ship | **no, 0 of 3** (and the ship gets smaller and farther away each time) | systematic |

**Result: 2 of the 13 page defects were random** (the knife, one of three bone redraws). **11 were systematic**: the same defect in all three redraws, so a human pressing Redraw would not have fixed them. This contradicts the earlier estimate from the first four stories (extra hands: 1 of 54 renders) because the defects found in this batch come from the planner and from the way the references are used, not from the random seed.

Added observations:
- Redrawing sometimes **changes other things**: the girl on dog p3 and the travellers on inn p8 change hair and dress between attempts (a blonde girl becomes a brunette, a boy becomes a girl).
- The reflection fix cannot be a redraw: it needs a different representation (reflection as an effect on the original character, not a character).
- Redraw is the right tool for hands, duplicates of the same character and similar slips (the earlier stories); it is the wrong tool for planning problems. The review screen should say so: after two redraws without improvement it should suggest "this may not be fixable by redrawing".


## The reflection fix (same day), measured
**Change (story-independent):** a reflection, shadow or mirror image is no longer a character. The planner is told so and each page gets `reflections: [{of, surface}]`; the page prompt says the reflection is a faint mirrored image in that surface, "not a second dog", with exactly one real character. A code guard (`rules.fold_reflections`) turns a reflection the model still lists as a character ("Reflection Dog", "Isla's Reflection") into that page effect when the owner can be recognised; an unrecognisable one is left alone. 4 new tests (31 script tests pass).

**Result, re-run from scratch (`runs/r_dog_reflection`, `r_attic_mirror`, `r_fox`), every page inspected at 700 px:**
| Story | Before | After |
|---|---|---|
| Dog and reflection | the reflection was a second real dog on pages 2, 3 and 5 (0 of 9 redraws fixed it) | the cast is one dog; **pages 2 and 5 show one dog with a faint upside-down reflection in the water**; page 4 shows the bone falling into the stream with a splash. **Page 3 still has a second dog on the bridge** (the sentence is "he barked at the dog in the water", so the model keeps drawing the other dog). Page 6 now matches the look of the others |
| Attic mirror | the reflection girl was a separate real girl on pages 1, 3 and 4; the blanket never covered the mirror; a knife-like object appeared | **one real girl on every page, her reflection stays inside the mirror** (page 4: the reflection grins with small teeth, page 5: a hand reaches out of the glass). **The blanket now covers the mirror on page 6.** Small flaws: page 1 shows the girl holding the mirror, page 2 shows a second faint figure in the mirror |
| Fox (regression, no reflections) | | plan has no `reflections`, same cast, same style; the lantern is now found on page 3 and carried only on page 4 (it was carried on page 1 before; this may be chance) |

Run times 6.4 to 7.8 minutes per book, as before. So **reflections were a planning problem, not a drawing problem**, and removing the second character fixed most of it. What remains: the model still draws the "other dog" when the sentence talks to it, and a reflection of a character the story lets act on its own (the attic girl who mouths words) is shown as a plain mirror image, not as an independent being.
