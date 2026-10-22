import json, sys, os
import analyze as A
def run(tag):
    rows, fails = [], 0
    for l in open(os.path.join(A.HERE, "results", f"{tag}.jsonl")):
        r = json.loads(l)
        try: checks = json.loads(r["content"])["checks"]; assert len(checks) == 5
        except Exception: fails += 1; continue
        p = r["pair"]
        for i, c in enumerate(checks):
            a = c["attribute"]; gt_same = p["truth_ref"][a] == p["truth_cand"][a]
            rows.append({"attr": a, "gt_same": gt_same, "pred_same": bool(c["same"]), "changed": p["changed"], "ref": c["in_reference"], "cand": c["in_candidate"], "pair": p["cand"], "tref": p["truth_ref"][a], "tcand": p["truth_cand"][a]})
    d = [r for r in rows if not r["gt_same"]]; s = [r for r in rows if r["gt_same"]]
    print(f"\n=== {tag}: {len(rows)} attribute comparisons ({fails} unparsable requests)")
    print("drift detection recall (changed attribute reported different):", A.fmt(sum(not r["pred_same"] for r in d), len(d)))
    print("false alarm rate (unchanged attribute reported different)   :", A.fmt(sum(not r["pred_same"] for r in s), len(s)))
    ctrl = [r for r in rows if r["changed"] is None]
    print("  of which control pairs (nothing changed; only background/position)", A.fmt(sum(not r["pred_same"] for r in ctrl), len(ctrl)))
    for a in A.ATTRS:
        dd = [r for r in d if r["attr"] == a]; ss = [r for r in s if r["attr"] == a]
        print(f"   {a:12s} recall {A.fmt(sum(not r['pred_same'] for r in dd), len(dd))} | false alarms {A.fmt(sum(not r['pred_same'] for r in ss), len(ss))}")
    print("-- missed drifts:", [(r["pair"], r["attr"], f"{r['tref']}->{r['tcand']}", f"saw '{r['ref']}' vs '{r['cand']}'") for r in d if r["pred_same"]][:6])
if __name__ == "__main__":
    for t in sys.argv[1:]: run(t)
