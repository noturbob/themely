#!/usr/bin/env python3
"""themely: wallpaper-driven theme engine. Spec: docs/superpowers/specs/2026-09-25-themely-design.md"""
import argparse
import colorsys
import configparser
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
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


# ---------- theme store ----------

def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "theme"


def theme_dir(slug):
    if not SLUG.match(slug or ""):
        raise ValueError(f"bad theme id: {slug!r}")
    d = THEMES / slug
    if not (d / "theme.json").exists():
        raise ValueError(f"no such theme: {slug}")
    return d


def current_slug():
    return CURRENT.resolve().name if CURRENT.exists() else None


def load(path):
    """Read a theme.json; ValueError unless it is a well-formed theme."""
    t = json.loads(path.read_text())
    if not (isinstance(t, dict) and isinstance(t.get("name"), str) and t["name"].strip()
            and isinstance(t.get("accent"), str) and HEX.match(t["accent"])
            and isinstance(t.get("opacity"), (int, float)) and 0.3 <= t["opacity"] <= 1):
        raise ValueError(f"not a valid theme: {path}")
    return t


def list_themes():
    cur = current_slug()
    out = []
    for f in THEMES.glob("*/theme.json"):
        try:
            t = load(f)
        except (OSError, ValueError) as e:
            print(f"themely: skipping {f.parent.name}: {e}", file=sys.stderr)
            continue
        slug = f.parent.name
        out.append({**t, "slug": slug, "wallpaper": str(f.parent / "wallpaper"), "current": slug == cur})
    return sorted(out, key=lambda t: t["name"].lower())


def save(name, wallpaper=None, accent=None, opacity=0.85, slug=None):
    """Create (no slug) or update (slug) a theme. Validates everything before touching disk."""
    name = name.strip()
    if not name:
        raise ValueError("name is required")
    if not 0.3 <= opacity <= 1:
        raise ValueError("opacity must be between 0.3 and 1")
    if slug:
        d = theme_dir(slug)
    else:
        slug = base = slugify(name)
        n = 2
        while (THEMES / slug).exists():
            slug, n = f"{base}-{n}", n + 1
        d = THEMES / slug
    wp = d / "wallpaper"
    src = Path(wallpaper).expanduser() if wallpaper else wp
    if not src.is_file():
        raise ValueError(f"wallpaper not found: {wallpaper}" if wallpaper else "wallpaper is required")
    accent = norm_hex(accent) if accent else swatches(src)[0]
    d.mkdir(parents=True, exist_ok=True)
    if src.resolve() != wp.resolve():
        shutil.copyfile(src, wp)
    theme = {"name": name, "accent": accent, "opacity": round(opacity, 2)}
    (d / "theme.json").write_text(json.dumps(theme, indent=2) + "\n")
    return slug


def delete(slug):
    d = theme_dir(slug)
    if slug == current_slug():
        raise ValueError("can't delete the active theme, switch to another one first")
    shutil.rmtree(d)


# ---------- config editing ----------

def replace_block(text, name, body, c="#"):
    """Replace the lines between `<c> >>> themely <name>` and the next `<c> <<< themely`."""
    c = re.escape(c)
    pat = re.compile(rf"(^[ \t]*{c} >>> themely {name}[ \t]*\n).*?(^[ \t]*{c} <<< themely[ \t]*$)", re.M | re.S)
    if not pat.search(text):
        raise ValueError(f"missing '>>> themely {name}' markers")
    body = body if body.endswith("\n") or not body else body + "\n"
    return pat.sub(lambda m: m.group(1) + body + m.group(2), text, count=1)


def write(path, content):
    """Write only on change; keep a one-time .themely-bak; replace atomically through symlinks."""
    old = path.read_text() if path.exists() else None
    if old == content:
        return
    bak = path.with_name(path.name + ".themely-bak")
    if old is not None and not bak.exists():
        bak.write_text(old)
    real = path.resolve()
    real.parent.mkdir(parents=True, exist_ok=True)
    tmp = real.with_name(real.name + ".themely-tmp")
    tmp.write_text(content)
    os.replace(tmp, real)


def edit(path, blocks, c="#"):
    """Rewrite marker blocks in an app's config. No config file = app not installed = skip."""
    if not path.exists():
        return
    text = path.read_text()
    for name, body in blocks.items():
        text = replace_block(text, name, body, c)
    write(path, text)


def has(cmd):
    return shutil.which(cmd) is not None


def running(name):
    return subprocess.run(["pgrep", "-x", name], capture_output=True).returncode == 0


def launch(*cmd):
    """Start an app detached from themely, so it outlives the apply."""
    subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run(*cmd):
    # Non-zero exit is fine ("not running"); a missing binary raises and fails the target.
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def alpha(o):
    return f"{round(o * 255):02x}"


def css(selector, props):
    return selector + " {\n" + "".join(f"  {k}: {v} !important;\n" for k, v in props.items()) + "}\n"


GENERATED = "/* Generated by themely; edits are overwritten. */\n"


# ---------- targets: fn(palette, opacity) ----------

def niri(p, o):
    edit(CFG / "niri/config.kdl", {
        "border": (
            "    border {\n"
            "        width 2\n"
            f'        active-color "{p["accent"]}"\n'
            f'        inactive-color "{p["surface1"]}"\n'
            '        urgent-color "#f38ba8"\n'
            "    }\n"),
        # Every window, so transparency is consistent; kitty does its own (text-preserving) background opacity.
        "opacity": f'window-rule {{\n    exclude app-id=r#"^kitty$"#\n    opacity {o}\n}}\n',
    }, c="//")


def kitty(p, o):
    colors = "".join(f"color{i} {p[f'color{i}']}\n" for i in range(16))
    edit(CFG / "kitty/kitty.conf", {"colors": (
        f"background {p['bg']}\n"
        f"foreground {p['fg']}\n"
        f"selection_background {p['accent']}\n"
        f"selection_foreground {p['bg']}\n"
        f"cursor {p['accent']}\n"
        f"cursor_text_color {p['bg']}\n"
        f"{colors}"
        "dynamic_background_opacity yes\n"
        f"background_opacity {o}\n")})
    run("pkill", "-USR1", "-x", "kitty")


def flowbar(p, o):
    edit(CFG / "flowbar/config.ini", {"colors": (
        f"accent     = {p['accent']}\n"
        f"accent-2   = {p['accent2']}\n"
        f"background = {p['bg']}\n"
        f"foreground = {p['fg']}\n"
        f"opacity = {o}\n")})  # flowbar watches its config dir and reloads itself


def mako(p, o):
    edit(CFG / "mako/config", {"colors": (
        f"background-color={p['bg']}{alpha(o)}\n"
        f"text-color={p['fg']}\n"
        f"border-color={p['accent']}\n")})
    run("makoctl", "reload")


def fuzzel(p, o):
    h = {k: v[1:] for k, v in p.items()}
    edit(CFG / "fuzzel/fuzzel.ini", {"colors": (
        f"background={h['bg']}{alpha(o)}\n"
        f"text={h['fg']}ff\n"
        f"match={h['accent']}ff\n"
        f"selection={h['surface1']}ff\n"
        f"selection-text={h['fg']}ff\n"
        f"border={h['accent']}ff\n")})


def vscode(p, o):
    bg, s0, s1, a = p["bg"], p["surface0"], p["surface1"], p["accent"]
    colors = {
        "editor.background": bg, "sideBar.background": bg, "activityBar.background": bg,
        "panel.background": bg, "terminal.background": bg, "titleBar.activeBackground": bg,
        "statusBar.background": bg, "editorGroupHeader.tabsBackground": bg, "tab.inactiveBackground": bg,
        "tab.activeBackground": s0, "editorWidget.background": s0, "input.background": s0,
        "dropdown.background": s0, "list.activeSelectionBackground": s1,
        "focusBorder": a, "activityBar.activeBorder": a, "tab.activeBorderTop": a,
        "button.background": a, "button.foreground": bg, "progressBar.background": a,
        "textLink.foreground": a, "editorCursor.foreground": a,
        "statusBarItem.remoteBackground": a, "statusBarItem.remoteForeground": bg,
        "editor.selectionBackground": a + "40", "selection.background": a + "66",
    }
    body = json.dumps(colors, indent=2).replace("\n", "\n  ")
    for app in ("Code", "Antigravity", "VSCodium", "Cursor"):  # VS Code and its forks share the format
        path = CFG / app / "User/settings.json"
        if path.exists() and ">>> themely colors" not in path.read_text():
            text = path.read_text()
            i = text.index("{") + 1
            write(path, text[:i] + "\n  // >>> themely colors\n  // <<< themely" + text[i:])
        edit(path, {"colors": f'  "workbench.colorCustomizations": {body},\n'}, c="//")


def vesktop(p, o):
    if not (CFG / "vesktop").exists():
        return
    header = "/**\n * @name themely\n * @description Generated by themely; edits are overwritten.\n * @author themely\n * @version 1.0.0\n */\n"
    write(CFG / "vesktop/themes/themely.css", header + css(":root, .theme-dark, .visual-refresh", {
        "--background-primary": p["surface0"], "--background-secondary": p["bg"],
        "--background-secondary-alt": p["bg"], "--background-tertiary": p["bg"],
        "--background-floating": p["surface0"],
        "--background-base-lowest": p["bg"], "--background-base-lower": p["bg"],
        "--background-base-low": p["surface0"], "--background-surface-high": p["surface0"],
        "--background-surface-higher": p["surface1"],
        "--background-modifier-hover": p["surface0"], "--background-modifier-selected": p["surface1"],
        "--brand-500": p["accent"], "--brand-560": p["accent"], "--text-link": p["accent"],
        "--text-normal": p["fg"], "--text-default": p["fg"], "--header-primary": p["fg"],
        "--interactive-active": p["fg"], "--text-muted": p["fg_muted"], "--channels-default": p["fg_muted"],
    }))


def gsetting(key):
    return subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", key],
                          capture_output=True, text=True).stdout.strip()


COLOR = re.compile(r"#([0-9a-fA-F]{6})\b|(rgba?\()(\d+),\s*(\d+),\s*(\d+)")


def recolor(css, p):
    """Shift a compiled theme's literal colors: blues → accent hue, grays → theme-tinted grays, same lightness."""
    ah, _, asat = hls(p["accent"])
    tint = min(asat, 0.25)

    def shift(hexc):
        h, l, s = hls(hexc)
        if s < 0.12:
            return from_hls(ah, l, tint)
        if 0.52 < h < 0.70:  # the base theme's blue accent family
            return from_hls(ah, l, s)
        return hexc  # reds/greens/yellows keep their meaning

    def sub(m):
        if m.group(1):
            return shift("#" + m.group(1))
        new = shift("#%02x%02x%02x" % tuple(int(m.group(i)) for i in (3, 4, 5)))
        return m.group(2) + ", ".join(str(int(new[i:i + 2], 16)) for i in (1, 3, 5))
    return COLOR.sub(sub, css)


def base_css(version):
    """GTK's built-in dark theme (compiled CSS with literal colors), read from the GTK library's resources."""
    path = {"3.0": "/org/gtk/libgtk/theme/Adwaita/gtk-contained-dark.css",
            "4.0": "/org/gtk/libgtk/theme/Default/Default-dark.css"}[version]
    code = (f"import gi, sys; gi.require_version('Gtk', '{version}'); from gi.repository import Gtk, Gio; "
            f"sys.stdout.write(Gio.resources_lookup_data('{path}', 0).get_data().decode())")
    return subprocess.run(["python3", "-c", code], capture_output=True, text=True, check=True).stdout


def gtk(p, o):
    """A generated GTK theme; flipping gtk-theme between two slots makes running GTK apps reload it live."""
    defines = "".join(f"@define-color {k} {p[v]};\n" for k, v in {
        "accent_color": "accent", "accent_bg_color": "accent", "accent_fg_color": "bg",
        "window_bg_color": "bg", "view_bg_color": "bg", "headerbar_bg_color": "surface0",
        "card_bg_color": "surface0", "popover_bg_color": "surface0", "theme_bg_color": "bg",
        "theme_base_color": "bg", "theme_fg_color": "fg", "theme_text_color": "fg",
        "theme_selected_bg_color": "accent", "theme_selected_fg_color": "bg",
        "borders": "surface1", "unfocused_borders": "surface1",
    }.items())
    slot = "Themely-b" if gsetting("gtk-theme") == "'Themely-a'" else "Themely-a"
    root = HOME / ".local/share/themes" / slot
    write(root / "index.theme", f"[Desktop Entry]\nType=X-GNOME-Metatheme\nName={slot}\n\n[X-GNOME-Metatheme]\nGtkTheme={slot}\n")
    for d in ("gtk-3.0", "gtk-4.0"):
        write(root / d / "gtk.css", recolor(base_css(d[4:]), p) + "\n" + GENERATED + defines)
        # The old static approach imported colors from ~/.config; that would pin stale colors over the live theme.
        user = CFG / d / "gtk.css"
        if user.exists() and not user.is_symlink() and "@import 'themely.css';\n" in user.read_text():
            rest = user.read_text().replace("@import 'themely.css';\n", "")
            user.unlink() if not rest.strip() else write(user, rest)
        (CFG / d / "themely.css").unlink(missing_ok=True)
    run("gsettings", "set", "org.gnome.desktop.interface", "color-scheme", "prefer-dark")
    run("gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", slot)


def set_keys(path, section, keys):
    """Set `key=value` lines in a QSettings-style ini, keeping every other line (the owning tool rewrites it too)."""
    text = path.read_text() if path.exists() else ""
    header = f"[{section}]\n"
    if header not in text:
        text = (text.rstrip("\n") + "\n\n" if text.strip() else "") + header
    start = text.index(header) + len(header)
    end = text.find("\n[", start)
    end = len(text) if end == -1 else end + 1
    body = text[start:end]  # keys are only unique within a section
    for k, v in keys.items():
        line = f"{k}={v}"
        body, n = re.subn(rf"^{re.escape(k)}=.*$", lambda m: line, body, count=1, flags=re.M)
        if not n:
            body = line + "\n" + body
    write(path, text[:start] + body + text[end:])


def qt(p, o):
    """qt5ct/qt6ct palette; both watch their config dir, so running Qt apps recolor live."""
    c = {k: "#ff" + v[1:] for k, v in p.items()}
    # QPalette role order: WindowText Button Light Midlight Dark Mid Text BrightText ButtonText Base Window
    # Shadow Highlight HighlightedText Link LinkVisited AlternateBase NoRole ToolTipBase ToolTipText PlaceholderText
    active = [c["fg"], c["surface0"], c["overlay"], c["surface1"], c["bg"], c["surface1"], c["fg"], "#ffffffff",
              c["fg"], c["bg"], c["bg"], "#ff000000", c["accent"], c["bg"], c["accent"], c["accent2"],
              c["surface0"], c["bg"], c["surface0"], c["fg"], "#80" + p["fg_muted"][1:]]
    disabled = [c["overlay"] if i in (0, 6, 8, 13) else col for i, col in enumerate(active)]
    body = "[ColorScheme]\n" + "".join(
        f"{name}_colors={', '.join(cols)}\n"
        for name, cols in (("active", active), ("disabled", disabled), ("inactive", active)))
    for tool in ("qt5ct", "qt6ct"):
        colors = CFG / tool / "themely-colors.conf"  # in the watched dir itself, so a change triggers a reload
        write(colors, body)
        set_keys(CFG / tool / f"{tool}.conf", "Appearance",
                 {"color_scheme_path": str(colors), "custom_palette": "true"})
    # KDE apps (Dolphin, ...) paint from kdeglobals' color groups on top of the Qt palette; empty = Breeze Light.
    rgb = {k: ",".join(str(int(v[i:i + 2], 16)) for i in (1, 3, 5)) for k, v in p.items()}
    scheme = "[General]\nName=Themely\n"
    for group, (bg, alt, fg) in {
        "View": ("bg", "surface0", "fg"), "Window": ("bg", "surface0", "fg"),
        "Button": ("surface0", "surface1", "fg"), "Selection": ("accent", "accent2", "bg"),
        "Tooltip": ("surface0", "surface1", "fg"), "Complementary": ("bg", "surface0", "fg"),
        "Header": ("bg", "surface0", "fg"),
    }.items():
        keys = {
            "BackgroundNormal": rgb[bg], "BackgroundAlternate": rgb[alt],
            "ForegroundNormal": rgb[fg], "ForegroundActive": rgb[fg], "ForegroundInactive": rgb["fg_muted"],
            "ForegroundLink": rgb["accent"], "ForegroundVisited": rgb["accent2"],
            "ForegroundNegative": rgb["color1"], "ForegroundNeutral": rgb["color3"], "ForegroundPositive": rgb["color2"],
            "DecorationFocus": rgb["accent"], "DecorationHover": rgb["accent"],
        }
        set_keys(CFG / "kdeglobals", f"Colors:{group}", keys)
        scheme += f"\n[Colors:{group}]\n" + "".join(f"{k}={v}\n" for k, v in keys.items())
    # Selectable as "Themely" in KDE apps' color menus. Not pinned: a pin (UiSettings/ColorScheme) makes KDE apps
    # apply it once at launch, while unpinned they follow kdeglobals live through plasma-integration.
    write(HOME / ".local/share/color-schemes/Themely.colors", scheme)
    kg = CFG / "kdeglobals"
    if "[UiSettings]\nColorScheme=Themely\n" in kg.read_text():  # pin written by an older themely
        write(kg, re.sub(r"\n*\[UiSettings\]\nColorScheme=Themely\n", "\n", kg.read_text()))
    # Tell running KDE apps the palette changed (what plasma-apply-colorscheme does).
    run("dbus-send", "--session", "--type=signal", "/KGlobalSettings", "org.kde.KGlobalSettings.notifyChange",
        "int32:0", "int32:0")


PREF = 'user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);\n'


def browser_profiles():
    for root in (CFG / "zen", HOME / ".mozilla/firefox"):
        ini = configparser.ConfigParser(interpolation=None)
        ini.read(root / "profiles.ini")
        for sec in ini.sections():
            if sec.startswith("Install") and ini[sec].get("Default"):
                yield root / ini[sec]["Default"]


def browsers(p, o):
    """Applies on the next browser start (userChrome.css isn't live)."""
    live = has("pywalfox")  # Pywalfox themes live; stale !important overrides would fight it
    for prof in set(browser_profiles()):
        if not prof.is_dir():
            continue
        write(prof / "chrome/userChrome.css", GENERATED + ("" if live else css(":root", {
            "--toolbar-bgcolor": p["bg"], "--toolbar-color": p["fg"],
            "--lwt-accent-color": p["bg"], "--lwt-text-color": p["fg"],
            "--tab-selected-bgcolor": p["surface0"],
            "--toolbar-field-background-color": p["surface0"], "--toolbar-field-color": p["fg"],
            "--toolbar-field-focus-background-color": p["surface1"],
            "--toolbar-field-focus-border-color": p["accent"], "--focus-outline-color": p["accent"],
            "--arrowpanel-background": p["bg"], "--arrowpanel-color": p["fg"],
            "--zen-primary-color": p["accent"], "--zen-colors-primary": p["surface0"],
            "--zen-colors-secondary": p["surface1"], "--zen-colors-tertiary": p["bg"],
            "--zen-colors-border": p["accent"], "--zen-main-browser-background": p["bg"],
        })))
        userjs = prof / "user.js"
        text = userjs.read_text() if userjs.exists() else ""
        if PREF not in text:
            write(userjs, text + PREF)


def pywalfox(p, o):
    """Live Firefox/Zen theming through the Pywalfox add-on, which reads pywal's colors.json."""
    order = ["bg", "accent", "accent2", "color2", "color3", "color5", "color6", "fg_muted",
             "overlay", "accent", "accent2", "color2", "color3", "color5", "color6", "fg"]
    write(HOME / ".cache/wal/colors.json", json.dumps({
        "wallpaper": str(CURRENT / "wallpaper"),
        "special": {"background": p["bg"], "foreground": p["fg"], "cursor": p["accent"]},
        "colors": {f"color{i}": p[k] for i, k in enumerate(order)},
    }, indent=2) + "\n")
    if has("pywalfox"):
        run("pywalfox", "update")


def btop(p, o):
    if not (CFG / "btop").exists():
        return
    grad = {"cpu": ("accent", "accent2", "color1"), "temp": ("accent", "accent2", "color1"),
            "used": ("accent", "accent2", "color1"), "process": ("accent", "accent2", "color1"),
            "free": ("color2", "accent", "accent2"), "cached": ("accent2", "accent", "fg"),
            "available": ("color2", "accent2", "accent"), "download": ("accent", "accent2", "fg"),
            "upload": ("accent2", "accent", "fg")}
    theme = {"main_bg": "bg", "main_fg": "fg", "title": "fg", "hi_fg": "accent", "selected_bg": "surface1",
             "selected_fg": "accent", "inactive_fg": "overlay", "graph_text": "fg_muted", "meter_bg": "surface1",
             "proc_misc": "accent2", "cpu_box": "overlay", "mem_box": "overlay", "net_box": "overlay",
             "proc_box": "overlay", "div_line": "surface1"}
    for name, (a, b, c) in grad.items():
        theme.update({f"{name}_start": a, f"{name}_mid": b, f"{name}_end": c})
    write(CFG / "btop/themes/themely.theme", "".join(f'theme[{k}]="{p[v]}"\n' for k, v in theme.items()))
    conf = CFG / "btop/btop.conf"
    text = conf.read_text() if conf.exists() else ""
    for k, v in {"color_theme": '"themely"', "theme_background": "False"}.items():  # no bg: kitty's opacity shows
        text, n = re.subn(rf"^{k}\s*=.*$", lambda m: f"{k} = {v}", text, count=1, flags=re.M)
        if not n:
            text += f"{k} = {v}\n"
    write(conf, text)
    run("pkill", "-USR2", "-x", "btop")  # btop reloads its config on SIGUSR2


def prompt(p, o):
    """Shell prompt colors; ~/.bashrc's __prompt sources this before every prompt, so terminals follow live."""
    h, l, s = hls(p["accent"])
    rgb = lambda c: [int(c[i:i + 2], 16) for i in (1, 3, 5)]
    fmt = lambda v: ";".join(map(str, v))
    out = []
    for name, color in {"lav": from_hls(h + 20 / 360, l, s), "blue": p["accent"], "sap": p["accent2"]}.items():
        blend = [round(0.3 * a + 0.7 * b) for a, b in zip(rgb(color), rgb(p["bg"]))]
        out.append(f"{name}='{fmt(rgb(color))}' {name}_bg='{fmt(blend)}'")
    write(HOME / ".cache/themely/prompt.sh", "# Generated by themely\n" + "\n".join(out) + "\n")


def spotify(p, o):
    """Spotify through spicetify (needs a one-time `spicetify backup apply` and a writable Spotify install)."""
    if not has("spicetify"):
        return
    d = HOME / ".config/spicetify/Themes/themely"
    roles = {"text": "fg", "subtext": "fg_muted", "main": "bg", "main-elevated": "surface0", "highlight": "surface1",
             "highlight-elevated": "surface1", "sidebar": "bg", "player": "bg", "card": "surface0",
             "shadow": "bg", "selected-row": "fg_muted", "button": "accent", "button-active": "accent2",
             "button-disabled": "overlay", "tab-active": "surface1", "notification": "surface0",
             "notification-error": "color1", "misc": "overlay"}
    write(d / "color.ini", "[themely]\n" + "".join(f"{k} = {p[v][1:]}\n" for k, v in roles.items()))
    write(d / "user.css", GENERATED)
    run("spicetify", "config", "current_theme", "themely", "color_scheme", "themely")
    run("spicetify", "refresh")
    if running("spotify"):  # Spotify only reads theme colors at start
        # Not `spicetify restart`: it runs the bare binary, skipping ~/.config/spotify-flags.conf that the
        # `spotify` launcher reads, and without those Wayland flags Spotify exits at once on niri.
        run("pkill", "-x", "spotify")
        for _ in range(50):  # a second Spotify hands off to one still shutting down, then exits
            if not running("spotify"):
                break
            time.sleep(0.1)
        launch("spotify")


# The whole command line of a slat daemon, nothing more: SIGUSR1 kills any other process it reaches.
SLAT_DAEMON = r"^(\S*/)?slat __daemon$"
SLAT_KEYS = {"bg": "bg", "fg": "fg", "dim": "fg_muted", "accent": "accent", "border": "surface1",
             "tab_bg": "surface0", "tab_fg": "fg_muted", "tab_active_bg": "accent", "tab_active_fg": "bg"}


def slat(p, o):
    """slat's [theme] colors; its daemon re-reads them on SIGUSR1, so open sessions recolor live."""
    conf = CFG / "slat/config.toml"
    if not conf.parent.exists():
        return
    text = conf.read_text() if conf.exists() else ""
    if ">>> themely colors" not in text:
        if not re.search(r"(?m)^\[theme\][ \t]*$", text):
            text = (text.rstrip("\n") + "\n\n" if text.strip() else "") + "[theme]\n"
        start = re.search(r"(?m)^\[theme\][ \t]*\n", text).end()
        nxt = re.search(r"(?m)^\[", text[start:])
        end = start + nxt.start() if nxt else len(text)
        # TOML forbids duplicate keys, so hand-set colours give way to the managed block.
        body = re.sub(rf"(?m)^[ \t]*({'|'.join(SLAT_KEYS)})[ \t]*=.*\n?", "", text[start:end])
        kept = body.rstrip("\n")
        body = (kept + "\n" if kept else "") + "# >>> themely colors\n# <<< themely\n" + body[len(kept) + 1:]
        write(conf, text[:start] + body + text[end:])
    edit(conf, {"colors": "".join(f'{k} = "{p[v]}"\n' for k, v in SLAT_KEYS.items())})
    run("pkill", "-USR1", "-f", SLAT_DAEMON)


def wallpaper(p, o):
    old = subprocess.run(["pgrep", "-x", "swaybg"], capture_output=True, text=True).stdout.split()
    subprocess.Popen(["swaybg", "-i", str(CURRENT / "wallpaper"), "-m", "fill"], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.3)  # let the new one map before the old one goes (the reveal overlay hides this)
    for pid in old:
        try:
            os.kill(int(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass


TARGETS = [("niri", niri), ("kitty", kitty), ("flowbar", flowbar), ("mako", mako), ("fuzzel", fuzzel),
           ("vscode", vscode), ("vesktop", vesktop), ("gtk", gtk), ("qt", qt), ("browsers", browsers), ("pywalfox", pywalfox), ("btop", btop), ("prompt", prompt), ("slat", slat), ("spotify", spotify),
           ("wallpaper", wallpaper)]


def apply(slug):
    d = theme_dir(slug)
    theme = load(d / "theme.json")
    p, o = palette(theme["accent"]), theme["opacity"]
    tmp = DATA / ".current-tmp"
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(Path("themes") / slug)
    os.replace(tmp, CURRENT)
    failed = []
    for name, fn in TARGETS:
        try:
            fn(p, o)
        except Exception as e:  # one broken app must not stop the rest
            failed.append(name)
            print(f"themely: {name}: {e}", file=sys.stderr)
    return failed


# ---------- CLI ----------

def main(argv=None):
    ap = argparse.ArgumentParser(prog="themely")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("palette").add_argument("accent")
    sub.add_parser("swatches").add_argument("image")
    sub.add_parser("apply").add_argument("slug")
    sub.add_parser("delete").add_argument("slug")
    s = sub.add_parser("save")
    s.add_argument("--name", required=True)
    s.add_argument("--wallpaper")
    s.add_argument("--accent")
    s.add_argument("--opacity", type=float, default=0.85)
    s.add_argument("--slug")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "list":
            print(json.dumps(list_themes()))
        elif a.cmd == "palette":
            print(json.dumps(palette(a.accent)))
        elif a.cmd == "swatches":
            print(json.dumps(swatches(a.image)))
        elif a.cmd == "apply":
            return 1 if apply(a.slug) else 0
        elif a.cmd == "save":
            print(save(a.name, a.wallpaper, a.accent, a.opacity, a.slug))
        elif a.cmd == "delete":
            delete(a.slug)
    except subprocess.CalledProcessError as e:
        print(f"themely: {e.cmd[0]} failed: {(e.stderr or '').strip()}", file=sys.stderr)
        return 1
    except (ValueError, OSError) as e:
        print(f"themely: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
