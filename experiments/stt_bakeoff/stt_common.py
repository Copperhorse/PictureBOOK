"""Shared helpers for the STT bake-off: clip lists, text normalisation, WER, key-term recall, sentence counts."""
import json, os, re, glob
HERE = os.path.dirname(os.path.abspath(__file__))
AUD = os.environ.get("STT_AUDIO", "/tmp/claude-1000/-home-copper-Git-PictureBOOK/dd2ae928-9ea4-4881-b211-7f35342dc072/scratchpad/stt_audio")   # derived WAVs; the user's clips stay outside the repo
TEXTS = json.load(open(os.path.join(HERE, "texts.json")))
KEY_TERMS = {"arcania_a": [], "arcania_b": ["arcania", "seventh prince"], "fox": [], "hood": [], "dragon": ["marcus", "biscuit", "willowbrook"], "whale": ["lina"], "robot": ["zed"], "garden": ["mia", "omar"]}
def clips(which):
    if which == "synth": return sorted(glob.glob(f"{AUD}/synth/*.wav"))
    if which == "user": return sorted(glob.glob(f"{AUD}/user/*.wav"))
    return []
_NUM = {"57": "fifty seven"}
def norm(t):
    t = t.lower().replace("-", " ").replace("’", "'")
    for k, v in _NUM.items(): t = t.replace(k, v)
    t = re.sub(r"\bgray\b", "grey", t)
    t = re.sub(r"[^a-z0-9' ]+", " ", t)
    return t.split()
def wer(ref, hyp):
    r, h = norm(ref), norm(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = d[j]; d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1])); prev = cur
    return d[len(h)] / max(1, len(r)), len(r)
def term_recall(key, hyp):
    terms = KEY_TERMS.get(key, []); h = " ".join(norm(hyp))
    return sum(t in h for t in terms), len(terms)
def n_sentences(t): return len([s for s in re.split(r"[.!?]+", t) if s.strip()])
def clip_key(path):
    b = os.path.basename(path)[:-4]; return b.rsplit("_", 1)[0], b.rsplit("_", 1)[1]
