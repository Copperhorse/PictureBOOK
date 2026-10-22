"""Where the pipeline finds its models. The ONE place for these locations: the stage scripts load models from here and the app's
first-run check (sidecar diagnostics) looks for exactly the same files, so the check can never disagree with what the pipeline does.
Pure standard library on purpose (the sidecar imports this file without torch)."""
import glob, os

def home(): return os.path.expanduser("~")
def models_dir(): return os.environ.get("PICTUREBOOK_MODELS") or os.path.join(home(), "models")
def hf_hub(): return os.environ.get("HF_HUB_CACHE") or os.path.join(os.environ.get("HF_HOME") or os.path.join(home(), ".cache", "huggingface"), "hub")

KLEIN_REPO = "hlhc/FLUX.2-klein-4B-bnb-4bit"          # FLUX.2 klein 4B, community NF4 bundle (4.8 GB)
WHISPER_REPO = "openai/whisper-large-v3-turbo"        # speech to text (about 1.6 GB)

def gemma_e4b():
    d = os.path.join(models_dir(), "gemma_4")
    return (os.path.join(d, "gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf"), os.path.join(d, "mmproj-F16.gguf"))
def qwen35_4b():
    d = os.path.join(models_dir(), "qwen3_5")
    return (os.path.join(d, "Qwen3.5-4B-Q4_K_M.gguf"), os.path.join(d, "mmproj-F16.gguf"))

def hf_snapshot(repo):
    """Newest downloaded snapshot folder of a Hugging Face repo, or None. A folder that has no files yet does not count."""
    snaps = sorted(glob.glob(os.path.join(hf_hub(), "models--" + repo.replace("/", "--"), "snapshots", "*")), key=os.path.getmtime, reverse=True)
    for s in snaps:
        if os.path.isdir(s) and any(True for _ in os.scandir(s)): return s
    return None
