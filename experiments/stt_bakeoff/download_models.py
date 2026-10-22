"""STT bake-off downloads (about 2.4 GB; the connection is about 0.9 MB/s, so ~45 minutes):
  Parakeet TDT 0.6B v3, ONNX int8 (istupakov/parakeet-tdt-0.6b-v3-onnx): encoder 0.65 GB + decoder 0.02 GB + vocab/config
  Whisper large-v3-turbo (openai/whisper-large-v3-turbo): 1.62 GB safetensors + tokenizer/config"""
import time
from huggingface_hub import snapshot_download
t = time.time()
p = snapshot_download("istupakov/parakeet-tdt-0.6b-v3-onnx", allow_patterns=["config.json", "vocab.txt", "nemo128.onnx", "encoder-model.int8.onnx", "decoder_joint-model.int8.onnx"])
print("parakeet:", p, f"{time.time()-t:.0f}s", flush=True)
t = time.time()
p = snapshot_download("openai/whisper-large-v3-turbo", allow_patterns=["*.json", "model.safetensors", "*.txt"])
print("whisper:", p, f"{time.time()-t:.0f}s", flush=True)
print("done")
