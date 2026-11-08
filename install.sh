#!/usr/bin/env bash
# Black Glass rice installer (Arch Linux)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="${XDG_CONFIG_HOME:-$HOME/.config}"
BIN="$HOME/.local/bin"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$HOME/config-backup-$STAMP"

PACKAGES=(
  hyprland waybar rofi mako kitty dolphin
  grim slurp wl-clipboard brightnessctl playerctl
  pipewire pipewire-pulse wireplumber pavucontrol
  libnotify ffmpeg
  ttf-jetbrains-mono-nerd ttf-nerd-fonts-symbols inter-font
  sddm qt6-declarative
)

ask() { read -r -p "$1 [y/N] " a; [[ "${a,,}" == y* ]]; }
say() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

[ "$(id -u)" -ne 0 ] || { echo "Run this as your normal user, not root."; exit 1; }

# ---- 1. packages ----
if command -v pacman >/dev/null 2>&1; then
  if ask "Install required packages with pacman?"; then
    say "Installing packages"
    sudo pacman -S --needed "${PACKAGES[@]}"
    sudo pacman -S --needed matugen 2>/dev/null \
      || echo "matugen is not in your repos: install it from the AUR (e.g. 'yay -S matugen-bin')."
  fi
  if ask "Install the optional extras (cava, fastfetch)?"; then
    sudo pacman -S --needed cava fastfetch
  fi
else
  echo "pacman not found: install the packages listed in README.md manually."
fi

# ---- 2. user configs ----
say "Installing configs to $CONF (backups: $BACKUP)"
mkdir -p "$CONF" "$BACKUP"
for d in hypr waybar rofi mako kitty matugen; do
  if [ -e "$CONF/$d" ]; then
    mv "$CONF/$d" "$BACKUP/"
    echo "backed up existing $d"
  fi
  cp -r "$REPO/config/$d" "$CONF/$d"
  echo "installed $d"
done
chmod +x "$CONF/hypr/scripts/"*.sh

# ---- 3. scripts ----
say "Installing scripts to $BIN"
mkdir -p "$BIN"
for f in "$REPO"/bin/*; do
  install -m 755 "$f" "$BIN/"
  echo "installed $(basename "$f")"
done
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "NOTE: $BIN is not on your PATH. Add it to your shell profile:  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

# ---- 4. wallpapers ----
mkdir -p "$CONF/wallpapers"
if [ -d "$REPO/wallpapers" ]; then
  cp -r "$REPO/wallpapers/." "$CONF/wallpapers/"
  echo "copied wallpapers"
fi
rmdir --ignore-fail-on-non-empty "$BACKUP" 2>/dev/null || true

# ---- 5. SDDM theme (root) ----
if ask "Install the SDDM login theme? (uses sudo)"; then
  say "Installing SDDM theme"
  sudo mkdir -p /usr/share/sddm/themes /etc/sddm.conf.d
  sudo rm -rf /usr/share/sddm/themes/black-glass
  sudo cp -r "$REPO/sddm/black-glass" /usr/share/sddm/themes/
  sudo cp "$REPO/sddm/zz-black-glass.conf" /etc/sddm.conf.d/
  if ask "Enable SDDM at boot? (replaces any other display manager)"; then
    sudo systemctl enable sddm
  fi
fi

say "Done"
echo "Add wallpapers to $CONF/wallpapers, run 'retheme' once to generate colors,"
echo "then log out and pick 'Hyprland' at the login screen."
