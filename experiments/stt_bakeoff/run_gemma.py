"""Gemma 4 audio transcription through llama serve (--mmproj has an audio encoder). usage: run_gemma.py --port 18080 --tag gemma_e4b --set synth"""
import argparse, base64, json, os, sys, time, urllib.request, soundfile as sf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stt_common as S
ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=18080); ap.add_argument("--tag", required=True); ap.add_argument("--set", default="synth"); ap.add_argument("--limit", type=int, default=0); a = ap.parse_args()
PROMPT = "Transcribe this audio exactly as spoken, with correct punctuation and capitalisation. Output only the transcript, nothing else."
out = open(os.path.join(S.HERE, "results", f"{a.tag}_{a.set}.jsonl"), "w") if os.path.isdir(os.path.join(S.HERE, "results")) else None
os.makedirs(os.path.join(S.HERE, "results"), exist_ok=True); out = open(os.path.join(S.HERE, "results", f"{a.tag}_{a.set}.jsonl"), "w")
cl = S.clips(a.set); cl = cl[:a.limit] if a.limit else cl
for p in cl:
    dur = sf.info(p).duration
    body = {"model": "x", "temperature": 0.0, "max_tokens": 600, "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": base64.b64encode(open(p, "rb").read()).decode(), "format": "wav"}}, {"type": "text", "text": PROMPT}]}]}
    req = urllib.request.Request(f"http://127.0.0.1:{a.port}/v1/chat/completions", json.dumps(body).encode(), {"Content-Type": "application/json", "Authorization": "Bearer critic-test-key"})
    t = time.time()
    try: r = json.load(urllib.request.urlopen(req, timeout=300)); txt = r["choices"][0]["message"]["content"] or ""; err = None; fin = r["choices"][0]["finish_reason"]
    except Exception as e: txt, err, fin = "", repr(e)[:300], None
    rec = {"clip": os.path.basename(p), "duration": dur, "seconds": time.time() - t, "text": txt.strip(), "error": err, "finish": fin}
    out.write(json.dumps(rec) + "\n"); out.flush(); print(rec["clip"], f"{rec['seconds']:.1f}s", repr(txt.strip()[:90]) if not err else err, flush=True)
