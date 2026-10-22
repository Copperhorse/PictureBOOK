# Speech-to-text bake-off (English)

Run on 2026-10-11 on the dev machine. Scripts and results: [`experiments/stt_bakeoff/`](../../experiments/stt_bakeoff/README.md). Engines tested: Parakeet TDT 0.6B v3 (ONNX int8, `onnx-asr`, CPU), Whisper large-v3-turbo (transformers, fp16, GPU), Gemma 4 E4B and E2B audio input (through `llama serve`, 1120-token vision budget irrelevant here). Qwen3-ASR was not tested (the user chose not to download it; 0.9 MB/s connection).

## 1. Test audio and its limits

- **Synthetic set (exact references):** 8 short story passages (8–13 s each, with names such as Arcania, Biscuit, Willowbrook, Lina, Zed) spoken by the Kyutai pocket-tts model (one voice), then degraded into 6 conditions: clean, 1.3× speed, phone band (300–3400 Hz at 8 kHz), reverb, white noise at 10 dB SNR and at 0 dB. 48 clips.
- **User clips (no references):** 14 clips supplied by the user from their Downloads folder: 13 short-to-medium TTS-style character voices (some with stylised baby-talk pronunciation such as "w" for "r"/"l") and one real voice note. Three further clips were excluded because their content is explicit and unsuitable for this project. The audio and all transcripts of these clips stay **outside the repository**; only aggregate numbers are reported here. Without references only disagreement between engines can be measured, plus a human look at the short benign clips.
- **Limits:** synthetic speech from one voice is easy and not representative of real parents and children; the real-voice material is one voice note. Treat the numbers as a first filter, not as accuracy for the product. Recordings of the intended users in the intended rooms are still needed.

## 2. Results on the synthetic set

WER in % (key proper nouns found / 9 in brackets); RTF = processing time / audio time.

| Engine | clean | 1.3× speed | phone | reverb | noise 10 dB | noise 0 dB | all | RTF | Resources |
|---|---|---|---|---|---|---|---|---|---|
| **Whisper large-v3-turbo** (GPU, fp16) | 0.8 (8) | 0.4 (8) | 1.1 (8) | 0.8 (8) | 0.4 (8) | **8.0** (5) | **1.9** | 0.06 | 2.1 GB VRAM, 2.6 GiB RAM, 1.6 GB download |
| Parakeet TDT 0.6B v3 (ONNX int8, **CPU**) | 1.9 (9) | 1.5 (9) | 1.9 (9) | 2.7 (7) | 1.9 (8) | 13.4 (4) | 3.9 | 0.10 | **0 VRAM**, 1.3–1.5 GiB RAM, 0.7 GB download |
| Gemma 4 E4B audio | **0.4** (8) | 1.1 (8) | 0.8 (8) | 1.1 (7) | 2.7 (7) | 28.7 (4) | 5.8 | 0.12 | llama server, 4.5 GB VRAM |
| Gemma 4 E2B audio | 0.4 (8) | 1.9 (8) | 0.4 (8) | 1.5 (7) | 3.1 (6) | 33.3 (4) | 6.8 | 0.07 | llama server, 3.1 GB VRAM |

- All engines are essentially perfect on clean synthetic speech; differences appear with noise and in robustness.
- **Sentence boundaries** (needed to split the story into pages): the difference in sentence count against the reference was 0.00 for Parakeet, −0.04 for Whisper, −0.10 for Gemma E4B and −0.12 for E2B, so all four punctuate usably; Gemma sometimes merges sentences.
- **Proper nouns** are the weak point of every engine ("Lina" heard as Nina, Amina, Lena; "Biscuit" as Biskit). The Review screen where the parent corrects the transcript is therefore essential, and a glossary or prompt-biasing option for names is worth trying (not tested).

## 3. What the user clips show (no references)

- Pairwise word disagreement between engines was 14.5–15.3% for Whisper vs Parakeet/Gemma E4B and 26% against Gemma E2B. The stylised baby-talk pronunciation makes these clips hard for everyone, and without references the disagreement cannot say who is right.
- On the **real voice note** all engines produced the right sentence, but **Parakeet transcribed the speaker's hesitations verbatim** ("could you uh could you s explain how f photosynthesis…"), whereas Whisper and Gemma returned a clean sentence. For storytelling, clean output is preferable; Parakeet output would need a filler/stutter clean-up step.
- **Gemma E2B answered a spoken question instead of transcribing it** on one clip (a clip containing "explain what photosynthesis is" came back as an explanation of photosynthesis). The audio content acts like an instruction. E4B did not do this on these clips but invented an introduction on another ("Hi, I'm …").
- A 34 s clip (over Gemma's documented short-audio comfort zone) produced output on all engines without errors; its quality was not checked because there is no reference.

## 4. Gemma 4 for audio: assessment

Attractive: the model is already on disk, one process could serve planning, vision critic and transcription, and on clean speech it was the most accurate (0.4% WER).
Against: under heavy noise it **fabricates fluent text** instead of failing (0 dB: "Under the severe rain, a narrow road near County Borders collapsed…" for a story about a whale), which is worse than a transcription error in a product that turns the text into pictures; the smaller E2B can follow the audio's content as an instruction; llama.cpp marks audio input experimental; it needs a 3–4.5 GB llama server running (VRAM that the image model needs later), and has no word timestamps. Verdict: not as the primary STT. It remains a possible fallback or a cleanup/second-opinion step when a dedicated engine is unavailable.

## 5. Decision

1. **Default: Whisper large-v3-turbo on the GPU** (best accuracy and noise robustness, clean output, 2.1 GB VRAM, about 0.5 s for a 9 s clip). It runs in the sequential scheduler before the LLM and image model.
2. **Fallback and low-resource mode: Parakeet TDT 0.6B v3 int8 on the CPU** (no VRAM, can run while the GPU is busy, 3.9% WER overall, best at proper nouns on clean audio, but verbatim fillers and weaker in 0 dB noise). Needs a filler clean-up step.
3. **Gemma 4 audio: not used for STT.**
4. Both chosen engines punctuate well enough to split sentences, so the planner can rely on sentence indices (class.md, "What code decides").

## 6. Not tested

Qwen3-ASR 0.6B/1.7B and other candidates (Cohere Transcribe, Granite Speech, Canary-Qwen); real children's and parents' voices, accents, long recordings (minutes), silence and breathing (Whisper is known to hallucinate on silence; add voice-activity detection and test), Whisper prompt biasing for character names, Parakeet on the GPU (the installed onnxruntime has no CUDA provider), streaming/live transcription.
