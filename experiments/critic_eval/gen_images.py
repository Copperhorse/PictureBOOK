"""Deterministic generator of 40 labelled cartoon-character test images for the critic evaluation.
Ground truth per image goes to manifest.json. Run: python3 gen_images.py"""
import json, random, math, os
from PIL import Image, ImageDraw, ImageFilter

SEED = 20261009
OUT = os.path.dirname(os.path.abspath(__file__))
SS = 2                       # supersampling factor
W = 512
PALETTE = {"red": (200, 40, 45), "orange": (235, 130, 40), "pink": (240, 130, 170), "blue": (50, 90, 200),
           "purple": (120, 70, 170), "green": (60, 150, 80), "yellow": (240, 205, 60)}
CONFUSABLE = {"red": ["orange", "pink"], "orange": ["red", "yellow"], "pink": ["red", "purple"],
              "blue": ["purple", "green"], "purple": ["blue", "pink"], "green": ["blue", "yellow"],
              "yellow": ["orange", "green"]}
HAIR = {"black": (30, 28, 32), "brown": (110, 70, 40), "blonde": (232, 200, 110), "red": (190, 75, 40), "grey": (165, 165, 170)}
HAIR_WRONG = {"black": ["brown"], "brown": ["black", "red"], "blonde": ["brown", "grey"], "red": ["brown", "blonde"], "grey": ["black", "blonde"]}
SKIN = [(245, 215, 190), (225, 180, 140), (160, 110, 80)]
HEADWEAR = ["none", "hood", "pointed hat"]
HEADWEAR_WRONG = {"none": ["pointed hat", "hood"], "hood": ["pointed hat", "none"], "pointed hat": ["hood", "none"]}
EYEWEAR = ["none", "round glasses"]
HELD = ["none", "wooden stick", "basket"]
HELD_WRONG = {"none": ["wooden stick", "basket"], "wooden stick": ["basket", "none"], "basket": ["wooden stick", "none"]}
SIZES = {"small": 0.62, "medium": 0.85, "large": 1.1}

def jitter(c, r, amt=14):
    return tuple(max(0, min(255, v + r.randint(-amt, amt))) for v in c)

def shade(c, f): return tuple(int(v * f) for v in c)

def draw_char(d, cx, ground, ch, r, outline):
    s = SIZES[ch["size"]] * SS
    ol = (35, 30, 40) if outline else None
    lw = max(1, int(3 * s / SS)) if outline else 0
    def poly(pts, fill): d.polygon(pts, fill=fill, outline=ol, width=lw)
    def ell(box, fill): d.ellipse(box, fill=fill, outline=ol, width=lw)
    body_h, body_w_top, body_w_bot = 170 * s, 60 * s, 120 * s
    top = ground - 40 * s - body_h
    robe = ch["_robe_rgb"]
    # boots
    for dx in (-22, 22):
        d.rectangle([cx + dx * s - 14 * s, ground - 40 * s, cx + dx * s + 14 * s, ground], fill=(95, 65, 45), outline=ol, width=lw)
    # robe
    poly([(cx - body_w_top / 2, top), (cx + body_w_top / 2, top), (cx + body_w_bot / 2, ground - 40 * s), (cx - body_w_bot / 2, ground - 40 * s)], robe)
    if ch["shading"]:
        poly([(cx + 4 * s, top), (cx + body_w_top / 2, top), (cx + body_w_bot / 2, ground - 40 * s), (cx + 18 * s, ground - 40 * s)], shade(robe, 0.8))
    # arms
    ell([cx - body_w_top / 2 - 22 * s, top + 8 * s, cx - body_w_top / 2 + 12 * s, top + 100 * s], robe)
    ell([cx + body_w_top / 2 - 12 * s, top + 8 * s, cx + body_w_top / 2 + 22 * s, top + 100 * s], robe)
    hand_r = (cx + body_w_top / 2 + 5 * s, top + 105 * s)
    ell([hand_r[0] - 9 * s, hand_r[1] - 9 * s, hand_r[0] + 9 * s, hand_r[1] + 9 * s], ch["_skin"])
    # held item
    if ch["held"] == "wooden stick":
        d.line([(hand_r[0], hand_r[1]), (hand_r[0] + 40 * s, hand_r[1] - 95 * s)], fill=(125, 85, 45), width=int(7 * s))
    elif ch["held"] == "basket":
        bx, by = hand_r[0] + 6 * s, hand_r[1] + 6 * s
        d.arc([bx - 24 * s, by - 34 * s, bx + 24 * s, by + 10 * s], 180, 360, fill=(110, 75, 40), width=int(5 * s))
        poly([(bx - 30 * s, by), (bx + 30 * s, by), (bx + 22 * s, by + 38 * s), (bx - 22 * s, by + 38 * s)], (170, 120, 60))
    # head
    hr = 42 * s
    hx, hy = cx, top - hr + 8 * s
    skin = ch["_skin"]
    hair = HAIR[ch["hair"]]
    # hair behind head
    ell([hx - hr - 6 * s, hy - hr - 4 * s, hx + hr + 6 * s, hy + hr + 14 * s], hair)
    ell([hx - hr, hy - hr, hx + hr, hy + hr], skin)
    # bangs
    d.pieslice([hx - hr - 2 * s, hy - hr - 2 * s, hx + hr + 2 * s, hy + hr * 0.4], 180, 360, fill=hair)
    # eyes + smile
    for dx in (-15, 15):
        ell([hx + dx * s - 4 * s, hy - 2 * s, hx + dx * s + 4 * s, hy + 6 * s], (30, 30, 30))
    d.arc([hx - 14 * s, hy + 8 * s, hx + 14 * s, hy + 30 * s], 20, 160, fill=(120, 40, 40), width=max(1, int(3 * s / SS)))
    # eyewear
    if ch["eyewear"] == "round glasses":
        gr = 13 * s
        for dx in (-15, 15):
            d.ellipse([hx + dx * s - gr, hy + 2 * s - gr, hx + dx * s + gr, hy + 2 * s + gr], outline=(25, 25, 30), width=max(2, int(3.5 * s / SS)))
        d.line([(hx - 15 * s + gr, hy + 2 * s), (hx + 15 * s - gr, hy + 2 * s)], fill=(25, 25, 30), width=max(2, int(3 * s / SS)))
    # headwear
    hw = ch["headwear"]
    if hw != "none":
        col = ch["_hw_rgb"]
        if hw == "hood":
            d.pieslice([hx - hr - 12 * s, hy - hr - 14 * s, hx + hr + 12 * s, hy + hr + 6 * s], 180, 360, fill=col, outline=ol, width=lw)
            d.rectangle([hx - hr - 12 * s, hy - 8 * s, hx - hr + 2 * s, hy + hr * 0.7], fill=col)
            d.rectangle([hx + hr - 2 * s, hy - 8 * s, hx + hr + 12 * s, hy + hr * 0.7], fill=col)
        else:
            poly([(hx - hr - 10 * s, hy - hr * 0.55), (hx + hr + 10 * s, hy - hr * 0.55), (hx + 4 * s, hy - hr - 85 * s)], col)
            ell([hx - hr - 22 * s, hy - hr * 0.7, hx + hr + 22 * s, hy - hr * 0.35], shade(col, 0.85))

def distractors(d, r, used):
    names = [n for n in PALETTE if n != used]
    for _ in range(r.randint(2, 4)):
        col = jitter(PALETTE[r.choice(names + [used] * 2)], r)
        kind = r.choice(["balloon", "flower", "house", "tree"])
        x, y = r.randint(30, 480) * SS, r.randint(70, 330) * SS
        s = r.randint(18, 40) * SS
        if kind == "balloon":
            d.ellipse([x - s, y - s * 1.2, x + s, y + s * 1.2], fill=col); d.line([(x, y + s * 1.2), (x, y + s * 3)], fill=(60, 60, 60), width=SS)
        elif kind == "flower":
            for a in range(0, 360, 72):
                d.ellipse([x + math.cos(math.radians(a)) * s * 0.8 - s * 0.6, y + math.sin(math.radians(a)) * s * 0.8 - s * 0.6,
                           x + math.cos(math.radians(a)) * s * 0.8 + s * 0.6, y + math.sin(math.radians(a)) * s * 0.8 + s * 0.6], fill=col)
            d.ellipse([x - s * 0.4, y - s * 0.4, x + s * 0.4, y + s * 0.4], fill=(250, 230, 120))
        elif kind == "house":
            d.rectangle([x - s, y, x + s, y + s * 1.4], fill=col); d.polygon([(x - s * 1.2, y), (x + s * 1.2, y), (x, y - s)], fill=shade(col, 0.7))
        else:
            d.rectangle([x - s * 0.2, y, x + s * 0.2, y + s * 1.6], fill=(100, 70, 40)); d.ellipse([x - s, y - s * 1.3, x + s, y + s * 0.4], fill=col)

def make_spec(i, r):
    ch = {"size": ["small", "medium", "large"][i % 3],
          "robe": list(PALETTE)[i % 7],
          "hair": list(HAIR)[(i * 3 + 1) % 5],
          "headwear": HEADWEAR[(i // 2) % 3],
          "eyewear": EYEWEAR[(i // 3) % 2],
          "held": HELD[(i // 2 + i // 5) % 3]}
    return ch

def render(i, r):
    img = Image.new("RGB", (W * SS, W * SS), (200, 225, 245) if i % 4 else (250, 238, 215))
    d = ImageDraw.Draw(img)
    ground = 440 * SS
    d.rectangle([0, 380 * SS, W * SS, W * SS], fill=(140, 195, 120) if i % 3 else (215, 195, 150))
    chars = [make_spec(i, r)]
    two = i % 3 == 1 and i >= 4
    target_side = "left" if i % 2 == 0 else "right"
    if two:
        other = make_spec(i + 17, r)
        # the other character wears a colour confusable with the target's robe
        other["robe"] = r.choice(CONFUSABLE[chars[0]["robe"]]); other["size"] = r.choice(["small", "medium", "large"])
        other["hair"] = r.choice(list(HAIR)); other["headwear"] = r.choice(HEADWEAR); other["eyewear"] = r.choice(EYEWEAR)
        chars.append(other)
    for c in chars:
        c["_robe_rgb"] = jitter(PALETTE[c["robe"]], r)
        c["_skin"] = r.choice(SKIN)
        c["shading"] = r.random() < 0.5
        hwc = r.choice(list(PALETTE)); c["_hw_name"] = hwc; c["_hw_rgb"] = jitter(PALETTE[hwc], r)
    distractors(d, r, chars[0]["robe"])
    outline = i % 2 == 0
    if two:
        xs = [150 * SS, 360 * SS] if target_side == "left" else [360 * SS, 150 * SS]
        for c, x in zip(chars, xs): draw_char(d, x, ground, c, r, outline)
    else:
        draw_char(d, 256 * SS, ground, chars[0], r, outline)
    img = img.resize((W, W), Image.LANCZOS)
    effect = None
    if i % 7 == 3: img = img.filter(ImageFilter.GaussianBlur(1.6)); effect = "blur"
    elif i % 7 == 5:
        px = img.load(); nr = random.Random(i)
        for _ in range(W * W // 6):
            x, y = nr.randrange(W), nr.randrange(W); v = nr.randint(-35, 35)
            p = px[x, y]; px[x, y] = tuple(max(0, min(255, c + v)) for c in p)
        effect = "noise"
    t = chars[0]
    truth = {"robe_colour": t["robe"], "hair_colour": t["hair"], "headwear": t["headwear"], "eyewear": t["eyewear"], "held_item": t["held"]}
    return img, {"target": ("the character on the " + target_side) if two else "the character", "n_characters": len(chars),
                 "size": t["size"], "effect": effect, "outline": outline, "truth": truth,
                 "headwear_colour": t["_hw_name"] if t["headwear"] != "none" else None}

def wrong_value(attr, true, r):
    if attr == "robe_colour": return r.choice(CONFUSABLE[true])
    if attr == "hair_colour": return r.choice(HAIR_WRONG[true])
    if attr == "headwear": return r.choice(HEADWEAR_WRONG[true])
    if attr == "eyewear": return "round glasses" if true == "none" else "none"
    if attr == "held_item": return r.choice(HELD_WRONG[true])

if __name__ == "__main__":
    r = random.Random(SEED)
    manifest = []
    os.makedirs(os.path.join(OUT, "images"), exist_ok=True)
    attrs = ["robe_colour", "hair_colour", "headwear", "eyewear", "held_item"]
    for i in range(40):
        img, meta = render(i, random.Random(SEED + i))
        name = f"img_{i:02d}.png"; img.save(os.path.join(OUT, "images", name))
        rr = random.Random(SEED * 3 + i)
        order = attrs[:]; rr.shuffle(order)
        wrongset_b, wrongset_c = order[:3], order[3:]
        wrong = {a: wrong_value(a, meta["truth"][a], rr) for a in attrs}
        meta.update({"file": name, "wrong": wrong, "variant_B_wrong": wrongset_b, "variant_C_wrong": wrongset_c})
        manifest.append(meta)
    json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w"), indent=1)
    # contact sheet
    sheet = Image.new("RGB", (8 * 160, 5 * 160), "white")
    for i in range(40):
        im = Image.open(os.path.join(OUT, "images", f"img_{i:02d}.png")).resize((160, 160))
        sheet.paste(im, ((i % 8) * 160, (i // 8) * 160))
    sheet.save(os.path.join(OUT, "contact_sheet.png"))
    # coverage report
    from collections import Counter
    for a in attrs: print(a, dict(Counter(m["truth"][a] for m in manifest)))
    print("two-character images:", sum(m["n_characters"] == 2 for m in manifest), "| effects:", dict(Counter(m["effect"] for m in manifest)), "| sizes:", dict(Counter(m["size"] for m in manifest)))
    print("wrong-pair counts:", dict(Counter((m["truth"][a], m["wrong"][a]) for m in manifest for a in attrs if a in ("robe_colour",))))
