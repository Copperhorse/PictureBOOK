"""What happens when the reasoning budget is exhausted? Run against a server started with a tiny --reasoning-budget."""
import json, sys, os
import run_critic as R
import planner_test as P
port = int(sys.argv[1]); budget = sys.argv[2]
man = json.load(open(os.path.join(R.HERE, "manifest_v2.json")))
res = []
# critic call, thinking default (on)
for m in man[:6]:
    body = R.build_request(m, m["truth"], "default", 4096, os.path.join(R.HERE, "images_v2", m["file"]))
    r, dt = R.call(port, body); c = r["choices"][0]; msg = c["message"]
    ok = True
    try: json.loads(msg.get("content") or "")
    except Exception: ok = False
    res.append(("critic", c["finish_reason"], r["usage"]["completion_tokens"], len(msg.get("reasoning_content") or ""), ok, round(dt, 1)))
# planner page call
sents = P.STORIES["arcania"]
schema = P.obj(P.page_props(["Arcania"], ["Seventh Prince"]))
for i in (3, 4):
    data, meta = P.llm(port, "on", P.RULES, "Story:\n" + P.story_text(sents) + f"\nDescribe page {i} (sentence {i}).", schema, "page", 4096, 7)
    res.append(("planner_page", meta["finish"], meta["completion_tokens"], meta["reasoning_chars"], data is not None, round(meta["latency"], 1)))
print("budget", budget)
for x in res: print("  ", x)
