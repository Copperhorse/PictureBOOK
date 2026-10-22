"""manifest_v2.json = reference images of every character + every labelled page image (labels_*.json)."""
import json, os, re
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(H, "..", ".."))
from page_meta import OBJECTS, MUST
labels = {}
for fn in ("labels_old.json", "labels_fresh.json", "labels_fresh2.json"): labels.update(json.load(open(os.path.join(H, fn))))
pages = [{"file": os.path.join(ROOT, k), "run": v["run"], "page": v["page"], "objects": OBJECTS.get((v["run"], v["page"]), []), "must_show": MUST.get((v["run"], v["page"]), [])} for k, v in labels.items()]
refs, seen = [], set()
for m in pages:
    plan = json.load(open(f"{ROOT}/runs/{m['run']}/plan.json"))
    for l in plan["pages"][m["page"] - 1]["layout"]:
        if (m["run"], l["character"]) in seen: continue
        seen.add((m["run"], l["character"])); refs.append({"file": f"{ROOT}/runs/{m['run']}/assets/ref_{re.sub(r'[^a-z0-9]+', '_', l['character'].lower()).strip('_')}.png", "run": m["run"], "page": 0, "only": l["character"]})
json.dump(refs + pages, open(os.path.join(H, "manifest_v2.json"), "w"), indent=1); print(len(refs), "refs +", len(pages), "pages")
