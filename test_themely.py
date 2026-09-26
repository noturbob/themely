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


def test_replace_block():
    text = "a\n  // >>> themely x\n  old\n  // <<< themely\nb\n"
    out = t.replace_block(text, "x", "  new", c="//")
    assert out == "a\n  // >>> themely x\n  new\n  // <<< themely\nb\n", out
    assert t.replace_block(out, "x", "  new\n", c="//") == out
    two = "# >>> themely a\n# <<< themely\nmid\n# >>> themely b\n# <<< themely\n"
    assert t.replace_block(two, "b", "B\n") == "# >>> themely a\n# <<< themely\nmid\n# >>> themely b\nB\n# <<< themely\n"
    raises(ValueError, t.replace_block, "no markers\n", "x", "y\n")


def jsonc(text):
    text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", text))


def test_apply():
    t.run = lambda *cmd: None  # don't signal the real desktop
    t.has = lambda cmd: False  # behave the same whatever is installed here
    t.gsetting = lambda key: "'Adwaita'"
    t.base_css = lambda version: "window { background: #202020; }\n"
    t.TARGETS = [x for x in t.TARGETS if x[0] != "wallpaper"]
    cfg = HOME / ".config"
    files = {
        "niri/config.kdl": "layout {\n    // >>> themely border\n    // <<< themely\n}\n// >>> themely opacity\n// <<< themely\n",
        "kitty/kitty.conf": "font_size 15\n# >>> themely colors\n# <<< themely\n",
        "flowbar/config.ini": "[theme]\n# >>> themely colors\n# <<< themely\npreset = x\n",
        "mako/config": "width=300\n# >>> themely colors\n# <<< themely\n",
        "fuzzel/fuzzel.ini": "[colors]\n# >>> themely colors\n# <<< themely\n[border]\nwidth=2\n",
        "Code/User/settings.json": '{\n  // >>> themely colors\n  // <<< themely\n  "b": [1,],\n}\n',
        "zen/profiles.ini": "[Install1]\nDefault=abc.default\n",
    }
    for rel, text in files.items():
        (cfg / rel).parent.mkdir(parents=True, exist_ok=True)
        (cfg / rel).write_text(text)
    (cfg / "vesktop").mkdir()
    prof = cfg / "zen/abc.default"
    prof.mkdir()

    slug = t.save("Test", wallpaper=str(image("apply.png", "-size", "40x40", "xc:#89b4fa")), accent="#89b4fa", opacity=0.8)
    assert t.apply(slug) == []
    niri = (cfg / "niri/config.kdl").read_text()
    assert 'active-color "#89b4fa"' in niri and "opacity 0.8" in niri
    # One rule for every window (consistent transparency), except kitty which does its own background opacity.
    rule = niri[niri.index(">>> themely opacity"):]
    assert "match" not in rule and 'exclude app-id=r#"^kitty$"#' in rule, rule
    assert "background_opacity 0.8" in (cfg / "kitty/kitty.conf").read_text()
    assert "preset = x" in (cfg / "flowbar/config.ini").read_text()
    assert "background-color=" in (cfg / "mako/config").read_text()
    assert "[border]\nwidth=2" in (cfg / "fuzzel/fuzzel.ini").read_text()
    vs = jsonc((cfg / "Code/User/settings.json").read_text())
    assert vs["workbench.colorCustomizations"]["focusBorder"] == "#89b4fa" and vs["b"] == [1]
    assert "@name themely" in (cfg / "vesktop/themes/themely.css").read_text()
    assert "--zen-primary-color: #89b4fa" in (prof / "chrome/userChrome.css").read_text()
    assert "legacyUserProfileCustomizations" in (prof / "user.js").read_text()
    assert (HOME / ".local/share/themes/Themely-a/gtk-4.0/gtk.css").exists()
    assert t.current_slug() == slug

    # Re-apply: nothing changes, backup still holds the pre-themely file.
    kitty = (cfg / "kitty/kitty.conf").read_text()
    assert t.apply(slug) == [] and (cfg / "kitty/kitty.conf").read_text() == kitty
    assert (cfg / "kitty/kitty.conf.themely-bak").read_text() == files["kitty/kitty.conf"]

    # Missing markers fail only that target; missing apps are skipped.
    (cfg / "mako/config").write_text("no markers\n")
    (cfg / "fuzzel/fuzzel.ini").unlink()
    assert t.apply(slug) == ["mako"]
    raises(ValueError, t.delete, slug)


def test_wrong_shape_theme_json():
    # Parses as JSON but isn't a theme: skipped by list, clean error from apply.
    for slug, text in {"empty": "{}", "arr": "[]", "badname": '{"name": 5, "accent": "#123456", "opacity": 0.8}',
                       "noopacity": '{"name": "n", "accent": "#123456"}'}.items():
        (t.THEMES / slug).mkdir()
        (t.THEMES / slug / "theme.json").write_text(text)
    slugs = {x["slug"] for x in t.list_themes()}
    assert not slugs & {"empty", "arr", "badname", "noopacity"}, slugs
    raises(ValueError, t.apply, "noopacity")
    for slug in ("empty", "arr", "badname", "noopacity"):
        shutil.rmtree(t.THEMES / slug)


def test_recolor():
    p = t.palette("#50c87c")
    ah = t.hls(p["accent"])[0]
    css = t.recolor("a { color: #15539e; background: #202020; border-color: rgba(21, 83, 158, 0.5); "
                    "outline-color: #e01b24; }", p)
    blue, gray = re.findall(r"#[0-9a-f]{6}", css)[:2]
    assert abs(t.hls(blue)[0] - ah) < 0.02 and abs(t.hls(blue)[1] - t.hls("#15539e")[1]) < 0.02, blue
    assert abs(t.hls(gray)[0] - ah) < 0.02 and abs(t.hls(gray)[1] - t.hls("#202020")[1]) < 0.02, gray
    r, g, b = map(int, re.search(r"rgba\((\d+), (\d+), (\d+), 0.5\)", css).groups())
    assert abs(t.hls("#%02x%02x%02x" % (r, g, b))[0] - ah) < 0.02, css
    assert "#e01b24" in css  # red keeps its meaning


def test_gtk_live_theme():
    calls = []
    t.run = lambda *cmd: calls.append(cmd)
    state = {"gtk-theme": "'Adwaita'"}
    t.gsetting = lambda key: state[key]
    t.base_css = lambda version: "window { background: #202020; color: #15539e; }\n"
    gtk3 = HOME / ".config/gtk-3.0"
    gtk3.mkdir(parents=True, exist_ok=True)
    # Left over from the old static approach: the import goes, the user's own rules stay.
    (gtk3 / "gtk.css").write_text("@import 'themely.css';\nwindow { padding: 3px; }\n")
    (gtk3 / "themely.css").write_text("stale\n")
    p = t.palette("#89b4fa")
    t.gtk(p, 0.8)
    assert (gtk3 / "gtk.css").read_text() == "window { padding: 3px; }\n"
    assert not (gtk3 / "themely.css").exists()
    themes = HOME / ".local/share/themes"
    css = (themes / "Themely-a/gtk-3.0/gtk.css").read_text()
    assert "#202020" not in css and "#15539e" not in css and css.startswith("window {"), css
    assert "@define-color theme_selected_bg_color #89b4fa;" in css
    assert (themes / "Themely-a/gtk-4.0/gtk.css").exists() and (themes / "Themely-a/index.theme").exists()
    assert ("gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", "Themely-a") in calls
    assert ("gsettings", "set", "org.gnome.desktop.interface", "color-scheme", "prefer-dark") in calls
    # Next switch flips to the other slot: a changed theme name is what makes running GTK apps reload.
    state["gtk-theme"] = "'Themely-a'"
    t.gtk(t.palette("#50c87c"), 0.8)
    assert ("gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", "Themely-b") in calls
    assert "#50c87c" in (themes / "Themely-b/gtk-3.0/gtk.css").read_text()
    # A gtk.css that was only our import disappears; a symlinked one is never touched.
    (gtk3 / "gtk.css").write_text("@import 'themely.css';\n")
    t.gtk(p, 0.8)
    assert not (gtk3 / "gtk.css").exists()
    other = HOME / "theme-owned.css"
    other.write_text("@import 'themely.css';\n")
    (gtk3 / "gtk.css").symlink_to(other)
    t.gtk(p, 0.8)
    assert other.read_text() == "@import 'themely.css';\n"
    (gtk3 / "gtk.css").unlink()
    t.run = lambda *cmd: None


def test_qt():
    qt5 = HOME / ".config/qt5ct"
    qt5.mkdir(parents=True, exist_ok=True)
    (qt5 / "qt5ct.conf").write_text("[Appearance]\ncolor_scheme_path=/usr/share/qt5ct/colors/darker.conf\n"
                                    "custom_palette=false\nstyle=Fusion\n\n[Fonts]\nfixed=x\n")
    p = t.palette("#89b4fa")
    t.qt(p, 0.8)
    t.qt(p, 0.8)
    conf5 = (qt5 / "qt5ct.conf").read_text()
    assert conf5 == (f"[Appearance]\ncolor_scheme_path={qt5}/themely-colors.conf\n"
                     "custom_palette=true\nstyle=Fusion\n\n[Fonts]\nfixed=x\n"), conf5
    # qt6ct had no config: created, pointing at its own copy of the palette.
    conf6 = (HOME / ".config/qt6ct/qt6ct.conf").read_text()
    assert f"color_scheme_path={HOME}/.config/qt6ct/themely-colors.conf" in conf6 and "custom_palette=true" in conf6
    colors = (HOME / ".config/qt6ct/themely-colors.conf").read_text()
    active = re.search(r"^active_colors=(.*)$", colors, re.M).group(1).split(", ")
    assert len(active) == 21 and active[12] == "#ff89b4fa" and active[10] == "#ff" + p["bg"][1:], active


def test_kde_colors():
    kg = HOME / ".config/kdeglobals"
    kg.write_text("[KFileDialog Settings]\nAllow Expansion=false\n")
    p = t.palette("#89b4fa")
    t.qt(p, 0.8)
    t.qt(p, 0.8)
    text = kg.read_text()
    assert text.startswith("[KFileDialog Settings]\nAllow Expansion=false\n"), text
    assert text.count("[Colors:View]") == 1
    rgb = lambda h: ",".join(str(int(h[i:i + 2], 16)) for i in (1, 3, 5))
    view = text[text.index("[Colors:View]"):].split("\n\n")[0]
    assert f"BackgroundNormal={rgb(p['bg'])}" in view and f"DecorationFocus={rgb(p['accent'])}" in view, view
    sel = text[text.index("[Colors:Selection]"):].split("\n\n")[0]
    assert f"BackgroundNormal={rgb(p['accent'])}" in sel, sel
    # A pinned scheme makes KDE apps apply it once at launch and never live-update: never pin, and unpin old ones.
    assert "UiSettings" not in text, text
    kg.write_text(text + "\n[UiSettings]\nColorScheme=Themely\n")
    t.qt(p, 0.8)
    assert "UiSettings" not in kg.read_text(), kg.read_text()
    scheme = (HOME / ".local/share/color-schemes/Themely.colors").read_text()
    assert scheme.startswith("[General]\nName=Themely\n"), scheme
    sview = scheme[scheme.index("[Colors:View]"):].split("\n\n")[0]
    assert f"BackgroundNormal={rgb(p['bg'])}" in sview and f"DecorationFocus={rgb(p['accent'])}" in sview, sview


def test_pywalfox():
    p = t.palette("#50c87c")
    t.pywalfox(p, 0.8)
    data = json.loads((HOME / ".cache/wal/colors.json").read_text())
    colors = list(data["colors"].values())
    # Pywalfox reads colors in order: 0 = browser background, 1/2 = accents, 15 = text.
    assert len(colors) == 16 and colors[0] == p["bg"] and colors[1] == p["accent"] and colors[15] == p["fg"], colors
    assert data["wallpaper"] == str(t.CURRENT / "wallpaper") and data["special"]["background"] == p["bg"]
    # With Pywalfox present, startup-only userChrome overrides would pin stale colors over its live ones.
    prof = HOME / ".config/zen/abc.default"
    t.has = lambda cmd: True
    t.browsers(p, 0.8)
    t.has = lambda cmd: False
    assert "--toolbar-bgcolor" not in (prof / "chrome/userChrome.css").read_text()


def test_vscode_forks():
    # Forks share the settings format; markers are added on first run instead of by hand.
    ag = HOME / ".config/Antigravity/User/settings.json"
    ag.parent.mkdir(parents=True, exist_ok=True)
    ag.write_text('{\n  "workbench.colorTheme": "Tokyo Night",\n}\n')
    p = t.palette("#50c87c")
    t.vscode(p, 0.8)
    t.vscode(p, 0.8)
    text = ag.read_text()
    assert text.count(">>> themely colors") == 1, text
    vs = jsonc(text)
    assert vs["workbench.colorCustomizations"]["focusBorder"] == "#50c87c" and vs["workbench.colorTheme"] == "Tokyo Night"


def test_btop():
    conf = HOME / ".config/btop/btop.conf"
    conf.parent.mkdir(parents=True, exist_ok=True)
    conf.write_text('color_theme = "Default"\ntheme_background = True\nupdate_ms = 2000\n')
    p = t.palette("#50c87c")
    t.btop(p, 0.8)
    t.btop(p, 0.8)
    text = conf.read_text()
    assert text == 'color_theme = "themely"\ntheme_background = False\nupdate_ms = 2000\n', text
    theme = (HOME / ".config/btop/themes/themely.theme").read_text()
    assert f'theme[hi_fg]="{p["accent"]}"' in theme and f'theme[main_fg]="{p["fg"]}"' in theme, theme
    conf.unlink()
    t.btop(p, 0.8)  # no config yet (btop writes it on exit): created with just our keys
    assert 'color_theme = "themely"' in conf.read_text()


def test_prompt():
    p = t.palette("#50c87c")
    t.prompt(p, 0.8)
    text = (HOME / ".cache/themely/prompt.sh").read_text()
    vals = dict(re.findall(r"(\w+)='([\d;]+)'", text))
    assert set(vals) == {"lav", "lav_bg", "blue", "blue_bg", "sap", "sap_bg"}, text
    rgb = lambda h: [int(h[i:i + 2], 16) for i in (1, 3, 5)]
    assert vals["blue"] == ";".join(map(str, rgb(p["accent"])))
    # *_bg = accent blended 30% into the background (same recipe as the hand-made Catppuccin prompt)
    expect = [round(0.3 * a + 0.7 * b) for a, b in zip(rgb(p["accent"]), rgb(p["bg"]))]
    assert vals["blue_bg"] == ";".join(map(str, expect)), vals


def test_spotify():
    calls = []
    t.run = lambda *cmd: calls.append(cmd)
    t.has = lambda cmd: cmd == "spicetify"
    p = t.palette("#50c87c")
    t.spotify(p, 0.8)
    ini = (HOME / ".config/spicetify/Themes/themely/color.ini").read_text()
    assert ini.startswith("[themely]\n") and f"button = {p['accent'][1:]}\n" in ini and f"main = {p['bg'][1:]}\n" in ini, ini
    assert (HOME / ".config/spicetify/Themes/themely/user.css").exists()
    assert ("spicetify", "config", "current_theme", "themely", "color_scheme", "themely") in calls
    assert ("spicetify", "refresh") in calls
    # Open Spotify restarts through the `spotify` launcher: `spicetify restart` runs the bare binary without
    # ~/.config/spotify-flags.conf, and on a Wayland-only session that Spotify exits at once.
    launched = []
    t.launch = lambda *cmd: launched.append(cmd)
    states = iter([True, True, False])  # open; still shutting down; gone
    t.running = lambda name: name == "spotify" and next(states, False)
    calls.clear()
    t.spotify(p, 0.8)
    assert ("spicetify", "restart") not in calls and ("pkill", "-x", "spotify") in calls and launched == [("spotify",)], (calls, launched)
    t.running = lambda name: False
    launched.clear()
    t.spotify(p, 0.8)
    assert launched == []  # closed Spotify stays closed
    calls.clear()
    t.has = lambda cmd: False
    t.spotify(p, 0.8)  # not installed: nothing runs
    assert calls == []
    t.run = lambda *cmd: None


def test_slat():
    calls = []
    t.run = lambda *cmd: calls.append(cmd)
    conf = HOME / ".config/slat/config.toml"
    conf.parent.mkdir(parents=True, exist_ok=True)
    conf.write_text('[theme]\nname = "nord"\naccent = "#ff0000"\n\n[borders]\nstyle = "rounded"\n')
    p = t.palette("#50c87c")
    t.slat(p, 0.8)
    t.slat(p, 0.8)
    text = conf.read_text()
    # TOML rejects duplicate keys: a hand-set colour in [theme] moves inside the managed block.
    assert text.count("accent = ") == 1 and f'accent = "{p["accent"]}"' in text, text
    assert text.startswith('[theme]\nname = "nord"\n# >>> themely colors\n'), text
    assert '[borders]\nstyle = "rounded"\n' in text and f'tab_active_bg = "{p["accent"]}"' in text, text
    assert ("pkill", "-USR1", "-f", t.SLAT_DAEMON) in calls
    # Only the daemon itself: a shell or editor whose command line mentions it must not get the signal.
    daemon = re.compile(t.SLAT_DAEMON)
    assert daemon.search("/home/u/go/bin/slat __daemon") and daemon.search("slat __daemon")
    assert not daemon.search("bash -c 'pgrep slat __daemon; sleep 1'") and not daemon.search("vim slat __daemon.txt")
    conf.write_text('[borders]\nstyle = "rounded"\n')  # no [theme] table yet
    t.slat(p, 0.8)
    assert conf.read_text().startswith('[borders]\nstyle = "rounded"\n\n[theme]\n# >>> themely colors\n'), conf.read_text()
    t.run = lambda *cmd: None


def test_cli():
    assert t.main(["palette", "#89b4fa"]) == 0
    assert t.main(["apply", "nope"]) == 1
    assert t.main(["save", "--name", "x", "--opacity", "5"]) == 1


if __name__ == "__main__":
    try:
        for name, fn in list(globals().items()):
            if name.startswith("test_"):
                fn()
                print("ok", name)
    finally:
        shutil.rmtree(HOME)
