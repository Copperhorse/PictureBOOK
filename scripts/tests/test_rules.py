"""Story-independent checks, no GPU: made-up plans only. Run: python3 -m pytest scripts/tests -q"""
import json, os, re, shutil, subprocess, sys
import pytest
from PIL import Image
import rules, common, review

HERE = os.path.dirname(os.path.abspath(__file__)); SCRIPTS = os.path.dirname(HERE)

def char(name, species="fox", accessories="none", headwear="none", outfit="scarf", hair_style="short"):
    return {"name": name, "species": species, "age_group": "child", "build": "average", "height_relative": "average", "hair": "brown", "hair_style": hair_style, "headwear": headwear, "eyewear": "none",
            "face": "none", "skin_colour": "fair", "outfit": [{"item": outfit, "colour": "green", "detail": "none"}], "accessories": accessories, "distinguishing_marks": "none", "inferred_fields": []}
def env(name, key_objects):
    return {"name": name, "setting": "outdoor", "location": "a meadow", "time_of_day": "noon", "weather": "clear", "season": "summer", "lighting": "sunny", "mood": "calm", "palette": ["green", "blue"], "key_objects": key_objects, "inferred_fields": []}
def layout(name, **k):
    return {"character": name, "pose": "standing", "pose_detail": "none", "placement": "standing on the grass", "expression": "happy", "facing": "front", "position": "center", "depth": "mid", **k}
def page(i, names, text="Something happens.", must_show=()):
    return {"index": i, "first_sentence": i, "last_sentence": i, "story_text": text, "scenario": "A scene.", "effects": [], "must_show": list(must_show), "camera": "wide", "environment": "Meadow",
            "render_mode": "ref_compose" if names else "layered", "layout": [layout(n) for n in names]}

# ---------------------------------------------------------------- limits and page ranges scale with the story
@pytest.mark.parametrize("n", [1, 2, 5, 6, 12, 35, 80])
def test_page_ranges_cover_every_sentence_once(n):
    for pages in (1, 4, 6, 10):
        r = rules.page_ranges(n, pages)
        assert len(r) == min(pages, n)
        flat = [i for a, b in r for i in range(a, b + 1)]
        assert flat == list(range(1, n + 1))                       # contiguous, no gaps, no overlap
        assert all(a <= b for a, b in r)

def test_limits_grow_with_story_length_but_stay_bounded():
    short, long_ = rules.limits_for_story(5), rules.limits_for_story(35, 8)
    assert short["n_pages"] == 5 and short["max_places"] == 2
    assert long_["n_pages"] == 8 and long_["max_places"] == 5 and long_["max_chars"] >= 4
    assert rules.limits_for_story(200, 99)["n_pages"] == rules.MAX_PAGES
    assert rules.limits_for_story(1)["n_pages"] == 1

def test_reference_size_shrinks_as_pictures_are_added():
    px = [rules.ref_pixels(n) for n in range(1, 8)]
    assert px == sorted(px, reverse=True) and px[0] == 1024 and px[-1] >= 256

def test_every_redraw_gets_a_new_seed():
    seeds = {rules.page_seed(p, a) for p in range(1, 11) for a in range(0, 6)}
    assert len(seeds) == 10 * 6

# ---------------------------------------------------------------- layout and plate rules
def test_clean_layout_dedupes_and_caps_in_order():
    lay = [layout("A"), layout("B"), layout("A"), layout("C"), layout("D"), layout("E")]
    out = rules.clean_layout(lay)
    assert [l["character"] for l in out] == ["A", "B", "C", "D"][:rules.MAX_CHARS_PER_PAGE]
    assert rules.clean_layout([]) == []

def test_carried_objects_are_removed_from_the_background_but_scenery_stays():
    chars = [char("Kid", accessories="red kite"), char("Man", accessories="fishing net", headwear="straw hat")]
    envs = rules.strip_carried([env("Hill", ["red kite", "big oak tree", "fishing net", "straw hat stand", "wooden boat"])], chars)
    assert envs[0]["key_objects"] == ["big oak tree", "wooden boat"]

def test_mentioned_and_pronoun_helpers():
    c = char("Papa Bear", species="bear")
    assert rules.mentioned(c, "Then the bear came home.") and not rules.mentioned(c, "A girl sang.")
    assert rules.PRONOUN.search("She ran away.")

def test_clean_text_removes_cjk_leaks_everywhere():
    d = {"a": "walls of淡 blue", "b": ["red 红 door", {"c": "한국어 ok"}], "n": 3}
    assert rules.clean_text(d) == {"a": "walls of blue", "b": ["red door", {"c": "ok"}], "n": 3}
    assert rules.clean_text("café — naïve") == "café — naïve"            # accents and dashes stay

def test_setting_lines_describe_each_place():
    t = rules.setting_lines([env("Kitchen", []), env("Forest", [])]); assert t.count("\n") == 1 and "Kitchen: a meadow" in t

# ---------------------------------------------------------------- prompts follow the chosen style, handle empty pages
def test_page_prompt_uses_the_chosen_style_and_the_placement():
    p = page(1, ["Kid"], must_show=["the string is broken"]); e = env("Meadow", [])
    for style in ("crayon", "flat", "watercolour"):
        t = common.page_instruction(p, {"Kid": char("Kid")}, e, ["Kid"], style)
        assert common.STYLE[style] in t and "standing on the grass" in t and "the string is broken" in t
    assert "crayon" not in common.page_instruction(p, {"Kid": char("Kid")}, e, ["Kid"], "flat").lower()

def test_page_prompt_names_species_and_forbids_feature_mixing_for_groups():
    chars = {"A": char("A", species="bear"), "B": char("B", species="human"), "C": char("C", species="owl")}
    t = common.page_instruction(page(1, ["A", "B", "C"]), chars, env("Meadow", []), ["A", "B", "C"])
    assert "Image 2 is A, a bear." in t and "Image 4 is C, an owl." in t and "Never mix features" in t and "A looks only like image 2" in t
    single = common.page_instruction(page(1, ["A"]), chars, env("Meadow", []), ["A"])
    assert "Never mix features" not in single                      # nothing to mix with one character

def test_descriptor_mentions_the_hair_style():
    assert "ponytail" in common.descriptor(char("Kid", hair_style="ponytail"))

# ---------------------------------------------------------------- the review sheet works for 0..N characters
def make_run(tmp_path, pages, chars):
    d = tmp_path / "run"; (d / "pages").mkdir(parents=True); (d / "checks").mkdir()
    plan = {"title": "T", "characters": chars, "environments": [env("Meadow", [])], "pages": pages}
    (d / "plan.json").write_text(json.dumps(plan))
    for p in pages: Image.new("RGB", (64, 64), (200, 220, 240)).save(d / "pages" / f"page_{p['index']:02d}.png")
    return common.Run(str(d))

def test_review_sheet_with_scenery_only_and_crowded_pages(tmp_path):
    chars = [char("A"), char("B"), char("C"), char("D")]
    run = make_run(tmp_path, [page(1, []), page(2, ["A"]), page(3, ["A", "B", "C", "D"], must_show=["door open"])], chars)
    (tmp_path / "run" / "checks" / "hints.json").write_text(json.dumps({"3": {"hints": ["B may be drawn 2 times"], "sig": review.picture_sig(run, 3)}}))
    rep = review.build(run)
    assert os.path.exists(run.p("review.png")) and os.path.exists(run.p("review.txt"))
    assert rep["3"]["hints"] == ["B may be drawn 2 times"] and rep["1"]["hints"] == [] and rep["3"]["checked"] is True
    txt = open(run.p("review.txt")).read()
    assert "nobody (scenery only)" in txt and "door open" in txt and "regen.py" in txt

def test_review_sheet_for_a_story_without_any_character_pages(tmp_path):
    run = make_run(tmp_path, [page(1, [])], [char("A")]); assert review.build(run)["1"]["hints"] == []

# ---------------------------------------------------------------- undo of a redraw (needs systemd-run for the memory-capped export step)
@pytest.mark.skipif(shutil.which("systemd-run") is None, reason="needs systemd-run")
def test_undo_restores_the_previous_picture_and_keeps_the_seed_counter(tmp_path):
    run = make_run(tmp_path, [page(1, ["A"]), page(2, ["A"])], [char("A")])
    Image.new("RGB", (64, 64), (255, 0, 0)).save(run.p("pages", "page_02.png"))          # the redrawn picture
    Image.new("RGB", (64, 64), (0, 0, 255)).save(run.p("pages", "page_02_v1.png"))       # the earlier one
    run.save("regen_log.json", {"2": {"attempt": 1, "archive": ["page_02_v1.png"]}})
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "regen.py"), run.dir, "--undo", "2"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert Image.open(run.p("pages", "page_02.png")).getpixel((1, 1)) == (0, 0, 255)
    log = run.load("regen_log.json"); assert log["2"]["attempt"] == 1 and log["2"]["archive"] == []
    assert os.path.exists(run.p("pages", "page_02_discarded_a1.png")) and os.path.exists(run.p("book.pdf"))
    r2 = subprocess.run([sys.executable, os.path.join(SCRIPTS, "regen.py"), run.dir, "--undo", "2"], capture_output=True, text=True)
    assert r2.returncode != 0 and "no earlier picture" in (r2.stdout + r2.stderr)       # nothing left to undo

def test_regen_rejects_unknown_pages(tmp_path):
    run = make_run(tmp_path, [page(1, ["A"])], [char("A")])
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "regen.py"), run.dir, "7"], capture_output=True, text=True)
    assert r.returncode != 0 and "no such page" in (r.stdout + r.stderr)

# ---------------------------------------------------------------- the code must not know any particular story
NAMES = re.compile(r"\b(Arcania|Arcanian|Mira|Bramble|Sammy|Omar|Goldilocks|Pip|Seventh Prince|Papa Bear|Mama Bear|Baby Bear)\b")
def test_no_story_specific_names_in_the_scripts():
    offenders = []
    for f in sorted(os.listdir(SCRIPTS)):
        if not f.endswith(".py"): continue
        for i, line in enumerate(open(os.path.join(SCRIPTS, f)), 1):
            if NAMES.search(line): offenders.append(f"{f}:{i}: {line.strip()[:80]}")
    assert not offenders, offenders


def test_notes_belong_to_the_picture_they_were_made_for(tmp_path):
    run = make_run(tmp_path, [page(1, ["A"])], [char("A")])
    (tmp_path / "run" / "checks" / "hints.json").write_text(json.dumps({"1": {"hints": ["A may be floating"], "sig": review.picture_sig(run, 1)}}))
    assert review.hints_for(run, 1) == (["A may be floating"], False)
    Image.new("RGB", (64, 64), (1, 2, 3)).save(run.p("pages", "page_01.png"))            # a redraw replaced the picture: different size/time
    Image.new("RGB", (80, 80), (9, 9, 9)).save(run.p("pages", "page_01.png"))
    notes, stale = review.hints_for(run, 1, redrawn=1)
    assert notes == [] and stale is True
    rep = review.build(run)
    assert rep["1"]["checked"] is False and "not checked since this page was redrawn" in open(run.p("review.txt")).read()


# ---------------------------------------------------------------- reflections are effects, not characters
def test_reflection_owner_matches_common_naming_styles():
    cast = ["Dog", "Isla", "Old Harlow", "Papa Bear"]
    assert rules.reflection_owner("Reflection Dog", cast) == "Dog"
    assert rules.reflection_owner("Isla's Reflection", cast) == "Isla"
    assert rules.reflection_owner("Mirror Image of Isla", cast) == "Isla"
    assert rules.reflection_owner("Reflection Girl", cast) is None            # no overlap: left alone rather than guessed
    assert rules.reflection_owner("Dog", cast) is None and rules.reflection_owner("Dogged Hunter", ["Dog"]) is None
    assert rules.reflection_owner("Reflection of the Old Harlow", cast) == "Old Harlow"

def test_fold_reflections_moves_the_double_into_the_page_effect():
    chars = [char("Dog", species="dog"), char("Reflection Dog", species="dog")]
    pages = [page(1, ["Dog"]), page(2, ["Dog", "Reflection Dog"]), page(3, ["Reflection Dog"])]
    pages[1]["reflections"] = []
    gone = rules.fold_reflections(chars, pages)
    assert gone == ["Reflection Dog"] and [c["name"] for c in chars] == ["Dog"]
    assert [[l["character"] for l in p["layout"]] for p in pages] == [["Dog"], ["Dog"], []]
    assert pages[1]["reflections"][0]["of"] == "Dog" and pages[2]["reflections"][0]["of"] == "Dog"
    assert pages[0].get("reflections", []) == []
    assert rules.fold_reflections(chars, pages) == []                          # nothing left to fold; idempotent

def test_a_reflection_with_an_unknown_owner_stays_a_character():
    chars = [char("Isla", species="girl"), char("Reflection Girl", species="girl")]
    pages = [page(1, ["Isla", "Reflection Girl"])]
    assert rules.fold_reflections(chars, pages) == [] and len(chars) == 2 and len(pages[0]["layout"]) == 2

def test_the_page_prompt_keeps_a_reflection_inside_its_surface():
    chars = {"Dog": char("Dog", species="dog")}
    p = page(2, ["Dog"]); p["reflections"] = [{"of": "Dog", "surface": "the stream"}]
    t = common.page_instruction(p, chars, env("Meadow", []), ["Dog"])
    assert "Dog's reflection is visible as a faint, mirrored" in t and "not a second dog" in t and "exactly one real Dog" in t and "inside the stream" in t
    assert "reflection" not in common.page_instruction(page(2, ["Dog"]), chars, env("Meadow", []), ["Dog"])      # no reflection, no mention


# ---------------------------------------------------------------- the three pipeline steps and single-item redraw
def test_steps_cover_every_stage_once_and_unknown_steps_fail():
    parts = rules.stages_for("plan") + rules.stages_for("assets") + rules.stages_for("pages")
    assert parts == rules.stages_for("all") and len(parts) == len(set(parts))
    assert rules.stages_for("plan")[-1] == "plan" and rules.stages_for("pages")[0] == "render" and "hints" in rules.stages_for("pages")
    for bad in ("", "everything", "Plan", None):
        with pytest.raises(ValueError):
            rules.stages_for(bad)

def test_every_stage_name_used_by_run_all_is_in_a_step():
    names = set(re.findall(r'stage\("([a-z_0-9]+)"', open(os.path.join(SCRIPTS, "run_all.py")).read()))
    assert names <= set(rules.stages_for("all")), sorted(names - set(rules.stages_for("all")))

def test_each_drawing_of_one_character_uses_a_different_seed():
    seeds = {rules.draw_seed(i, n) for i in (1, 2, 3) for n in range(0, 20)}
    assert len(seeds) == 3 * 20 and rules.draw_seed(1, 0) == 1 and rules.draw_seed(2, 0) == 2      # the first drawing keeps the old seeds

def test_asset_files_pick_exactly_one_items_pictures():
    files = ["ref_bear.png", "ref_bear_c1.png", "ref_bear_c2.png", "ref_bear_before_repair.png", "ref_bear_cub.png", "ref_bear_cub_c1.png", "plate_bear.png", "plate_kitchen.png", "draw_log.json", "notes_ref_bear.png"]
    assert sorted(rules.asset_files(files, "Bear")) == ["plate_bear.png", "ref_bear.png", "ref_bear_before_repair.png", "ref_bear_c1.png", "ref_bear_c2.png"]
    assert sorted(rules.asset_files(files, "Bear Cub")) == ["ref_bear_cub.png", "ref_bear_cub_c1.png"]
    assert rules.asset_files(files, "Kitchen") == ["plate_kitchen.png"] and rules.asset_files(files, "Nobody") == []

def test_slug_examples_shared_with_the_rust_side():
    cases = {"Papa Bear": "papa_bear", "  Isla's Mirror!! ": "isla_s_mirror", "Seventh Prince": "seventh_prince", "Éclair": "clair", "日本": "", "a--b__c": "a_b_c"}
    for name, want in cases.items():
        assert rules.slug(name) == want, name


# ---------------------------------------------------------------- privacy: the recording goes once the story exists as text
def test_recordings_are_deleted_only_after_a_usable_transcript(tmp_path):
    d = tmp_path / "book"; d.mkdir()
    (d / "audio.wav").write_bytes(b"RIFF"); (d / "story.txt").write_text("keep"); (d / "audio.txt").write_text("not a recording"); (d / "plan.json").write_text("{}")
    assert rules.delete_recordings(str(d)) == [] and (d / "audio.wav").exists(), "no transcript yet: nothing is deleted"
    (d / "transcript.json").write_text("{ not json")
    assert rules.delete_recordings(str(d)) == [] and (d / "audio.wav").exists(), "a damaged transcript counts as none"
    (d / "transcript.json").write_text(json.dumps({"text": "   ", "sentences": []}))
    assert rules.delete_recordings(str(d)) == [] and (d / "audio.wav").exists(), "an empty transcript counts as none"
    (d / "transcript.json").write_text(json.dumps({"text": "Once upon a time there was a fox.", "sentences": ["Once upon a time there was a fox."]}))
    (d / "audio.mp3").write_bytes(b"x")
    assert rules.delete_recordings(str(d)) == ["audio.mp3", "audio.wav"]
    assert sorted(p.name for p in d.iterdir()) == ["audio.txt", "plan.json", "story.txt", "transcript.json"], "only the recordings are removed"

def test_a_symlink_named_like_a_recording_is_never_followed(tmp_path):
    d = tmp_path / "book"; d.mkdir()
    outside = tmp_path / "precious.wav"; outside.write_bytes(b"mine")
    (d / "audio.wav").symlink_to(outside)
    (d / "transcript.json").write_text(json.dumps({"text": "A long enough story text here."}))
    assert rules.delete_recordings(str(d)) == [] and outside.exists()


# ---------------------------------------------------------------- no story, no book
@pytest.mark.parametrize("text", ["", "   ", ".", "...", "Thank you.", "Thank you. Thank you. Thank you.", "Thanks for watching!", "you", "Bye. Bye bye.", "Hmm. Yeah. Okay.",
                                  "The cat sat.", "Hello there", "la la la la la la la la", "the the the the the the the the the"])
def test_things_that_are_not_stories_are_refused_with_a_plain_reason(text):
    why = rules.story_problem(text)
    assert why and len(why) < 140 and "Traceback" not in why, text

@pytest.mark.parametrize("text", ["Once upon a time there was a fox.", "A small blue robot named Beep found a red ball on a quiet hill.", "Mira had a kite and the wind took it away.",
                                  "Thank you, said the fox. The hare smiled and went home to sleep.", "Der Hase und die Igel sind Freunde von dem kleinen Fuchs."])
def test_real_stories_pass_even_when_they_contain_thank_you(text):
    assert rules.story_problem(text) is None

def test_every_demo_story_passes_the_gate():
    for e in json.load(open(os.path.join(SCRIPTS, "demo", "stories.json"))):
        assert rules.story_problem(open(os.path.join(SCRIPTS, "demo", e["file"])).read()) is None, e["file"]


# --- a job must not outlive the app that started it -----------------------------------------------------------------------------------------------------------
def _run_child(code, **envvars):
    return subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {SCRIPTS!r}); import common; common.die_with_parent(); {code}"],
                          env={**os.environ, **envvars}, capture_output=True, text=True, timeout=30)

def test_die_with_parent_stops_when_the_starter_is_already_gone():
    r = _run_child("print('still running')", PICTUREBOOK_PARENT="999999")      # not our parent -> the sidecar died before we got going
    assert r.returncode != 0 and "still running" not in r.stdout

def test_die_with_parent_runs_on_when_the_starter_is_alive():
    r = _run_child("print('still running')", PICTUREBOOK_PARENT=str(os.getpid()))
    assert r.returncode == 0 and "still running" in r.stdout

def test_job_ends_when_its_parent_is_killed():
    """The real thing: SIGKILL the starter, the job (started through die_with_parent) must follow."""
    import signal, time
    code = ("import subprocess, sys, os; "
            f"p = subprocess.Popen([sys.executable, '-c', \"import sys,time; sys.path.insert(0, {SCRIPTS!r}); import common; common.die_with_parent(); print('up', flush=True); time.sleep(60)\"], stdout=subprocess.PIPE, text=True); "
            "print(p.pid, flush=True); p.stdout.readline(); print('ready', flush=True); time.sleep(60)")
    starter = subprocess.Popen([sys.executable, "-c", "import time; " + code], stdout=subprocess.PIPE, text=True)
    child = int(starter.stdout.readline()); assert starter.stdout.readline().strip() == "ready"
    os.kill(starter.pid, signal.SIGKILL); starter.wait()
    for _ in range(50):
        try:
            os.kill(child, 0)
            with open(f"/proc/{child}/stat") as f:
                if f.read().split(")")[-1].split()[0] == "Z": break          # zombie = dead, just not collected by init yet
        except (ProcessLookupError, FileNotFoundError): break
        time.sleep(0.1)
    else:
        os.kill(child, signal.SIGKILL); pytest.fail("the job survived the death of its parent")
