import sys, os
os.environ.setdefault("DATASET", "_v2")
import analyze as A
def key(r): return (r["image"], r["variant"], r["attr"])
def summ(rows):
    N = len(rows); neg = [r for r in rows if not r["gt"]]; pos = [r for r in rows if r["gt"]]
    return dict(acc=sum(r["gt"] == r["pred"] for r in rows) / N, rec=sum(not r["pred"] for r in neg) / len(neg), fa=sum(not r["pred"] for r in pos) / len(pos), N=N)
def line(name, rows):
    s = summ(rows); per = {}
    for a in A.ATTRS:
        n_ = [r for r in rows if r["attr"] == a and not r["gt"]]; p_ = [r for r in rows if r["attr"] == a and r["gt"]]
        per[a] = (sum(not r["pred"] for r in n_) / len(n_), sum(not r["pred"] for r in p_) / len(p_))
    cells = " | ".join(f"{100*per[a][0]:.0f}/{100*per[a][1]:.0f}" for a in A.ATTRS)
    print(f"| {name} | {100*s['acc']:.1f}% | {100*s['rec']:.1f}% | {100*s['fa']:.1f}% | {cells} |")
if __name__ == "__main__":
    tags = sys.argv[1:]; data = {t: A.load(t)[0] for t in tags}
    print("| condition | accuracy | mismatch recall | false alarms | robe rec/FA | hair rec/FA | headwear rec/FA | eyewear rec/FA | held rec/FA |\n|---|---|---|---|---|---|---|---|---|")
    for t in tags: line(t, data[t])
    if len(tags) >= 2:
        a, b = data[tags[0]], data[tags[1]]; bm = {key(r): r for r in b}
        both = [r for r in a if key(r) in bm]
        for name, rule in (("AND (mismatch only if both say mismatch)", lambda x, y: x or y), ("OR (mismatch if either says mismatch)", lambda x, y: x and y)):
            rows = [dict(r, pred=rule(r["pred"], bm[key(r)]["pred"])) for r in both]
            line(f"{tags[0]} + {tags[1]}: {name}", rows)
