ARCADE LED PLAYER: WINDOWS DESKTOP

Extract or clone the entire repository. Install Python 3.13 with the Python
launcher and Tkinter, plus Git for Windows. Then double-click:
  windows\Install_CoolLED.cmd

Keep setup_player.py, tools, both platform folders and the license files
together. The installer needs the complete source checkout.

Setup creates the environment and pinned driver, then lets you select a
display or supply its Bluetooth address. It installs into:
  %USERPROFILE%\CoolLED
Setup does not upload an animation. Start the installed app using:
  %USERPROFILE%\CoolLED\Start_CoolLED.cmd

Add GIFs, choose speed and fit, set the interval and click Start rotation.
Check Shuffle rotation next to the interval to randomize playback. Every
animation plays once per round, with no immediate repeat between rounds.
The checkbox is saved and cannot change during an upload or active rotation.
Stop rotation before editing it. A failed upload retries the same animation.
The PC must stay awake and the application must remain running.
X minimizes it; Exit quits. No Windows startup entry is installed.

Use normal individual rotation. The imported combined-reel option remains
experimental and caused unacceptable frame loss in the personal setup.

For custom paths or Python 3.11/3.12, invoke setup_player.py directly.
Use --root for the installation directory. The installed launcher detects
its own directory. Existing playlist entries are preserved on updates.

See docs/SETUP.md and docs/VALIDATION.md in the source repository.
The bundled RGB test is the only sample animation in this import.
Game-themed artwork from the personal setup is not included.

The root LICENSE and NOTICE offer original project files under MIT.
Third-party licenses and attribution are retained alongside this file.
