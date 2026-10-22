"""Review sheet for the human: review.png (all pages, numbered, large enough to see hands) and review.txt (a checklist built from the plan, plus the computer's warning notes).
usage: python3 review.py <run_dir>"""
import json, os, sys, textwrap
from PIL import Image, ImageDraw, ImageFont
from common import Run

CHECKLIST = ["every person/animal has two hands and two legs (unless hidden)", "every character appears exactly once", "everyone stands or sits on something solid",
             "the page shows what its sentence says", "hair and clothes match the other pages"]

def font(size):
    for f in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try: return ImageFont.truetype(f, size)
        except OSError: pass
    return ImageFont.load_default()

def picture_sig(run, index):
    st = os.stat(run.p("pages", f"page_{index:02d}.png"))
    return f"{st.st_size}-{int(st.st_mtime)}"

def hints_for(run, index, redrawn=0):
    """(notes, stale). Spec mismatches the critic was sure about, plus checks/hints.json (hints.py). Notes only count for the picture they were made for:
    after a redraw (or an undo) the old notes are dropped and the page is reported as 'not checked yet'."""
    out, stale = [], False
    if not redrawn:                                       # the spec check ran on the first drawing only
        for name in ("pages_r1.json", "pages_r0.json"):   # the latest spec check available
            if os.path.exists(run.p("checks", name)):
                for e in json.load(open(run.p("checks", name))).get(str(index), []):
                    out += [f"{e['character']}: {r['attribute'].replace('_', ' ')} looks like '{r['observed']}', plan says '{r['expected']}'" for r in e["confident_mismatches"]]
                break
    if os.path.exists(run.p("checks", "hints.json")):
        rec = json.load(open(run.p("checks", "hints.json"))).get(str(index))
        if isinstance(rec, dict):
            if rec.get("sig") == picture_sig(run, index): out += rec.get("hints", [])
            else: stale = True
    return out, stale

def build(run, tile=700, cols=2):
    plan = run.load("plan.json"); log = run.load("regen_log.json") if os.path.exists(run.p("regen_log.json")) else {}
    pages = plan["pages"]; rows = (len(pages) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile, rows * tile), "white"); d = ImageDraw.Draw(sheet); big = font(34); small = font(18)
    lines, report = [f"Review: {plan['title']}", "Look at every page at FULL size (review_pages/), the thumbnail sheet hides small mistakes such as a third leg. For a page with a mistake run:  python3 scripts/regen.py " + run.dir + " <page numbers, e.g. 2,4>", ""], {}
    for i, p in enumerate(pages):
        n = p["index"]; x, y = (i % cols) * tile, (i // cols) * tile
        sheet.paste(Image.open(run.p("pages", f"page_{n:02d}.png")).convert("RGB").resize((tile, tile)), (x, y))
        tries = log.get(str(n), {}).get("attempt", 0)
        d.rectangle([x, y, x + 150 + (130 if tries else 0), y + 48], fill="black"); d.text((x + 10, y + 5), f"Page {n}", fill="white", font=big)
        if tries: d.text((x + 150, y + 15), f"redrawn x{tries}", fill="yellow", font=small)
        who = [f"{l['character']} ({next(c['species'] for c in plan['characters'] if c['name'] == l['character'])})" for l in p["layout"]]
        h, stale = hints_for(run, n, tries); report[str(n)] = {"hints": h, "redrawn": tries, "checked": not stale}
        lines += [f"Page {n}  ({'redrawn x%d' % tries if tries else 'first drawing'})", "  Story: " + textwrap.shorten(p["story_text"], 150), "  Characters: " + (", ".join(who) or "nobody (scenery only)")]
        if p.get("must_show"): lines.append("  Must show: " + "; ".join(p["must_show"]))
        lines += ["  Check: " + " | ".join(CHECKLIST[:3 if not p["layout"] else 5]), "  Computer notes: " + ("; ".join(h) if h else ("not checked since this page was redrawn, look carefully" if stale else "none (it cannot see extra hands, so look at the hands yourself)")), ""]
    os.makedirs(run.p("review_pages"), exist_ok=True)
    for p in pages: Image.open(run.p("pages", f"page_{p['index']:02d}.png")).convert("RGB").resize((1024, 1024)).save(run.p("review_pages", f"page_{p['index']:02d}.png"))   # full size: the thumbnail sheet hides small mistakes
    sheet.save(run.p("review.png")); open(run.p("review.txt"), "w").write("\n".join(lines)); run.save("checks/report.json", report)
    return report

if __name__ == "__main__":
    run = Run(sys.argv[1]); rep = build(run)
    print(f"wrote {run.p('review.png')} and {run.p('review.txt')}; computer notes on {sum(1 for v in rep.values() if v['hints'])} of {len(rep)} pages")
    print(f"To redraw pages with mistakes:  python3 scripts/regen.py {run.dir} <page numbers>   (undo: --undo <page>)")
