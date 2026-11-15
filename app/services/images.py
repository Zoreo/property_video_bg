"""Photo intake: checks the file is a real image, fixes phone rotation, saves as JPEG."""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 3840


class BadImage(ValueError):
    pass


def normalise(data: bytes, max_side: int = MAX_SIDE) -> tuple[bytes, int, int]:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as e:
        raise BadImage("not an image we can read (use JPG, PNG or WebP)") from e
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    return out.getvalue(), img.width, img.height
