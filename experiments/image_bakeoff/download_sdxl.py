"""Download SDXL base 1.0 (fp16 components only, about 7 GB) and the IP-Adapter Plus (ViT-H) weights plus its CLIP ViT-H image encoder (about 3.4 GB).
The connection is about 0.9 MB/s, so this takes roughly 3 hours; it is resumable."""
import time
from huggingface_hub import snapshot_download
t = time.time()
p = snapshot_download("stabilityai/stable-diffusion-xl-base-1.0", allow_patterns=[
    "model_index.json", "scheduler/*", "tokenizer/*", "tokenizer_2/*", "text_encoder/config.json", "text_encoder/model.fp16.safetensors",
    "text_encoder_2/config.json", "text_encoder_2/model.fp16.safetensors", "unet/config.json", "unet/diffusion_pytorch_model.fp16.safetensors",
    "vae/config.json", "vae/diffusion_pytorch_model.fp16.safetensors"])
print("sdxl:", p, f"{time.time()-t:.0f}s", flush=True)
t = time.time()
p = snapshot_download("h94/IP-Adapter", allow_patterns=["sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors", "models/image_encoder/config.json", "models/image_encoder/model.safetensors"])
print("ip-adapter:", p, f"{time.time()-t:.0f}s", flush=True)
print("done")
