"""Critic evaluation runner. usage: run_critic.py --port 18080 --tag e2b_think_on --think on|off [--limit N]
Every image is tested with 3 spec variants: A = all five expected values true; B = three attributes replaced by a
plausible wrong value; C = the other two replaced. So every (image, attribute) gets one true and one wrong test."""
import argparse, base64, json, math, os, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
SET = os.environ.get("DATASET", "")   # "" = v1 (flawed), "_v2" = corrected set
ATTRS = ["robe_colour", "hair_colour", "headwear", "eyewear", "held_item"]
DESC = {"robe_colour": "colour of the character's long robe or coat",
        "hair_colour": "colour of the character's hair (visible at the sides, bangs or beard)",
        "headwear": "what is on the head: none, hood, or pointed hat",
        "eyewear": "none, or round glasses",
        "held_item": "what the character holds in their hand: none, wooden stick, or basket"}
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["checks"], "properties": {"checks": {
    "type": "array", "minItems": 5, "maxItems": 5, "items": {"type": "object", "additionalProperties": False,
    "required": ["attribute", "expected", "observed", "match"], "properties": {
        "attribute": {"enum": ATTRS}, "expected": {"type": "string", "maxLength": 30},
        "observed": {"type": "string", "maxLength": 40}, "match": {"type": "boolean"}}}}}}
SYSTEM = ("You are a strict visual inspector for children's picture-book illustrations. For each check, look at the image and "
          "write what you actually see in 'observed' (a few words) BEFORE deciding 'match'. 'match' is true only if what you see "
          "agrees with 'expected'. Do not assume the expected value is correct. Answer only with JSON.")

def b64(path): return "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()

def build_request(meta, expected, think, max_tokens, img_path, temperature=0.0):
    lines = [f"Inspect {meta['target']} only. Answer all five checks, in this order:"]
    for i, a in enumerate(ATTRS, 1):
        lines.append(f"{i}. {a} ({DESC[a]}) — expected: {expected[a]}")
    body = {"model": "x", "temperature": temperature, "max_tokens": max_tokens, "logprobs": True, "top_logprobs": 5,
            "response_format": {"type": "json_schema", "json_schema": {"name": "critic", "strict": True, "schema": SCHEMA}},
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": [{"type": "image_url", "image_url": {"url": b64(img_path)}}, {"type": "text", "text": "\n".join(lines)}]}]}
    if think == "off": body["chat_template_kwargs"] = {"enable_thinking": False}
    return body

def call(port, body, timeout=900):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": "Bearer critic-test-key"})
    t = time.time(); r = json.load(urllib.request.urlopen(req, timeout=timeout)); return r, time.time() - t

def match_probs(choice):
    """P(true) renormalised over {true,false} for each boolean token in the content, in order."""
    lp = (choice.get("logprobs") or {}).get("content") or []
    out = []
    for t in lp:
        if t["token"].strip() in ("true", "false"):
            p = {"true": 0.0, "false": 0.0}
            for a in t.get("top_logprobs", []) + [{"token": t["token"], "logprob": t["logprob"]}]:
                k = a["token"].strip()
                if k in p: p[k] = max(p[k], math.exp(a["logprob"]))
            s = p["true"] + p["false"]; out.append(p["true"] / s if s else None)
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, required=True); ap.add_argument("--tag", required=True)
    ap.add_argument("--think", choices=["on", "off", "default"], default="off"); ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--max-tokens", type=int, default=0); a = ap.parse_args()
    mt = a.max_tokens or (8192 if a.think != "off" else 700)
    manifest = json.load(open(os.path.join(HERE, f"manifest{SET}.json")))[:a.limit]
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    out = open(os.path.join(HERE, "results", f"{a.tag}.jsonl"), "w")
    n = 0; t0 = time.time()
    for m in manifest:
        truth = m["truth"]
        variants = {"A": dict(truth), "B": {x: (m["wrong"][x] if x in m["variant_B_wrong"] else truth[x]) for x in ATTRS},
                    "C": {x: (m["wrong"][x] if x in m["variant_C_wrong"] else truth[x]) for x in ATTRS}}
        for v, exp in variants.items():
            body = build_request(m, exp, a.think, mt, os.path.join(HERE, f"images{SET}", m["file"]))
            try:
                r, dt = call(a.port, body); c = r["choices"][0]; msg = c["message"]
                rec = {"image": m["file"], "variant": v, "expected": exp, "truth": truth, "latency": dt, "finish": c["finish_reason"],
                       "usage": r.get("usage"), "content": msg.get("content"), "reasoning_chars": len(msg.get("reasoning_content") or ""),
                       "p_true": match_probs(c), "timings": {k: r.get("timings", {}).get(k) for k in ("predicted_n", "predicted_per_second", "prompt_n")}}
            except Exception as e:
                rec = {"image": m["file"], "variant": v, "error": repr(e)[:300], "expected": exp, "truth": truth}
            out.write(json.dumps(rec) + "\n"); out.flush(); n += 1
            if n % 10 == 0: print(f"{a.tag}: {n} requests, {time.time()-t0:.0f}s", flush=True)
    print(f"{a.tag}: done {n} requests in {time.time()-t0:.0f}s")
