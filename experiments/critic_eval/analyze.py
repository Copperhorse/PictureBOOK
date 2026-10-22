import json, math, sys, os, statistics as st
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
SET = os.environ.get("DATASET", "")
MAN = {m["file"]: m for m in json.load(open(os.path.join(HERE, f"manifest{SET}.json")))}
ATTRS = ["robe_colour", "hair_colour", "headwear", "eyewear", "held_item"]

def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"),) * 2
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)
def fmt(k, n):
    if n == 0: return "n/a"
    lo, hi = wilson(k, n); return f"{100*k/n:5.1f}% [{100*lo:4.1f}-{100*hi:4.1f}] (n={n})"

def load(tag):
    rows, fails = [], defaultdict(int)
    for line in open(os.path.join(HERE, "results", f"{tag}.jsonl")):
        r = json.loads(line)
        if "error" in r: fails["http_error"] += 1; continue
        if r["finish"] != "stop": fails["finish_" + r["finish"]] += 1
        if not r.get("content"): fails["empty_content"] += 1; continue
        try: checks = json.loads(r["content"])["checks"]
        except Exception: fails["bad_json"] += 1; continue
        if len(checks) != 5: fails["wrong_count"] += 1; continue
        meta = MAN[r["image"]]
        for i, c in enumerate(checks):
            a = c["attribute"]; exp = r["expected"][a]; gt = (exp == r["truth"][a])
            p = r["p_true"][i] if i < len(r.get("p_true", [])) else None
            rows.append({"image": r["image"], "variant": r["variant"], "attr": a, "expected": exp, "truth": r["truth"][a], "gt": gt,
                         "pred": bool(c["match"]), "observed": c["observed"], "p_true": p, "size": meta["size"], "n": meta["n_characters"],
                         "effect": meta["effect"], "lat": r["latency"], "tok": r["usage"]["completion_tokens"], "rchars": r["reasoning_chars"]})
    return rows, fails

def report(tag):
    rows, fails = load(tag)
    N = len(rows); print(f"\n=== {tag}: {N} checks parsed; request failures: {dict(fails) or 'none'}")
    lat = [r["lat"] for r in rows[::5]]; tok = [r["tok"] for r in rows[::5]]
    print(f"latency/request mean {st.mean(lat):.1f}s (max {max(lat):.1f}s); completion tokens mean {st.mean(tok):.0f}; reasoning chars mean {st.mean([r['rchars'] for r in rows[::5]]):.0f}")
    acc = sum(r["gt"] == r["pred"] for r in rows)
    neg = [r for r in rows if not r["gt"]]; pos = [r for r in rows if r["gt"]]
    print("overall accuracy      ", fmt(acc, N))
    print("mismatch recall       ", fmt(sum(not r["pred"] for r in neg), len(neg)), " <- wrong value correctly rejected")
    print("false-alarm rate      ", fmt(sum(not r["pred"] for r in pos), len(pos)), " <- correct value wrongly rejected")
    print("precision of 'mismatch'", fmt(sum(not r["pred"] for r in neg), sum(not r["pred"] for r in rows)))
    print("-- per attribute (recall of wrong values | false alarms on correct values)")
    for a in ATTRS:
        n_ = [r for r in neg if r["attr"] == a]; p_ = [r for r in pos if r["attr"] == a]
        print(f"   {a:12s} recall {fmt(sum(not r['pred'] for r in n_), len(n_))} | false alarms {fmt(sum(not r['pred'] for r in p_), len(p_))}")
    print("-- by character size (accuracy)")
    for s in ("small", "medium", "large"):
        x = [r for r in rows if r["size"] == s]; print(f"   {s:7s}", fmt(sum(r['gt'] == r['pred'] for r in x), len(x)))
    print("-- by number of characters / image effect (accuracy)")
    for k, f in (("1 char", lambda r: r["n"] == 1), ("2 chars", lambda r: r["n"] == 2), ("clean", lambda r: r["effect"] is None), ("blur", lambda r: r["effect"] == "blur"), ("noise", lambda r: r["effect"] == "noise")):
        x = [r for r in rows if f(r)]; print(f"   {k:7s}", fmt(sum(r['gt'] == r['pred'] for r in x), len(x)))
    print("-- robe colour: wrong value accepted (misses) by confusable pair")
    miss = defaultdict(lambda: [0, 0])
    for r in neg:
        if r["attr"] == "robe_colour": k = f"{r['truth']}->{r['expected']}"; miss[k][1] += 1; miss[k][0] += r["pred"]
    print("   " + ", ".join(f"{k}: {a}/{b}" for k, (a, b) in sorted(miss.items()) if a))
    cal = [r for r in rows if r["p_true"] is not None]
    if cal:
        print("-- confidence calibration (confidence = renormalised probability of the answer actually given)")
        bins = [(0.5, 0.9), (0.9, 0.99), (0.99, 1.0001)]
        for lo, hi in bins:
            x = [r for r in cal if lo <= max(r["p_true"], 1 - r["p_true"]) < hi]
            print(f"   conf {lo:.2f}-{min(hi,1):.2f}: error rate", fmt(sum(r['gt'] != r['pred'] for r in x), len(x)))
    errs = [r for r in rows if r["gt"] != r["pred"]]
    print(f"-- {len(errs)} errors; examples:")
    for r in errs[:8]: print(f"   {r['image']} {r['variant']} {r['attr']}: expected={r['expected']} truth={r['truth']} observed='{r['observed']}' model_match={r['pred']}")
    return rows

if __name__ == "__main__":
    for t in sys.argv[1:]: report(t)
