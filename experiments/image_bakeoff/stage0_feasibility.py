"""Stage 0: does FLUX.2 klein 4B (community bnb-NF4 bundle) run on the 8 GB RTX A2000, and how fast / how much memory?
Run under a memory cap:  systemd-run --user --scope -p MemoryMax=11G -p MemorySwapMax=0 python3 stage0_feasibility.py [--offload]
Writes images to out/stage0/ and measurements to results/stage0.jsonl"""
import argparse, gc, glob, os, sys, time, json
import torch
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bakeoff_common as B

ap = argparse.ArgumentParser(); ap.add_argument("--offload", action="store_true", help="use enable_model_cpu_offload instead of putting everything on the GPU")
ap.add_argument("--repo", default="hlhc/FLUX.2-klein-4B-bnb-4bit"); ap.add_argument("--tag", default="stage0_bnb4"); a = ap.parse_args()
OUT = os.path.join(B.HERE, "out", a.tag); os.makedirs(OUT, exist_ok=True); os.makedirs(os.path.join(B.HERE, "results"), exist_ok=True)
RES = os.path.join(B.HERE, "results", f"{a.tag}.jsonl")
avail = B.require_ram(6.0)
snap = glob.glob(os.path.expanduser(f"~/.cache/huggingface/hub/models--{a.repo.replace('/', '--')}/snapshots/*"))[0]
chars, envs, pages = B.load_mock()
prince, arcania = chars["Seventh Prince"], envs["Arcania"]
rec = lambda **k: (B.log_json(RES, k), print(json.dumps(k), flush=True))
rec(event="start", repo=a.repo, offload=a.offload, ram_available_gib=round(avail, 1), gpu=torch.cuda.get_device_name(0), vram_total_gib=round(torch.cuda.get_device_properties(0).total_memory / 2**30, 2))

with B.GpuSampler() as gpu:
    from diffusers import Flux2KleinPipeline
    t = time.time(); gpu.reset(); torch.cuda.reset_peak_memory_stats()
    pipe = Flux2KleinPipeline.from_pretrained(snap, torch_dtype=torch.bfloat16)
    rec(event="loaded_to_cpu", seconds=round(time.time() - t, 1), peak_rss_gib=round(B.peak_rss_gib(), 2))
    t = time.time()
    try:
        if a.offload: pipe.enable_model_cpu_offload()
        else: pipe.to("cuda")
    except Exception as e:
        rec(event="placement_failed", error=repr(e)[:300]); raise
    rec(event="placed", mode="offload" if a.offload else "gpu", seconds=round(time.time() - t, 1), vram_alloc_gib=round(torch.cuda.memory_allocated() / 2**30, 2), nvsmi_peak_mib=gpu.peak, peak_rss_gib=round(B.peak_rss_gib(), 2))

    def gen(name, prompt, w, h, image=None, seed=1, steps=4, cold=False):
        gpu.reset(); torch.cuda.reset_peak_memory_stats(); torch.cuda.synchronize(); t = time.time()
        g = torch.Generator("cuda").manual_seed(seed)
        try:
            im = pipe(image=image, prompt=prompt, height=h, width=w, num_inference_steps=steps, guidance_scale=1.0, generator=g).images[0]
        except torch.cuda.OutOfMemoryError as e:
            rec(event="oom", name=name, w=w, h=h, error=str(e)[:200]); torch.cuda.empty_cache(); return None
        torch.cuda.synchronize(); dt = time.time() - t; im.save(os.path.join(OUT, name + ".png"))
        rec(event="image", name=name, w=w, h=h, steps=steps, seconds=round(dt, 1), torch_peak_gib=round(torch.cuda.max_memory_allocated() / 2**30, 2), nvsmi_peak_mib=gpu.peak, peak_rss_gib=round(B.peak_rss_gib(), 2), prompt=prompt[:120])
        return im

    p_ref = B.character_prompt(prince, "flat")
    ref = gen("ref_flat_1024_cold", p_ref, 1024, 1024, seed=1)
    ref2 = gen("ref_flat_1024_warm", p_ref, 1024, 1024, seed=2)
    ref768 = gen("ref_flat_768", p_ref, 768, 768, seed=1)
    plate = gen("plate_flat_1024", B.plate_prompt(arcania, "flat"), 1024, 1024, seed=3)
    if ref is not None:
        gen("edit_sitting_shy", B.derive_pose_instruction("sitting on a stone step with hands in lap", "shy"), 1024, 1024, image=[ref], seed=4)
        gen("edit_robe_red", B.repair_instruction("robe", "deep blue", "red"), 1024, 1024, image=[ref], seed=5)
        if plate is not None:
            gen("multiref_prince_in_arcania", "Place the prince from the first image in the wide kingdom scene from the second image, standing on a stone bridge. Keep the prince's appearance exactly as in the first image.", 1024, 1024, image=[ref, plate], seed=6)
rec(event="done", peak_rss_gib=round(B.peak_rss_gib(), 2))
