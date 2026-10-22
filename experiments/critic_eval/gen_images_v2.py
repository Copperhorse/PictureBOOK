"""v2 of the test set. v1 problems found by the first full run: hair was hidden or looked like a hood (the hood shape covered the hair, the grey hair cap looked like a hood),
and glasses were tiny on small characters. v2 draws the hood as a shell BEHIND the face with the hair fringe visible, adds hair styles (short, bun, long, ponytail),
avoids hood/hat colours equal to the hair colour, and uses larger characters. Run: python3 gen_images_v2.py"""
import json, os, random
from PIL import Image, ImageDraw
import gen_images as g

OUT = os.path.dirname(os.path.abspath(__file__))
g.SIZES = {"small": 0.75, "medium": 0.95, "large": 1.1}
ANALOG = {"red": "red", "blonde": "yellow", "brown": "orange", "black": None, "grey": None}
SS = g.SS

def draw_char(d, cx, ground, ch, r, outline):
    ground = ground + 10 * SS
    s = g.SIZES[ch["size"]] * SS
    ol = (35, 30, 40) if outline else None
    lw = max(1, int(3 * s / SS)) if outline else 0
    def poly(pts, fill): d.polygon(pts, fill=fill, outline=ol, width=lw)
    def ell(box, fill): d.ellipse(box, fill=fill, outline=ol, width=lw)
    body_h, wt, wb = 170 * s, 60 * s, 120 * s
    top = ground - 40 * s - body_h
    robe = ch["_robe_rgb"]
    for dx in (-22, 22):
        d.rectangle([cx + dx * s - 14 * s, ground - 40 * s, cx + dx * s + 14 * s, ground], fill=(95, 65, 45), outline=ol, width=lw)
    poly([(cx - wt / 2, top), (cx + wt / 2, top), (cx + wb / 2, ground - 40 * s), (cx - wb / 2, ground - 40 * s)], robe)
    if ch["shading"]:
        poly([(cx + 4 * s, top), (cx + wt / 2, top), (cx + wb / 2, ground - 40 * s), (cx + 18 * s, ground - 40 * s)], g.shade(robe, 0.8))
    ell([cx - wt / 2 - 22 * s, top + 8 * s, cx - wt / 2 + 12 * s, top + 100 * s], robe)
    ell([cx + wt / 2 - 12 * s, top + 8 * s, cx + wt / 2 + 22 * s, top + 100 * s], robe)
    hand = (cx + wt / 2 + 5 * s, top + 105 * s)
    ell([hand[0] - 9 * s, hand[1] - 9 * s, hand[0] + 9 * s, hand[1] + 9 * s], ch["_skin"])
    if ch["held"] == "wooden stick":
        d.line([(hand[0], hand[1]), (hand[0] + 40 * s, hand[1] - 95 * s)], fill=(125, 85, 45), width=int(7 * s))
    elif ch["held"] == "basket":
        bx, by = hand[0] + 6 * s, hand[1] + 6 * s
        d.arc([bx - 24 * s, by - 34 * s, bx + 24 * s, by + 10 * s], 180, 360, fill=(110, 75, 40), width=int(5 * s))
        poly([(bx - 30 * s, by), (bx + 30 * s, by), (bx + 22 * s, by + 38 * s), (bx - 22 * s, by + 38 * s)], (170, 120, 60))
    hr = 42 * s; hx, hy = cx, top - hr + 8 * s
    skin, hair = ch["_skin"], g.HAIR[ch["hair"]]
    hw, style = ch["headwear"], ch["_hair_style"]
    hwc = ch["_hw_rgb"]
    if hw == "hood":   # cloth shell behind the face, draped to the shoulders
        ell([hx - hr - 16 * s, hy - hr - 18 * s, hx + hr + 16 * s, hy + hr + 14 * s], hwc)
        poly([(hx - hr - 12 * s, hy + 4 * s), (hx + hr + 12 * s, hy + 4 * s), (hx + hr + 30 * s, hy + hr + 40 * s), (hx - hr - 30 * s, hy + hr + 40 * s)], hwc)
    # hair behind head (long / ponytail / bun)
    if style == "long":
        ell([hx - hr - 10 * s, hy - 8 * s, hx - hr + 14 * s, hy + hr + 38 * s], hair); ell([hx + hr - 14 * s, hy - 8 * s, hx + hr + 10 * s, hy + hr + 38 * s], hair)
    elif style == "ponytail":
        ell([hx + hr - 6 * s, hy - 10 * s, hx + hr + 30 * s, hy + hr + 20 * s], hair)
    ell([hx - hr, hy - hr, hx + hr, hy + hr], skin)
    # hair cap with a clear fringe (always visible, also under hood or hat)
    d.pieslice([hx - hr - 3 * s, hy - hr - 3 * s, hx + hr + 3 * s, hy + hr * 0.55], 180, 360, fill=hair, outline=ol, width=lw)
    if style == "bun" and hw == "none":
        ell([hx - 16 * s, hy - hr - 22 * s, hx + 16 * s, hy - hr + 6 * s], hair)
    if style == "short":
        for dx in (-hr, hr - 8 * s): d.rectangle([hx + dx, hy - 14 * s, hx + dx + 8 * s, hy + 6 * s], fill=hair)
    for dx in (-15, 15): ell([hx + dx * s - 4 * s, hy - 2 * s, hx + dx * s + 4 * s, hy + 6 * s], (30, 30, 30))
    d.arc([hx - 14 * s, hy + 8 * s, hx + 14 * s, hy + 30 * s], 20, 160, fill=(120, 40, 40), width=max(1, int(3 * s / SS)))
    if ch["eyewear"] == "round glasses":
        gr = 14 * s
        for dx in (-15, 15): d.ellipse([hx + dx * s - gr, hy + 2 * s - gr, hx + dx * s + gr, hy + 2 * s + gr], outline=(25, 25, 30), width=max(3, int(4 * s / SS)))
        d.line([(hx - 15 * s + gr, hy + 2 * s), (hx + 15 * s - gr, hy + 2 * s)], fill=(25, 25, 30), width=max(3, int(3.5 * s / SS)))
    if hw == "hood":   # hood front trim framing the face
        d.arc([hx - hr - 4 * s, hy - hr - 6 * s, hx + hr + 4 * s, hy + hr + 4 * s], 200, 340, fill=g.shade(hwc, 0.7), width=max(2, int(5 * s / SS)))
    elif hw == "pointed hat":
        poly([(hx - hr - 10 * s, hy - hr * 0.55), (hx + hr + 10 * s, hy - hr * 0.55), (hx + 4 * s, hy - hr - 85 * s)], hwc)
        ell([hx - hr - 22 * s, hy - hr * 0.7, hx + hr + 22 * s, hy - hr * 0.35], g.shade(hwc, 0.85))

orig_make_spec = g.make_spec
def make_spec(i, r):
    c = orig_make_spec(i, r)
    c["_hair_style"] = ["short", "bun", "long", "ponytail"][(i * 5 + i // 4) % 4]
    return c
g.draw_char = draw_char; g.make_spec = make_spec

# patch hood/hat colours so they never match the hair analogue: wrap render's use via post-fix in a custom render
_orig_render = g.render
def render(i, r):
    # call the original, but pre-seed palette choice by monkeypatching jitter-based hw colour after creation is not possible; instead retry until safe
    for attempt in range(20):
        rr = random.Random(g.SEED + i + 1000 * attempt)
        img, meta = _orig_render(i, rr)
        if meta["headwear_colour"] is None or ANALOG.get(meta["truth"]["hair_colour"]) != meta["headwear_colour"]: return img, meta
    return img, meta
if __name__ == "__main__":
    os.makedirs(os.path.join(OUT, "images_v2"), exist_ok=True)
    attrs = ["robe_colour", "hair_colour", "headwear", "eyewear", "held_item"]
    manifest = []
    for i in range(40):
        img, meta = render(i, None)
        name = f"img_{i:02d}.png"; img.save(os.path.join(OUT, "images_v2", name))
        rr = random.Random(g.SEED * 3 + i); order = attrs[:]; rr.shuffle(order)
        wrong = {a: g.wrong_value(a, meta["truth"][a], rr) for a in attrs}
        meta.update({"file": name, "wrong": wrong, "variant_B_wrong": order[:3], "variant_C_wrong": order[3:]}); manifest.append(meta)
    json.dump(manifest, open(os.path.join(OUT, "manifest_v2.json"), "w"), indent=1)
    sheet = Image.new("RGB", (8 * 160, 5 * 160), "white")
    for i in range(40): sheet.paste(Image.open(os.path.join(OUT, "images_v2", f"img_{i:02d}.png")).resize((160, 160)), ((i % 8) * 160, (i // 8) * 160))
    sheet.save(os.path.join(OUT, "contact_sheet_v2.png"))
    from collections import Counter
    for a in attrs: print(a, dict(Counter(m["truth"][a] for m in manifest)))
    print("two-char:", sum(m["n_characters"] == 2 for m in manifest), "sizes", dict(Counter(m["size"] for m in manifest)), "effects", dict(Counter(m["effect"] for m in manifest)))
