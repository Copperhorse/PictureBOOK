"""FLUX.2 klein 4B (community NF4 bundle) on the GPU: generate / edit / multi-reference compose. Whole pipeline on the card (measured at 1024²: 6.9 GiB PyTorch peak allocation, 7.8 GB board peak by nvidia-smi)."""
import torch
from PIL import Image

class Klein:
    def __init__(self, repo=None):
        import modelpaths
        repo = repo or modelpaths.KLEIN_REPO
        from diffusers import Flux2KleinPipeline
        snap = modelpaths.hf_snapshot(repo)
        if snap is None: raise SystemExit(f"the image model {repo} is not downloaded (see the Setup screen)")
        self.pipe = Flux2KleinPipeline.from_pretrained(snap, torch_dtype=torch.bfloat16)
        self.pipe.to("cuda")

    def __call__(self, prompt, images=None, seed=1, res=1024, steps=4):
        imgs = [Image.open(i).convert("RGB") if isinstance(i, str) else i for i in images] if images else None
        g = torch.Generator("cuda").manual_seed(seed)
        out = self.pipe(image=imgs, prompt=prompt, height=res, width=res, num_inference_steps=steps, guidance_scale=1.0, generator=g).images[0]
        torch.cuda.empty_cache()
        return out
