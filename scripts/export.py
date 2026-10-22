"""Stage 6: pages + story text -> book.pdf (square page: picture on top, story text below). usage: python3 export.py <run_dir>"""
import sys, textwrap
from PIL import Image, ImageDraw, ImageFont
from common import Run, timed
run = Run(sys.argv[1]); plan = run.load("plan.json")
W = 1024; BAND = 220; BG = (250, 246, 238)
def font(size):
    for f in ("DejaVuSerif.ttf", "/usr/share/fonts/TTF/DejaVuSerif.ttf", "/usr/share/fonts/noto/NotoSerif-Regular.ttf"):
        try: return ImageFont.truetype(f, size)
        except OSError: pass
    return ImageFont.load_default()
pages = []
with timed(run, "export"):
    title = Image.new("RGB", (W, W + BAND), BG); d = ImageDraw.Draw(title)
    d.multiline_text((W // 2, (W + BAND) // 2), "\n".join(textwrap.wrap(plan["title"], 22)), font=font(64), fill=(60, 50, 40), anchor="mm", align="center"); pages.append(title)
    for p in plan["pages"]:
        im = Image.open(run.p("pages", f"page_{p['index']:02d}.png")).convert("RGB").resize((W, W))
        canvas = Image.new("RGB", (W, W + BAND), BG); canvas.paste(im, (0, 0)); d = ImageDraw.Draw(canvas)
        d.multiline_text((W // 2, W + BAND // 2), "\n".join(textwrap.wrap(p["story_text"], 52)), font=font(30), fill=(50, 42, 34), anchor="mm", align="center"); pages.append(canvas)
    pages[0].save(run.p("book.pdf"), save_all=True, append_images=pages[1:], resolution=110)
print("wrote", run.p("book.pdf"))
