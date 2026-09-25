# themely

A wallpaper-driven theme switcher for the [niri](https://github.com/YaLTeR/niri) Wayland compositor.

Press **Mod+Shift+T**, pick a wallpaper card, and the whole desktop recolors behind a circular reveal
that grows out of the card you clicked. The accent color comes from the wallpaper automatically.
The same opacity applies to every window. Terminals, editors, GTK and KDE apps, Discord, Firefox/Zen,
Spotify, btop and your shell prompt all follow the new theme, most of them live, without restarting.

A small dashboard creates, edits and deletes themes.

---

## Contents

- [How it works](#how-it-works)
- [What gets themed](#what-gets-themed)
- [Requirements](#requirements)
- [Install](#install)
- [One-time app setup](#one-time-app-setup)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)
- [Uninstall and backups](#uninstall-and-backups)
- [Development](#development)

---

## How it works

```
Mod+Shift+T ─► Quickshell switcher ─► pick a card
                                         │
             freeze the screen (screencopy) on every output
                                         │
             themely apply <theme>  ──►  rewrite each app's colors + reload it
                                         │
             grow a circular hole from the card: the new desktop shows through
```

There are two parts:

| Part | What it does |
|---|---|
| `themely.py` | The engine and CLI (Python stdlib + ImageMagick). It owns all theme data and every config write. |
| `shell/` | A [Quickshell](https://quickshell.outfoxxed.me) config: the switcher overlay, the reveal animation and the dashboard. It calls `themely` for everything. |

**A theme** is a folder `~/.config/themely/themes/<id>/` with a `wallpaper` image and a `theme.json`:

```json
{ "name": "Nebula", "accent": "#50c87c", "opacity": 0.85 }
```

`~/.config/themely/current` is a symlink to the active theme. It is also what swaybg shows at login.

**Colors.** When you add a theme, the engine picks the accent from the wallpaper. It shrinks the image to
8 colors with ImageMagick and chooses the most vivid one that isn't tiny, grey, black or white. Every
other color is derived from that one accent: background, surfaces, text, a second accent, and the 16
terminal colors. Red, green and yellow keep their usual meaning. You can override the accent in the
dashboard.

**Safe edits.** In hand-written configs, themely only rewrites the lines between two marker comments:

```
# >>> themely colors
...generated, replaced on every switch...
# <<< themely
```

Everything outside the markers is yours. Every write:
- is skipped when nothing changed;
- is atomic, and follows symlinks, so a dotfiles repo stays intact;
- keeps a one-time `<file>.themely-bak` of the file as it was before themely first changed it.

---

## What gets themed

| App | How | When |
|---|---|---|
| **Wallpaper** | swaybg restarted under the reveal overlay | live |
| **Window opacity** | one niri rule for every window (kitty uses its own background opacity so text stays crisp) | live |
| **niri borders** | `layout { border }` colors | live |
| **kitty** | colors + `background_opacity`, reloaded with `SIGUSR1` | live |
| **Shell prompt** (bash powerline) | `~/.cache/themely/prompt.sh`, sourced before each prompt | next prompt |
| **flowbar** | `[theme]` accent/background/opacity (flowbar watches its config) | live |
| **mako** | notification colors + `makoctl reload` | live |
| **fuzzel** | `[colors]` | next launch |
| **VS Code, Antigravity, VSCodium, Cursor** | `workbench.colorCustomizations` in `settings.json` | live |
| **Vesktop** | `~/.config/vesktop/themes/themely.css` (Vencord hot-reloads it) | live |
| **GTK 3 / GTK 4** | recolored copy of GTK's own theme, switched through `gsettings` | live |
| **Brave / Chromium** | follows the GTK theme (Settings → Appearance → Theme → **GTK**) | live |
| **KDE / Qt 6** (Dolphin, Okular, Gwenview, Ark …) | `kdeglobals` color groups via `plasma-integration` | live |
| **Qt 5** (VLC) | qt5ct color scheme | next launch |
| **Firefox / Zen** | [Pywalfox](https://github.com/Frewacom/pywalfox) (`~/.cache/wal/colors.json` + `pywalfox update`) | live |
| **btop** | `themes/themely.theme`, reloaded with `SIGUSR2` | live |
| **Spotify** | [spicetify](https://spicetify.app) color scheme | Spotify restarts |
| **System dark mode** | `gsettings color-scheme prefer-dark` | live |

**Can't be themed:**
- the official Discord client (use Vesktop);
- apps with only built-in themes (e.g. Bruno);
- the colors of web pages themselves.

A target whose app isn't installed is skipped. A target that fails, for example because its markers
were deleted, doesn't stop the others. `themely apply` names it and exits non-zero, and the switcher
shows a notification.

---

## Requirements

**Required**

- niri
- [Quickshell](https://quickshell.outfoxxed.me) ≥ 0.3
- Python ≥ 3.10 with PyGObject (`python-gobject`). PyGObject is used to read GTK's built-in theme.
- ImageMagick 7 (`magick`)
- swaybg

**Optional**, each one only needed for its app:

- `plasma-integration`: live recoloring of KDE/Qt 6 apps
- `pywalfox` + the Pywalfox browser add-on: Firefox/Zen
- `spicetify-cli`: Spotify
- btop, kitty, mako, fuzzel, flowbar, Vesktop, VS Code …

On Arch:

```sh
sudo pacman -S quickshell python-gobject imagemagick swaybg
sudo pacman -S plasma-integration            # optional: live KDE/Qt apps
uv tool install pywalfox                     # optional: Firefox/Zen
yay -S spicetify-cli                         # optional: Spotify
```

---

## Install

```sh
git clone https://github.com/noturbob/themely ~/projects/themely
cd ~/projects/themely

# the CLI
chmod +x themely.py
ln -s "$PWD/themely.py" ~/.local/bin/themely

# the Quickshell UI
mkdir -p ~/.config/quickshell
ln -s "$PWD/shell" ~/.config/quickshell/themely

# theme storage (optionally inside your dotfiles, e.g. ln -s ~/dotfiles/themely ~/.config/themely)
mkdir -p ~/.config/themely/themes
```

### niri

Add these to `~/.config/niri/config.kdl`. Replace `/home/you` with your home directory; niri doesn't
expand `~`.

```kdl
environment {
    QT_QPA_PLATFORMTHEME "kde"   // live KDE/Qt colors (needs plasma-integration)
}

spawn-at-startup "swaybg" "-i" "/home/you/.config/themely/current/wallpaper" "-m" "fill"
spawn-at-startup "qs" "-c" "themely"

// the dashboard floats
window-rule {
    match title="^themely$"
    open-floating true
}

binds {
    Mod+Shift+T hotkey-overlay-title="Switch theme" { spawn "qs" "-c" "themely" "ipc" "call" "switcher" "toggle"; }
}
```

Then add the two marker blocks themely fills in.

The border block goes **inside** `layout { }`. Remove your own `border { }` block:

```kdl
layout {
    // >>> themely border
    // <<< themely
}
```

The opacity block goes at the top level. Remove your own per-app `opacity` window rules:

```kdl
// >>> themely opacity
// <<< themely
```

### Markers for the other configs

Put the markers where the generated lines should go, and delete your own copies of those lines:

| File | Marker lines | Replaces these lines of yours |
|---|---|---|
| `~/.config/kitty/kitty.conf` | `# >>> themely colors` / `# <<< themely` | `background`, `foreground`, `selection_*`, `cursor*`, `color0`–`color15`, `background_opacity`, `dynamic_background_opacity` |
| `~/.config/flowbar/config.ini` (in `[theme]`) | `# >>> themely colors` / `# <<< themely` | `accent`, `accent-2`, `background`, `foreground`, `opacity` |
| `~/.config/mako/config` | `# >>> themely colors` / `# <<< themely` | `background-color`, `text-color`, `border-color` |
| `~/.config/fuzzel/fuzzel.ini` (under `[colors]`) | `# >>> themely colors` / `# <<< themely` | the whole `[colors]` body |

VS Code and its forks need nothing: themely adds its markers to `settings.json` on the first run.

### Your first theme

```sh
themely save --name "My Theme" --wallpaper ~/Pictures/wall.jpg   # accent picked automatically
themely apply my-theme
```

Log out and back in once, so apps start with the new `QT_QPA_PLATFORMTHEME` and swaybg reads the
`current` wallpaper.

---

## One-time app setup

These steps are one click or one command each. Skip the ones for apps you don't use.

**Shell prompt (bash).** Inside your prompt function, after your default colors, source the generated
file. It defines `lav lav_bg blue blue_bg sap sap_bg` as `R;G;B` strings for 24-bit escape codes:

```bash
__prompt() {
  local lav='180;190;254' lav_bg='90;94;129' blue='137;180;250' blue_bg='64;78;111' sap='116;199;236' sap_bg='52;74;95'
  [ -r ~/.cache/themely/prompt.sh ] && . ~/.cache/themely/prompt.sh   # themely colors
  ...
}
```

**Vesktop.** Open Settings (gear, bottom left) → **Vencord** → **Themes** → **Local Themes**, and turn
on **themely**. Alternatively, quit Vesktop, add `"themely.css"` to `enabledThemes` in
`~/.config/vesktop/settings/settings.json`, and start it again.

**Firefox / Zen (Pywalfox).**

```sh
pywalfox install                                                      # Firefox
pywalfox install --manifest-path ~/.config/zen/native-messaging-hosts \
                 --profile-path ~/.config/zen                         # Zen
```

Then install the [Pywalfox add-on](https://addons.mozilla.org/firefox/addon/pywalfox/) in each
browser and click **Fetch Pywal colors** once. Any other browser theme (e.g. Catppuccin) is replaced.

**Spotify (spicetify).** Spotify must be writable, and needs one backup:

```sh
sudo chmod -R a+wr /opt/spotify
spicetify backup apply
```

On niri without Xwayland, Spotify also needs Wayland flags, or it exits silently at launch:

```sh
printf -- '--enable-features=UseOzonePlatform\n--ozone-platform=wayland\n' > ~/.config/spotify-flags.conf
```

**Qt 5 apps (VLC).** `plasma-integration` is Qt 6 only, so keep qt5ct for VLC with a launcher override:

```sh
sed 's/^Exec=/Exec=env QT_QPA_PLATFORMTHEME=qt5ct /' /usr/share/applications/vlc.desktop \
  > ~/.local/share/applications/vlc.desktop
```

**Brave / Chromium.** Open Settings → Appearance → Theme and choose **GTK**.

---

## Usage

### Switcher

| Key / action | Does |
|---|---|
| **Mod+Shift+T** | open or close the switcher on the focused monitor |
| ← / → | move between themes |
| **Enter** or click | switch, with the reveal animation |
| **Esc** or click outside | close |
| **+** card | open the dashboard |

### Dashboard

Open it from the **+** card, or run `qs -c themely ipc call dashboard toggle`.

**Left side:** your themes. Click one to edit it, or use **+ New theme**.

**Right side:**
- Name.
- Wallpaper: click the preview to choose an image.
- Accent:
  - picked from the wallpaper when you choose one;
  - click another swatch, or type a hex, to override.
- Opacity for every window.
- A live palette preview. The dashboard itself recolors as you edit.

**Buttons:**
- **Save** applies right away if you're editing the active theme.
- **Delete** asks you to confirm. The active theme can't be deleted.

### CLI

```sh
themely list                         # themes as JSON (which one is current)
themely apply <id>                   # switch without the animation
themely save --name N --wallpaper IMG [--accent '#rrggbb'] [--opacity 0.85] [--slug ID]
                                     # create (no --slug) or edit (--slug); no --accent = from the wallpaper
themely delete <id>
themely swatches IMG                 # colors the wallpaper offers, the automatic pick first
themely palette '#rrggbb'            # the full derived palette
```

For an animated switch from scripts or keybinds:

```sh
qs -c themely ipc call theme apply <id>
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Notification "Some apps didn't switch" | It names each failing target. Usually its markers were edited away: put them back. |
| Switcher doesn't open | Is Quickshell running? `pgrep -a qs`, or start it with `qs -c themely`. Check `themely` is on `$PATH` for niri. |
| KDE apps don't change live | `plasma-integration` must be installed and `QT_QPA_PLATFORMTHEME=kde` set (log out and in). Apps started from an old terminal keep the old variable. |
| KDE folder icons keep the old color | Icons are cached; they update when redrawn or on the app's next start. |
| Firefox/Zen keep the old colors | Pywalfox add-on installed in *that* browser, and **Fetch Pywal colors** clicked once? |
| Spotify won't start | Missing `~/.config/spotify-flags.conf` Wayland flags (see above). |
| Prompt didn't change in an open terminal | `source ~/.bashrc` once; new terminals are fine. |
| A theme is missing from the list | Its `theme.json` is invalid; `themely list` prints why on stderr. |

---

## Uninstall and backups

Before its first change to a file, themely saves `<file>.themely-bak` next to it. To undo themely:

1. Restore each `*.themely-bak` (or remove the marker blocks) and delete the niri lines above.
2. `rm ~/.local/bin/themely ~/.config/quickshell/themely`
3. Theme data lives in `~/.config/themely`. Keep it or delete it.
4. Generated files you can delete:
   - `~/.local/share/themes/Themely-*`
   - `~/.local/share/color-schemes/Themely.colors`
   - `~/.config/vesktop/themes/themely.css`
   - `~/.config/btop/themes/themely.theme`
   - `~/.config/spicetify/Themes/themely`
   - `~/.cache/themely`
5. Set GTK back: `gsettings set org.gnome.desktop.interface gtk-theme Adwaita`.

---

## Development

```sh
python3 test_themely.py
```

The tests are plain asserts. They run against a temporary `$HOME` (via `THEMELY_HOME`) and never
touch the real desktop.

- **Adding an app:** write a `fn(palette, opacity)` in `themely.py`, add it to `TARGETS`, and add a
  test.
- **Palette keys:** `accent accent2 bg surface0 surface1 overlay fg fg_muted color0…color15`.

Design notes live in `docs/superpowers/`.
