# Speech-to-text bake-off (2026-10-11)

Report: [`docs/research/stt-bakeoff.md`](../../docs/research/stt-bakeoff.md).

| File | Purpose |
|---|---|
| `texts.json` | Reference texts of the 8 synthetic passages |
| `stt_common.py` | Clip lists, text normalisation, WER, key-term recall, sentence counts |
| `download_models.py` | Parakeet TDT 0.6B v3 ONNX int8 (0.7 GB) and Whisper large-v3-turbo (1.6 GB) into the Hugging Face cache |
| `run_asr.py` | Runs `parakeet` (via `onnx-asr`, installed into the local `.deps/` folder, no change to the conda environment) or `whisper` (transformers pipeline, fp16, GPU) over a clip set |
| `run_gemma.py` | Gemma 4 audio through `llama serve` (start it with `../critic_eval/serve.sh`; audio is sent as `input_audio`) |
| `analyze_stt.py` | Scores WER by condition, key terms, sentence counts, and compares engines on the user clips without printing their content |
| `results/` | Raw transcripts of the **synthetic** set for all engines |

Audio is not stored here. The synthetic clips (generated with `pocket-tts generate`, then degraded: white noise at 10 and 0 dB SNR, `aecho` reverb, 300-3400 Hz phone band at 8 kHz, `atempo=1.3`) and the converted 16 kHz WAVs of the user's own clips live in a temporary scratchpad (`STT_AUDIO` environment variable, see `stt_common.py`), and the transcripts of the user's clips are kept outside the repo on purpose. Regenerate the synthetic set from `texts.json` with `pocket-tts generate --text ... --output-path ...` and the ffmpeg filters above.
