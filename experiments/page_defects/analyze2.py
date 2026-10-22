"""Score detector v2 output against labels. usage: python3 analyze2.py <results.jsonl> [--crops] [--thr 0.99]
Predictions are relative to the character's reference image: hands/legs > max(ref, 2), figures > 1, hair_style != ref style, floating true.
'crop' mode takes hands/legs/hair/floating from the zoomed per-character crop and figures/objects/events from the full image."""
import json, os, re, sys
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(H, "..", ".."))
CROPS = "--crops" in sys.argv; THR = float(sys.argv[sys.argv.index("--thr") + 1]) if "--thr" in sys.argv else 0.99
res = [json.loads(l) for l in open(sys.argv[1])]; man = {m["file"]: m for m in json.load(open(os.path.join(H, "manifest_v2.json")))}
labels = {}
for fn in ("labels_old.json", "labels_fresh.json", "labels_fresh2.json"): labels.update(json.load(open(os.path.join(H, fn))))
full = {r["file"]: r for r in res if r["crop"] is None}; crops = {(r["file"], r["crop"]): r for r in res if r["crop"] is not None}
ref = {}
for f, r in full.items():
    m = man[f]
    if m["page"] == 0: ref[(m["run"], m["only"])] = list(r["answers"]["characters"].values())[0]
def p_gt(dist, thr):
    return sum(v for k, v in dist.items() if k.isdigit() and int(k) > thr) if dist else None
def p_value(dist, v): return dist.get(v, 0.0) if dist else None
rows = {t: [] for t in ("extra_hand", "extra_leg", "duplicate", "floating", "object_dup", "event_missing", "hair_changed")}
for f, r in full.items():
    m = man[f]
    if m["page"] == 0: continue
    L = labels.get(os.path.relpath(f, ROOT))
    if L is None or L.get("disputed"): continue
    skip = set(L.get("uncertain", []))
    for i, n in enumerate(r["answers"]["characters"]):
        a = r["answers"]["characters"][n]; d = {k: (r["dists"][k][i] if i < len(r["dists"][k]) else None) for k in r["dists"]}
        src = crops.get((f, n)) if CROPS else None
        if src: a2 = src["answers"]["characters"][n]; d2 = {k: (src["dists"][k][0] if src["dists"][k] else None) for k in src["dists"]}
        else: a2, d2 = a, d
        rf = ref.get((m["run"], n), {"hands": 2, "legs": 2, "hair_style": a2["hair_style"]})
        def put(t, truth, pred, conf):
            if f"{t}:{n}" not in skip: rows[t].append((truth, pred, conf))
        for t, fld in (("extra_hand", "hands"), ("extra_leg", "legs")):
            thr = max(rf[fld], 2); pe = p_gt(d2[fld], thr); put(t, n in L.get(t, []), a2[fld] > thr, None if pe is None else (pe if a2[fld] > thr else 1 - pe))
        pe = p_gt(d["figures"], 1); put("duplicate", n in L.get("duplicate", []), a["figures"] > 1, None if pe is None else (pe if a["figures"] > 1 else 1 - pe))
        pt = p_value(d2["floating"], "true"); put("floating", n in L.get("floating", []), a2["floating"], None if pt is None else (pt if a2["floating"] else 1 - pt))
        ps = p_value(d2["hair_style"], a2["hair_style"]); ch = a2["hair_style"] != rf["hair_style"] and rf["hair_style"] != "covered" and a2["hair_style"] != "covered"
        put("hair_changed", n in L.get("hair_changed", []), ch, None)
    for o, c in (r["answers"].get("objects") or {}).items():
        if f"object_dup:{o}" not in skip: rows["object_dup"].append((o in L.get("object_dup", []), c >= 2, None))
    ev = r["answers"].get("events") or {}
    if ev: rows["event_missing"].append((bool(L.get("event_missing")), not all(ev.values()), None))
print(f"{'type':14s}{'pos':>4s}{'neg':>5s}{'recall':>8s}{'false-alarm':>13s}   (confident only, >= {THR}: recall / false-alarm)")
for t, rs in rows.items():
    if not rs: continue
    pos = [x for x in rs if x[0]]; neg = [x for x in rs if not x[0]]; rec = sum(x[1] for x in pos) / len(pos) if pos else float("nan"); fa = sum(x[1] for x in neg) / len(neg) if neg else float("nan")
    ok = lambda x: x[2] is None or x[2] >= THR
    r99 = sum(x[1] and ok(x) for x in pos) / len(pos) if pos else float("nan"); f99 = sum(x[1] and ok(x) for x in neg) / len(neg) if neg else float("nan")
    print(f"{t:14s}{len(pos):4d}{len(neg):5d}{rec:8.2f}{fa:13.2f}   {r99:.2f} / {f99:.2f}")
