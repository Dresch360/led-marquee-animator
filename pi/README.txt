ARCADE LED PLAYER: PI / LINUX WEB PLAYER

From the full source checkout, run as your normal account:
  python3 setup_player.py
or:
  bash pi/install.sh

Requires Python 3.11-3.13, git, python3-venv, BlueZ, rfkill and systemd
for background startup. Do not run the whole installer with sudo.
It requests sudo when installing services. The account need not be named pi.

Setup creates a virtual environment, obtains and patches the pinned driver,
lets you select a display and installs into ~/CoolLED by default.
Use --root for another directory and --no-service for foreground-only use.
Setup itself does not upload an animation.

Open http://<your-linux-host-ip>:8080 on your trusted home LAN.
No login is provided. Do not expose the port to the internet.

Stop rotation to add GIFs or change settings. Start rotation to save and run.
Close the browser when desired; the background service keeps running.
Stop saves the stopped state. Leaving rotation running allows it to resume
on service restart. Each file is uploaded individually.

Settings, animations, hardware.json, driver and .venv are under the chosen
installation directory. The installed code is in its Player subdirectory.
Service: coolled-player.service

See docs/SETUP.md and docs/VALIDATION.md in the source repository for
installation, update backups and recorded validation coverage.
The root LICENSE and NOTICE offer original project files under MIT.
Third-party licenses and attribution are retained alongside this file.
