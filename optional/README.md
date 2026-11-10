# Black-Glass-Rice optional features

ill upload stuff here theyre optional no i wont put any effort to organizing them, 
to use this media controller make sure you have cairo `sudo pacman -S --needed python-cairo`

if you have my waybar config just edit `~/.config/waybar/config.jsonc` and find the "pulseaudio" block it should look something like

"on-click": "pavucontrol", you replace it with "on-click": "~/path/to/audio-panel/toggle.sh",

deps too sudo pacman -S --needed python-gobject gtk3 gtk-layer-shell libpulse

make it executable:
chmod +x ~/path/to/audio-panel/toggle.sh ~/path/to/audio-panel/audio-panel.py

to keep it clean i just put the files in ~/.config/waybar/audio-panel like this:

[mxrdxr@mxrdxr waybar]$ ls
 audio-panel   config.jsonc   style.css
[mxrdxr@mxrdxr waybar]$ ls audio-panel
 __pycache__       colors.css             toggle.sh
 audio-panel.css   icons.py               widgets.py
 audio-panel.py    matugen-template.css
 audio.py          mpris.py
  ✓ 4.1s  (=^.^=)
[mxrdxr@mxrdxr waybar]$ 
