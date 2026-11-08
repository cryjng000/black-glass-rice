# Black Glass: Hyprland Rice

A dark, monochrome, glassy desktop: **Hyprland** (Lua config) with a blurred **Waybar**, **Rofi**, **Mako** and **Kitty**, wallpaper-driven accent colors via **matugen**, and a matching **SDDM** login screen.

> **Made on Arch Linux.** The install steps use `pacman`. Other distros should work, but package names will differ.

![Desktop](screenshots/desktop.png)
![App launcher](screenshots/launcher.png)

## What's included

| Part | What it does | Location |
|------|--------------|----------|
| Hyprland | Window manager: 1px white border, rounded corners, blur, custom binds | `config/hypr` |
| Waybar | Floating glass top bar: workspaces, window title, clock, audio, network, CPU, RAM, tray | `config/waybar` |
| Rofi | Glass app launcher panel on the right edge | `config/rofi` |
| Mako | Glass notifications, top right | `config/mako` |
| Kitty | Transparent black-and-white terminal with a cursor trail | `config/kitty` |
| matugen | Generates Rofi, Mako and Kitty colors from your wallpaper | `config/matugen` |
| `retheme` | One command: pick a wallpaper, regenerate colors, repaint | `bin/retheme` |
| Wallpaper picker | Rofi grid of wallpaper previews (`SUPER + W`) | `config/hypr/scripts/wppicker.sh` |
| SDDM | `black-glass` login theme (Qt6) | `sddm/` |

## Quick install

```bash
git clone https://github.com/cryjng000/black-glass-rice.git
cd black-glass-rice
./install.sh
```

The script asks before each step: install packages, install the SDDM theme (needs `sudo`), enable SDDM. Your existing configs are backed up to `~/config-backup-<date>` first.

Then add a wallpaper (see below) and run `retheme` once. Log out and pick **Hyprland** at the login screen. If you'd rather do it by hand, follow the steps below.

## Manual install

### 1. Install dependencies

```bash
sudo pacman -S --needed hyprland waybar rofi mako kitty dolphin \
  grim slurp wl-clipboard brightnessctl playerctl \
  pipewire pipewire-pulse wireplumber pavucontrol libnotify ffmpeg \
  ttf-jetbrains-mono-nerd ttf-nerd-fonts-symbols inter-font \
  sddm qt6-declarative matugen
```

- If `matugen` isn't in your repos, install it from the AUR (for example `yay -S matugen-bin`).
- Your Hyprland version must support the **Lua config** (`hyprland.lua`).
- Fonts: **JetBrainsMono Nerd Font** (bar, launcher, notifications, terminal), **Symbols Nerd Font** (icons) and **Inter** (login screen).
- `ffmpeg` is for video wallpapers. `pavucontrol` opens when you click the volume module.
- Optional extras for the full look in the screenshots: `cava` (audio visualizer) and `fastfetch` (system info).

### 2. Copy the configs and scripts

```bash
mkdir -p ~/.config ~/.local/bin ~/config-backup
for d in hypr waybar rofi mako kitty matugen; do
  [ -e ~/.config/$d ] && mv ~/.config/$d ~/config-backup/
done

cp -r config/hypr config/waybar config/rofi config/mako config/kitty config/matugen ~/.config/
chmod +x ~/.config/hypr/scripts/wppicker.sh
install -m 755 bin/* ~/.local/bin/
mkdir -p ~/.config/wallpapers
```

Make sure `~/.local/bin` is on your `PATH`. Waybar and Mako start automatically with Hyprland (see the `hyprland.start` block in `hyprland.lua`).

### 3. Add a wallpaper and generate colors

```bash
cp /path/to/your-wallpaper.jpg ~/.config/wallpapers/
retheme ~/.config/wallpapers/your-wallpaper.jpg
```

### 4. Install the SDDM theme (needs root)

```bash
sudo mkdir -p /usr/share/sddm/themes /etc/sddm.conf.d
sudo cp -r sddm/black-glass /usr/share/sddm/themes/
sudo cp sddm/zz-black-glass.conf /etc/sddm.conf.d/
sudo systemctl enable sddm
```

Preview it without logging out:

```bash
sddm-greeter-qt6 --test-mode --theme /usr/share/sddm/themes/black-glass
```

**Change the login wallpaper:** edit `background=` in `/usr/share/sddm/themes/black-glass/theme.conf`. Any image works. Other options there: `fontFamily`, `enableBlur`, `backgroundBlur`, `clock24h`.

### 5. Start it

Log out (or reboot), choose **Hyprland** in SDDM, and log in.

## Wallpapers and colors

No wallpapers are shipped, so add your own to `~/.config/wallpapers/` (`jpg`, `png`, and `mp4`/`webm`/`mkv` videos). Then:

```bash
retheme                       # random wallpaper from the folder
retheme path/to/file          # a specific image or video
PREFER=darkness retheme file  # change how matugen picks the accent color
MODE=light retheme file       # light palette
```

Or press `SUPER + W` for a grid picker (`Ctrl + O` opens the folder).

`retheme` runs matugen on the wallpaper, which regenerates `rofi/colors.rasi`, `mako/config` and `kitty/matugen-colors.conf` from the templates in `config/matugen/templates/`. Edit the templates, not the generated files.

**The terminal stays black and white on purpose.** `kitty.conf` ends with `include mono.conf`, which overrides the wallpaper colors with a greyscale palette (`theme.conf`). Delete that line if you want Kitty to follow your wallpaper too.

## Keybinds

`SUPER` is the main modifier. The keyboard layout is Turkish (`tr`); change `kb_layout` in `hyprland.lua` for yours.

| Keys | Action |
|------|--------|
| `SUPER + Q` | Terminal (Kitty) |
| `SUPER + C` | Close window |
| `SUPER + M` | Exit Hyprland |
| `SUPER + E` | File manager (Dolphin) |
| `SUPER + R` | App launcher (Rofi) |
| `SUPER + W` | Wallpaper picker |
| `SUPER + V` | Toggle floating |
| `SUPER + P` | Pseudo-tile |
| `SUPER + J` | Toggle split direction |
| `SUPER + Arrow keys` | Move focus |
| `SUPER + 1-0` | Go to workspace 1-10 |
| `SUPER + SHIFT + 1-0` | Move window to workspace |
| `SUPER + S` | Toggle scratchpad |
| `SUPER + SHIFT + S` | Send window to scratchpad |
| `SUPER + Scroll` | Cycle workspaces |
| `SUPER + Left/Right mouse drag` | Move / resize window |
| `SHIFT + Print` | Screenshot a region to the clipboard |
| 3-finger swipe | Switch workspace |

Volume, brightness and media keys work through `wpctl`, `brightnessctl` and `playerctl`.

Reload things without logging out:

```bash
hyprctl reload          # Hyprland config
pkill waybar; waybar &  # Waybar
makoctl reload          # Mako
```

## Troubleshooting

- **No bar or notifications:** check that `waybar` and `mako` are installed and that the `hyprland.start` block in `hyprland.lua` is present.
- **No blur on the bar, launcher, notifications or terminal:** blur comes from Hyprland. The `layer_rule` entries at the bottom of `hyprland.lua` must match the namespaces (`waybar`, `rofi`, `notifications`).
- **Missing icons or squares in the bar:** install `ttf-jetbrains-mono-nerd` and `ttf-nerd-fonts-symbols`, then restart Waybar.
- **`retheme: command not found`:** add `~/.local/bin` to your `PATH`.
- **`retheme` fails with `matugen: command not found`:** install matugen (see above).
- **SDDM shows the default theme:** confirm `/etc/sddm.conf.d/zz-black-glass.conf` exists and the theme folder is in `/usr/share/sddm/themes/`.
- **SDDM looks flat or slow:** set `enableBlur=false` in the theme's `theme.conf` (for software rendering).

## Credits

Built with [Hyprland](https://hypr.land), [Waybar](https://github.com/Alexays/Waybar), [Rofi](https://github.com/davatorium/rofi), [Mako](https://github.com/emersion/mako), [Kitty](https://sw.kovidgoyal.net/kitty/), [SDDM](https://github.com/sddm/sddm) and [matugen](https://github.com/InioX/matugen).
