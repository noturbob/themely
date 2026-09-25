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


def test_store():
    wp = image("store.png", "-size", "80x80", "xc:#3060ff")
    assert t.slugify("Ocean Blue!") == "ocean-blue" and t.slugify("!!!") == "theme"
    slug = t.save("Ocean Blue", wallpaper=str(wp))
    assert slug == "ocean-blue"
    # Same name again: new slug, the first theme is untouched.
    assert t.save("Ocean Blue", wallpaper=str(wp)) == "ocean-blue-2"
    # Edit: keeps the stored wallpaper when none is given.
    t.save("Ocean Blue", accent="#123456", opacity=0.9, slug="ocean-blue")
    themes = {x["slug"]: x for x in t.list_themes()}
    assert themes["ocean-blue"]["accent"] == "#123456" and themes["ocean-blue"]["opacity"] == 0.9
    assert Path(themes["ocean-blue"]["wallpaper"]).is_file()
    # Bad input: error, nothing written.
    raises(ValueError, t.save, "  ", wallpaper=str(wp))
    raises(ValueError, t.save, "x", wallpaper=str(HOME / "missing.png"))
    raises(ValueError, t.save, "x", wallpaper=str(wp), opacity=0.1)
    raises(ValueError, t.save, "x", wallpaper=str(wp), accent="#12")
    raises(ValueError, t.save, "x")
    raises(ValueError, t.save, "x", slug="../etc")
    raises(ValueError, t.delete, "../etc")
    assert not (t.THEMES / "x").exists()
    # A broken theme.json doesn't break the list.
    (t.THEMES / "broken").mkdir()
    (t.THEMES / "broken/theme.json").write_text("{nope")
    assert "broken" not in {x["slug"] for x in t.list_themes()}
    shutil.rmtree(t.THEMES / "broken")
    t.delete("ocean-blue-2")
    assert "ocean-blue-2" not in {x["slug"] for x in t.list_themes()}


if __name__ == "__main__":
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_"):
                fn()
                print("ok", name)
    finally:
        shutil.rmtree(HOME)
