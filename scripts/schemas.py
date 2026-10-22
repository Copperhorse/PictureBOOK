"""Pydantic models for the structured plan (docs/class.md, section 3). Every key is always present; "None" means absent."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

AgeGroup = Literal["infant", "child", "teen", "adult", "elderly", "none"]
Build = Literal["slight", "average", "sturdy", "large"]
Height = Literal["very_short", "short", "average", "tall"]
Pose = Literal["standing", "walking", "running", "sitting", "jumping", "waving", "pointing", "sleeping", "holding_item", "hugging", "other"]
Expression = Literal["happy", "sad", "surprised", "scared", "angry", "curious", "sleepy", "neutral", "shy", "proud", "determined", "embarrassed"]
Camera = Literal["wide", "medium", "close-up"]
HairStyle = Literal["short", "medium", "long", "bun", "ponytail", "braids", "curly", "bald", "covered"]   # covered = hidden by headwear
RenderMode = Literal["layered", "ref_compose", "composite_refine", "full_scene"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OutfitItem(Model):
    item: str = Field(max_length=30)
    colour: str = Field(max_length=30)
    detail: str = Field(max_length=60)


class CharacterSpec(Model):
    name: str = Field(max_length=40)
    species: str = Field(max_length=30)
    age_group: AgeGroup
    build: Build
    height_relative: Height
    hair: str = Field(max_length=60)
    hair_style: HairStyle
    headwear: str = Field(max_length=60)
    eyewear: str = Field(max_length=60)
    face: str = Field(max_length=60)
    skin_colour: str = Field(max_length=40)
    outfit: list[OutfitItem] = Field(min_length=1, max_length=4)
    accessories: str = Field(max_length=60)
    distinguishing_marks: str = Field(max_length=60)
    inferred_fields: list[str] = []          # filled in by code, never by the LLM


class EnvironmentSpec(Model):
    name: str = Field(max_length=40)
    setting: Literal["indoor", "outdoor"]
    location: str = Field(max_length=80)
    time_of_day: Literal["dawn", "morning", "noon", "afternoon", "evening", "night", "none"]
    weather: str = Field(max_length=40)
    season: Literal["spring", "summer", "autumn", "winter", "none"]
    lighting: str = Field(max_length=60)
    mood: str = Field(max_length=40)
    palette: list[str] = Field(min_length=2, max_length=4)
    key_objects: list[str] = Field(max_length=6)
    inferred_fields: list[str] = []


class LayoutItem(Model):
    character: str
    pose: Pose
    pose_detail: str = Field(max_length=60)
    placement: str = Field(max_length=60)    # where the character is, naming a solid thing from the setting (prevents floating characters)
    expression: Expression
    facing: Literal["left", "right", "front", "back"]
    position: Literal["left", "center", "right"]
    depth: Literal["foreground", "mid", "background"]


class Reflection(Model):
    of: str                                  # name of the ORIGINAL character whose reflection / mirror image is visible
    surface: str = Field(max_length=40)      # where it is seen: "the stream", "the mirror", "the window glass"


class Page(Model):
    index: int
    first_sentence: int
    last_sentence: int
    story_text: str                          # copied by code from the transcript sentences
    scenario: str = Field(max_length=240)
    effects: list[str] = Field(max_length=3)
    reflections: list[Reflection] = Field(default=[], max_length=2)   # reflections are drawn inside their surface; they are never separate characters
    must_show: list[str] = Field(max_length=2)   # short visual facts the picture must show (events, changes); checked by the critic
    camera: Camera
    environment: str
    render_mode: RenderMode                  # set by code
    layout: list[LayoutItem] = Field(max_length=4)


class Plan(Model):
    title: str
    characters: list[CharacterSpec]
    environments: list[EnvironmentSpec]
    pages: list[Page]
