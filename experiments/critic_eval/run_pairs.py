"""Reference-vs-candidate critic. usage: run_pairs.py --port 18080 --tag pairs_e2b_img1120 --think off"""
import argparse, json, os, time
import run_critic as R
HERE = R.HERE
ATTRS = R.ATTRS
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["checks"], "properties": {"checks": {"type": "array", "minItems": 5, "maxItems": 5, "items": {
    "type": "object", "additionalProperties": False, "required": ["attribute", "in_reference", "in_candidate", "same"], "properties": {
        "attribute": {"enum": ATTRS}, "in_reference": {"type": "string", "maxLength": 30}, "in_candidate": {"type": "string", "maxLength": 30}, "same": {"type": "boolean"}}}}}}
SYSTEM = ("You compare two picture-book illustrations of the same character: image 1 is the REFERENCE, image 2 is a CANDIDATE that was generated later. "
          "For each attribute, first write what you see in the reference and in the candidate (a few words each), then say whether the attribute is the same. "
          "Ignore differences in background, position and exact shade of the same colour. Answer only with JSON.")
def request(pair, think, max_tokens):
    lines = ["Compare the character in image 2 with the character in image 1. Answer all five attributes in this order:"]
    for i, a in enumerate(ATTRS, 1): lines.append(f"{i}. {a} ({R.DESC[a]})")
    body = {"model": "x", "temperature": 0.0, "max_tokens": max_tokens, "logprobs": True, "top_logprobs": 5,
            "response_format": {"type": "json_schema", "json_schema": {"name": "pair", "strict": True, "schema": SCHEMA}},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": R.b64(os.path.join(HERE, "images_pairs", pair["ref"]))}},
                {"type": "image_url", "image_url": {"url": R.b64(os.path.join(HERE, "images_pairs", pair["cand"]))}},
                {"type": "text", "text": "\n".join(lines)}]}]}
    if think == "off": body["chat_template_kwargs"] = {"enable_thinking": False}
    return body
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, required=True); ap.add_argument("--tag", required=True)
    ap.add_argument("--think", default="off"); ap.add_argument("--limit", type=int, default=120); a = ap.parse_args()
    pairs = json.load(open(os.path.join(HERE, "manifest_pairs.json")))[:a.limit]
    out = open(os.path.join(HERE, "results", f"{a.tag}.jsonl"), "w"); t0 = time.time()
    for n, p in enumerate(pairs, 1):
        try:
            r, dt = R.call(a.port, request(p, a.think, 700 if a.think == "off" else 8192)); c = r["choices"][0]
            rec = {"pair": p, "latency": dt, "finish": c["finish_reason"], "usage": r["usage"], "content": c["message"].get("content"), "p_true": R.match_probs(c)}
        except Exception as e: rec = {"pair": p, "error": repr(e)[:300]}
        out.write(json.dumps(rec) + "\n"); out.flush()
        if n % 20 == 0: print(f"{a.tag}: {n}/{len(pairs)} {time.time()-t0:.0f}s", flush=True)
    print(f"{a.tag}: done {len(pairs)} in {time.time()-t0:.0f}s")
