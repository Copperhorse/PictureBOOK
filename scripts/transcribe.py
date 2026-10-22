"""Stage 1: audio -> transcript.json with Whisper large-v3-turbo (GPU, fp16). usage: python3 transcribe.py <run_dir> <audio>"""
import os, sys, time
from common import Run, split_sentences, timed, require_ram
run = Run(sys.argv[1]); audio = sys.argv[2]
require_ram(5)
import soundfile as sf, torch
from transformers import pipeline
with timed(run, "stt_total"):
    t = time.time()
    import modelpaths
    d = modelpaths.hf_snapshot(modelpaths.WHISPER_REPO)
    if d is None: sys.exit(f"the speech model {modelpaths.WHISPER_REPO} is not downloaded (see the Setup screen)")
    pipe = pipeline("automatic-speech-recognition", model=d, dtype=torch.float16, device="cuda")
    x, sr = sf.read(audio, dtype="float32")
    if x.ndim > 1: x = x.mean(axis=1)
    load_s = time.time() - t; t = time.time()
    text = pipe({"raw": x, "sampling_rate": sr}, chunk_length_s=30, generate_kwargs={"language": "en", "task": "transcribe"})["text"].strip()
    run.save("transcript.json", {"text": text, "sentences": split_sentences(text), "duration_s": len(x) / sr, "engine": "whisper-large-v3-turbo", "audio": os.path.basename(audio)})
    run.log("stt_decode", time.time() - t, load_seconds=round(load_s, 1), audio_seconds=round(len(x) / sr, 1))
print(run.load("transcript.json")["sentences"])
from rules import story_problem
if (why := story_problem(run.load("transcript.json")["text"])): sys.exit(why)       # silence and noise become "Thank you." or ".": stop here, plainly
