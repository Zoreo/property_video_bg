"""Joins clips with crossfades and adds an intro and outro card.

A stand-in for the final assembly step (Remotion or a richer ffmpeg template),
which is chosen once the model tests are done. Cards are drawn with Pillow so
we don't depend on ffmpeg's font setup.
"""

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.pipeline.base import Aspect, ListingCard
from app.pipeline.fake import SIZES

FADE = 0.8
CARD_SECONDS = 3


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _card_image(lines: list[tuple[str, int]], size: tuple[int, int], out: Path, photo: Path | None = None) -> Path:
    w, h = size
    img = Image.new("RGB", size, (17, 20, 24))
    draw = ImageDraw.Draw(img)
    y = h // 2 - sum(s + 18 for _, s in lines) // 2
    if photo and photo.exists():
        p = Image.open(photo).convert("RGB")
        d = min(w, h) // 4
        p.thumbnail((d, d))
        img.paste(p, ((w - p.width) // 2, y - p.height - 24))
    for text, s in lines:
        f = _font(s)
        tw = draw.textlength(text, font=f)
        draw.text(((w - tw) / 2, y), text, font=f, fill=(245, 241, 234))
        y += s + 18
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def _still_clip(image: Path, seconds: int, out: Path) -> Path:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(image), "-t", str(seconds),
         "-r", "25", "-vf", "format=yuv420p", "-c:v", "libx264", str(out)],
        check=True,
    )
    return out


def _duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(r.stdout.strip())


class FfmpegAssembler:
    def assemble(self, clips: list[Path], card: ListingCard, aspect: Aspect, out: Path) -> Path:
        size = SIZES[aspect]
        work = out.parent / f"_{aspect.replace(':', 'x')}"
        work.mkdir(parents=True, exist_ok=True)
        place = ", ".join(x for x in (card.neighbourhood, card.city) if x)
        intro = _card_image(
            [(card.template_label.upper(), 72), (card.address or place, 40), (place if card.address else "", 32),
             (f"{card.size_text}  ·  {card.bedrooms} bed  ·  {card.bathrooms} bath  ·  {card.parking_text} parking", 28)],
            size, work / "intro.png",
        )
        outro = _card_image(
            [(card.agent_name, 52), (card.agency, 32), (card.agent_phone, 30), (card.agent_email, 30)],
            size, work / "outro.png", card.agent_photo,
        )
        parts = [_still_clip(intro, CARD_SECONDS, work / "intro.mp4"), *clips,
                 _still_clip(outro, CARD_SECONDS + 1, work / "outro.mp4")]

        inputs: list[str] = []
        for p in parts:
            inputs += ["-i", str(p)]
        w, h = size
        chains = [f"[{i}:v]scale={w}:{h},setsar=1,fps=25,format=yuv420p[v{i}]" for i in range(len(parts))]
        prev, offset = "v0", 0.0
        for i in range(1, len(parts)):
            offset += _duration(parts[i - 1]) - FADE
            label = f"x{i}"
            chains.append(f"[{prev}][v{i}]xfade=transition=fade:duration={FADE}:offset={offset:.3f}[{label}]")
            prev = label
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(chains),
             "-map", f"[{prev}]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
            check=True,
        )
        return out
