"""
Arabic Text Renderer - Professional Arabic/RTL text rendering for image compositing.

This module renders pixel-perfect Arabic text onto images with professional
typography effects (drop shadows, outlines, glow, gradients). It handles
RTL shaping, ligatures, and multi-line layout correctly.

Usage standalone:
    python arabic_text_renderer.py --text "مرحبا بالعالم" --output ref.png
    python arabic_text_renderer.py --text "بسم الله الرحمن الرحيم" --output ref.png --style naskh --effect shadow

Usage as library:
    from arabic_text_renderer import ArabicTextRenderer
    renderer = ArabicTextRenderer()
    renderer.render_text_image("مرحبا", "output.png", 1152, 896)
    renderer.composite_text_on_image("مرحبا", "background.png", "result.png")
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import argparse
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dreamforge_cli_inventory import (
    add_inventory_arguments,
    find_font_for_style,
    handle_inventory_arguments,
    resolve_font_identifier,
)

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_BIDI = True
except ImportError:
    HAS_BIDI = False
    print("[WARNING] arabic-reshaper or python-bidi not installed. Arabic shaping disabled.")


# ============================================================
# FONT CATALOG
# ============================================================
FONT_CATALOG = {
    "naskh": [
        "C:\\Windows\\Fonts\\DTNASKH0.TTF",
        "C:\\Windows\\Fonts\\DTNASKH1.TTF",
        "C:\\Windows\\Fonts\\DTNASKH2.TTF",
        "C:\\Windows\\Fonts\\arabtype.ttf",   # fallback
        "C:\\Windows\\Fonts\\arial.ttf",       # full Unicode coverage fallback
    ],
    "arabic": [
        "C:\\Windows\\Fonts\\arabtype.ttf",
        "C:\\Windows\\Fonts\\ARABSQ.TTF",
        "C:\\Windows\\Fonts\\DTNASKH0.TTF",
        "C:\\Windows\\Fonts\\arial.ttf",       # full Unicode coverage fallback
    ],
    "default": [
        "C:\\Windows\\Fonts\\arial.ttf",       # best overall Arabic coverage on Windows
        "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\tahoma.ttf",
    ],
}


def find_font(style="default", custom_path=None, random_font=False):
    """Find an available font, trying the requested style first then falling back."""
    resolved = resolve_font_identifier(custom_path)
    if resolved and os.path.exists(resolved):
        return resolved

    try:
        return find_font_for_style(style, custom_path=custom_path, random_choice=random_font)
    except FileNotFoundError:
        pass

    import random
    
    # Try requested style first
    available = []
    for path in FONT_CATALOG.get(style, []):
        if os.path.exists(path):
            available.append(path)
            
    if available:
        if random_font:
            return random.choice(available)
        return available[0]

    # Fallback through all categories
    all_fonts = []
    for cat_name, paths in FONT_CATALOG.items():
        for path in paths:
            if os.path.exists(path):
                all_fonts.append(path)
                
    if all_fonts:
        if random_font:
            return random.choice(all_fonts)
        return all_fonts[0]

    raise FileNotFoundError("No suitable Arabic-compatible font found on this system.")


def shape_arabic(text):
    """Apply Arabic reshaping and BiDi algorithm for correct RTL rendering."""
    if not HAS_BIDI:
        return text
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)


# ============================================================
# TEXT EFFECT RENDERERS
# ============================================================
def _draw_text_with_outline(draw, position, text, font, fill, outline_color, outline_width):
    """Draw text with an outline/stroke effect."""
    x, y = position
    # Draw outline by offsetting in all directions
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx * dx + dy * dy <= outline_width * outline_width:
                draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    # Draw main text on top
    draw.text(position, text, font=font, fill=fill)


def _create_shadow_layer(size, position, text, font, shadow_color, shadow_offset, shadow_blur):
    """Create a drop shadow on a separate layer."""
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sx = position[0] + shadow_offset[0]
    sy = position[1] + shadow_offset[1]
    sdraw.text((sx, sy), text, font=font, fill=shadow_color)
    if shadow_blur > 0:
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=shadow_blur))
    return shadow


def _create_glow_layer(size, position, text, font, glow_color, glow_radius):
    """Create a glow effect on a separate layer."""
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.text(position, text, font=font, fill=glow_color)
    glow = glow.filter(ImageFilter.GaussianBlur(radius=glow_radius))
    return glow


# ============================================================
# MAIN RENDERER CLASS
# ============================================================
class ArabicTextRenderer:
    """Professional Arabic text renderer with compositing capabilities."""

    def __init__(self, font_style="default", font_path=None, random_font=False):
        self.font_path = find_font(font_style, font_path, random_font)
        print(f"[TextRenderer] Using font: {self.font_path}")

    def _fit_font_size(self, draw, text, max_width, max_height, start_size=200, min_size=16):
        """Find the largest font size that fits within the given dimensions."""
        for size in range(start_size, min_size - 1, -2):
            font = ImageFont.truetype(self.font_path, size)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            if tw <= max_width and th <= max_height:
                return font, size, tw, th
        font = ImageFont.truetype(self.font_path, min_size)
        bbox = draw.textbbox((0, 0), text, font=font)
        return font, min_size, bbox[2] - bbox[0], bbox[3] - bbox[1]

    def _measure_text(self, draw, text, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1], bbox[1]

    def _split_long_word(self, draw, word, font, max_width):
        """Split a single oversized word without dropping any characters."""
        pieces = []
        current = ""
        for char in word:
            candidate = current + char
            shaped_candidate = shape_arabic(candidate)
            width, _, _ = self._measure_text(draw, shaped_candidate, font)
            if current and width > max_width:
                pieces.append(current)
                current = char
            else:
                current = candidate
        if current:
            pieces.append(current)
        return pieces

    def _wrap_paragraph(self, draw, paragraph, font, max_width):
        """Word-wrap a raw paragraph, measuring shaped RTL display text."""
        words = paragraph.split()
        if not words:
            return []

        lines = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            shaped_candidate = shape_arabic(candidate)
            width, _, _ = self._measure_text(draw, shaped_candidate, font)
            if width <= max_width:
                current = candidate
                continue

            if current:
                lines.append(current)
                current = ""

            shaped_word = shape_arabic(word)
            word_width, _, _ = self._measure_text(draw, shaped_word, font)
            if word_width <= max_width:
                current = word
            else:
                lines.extend(self._split_long_word(draw, word, font, max_width))

        if current:
            lines.append(current)
        return lines

    def _shape_lines(self, draw, text, font, max_width, wrap=True, max_lines=None):
        """Return shaped visual lines, optionally auto-wrapped to the text box."""
        raw_lines = text.split("\\n") if "\\n" in text else text.split("\n")
        raw_lines = [line.strip() for line in raw_lines if line.strip()]
        if not raw_lines:
            raw_lines = [text]

        wrapped = []
        for raw_line in raw_lines:
            if wrap:
                wrapped.extend(self._wrap_paragraph(draw, raw_line, font, max_width))
            else:
                wrapped.append(raw_line)

        shaped = [shape_arabic(line) for line in wrapped if line.strip()]
        if not shaped:
            shaped = [shape_arabic(text)]

        if max_lines and len(shaped) > max_lines:
            return shaped, False
        return shaped, True

    def _fit_text_block(
        self,
        draw,
        text,
        max_width,
        max_height,
        start_size=200,
        min_size=16,
        line_spacing=1.4,
        wrap=True,
        max_lines=None,
    ):
        """Fit a complete text block after Arabic shaping and optional wrapping."""
        fallback = None
        for size in range(start_size, min_size - 1, -2):
            font = ImageFont.truetype(self.font_path, size)
            shaped_lines, line_count_ok = self._shape_lines(
                draw, text, font, max_width, wrap=wrap, max_lines=max_lines
            )
            metrics, total_h = self._compute_multiline(draw, shaped_lines, font, line_spacing)
            max_lw = max((m[0] for m in metrics), default=0)
            fallback = (font, size, shaped_lines, metrics, total_h)
            if line_count_ok and max_lw <= max_width and total_h <= max_height:
                return fallback

        return fallback

    def _compute_multiline(self, draw, lines, font, line_spacing=1.4):
        """Compute total height and per-line metrics for multi-line text."""
        metrics = []
        total_h = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            lw = bbox[2] - bbox[0]
            lh = bbox[3] - bbox[1]
            ly_off = bbox[1]  # y offset from textbbox
            metrics.append((lw, lh, ly_off))
            total_h += int(lh * line_spacing)
        # Remove extra spacing after last line
        if metrics:
            total_h -= int(metrics[-1][1] * (line_spacing - 1))
        return metrics, total_h

    def render_text_image(
        self,
        text,
        output_path,
        width=1152,
        height=896,
        padding=60,
        text_color=(255, 255, 255),
        bg_color=(0, 0, 0),
        effect="none",
        outline_color=(0, 0, 0),
        outline_width=3,
        shadow_color=(0, 0, 0, 180),
        shadow_offset=(4, 4),
        shadow_blur=6,
        glow_color=(255, 255, 255, 100),
        glow_radius=15,
        position="center",
        font_size=None,
        line_spacing=1.4,
        wrap=True,
        max_lines=None,
    ):
        """
        Render Arabic text onto a solid-color background image.

        This is used to create ControlNet reference images (black bg + white text)
        or standalone text images.

        Args:
            text: Arabic text string (can include \\n for multi-line)
            output_path: Where to save the result
            width, height: Image dimensions
            padding: Pixel padding from edges
            text_color: RGB tuple for text
            bg_color: RGB tuple for background
            effect: "none", "outline", "shadow", "glow", "all"
            position: "center", "top", "bottom" or (x, y) tuple
            font_size: Fixed font size (None = auto-fit)
            line_spacing: Multiplier for line height
        """
        # Create image
        img = Image.new("RGBA", (width, height), bg_color + (255,) if len(bg_color) == 3 else bg_color)
        draw = ImageDraw.Draw(img)

        # Determine font size
        max_text_w = width - padding * 2
        max_text_h = height - padding * 2

        if font_size:
            font = ImageFont.truetype(self.font_path, font_size)
            actual_size = font_size
            shaped_lines, _ = self._shape_lines(
                draw, text, font, max_text_w, wrap=wrap, max_lines=max_lines
            )
            metrics, total_h = self._compute_multiline(draw, shaped_lines, font, line_spacing)
        else:
            font, actual_size, shaped_lines, metrics, total_h = self._fit_text_block(
                draw,
                text,
                max_text_w,
                max_text_h,
                start_size=min(300, height // 2),
                line_spacing=line_spacing,
                wrap=wrap,
                max_lines=max_lines,
            )

        # Compute starting Y based on position
        if isinstance(position, tuple):
            start_x, start_y = position
        elif position == "top":
            start_y = padding
            start_x = None  # center horizontally
        elif position == "bottom":
            start_y = height - padding - total_h
            start_x = None
        else:  # center
            start_y = (height - total_h) // 2
            start_x = None

        # Render each line
        current_y = start_y
        for i, (line, (lw, lh, ly_off)) in enumerate(zip(shaped_lines, metrics)):
            # Horizontal centering
            if start_x is None:
                lx = (width - lw) // 2
            else:
                lx = start_x

            pos = (lx, current_y - ly_off)

            # Apply effects on separate layers
            if effect in ("shadow", "all"):
                shadow_layer = _create_shadow_layer(
                    (width, height), pos, line, font, shadow_color, shadow_offset, shadow_blur
                )
                img = Image.alpha_composite(img, shadow_layer)

            if effect in ("glow", "all"):
                glow_layer = _create_glow_layer(
                    (width, height), pos, line, font, glow_color, glow_radius
                )
                img = Image.alpha_composite(img, glow_layer)

            # Re-create draw on potentially composited image
            draw = ImageDraw.Draw(img)

            if effect in ("outline", "all"):
                _draw_text_with_outline(draw, pos, line, font, text_color, outline_color, outline_width)
            else:
                draw.text(pos, line, font=font, fill=text_color)

            current_y += int(lh * line_spacing)

        # Save
        img.convert("RGB").save(output_path)
        print(f"[TextRenderer] Reference image saved: {output_path} ({width}x{height})")
        return output_path

    def composite_text_on_image(
        self,
        text,
        background_path,
        output_path,
        padding=60,
        text_color=(255, 255, 255),
        effect="shadow",
        outline_color=(20, 20, 20),
        outline_width=3,
        shadow_color=(0, 0, 0, 200),
        shadow_offset=(5, 5),
        shadow_blur=8,
        glow_color=(255, 255, 255, 80),
        glow_radius=20,
        position="center",
        font_size=None,
        opacity=1.0,
        line_spacing=1.4,
        text_area_darken=0.0,
        wrap=True,
        max_lines=None,
    ):
        """
        Composite Arabic text directly onto an existing image.

        This is the KEY function for the hybrid pipeline:
        1. DreamForge generates the scene/background
        2. This function overlays pixel-perfect Arabic text

        Args:
            text: Arabic text string
            background_path: Path to the AI-generated background image
            output_path: Where to save the final composited result
            text_area_darken: 0.0-1.0, darken the text area for readability
            opacity: 0.0-1.0, overall text opacity
            (other args same as render_text_image)
        """
        # Load background
        bg = Image.open(background_path).convert("RGBA")
        width, height = bg.size

        # Create transparent text layer
        txt_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_layer)

        # Font
        max_text_w = width - padding * 2
        max_text_h = height - padding * 2

        if font_size:
            font = ImageFont.truetype(self.font_path, font_size)
            shaped_lines, _ = self._shape_lines(
                draw, text, font, max_text_w, wrap=wrap, max_lines=max_lines
            )
            metrics, total_h = self._compute_multiline(draw, shaped_lines, font, line_spacing)
        else:
            font, actual_size, shaped_lines, metrics, total_h = self._fit_text_block(
                draw,
                text,
                max_text_w,
                max_text_h,
                start_size=min(300, height // 2),
                line_spacing=line_spacing,
                wrap=wrap,
                max_lines=max_lines,
            )

        # Position
        if isinstance(position, tuple):
            start_x, start_y = position
        elif position == "top":
            start_y = padding
            start_x = None
        elif position == "bottom":
            start_y = height - padding - total_h
            start_x = None
        else:
            start_y = (height - total_h) // 2
            start_x = None

        # Optional: darken text area for better readability
        if text_area_darken > 0:
            darken_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            dd = ImageDraw.Draw(darken_layer)
            # Compute bounding rect of all text
            max_lw = max(m[0] for m in metrics) if metrics else 0
            rect_pad = 30
            rx = ((width - max_lw) // 2) - rect_pad if start_x is None else start_x - rect_pad
            ry = start_y - rect_pad
            rw = max_lw + rect_pad * 2
            rh = total_h + rect_pad * 2
            alpha = int(255 * text_area_darken)
            dd.rounded_rectangle(
                [(rx, ry), (rx + rw, ry + rh)],
                radius=20,
                fill=(0, 0, 0, alpha)
            )
            bg = Image.alpha_composite(bg, darken_layer)

        # Render text lines onto transparent layer
        current_y = start_y
        for line, (lw, lh, ly_off) in zip(shaped_lines, metrics):
            lx = (width - lw) // 2 if start_x is None else start_x
            pos = (lx, current_y - ly_off)

            if effect in ("shadow", "all"):
                shadow = _create_shadow_layer(
                    (width, height), pos, line, font, shadow_color, shadow_offset, shadow_blur
                )
                txt_layer = Image.alpha_composite(txt_layer, shadow)
                draw = ImageDraw.Draw(txt_layer)

            if effect in ("glow", "all"):
                glow = _create_glow_layer(
                    (width, height), pos, line, font, glow_color, glow_radius
                )
                txt_layer = Image.alpha_composite(txt_layer, glow)
                draw = ImageDraw.Draw(txt_layer)

            if effect in ("outline", "all"):
                _draw_text_with_outline(draw, pos, line, font, text_color, outline_color, outline_width)
            else:
                draw.text(pos, line, font=font, fill=text_color)

            current_y += int(lh * line_spacing)

        # Apply opacity
        if opacity < 1.0:
            alpha = txt_layer.split()[3]
            alpha = alpha.point(lambda p: int(p * opacity))
            txt_layer.putalpha(alpha)

        # Composite
        result = Image.alpha_composite(bg, txt_layer)
        result.convert("RGB").save(output_path, quality=95)
        print(f"[TextRenderer] Composited image saved: {output_path}")
        
        actual_font_size = font_size if font_size else actual_size
        return output_path, actual_font_size

    def create_text_mask(
        self,
        text,
        output_path,
        width=1152,
        height=896,
        padding=60,
        position="center",
        font_size=None,
        line_spacing=1.4,
        dilate=10,
        wrap=True,
        max_lines=None,
    ):
        """
        Create a binary mask image where the text area is white (255) and
        the rest is black (0). Used for inpainting workflows.

        Args:
            dilate: Pixels to expand the mask beyond the text edges
        """
        # Create mask
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)

        max_text_w = width - padding * 2
        max_text_h = height - padding * 2

        if font_size:
            font = ImageFont.truetype(self.font_path, font_size)
            shaped_lines, _ = self._shape_lines(
                draw, text, font, max_text_w, wrap=wrap, max_lines=max_lines
            )
            metrics, total_h = self._compute_multiline(draw, shaped_lines, font, line_spacing)
        else:
            font, _, shaped_lines, metrics, total_h = self._fit_text_block(
                draw,
                text,
                max_text_w,
                max_text_h,
                start_size=min(300, height // 2),
                line_spacing=line_spacing,
                wrap=wrap,
                max_lines=max_lines,
            )

        if isinstance(position, tuple):
            start_x, start_y = position
        elif position == "top":
            start_y = padding
            start_x = None
        elif position == "bottom":
            start_y = height - padding - total_h
            start_x = None
        else:
            start_y = (height - total_h) // 2
            start_x = None

        current_y = start_y
        for line, (lw, lh, ly_off) in zip(shaped_lines, metrics):
            lx = (width - lw) // 2 if start_x is None else start_x
            pos = (lx, current_y - ly_off)
            draw.text(pos, line, font=font, fill=255)
            current_y += int(lh * line_spacing)

        # Dilate the mask
        if dilate > 0:
            mask = mask.filter(ImageFilter.MaxFilter(size=dilate * 2 + 1))

        mask.save(output_path)
        print(f"[TextRenderer] Mask image saved: {output_path}")
        return output_path


# ============================================================
# CLI INTERFACE
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="Professional Arabic Text Renderer for DreamForge image compositing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a ControlNet reference (white text on black)
  python arabic_text_renderer.py --text "مرحبا بالعالم" --output ref.png --mode reference

  # Composite text onto an AI-generated image
  python arabic_text_renderer.py --text "بسم الله" --mode composite --background scene.png --output final.png

  # Create an inpaint mask for text area
  python arabic_text_renderer.py --text "النص" --mode mask --output mask.png

  # Multi-line with Naskh font and shadow effect
  python arabic_text_renderer.py --text "السلام عليكم\\nمرحبا بالعالم" --style naskh --effect shadow
        """
    )
    add_inventory_arguments(parser)
    parser.add_argument("--text", default=None, help="Arabic text to render (use \\\\n for newlines)")
    parser.add_argument("--output", default="arabic_reference.png", help="Output image path")
    parser.add_argument("--width", type=int, default=1152, help="Image width")
    parser.add_argument("--height", type=int, default=896, help="Image height")
    parser.add_argument("--mode", default="reference",
                        choices=["reference", "composite", "mask"],
                        help="reference=white-on-black for ControlNet, composite=overlay on image, mask=inpaint mask")
    parser.add_argument("--background", default=None, help="Background image path (required for composite mode)")
    parser.add_argument("--style", default="default",
                        choices=["default", "naskh", "arabic"],
                        help="Font style category")
    parser.add_argument("--font", default=None, help="Custom font file path")
    parser.add_argument("--effect", default="none",
                        choices=["none", "outline", "shadow", "glow", "all"],
                        help="Text effect to apply")
    parser.add_argument("--position", default="center",
                        choices=["center", "top", "bottom"],
                        help="Text position")
    parser.add_argument("--font-size", type=int, default=None, help="Fixed font size (auto if not set)")
    parser.add_argument("--opacity", type=float, default=1.0, help="Text opacity (0.0-1.0)")
    parser.add_argument("--darken", type=float, default=0.0,
                        help="Darken background behind text (0.0-1.0, composite mode only)")
    parser.add_argument("--padding", type=int, default=60, help="Padding from edges in pixels")
    parser.add_argument("--text-color", default="255,255,255", help="Text color as R,G,B")
    parser.add_argument("--dilate", type=int, default=10, help="Mask dilation in pixels (mask mode only)")
    parser.add_argument("--no-wrap", action="store_true",
                        help="Disable automatic word wrapping inside the text area")
    parser.add_argument("--max-lines", type=int, default=None,
                        help="Maximum wrapped lines to fit before shrinking the font")
    parser.add_argument("--line-spacing", type=float, default=1.4,
                        help="Line spacing multiplier")

    args = parser.parse_args()

    if handle_inventory_arguments(args):
        return

    if not args.text:
        parser.error("--text is required unless you use --list-fonts, --list-models, or --list-inventory")

    # Parse text color
    text_color = tuple(int(c) for c in args.text_color.split(","))

    renderer = ArabicTextRenderer(font_style=args.style, font_path=args.font)

    if args.mode == "reference":
        renderer.render_text_image(
            text=args.text,
            output_path=args.output,
            width=args.width,
            height=args.height,
            padding=args.padding,
            text_color=text_color,
            bg_color=(0, 0, 0),
            effect=args.effect,
            position=args.position,
            font_size=args.font_size,
            line_spacing=args.line_spacing,
            wrap=not args.no_wrap,
            max_lines=args.max_lines,
        )
    elif args.mode == "composite":
        if not args.background:
            print("ERROR: --background is required for composite mode")
            sys.exit(1)
        renderer.composite_text_on_image(
            text=args.text,
            background_path=args.background,
            output_path=args.output,
            padding=args.padding,
            text_color=text_color,
            effect=args.effect,
            position=args.position,
            font_size=args.font_size,
            opacity=args.opacity,
            text_area_darken=args.darken,
            line_spacing=args.line_spacing,
            wrap=not args.no_wrap,
            max_lines=args.max_lines,
        )
    elif args.mode == "mask":
        renderer.create_text_mask(
            text=args.text,
            output_path=args.output,
            width=args.width,
            height=args.height,
            padding=args.padding,
            position=args.position,
            font_size=args.font_size,
            dilate=args.dilate,
            line_spacing=args.line_spacing,
            wrap=not args.no_wrap,
            max_lines=args.max_lines,
        )


if __name__ == "__main__":
    main()
