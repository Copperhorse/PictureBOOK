"""The demo stories and their catalogue (scripts/demo/stories.json) stay in step, and every story is a sane input for the pipeline."""
import json, os
import common

DEMO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "demo")
CAT = json.load(open(os.path.join(DEMO, "stories.json")))

def test_every_story_file_is_in_the_catalogue_and_vice_versa():
    on_disk = {os.path.relpath(os.path.join(d, f), DEMO) for d, _, fs in os.walk(DEMO) for f in fs if f.endswith(".txt")}
    assert on_disk == {e["file"] for e in CAT}

def test_stories_have_a_usable_size_and_plain_text():
    for e in CAT:
        text = open(os.path.join(DEMO, e["file"]), encoding="utf-8").read()
        words = len(text.split())
        assert e["words"] == words, e["file"]                          # the catalogue is current
        assert 40 <= words <= 700, (e["file"], words)                  # a few sentences up to a long story
        assert len(common.split_sentences(text)) >= 5, e["file"]        # enough sentences for 4-6 pages
        assert '"' not in text and "“" not in text, e["file"]       # speech comes without quote marks, like transcribed speech
        assert text.isascii() or "'" in text, e["file"]
        assert e["stresses"] and e["contains"], e["file"]

def test_the_catalogue_covers_both_new_kinds():
    kinds = {e["kind"] for e in CAT}
    assert {"aesop fable", "spooky tale", "earlier test"} <= kinds
    assert sum(e["kind"] == "aesop fable" for e in CAT) >= 8 and sum(e["kind"] == "spooky tale" for e in CAT) >= 6
