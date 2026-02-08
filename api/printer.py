from __future__ import annotations

import subprocess
import tempfile
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import get_settings

# Label dimensions: 30256 Shipping (4" x 2-5/16"), printed landscape
# At 300 DPI: 1200 x 696 pixels
LABEL_W = 1200
LABEL_H = 696
DPI = 300

# Divider splits label into two halves (kid side + parent tear-off)
DIVIDER_X = LABEL_W // 2


@dataclass
class LabelData:
    name: str
    code: str = ""
    extra: str = ""


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Get a font, falling back to default if system fonts unavailable."""
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSText.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    if bold:
        candidates = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSText-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ] + candidates
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_centered(draw: ImageDraw.ImageDraw, cx: int, y: int,
                    text: str, font: ImageFont.FreeTypeFont,
                    fill: str = "black") -> int:
    """Draw centered text, return the height consumed."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((cx - tw // 2, y), text, fill=fill, font=font)
    return th


def _measure_section(name: str, code: str, extra: str, timestamp: str) -> int:
    """Calculate total content height for vertical centering."""
    h = 0
    # Name
    font_name = _get_font(72, bold=True)
    bbox = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), name, font=font_name)
    h += bbox[3] - bbox[1] + 25  # text + gap before rule

    h += 2 + 20  # rule + gap after rule

    if code:
        font_code = _get_font(60)
        bbox = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), code, font=font_code)
        h += bbox[3] - bbox[1] + 15

    if extra:
        font_extra = _get_font(42)
        bbox = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), extra, font=font_extra)
        h += bbox[3] - bbox[1] + 10

    # Timestamp
    font_ts = _get_font(33)
    bbox = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), timestamp, font=font_ts)
    h += bbox[3] - bbox[1]

    return h


def _draw_section(draw: ImageDraw.ImageDraw, x_offset: int, width: int,
                  height: int, name: str, code: str, extra: str, timestamp: str):
    """Draw label content vertically centered within a given region."""
    cx = x_offset + width // 2
    margin = 20

    content_h = _measure_section(name, code, extra, timestamp)
    y = max(margin, (height - content_h) // 2)

    # Name (large)
    y += _draw_centered(draw, cx, y, name, _get_font(72, bold=True))
    y += 25

    # Horizontal rule
    draw.line([(x_offset + margin, y), (x_offset + width - margin, y)],
              fill="#cccccc", width=2)
    y += 20

    # Code
    if code:
        y += _draw_centered(draw, cx, y, code, _get_font(60))
        y += 15

    # Extra (kid names on parent label) — wrap if too wide
    if extra:
        font_extra = _get_font(42)
        max_w = width - margin * 2
        bbox = draw.textbbox((0, 0), extra, font=font_extra)
        if (bbox[2] - bbox[0]) > max_w:
            for line in extra.split(", "):
                y += _draw_centered(draw, cx, y, line, font_extra)
                y += 4
        else:
            y += _draw_centered(draw, cx, y, extra, font_extra)
        y += 10

    # Timestamp + date
    _draw_centered(draw, cx, y, timestamp, _get_font(33), fill="#888888")


def render_kid_label(label: LabelData, timestamp: str) -> Image.Image:
    """Full-width label for a child — no divider, single sticker."""
    img = Image.new("RGB", (LABEL_W, LABEL_H), "white")
    draw = ImageDraw.Draw(img)
    _draw_section(draw, 0, LABEL_W, LABEL_H, label.name, label.code, label.extra, timestamp)
    return img


def render_parent_label(label: LabelData, timestamp: str) -> Image.Image:
    """Two-half tear-off label for parent — divider down the middle."""
    img = Image.new("RGB", (LABEL_W, LABEL_H), "white")
    draw = ImageDraw.Draw(img)

    half_w = DIVIDER_X
    _draw_section(draw, 0, half_w, LABEL_H, label.name, label.code, label.extra, timestamp)
    draw.line([(DIVIDER_X, 10), (DIVIDER_X, LABEL_H - 10)],
              fill="#cccccc", width=2)
    _draw_section(draw, DIVIDER_X, half_w, LABEL_H, label.name, label.code, label.extra, timestamp)

    return img


class CupsPrinter:
    def __init__(self):
        settings = get_settings()
        self.printer_name = settings.printer_name

    async def is_connected(self) -> bool:
        """Check if the CUPS printer is available."""
        try:
            result = subprocess.run(
                ["lpstat", "-p", self.printer_name],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    async def get_printers(self) -> str:
        """List available printers."""
        try:
            result = subprocess.run(
                ["lpstat", "-p"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout
        except Exception:
            return ""

    async def print_labels(self, labels: list[LabelData]) -> bool:
        """Render all labels into a single multi-page PDF, one CUPS job."""
        if not labels:
            return False

        timestamp = datetime.now().strftime("%a %b %d, %Y  %I:%M %p")

        pages = []
        for label in labels:
            if label.extra:
                pages.append(render_parent_label(label, timestamp))
            else:
                pages.append(render_kid_label(label, timestamp))

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                tmp_path = f.name
                # Save all pages as a single PDF
                pages[0].save(
                    f, format="PDF", resolution=DPI,
                    save_all=True, append_images=pages[1:] if len(pages) > 1 else [],
                )

            result = subprocess.run(
                [
                    "lp",
                    "-d", self.printer_name,
                    "-o", "PageSize=w167h288",
                    "-o", "orientation-requested=4",
                    "-o", "fit-to-page",
                    tmp_path,
                ],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                print(f"Print error: {result.stderr}")
                return False
            return True
        except Exception as e:
            print(f"Print error: {e}")
            return False
        finally:
            if tmp_path:
                Path(tmp_path).unlink(missing_ok=True)

    async def print_label(self, label: LabelData) -> bool:
        """Print a single label."""
        return await self.print_labels([label])


# Singleton
_printer: CupsPrinter | None = None


def get_printer() -> CupsPrinter:
    global _printer
    if _printer is None:
        _printer = CupsPrinter()
    return _printer
