ARCADE LED PLAYER: PI / LINUX WEB PLAYER

Source import of the dedicated Pi player. See ../README.md and
../docs/SETUP.md in the repository for setup assumptions and limitations.

The current installer requires user pi, /home/pi/CoolLED/.venv and the pinned,
patched driver in /home/pi/CoolLED/driver. It is not a general Linux installer.
Do not run it to update an existing working installation without reviewing it.

From the repository, run as pi:
  bash pi/install.sh

The control page is http://<your-pi-ip>:8080 on your trusted home LAN.
No login is provided. Do not expose the port to the internet.

Stop rotation to add GIFs or change settings. Start rotation to save and run.
Close the browser when desired; the Pi keeps running. Stop saves the stopped
state. Leaving rotation running allows it to resume on service restart.
Each file is uploaded individually. There is no combined reel.

Settings: /home/pi/CoolLED/pi_player_settings.json
Animations: /home/pi/CoolLED/animations
Installed program: /home/pi/CoolLED/Player
Service: coolled-player.service

Attribution and original third-party notices are in ATTRIBUTION.md and
LICENSES/ at the repository root. The original player code is offered under
the PolyForm Noncommercial License 1.0.0. See the root LICENSE and NOTICE.
