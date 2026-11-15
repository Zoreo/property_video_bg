"""Fake steps: no AI, no network. Good enough to see the whole flow work."""

import shutil
import subprocess
from pathlib import Path

from app.pipeline.base import Aspect, Shot

_MOVES = ["push_in", "pan_right", "pull_out", "pan_left"]

SIZES = {"16:9": (1280, 720), "9:16": (720, 1280)}


class FakeShotPlanner:
    def plan(self, photos: list[Path]) -> list[Shot]:
        return [
            Shot(
                photo_path=p,
                room="room",
                move=_MOVES[i % len(_MOVES)],
                prompt="slow cinematic camera move, steady, natural light",
            )
            for i, p in enumerate(photos)
        ]


class FakeStager:
    def stage(self, photo: Path, style: str, out: Path) -> Path:
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(photo, out)
        return out


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


class FakeClipGenerator:
    """A slow zoom or pan over the still photo (Ken Burns), made with ffmpeg."""

    fps = 25

    def generate(self, shot: Shot, seconds: int, aspect: Aspect, out: Path) -> Path:
        w, h = SIZES[aspect]
        frames = seconds * self.fps
        # Scale up first so zoompan has room to move without jitter.
        big = f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2}"
        z = {
            "push_in": "z='1+0.15*on/{f}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2'",
            "pull_out": "z='1.15-0.15*on/{f}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2'",
            "pan_right": "z=1.15:x='(iw-iw/zoom)*on/{f}':y='ih/2-ih/zoom/2'",
            "pan_left": "z=1.15:x='(iw-iw/zoom)*(1-on/{f})':y='ih/2-ih/zoom/2'",
        }.get(shot.move, "z='1+0.15*on/{f}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2'")
        vf = f"{big},zoompan={z.format(f=frames)}:d={frames}:s={w}x{h}:fps={self.fps},format=yuv420p"
        out.parent.mkdir(parents=True, exist_ok=True)
        _ffmpeg("-i", str(shot.photo_path), "-vf", vf, "-frames:v", str(frames), "-c:v", "libx264", str(out))
        return out
