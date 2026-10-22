"""SDXL base 1.0 (fp16) suite, mirroring klein_suite.py on the same prompts. Everything runs with model CPU offload (fp16 SDXL + IP-Adapter encoder does not fit on 8 GB: measured OOM).
Three invocations keep RAM under the 11 GB cap:
  --only refs,plates,scenes    plain SDXL (no adapter)
  --only poses                 IP-Adapter Plus: the CLIP ViT-H encoder runs once on the GPU to embed the reference, is freed, then the pipeline loads without it
  --only harmonise             low-denoise img2img over the klein ref_compose page
usage: systemd-run --user --scope -p MemoryMax=11G -p MemorySwapMax=0 python3 sdxl_suite.py --tag sdxl_fp16 --only refs,plates,scenes"""
import argparse, gc, glob, os, sys, time
import torch
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bakeoff_common as B

ap = argparse.ArgumentParser(); ap.add_argument("--tag", default="sdxl_fp16"); ap.add_argument("--only", default="refs,plates,scenes"); ap.add_argument("--styles", default="crayon,flat"); ap.add_argument("--steps", type=int, default=30); ap.add_argument("--quant", default="", help="nf4 or int8: quantise the UNet with bitsandbytes at load time (no offload)"); a = ap.parse_args()
OUT = os.path.join(B.HERE, "out", a.tag); os.makedirs(OUT, exist_ok=True); os.makedirs(os.path.join(B.HERE, "results"), exist_ok=True)
RES = os.path.join(B.HERE, "results", f"{a.tag}.jsonl")
B.require_ram(6.0)
hub = os.path.expanduser("~/.cache/huggingface/hub")
sdxl = glob.glob(f"{hub}/models--stabilityai--stable-diffusion-xl-base-1.0/snapshots/*")[0]
ipa = glob.glob(f"{hub}/models--h94--IP-Adapter/snapshots/*")[0]
chars, envs, pages = B.load_mock(); prince = chars["Seventh Prince"]
styles = a.styles.split(","); only = set(a.only.split(",")); use_ip = "poses" in only
NEG = "text, letters, lettering, caption, watermark, signature, blurry, deformed hands, extra limbs, photo, realistic"
NT = " No text, no lettering."
def load(n):
    p = os.path.join(OUT, n + ".png"); return Image.open(p).convert("RGB") if os.path.exists(p) else None
from diffusers import StableDiffusionXLPipeline, StableDiffusionXLImg2ImgPipeline
ip_embeds = {}
if use_ip:
    from transformers import CLIPVisionModelWithProjection, CLIPImageProcessor
    ref = load(f"ref_{a.styles.split(',')[0]}_s1")
    assert ref is not None, "run --only refs first"
    enc = CLIPVisionModelWithProjection.from_pretrained(os.path.join(ipa, "models", "image_encoder"), torch_dtype=torch.float16).to("cuda").eval()
    proc = CLIPImageProcessor()
    with torch.no_grad():
        px = proc(images=ref, return_tensors="pt").pixel_values.to("cuda", torch.float16)
        pos = enc(px, output_hidden_states=True).hidden_states[-2]; neg = enc(torch.zeros_like(px), output_hidden_states=True).hidden_states[-2]
    ip_embeds["ref"] = torch.cat([neg[None], pos[None]], dim=0).cpu()          # [2, 1, tokens, dim] as expected by ip_adapter_image_embeds with CFG
    del enc; gc.collect(); torch.cuda.empty_cache()
    B.log_json(RES, {"event": "ip_embeds_ready", "shape": list(ip_embeds["ref"].shape), "vram_after_free_mib": int(torch.cuda.memory_reserved() / 2**20)})
with B.GpuSampler() as gpu:
    t = time.time()
    extra = {}
    if a.quant:
        from diffusers import UNet2DConditionModel, BitsAndBytesConfig
        qc = BitsAndBytesConfig(load_in_8bit=True) if a.quant == "int8" else BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
        extra["unet"] = UNet2DConditionModel.from_pretrained(sdxl, subfolder="unet", variant="fp16", torch_dtype=torch.float16, quantization_config=qc)
        from diffusers import AutoencoderKL
        extra["vae"] = AutoencoderKL.from_pretrained(sdxl, subfolder="vae", variant="fp16", torch_dtype=torch.float32)   # fp32 VAE avoids the fp16 upcast path that failed after the first image
        B.log_json(RES, {"event": "unet_quantised", "quant": a.quant, "unet_gib": round(extra["unet"].get_memory_footprint() / 2**30, 2)})
    pipe = StableDiffusionXLPipeline.from_pretrained(sdxl, torch_dtype=torch.float16, variant="fp16", use_safetensors=True, **extra)
    if use_ip: pipe.load_ip_adapter(ipa, subfolder="sdxl_models", weight_name="ip-adapter-plus_sdxl_vit-h.safetensors", image_encoder_folder=None)
    pipe.vae.enable_tiling()
    if a.quant: pipe.to('cuda')
    else: pipe.enable_model_cpu_offload()
    B.log_json(RES, {"event": "loaded", "mode": "ip" if use_ip else "plain", "quant": a.quant or "fp16+offload", "vram_alloc_gib": round(torch.cuda.memory_allocated() / 2**30, 2), "seconds": round(time.time() - t, 1), "peak_rss_gib": round(B.peak_rss_gib(), 2)})
    def gen(name, prompt, seed=1, ip_scale=None, res=1024):
        path = os.path.join(OUT, name + ".png")
        if os.path.exists(path): return load(name)
        kw = {}
        if use_ip: pipe.set_ip_adapter_scale(ip_scale); kw["ip_adapter_image_embeds"] = [ip_embeds["ref"].to("cuda", torch.float16)]
        gpu.reset(); torch.cuda.reset_peak_memory_stats(); t = time.time()
        try:
            if a.quant:   # denoise in fp16 with the quantised UNet, decode the latents ourselves with the fp32 tiled VAE
                lat = pipe(prompt=prompt, negative_prompt=NEG, height=res, width=res, num_inference_steps=a.steps, guidance_scale=6.0, generator=torch.Generator("cuda").manual_seed(seed), output_type="latent", **kw).images
                with torch.no_grad(): im = pipe.image_processor.postprocess(pipe.vae.decode(lat.to(torch.float32) / pipe.vae.config.scaling_factor, return_dict=False)[0], output_type="pil")[0]
            else:
                im = pipe(prompt=prompt, negative_prompt=NEG, height=res, width=res, num_inference_steps=a.steps, guidance_scale=6.0, generator=torch.Generator("cuda").manual_seed(seed), **kw).images[0]
        except torch.cuda.OutOfMemoryError:
            B.log_json(RES, {"event": "oom", "name": name}); torch.cuda.empty_cache(); return None
        torch.cuda.synchronize(); dt = time.time() - t; im.save(path)
        B.log_json(RES, {"event": "image", "name": name, "seconds": round(dt, 1), "seed": seed, "steps": a.steps, "res": res, "ip_scale": ip_scale, "torch_peak_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
                         "nvsmi_peak_mib": gpu.peak, "peak_rss_gib": round(B.peak_rss_gib(), 2), "prompt": prompt})
        print(name, f"{dt:.1f}s", f"rss {B.peak_rss_gib():.1f}GiB", flush=True); return im
    if "refs" in only:
        for st in styles:
            for sd in (1, 2, 3): gen(f"ref_{st}_s{sd}", B.character_prompt_short(prince, st), seed=sd)
    if "plates" in only:
        for st in styles:
            for sd in (1, 2): gen(f"plate_arcania_{st}_s{sd}", B.plate_prompt_short(envs["Arcania"], st), seed=sd)
    if "scenes" in only:
        for st in styles:
            for sd in (1, 2): gen(f"scene_p4_{st}_s{sd}", B.scene_prompt_short(pages[3], chars, envs["Spell courtyard"], st), seed=sd)
    if use_ip:
        for key, pose, expr in (("sit_shy", "sitting on a stone step with the stick across the lap", "shy"), ("walk_determined", "walking to the right", "determined"), ("wave_proud", "waving one hand while the other holds the stick", "proud"),
                                ("stick_raised", "holding the wooden stick raised in the right hand", "determined"), ("stand_happy", "standing with the stick held at the side", "happy")):
            for sc in (0.6, 0.9):
                gen(f"pose_ipa{int(sc*10)}_{key}", B.character_prompt_short(prince, styles[0], pose=f"{pose}, {expr} expression"), seed=10, ip_scale=sc)
    if "harmonise" in only:
        src = os.path.join(B.HERE, "out", "klein_bnb4", "compose_p3_refs.png")
        i2i = StableDiffusionXLImg2ImgPipeline(**{k: v for k, v in pipe.components.items() if k in ("vae", "text_encoder", "text_encoder_2", "tokenizer", "tokenizer_2", "unet", "scheduler")}); i2i.enable_model_cpu_offload()
        init = Image.open(src).convert("RGB").resize((1024, 1024))
        for strength in (0.2, 0.35):
            path = os.path.join(OUT, f"harmonise_{int(strength*100)}.png")
            if os.path.exists(path): continue
            t = time.time(); im = i2i(prompt=B.STYLES["flat"] + ", soft lighting, characters blended into the scene", negative_prompt=NEG, image=init, strength=strength, num_inference_steps=a.steps, guidance_scale=6.0, generator=torch.Generator("cuda").manual_seed(5)).images[0]
            im.save(path); B.log_json(RES, {"event": "image", "name": f"harmonise_{int(strength*100)}", "seconds": round(time.time() - t, 1), "strength": strength}); print("harmonise", strength, flush=True)
B.log_json(RES, {"event": "done", "peak_rss_gib": round(B.peak_rss_gib(), 2)})
