#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/pi/CoolLED
SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$ROOT/.venv/bin/python"
if [[ "$(id -un)" != pi ]]; then
  echo 'Run this installer as pi, without sudo. It requests sudo for the service setup.' >&2
  exit 1
fi
"$PYTHON" -c "from pathlib import Path; import re; p=Path('/home/pi/CoolLED/driver/src/coolledx/client.py'); assert re.search(r'response\s*=\s*False', p.read_text()), 'Driver Bluetooth write patch is missing'"
ACTUAL="$(git -C "$ROOT/driver" rev-parse HEAD)"
if [[ "$ACTUAL" != abf781b671b7a89571711127be0094b308e7f722 ]]; then
  echo 'The driver is not at the verified revision. Stop here and check the driver.' >&2
  exit 1
fi
"$PYTHON" -m pip install -r "$SOURCE/requirements.txt"
sudo -v
if systemctl is-active --quiet coolled-player.service; then
  sudo systemctl stop coolled-player.service
fi
if [[ -d "$ROOT/Player" && ! -e "$ROOT/Player.before-shuffle" ]]; then
  cp -a "$ROOT/Player" "$ROOT/Player.before-shuffle"
fi
if [[ -f "$ROOT/pi_player_settings.json" && ! -e "$ROOT/pi_player_settings.before-shuffle.json" ]]; then
  cp -p "$ROOT/pi_player_settings.json" "$ROOT/pi_player_settings.before-shuffle.json"
fi
mkdir -p "$ROOT/Player" "$ROOT/animations"
cp "$SOURCE/player.py" "$SOURCE/requirements.txt" "$SOURCE/README.txt" "$ROOT/Player/"
cp -R "$SOURCE/templates" "$SOURCE/static" "$ROOT/Player/"
"$PYTHON" -m py_compile "$ROOT/Player/player.py"
RFKILL="$(PATH=/usr/sbin:/usr/bin:/sbin:/bin command -v rfkill)"
BLUETOOTHCTL="$(command -v bluetoothctl)"
if getent group bluetooth >/dev/null; then
  sudo usermod -a -G bluetooth pi
fi
sudo systemctl enable --now bluetooth.service
sudo tee /etc/systemd/system/coolled-bluetooth.service >/dev/null <<UNIT
[Unit]
Description=Enable Bluetooth for the CoolLED player
Wants=bluetooth.service
After=bluetooth.service
StartLimitIntervalSec=0

[Service]
Type=oneshot
ExecStart=$RFKILL unblock bluetooth
ExecStart=$BLUETOOTHCTL power on
RemainAfterExit=yes
Restart=on-failure
RestartSec=5
TimeoutStartSec=30

[Install]
WantedBy=multi-user.target
UNIT
sudo tee /etc/systemd/system/coolled-player.service >/dev/null <<'UNIT'
[Unit]
Description=CoolLED animation player and local controls
Wants=coolled-bluetooth.service
After=coolled-bluetooth.service
StartLimitIntervalSec=0

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/CoolLED/Player
Environment=COOLLED_ROOT=/home/pi/CoolLED
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/pi/CoolLED/.venv/bin/python /home/pi/CoolLED/Player/player.py
Restart=on-failure
RestartSec=5
TimeoutStopSec=10
KillMode=control-group
Nice=10
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
RestrictSUIDSGID=yes
StandardOutput=journal
StandardError=journal
LogRateLimitIntervalSec=30
LogRateLimitBurst=100

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable coolled-bluetooth.service coolled-player.service
sudo systemctl restart coolled-bluetooth.service
sudo systemctl restart coolled-player.service
sleep 1
if ! systemctl is-active --quiet coolled-player.service; then
  sudo journalctl -u coolled-player.service -n 30 --no-pager
  exit 1
fi
echo 'Player service started. Check its page in your browser:'
echo 'http://LEDMatrix.local:8080'
echo 'Rotation is initially stopped. Choose your interval and click Start rotation.'
