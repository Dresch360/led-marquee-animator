# Setup notes for the imported applications

These applications currently depend on the working driver/environment arrangement from the personal prototype. This document records those prerequisites; a general installation wizard is not yet available. Do not run an installer against a working player just to view this repository.

## Shared requirements

- A Bluetooth adapter supporting BLE and a compatible powered sign within range.
- Python, Bleak 1.1.1 and Pillow 11.3.0. Python 3.13 was used in the personal setup.
- A separately obtained copy of [coolledx-driver](https://github.com/UpDryTwist/coolledx-driver), pinned to `abf781b671b7a89571711127be0094b308e7f722`.
- In that driver's `src/coolledx/client.py`, the GATT write argument `response=expect_response,` was changed to `response=False,` for the tested characteristic. Retain a backup and check that the expected source is present before modifying it.
- The correct Bluetooth address for your sign. The imported defaults still refer to the original test sign.

Do not substitute the driver's latest branch without testing. The working revision was deliberately pinned. The earlier protocol provenance follow-up is recorded in the root attribution file.

## Windows desktop

The launcher currently looks for this Python environment:

```text
%USERPROFILE%\CoolLED\coolledx-driver-main\.venv\Scripts\pythonw.exe
```

The corresponding console Python must import `tkinter` and `PIL.ImageTk` successfully. The default driver directory is:

```text
%USERPROFILE%\CoolLED\September\coolledx-driver-abf781b671b7a89571711127be0094b308e7f722
```

1. Keep the verified environment and patched driver in place.
2. Open `windows\Start_CoolLED.cmd`.
3. In Setup, check the Bluetooth address, driver folder and Python executable.
4. Add GIFs, choose their order, speed and fit, then use Send selected or Start rotation.

Settings are saved in `%USERPROFILE%\CoolLED\uploader_settings.json`. The PC must stay awake and the app must remain running. X minimizes; Exit stops the application. No Windows startup entry is installed.

Use normal individual rotation. The imported combined-reel feature is experimental and caused unacceptable frame loss in the personal setup.

## Dedicated Raspberry Pi

The tested host was a Pi 3 running 64-bit Raspberry Pi OS / Debian 13 with Python 3.13.5. The installer requires the account `pi`, sudo access, systemd, BlueZ, `bluetoothctl` and `rfkill`.

The existing directory layout is:

```text
/home/pi/CoolLED/.venv
/home/pi/CoolLED/driver
/home/pi/CoolLED/animations
```

The Python environment must already exist and the driver must be at the pinned revision with its write patch. Bluetooth must be unblocked and powered on. Copy any existing GIFs into the animations directory.

After reviewing those prerequisites, from this repository run as `pi`, without prefixing the whole command with sudo:

```bash
bash pi/install.sh
```

The installer installs `pi/requirements.txt` into the existing environment, requests sudo for service setup and installs:

- `coolled-player.service`, running as `pi`
- `coolled-bluetooth.service`, enabling the Bluetooth radio

It preserves existing animations and settings. On the first update it also keeps `Player.before-shuffle` and `pi_player_settings.before-shuffle.json` if those originals exist.

Open `http://<your-pi-ip>:8080` from a browser on the same home network. The hostname printed by the prototype installer is a legacy default; use your actual Pi IP or hostname. Stop rotation before uploading GIFs or editing settings, then start it again.

The installed program is `/home/pi/CoolLED/Player`. Settings are `/home/pi/CoolLED/pi_player_settings.json`. There is no login on the web page; keep it on a trusted LAN.

Useful service commands, run separately on the Pi:

```bash
sudo systemctl status coolled-player.service --no-pager
```

```bash
sudo journalctl -u coolled-player.service -n 60 --no-pager
```

```bash
sudo systemctl restart coolled-player.service
```

To disable background startup and stop the services:

```bash
sudo systemctl disable --now coolled-player.service coolled-bluetooth.service
```

Other Linux accounts, file layouts and distribution configurations need installer adaptation. This source import does not establish compatibility with every Linux system.
