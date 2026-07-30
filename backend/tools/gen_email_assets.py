"""Regenerate the baked email-chrome PNGs in ``backend/app/assets``.

Classic Outlook renders mail with Word's engine: it cannot draw rounded corners
from CSS and mangles VML on send, but it renders images perfectly. So the
rounded chrome — the navy header band (logo mark + wordmark + tagline), the
white closing strip, and each CTA pill — is baked into PNGs.

The images are saved at **2x** their display size and scaled down by the
``width``/``height`` attributes in ``email_frame.py``, which keeps them crisp on
high-DPI screens. Everything is drawn at 4x and downsampled with LANCZOS to get
antialiased arcs and text.

Run from the ``backend`` directory::

    python tools/gen_email_assets.py            # header only (the usual case)
    python tools/gen_email_assets.py --all      # every asset
    python tools/gen_email_assets.py --all --out /tmp/x   # dry run elsewhere

Only the header carries the product name, so a rename needs nothing else
regenerated. Commit the PNGs — they are not built at runtime.

Caveat on ``--all``: the committed button pills predate this script and came out
4-5px narrower than it produces (their original padding/hinting differed
slightly). Regenerating them means updating the display widths in
``email_frame.BUTTONS`` to whatever this script prints, or the ``<img width>``
attribute will stretch the pill.
"""

import argparse
import math
import os

from PIL import Image, ImageDraw, ImageFont

NAVY = "#0B2A4A"
BLUE = "#2563EB"
SKY = "#93BBF5"
WHITE = "#ffffff"

FONT_BOLD = "C:/Windows/Fonts/arialbd.ttf"
FONT_REG = "C:/Windows/Fonts/arial.ttf"

SS = 4          # supersample: draw at 4x display, save at 2x
SAVE = 2
RADIUS = 12     # corner radius in display px

ASSETS = os.path.join(os.path.dirname(__file__), "..", "app", "assets")

# Button pills: display width comes out of the label, so it is printed for the
# BUTTONS table in email_frame.py rather than hard-coded here.
BUTTONS = {
    "email_btn_assigned.png": "Review & approve",
    "email_btn_approved.png": "View the request",
    "email_btn_rejected.png": "Open the request",
    "email_btn_finance_ready.png": "Complete the finance section",
}


def _font(path, size):
    return ImageFont.truetype(path, int(size * SS))


def _save(img, path):
    w, h = img.size
    out = img.resize((w * SAVE // SS, h * SAVE // SS), Image.LANCZOS)
    out.save(path)
    return out.size


def _mark(d, x, y, size):
    """Draw the 1d "Capital Cycle" mark: sky cycle arrow + white chevron.

    Geometry is the brand file's 100-unit viewBox
    (brand/project/UUS CAPEX Flow - Logo.dc.html, direction 1d), mapped onto a
    `size`-wide box whose top-left corner is (x, y). Display units in, 4x out.
    """
    def px(v):
        return (x + v * size / 100.0) * SS

    def py(v):
        return (y + v * size / 100.0) * SS

    stroke = int(11 * size / 100.0 * SS)

    # Cycle arc: the brand's SVG arc is a circle centred on (50,50) with r=33,
    # open at the upper right where the arrowhead sits. PIL sweeps clockwise
    # from `start` to `end` with 0 deg at 3 o'clock.
    d.arc([px(50 - 33), py(50 - 33), px(50 + 33), py(50 + 33)],
          start=math.degrees(math.atan2(4, 32)),
          end=360 + math.degrees(math.atan2(-22, 24)),
          fill=SKY, width=stroke)

    # Arrowhead wedge at the head of the cycle.
    d.polygon([(px(63), py(20)), (px(84), py(20)), (px(74), py(38))], fill=SKY)

    # Rising chevron, round caps and join.
    pts = [(px(38), py(56)), (px(50), py(44)), (px(62), py(56))]
    d.line(pts, fill=WHITE, width=stroke, joint="curve")
    for cx, cy in (pts[0], pts[2]):
        r = stroke / 2
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)


def header(path, w=640, h=100):
    img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Round the TOP corners only: rounded rect, then square off the bottom.
    d.rounded_rectangle([0, 0, w * SS - 1, h * SS - 1],
                        radius=RADIUS * SS, fill=NAVY)
    d.rectangle([0, (h - RADIUS) * SS, w * SS - 1, h * SS - 1], fill=NAVY)

    mark = 56
    _mark(d, 28, (h - mark) / 2, mark)

    f_company = _font(FONT_BOLD, 21)
    f_word = _font(FONT_BOLD, 15)
    f_tag = _font(FONT_REG, 11)

    text_x = (28 + mark + 18) * SS
    lines_h = 25 + 18 + 15                      # display-px line boxes
    y = (h - lines_h) / 2 * SS

    d.text((text_x, y), "United Uptime Services", font=f_company, fill=WHITE)
    y += 25 * SS

    # Two-tone wordmark: CAP in white, RI in sky.
    d.text((text_x, y), "CAP", font=f_word, fill=WHITE)
    cap_w = d.textlength("CAP", font=f_word)
    d.text((text_x + cap_w, y), "RI", font=f_word, fill=SKY)
    y += 18 * SS

    d.text((text_x, y), "Capital Approval, Planning, Reporting & Investment",
           font=f_tag, fill=SKY)

    size = _save(img, path)
    print(f"{os.path.basename(path)}: saved {size[0]}x{size[1]}px, "
          f"display {w}x{h}")


def bottom(path, w=640, h=14):
    img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Round the BOTTOM corners only.
    d.rounded_rectangle([0, 0, w * SS - 1, h * SS - 1],
                        radius=RADIUS * SS, fill=WHITE)
    d.rectangle([0, 0, w * SS - 1, RADIUS * SS], fill=WHITE)
    size = _save(img, path)
    print(f"{os.path.basename(path)}: saved {size[0]}x{size[1]}px, "
          f"display {w}x{h}")


def button(path, label, h=44, pad=24):
    f = _font(FONT_BOLD, 15)
    text_w = ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(label, font=f)
    w = int(text_w / SS) + 2 * pad
    img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w * SS - 1, h * SS - 1],
                        radius=h * SS // 2, fill=BLUE)
    d.text((w * SS // 2, h * SS // 2), label, font=f, fill=WHITE, anchor="mm")
    _save(img, path)
    # email_frame.BUTTONS needs the DISPLAY width, not the pixel width.
    print(f"{os.path.basename(path)}: display width={w}, height={h}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=ASSETS, help="output directory")
    ap.add_argument("--all", action="store_true",
                    help="also regenerate the closing strip and CTA buttons")
    args = ap.parse_args()

    header(os.path.join(args.out, "email_header.png"))
    if args.all:
        bottom(os.path.join(args.out, "email_bottom.png"))
        for name, label in BUTTONS.items():
            button(os.path.join(args.out, name), label)


if __name__ == "__main__":
    main()
