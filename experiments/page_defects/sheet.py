"""usage: python3 sheet.py <out.png> <img1> <img2> ... (2x2 grid, 700 px each, captioned with the file name)"""
import sys, os
from PIL import Image, ImageDraw
out, files = sys.argv[1], sys.argv[2:]
s = Image.new("RGB", (1400, 1400), "white"); d = ImageDraw.Draw(s)
for i, f in enumerate(files):
    im = Image.open(f).convert("RGB").resize((700, 700)); x, y = (i % 2) * 700, (i // 2) * 700; s.paste(im, (x, y))
    d.rectangle([x, y, x + 330, y + 22], fill="black"); d.text((x + 4, y + 4), os.path.basename(f)[:48] if "runs" not in f else "/".join(f.split("/")[-3:])[:48], fill="white")
s.save(out)
