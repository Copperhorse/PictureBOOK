"""The three pipeline steps (plan / assets / pages) and editing characters and places. Uses the real scripts/schemas.py and scripts/rules.py."""
import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from picturebook_sidecar import plan_edit
from picturebook_sidecar.app import create_app
from picturebook_sidecar.pipeline import STEP_BASE
from tests.test_pipeline import AUTH, FAKE_REGEN, FAKE_RUN_ALL, TOKEN, events

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def character(name="Mira", **kw):
    return {"name": name, "species": "human", "age_group": "child", "build": "average", "height_relative": "average", "hair": "brown", "hair_style": "braids", "headwear": "None", "eyewear": "round glasses",
            "face": "freckles", "skin_colour": "fair", "outfit": [{"item": "raincoat", "colour": "yellow", "detail": "None"}], "accessories": "red kite", "distinguishing_marks": "None",
            "inferred_fields": ["hair", "skin_colour", "build"], **kw}


def place(name="Hilltop", **kw):
    return {"name": name, "setting": "outdoor", "location": "a green hill", "time_of_day": "morning", "weather": "windy", "season": "spring", "lighting": "bright", "mood": "joyful",
            "palette": ["green", "blue"], "key_objects": ["oak tree"], "inferred_fields": ["mood"], **kw}


@pytest.fixture()
def env(tmp_path):
    lib = tmp_path / "books"
    book = lib / "story-1234abcd"
    (book / "assets").mkdir(parents=True)
    (book / "checks").mkdir()
    (book / "book.json").write_text("{}")
    (book / "plan.json").write_text(json.dumps({"title": "T", "characters": [character(), character("Fisherman", hair="grey", eyewear="None", accessories="net")], "environments": [place(), place("Riverbank")], "pages": []}))
    for f in ("ref_mira.png", "ref_mira_c1.png", "ref_mira_c2.png", "ref_mira_before_repair.png", "ref_fisherman.png", "plate_hilltop.png", "plate_riverbank.png"):
        (book / "assets" / f).write_bytes(b"png")
    (book / "checks" / "assets.json").write_text(json.dumps({"Mira": {"chosen": "ref_mira_c1.png"}, "Fisherman": {"chosen": "ref_fisherman_c1.png"}}))
    return lib, book


def plan_of(book):
    return json.loads((book / "plan.json").read_text())


def names(book):
    return sorted(p.name for p in (book / "assets").iterdir())


def test_editing_a_character_changes_the_plan_and_drops_only_that_characters_pictures(env):
    _, book = env
    spec = plan_edit.save_item(SCRIPTS, book, "character", "Mira", {"hair": "black", "hair_style": "ponytail"})
    assert spec["hair"] == "black" and plan_of(book)["characters"][0]["hair"] == "black" and plan_of(book)["characters"][0]["hair_style"] == "ponytail"
    assert names(book) == ["ref_fisherman.png", "plate_hilltop.png", "plate_riverbank.png"] or names(book) == ["plate_hilltop.png", "plate_riverbank.png", "ref_fisherman.png"]
    assert "Mira" not in json.loads((book / "checks" / "assets.json").read_text()) and "Fisherman" in json.loads((book / "checks" / "assets.json").read_text())
    assert plan_of(book)["characters"][0]["inferred_fields"] == ["skin_colour", "build"]       # what the parent typed is no longer a guess
    assert plan_of(book)["characters"][1]["hair"] == "grey"                                    # the other character is untouched
    assert not [f for f in os.listdir(book) if f.startswith(".plan-")], "no temporary file left behind"


def test_editing_a_place_drops_its_plate(env):
    _, book = env
    plan_edit.save_item(SCRIPTS, book, "place", "Riverbank", {"time_of_day": "evening", "key_objects": ["reeds", "rocks"]})
    assert plan_of(book)["environments"][1]["time_of_day"] == "evening" and "plate_riverbank.png" not in names(book) and "plate_hilltop.png" in names(book)


def test_saving_the_same_values_keeps_the_pictures(env):
    _, book = env
    before = names(book)
    plan_edit.save_item(SCRIPTS, book, "character", "Mira", {"hair": "brown"})
    assert names(book) == before


@pytest.mark.parametrize("fields,why", [
    ({"age_group": "wizard"}, "age_group"), ({"hair_style": "mohawk"}, "hair_style"), ({"hair": "x" * 200}, "hair"),
    ({"name": "Other"}, "cannot be changed"), ({"inferred_fields": []}, "cannot be changed"), ({"layout": 1}, "cannot be changed"), ({}, "nothing"),
    ({"outfit": []}, "outfit"), ({"outfit": [{"item": "hat"}]}, "outfit"),
])
def test_invalid_edits_are_refused_and_change_nothing(env, fields, why):
    _, book = env
    before_plan, before_files = (book / "plan.json").read_text(), names(book)
    with pytest.raises(plan_edit.PlanEditError) as e:
        plan_edit.save_item(SCRIPTS, book, "character", "Mira", fields)
    assert why in str(e.value)
    assert (book / "plan.json").read_text() == before_plan and names(book) == before_files


def test_unknown_names_kinds_and_path_tricks_are_refused(env):
    _, book = env
    for kind, name in (("character", "Nobody"), ("character", "../../etc/passwd"), ("place", "Mira"), ("pages", "Mira"), ("character", "")):
        with pytest.raises(plan_edit.PlanEditError):
            plan_edit.save_item(SCRIPTS, book, kind, name, {"hair": "red"})
    assert (book / "assets" / "ref_mira.png").exists()


def test_no_edits_once_pages_are_drawn_or_without_a_plan(env):
    _, book = env
    (book / "pages").mkdir()
    (book / "pages" / "page_01.png").write_bytes(b"x")
    with pytest.raises(plan_edit.PlanEditError, match="already drawn"):
        plan_edit.save_item(SCRIPTS, book, "character", "Mira", {"hair": "red"})
    (book / "pages" / "page_01.png").unlink()
    (book / "plan.json").write_text("garbage")
    with pytest.raises(plan_edit.PlanEditError, match="readable plan"):
        plan_edit.save_item(SCRIPTS, book, "character", "Mira", {"hair": "red"})


def test_options_come_from_the_pipeline_models():
    o = plan_edit.options(SCRIPTS)
    assert "ponytail" in o["hair_style"] and "child" in o["age_group"] and "outdoor" in o["setting"] and "night" in o["time_of_day"] and "winter" in o["season"]
    assert set(o) == {"age_group", "build", "height_relative", "hair_style", "setting", "time_of_day", "season"}


def test_the_sidecar_copies_of_the_rules_match_the_scripts():
    """slug, the picture-file pattern and the step lists are written twice (the sidecar must not import the scripts' heavy helpers); this keeps them identical."""
    sys.path.insert(0, str(SCRIPTS))
    try:
        import rules
        names_ = ["Papa Bear", "  Isla's Mirror!! ", "Éclair", "日本", "a--b__c", "Bear Cub", "Quiet Blue Lake"]
        assert [plan_edit.slug(n) for n in names_] == [rules.slug(n) for n in names_]
        for n in ("Bear", "Bear Cub", "Quiet Blue Lake"):
            files = [f"{kind}_{rules.slug(x)}{suf}.png" for kind in ("ref", "plate") for x in ("Bear", "Bear Cub", "Quiet Blue Lake") for suf in ("", "_c1", "_c12", "_before_repair", "_x")]
            import re
            pat = re.compile(rf"^(ref|plate)_{re.escape(plan_edit.slug(n))}(_c\d+|_before_repair)?\.png$")
            assert sorted(f for f in files if pat.match(f)) == sorted(rules.asset_files(files, n)), n
        for step, stages in STEP_BASE.items():
            assert [s for s in stages if s in rules.stages_for(step)] == stages and stages[0] == rules.stages_for(step)[0], step
    finally:
        sys.path.remove(str(SCRIPTS))


# ---------------------------------------------------------------- the endpoints
@pytest.fixture()
def client(env, tmp_path):
    lib, book = env
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "run_all.py").write_text(FAKE_RUN_ALL)
    (scripts / "regen.py").write_text(FAKE_REGEN)
    for f in ("schemas.py",):
        (scripts / f).write_text((SCRIPTS / f).read_text())
    with TestClient(create_app(TOKEN, library_root=lib, scripts_dir=scripts, pipeline_python=sys.executable)) as c:
        yield c, book


def test_step_endpoint_passes_the_step_and_only_to_the_script(client):
    c, book = client
    (book / "story.txt").write_text("A story.")
    for step, only in (("plan", None), ("assets", None), ("assets", "Mira"), ("pages", None)):
        r = c.post("/jobs/step", headers=AUTH, json={"book_dir": str(book), "step": step, "only": only, "style": "flat", "pages": 5})
        assert r.status_code == 200, r.text
        assert events(c, r.json()["job_id"])[-1][0] == "done"
        args = (book / "args.txt").read_text()
        assert f"--steps {step}" in args and "--style flat" in args and "--pages 5" in args and (f"--only {only}" in args if only else "--only" not in args)


def test_later_steps_do_not_need_the_story_file_any_more(client):
    c, book = client                       # no story.txt: a recording was deleted after it was transcribed
    assert c.post("/jobs/step", headers=AUTH, json={"book_dir": str(book), "step": "pages"}).status_code == 200
    events(c, next(iter(c.app.state.jobs.jobs)))
    assert c.post("/jobs/step", headers=AUTH, json={"book_dir": str(book), "step": "plan"}).status_code == 400          # the plan step does need its input


@pytest.mark.parametrize("body", [{"step": "everything"}, {"step": "plan", "only": "Mira"}, {"step": "assets", "only": "  "}, {"step": "assets", "only": "x" * 81}, {"step": ""}])
def test_bad_step_requests_are_refused(client, body):
    c, book = client
    (book / "story.txt").write_text("x")
    assert c.post("/jobs/step", headers=AUTH, json={"book_dir": str(book), **body}).status_code in (400, 422)


def test_save_endpoints_validate_and_need_the_token(client):
    c, book = client
    body = {"book_dir": str(book), "name": "Mira", "fields": {"hair": "red"}}
    assert c.post("/plan/character", json=body).status_code == 401
    r = c.post("/plan/character", headers=AUTH, json=body)
    assert r.status_code == 200 and r.json()["spec"]["hair"] == "red"
    bad = c.post("/plan/character", headers=AUTH, json={**body, "fields": {"age_group": "wizard"}})
    assert bad.status_code == 400 and "age_group" in bad.json()["detail"]
    assert c.post("/plan/place", headers=AUTH, json={"book_dir": str(book), "name": "Hilltop", "fields": {"mood": "calm"}}).status_code == 200
    assert c.post("/plan/character", headers=AUTH, json={**body, "book_dir": "/etc"}).status_code == 400
    assert "ponytail" in c.get("/plan/options", headers=AUTH).json()["hair_style"]


def test_no_editing_while_a_job_is_running(client):
    c, book = client
    (book / "story.txt").write_text("SLOW")
    job = c.post("/jobs/step", headers=AUTH, json={"book_dir": str(book), "step": "plan"}).json()["job_id"]
    for _ in range(100):
        if (book / "child.pid").exists():
            break
        import time
        time.sleep(0.1)
    r = c.post("/plan/character", headers=AUTH, json={"book_dir": str(book), "name": "Mira", "fields": {"hair": "red"}})
    assert r.status_code == 409
    c.post(f"/jobs/{job}/cancel", headers=AUTH)
    events(c, job)


def test_keep_audio_reaches_the_script_only_when_asked(client):
    c, book = client
    (book / "story.txt").write_text("A story.")
    for keep in (False, True):
        for path, body in (("/jobs/step", {"step": "plan"}), ("/jobs/generate", {})):
            r = c.post(path, headers=AUTH, json={"book_dir": str(book), "keep_audio": keep, **body})
            assert r.status_code == 200, r.text
            events(c, r.json()["job_id"])
            assert ("--keep-audio" in (book / "args.txt").read_text()) is keep, (path, keep)
