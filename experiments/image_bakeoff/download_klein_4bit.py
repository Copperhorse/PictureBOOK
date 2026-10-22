"""Download the community pre-quantised bundle hlhc/FLUX.2-klein-4B-bnb-4bit (4.8 GB: bnb-4bit text encoder 2.65 GB, transformer 2.0 GB, VAE).
Chosen first because the connection is about 0.9 MB/s; the official bf16 files can be fetched later for a quality comparison."""
import time
from huggingface_hub import snapshot_download
t = time.time()
p = snapshot_download("hlhc/FLUX.2-klein-4B-bnb-4bit")
print("done:", p, f"{time.time()-t:.0f}s", flush=True)
