# Phase 1 results: command-line pipeline (2026-10-11)

One command turns a spoken story into a PDF: `python3 scripts/run_all.py scripts/demo/arcania.wav runs/<name>`. Each stage is its own process under a memory-capped systemd scope (`MemoryMax=11G`, no swap), so only one model is in memory at a time.

| Stage | Script | Model | Wall time |
|---|---|---|---|
| 1 transcribe | `transcribe.py` | Whisper large-v3-turbo (GPU) | 15 s |
| 2 plan | `plan.py` | Gemma 4 E4B, grammar-constrained calls | 42 s |
| 3 assets | `assets.py` | klein 4B NF4: 1 plate + 2 candidates per character | 60 s |
| 4 critic (assets) | `critic.py assets` | Gemma 4 E4B, 1120 image tokens | 32 s |
| 5 pages | `render.py render` | klein, `ref_compose` (plate + character references) | 179 s (about 31 s per page, 45 s with two characters) |
| 6 critic (pages) | `critic.py pages` | Gemma 4 E4B | 45 s |
| reference repair | `assets.py repair`, then `critic.py refs` | klein edit of a reference the critic found wrong (>= 0.99) | about 30 s + 18-33 s |
| page repair | `render.py repair`, then critic again | klein edit of a page; **kept only if the confident mismatches go down**, else the pre-repair page is restored | 31-50 s + 50-80 s |
| 7 export | `export.py` | PIL | 0.3 s |
| **Total** | | | **373 s (6.2 min)** for a 22.8 s story, 5 pages |

## What was tested (second round: four stories)
Four synthetic-speech stories of 20-24 s, each run end to end from the audio file: Arcania (prince and mage, 2 environments), Mira (girl with glasses and a kite, hilltop and river, a fisherman), Fox (fox with a scarf and a hedgehog, snow and cave, a lantern), Boat (grandfather and grandson in a boat, a fish and ducks). Stories are in `scripts/demo/*.txt`, outputs in `runs/<name>/` (`book.pdf`, `contact.png`, `checks/`, `timings.jsonl`). Total wall time per book **6-9 minutes** (366-517 s for the generate-and-check path, plus 1-3 minutes when a page repair ran).

| Story | Same characters on every page (my judgement from the contact sheets) | Main problems I saw |
|---|---|---|
| Arcania | Yes | Pages 1-2 show the mage, not the prince (faithful to the text) |
| Mira | Yes | The girl got a ponytail on page 4 (hair style is not checked); the fisherman has a cap on page 5 but none on page 4 |
| Fox | Yes | Two hedgehogs on page 3 (a duplicate of Bramble); animals are drawn dressed in clothes although the spec said none |
| Boat | Faces and clothes yes; **pages no** | Page 5 has a floating head of the boy plus a second boy; the boy sits on open water on page 2; the plate "Boat Interior" gives crowded, odd pages; page 1 shows the grandfather steering a wheel |

## Repair results
- **Reference repair works.** The mage's spear (spec: wand) was still a spear after the first template, "Change the held item from X to Y". The template "Remove the X completely. Instead the character holds Y in one hand." fixed it and the critic confirmed it. The same path ran on the Boat references (4 characters) and all four passed afterwards.
- **Page repair: 1 kept, 2 reverted, 0 harmful kept.** Mira page 4 (fisherman's cap) was fixed and kept. Mira page 5 and Boat page 5 did not improve, so the pre-repair pages were restored. In the first attempt, before the acceptance rule existed, a repair on Mira page 4 removed her glasses and gave her a fishing net; that is why the rule exists.
- The critic's page checks only see what is in the spec. It did **not** catch the duplicate hedgehog, the floating head, the ponytail or the girl on the water. A page-level check ("how many characters are visible, is anyone missing a body") is the obvious next addition.

## Bugs found and fixed while doing this
- Four or more 1024 px input images ran out of GPU memory (7.7 GB card). References are now shrunk (768 px for three images, 512 px for four) and the planner allows at most three characters per page, each once.
- `held_item` is a hard check on references only; on pages it is soft because what a character holds changes per page (the kite flies away). A character with no outfit is exempt from the outfit check.
- My first edit left the page critic silently checking nothing for one run (a comment swallowed the rest of a line). Found because the output said "no characters" on every page. Lesson: look at the output, not only the exit code.

## Not yet covered
Real parent recordings; non-English or noisy speech; styles other than crayon; resume after a failed stage (only `--resume-from-critic` exists); the composition problems above; planner choices that are poor for a picture (a plate called "Boat Interior" for a story that happens on a lake).
