# Mock run: "The Seventh Prince of Arcania"

An illustrative walk-through of every structured output the pipeline would produce for one spoken story. **All values are invented by hand to show the shape of the data**; nothing here was produced by a model. The schemas are the ones in [class.md, section 3](../class.md#3-structured-json-specs).

Style prefix used in the prompts below (placeholder until a style is chosen): `flat storybook illustration, soft watercolour texture, clean outlines, muted gentle palette`.

## 0. Spoken input

> Once upon a time in a land not like ours, used to be the kingdom of mages. The mages were people capable of bending the laws of the nature to their will. And the most talented mage of them all in Arcania was the 7th prince. He was a timid boy with a small frame and stature, but his mind was like no other, capable of understanding complex structures in mere seconds and display his prowess with a small wooden stick. He was the pride of the kingdom.

## 1. Speech-to-text → `Transcript`

```json
{
  "text": "Once upon a time in a land not like ours, used to be the kingdom of mages. The mages were people capable of bending the laws of nature to their will. And the most talented mage of them all in Arcania was the seventh prince. He was a timid boy with a small frame and stature, but his mind was like no other, capable of understanding complex structures in mere seconds and display his prowess with a small wooden stick. He was the pride of the kingdom.",
  "segments": [
    {"start": 0.0,  "end": 7.4,  "text": "Once upon a time in a land not like ours, used to be the kingdom of mages."},
    {"start": 7.9,  "end": 14.8, "text": "The mages were people capable of bending the laws of nature to their will."},
    {"start": 15.3, "end": 22.0, "text": "And the most talented mage of them all in Arcania was the seventh prince."},
    {"start": 22.6, "end": 38.5, "text": "He was a timid boy with a small frame and stature, but his mind was like no other, capable of understanding complex structures in mere seconds and display his prowess with a small wooden stick."},
    {"start": 39.1, "end": 41.2, "text": "He was the pride of the kingdom."}
  ],
  "stt_backend": "parakeet-tdt-0.6b-v3",
  "duration_s": 41.2
}
```

The parent sees this on the Review screen and can fix mistakes (for example a misheard "Arcania") before any GPU time is spent. The audio is already deleted.

## 2. Planner call 1 — characters and environments

Prompt (abridged): system message describing each field, then the transcript. `response_format` is the JSON Schema generated from `PlanPart1` (pydantic), which llama.cpp turns into a grammar, so the reply always parses.

```json
{
  "title": "The Seventh Prince of Arcania",
  "characters": [
    {
      "name": "Seventh Prince",
      "species": "human",
      "age_group": "child",
      "build": "slight",
      "height_relative": "short",
      "hair": "short, dark brown, slightly messy",
      "headwear": "None",
      "eyewear": "None",
      "face": "None",
      "skin_colour": "pale",
      "outfit": [
        {"item": "robe", "colour": "deep blue", "detail": "long, gold trim, sleeves slightly too long"},
        {"item": "shirt", "colour": "white", "detail": "None"},
        {"item": "boots", "colour": "brown", "detail": "None"}
      ],
      "accessories": "small wooden stick held like a wand",
      "distinguishing_marks": "None",
      "inferred_fields": ["hair", "skin_colour", "outfit", "face", "eyewear"]
    },
    {
      "name": "Arcanian Mage",
      "species": "human",
      "age_group": "adult",
      "build": "average",
      "height_relative": "tall",
      "hair": "long silver, tied back",
      "headwear": "pointed hat, dark teal",
      "eyewear": "None",
      "face": "short grey beard",
      "skin_colour": "tan",
      "outfit": [
        {"item": "robe", "colour": "teal", "detail": "long, silver stars embroidered on the hem"},
        {"item": "boots", "colour": "black", "detail": "None"}
      ],
      "accessories": "carved staff",
      "distinguishing_marks": "None",
      "inferred_fields": ["species", "age_group", "build", "hair", "headwear", "face", "skin_colour", "outfit", "accessories"]
    }
  ],
  "environments": [
    {
      "name": "Arcania",
      "setting": "outdoor",
      "location": "hilltop kingdom of slender stone towers with small islands floating above",
      "time_of_day": "afternoon",
      "weather": "None",
      "season": "spring",
      "lighting": "soft golden sunlight",
      "mood": "wondrous",
      "palette": ["deep blue", "gold", "soft teal"],
      "key_objects": ["floating islands", "glowing crystal spires", "winding stone bridges"],
      "inferred_fields": ["location", "time_of_day", "season", "lighting", "palette", "key_objects"]
    },
    {
      "name": "Spell courtyard",
      "setting": "outdoor",
      "location": "round stone training courtyard ringed by tall arches",
      "time_of_day": "morning",
      "weather": "None",
      "season": "spring",
      "lighting": "soft morning light with faint glowing runes",
      "mood": "calm, a little awe",
      "palette": ["pale grey", "teal", "gold"],
      "key_objects": ["rune circle on the floor", "stone arches", "floating stone blocks"],
      "inferred_fields": ["setting", "location", "time_of_day", "season", "lighting", "palette", "key_objects"]
    }
  ]
}
```

What the planner had to decide that the speaker never said (the Review screen should highlight these so the parent can change them): the prince's hair, skin, robe colours and boots; the mage's whole appearance; the two locations' look. The speaker only stated: seventh prince, timid, boy, small frame and stature, small wooden stick, mages, kingdom of Arcania.

## 3. Planner calls 2…n — pages (one constrained call per page in the real pipeline)

Same model, new grammar. The names from call 1 are inserted as enums, so a page can only mention `"Seventh Prince"`, `"Arcanian Mage"`, `"Arcania"` or `"Spell courtyard"`:

```json
{ "environment": { "enum": ["Arcania", "Spell courtyard"] },
  "layout[].character": { "enum": ["Seventh Prince", "Arcanian Mage"] } }
```

```json
{
  "pages": [
    {
      "index": 1,
      "first_sentence": 1,
      "last_sentence": 1,
      "story_text": "Once upon a time in a land not like ours, used to be the kingdom of mages.",
      "scenario": "A sweeping view of the kingdom of Arcania: tall stone towers, glowing crystals and small islands floating in a golden sky.",
      "effects": [],
      "camera": "wide",
      "environment": "Arcania",
      "render_mode": "layered",
      "layout": []
    },
    {
      "index": 2,
      "first_sentence": 2,
      "last_sentence": 2,
      "story_text": "The mages were people capable of bending the laws of nature to their will.",
      "scenario": "A mage on a stone bridge raises both hands; a ribbon of water rises from the river below and spirals up into the air while flowers bloom along the bridge.",
      "effects": ["ribbon of water spiralling upward", "flowers blooming along the bridge"],
      "camera": "medium",
      "environment": "Arcania",
      "render_mode": "ref_compose",
      "layout": [
        {"character": "Arcanian Mage", "pose": "other", "pose_detail": "both arms raised, conjuring a spiral of water",
         "expression": "happy", "facing": "left", "position": "center", "depth": "mid"}
      ]
    },
    {
      "index": 3,
      "first_sentence": 3,
      "last_sentence": 3,
      "story_text": "And the most talented mage of them all in Arcania was the seventh prince.",
      "scenario": "In the courtyard the small prince stands at the edge of the rune circle, shoulders hunched and eyes lowered, while a tall mage stands far behind him.",
      "effects": [],
      "camera": "medium",
      "environment": "Spell courtyard",
      "render_mode": "layered",
      "layout": [
        {"character": "Seventh Prince", "pose": "standing", "pose_detail": "hands clasped in front, looking down",
         "expression": "shy", "facing": "front", "position": "left", "depth": "foreground"},
        {"character": "Arcanian Mage", "pose": "standing", "pose_detail": "None",
         "expression": "neutral", "facing": "left", "position": "right", "depth": "background"}
      ]
    },
    {
      "index": 4,
      "first_sentence": 4,
      "last_sentence": 4,
      "story_text": "He was a timid boy with a small frame and stature, but his mind was like no other, capable of understanding complex structures in mere seconds and display his prowess with a small wooden stick.",
      "scenario": "Close on the prince concentrating, the wooden stick raised; in front of him a glowing geometric lattice of light unfolds piece by piece and floating stone blocks line up.",
      "effects": ["glowing lattice of light unfolding", "floating stone blocks lining up"],
      "camera": "close-up",
      "environment": "Spell courtyard",
      "render_mode": "ref_compose",
      "layout": [
        {"character": "Seventh Prince", "pose": "holding_item", "pose_detail": "stick raised in his right hand, other hand open",
         "expression": "determined", "facing": "right", "position": "center", "depth": "foreground"}
      ]
    },
    {
      "index": 5,
      "first_sentence": 5,
      "last_sentence": 5,
      "story_text": "He was the pride of the kingdom.",
      "scenario": "The prince stands small and a little embarrassed in the middle of the square while mages on both sides smile and applaud.",
      "effects": [],
      "camera": "wide",
      "environment": "Arcania",
      "render_mode": "layered",
      "layout": [
        {"character": "Seventh Prince", "pose": "standing", "pose_detail": "None",
         "expression": "proud", "facing": "front", "position": "center", "depth": "foreground"},
        {"character": "Arcanian Mage", "pose": "standing", "pose_detail": "applauding",
         "expression": "happy", "facing": "right", "position": "left", "depth": "background"},
        {"character": "Arcanian Mage", "pose": "standing", "pose_detail": "applauding",
         "expression": "happy", "facing": "left", "position": "right", "depth": "background"}
      ]
    }
  ]
}
```

The speaker told only the opening of a story, so the plan illustrates exactly what was said. It does not invent a plot.

The planner writes only `first_sentence` / `last_sentence`; `story_text` is **copied by code** from those sentences of the transcript, so the book repeats the parent's words exactly. (An earlier live test with a 2B model paraphrased and even truncated the text when asked to write it.) Likewise `inferred_fields` is filled in by code, and `render_mode` is corrected by code if the planner chose `layered` for a page with effects.

pydantic then validates: 4–6 pages, every referenced name exists, `layout` count matches the characters in the `scenario`, `render_mode` is allowed.

## 4. Code builds the prompts (no LLM involved)

`render_descriptor` for the prince (fields equal to `None` are dropped; `build` and `height_relative` become adjectives):

```
Seventh Prince, a short, slight-build child human with short, dark brown, slightly messy hair, pale skin,
wearing a long deep blue robe with gold trim and sleeves slightly too long, a white shirt and brown boots,
holding a small wooden stick like a wand
```

Because `headwear` and `eyewear` are `None`, the negative prompt gets `hat, glasses`. The `Compositor` also reads `height_relative` (`short` for the prince, `tall` for the mage) to scale their cutouts against each other.

**First generation, the reference** (text-to-image, plain background; the prince, `standing / neutral / front`):

```
flat storybook illustration, soft watercolour texture, clean outlines, muted gentle palette.
Full-body character on a plain light background. <descriptor>. Standing, hands clasped in front,
neutral expression, facing the viewer.
negative: hat, glasses, background scenery, extra characters
```

**Derived pose** (edit of the reference; instruction built in code, one hop from the reference), for the happy/proud pose on page 5:

```
inputs: [prince reference asset]
instruction: Same character, now standing with a small proud smile, facing the viewer, plain light background.
Keep the face, hair, outfit colours and proportions unchanged.
```

**Environment plate** (Arcania, wide):

```
flat storybook illustration, soft watercolour texture, clean outlines, muted gentle palette.
Wide view of a hilltop kingdom of slender stone towers with small islands floating above; floating islands,
glowing crystal spires, winding stone bridges; afternoon, soft golden sunlight, wondrous mood;
palette deep blue, gold, soft teal. No people, no characters.
```

**Page 4 (`ref_compose`)**: inputs are the courtyard plate and the prince's reference asset; the instruction is built from `scenario`, `layout` and `effects`:

```
inputs: [Spell courtyard plate, Seventh Prince reference]
instruction: Close-up of the Seventh Prince from the second image standing in the first image's courtyard,
stick raised in his right hand, other hand open, determined expression, facing right.
In front of him a glowing lattice of light unfolds and floating stone blocks line up.
Keep the prince's appearance exactly as in his reference.
```

## 5. Assets and generations needed

| Item | Kind | Used by | Generation |
|---|---|---|---|
| Arcania, wide | plate | pages 1, 5; input to page 2 | 1 text-to-image (page 1 *is* this plate) |
| Spell courtyard, medium | plate | page 3; input to page 4 | 1 text-to-image |
| Seventh Prince, standing / neutral / front | reference cutout | page 3; input to pages 2, 4 | 1 text-to-image + 1 segmentation |
| Seventh Prince, standing / proud / front | cutout | page 5 | 1 **edit** of the reference + 1 segmentation |
| Arcanian Mage, standing / neutral / left | reference cutout | page 3; page 5 twice (one flipped); input to page 2 | 1 text-to-image + 1 segmentation |
| Page 2 | `ref_compose` (plate + mage reference + effects) | — | 1 edit/multi-reference |
| Page 4 | `ref_compose` (plate + prince reference + effects) | — | 1 edit/multi-reference |
| Pages 3 and 5 | compose from cached assets | — | 0 (CPU, seconds) |

Total: 8 image-model calls (4 text-to-image, 4 edit) plus 3 cheap segmentations for 5 pages. In a story this short, layering and caching save little; they pay off when the same characters and places recur on many pages, when one page needs a retry, or when a spec field is edited (only that character's derived assets are redone).

## 6. Critic output (once per asset, then per page)

The checklist is built from the spec. Example for the first prince asset, using the schema field order `attribute → expected → observed → match → confidence`:

```json
{
  "checks": [
    {"attribute": "species",             "expected": "human",            "observed": "human",              "match": true,  "confidence": 0.97, "hard": true},
    {"attribute": "build",               "expected": "slight",           "observed": "slight",             "match": true,  "confidence": 0.84, "hard": true},
    {"attribute": "hair",                "expected": "short dark brown", "observed": "short dark brown",   "match": true,  "confidence": 0.88, "hard": true},
    {"attribute": "headwear",            "expected": "None",             "observed": "None",               "match": true,  "confidence": 0.95, "hard": true},
    {"attribute": "eyewear",             "expected": "None",             "observed": "None",               "match": true,  "confidence": 0.96, "hard": true},
    {"attribute": "skin_colour",         "expected": "pale",             "observed": "pale",               "match": true,  "confidence": 0.90, "hard": true},
    {"attribute": "outfit[0].colour",    "expected": "deep blue",        "observed": "purple",             "match": false, "confidence": 0.58, "hard": true},
    {"attribute": "outfit[1].colour",    "expected": "white",            "observed": "white",              "match": true,  "confidence": 0.92, "hard": true},
    {"attribute": "accessories",         "expected": "small wooden stick","observed": "no stick visible",  "match": false, "confidence": 0.81, "hard": false}
  ],
  "same_character_as_reference": {"differences": [], "same": true}
}
```

One *hard* field failed (`outfit[0].colour`). The retry policy tries a **targeted edit first**, built from the failed check:

```
inputs: [prince reference asset (attempt 1)]
instruction: Change the robe colour from purple to deep blue. Keep everything else exactly the same.
```

The critic re-checks the edited asset; if `outfit[0].colour` now passes it is accepted. If not, the asset is regenerated with a new seed, and only then is the reference weight raised. The missing stick is a *soft* field and is only logged. The `confidence` values come from token probabilities of the `match` answer, so a low value (0.58 here) is also a signal to ask the parent when retries run out.

After composing page 3 the page-level check is smaller (setting, lighting, whether both characters are visible and in the right places, relative heights), because each character's fields were already verified on the asset.

## 7. What the parent sees

1. **Review story:** transcript, five page cards (text, scenario, effects, camera, render mode), and the two character cards and two place cards with fields editable. Fields the planner invented (listed in each spec's `inferred_fields`) are shown in a different tint with a one-click confirm.
2. **Generating:** an asset lane (plates, then character poses) followed by a page lane, with critic chips such as `robe: purple, expected deep blue — fixing with an edit`.
3. **Reader:** five pages; pages the critic could not verify carry a small warning badge.

## 8. What this mock run revealed about the schemas

All of these have been applied to [class.md](../class.md#3-structured-json-specs).

| # | Finding | Change applied |
|---|---|---|
| 1 | The most important trait ("small frame and stature") had no field | `CharacterSpec` gained `build` and `height_relative` (both hard); `height_relative` also drives relative cutout scale |
| 2 | No `shy` / `proud` / `determined` expression | Expression enum gained `shy`, `proud`, `determined`, `embarrassed` (used on pages 3, 5 and 4) |
| 3 | Establishing shots have no characters | `layout` may be `[]` (page 1) |
| 4 | Crowds need several copies of one character | A character may appear twice in `layout`; the same cutout is reused, flipped (page 5) |
| 5 | Magic effects belong to neither a character nor a plate | New always-present page field `effects`; pages with effects are never `layered` (pages 2 and 4 use `ref_compose`) |
| 6 | The planner invented most visual details | `inferred_fields` added as the last key of `CharacterSpec` and `EnvironmentSpec`; the Review screen highlights them |
| 7 | The story is only an opening | No change: the plan illustrates what was said and does not invent a plot; "continue the story" is a later idea |
| 8 | STT can mis-hear names such as "Arcania" | No change: the Review screen lets the parent correct the transcript first |
| 9 | Independent text-to-image generation of every pose risks identity drift | Poses are derived by **editing the reference** (architecture section 5.2); targeted edits repair failed hard fields before any regeneration |
