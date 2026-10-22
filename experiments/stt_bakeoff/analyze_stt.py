"""Score the engines on the synthetic set (exact references) and compare engines on the user's clips (no references: pairwise disagreement only, nothing printed from private transcripts).
usage: python3 analyze_stt.py parakeet whisper gemma_e4b gemma_e2b"""
import json, os, sys, collections, itertools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stt_common as S
def load(tag, which):
    d = os.path.join(S.HERE, "results") if which == "synth" else os.path.join(S.AUD, "private_results")
    p = os.path.join(d, f"{tag}_{which}.jsonl")
    if not os.path.exists(p): return None
    d = {json.loads(l)["clip"]: json.loads(l) for l in open(p)}
    if which == "user": allowed = {os.path.basename(x) for x in S.clips("user")}; d = {k: v for k, v in d.items() if k in allowed}   # clips excluded from the benchmark never count
    return d
tags = sys.argv[1:]
print("== Synthetic set (8 passages x 6 conditions, exact references): WER % (key terms found / total)")
conds = ["clean", "fast", "phone", "reverb", "noise10", "noise0"]
print(f"{'engine':12s} " + " ".join(f"{c:>13s}" for c in conds) + "   all   RTF")
for t in tags:
    d = load(t, "synth")
    if not d: print(t, "no results"); continue
    by = collections.defaultdict(list)
    for clip, r in d.items():
        key, cond = S.clip_key(clip); w, n = S.wer(S.TEXTS[key], r["text"]); tr = S.term_recall(key, r["text"]); by[cond].append((w, n, tr, r["seconds"], r["duration"], S.n_sentences(r["text"]) - S.n_sentences(S.TEXTS[key])))
    cells = []
    for c in conds:
        v = by[c]; ww = 100 * sum(x[0] * x[1] for x in v) / sum(x[1] for x in v); cells.append(f"{ww:5.1f} ({sum(x[2][0] for x in v)}/{sum(x[2][1] for x in v)})")
    allv = [x for v in by.values() for x in v]; wall = 100 * sum(x[0] * x[1] for x in allv) / sum(x[1] for x in allv); rtf = sum(x[3] for x in allv) / sum(x[4] for x in allv)
    print(f"{t:12s} " + " ".join(f"{c:>13s}" for c in cells) + f"  {wall:5.1f}  {rtf:.2f}")
print("\n== Sentence-count difference vs reference (negative = sentences merged/lost; matters for splitting pages)")
for t in tags:
    d = load(t, "synth")
    if d: print(f"{t:12s} mean {sum(S.n_sentences(r['text']) - S.n_sentences(S.TEXTS[S.clip_key(c)[0]]) for c, r in d.items()) / len(d):+.2f}")
print("\n== User clips (14, TTS-style voices + one voice note): pairwise word disagreement between engines (WER of one against the other, %), no reference available")
dd = {t: load(t, "user") for t in tags}; dd = {t: v for t, v in dd.items() if v}
for a, b in itertools.combinations(dd, 2):
    ws = [S.wer(dd[a][c]["text"], dd[b][c]["text"]) for c in dd[a] if c in dd[b]]
    print(f"{a:12s} vs {b:12s} {100 * sum(w * n for w, n in ws) / sum(n for _, n in ws):5.1f}%  (clips where they differ at all: {sum(w > 0 for w, _ in ws)}/{len(ws)})")
for t, v in dd.items():
    long = [r for r in v.values() if r["duration"] > 30]
    print(f"{t:12s} errors: {sum(bool(r.get('error')) for r in v.values())}; clips > 30 s: {len(long)} (non-empty output on {sum(bool(r['text']) for r in long)})")
