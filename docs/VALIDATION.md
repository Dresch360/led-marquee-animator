# Validation

## Personal setup

The player has been tested with a GOTUS CoolLED1248-app-compatible sign advertising as `CoolLEDX`, using a 96 × 16 canvas.

Confirmed behavior:

- Individual GIF uploads and playback from Windows.
- Text and GIF uploads and playback from a Raspberry Pi 3.
- Pi web controls and shuffle.
- Pi playback after reboot without logging in.

The Windows source installer also completed in a separate test folder and opened the application with the RGB test GIF. Bluetooth playback from that separate installation has not been confirmed.

## Automated tests

| Suite | Coverage |
| --- | --- |
| Installer | Address selection, driver setup, updates, backups and service configuration |
| Pi player | GIF conversion, playlists, shuffle, retries, settings and upload handling |
| Windows player | Configuration, playlists, shuffle, retries and saved settings |

The latest Windows UI cleanup passed all 11 nonvisual tests. Its GUI smoke test was skipped because no graphical display was available. Automated tests simulate Bluetooth behavior and do not replace checking the physical sign.

## Known limits

- Only the personal 96 × 16 CoolLEDX setup has been physically tested.
- 48-frame clips played correctly; a 64-frame diagnostic did not. Higher frame counts accepted by the application are not verified panel capacity.
- Full playback from fresh installations, physical shuffle round boundaries, closed-browser playback, display power recovery and reboot with rotation saved as stopped have not all been verified.

See the [setup guide](SETUP.md) for installation and service commands.
