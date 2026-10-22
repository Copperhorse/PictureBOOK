"""Stage 1 suite for FLUX.2 klein 4B: references, plates, scenes, pose derivation by editing, repair, ref_compose.
usage (memory-capped): systemd-run --user --scope -p MemoryMax=11G -p MemorySwapMax=0 python3 klein_suite.py --tag klein_bnb4 [--offload] [--only refs,plates,scenes,poses,repair,compose]
Resumable: existing images are skipped. Images -> out/<tag>/, measurements -> results/<tag>.jsonl"""
import argparse, glob, os, sys, time, json
import torch
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bakeoff_common as B

ap = argparse.ArgumentParser(); ap.add_argument("--repo", default="hlhc/FLUX.2-klein-4B-bnb-4bit"); ap.add_argument("--tag", default="klein_bnb4")
ap.add_argument("--offload", action="store_true"); ap.add_argument("--only", default="refs,plates,scenes,poses,repair,compose"); ap.add_argument("--ref-style", default="flat"); ap.add_argument("--ref-seed", type=int, default=1)
ap.add_argument("--res", type=int, default=1024); a = ap.parse_args()
OUT = os.path.join(B.HERE, "out", a.tag); os.makedirs(OUT, exist_ok=True); os.makedirs(os.path.join(B.HERE, "results"), exist_ok=True)
RES = os.path.join(B.HERE, "results", f"{a.tag}.jsonl")
B.require_ram(6.0)
snap = glob.glob(os.path.expanduser(f"~/.cache/huggingface/hub/models--{a.repo.replace('/', '--')}/snapshots/*"))[0]
chars, envs, pages = B.load_mock(); prince, mage = chars["Seventh Prince"], chars["Arcanian Mage"]
only = set(a.only.split(","))
from diffusers import Flux2KleinPipeline
with B.GpuSampler() as gpu:
    t = time.time(); pipe = Flux2KleinPipeline.from_pretrained(snap, torch_dtype=torch.bfloat16)
    pipe.enable_model_cpu_offload() if a.offload else pipe.to("cuda")
    B.log_json(RES, {"event": "loaded", "seconds": round(time.time() - t, 1), "offload": a.offload, "peak_rss_gib": round(B.peak_rss_gib(), 2)})
    cache = {}
    def load(name):
        p = os.path.join(OUT, name + ".png"); return Image.open(p).convert("RGB") if os.path.exists(p) else None
    def gen(name, prompt, image=None, seed=1, steps=4, res=None):
        res = res or a.res; path = os.path.join(OUT, name + ".png")
        if os.path.exists(path): return load(name)
        gpu.reset(); torch.cuda.reset_peak_memory_stats(); t = time.time()
        try: im = pipe(image=image, prompt=prompt, height=res, width=res, num_inference_steps=steps, guidance_scale=1.0, generator=torch.Generator("cuda").manual_seed(seed)).images[0]
        except torch.cuda.OutOfMemoryError as e:
            B.log_json(RES, {"event": "oom", "name": name}); torch.cuda.empty_cache(); return None
        torch.cuda.synchronize(); dt = time.time() - t; im.save(path)
        B.log_json(RES, {"event": "image", "name": name, "seconds": round(dt, 1), "seed": seed, "steps": steps, "res": res, "n_refs": 0 if image is None else len(image),
                         "torch_peak_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2), "nvsmi_peak_mib": gpu.peak, "peak_rss_gib": round(B.peak_rss_gib(), 2), "prompt": prompt})
        print(name, f"{dt:.1f}s", flush=True); return im
    if "refs" in only:
        for st in B.STYLES:
            for sd in (1, 2, 3): gen(f"ref_{st}_s{sd}", B.character_prompt(prince, st), seed=sd)
        for st in ("flat",): gen(f"mage_{st}_s1", B.character_prompt(mage, st), seed=1)
    if "plates" in only:
        for st in B.STYLES:
            for sd in (1, 2): gen(f"plate_arcania_{st}_s{sd}", B.plate_prompt(envs["Arcania"], st), seed=sd)
        gen("plate_courtyard_flat_s1", B.plate_prompt(envs["Spell courtyard"], "flat"), seed=1)
    if "scenes" in only:
        for st in B.STYLES:
            for sd in (1, 2): gen(f"scene_p4_{st}_s{sd}", B.scene_prompt(pages[3], chars, envs["Spell courtyard"], st), seed=sd)
    ref = load(f"ref_{a.ref_style}_s{a.ref_seed}")
    if "poses" in only and ref is not None:
        for key, pose, expr in (("sit_shy", "sitting on a stone step with hands in lap", "shy"), ("walk_determined", "walking to the right", "determined"), ("wave_proud", "waving one hand", "proud"),
                                ("stick_raised", "holding the wooden stick raised in the right hand", "determined"), ("stand_happy", "standing with arms down", "happy")):
            gen(f"pose_{key}", B.derive_pose_instruction(pose, expr), image=[ref], seed=10)
    if "poses2" in only and ref is not None:
        for key, pose, expr in (("sit_shy", "sitting on a stone step with the stick resting across the lap", "shy"), ("walk_determined", "walking to the right", "determined"), ("wave_proud", "waving one hand while the other holds the stick", "proud"),
                                ("stick_raised", "holding the wooden stick raised in the right hand", "determined"), ("stand_happy", "standing with the stick held at the side", "happy")):
            gen(f"pose2_{key}", B.derive_pose_instruction_v2(pose, expr), image=[ref], seed=10)
    if "repair" in only and ref is not None:
        gen("repair_robe_red", B.repair_instruction("robe", "deep blue", "red"), image=[ref], seed=11)
        gen("repair_robe_purple", B.repair_instruction("robe", "deep blue", "purple"), image=[ref], seed=12)
    if "compose" in only and ref is not None:
        plate, mref = load("plate_courtyard_flat_s1"), load("mage_flat_s1")
        if plate is not None and mref is not None:
            p5 = pages[2]
            gen("compose_p3_refs", "Compose one picture-book page. Image 1 is the courtyard background. Image 2 is the Seventh Prince, image 3 is the tall Arcanian Mage. " + p5["scenario"] + " Keep both characters' appearance exactly as in their reference images; the prince is much shorter than the mage.", image=[plate, ref, mref], seed=20)
            gen("compose_p3_textonly", B.scene_prompt(p5, chars, envs["Spell courtyard"], "flat"), seed=20)
B.log_json(RES, {"event": "done", "peak_rss_gib": round(B.peak_rss_gib(), 2)})
