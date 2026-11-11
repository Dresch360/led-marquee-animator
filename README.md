# Arcade LED Player

Play animated GIFs on a compatible Bluetooth LED marquee using a Windows PC or a dedicated Raspberry Pi. Build a playlist, set an interval and let the host upload each animation in turn.

**Status: private release preparation.** Source installers for Windows and Linux now create the environment, obtain the pinned driver and save the user's display address. Automated setup checks pass, but fresh installations and Bluetooth playback still need verification on real hardware. The current canvas is fixed at 96 × 16 pixels.

## Demo

<img src="https://github.com/user-attachments/assets/df71d001-9867-4811-a056-06e58253ff35" alt="Personal arcade cabinet with a Bluetooth LED marquee" width="420" />

*Personal arcade cabinet. Photo retouched for lighting and background cleanup.*

<img src="https://github.com/user-attachments/assets/9f44ad49-5874-428b-ac14-c2ec6cda230f" alt="LED marquee displaying 86 percent upload progress" width="720" />

*Marquee close-up showing the 86% upload progress indicator (retouched photo).*

https://github.com/user-attachments/assets/b000e28f-3a47-4652-9829-17c2b482e518

A short clip cropped to focus on the LED marquee in the personal arcade cabinet.

## Why I built this

I'm a novice programmer who just wanted to upload my own animations to an LED matrix. That turned out to be harder than expected. I spent several months working through the app's restrictions and Bluetooth communication issues. This player grew out of that effort to make custom animations easier to upload, organize and rotate.

For my own setup, I built a full-size retro arcade cabinet from spare wood, a display and a Raspberry Pi that were lying around my shop. A static, backlit marquee felt too boring. I wanted one that moved.

If you're not a retro arcade purist or you just want more control over a compatible LED matrix, this may be for you.

## Choose a player

| | Windows desktop | Raspberry Pi / Linux |
| --- | --- | --- |
| Interface | Tkinter desktop window | Browser page hosted on the Pi |
| Playback host | Windows PC must stay awake with the app running | Pi runs independently of the browser and PC |
| Playlists | Ordered rotation or shuffle | Ordered rotation or shuffle |
| GIF controls | Preview, speed and fit per file | Preview, selection, order, speed and fit per file |
| Startup | Manual launch | systemd service; resumes if rotation was left running |
| Display unavailable | Retries the same pending animation | Retries the same pending animation |
| Source | [windows/](windows/) | [pi/](pi/) |

The Linux web player uses `fcntl` and systemd. It is not the Windows application. Setup uses the account that runs it and installs into that user's `CoolLED` folder by default; a different directory can be selected with `--root`.

## How rotation works

The host uploads one complete animation. The panel repeats it while the host waits for the selected interval, then the host uploads the next file. The interval begins after an upload completes. The host remains responsible for the playlist.

On connection failures, the host keeps the same file pending and waits 30 seconds after the failed attempt before trying again. File and setup errors stop rotation. Only one uploader should control the sign at a time.

Both players offer shuffle: every animation in the rotation plays once per round, with no immediate repeat at the boundary when multiple files are selected. Stop rotation before changing the saved Shuffle rotation checkbox. The displayed playlist order is preserved.

Closing the Pi browser page does not stop rotation. Stop saves the stopped state; leaving rotation running allows it to resume when the service restarts.

In the Windows player, X minimizes the window and leaves rotation running. Exit quits the program. Windows rotation does not automatically start when the app opens.

## Compatibility and animation limits

The personal setup has played animations on a GOTUS CoolLED1248-app-compatible sign advertising as `CoolLEDX`, using a 96 × 16 pixel canvas. Compatibility with other sizes, controllers or firmware is unverified. This is not a HUB75 panel driver.

GIFs are converted to eight primary RGB colors and scaled, padded or stretched to the canvas. Lower speed values play faster. Short, low-resolution GIFs work best.

48-frame clips have played correctly on the tested sign. The applications accept up to 113 frames based on the encoder's payload size; that is not a verified controller capacity. A 64-frame diagnostic did not play correctly. Check the physical display after uploading.

The on-sign 0–100% transfer can take around 30 seconds in the tested setup. This project does not eliminate that delay. A sender's success message alone does not prove correct panel playback.

Both players use individual uploads and playlist rotation. Experimental combined-reel code is retained internally in the Windows source but is not exposed in the interface because it produced unacceptable missing frames in the personal setup.

## Setup

See [the setup instructions](docs/SETUP.md). Windows users can run `windows/Install_CoolLED.cmd` from the full source checkout. On Linux, run `python3 setup_player.py` as your normal account. The installer lets you select a display or provide its address and includes the RGB test animation. It does not upload an animation during setup.

Both applications use [UpDryTwist/coolledx-driver](https://github.com/UpDryTwist/coolledx-driver) at revision `abf781b671b7a89571711127be0094b308e7f722`, with its GATT write set to `response=False` for the tested characteristic. Setup obtains that driver separately. Driver source and Python runtimes are not bundled in this repository.

The Pi web page is intended for a trusted home network. It listens on port 8080 without a login. Do not expose it to the internet or forward its port.

## Tests

On Linux, in an environment with the Pi requirements installed:

```bash
python3 -m unittest discover -s pi/tests -v
```

Installer checks run with `python3 -m unittest discover -s tests -v`. Windows configuration checks run with `python -m unittest discover -s windows/tests -v` in an environment with Tkinter and Pillow. See [validation notes](docs/VALIDATION.md) for the distinction between automated checks and physical testing.

## Attribution, licensing and artwork

See [ATTRIBUTION.md](ATTRIBUTION.md) for credits to Greg Tatham / UpDryTwist, CrimsonClyde's earlier protocol work and the runtime libraries. Original third-party notices are retained under [LICENSES/](LICENSES/), with sources and checksums in [LICENSE_SOURCES.json](LICENSE_SOURCES.json).

The original player code, project documentation and RGB test animation are **open source under the [MIT License](LICENSE)**. See [NOTICE](NOTICE) for the project copyright notice. Commercial use, modification and redistribution are permitted, provided the copyright and license notices are retained as required by the license.

Third-party components retain their original licenses. This project license does not replace those terms or resolve the earlier-source provenance question recorded in ATTRIBUTION.md. Windows binary notice collection also remains a release preparation item.

This import includes an RGB test GIF. Game-themed animations from the personal setup are not included. Software credits do not grant rights to game artwork or imply manufacturer endorsement.

The player is independent of RetroPie and does not automatically change animations when a game is selected.

## Before a public release

- Resolve the recorded upstream provenance question before bundling or redistributing derived driver code.
- Test fresh installations, Pi reboot and display power recovery on physical hardware.
- Collect exact runtime notices if distributing executables or bundled environments.
- Add screenshots after the release interface is settled.
