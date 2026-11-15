"""Picks each step's implementation from config."""

from app.config import get_settings
from app.pipeline.base import Assembler, ClipGenerator, ShotPlanner, Stager


def shot_planner() -> ShotPlanner:
    from app.pipeline.fake import FakeShotPlanner

    return FakeShotPlanner()  # Claude-based planner plugs in here


def stager() -> Stager:
    from app.pipeline.fake import FakeStager

    return FakeStager()  # Nano Banana (or the staging test winner) plugs in here


def clip_generator() -> ClipGenerator:
    name = get_settings().clip_generator
    if name.startswith("fal:"):
        from app.pipeline.fal import FalClipGenerator

        return FalClipGenerator(get_settings().fal_key, name.removeprefix("fal:"))
    from app.pipeline.fake import FakeClipGenerator

    return FakeClipGenerator()


def assembler() -> Assembler:
    from app.pipeline.ffmpeg_assembler import FfmpegAssembler

    return FfmpegAssembler()
