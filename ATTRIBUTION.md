# Attribution and third-party credits

This project adds player interfaces and scheduling around an existing CoolLEDX
Bluetooth driver. It does not claim authorship of the original protocol or its
reverse engineering. These notices accompany this source import; they do not certify a completed
public-release license review.

## Upstream driver

**Greg Tatham / UpDryTwist**, author of
[coolledx-driver](https://github.com/UpDryTwist/coolledx-driver).

The tested revision is `abf781b671b7a89571711127be0094b308e7f722`.
Its original notice is **Copyright (c) 2025 Greg Tatham**, under the MIT License.
The complete, unedited license is retained at
`LICENSES/coolledx-driver/abf781b671b7a89571711127be0094b308e7f722/LICENSE`.
The local compatibility change sets GATT writes to `response=False` for the
tested characteristic. 
## Earlier protocol work

The driver's README credits **CrimsonClyde** and
[LED FaceShields](https://git.team23.org/CrimsonClyde/led-faceshields) for earlier
reverse engineering and implementation work. We retain that acknowledgment,
attributed to the upstream README. This repository does not directly bundle
files from LED FaceShields.

**Provenance follow-up:** at inspected revision
`afb98c514147123b7232d60f02b3ac4aa38acd75`, no explicit license file or permission
statement was found in its README or Python sources checked. This does not
establish whether the driver author received separate permission. Clarify that
history before bundling or redistributing derived driver code publicly.
Attribution alone does not resolve this question.

## Player additions

Project-specific work includes the Windows desktop interface, Pi browser
interface, GIF preparation, playlists, per-file speed and fit controls, rotation,
shuffle, saved settings, startup integration and reconnection scheduling.
These features are built around the driver and libraries credited here.
A license for the new player code has not been selected by these notices.

## Runtime libraries

The following versions match the Pi installation recorded during setup.
Complete retained notices are under `LICENSES/`. `LICENSE_SOURCES.json` records
their sources and checksums. Refresh the inventory for every public build,
because most transitive dependencies are not pinned by the application.

| Component | Version | Role | License / attribution |
| --- | --- | --- | --- |
| [Bleak](https://github.com/hbldh/bleak) | 1.1.1 | Bluetooth on Windows and Linux | MIT; Henrik Blidh and contributors |
| [Pillow](https://python-pillow.github.io/) | 11.3.0 | Images and GIFs | MIT-CMU terms plus bundled-library notices; complete Linux aarch64 wheel notice retained |
| [Flask](https://flask.palletsprojects.com/) | 3.1.2 | Pi web application | BSD-3-Clause; Pallets and contributors |
| [Waitress](https://docs.pylonsproject.org/projects/waitress/) | 3.0.2 | Pi web server | ZPL-2.1 and embedded source notices, including Sam Rushing's notice |
| [dbus-fast](https://github.com/Bluetooth-Devices/dbus-fast) | 5.2.0 | Linux Bluetooth D-Bus | MIT; Bluetooth Devices Authors |
| [Blinker](https://blinker.readthedocs.io/) | 1.9.0 | Flask signals | MIT; Jason Kirtland and contributors |
| [Click](https://click.palletsprojects.com/) | 8.5.1 | Flask CLI dependency | BSD-3-Clause; Pallets and contributors |
| [ItsDangerous](https://itsdangerous.palletsprojects.com/) | 2.2.0 | Flask signing dependency | BSD-3-Clause; Pallets and contributors |
| [Jinja2](https://jinja.palletsprojects.com/) | 3.1.6 | Templates | BSD-3-Clause; Pallets and contributors |
| [MarkupSafe](https://markupsafe.palletsprojects.com/) | 3.0.4 | Template escaping | BSD-3-Clause; Pallets and contributors |
| [Werkzeug](https://werkzeug.palletsprojects.com/) | 3.1.9 | Flask HTTP utilities | BSD-3-Clause; Pallets and contributors; icon notice also retained |

Python and, for the desktop player, Tkinter/Tk provide the runtime and GUI
framework. This source repository does not bundle a Python or Tk runtime.

### Windows binary-build follow-up

The desktop player uses Bleak and Pillow. Bleak additionally installs the
Windows-specific `winrt-runtime` and `winrt-Windows.*` Bluetooth, Enumeration,
Foundation and Streams packages. These dependency distributions are not bundled
in this source repository. Before shipping a Windows executable, installer or
bundled environment, collect its exact dependencies and retain their own notices,
including Windows Pillow binary notices and any bundled Python/Tk notices.
The Pi inventory above is not a complete Windows binary license audit.

## Artwork and compatibility names

These software licenses and credits do not grant rights to game characters,
logos or other third-party artwork. Game-themed GIFs made for the personal
setup are not cleared for a public animation pack by this document. Use original
generic demos or appropriately licensed assets for public distribution, and
review recognizable artwork separately.

CoolLEDX, CoolLED1248, Raspberry Pi, RetroPie and game names identify
compatibility or subject matter. No endorsement or affiliation is claimed.
The player operates independently of RetroPie; it does not automatically change
animations in response to game selection.
