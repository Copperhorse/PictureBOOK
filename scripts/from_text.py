"""Stage 1 for typed stories: story text file -> transcript.json (the same format transcribe.py writes for audio).
usage: python3 from_text.py <run_dir> <story.txt>"""
import os, sys
from common import Run, split_sentences, timed
run = Run(sys.argv[1]); path = sys.argv[2]
with timed(run, "text_input"):
    text = " ".join(open(path, encoding="utf-8").read().split())          # one line, single spaces
    from rules import story_problem
    if (why := story_problem(text)): sys.exit(why)
    run.save("transcript.json", {"text": text, "sentences": split_sentences(text), "duration_s": 0.0, "engine": "typed", "audio": os.path.basename(path)})
print(run.load("transcript.json")["sentences"])
