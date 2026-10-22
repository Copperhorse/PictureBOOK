"""Score enumeration output: duplicate = more figure entries than layout characters (or one character listed twice); extra_hand = more than 2 hand entries owned by one non-animal-group character."""
import json, os, sys
from collections import Counter
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(H, "..", ".."))
res = [json.loads(l) for l in open(sys.argv[1])]; man = {m["file"]: m for m in json.load(open(os.path.join(H, "manifest_v2.json")))}
labels = {}
for fn in ("labels_old.json", "labels_fresh.json", "labels_fresh2.json"): labels.update(json.load(open(os.path.join(H, fn))))
dup, hand = [], []
for r in res:
    L = labels.get(os.path.relpath(r["file"], ROOT)); m = man[r["file"]]
    if L is None or L.get("disputed"): continue
    plan = json.load(open(f"{ROOT}/runs/{m['run']}/plan.json")); names = [l["character"] for l in plan["pages"][m["page"] - 1]["layout"]]
    fc = Counter(x["who"] for x in r["answers"]["figures"]); hc = Counter(x["owner"] for x in r["answers"]["hands"])
    for n in names:
        if f"duplicate:{n}" in set(L.get("uncertain", [])): continue
        dup.append((n in L.get("duplicate", []), fc[n] > 1 or sum(fc.values()) > len(names) + (1 if "Ducks" in names else 0)))
        hand.append((n in L.get("extra_hand", []), hc[n] > 2))
for name, rs in (("duplicate", dup), ("extra_hand", hand)):
    pos = [x for x in rs if x[0]]; neg = [x for x in rs if not x[0]]
    print(f"{name:12s} pos {len(pos):3d} neg {len(neg):3d}  recall {sum(x[1] for x in pos)/max(1,len(pos)):.2f}  false-alarm {sum(x[1] for x in neg)/max(1,len(neg)):.2f}")
