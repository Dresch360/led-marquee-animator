# Install from source

These instructions install the Windows desktop player or Pi/Linux web player from source. See [validation notes](VALIDATION.md) for tested hardware and installation coverage.

## Requirements

- A compatible Bluetooth BLE sign, a BLE adapter and a Windows or Linux host.
- Python 3.11, 3.12 or 3.13 with venv and pip. The Windows double-click installer uses Python 3.13 specifically.
- Git available on PATH.
- Internet access during setup to download the pinned driver and Python dependencies.
- A 96 × 16 sign for the current fixed canvas. Other controllers and sizes are not verified.

The installer asks you to select your display from a scan, enter its Bluetooth address or reuse a saved address. It does not upload an animation. A successful installation still needs a physical playback check.

## Windows

Install Python 3.13 with its launcher and Tcl/Tk components using the [official Python instructions](https://docs.python.org/3.13/using/windows.html). Install [Git for Windows](https://gitforwindows.org/) if Git is not already available. Open a new terminal after installing Git.

Download and extract the entire repository, then double-click:

```text
windows\Install_CoolLED.cmd
```

Keep the top-level `setup_player.py`, `tools`, `pi`, `windows` and license files together. Copying only the Windows folder is not sufficient.

Alternatively, in PowerShell, clone the repository into your user folder:

```powershell
git clone https://github.com/Dresch360/led-marquee-animator.git "$env:USERPROFILE\led-marquee-animator"
```

Then run:

```powershell
py -3.13 "$env:USERPROFILE\led-marquee-animator\setup_player.py"
```

The default installation directory is `%USERPROFILE%\CoolLED`. When setup finishes, open:

```text
%USERPROFILE%\CoolLED\Start_CoolLED.cmd
```

Add GIFs, set their order, speed and fit, then use Send selected or Start rotation. The PC must stay awake and the application must remain running. X minimizes it; Exit quits. No Windows startup entry is installed.

Check **Shuffle rotation** next to the rotation interval for a random order. It plays every animation once per round and avoids an immediate repeat at round boundaries. The setting is saved without rearranging the visible playlist. Stop rotation before changing it; the checkbox is disabled while uploading or rotating. Connection failures retry the same pending animation.

For a custom installation directory, pass `--root` with an absolute path. The installed launcher uses its own installation folder.

Python 3.11 or 3.12 users can invoke `setup_player.py` explicitly with their installed Python version instead of the double-click installer.

## Raspberry Pi / Linux

Use your normal account. It does not have to be named `pi`. Do not run the entire installer with sudo.

On Raspberry Pi OS or Debian, run each command separately:

```bash
sudo apt update
```

```bash
sudo apt install -y git python3-venv bluez rfkill
```

```bash
git clone https://github.com/Dresch360/led-marquee-animator.git "$HOME/led-marquee-animator"
```

```bash
python3 "$HOME/led-marquee-animator/setup_player.py"
```

The default installation directory is `$HOME/CoolLED`. After downloading dependencies, setup scans for your display unless you provided `--address` or have a saved address. It then requests sudo to install these systemd services:

- `coolled-player.service`, running as your normal account
- `coolled-bluetooth.service`, enabling the Bluetooth radio

Open `http://<your-linux-host-ip>:8080` from a browser on the same trusted home network. Use your actual host IP. The page has no login; do not expose or forward its port to the internet.

Stop rotation before adding GIFs or changing settings, then start it again. Closing the browser or shutting down the browsing PC does not stop the Pi. The system service starts at boot without a console or desktop login. Leaving rotation running allows it to resume after a service restart; Stop saves the stopped state.

To choose a different installation directory, use `--root "/absolute/path/to/CoolLED"`. To install without systemd startup:

```bash
python3 "$HOME/led-marquee-animator/setup_player.py" --no-service
```

Setup prints a correctly quoted foreground launch command for that directory. In foreground mode, the process must stay running. There is only one systemd player instance per host; installing with services into a different directory repoints that instance to the new directory.

The tested personal host was a Pi 3 with 64-bit Raspberry Pi OS / Debian 13 and Python 3.13.5. Other Linux distributions may need different package names and Bluetooth permissions.

## Files and updates

Within your chosen installation directory:

| Path | Purpose |
| --- | --- |
| `.venv/` | Python environment |
| `driver/` | Pinned Bluetooth driver |
| `Player/` | Installed application and license notices |
| `animations/` | GIF files; includes the RGB test demo |
| `hardware.json` | Selected Bluetooth address |
| `uploader_settings.json` | Windows playlist and settings |
| `pi_player_settings.json` | Pi playlist, shuffle and running/stopped state |

Rerun the installer from an updated source checkout to update that installation. Close the Windows uploader first. The Linux service is stopped before the application files are replaced and restarted after service setup succeeds.

Existing animations are not overwritten. Pi playlist settings are preserved byte for byte. Windows playlist entries, speeds, fit and interval are retained while the configured driver, Python path and Bluetooth address are updated.

The previous application is kept in a timestamped `Player.before-*` directory. Hardware and Windows settings files are also backed up before replacement. Dependencies and service settings are updated separately from these application backups. If setup fails, check its reported error before retrying.

The installer uses driver revision `abf781b671b7a89571711127be0094b308e7f722`. It applies only the known `response=False` Bluetooth write patch and accepts Windows Git line-ending conversion. A different revision or other changes to the driver's client file cause setup to stop without overwriting that file. Existing extra edits elsewhere in the driver are left in place.

## Service controls

Run each command separately:

```bash
sudo systemctl status coolled-player.service --no-pager
```

```bash
sudo journalctl -u coolled-player.service -n 60 --no-pager
```

```bash
sudo systemctl restart coolled-player.service
```

To stop background playback and disable startup:

```bash
sudo systemctl disable --now coolled-player.service coolled-bluetooth.service
```

## Tests

Use a development environment with the Pi requirements installed for Linux tests:

```bash
python3 -m unittest discover -s tests -v
```

```bash
python3 -m unittest discover -s pi/tests -v
```

The Windows configuration tests require Tkinter and Pillow but do not open a window:

```text
python -m unittest discover -s windows/tests -v
```

See [validation notes](VALIDATION.md) for what has and has not been tested physically.
