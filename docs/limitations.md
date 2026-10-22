# Known limitations (state of Phase 1, 2026-10-11)

What the command-line pipeline cannot do yet, with the evidence. Numbers come from [research/page-defects.md](research/page-defects.md) and [research/phase1-results.md](research/phase1-results.md). Decided with the user on 2026-10-11 to accept these for now and move on to the app.

## Picture quality
| Limitation | Evidence | What the product does about it |
|---|---|---|
| **Extra or merged hands and legs, second copies of a character, a character missing from a page, features leaking between characters** (a girl with bear ears) can still happen | no model, local or frontier, detects extra hands (0 of 3 on Gemma 4 E4B and on Qwen3.5-4B; 2026 benchmarks: zero-shot detection AUC 0.23-0.38 for GPT-4o, Claude Sonnet 4.6, Qwen3.5-Plus 397B) | A human reviews every page at full size; **Redraw** gives the page a new seed (`regen.py`, about 30-45 s). Random mistakes usually vanish (extra hand: 1 of 54 renders), but pages with 3-4 characters needed 3-5 redraws in Goldilocks |
| **Pages with 3-4 characters are the weakest** | each reference picture is shrunk (448 px with four characters) to fit the 8 GB card (6.9 GiB peak measured); bear count was 3-5 instead of 3 in most tries | Species and "never mix features" are named in the prompt (helped); further fixes not done: cap at 3 characters, split large groups, higher-resolution references on a bigger GPU |
| **The image model ignores some story events** | Mira p4: the kite string never snaps in 6 of 7 renders; Boat: the grandfather stands on the water on two pages | Listed as a computer note ("page may not show ...") when Gemma notices (57% of missing events); otherwise the reviewer redraws. Rewording the story into "what the eye sees" was **rejected** because it may change the style a parent wants |
| **Objects can appear before the story introduces them** (Fox: the lantern is carried on page 1, found on page 3) | observed in the re-run | none yet |
| Fine details such as a second fishing rod, floating, hair style are caught only partly | Gemma 4 E4B: duplicate figure 75% (when it must list every figure), floating 90% with 14-20% false alarms, duplicate object 70%, hair style 75% (4 cases), missing event 57%; small test set (3-10 positives per type) | notes only, never an automatic action |
| The automatic repair edit often makes pages worse | in 6 tries 1 improved the page, so repairs are kept only when the critic then finds fewer mismatches | built in |

## Found by the story battery (2026-10-11, [research/story-battery.md](research/story-battery.md))
- **Reflections** (dog in the stream, girl in the mirror) are now planned as a page effect, not a character, and mostly come out as a mirror image (fixed 2026-10-11, see the story battery). Remaining: a sentence that talks to the reflection can still make the model draw a second real figure (dog page 3), and a reflection that acts on its own is drawn as an ordinary mirror image. **Doubles that are not reflections** (twins, a doppelganger) are still ordinary characters.
- **Extreme size differences** (mouse and lion) are lost: the plan only knows short/average/tall and the references are drawn at one scale.
- **Several rooms of one house look alike** unless the planner names them as different places; stories with unusual rooms (cellar, attic) can end up in one hall.
- **Adults can be drawn as children** in the crayon style even when the plan says adult.
- **Small unplanned figures and props** (a sleeping boy, a knife-like object) can appear; the computer's notes catch some, not all.

**Redraw does not fix these (measured):** in a 39-redraw experiment on 13 flagged pages, 11 defects came back in all three redraws and only 2 were random ([research/story-battery.md](research/story-battery.md)). Reflections (before the fix), extreme size ratios, objects that must end up in a particular place (a blanket over a mirror) and unplanned extra characters are systematic; hands, a stray prop and a lingering object were the random ones.

## Planning
- The planner (Gemma 4 E4B) can mis-assign a place, drop a character from a page, or invent a visual detail; `inferred_fields` is computed by code, not trusted from the model. A story with no named characters or one sentence has not been tried.
- Page count is fixed by code (default 6, up to 10 with `--pages`); there is no adaptive page count and no parent approval step for the character references yet.
- Dates in spoken stories, names the speech model mishears, and non-English or noisy speech are untested (only synthetic speech and 14 user clips were used for the speech bake-off).

## Machine and speed
- One 8 GB GPU: one model at a time, so a book takes 6-9 minutes (Goldilocks with 8 pages: 14.7 minutes) and each redraw about 30-45 s plus model loading.
- Downloads are slow (about 1 MB/s here); a first run needs about 20 GB of models.
- Qwen3.5 and larger vision models were evaluated as page checkers and did not help ([research/page-defects.md](research/page-defects.md), section 8).

## The app (thin slice)
- Only one job at a time: while a book is being made no other book or redraw can run (one GPU); a second request is refused with a message.
- Moving a book folder **out of** the library folder removes it from the library (moving it back restores it); a changed library folder takes effect after the app is restarted.
- A job survives leaving its screen but not closing the app: the book then shows as "interrupted" with Try again (a stage restarts from the beginning; finished pictures of an earlier attempt are reused only by redraw, not by Try again).
- The app starts the sidecar from the repository's `sidecar/.venv` and the scripts from `scripts/` (development layout); packaging for other machines is open. The `llama` binary and the models are found in `~/.local/bin` and `~/models`; there is no first-run check yet.
- Audio import accepts wav, mp3, m4a, flac and ogg; only wav and mp3 were exercised with the speech model.

## Approval flow (second milestone)
- Characters and places can be edited **before** the pages are drawn only; after that the screen is read-only (to try other looks, make a new book).
- Unsaved edits are protected by the Save / Discard banner and the disabled buttons, not by a prompt when leaving the screen: leaving without saving loses them.
- "Draw again" gives new random pictures, there is no way to keep an earlier candidate; the chosen picture is the critic's pick of two.
- Pages and names of the plan are not editable (names are used in the page layout), and a place or character cannot be added or removed by hand.
- The first-run check only reads the machine; downloading missing models is still done by hand with the command it shows.

## Recording
- English only, 15 minutes at most, one take (Pause/Continue exists but there is no editing or trimming).
- The recording is kept in memory until "Use this recording"; if the app is closed before that, it is lost.
- A real voice recording was not tested end to end (see the verification log); the path was tested with a prepared speech file.
- The microphone choice is the system default; there is no device picker.
- The recording is deleted after transcription by default; with the setting off the audio stays in the book folder.

## Found by the code review (2026-10-12, [research/verification-log.md](research/verification-log.md) 5i)
- After a full reload of the window the live progress of a running job is not shown (the job keeps running; the result appears when it ends).
- The library is rescanned for every command; fine for dozens of books, slow for hundreds.
- The picture cache in the window holds 160 pictures; after that an old picture can be dropped while still on screen (it reloads on the next visit).
- The language model server uses a fixed port (18090); a stale server from a crash could clash until it is stopped.
- Changing the library folder in Settings needs an app restart.

## Not built yet
Packaging of the Python sidecar, first-run checks, PDF layout options (page size, text inside the picture), read-aloud, character library reuse across books, per-page text editing.

## Ideas that could remove limitations (not decided)
Layered rendering (one character per picture, cut out and composited: no second copy or merged limbs by construction), a fine-tuned small VLM on AGIDefect-4K (published AUC 0.65), a "character missing from page" note, a 3-character cap.
