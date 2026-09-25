#!/usr/bin/env python3
"""themely: wallpaper-driven theme engine. Spec: docs/superpowers/specs/2026-09-25-themely-design.md"""
import colorsys
import os
import re
import subprocess
from pathlib import Path

HOME = Path(os.environ.get("THEMELY_HOME") or Path.home())
CFG = HOME / ".config"
DATA = CFG / "themely"
THEMES = DATA / "themes"
CURRENT = DATA / "current"
HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


# ---------- colors ----------

def hls(hex_):
    h = hex_.lstrip("#")
    return colorsys.rgb_to_hls(*(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)))


def from_hls(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h % 1, l, s)
    return "#%02x%02x%02x" % tuple(round(c * 255) for c in (r, g, b))


def norm_hex(value):
    m = HEX.match(value.strip())
    if not m:
        raise ValueError(f"not a #rrggbb color: {value!r}")
    return "#" + m.group(1).lower()


def palette(accent):
    accent = norm_hex(accent)
    h, l, s = hls(accent)
    tint = min(s, 0.25)
    p = {
        "accent": accent,
        "accent2": from_hls(h - 25 / 360, l, s),
        "bg": from_hls(h, 0.13, tint),
        "surface0": from_hls(h, 0.19, tint),
        "surface1": from_hls(h, 0.25, tint),
        "overlay": from_hls(h, 0.40, tint),
        "fg": from_hls(h, 0.88, 0.45),
        "fg_muted": from_hls(h, 0.70, 0.45),
    }
    # Catppuccin pastels keep the hues that carry meaning (red = error, green = ok).
    normal = [p["surface1"], "#f38ba8", "#a6e3a1", "#f9e2af", accent, "#f5c2e7", "#94e2d5", p["fg_muted"]]
    bright = [p["overlay"], "#f38ba8", "#a6e3a1", "#f9e2af", p["accent2"], "#f5c2e7", "#94e2d5", p["fg"]]
    for i, c in enumerate(normal + bright):
        p[f"color{i}"] = c
    return p


def swatches(image):
    """Up to 8 colors from the image, the automatic accent pick first."""
    out = subprocess.run(
        ["magick", str(image), "-resize", "64x64", "-colors", "8", "-format", "%c", "histogram:info:-"],
        capture_output=True, text=True, check=True).stdout
    found = [(int(n), c.lower()) for n, c in re.findall(r"^\s*(\d+):.*?(#[0-9A-Fa-f]{6})", out, re.M)]
    if not found:
        raise ValueError(f"no colors found in {image}")
    total = sum(n for n, _ in found)

    def score(item):
        n, c = item
        _, l, s = hls(c)
        if s < 0.2 or l < 0.2 or l > 0.9:
            return -1
        return s * n / total * (1 - abs(l - 0.65))

    found.sort(key=score, reverse=True)
    h, l, s = hls(found[0][1])
    if score(found[0]) < 0:  # all gray/black/white: lift the most common color into a usable accent
        h, _, s = hls(max(found)[1])
        l, s = 0.65, max(s, 0.4)
    auto = from_hls(h, min(max(l, 0.55), 0.80), s)
    return [auto] + [c for _, c in found if c != auto]
