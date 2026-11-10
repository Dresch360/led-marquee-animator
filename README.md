# Arcade LED Player

Play animated GIFs on a compatible Bluetooth LED marquee using a Windows PC or a dedicated Raspberry Pi. Build a playlist, set an interval and let the host upload each animation in turn.

**Status: private release preparation.** This first source import preserves the working personal applications. Installation still assumes an existing driver setup and some defaults match the original 96 × 16 panel. It is not a general-purpose installer or a finished public release.

## Choose a player

| | Windows desktop | Raspberry Pi / Linux |
| --- | --- | --- |
| Interface | Tkinter desktop window | Browser page hosted on the Pi |
| Playback host | Windows PC must stay awake with the app running | Pi runs independently of the browser and PC |
| Playlists | Ordered rotation | Ordered rotation or shuffle |
| GIF controls | Preview, speed and fit per file | Preview, selection, order, speed and fit per file |
| Startup | Manual launch | systemd service; resumes if rotation was left running |
| Display unavailable | Retries the same pending animation | Retries the same pending animation |
| Source | [windows/](windows/) | [pi/](pi/) |

The Linux web player uses `fcntl` and systemd. It is not the Windows application. Its installer currently requires the username `pi` and `/home/pi/CoolLED`; other Linux setups need adaptation.

## How rotation works

The host uploads one complete animation. The panel repeats it while the host waits for the selected interval, then the host uploads the next file. The interval begins after an upload completes. The host remains responsible for the playlist.

On connection failures, the host keeps the same file pending and waits 30 seconds after the failed attempt before trying again. File and setup errors stop rotation. Only one uploader should control the sign at a time.

The Pi player offers shuffle: every selected animation once per round, with no immediate repeat at the boundary when multiple files are selected. Closing its browser page does not stop rotation. Stop saves the stopped state; leaving rotation running allows it to resume when the service restarts.

In the Windows player, X minimizes the window and leaves rotation running. Exit quits the program. Windows rotation does not automatically start when the app opens.

## Compatibility and animation limits

The personal setup has played animations on a GOTUS CoolLED1248-app-compatible sign advertising as `CoolLEDX`, using a 96 × 16 pixel canvas. Compatibility with other sizes, controllers or firmware is unverified. This is not a HUB75 panel driver.

GIFs are converted to eight primary RGB colors and scaled, padded or stretched to the canvas. Lower speed values play faster. Short, low-resolution GIFs work best.

48-frame clips have played correctly on the tested sign. The applications accept up to 113 frames based on the encoder's payload size; that is not a verified controller capacity. A 64-frame diagnostic did not play correctly. Check the physical display after uploading.

The on-sign 0–100% transfer can take around 30 seconds in the tested setup. This project does not eliminate that delay. A sender's success message alone does not prove correct panel playback.

The Pi uses individual uploads only. The imported Windows source still contains an experimental combined-reel option that reduces frames to fit a 48-frame budget. It produced unacceptable missing frames in the personal setup and is not the recommended playback path.

## Setup

See [the setup notes](docs/SETUP.md). These describe the existing setup prerequisites and current assumptions. A new-user installation flow is still being prepared.

Both applications use [UpDryTwist/coolledx-driver](https://github.com/UpDryTwist/coolledx-driver) at revision `abf781b671b7a89571711127be0094b308e7f722`, with its GATT write set to `response=False` for the tested characteristic. Driver source and Python runtimes are not bundled here.

The Pi web page is intended for a trusted home network. It listens on port 8080 without a login. Do not expose it to the internet or forward its port.

## Tests

On Linux, in an environment with the Pi requirements installed:

```bash
python3 -m unittest discover -s pi/tests -v
```

See [validation notes](docs/VALIDATION.md) for the distinction between automated checks and physical testing.

## Attribution, licensing and artwork

See [ATTRIBUTION.md](ATTRIBUTION.md) for credits to Greg Tatham / UpDryTwist, CrimsonClyde's earlier protocol work and the runtime libraries. Original third-party notices are retained under [LICENSES/](LICENSES/), with sources and checksums in [LICENSE_SOURCES.json](LICENSE_SOURCES.json).

The original player code, project documentation and RGB test animation are **open source under the [MIT License](LICENSE)**. See [NOTICE](NOTICE) for the project copyright notice. Commercial use, modification and redistribution are permitted, provided the copyright and license notices are retained as required by the license.

Third-party components retain their original licenses. This project license does not replace those terms or resolve the earlier-source provenance question recorded in ATTRIBUTION.md. Windows binary notice collection also remains a release preparation item.

This import includes an RGB test GIF. Game-themed animations from the personal setup are not included. Software credits do not grant rights to game artwork or imply manufacturer endorsement.

The player is independent of RetroPie and does not automatically change animations when a game is selected.

## Before a public release

- Resolve the recorded upstream provenance question before bundling or redistributing derived driver code.
- Replace personal hardware defaults with setup controls and provide clean-install instructions for both platforms.
- Remove the unsuccessful Windows combined-reel option from the release interface.
- Test fresh installations, Pi reboot and display power recovery on physical hardware.
- Collect exact runtime notices if distributing executables or bundled environments.
- Add a short demo video and screenshots after the release interface is settled.
