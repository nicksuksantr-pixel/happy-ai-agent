"""Generate a multi-resolution ICO from the HAPPY mascot PNG.

Renders 7 frames natively (256/128/64/48/32/24/16) instead of letting
PIL auto-downsample from a single source — that auto path destroys the
robot's hands at <32 px, which is what Nick reported.

For sizes <= 24 px we also crop tighter to the robot's body so the
silhouette stays readable at taskbar size (otherwise hands clip outside
the icon's bounding box).

Run from project root:
  python tools/make_icon.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "happy_logo_square.png"
DST = ROOT / "assets" / "happy_logo.ico"

# Big -> small. PIL writes the first as primary and the rest as
# append_images. Each frame is rendered separately from the source
# so the rasterizer can pick the best filter per size.
TARGET_SIZES = [256, 128, 64, 48, 32, 24, 16]


def _render_at(src: Image.Image, size: int) -> Image.Image:
    """LANCZOS down-resize from the full source.

    For the smallest sizes we crop tighter to the central robot box —
    the source PNG has padding + hands + feet that vanish below ~24 px,
    so we lose less detail by zooming on the head + body.
    """
    s = src.copy()
    w, h = s.size

    if size <= 24:
        # Tight crop around the head + body (centered, ~70% of source).
        crop_size = int(min(w, h) * 0.78)
        left = (w - crop_size) // 2
        top = (h - crop_size) // 2 - int(h * 0.02)  # bias slightly up
        s = s.crop((left, max(0, top),
                    left + crop_size, max(0, top) + crop_size))

    return s.resize((size, size), Image.LANCZOS)


def main() -> int:
    if not SRC.exists():
        print(f"[!] source missing: {SRC}")
        return 1

    src = Image.open(SRC).convert("RGBA")
    print(f"[*] source: {SRC.name}   {src.size}")

    frames = [_render_at(src, s) for s in TARGET_SIZES]
    print(f"[*] frames: {[(f.width, f.height) for f in frames]}")

    # PIL's ICO writer takes the first image as the canonical one and
    # the rest via append_images. Sizes list controls which frames go
    # into the multi-image ICO.
    primary = frames[0]
    primary.save(
        DST,
        format="ICO",
        sizes=[(s, s) for s in TARGET_SIZES],
        append_images=frames[1:],
    )

    out_size = DST.stat().st_size
    print(f"[OK] wrote {DST} ({out_size / 1024:.1f} KB, "
          f"{len(TARGET_SIZES)} frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
