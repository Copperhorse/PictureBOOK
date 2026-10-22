"""Job endpoints with fake stage scripts (no GPU, no models): progress mapping, failure, cancel, process-group kill, one job at a time, path safety."""
import json
import os
import sys
import time

import pytest
from fastapi.testclient import TestClient

from picturebook_sidecar.app import create_app

TOKEN = "t" * 32
AUTH = {"Authorization": f"Bearer {TOKEN}"}

FAKE_RUN_ALL = r'''
import json, os, subprocess, sys, time
story, rd = sys.argv[1], sys.argv[2]
open(os.path.join(rd, "args.txt"), "w").write(" ".join(sys.argv[3:]))
def ev(**k): print("@@pb " + json.dumps(k), flush=True)
text = open(story).read() if story.endswith(".txt") else ""
for st in ["transcribe", "plan", "assets", "critic_assets", "render"]:
    ev(stage=st, state="start")
    if st == "render":
        os.makedirs(os.path.join(rd, "pages"), exist_ok=True)
        for i in (1, 2):
            print("[page] 1.0s {'page': %d}" % i, flush=True)
            open(os.path.join(rd, "pages", "page_%02d.png" % i), "w").write("x")
    if st == "plan":
        open(os.path.join(rd, "plan.json"), "w").write(json.dumps({"pages": [{"index": 1}, {"index": 2}]}))
    if "FAIL" in text and st == "assets":
        print("Traceback: boom in assets", flush=True); ev(stage=st, state="failed", code=3); sys.exit(1)
    if "SLOW" in text and st == "assets":
        print("sleeping", flush=True)
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])      # like llama serve: a grandchild that must die too
        open(os.path.join(rd, "child.pid"), "w").write(str(child.pid))
        time.sleep(60)
    ev(stage=st, state="done", seconds=0.1)
if "OPTIONAL" in text:
    ev(stage="repair", state="start"); ev(stage="repair", state="done", seconds=0.1)
open(os.path.join(rd, "book.pdf"), "w").write("pdf")
ev(stage="all", state="done", seconds=1)
'''
FAKE_REGEN = r'''
import json, sys
def ev(**k): print("@@pb " + json.dumps(k), flush=True)
for st in ["render", "export", "review"]:
    ev(stage=st, state="start"); ev(stage=st, state="done")
open(sys.argv[1] + "/regen_args.txt", "w").write(" ".join(sys.argv[2:]))
'''


@pytest.fixture()
def env(tmp_path):
    lib = tmp_path / "books"
    lib.mkdir()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "run_all.py").write_text(FAKE_RUN_ALL)
    (scripts / "regen.py").write_text(FAKE_REGEN)
    book = lib / "my-book-1234abcd"
    book.mkdir()
    (book / "book.json").write_text("{}")
    app = create_app(TOKEN, library_root=lib, scripts_dir=scripts, pipeline_python=sys.executable)
    with TestClient(app) as client:
        yield client, lib, book


def events(client, job_id, timeout=20):
    out, name = [], None
    with client.stream("GET", f"/events/{job_id}", headers=AUTH) as r:
        for line in r.iter_lines():
            if line.startswith("event:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                out.append((name, json.loads(line.split(":", 1)[1])))
    return out


def start(client, book, text="Once upon a time.", **extra):
    (book / "story.txt").write_text(text)
    return client.post("/jobs/generate", headers=AUTH, json={"book_dir": str(book), "input": "story.txt", **extra})


def test_generate_streams_stage_progress_then_done(env):
    client, lib, book = env
    r = start(client, book, style="flat", pages=2)
    assert r.status_code == 200, r.text
    ev = events(client, r.json()["job_id"])
    kinds = [k for k, _ in ev]
    assert kinds[-1] == "done" and kinds.count("done") == 1
    prog = [d for k, d in ev if k == "progress"]
    assert [d["stage"] for d in prog if d["state"] == "start"][:3] == ["transcribe", "plan", "assets"]
    fractions = [d["fraction"] for d in prog]
    assert fractions == sorted(fractions) and 0 <= fractions[0] and fractions[-1] < 1      # never goes backwards, never claims 100% before done
    assert any(d["message"] == "Page 2 of 2 drawn" for d in prog)                        # the page count comes from plan.json
    assert ev[-1][1]["result"]["pdf"] is True and (book / "book.pdf").exists()


def test_an_optional_stage_does_not_make_the_bar_go_backwards(env):
    client, _, book = env
    ev = events(client, start(client, book, "OPTIONAL").json()["job_id"])
    f = [d["fraction"] for k, d in ev if k == "progress"]
    assert f == sorted(f) and any(d["stage"] == "repair" for k, d in ev if k == "progress")


def test_a_failing_stage_reports_the_output_tail(env):
    client, _, book = env
    ev = events(client, start(client, book, "FAIL please").json()["job_id"])
    k, d = ev[-1]
    assert k == "error" and d["code"] == "stage_failed" and "boom in assets" in d["message"]


def test_cancel_stops_the_job_and_kills_grandchildren(env):
    client, _, book = env
    job_id = start(client, book, "SLOW").json()["job_id"]
    for _ in range(100):                                    # wait until the fake stage has started its grandchild
        if (book / "child.pid").exists():
            break
        time.sleep(0.1)
    pid = int((book / "child.pid").read_text())
    os.kill(pid, 0)                                         # alive
    assert client.post(f"/jobs/{job_id}/cancel", headers=AUTH).json() == {"cancelled": True}
    ev = events(client, job_id)
    assert ev[-1][0] == "cancelled"
    for _ in range(50):
        try:
            os.kill(pid, 0)
            time.sleep(0.1)
        except ProcessLookupError:
            break
    else:
        pytest.fail("the grandchild process survived the cancel")
    assert client.post(f"/jobs/{job_id}/cancel", headers=AUTH).json() == {"cancelled": False}   # nothing left to cancel


def test_only_one_pipeline_job_at_a_time(env):
    client, lib, book = env
    first = start(client, book, "SLOW").json()["job_id"]
    for _ in range(100):
        if (book / "child.pid").exists():
            break
        time.sleep(0.1)
    r = client.post("/jobs/regen", headers=AUTH, json={"book_dir": str(book), "pages": [1]})
    assert r.status_code == 409 and first in r.json()["detail"]
    client.post(f"/jobs/{first}/cancel", headers=AUTH)
    events(client, first)
    assert client.post("/jobs/regen", headers=AUTH, json={"book_dir": str(book), "pages": [1]}).status_code == 200   # free again


def test_regen_and_undo_pass_page_numbers_through(env):
    client, _, book = env
    job = client.post("/jobs/regen", headers=AUTH, json={"book_dir": str(book), "pages": [4, 2, 2]}).json()["job_id"]
    assert events(client, job)[-1][0] == "done"
    assert (book / "regen_args.txt").read_text() == "2,4"
    job = client.post("/jobs/undo", headers=AUTH, json={"book_dir": str(book), "page": 3}).json()["job_id"]
    assert events(client, job)[-1][0] == "done" and (book / "regen_args.txt").read_text() == "--undo 3"


@pytest.mark.parametrize("bad_dir", ["/etc", "/", "..", "{lib}", "{lib}/../escape", "{lib}/nope", "{lib}/my-book-1234abcd/sub"])
def test_paths_outside_the_library_or_without_book_json_are_refused(env, bad_dir):
    client, lib, book = env
    (book / "sub").mkdir(exist_ok=True)
    (lib.parent / "escape").mkdir(exist_ok=True)
    r = client.post("/jobs/regen", headers=AUTH, json={"book_dir": bad_dir.format(lib=lib), "pages": [1]})
    assert r.status_code == 400, (bad_dir, r.text)


def test_a_symlink_to_a_foreign_folder_is_refused(env):
    client, lib, book = env
    foreign = lib.parent / "foreign"
    foreign.mkdir()
    (foreign / "book.json").write_text("{}")
    os.symlink(foreign, lib / "link")
    assert client.post("/jobs/regen", headers=AUTH, json={"book_dir": str(lib / "link"), "pages": [1]}).status_code == 400


@pytest.mark.parametrize("name", ["../story.txt", "story.txt.exe", "evil.sh", "audio.wav/../../x", "AUDIO.WAV", ""])
def test_input_names_are_a_fixed_pattern(env, name):
    client, _, book = env
    assert client.post("/jobs/generate", headers=AUTH, json={"book_dir": str(book), "input": name}).status_code in (400, 422)


def test_style_and_page_limits(env):
    client, _, book = env
    (book / "story.txt").write_text("x")
    assert client.post("/jobs/generate", headers=AUTH, json={"book_dir": str(book), "style": "oil"}).status_code == 400
    assert client.post("/jobs/generate", headers=AUTH, json={"book_dir": str(book), "pages": 11}).status_code == 422
    assert client.post("/jobs/regen", headers=AUTH, json={"book_dir": str(book), "pages": []}).status_code == 422
    assert client.post("/jobs/regen", headers=AUTH, json={"book_dir": str(book), "pages": [0]}).status_code == 400


def test_requires_the_token_and_a_configured_library(tmp_path):
    with TestClient(create_app(TOKEN)) as c:
        assert c.post("/jobs/generate", json={"book_dir": "/x"}).status_code == 401
        assert c.post("/jobs/generate", headers=AUTH, json={"book_dir": str(tmp_path)}).status_code == 400    # no library configured
    with TestClient(create_app(TOKEN, library_root=tmp_path, scripts_dir=tmp_path / "missing")) as c:
        assert "not found" in c.post("/jobs/regen", headers=AUTH, json={"book_dir": str(tmp_path), "pages": [1]}).json()["detail"]


def test_every_stage_name_the_scripts_announce_is_known_to_the_progress_table():
    """run_all.py and regen.py announce stage names; a typo would silently give a wrong progress bar."""
    import re
    from pathlib import Path
    from picturebook_sidecar.pipeline import STAGES
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    names = set(re.findall(r'stage\("([a-z_0-9]+)"', (scripts / "run_all.py").read_text())) | {"render", "export", "review"}
    assert names, "no stage names found"
    assert names <= set(STAGES), sorted(names - set(STAGES))
