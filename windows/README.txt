ARCADE LED PLAYER: WINDOWS DESKTOP

Source import of the Windows desktop player. See ../README.md and
../docs/SETUP.md for setup assumptions and limitations.

Start_CoolLED.cmd requires the existing Python environment in:
  %USERPROFILE%\CoolLED\coolledx-driver-main\.venv
It also requires the pinned September driver with the Bluetooth write patch.
Check your Bluetooth address, Python path and driver path in Setup.

Double-click Start_CoolLED.cmd. Add GIFs, set per-file speed and fit, choose
the rotation interval and click Start rotation. The PC must stay awake and
the application must remain running. X minimizes it; Exit quits.
No Windows startup entry is installed.

Use normal individual rotation. The imported combined-reel option is
experimental and caused unacceptable frame loss in the personal setup.

Settings: %USERPROFILE%\CoolLED\uploader_settings.json

The bundled RGB test is the only sample animation in this import.
Game-themed artwork from the personal setup is not included.

Attribution and original third-party notices are in ATTRIBUTION.md and
LICENSES/ at the repository root. A player-code license is still to be chosen.
