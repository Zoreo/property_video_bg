"""Interfaces for each pipeline step.

Each step has a fake implementation (app/pipeline/fake.py) so the whole site
runs end to end without any AI provider. Real providers implement the same
Protocol and are picked in config (SHOT_PLANNER, STAGER, CLIP_GENERATOR,
ASSEMBLER). See app/pipeline/registry.py.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

Aspect = Literal["16:9", "9:16"]
CameraMove = Literal["push_in", "pull_out", "pan_left", "pan_right", "orbit", "tilt_up"]


@dataclass
class Shot:
    photo_path: Path
    room: str  # "living room", "kitchen", "exterior", ...
    move: CameraMove
    prompt: str  # motion prompt sent to the clip model
    warnings: list[str] = field(default_factory=list)  # "too dark", "blurry", ...


@dataclass
class ListingCard:
    """Everything the assembler prints on screen."""

    template_label: str
    address: str
    city: str
    neighbourhood: str
    size_text: str
    bedrooms: int
    bathrooms: int
    parking_text: str
    agent_name: str
    agency: str
    agent_phone: str
    agent_email: str
    agent_photo: Path | None


class ShotPlanner(Protocol):
    def plan(self, photos: list[Path]) -> list[Shot]: ...


class Stager(Protocol):
    def stage(self, photo: Path, style: str, out: Path) -> Path: ...


class ClipGenerator(Protocol):
    def generate(self, shot: Shot, seconds: int, aspect: Aspect, out: Path) -> Path: ...


class Assembler(Protocol):
    def assemble(self, clips: list[Path], card: ListingCard, aspect: Aspect, out: Path) -> Path: ...
