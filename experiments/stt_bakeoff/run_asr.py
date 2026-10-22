"""Dedicated ASR engines on the same clips as run_gemma.py.
usage: python3 run_asr.py --engine parakeet|whisper --set synth|user
Parakeet: onnx-asr (ONNX int8 on the CPU: the installed onnxruntime has no GPU provider). Whisper large-v3-turbo: transformers pipeline, fp16 on the GPU.
Results for the user's clips are written outside the repo (private)."""
import argparse, glob, json, os, resource, subprocess, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".deps"))
import soundfile as sf
import stt_common as S
ap = argparse.ArgumentParser(); ap.add_argument("--engine", required=True); ap.add_argument("--set", default="synth"); ap.add_argument("--limit", type=int, default=0); a = ap.parse_args()
hub = os.path.expanduser("~/.cache/huggingface/hub")
peak = {"vram": 0, "stop": False}
def sampler():
    while not peak["stop"]:
        try: peak["vram"] = max(peak["vram"], int(subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5).stdout.split()[0]))
        except Exception: pass
        time.sleep(0.5)
threading.Thread(target=sampler, daemon=True).start()
t0 = time.time()
if a.engine == "parakeet":
    import onnx_asr
    d = glob.glob(f"{hub}/models--istupakov--parakeet-tdt-0.6b-v3-onnx/snapshots/*")[0]
    model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3", path=d, quantization="int8")
    def transcribe(p): return model.recognize(p)
elif a.engine == "whisper":
    import torch
    from transformers import pipeline
    d = glob.glob(f"{hub}/models--openai--whisper-large-v3-turbo/snapshots/*")[0]
    pipe = pipeline("automatic-speech-recognition", model=d, dtype=torch.float16, device="cuda")
    def transcribe(p):
        x, sr = sf.read(p, dtype="float32")
        return pipe({"raw": x, "sampling_rate": sr}, chunk_length_s=30, generate_kwargs={"language": "en", "task": "transcribe"})["text"]
load_s = time.time() - t0
cl = S.clips(a.set); cl = cl[:a.limit] if a.limit else cl
transcribe(cl[0])   # warm-up (not recorded)
outdir = os.path.join(S.HERE, "results") if a.set == "synth" else os.path.join(S.AUD, "private_results"); os.makedirs(outdir, exist_ok=True)
out = open(os.path.join(outdir, f"{a.engine}_{a.set}.jsonl"), "w")
for p in cl:
    dur = sf.info(p).duration; t = time.time()
    try: txt, err = transcribe(p), None
    except Exception as e: txt, err = "", repr(e)[:300]
    rec = {"clip": os.path.basename(p), "duration": dur, "seconds": time.time() - t, "text": (txt or "").strip(), "error": err}
    out.write(json.dumps(rec) + "\n"); out.flush()
    if a.set == "synth": print(rec["clip"], f"{rec['seconds']:.2f}s", repr(rec["text"][:70]), flush=True)
peak["stop"] = True
print(json.dumps({"engine": a.engine, "set": a.set, "load_seconds": round(load_s, 1), "peak_vram_mib": peak["vram"], "peak_rss_gib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576, 2), "clips": len(cl)}))
