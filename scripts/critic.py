"""Gemma 4 E4B vision critic (1120 image tokens, thinking off, temperature 0, confidence from renormalised token probabilities).
usage: python3 critic.py <run_dir> assets   -> chooses the best reference per character (assets/ref_<slug>.png), writes checks/assets.json
       python3 critic.py <run_dir> pages    -> checks every page, writes checks/pages.json
Policy (docs/research/critic-evaluation.md): a hard mismatch is acted on only when confidence >= 0.99; lower-confidence mismatches are reported as 'uncertain'."""
import json, math, os, re, shutil, sys
from common import Run, llama_server, chat, image_part, timed, require_ram, _none

ATTRS = ["outfit", "hair", "headwear", "eyewear", "held_item"]
HARD = {"outfit", "headwear", "eyewear", "held_item"}
DESC = {"outfit": "the main garment the character wears (colour and kind, e.g. 'deep blue robe')", "hair": "colour of the hair", "headwear": "what is on the head: none, hood, hat, crown, ...",
        "eyewear": "none, or glasses", "held_item": "what the character holds in the hand: none, a stick, a basket, ..."}
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["checks"], "properties": {"checks": {"type": "array", "minItems": 5, "maxItems": 5, "items": {
    "type": "object", "additionalProperties": False, "required": ["attribute", "expected", "observed", "match"], "properties": {
        "attribute": {"enum": ATTRS}, "expected": {"type": "string", "maxLength": 60}, "observed": {"type": "string", "maxLength": 60}, "match": {"type": "boolean"}}}}}}
SYSTEM = ("You are a strict visual inspector for children's picture-book illustrations. For each check, look at the image and write what you actually see in 'observed' "
          "(a few words) BEFORE deciding 'match'. 'match' is true only if what you see agrees with 'expected'. Do not assume the expected value is correct. Answer only with JSON.")

def expected_of(c):
    o = c["outfit"][0]
    if _none(o["item"]): o = {"item": "no clothing (natural body)", "colour": ""}
    held = "none" if _none(c["accessories"]) else re.sub(r"\s*(held|carried)\b.*$", "", c["accessories"], flags=re.I).strip()
    return {"outfit": f"{o['colour']} {o['item']}", "hair": "none (bald)" if _none(c["hair"]) else f"{c['hair']} hair", "headwear": "none" if _none(c["headwear"]) else c["headwear"],
            "eyewear": "none" if _none(c["eyewear"]) else c["eyewear"], "held_item": held}

def who(c): return f"the {c['height_relative'].replace('_', ' ')} {c['age_group']} {c['species']} wearing a {c['outfit'][0]['colour']} {c['outfit'][0]['item']}"

def probs(choice):
    out = []
    for t in (choice.get("logprobs") or {}).get("content") or []:
        if t["token"].strip() in ("true", "false"):
            p = {"true": 0.0, "false": 0.0}
            for a in t.get("top_logprobs", []) + [{"token": t["token"], "logprob": t["logprob"]}]:
                k = a["token"].strip()
                if k in p: p[k] = max(p[k], math.exp(a["logprob"]))
            s = p["true"] + p["false"]; out.append(p["true"] / s if s else 0.5)
    return out

def check_character(port, image, c, multi=False, hard=HARD):
    hard = set(hard) - ({"outfit"} if _none(c["outfit"][0]["item"]) else set())
    exp = expected_of(c)
    lines = [f"Inspect {who(c) if multi else 'the main character'} only. Answer all five checks, in this order:"] + [f"{i}. {a} ({DESC[a]}) — expected: {exp[a]}" for i, a in enumerate(ATTRS, 1)]
    msg = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": [image_part(image), {"type": "text", "text": "\n".join(lines)}]}]
    ch = chat(port, msg, SCHEMA, "critic", temperature=0.0, max_tokens=700, logprobs=True)
    checks = json.loads(ch["message"]["content"])["checks"]; pr = probs(ch)
    res = []
    for i, cc in enumerate(checks):
        p_true = pr[i] if i < len(pr) else 0.5
        conf = max(p_true, 1 - p_true)
        res.append({"attribute": cc["attribute"], "expected": cc["expected"], "observed": cc["observed"], "match": cc["match"], "confidence": round(conf, 4), "hard": cc["attribute"] in hard})
    return res

def verdict(res):
    bad = [r for r in res if r["hard"] and not r["match"] and r["confidence"] >= 0.99]
    unsure = [r for r in res if r["hard"] and not r["match"] and r["confidence"] < 0.99]
    return {"confident_mismatches": bad, "uncertain": unsure, "ok": not bad}

if __name__ == "__main__":
    run = Run(sys.argv[1]); mode = sys.argv[2]
    require_ram(5); plan = run.load("plan.json"); chars = {c["name"]: c for c in plan["characters"]}
    slug = lambda s: re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    with timed(run, f"critic_{mode}"), llama_server(run.p("llama_critic.log")) as port:
        ONLY = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
        if mode == "assets":
            try: out = run.load("checks/assets.json") if ONLY else {}          # a single character is re-checked into the existing results
            except FileNotFoundError: out = {}
            for c in plan["characters"]:
                if ONLY and c["name"] != ONLY: continue
                cands = sorted(f for f in os.listdir(run.p("assets")) if f.startswith(f"ref_{slug(c['name'])}_c"))
                if not cands:
                    print(f"{c['name']}: no candidate pictures to check (skipped)", flush=True); continue
                scored = []
                for f in cands:
                    res = check_character(port, run.p("assets", f), c); v = verdict(res)
                    score = sum(r["match"] for r in res if r["hard"]) * 10 + sum(r["match"] for r in res if not r["hard"]) - 100 * len(v["confident_mismatches"])
                    scored.append({"file": f, "score": score, "checks": res, **v})
                best = max(scored, key=lambda s: s["score"])
                shutil.copy(run.p("assets", best["file"]), run.p("assets", f"ref_{slug(c['name'])}.png"))
                out[c["name"]] = {"chosen": best["file"], "confident_mismatches": best["confident_mismatches"], "candidates": scored}
                print(f"{c['name']}: chose {best['file']} (hard mismatches: {[ (r['attribute'], r['observed']) for r in best['confident_mismatches']]})", flush=True)
            run.save("checks/assets.json", out)
        elif mode == "refs":  # re-check the final reference images (after repair)
            out = {}
            for c in plan["characters"]:
                if ONLY and c["name"] != ONLY: continue
                res = check_character(port, run.p("assets", f"ref_{slug(c['name'])}.png"), c); v = verdict(res)
                out[c["name"]] = {"checks": res, **v}
                print(f"{c['name']} (after repair): " + ("ok" if v["ok"] else "STILL MISMATCH " + str([(r['attribute'], r['expected'], r['observed']) for r in v["confident_mismatches"]])), flush=True)
            run.save("checks/refs_after_repair.json", out)
        elif mode == "hints":   # warning notes for the human reviewer, never an automatic action (hints.py); `--pages 2,4` re-checks only those pages
            from hints import figure_hints, scene_hints
            only = {int(x) for x in sys.argv[sys.argv.index("--pages") + 1].split(",")} if "--pages" in sys.argv else None
            try: out = run.load("checks/hints.json")
            except FileNotFoundError: out = {}
            for p in plan["pages"]:
                if only is not None and p["index"] not in only: continue
                names = [l["character"] for l in p["layout"]]; img = run.p("pages", f"page_{p['index']:02d}.png"); h = []
                if names: h += figure_hints(port, img, names)
                h += scene_hints(port, img, p, chars)
                st = os.stat(img)
                out[str(p["index"])] = {"hints": h, "sig": f"{st.st_size}-{int(st.st_mtime)}"}   # notes belong to this exact picture file
                print(f"page {p['index']}: " + ("; ".join(h) if h else "no hints"), flush=True)
            run.save("checks/hints.json", out)
        elif mode == "pages":
            out = {}
            for p in plan["pages"]:
                img = run.p("pages", f"page_{p['index']:02d}.png")
                entries = []
                for l in p["layout"]:
                    c = chars[l["character"]]; res = check_character(port, img, c, multi=len(p["layout"]) > 1, hard=HARD - {"held_item"}); entries.append({"character": c["name"], "checks": res, **verdict(res)})
                out[str(p["index"])] = entries
                print(f"page {p['index']}: " + ("; ".join(f"{e['character']}: " + ("ok" if e["ok"] else "MISMATCH " + str([(r['attribute'], r['expected'], r['observed']) for r in e['confident_mismatches']])) + (f" (uncertain {[r['attribute'] for r in e['uncertain']]})" if e["uncertain"] else "") for e in entries) or "no characters"), flush=True)
            run.save(f"checks/pages_{sys.argv[3] if len(sys.argv) > 3 else 'r0'}.json", out)
