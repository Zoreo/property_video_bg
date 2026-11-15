"""fal.ai clip generator (image to video).

Filled in once the model tests pick a winner (Veo 3.1 Lite or Fast lead so far).
The model id comes from config, e.g. CLIP_GENERATOR=fal:fal-ai/veo3.1/lite/image-to-video
"""

from pathlib import Path

from app.pipeline.base import Aspect, Shot


class FalClipGenerator:
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise RuntimeError("FAL_KEY is not set")
        self.api_key, self.model = api_key, model

    def generate(self, shot: Shot, seconds: int, aspect: Aspect, out: Path) -> Path:
        # Plan: upload shot.photo_path, call the model with shot.prompt, aspect and
        # duration, poll the queue, download the mp4 to `out`.
        raise NotImplementedError("fal.ai generator is wired in after the model tests")
