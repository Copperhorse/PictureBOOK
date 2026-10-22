import json, sys, os, collections, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__))
def load(tag): return [json.loads(l) for l in open(os.path.join(HERE, "results", f"{tag}.jsonl"))]
def report(tags):
    recs = [r for t in tags for r in load(t)]
    conds = sorted({r["cond"] for r in recs}, key=lambda c: ["single_off", "single_on", "multi_off", "multi_on"].index(c) if c in ["single_off", "single_on", "multi_off", "multi_on"] else 9)
    print("| condition | runs | parse ok | finish≠stop | latency (s) | completion tokens | dangling env / char (per plan) | effects on 'layered' pages | characters missing from layout | pages with empty layout | ranges ok | 'None' misuse | stated facts kept | pages w/ any rule violation |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in conds:
        rs = [r for r in recs if r["cond"] == c]; ok = [r for r in rs if r["check"].get("parse_ok")]
        fin = sum(m["finish"] != "stop" for r in rs for m in r["metas"])
        lat = st.mean(r["total_latency"] for r in rs); tok = st.mean(sum(m["completion_tokens"] for m in r["metas"]) for r in rs)
        def avg(k): return st.mean(r["check"][k] for r in ok) if ok else float("nan")
        facts = [v for r in ok for v in r["check"]["facts"].values()]
        viol = []
        for r in ok:
            ck = r["check"]; n = ck["pages"]
            viol.append(ck["dangling_env"] + ck["dangling_char"] + ck["effects_layered"] + ck["char_missing_from_layout"])
        print(f"| {c} | {len(rs)} | {len(ok)}/{len(rs)} | {fin} | {lat:.0f} | {tok:.0f} | {avg('dangling_env'):.1f} / {avg('dangling_char'):.1f} | {avg('effects_layered'):.1f} | {avg('char_missing_from_layout'):.1f} | {avg('empty_layout_pages'):.1f} | {sum(r['check']['ranges_ok'] for r in ok)}/{len(ok)} | {avg('none_misuse'):.1f} | {sum(facts)}/{len(facts)} | {sum(v>0 for v in viol)}/{len(ok)} plans |")
    print("\nPer story (stated facts kept / total):")
    for c in conds:
        row = []
        for sk in ("arcania", "red_hood", "fox_lantern"):
            f = [v for r in recs if r["cond"] == c and r["story"] == sk and r["check"].get("parse_ok") for v in r["check"]["facts"].values()]
            row.append(f"{sk} {sum(f)}/{len(f)}")
        print(" ", c, "|", ", ".join(row))
if __name__ == "__main__": report(sys.argv[1:])
