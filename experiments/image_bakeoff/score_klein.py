"""Score the klein outputs with the Gemma 4 E4B critic (server must be running on --port, started with 1120 image tokens).
Spec check: every image is checked with variant A (true spec values) and with wrong values (B: three attributes, C: two attributes).
Pair check: derived poses/repairs vs the reference (reference-vs-candidate comparison)."""
import argparse, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "critic_eval"))
import run_critic as R, run_pairs as P
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=18080); ap.add_argument("--tag", default="klein_bnb4"); ap.add_argument("--stage", default="spec,pair"); ap.add_argument("--prefix", default=""); ap.add_argument("--ref", default="ref_flat_s1"); ap.add_argument("--suffix", default=""); a = ap.parse_args()
stages = set(a.stage.split(","))
D = os.path.join(HERE, "out", a.tag)
TRUE = {"robe_colour": "deep blue", "hair_colour": "dark brown", "headwear": "none", "eyewear": "none", "held_item": "wooden stick"}
WRONG = {"robe_colour": "purple", "hair_colour": "blonde", "headwear": "pointed hat", "eyewear": "round glasses", "held_item": "basket"}
B_SET, C_SET = ["robe_colour", "headwear", "held_item"], ["hair_colour", "eyewear"]
names = sorted(f[:-4] for f in os.listdir(D) if f.endswith(".png"))
single = [n for n in names if n.startswith(a.prefix) and n.startswith(("ref_", "pose_", "pose2_", "scene_p4_", "repair_"))]
def pair_body(ref_path, cand_path):
    lines = ["Compare the character in image 2 with the character in image 1. Answer all five attributes in this order:"] + [f"{i}. {x} ({R.DESC[x]})" for i, x in enumerate(R.ATTRS, 1)]
    return {"model": "x", "temperature": 0.0, "max_tokens": 700, "logprobs": True, "top_logprobs": 5, "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_schema", "json_schema": {"name": "pair", "strict": True, "schema": P.SCHEMA}},
            "messages": [{"role": "system", "content": P.SYSTEM}, {"role": "user", "content": [{"type": "image_url", "image_url": {"url": R.b64(ref_path)}}, {"type": "image_url", "image_url": {"url": R.b64(cand_path)}}, {"type": "text", "text": "\n".join(lines)}]}]}
resspec = open(os.path.join(HERE, "results", f"{a.tag}_critic_spec{a.suffix}.jsonl"), "w") if "spec" in stages else None
respair = open(os.path.join(HERE, "results", f"{a.tag}_critic_pair{a.suffix}.jsonl"), "w") if "pair" in stages else None
for n in (single if "spec" in stages else []):
    truth = dict(TRUE)
    if n == "repair_robe_red": truth["robe_colour"] = "red"
    if n == "repair_robe_purple": truth["robe_colour"] = "purple"
    wrong = dict(WRONG)
    if truth["robe_colour"] == "purple": wrong["robe_colour"] = "blue"
    if truth["robe_colour"] == "red": wrong["robe_colour"] = "green"
    variants = {"A": dict(truth), "B": {k: (wrong[k] if k in B_SET else truth[k]) for k in R.ATTRS}, "C": {k: (wrong[k] if k in C_SET else truth[k]) for k in R.ATTRS}}
    for v, exp in variants.items():
        body = R.build_request({"target": "the boy character"}, exp, "off", 700, os.path.join(D, n + ".png"))
        r, dt = R.call(a.port, body); c = r["choices"][0]
        try: checks = json.loads(c["message"]["content"])["checks"]
        except Exception: checks = None
        resspec.write(json.dumps({"kind": "spec", "image": n, "variant": v, "expected": exp, "truth": truth, "checks": checks, "p_true": R.match_probs(c), "latency": dt}) + "\n"); resspec.flush()
    print("spec", n, flush=True)
ref = a.ref
for n in ([x for x in names if x.startswith(a.prefix) and x.startswith(("pose_", "pose2_", "repair_"))] if "pair" in stages else []):
    body = pair_body(os.path.join(D, ref + ".png"), os.path.join(D, n + ".png"))
    r, dt = R.call(a.port, body); c = r["choices"][0]
    try: checks = json.loads(c["message"]["content"])["checks"]
    except Exception: checks = None
    respair.write(json.dumps({"kind": "pair", "image": n, "ref": ref, "checks": checks, "p_true": R.match_probs(c), "latency": dt}) + "\n"); respair.flush(); print("pair", n, flush=True)
