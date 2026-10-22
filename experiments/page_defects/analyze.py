"""Score detector output against labels. usage: python3 analyze.py <results.jsonl> [labels files...]  (default labels_old.json labels_fresh.json)
A prediction is made per (image, character|object) and defect type; confidence = probability mass of the chosen side over the allowed tokens (renormalised)."""
import json, os, sys
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(H, "..", ".."))
res = [json.loads(l) for l in open(sys.argv[1])]
labels = {}
for fn in (sys.argv[2:] or ["labels_old.json", "labels_fresh.json"]):
    p = os.path.join(H, fn)
    if os.path.exists(p): labels.update(json.load(open(p)))
def key(f): return os.path.relpath(f, ROOT)
def p_exceed(dist, thr):
    if not dist: return None
    tot = sum(dist.values()); return sum(v for k, v in dist.items() if k.isdigit() and int(k) > thr) / tot if tot else None
TYPES = {"extra_hand": ("hands", 2), "extra_leg": ("legs", 2), "duplicate": ("figures", 1)}
rows = {t: [] for t in ("extra_hand", "extra_leg", "duplicate", "floating", "object_dup", "event_missing", "hair_changed")}   # (truth, predicted, confidence)
for r in res:
    L = labels.get(key(r["file"]))
    if L is None or L.get("disputed"): continue
    chars = list(r["answers"]["characters"])
    skip = set(L.get("uncertain", []))
    for i, n in enumerate(chars):
        a = r["answers"]["characters"][n]
        for t, (fld, thr) in TYPES.items():
            if f"{t}:{n}" in skip: continue
            d = (r["dists"].get(fld) or [])[i]["dist"] if i < len(r["dists"].get(fld) or []) else None
            pe = p_exceed(d, thr); pred = a[fld] > thr
            conf = None if pe is None else (pe if pred else 1 - pe)
            rows[t].append((n in L.get(t, []), pred, conf))
        if f"floating:{n}" not in skip: rows["floating"].append((n in L.get("floating", []), a["floating"], None))
        rows["hair_changed"].append((n in L.get("hair_changed", []), not a["hair_style_matches"], None))
    for o, c in (r["answers"].get("objects") or {}).items():
        if f"object_dup:{o}" in skip: continue
        rows["object_dup"].append((o in L.get("object_dup", []), c >= 2, None))
    ev = r["answers"].get("events") or {}
    if ev: rows["event_missing"].append((bool(L.get("event_missing")), not all(ev.values()), None))
print(f"{'type':14s}{'pos':>4s}{'neg':>5s}{'recall':>8s}{'false-alarm':>13s}   (at >=0.99 confidence: recall / false-alarm)")
for t, rs in rows.items():
    pos = [x for x in rs if x[0]]; neg = [x for x in rs if not x[0]]
    if not rs: continue
    rec = sum(x[1] for x in pos) / len(pos) if pos else float("nan"); fa = sum(x[1] for x in neg) / len(neg) if neg else float("nan")
    hi = lambda xs: [x for x in xs if x[2] is None or x[2] >= 0.99]
    rec99 = sum(x[1] for x in hi(pos)) / len(pos) if pos else float("nan"); fa99 = sum(x[1] for x in hi(neg)) / len(neg) if neg else float("nan")
    print(f"{t:14s}{len(pos):4d}{len(neg):5d}{rec:8.2f}{fa:13.2f}   {rec99:.2f} / {fa99:.2f}")
