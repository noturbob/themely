# themely — design

Date: 2026-09-25

## Goal

One keybind opens a horizontal strip of theme previews. Clicking one re-themes the whole
desktop (wallpaper, accent, opacity) with a magic-ui style circular reveal growing from the
clicked card. A small dashboard creates, edits and deletes themes.

## What a theme is

`~/.config/themely/themes/<slug>/theme.json` + `wallpaper.<ext>` (copied in on save).

```json
{ "name": "Mocha Blue", "accent": "#89b4fa", "opacity": 0.85 }
```

`~/.config/themely` is a symlink to `/conf/themely`, so themes live in the dotfiles repo.
`~/.config/themely/current` is a symlink to the active theme dir; it is what survives reboots.

**Default is automatic:** on save without `--accent`, the engine pulls the accent from the
wallpaper. The user can later override it in the dashboard (click another extracted swatch or
type a hex) if the automatic pick looks off. Everything else is derived from the accent.
Dark themes only.

### Automatic accent pick

`magick <wallpaper> -resize 64x64 -colors 8 -format %c histogram:info:-` gives 8 colors with
pixel counts. Score each: drop near-grays (HLS sat < 0.2) and near-black/white (light < 0.2 or
> 0.9); score = sat × pixel share × (1 − |light − 0.65|). Highest wins; if everything was
dropped, fall back to the most common color with its lightness lifted to 0.65 and sat to
≥ 0.4. The chosen accent is then normalized to light ∈ [0.55, 0.80] so it reads on the dark bg.

## Palette derivation (from accent hue h)

| Role | Rule |
|---|---|
| `bg` | hue h, sat min(s_accent, 0.25), light 0.13 |
| `surface0` / `surface1` / `overlay` | same hue/sat, light 0.19 / 0.25 / 0.40 |
| `fg` / `fg_muted` | hue h, sat 0.45, light 0.88 / 0.70 |
| `accent` | as given |
| `accent2` | accent with hue −25° |
| ANSI | fixed Catppuccin pastels for red/green/yellow/magenta/cyan; blue = accent; 0/8 = surface1/overlay; 7/15 = fg_muted/fg |

## Components

### 1. Engine — `themely.py` (Python, stdlib only)

```
themely list                 # JSON array of themes + which is current (for the UI)
themely palette '#89b4fa'    # JSON palette (dashboard preview)
themely swatches <image>     # JSON: 8 extracted colors, best (auto) pick first
themely apply <slug>         # write every target, reload apps, swap wallpaper, repoint `current`
themely save --name N --wallpaper PATH [--accent HEX] [--opacity F] [--slug S]
                             # create/update; no --accent = auto from wallpaper, opacity default 0.85
themely delete <slug>        # refuses the current theme
```

Every config edit goes through one function: replace the text between
`themely:begin` / `themely:end` marker comments (comment syntax per file). Markers are inserted
once during setup. Before the first write to any file, a one-time `<file>.themely-bak` is kept.
Each target is independent: a failing target is reported on stderr, the rest still apply,
exit code is non-zero if any failed.

### 2. Targets

| App | Block written | Reload |
|---|---|---|
| niri `config.kdl` | `border {}` colors; opacity window-rules (firefox, zen, vesktop, spotify, code, dolphin) | niri auto-reloads |
| kitty `kitty.conf` | colors, `background_opacity` | `pkill -USR1 kitty` |
| flowbar `config.ini` | `[theme]` accent, accent-2, opacity | auto (file monitor) |
| mako `config` | bg (with alpha), text, border | `makoctl reload` |
| fuzzel `fuzzel.ini` | `[colors]` | read on each launch |
| VS Code `settings.json` | `workbench.colorCustomizations` (bg/surfaces/accent keys) | live |
| Vesktop `themes/themely.css` | whole file: Discord CSS vars | live (enable once in Vencord → Themes) |
| GTK 3/4 `gtk.css` | `@define-color` accent/bg overrides | new windows only |
| Zen + Firefox profiles `chrome/userChrome.css` | whole file: toolbar/bg/accent vars; `user.js` pref enabling it | on browser restart |
| Wallpaper | start new `swaybg -i current/wallpaper`, then kill the old one | hidden by the reveal |

Out of v1: live browser theming (needs a companion extension), Spotify (needs spicetify
installed), Dolphin/Qt (KDE color schemes need restarts outside Plasma).

### 3. Shell — Quickshell config `shell/` (symlinked to `~/.config/quickshell/themely`)

Runs as a daemon (`spawn-at-startup "qs" "-c" "themely"`), exposes
`qs -c themely ipc call switcher toggle` bound to **Mod+Shift+T** in niri.

- **Switcher** — layer-shell overlay, centered horizontal strip of cards (rounded wallpaper
  thumbnail, name, accent dot, ring on the current theme). ←/→ + Enter, mouse click, Esc/click
  outside closes. Gear button opens the dashboard.
- **Reveal** (the animation), per screen:
  1. freeze: a ScreencopyView frame of each output fills a fullscreen overlay;
  2. run `themely apply`, wait for it + ~250 ms for apps to repaint;
  3. grow an inverted circular mask (MultiEffect) from the clicked point — on other screens from
     the nearest edge point — over ~700 ms OutCubic, revealing the live new desktop;
  4. destroy the overlay. If apply fails, still reveal, then notify via `notify-send`.
- **Dashboard** — normal floating window. Left: theme list (click = edit). Right: form with name,
  wallpaper file picker, opacity slider. Picking a wallpaper runs `themely swatches` and
  pre-selects the auto accent; the override row (other swatches + hex field) is there for when
  the auto pick looks wrong. Live palette preview from `themely palette`. Save / Delete (with
  confirm). Calls the engine for all writes.

## Files

```
themely.py
test_themely.py
shell/shell.qml  shell/Switcher.qml  shell/Reveal.qml  shell/Dashboard.qml
```

## Setup (done once during implementation)

Symlinks (`~/.config/themely`, `~/.config/quickshell/themely`, `~/.local/bin/themely`), marker
insertion in each config, niri keybind + startup lines, swaybg startup line pointed at
`/home/agony/.config/themely/current/wallpaper`, a seed theme "Mocha Blue" from
`/conf/wallpapers/wallpaper.jpg` with `#89b4fa` / 0.85 so nothing changes visually on day one.

## Testing

`test_themely.py` (plain asserts): auto accent pick on a generated test image (vivid color beats
a larger gray area; all-gray image hits the fallback), palette derivation stays in range, marker replacement
(present, missing, idempotent), save/delete round-trip in a temp dir, apply against a temp
home with fixture configs. The UI is verified by running it.
