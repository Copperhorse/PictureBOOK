"""Stage 0 download: FLUX.2 klein 4B text encoder + VAE + tokenizer + configs (not the 7.75 GB bf16 transformer) and the Q4_K_M GGUF transformer.
Files go to the normal Hugging Face cache (outside the repo). Usage: python3 download_klein.py [extra GGUF names, e.g. flux-2-klein-4b-Q8_0.gguf]"""
import sys, time
from huggingface_hub import snapshot_download, hf_hub_download
t = time.time()
p = snapshot_download("black-forest-labs/FLUX.2-klein-4B", allow_patterns=["model_index.json", "scheduler/*", "text_encoder/*", "tokenizer/*", "transformer/config.json", "vae/*"])
print("klein base files:", p, f"{time.time()-t:.0f}s", flush=True)
for name in ["flux-2-klein-4b-Q4_K_M.gguf"] + sys.argv[1:]:
    t = time.time(); g = hf_hub_download("unsloth/FLUX.2-klein-4B-GGUF", name); print("gguf:", g, f"{time.time()-t:.0f}s", flush=True)
