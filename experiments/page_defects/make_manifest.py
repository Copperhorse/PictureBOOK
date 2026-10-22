"""Build manifest.json for detect.py: the 20 old pages + every fresh render in out/ (variant given as argv[1], default all)."""
import glob, json, os, re, sys
from page_meta import OBJECTS, MUST
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
variant = sys.argv[1] if len(sys.argv) > 1 else None
M = []
for f in sorted(json.load(open(os.path.join(os.path.dirname(__file__), "labels_old.json")))):
    r = json.load(open(os.path.join(os.path.dirname(__file__), "labels_old.json")))[f]; k = (r["run"], r["page"])
    if variant in (None, "old"): M.append({"file": os.path.join(ROOT, f), "run": r["run"], "page": r["page"], "objects": OBJECTS.get(k, []), "must_show": MUST.get(k, [])})
for f in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "out", "*.png"))):
    m = re.match(r"(\w+)_p(\d+)_(\w+)_s(\d+)\.png", os.path.basename(f))
    if not m or variant not in (None, m.group(3)): continue
    k = (m.group(1), int(m.group(2))); M.append({"file": f, "run": k[0], "page": k[1], "objects": OBJECTS.get(k, []), "must_show": MUST.get(k, [])})
json.dump(M, open(os.path.join(os.path.dirname(__file__), "manifest.json"), "w"), indent=1); print(len(M), "images")
