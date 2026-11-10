#!/bin/sh
# Waybar on-click handler.  Fast path: ask the running panel to toggle itself
# over D-Bus (no Python start-up).  Otherwise start the panel; it toggles on
# launch.  setsid keeps it alive across Waybar restarts.
dir=$(dirname "$(readlink -f "$0")")

if command -v gdbus >/dev/null 2>&1 &&
   gdbus call --session --dest dev.local.AudioPanel \
        --object-path /dev/local/AudioPanel \
        --method org.gtk.Actions.Activate toggle '[]' '{}' >/dev/null 2>&1; then
    exit 0
fi

exec setsid -f python3 "$dir/audio-panel.py" toggle >/dev/null 2>&1
