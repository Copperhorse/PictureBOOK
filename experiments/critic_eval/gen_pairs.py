"""Reference-vs-candidate pairs. For 20 base characters: a reference image and 6 candidates: one control (same character, different background and position)
and five candidates where exactly one attribute differs. Ground truth: which attribute changed."""
import json, os, random
from PIL import Image, ImageDraw
import gen_images_v2 as v2          # patches draw_char / make_spec
import gen_images as g

OUT = os.path.dirname(os.path.abspath(__file__)); SS = g.SS
ATTRS = ["robe_colour", "hair_colour", "headwear", "eyewear", "held_item"]
KEY = {"robe_colour": "robe", "hair_colour": "hair", "headwear": "headwear", "eyewear": "eyewear", "held_item": "held"}

def base_spec(i):
    r = random.Random(g.SEED + 77 + i)
    ch = g.make_spec(i * 2 + 1, r)           # odd indices -> variety
    if ch["headwear"] != "none":
        hwc = r.choice([c for c in g.PALETTE if v2.ANALOG.get(ch["hair"]) != c]); ch["_hw_name"] = hwc; ch["_hw_rgb"] = g.jitter(g.PALETTE[hwc], r)
    else:
        hwc = r.choice(list(g.PALETTE)); ch["_hw_name"] = hwc; ch["_hw_rgb"] = g.jitter(g.PALETTE[hwc], r)
    ch["_robe_rgb"] = g.jitter(g.PALETTE[ch["robe"]], r); ch["_skin"] = r.choice(g.SKIN); ch["shading"] = r.random() < 0.5
    ch["size"] = ["medium", "large", "medium", "small"][i % 4]
    return ch

def render_one(ch, seed, bg, shift):
    r = random.Random(seed)
    img = Image.new("RGB", (g.W * SS, g.W * SS), (200, 225, 245) if bg == 0 else (250, 238, 215)); d = ImageDraw.Draw(img)
    d.rectangle([0, 380 * SS, g.W * SS, g.W * SS], fill=(140, 195, 120) if bg == 0 else (215, 195, 150))
    g.distractors(d, r, ch["robe"])
    g.draw_char(d, (256 + shift) * SS, 440 * SS, ch, r, outline=True)
    return img.resize((g.W, g.W), Image.LANCZOS)

if __name__ == "__main__":
    os.makedirs(os.path.join(OUT, "images_pairs"), exist_ok=True); pairs = []
    for i in range(20):
        base = base_spec(i)
        ref_name = f"ref_{i:02d}.png"; render_one(base, 5000 + i, 0, 0).save(os.path.join(OUT, "images_pairs", ref_name))
        truth = {a: base[KEY[a]] for a in ATTRS}
        rr = random.Random(g.SEED + 999 + i)
        for k, changed in enumerate([None] + ATTRS):
            cand = dict(base)
            if changed:
                new = g.wrong_value(changed, truth[changed], rr); cand[KEY[changed]] = new
                if changed == "robe_colour": cand["_robe_rgb"] = g.jitter(g.PALETTE[new], rr)
                if changed == "headwear" and new != "none": cand["_hw_rgb"] = base["_hw_rgb"]
            # candidate differs in background, position, and a little colour jitter (like a regeneration would)
            cand["_robe_rgb"] = g.jitter(cand["_robe_rgb"], rr, 8)
            name = f"cand_{i:02d}_{k}.png"; render_one(cand, 6000 + i * 10 + k, 1, rr.choice([-60, -30, 30, 60])).save(os.path.join(OUT, "images_pairs", name))
            pairs.append({"ref": ref_name, "cand": name, "changed": changed, "truth_ref": truth,
                          "truth_cand": {a: cand[KEY[a]] for a in ATTRS}, "size": base["size"]})
    json.dump(pairs, open(os.path.join(OUT, "manifest_pairs.json"), "w"), indent=1)
    sheet = Image.new("RGB", (7 * 150, 3 * 150), "white")
    for row, i in enumerate((0, 1, 2)):
        sheet.paste(Image.open(os.path.join(OUT, "images_pairs", f"ref_{i:02d}.png")).resize((150, 150)), (0, row * 150))
        for k in range(6): sheet.paste(Image.open(os.path.join(OUT, "images_pairs", f"cand_{i:02d}_{k}.png")).resize((150, 150)), ((k + 1) * 150, row * 150))
    sheet.save(os.path.join(OUT, "pairs_sheet.png")); print(len(pairs), "pairs;", [ (p['changed'], p['truth_ref'][p['changed']], p['truth_cand'][p['changed']]) for p in pairs[:6] if p['changed']])
