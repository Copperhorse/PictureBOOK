"""Editing the plan from the characters screen. Validation uses the pipeline's own pydantic models (`scripts/schemas.py`), so the enums,
lengths and field names can never drift from what the stages expect. Only characters and places may be edited (never names, pages or layouts),
only before any page picture exists, and an edit throws away exactly that item's pictures so the next drawing uses the new description."""
import importlib.util
import json
import os
import re
import tempfile
from pathlib import Path
from typing import get_args

from pydantic import ValidationError


class PlanEditError(ValueError):
    """A request that must be refused (HTTP 400), with a plain-words reason."""


CHARACTER_FIELDS = {"species", "age_group", "build", "height_relative", "hair", "hair_style", "headwear", "eyewear", "face", "skin_colour", "outfit", "accessories", "distinguishing_marks"}
PLACE_FIELDS = {"setting", "location", "time_of_day", "weather", "season", "lighting", "mood", "palette", "key_objects"}
SELECT_FIELDS = {"character": ["age_group", "build", "height_relative", "hair_style"], "place": ["setting", "time_of_day", "season"]}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def load_schemas(scripts_dir: Path):
    f = Path(scripts_dir) / "schemas.py"
    if not f.is_file():
        raise PlanEditError("the pipeline scripts are not installed")
    spec = importlib.util.spec_from_file_location("pb_schemas", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def options(scripts_dir: Path) -> dict:
    """The allowed values of every drop-down, read from the models."""
    m = load_schemas(scripts_dir)
    out = {}
    for kind, model in (("character", m.CharacterSpec), ("place", m.EnvironmentSpec)):
        for fld in SELECT_FIELDS[kind]:
            ann = model.model_fields[fld].annotation
            out[fld] = list(get_args(ann))
    return out


def _read_plan(book_dir: Path) -> dict:
    try:
        return json.loads((book_dir / "plan.json").read_text())
    except (OSError, ValueError):
        raise PlanEditError("this book has no readable plan yet") from None


def _write_atomic(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".plan-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _drop_pictures(book_dir: Path, name: str) -> None:
    assets = book_dir / "assets"
    s = re.escape(slug(name))
    pat = re.compile(rf"^(ref|plate)_{s}(_c\d+|_before_repair)?\.png$")        # same rule as scripts/rules.asset_files (parity-tested)
    if assets.is_dir():
        for f in assets.iterdir():
            if pat.match(f.name):
                f.unlink()
    checks = book_dir / "checks" / "assets.json"
    if checks.is_file():
        try:
            data = json.loads(checks.read_text())
            if data.pop(name, None) is not None:
                _write_atomic(checks, json.dumps(data, indent=2))
        except ValueError:
            checks.unlink()                                                      # unreadable: the critic redoes it


def _check_editable(book_dir: Path) -> None:
    pages = book_dir / "pages"
    if pages.is_dir() and any(p.name.startswith("page_") for p in pages.iterdir()):
        raise PlanEditError("the pages are already drawn, so characters and places can no longer be changed (make a new book to start over)")


def save_item(scripts_dir: Path, book_dir: Path, kind: str, name: str, fields: dict) -> dict:
    """kind = 'character' or 'place'. Returns the saved spec."""
    if kind not in ("character", "place"):
        raise PlanEditError("unknown kind")
    allowed = CHARACTER_FIELDS if kind == "character" else PLACE_FIELDS
    bad = sorted(set(fields) - allowed)
    if bad:
        raise PlanEditError(f"these fields cannot be changed: {', '.join(bad)}")
    if not fields:
        raise PlanEditError("nothing to change")
    _check_editable(book_dir)
    plan = _read_plan(book_dir)
    items = plan.get("characters" if kind == "character" else "environments", [])
    old = next((i for i in items if i.get("name") == name), None)
    if old is None:
        raise PlanEditError(f"there is no {kind} named {name!r}")
    schemas = load_schemas(scripts_dir)
    model = schemas.CharacterSpec if kind == "character" else schemas.EnvironmentSpec
    new = {**old, **fields}
    new["inferred_fields"] = [f for f in old.get("inferred_fields", []) if f not in fields]       # what the parent typed is no longer a guess
    try:
        spec = model.model_validate(new).model_dump()
    except ValidationError as exc:
        e = exc.errors()[0]
        raise PlanEditError(f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}") from None
    if all(spec.get(k) == old.get(k) for k in allowed):
        return spec                                                              # nothing really changed: keep the pictures
    items[items.index(old)] = spec
    _write_atomic(book_dir / "plan.json", json.dumps(plan, indent=2, ensure_ascii=False))
    _drop_pictures(book_dir, name)
    return spec
