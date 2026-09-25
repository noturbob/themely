"""Run: python3 test_themely.py"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOME = Path(tempfile.mkdtemp())
os.environ["THEMELY_HOME"] = str(HOME)
sys.path.insert(0, str(Path(__file__).parent))
import themely as t  # noqa: E402


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc:
        return
    raise AssertionError(f"{fn.__name__}{a} did not raise {exc.__name__}")


def image(name, *spec):
    path = HOME / name
    subprocess.run(["magick", *spec, str(path)], check=True)
    return path


def test_palette():
    p = t.palette("#89B4FA")
    assert p["accent"] == "#89b4fa"
    assert all(t.HEX.match(v) for v in p.values()), p
    assert t.hls(p["bg"])[1] < 0.15 and t.hls(p["fg"])[1] > 0.85
    assert p["color4"] == "#89b4fa"
    assert sum(k.startswith("color") for k in p) == 16
    for bad in ("89b4f", "#zzzzzz", "", "red"):
        raises(ValueError, t.palette, bad)


def test_swatches():
    # 30% vivid red on 70% gray: the smaller vivid area must win.
    vivid = image("vivid.png", "-size", "100x100", "xc:gray50", "-fill", "#ff3050", "-draw", "rectangle 0,0 29,99")
    h, l, s = t.hls(t.swatches(vivid)[0])
    assert (h < 0.05 or h > 0.9) and 0.55 <= l <= 0.80, (h, l, s)
    # All gray: fallback lifts it into a usable accent.
    gray = image("gray.png", "-size", "50x50", "xc:gray40")
    h, l, s = t.hls(t.swatches(gray)[0])
    assert 0.6 < l < 0.7 and s > 0.35, (h, l, s)
    raises(subprocess.CalledProcessError, t.swatches, HOME / "missing.png")


if __name__ == "__main__":
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_"):
                fn()
                print("ok", name)
    finally:
        shutil.rmtree(HOME)
