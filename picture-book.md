# Picture Book App: Project Brief

## Idea
A person tells a story out loud. The app turns their voice into text, then generates simple, colorful storybook-style pictures from the story. A second, optional model generates short music to go with the story.

Owner's original description: speech to text, a text-to-image model producing simple colored storybook pictures from the voice, and a music-generation model to make small stories "pop".

## Core flow
1. User records a story by voice.
2. Speech-to-text turns the audio into a transcript.
3. An LLM splits the story into pages and writes an image prompt for each page.
4. A text-to-image model generates one picture per page, in one consistent storybook style.
5. The app shows pages as a picture book (picture + story text).
6. Optional, later: generate short background music for the story.

## Constraints and known facts
- Developer's phone is an OPPO A16 (4 GB RAM, about 2 GB free storage, Android 11). Image generation will not run on it. Assume a cloud API or a self-hosted server for images.
- Speech-to-text may need to handle Urdu and English, including mixed speech (code-switching). Small on-device models are weak at this. Design the speech step as a swappable module.
- Developer is considering Flutter, Kotlin or Tauri for the app. Not decided. Keep model and API calls behind a clean interface so the UI framework can change.
- UI direction: muted grays and blacks, inspired by Nothing UI. Not required for the first prototype.

## Main technical risks
- Character consistency: the same character should look the same on every page. Try reference images or a fixed style/character description in every prompt, and test how well it works.
- Cost and latency per page for cloud image generation.
- If children are the users: moderate story text and generated images, and be careful with children's voice data and privacy.
- Music generation adds cost and quality risk. Licensing differs by model. Check before shipping.

## Suggested first version (suggestion, not a decision)
- Voice in, 4 to 6 illustrated pages out.
- No music, no editing, no accounts.
- Goal: find out whether the story-to-pictures loop is fun and whether the characters stay consistent.

## Open questions for the developer
- Which image model or API to use, and the budget per story?
- Target language(s) for stories: English, Urdu, both?
- Who are the users: children, parents, or general?
- Platform: Android only, or also web?
- Should pages be exportable (PDF, images)?

## Notes for Claude Code
- Start by building a working prototype of the pipeline with simple scripts before building any app UI.
- Ask the developer before choosing paid services.
- Keep each stage (speech, story splitting, image generation, music) as a separate module with a simple input and output.
