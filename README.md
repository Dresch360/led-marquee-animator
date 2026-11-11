# LED Marquee Animator

**Your marquee. Your animations.**

Upload your own animated GIFs to a compatible Bluetooth LED marquee. Organize playlists, adjust playback and rotate or shuffle your animations.

Run the player on Windows or let a dedicated Raspberry Pi handle playback independently **without keeping a PC running**.

**Experimental source release.** Tested on a 96 × 16 CoolLEDX-compatible sign using Windows and a Raspberry Pi 3.

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
| Controls | Desktop application | Web page on your home network |
| Playback host | Windows PC stays awake with the app running | Pi runs in the background |
| Playlists | Ordered rotation or shuffle | Ordered rotation or shuffle |
| GIF settings | Preview, speed and fit per animation | Preview, speed and fit per animation |
| Startup | Open the app manually | Starts at boot without logging in |
| Source | [windows/](windows/) | [pi/](pi/) |

## Install

Follow the [setup instructions](docs/SETUP.md).

- **Windows:** download the full repository and run `windows/Install_CoolLED.cmd`.
- **Pi / Linux:** run `python3 setup_player.py` as your normal account.

Setup installs the player, downloads the Bluetooth driver and lets you choose your display. It includes a generic RGB test animation.

## Use

1. Add GIFs to the playlist.
2. Choose each animation's speed and fit.
3. Set the rotation interval and optionally enable **Shuffle rotation**.
4. Click **Start rotation** to run the playlist. Windows also offers **Send selected** for a single animation.

The panel repeats the current animation until the host sends the next one. The rotation interval starts after each upload finishes. Keep only one player connected to the sign at a time.

Shuffle plays each animation once per round and avoids immediate repeats between rounds. Stop rotation before changing the playlist or shuffle setting. Connection failures retry the same pending animation.

**Windows:** X minimizes the window and keeps rotation running. **Exit** quits. The PC must stay awake.

**Pi:** closing the browser does not stop playback. If rotation is left running, it resumes after reboot without a console or desktop login. **Stop** saves the stopped state.

## Compatibility

The tested sign is a GOTUS CoolLED1248-app-compatible model advertising as `CoolLEDX`, with a **96 × 16** canvas. Other sizes, controllers and firmware are unverified. This is not a HUB75 panel driver.

GIFs are converted to eight primary RGB colors and can be scaled, padded or stretched. Lower speed values play faster. Short animations work best: 48-frame clips played correctly on the tested sign, while a 64-frame diagnostic did not. The application's higher frame limit is not a guarantee of panel support.

An upload can take around 30 seconds on the tested setup. The host must stay running to rotate the playlist.

The Pi controls listen on port 8080 without a login and are intended for a trusted home network. Do not expose that port to the internet.

See [validation](docs/VALIDATION.md) for tested behavior and remaining coverage.

## Development tests

```bash
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s pi/tests -v
python3 -m unittest discover -s windows/tests -v
```

Install the relevant requirements first. Windows tests need Tkinter and Pillow; the GUI test also needs a graphical display.

## Credits and license

Built on [UpDryTwist/coolledx-driver](https://github.com/UpDryTwist/coolledx-driver), which credits CrimsonClyde's earlier protocol work. See [ATTRIBUTION.md](ATTRIBUTION.md) for credits and third-party notices.

Original player code, documentation and the RGB test animation are released under the [MIT License](LICENSE). Third-party components retain their own licenses.

Game-themed animation files from the personal setup are not bundled. The photos and video show a personal arcade cabinet; no game publisher or hardware manufacturer endorses this project.

The player works independently of RetroPie and does not automatically change animations when a game is selected.
