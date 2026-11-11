"""Install a source checkout without depending on an earlier personal setup.

Run with Python 3.11-3.13 as your normal account. Network access is used only
to obtain the pinned driver and Python dependencies, not for normal playback.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import venv

SOURCE = Path(__file__).resolve().parent
REVISION = 'abf781b671b7a89571711127be0094b308e7f722'
DRIVER_URL = 'https://github.com/UpDryTwist/coolledx-driver.git'
CLIENT_PATH = 'src/coolledx/client.py'


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def find_tool(name):
    found = shutil.which(name)
    if found or sys.platform == 'win32':
        return found
    # Debian's normal-user PATH may omit sbin even when rfkill is installed.
    for folder in ('/usr/sbin', '/sbin'):
        candidate = Path(folder) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def address(value):
    value = value.strip().upper()
    if not re.fullmatch(r'(?:[0-9A-F]{2}:){5}[0-9A-F]{2}', value):
        raise ValueError('Use a Bluetooth address such as AA:BB:CC:DD:EE:FF.')
    return value


def read_object(path):
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError(f'{path} must contain a JSON object. No settings were overwritten.')
    return data


def write_object(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8') as output:
        json.dump(data, output, indent=2)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
    temp.replace(path)


def back_up_file(path):
    if path.is_file():
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        shutil.copy2(path, path.with_name(path.name + f'.before-{stamp}'))


def python_path(root, windows=False):
    return root / '.venv' / ('Scripts/python.exe' if windows else 'bin/python')


def prepare_driver(root):
    repo = root / 'driver'
    if not repo.exists():
        # Clone into a temporary directory so an interrupted clone is not mistaken
        # for a complete installation on the next attempt.
        with tempfile.TemporaryDirectory(prefix='.driver-', dir=root) as temp:
            checkout = Path(temp) / 'checkout'
            run(['git', 'clone', '--no-checkout', DRIVER_URL, checkout])
            run(['git', '-C', checkout, 'checkout', '--detach', REVISION])
            checkout.rename(repo)
    actual = run(['git', '-C', repo, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    if actual != REVISION:
        raise ValueError(f'{repo} is at a different revision. Its files were not replaced.')
    original = run(['git', '-C', repo, 'show', f'{REVISION}:{CLIENT_PATH}'], capture_output=True).stdout
    token = b'response=expect_response,'
    if original.count(token) != 1:
        raise ValueError('Pinned driver source did not contain the expected Bluetooth write. No patch applied.')
    original = original.replace(b'\r\n', b'\n')
    patched = original.replace(token, b'response=False,')
    path = repo / CLIENT_PATH
    current = path.read_bytes()
    normalized = current.replace(b'\r\n', b'\n')
    if normalized == patched:
        return
    if normalized != original:
        raise ValueError(f'{path} has other edits. No changes were made to that file.')
    backup = path.with_suffix('.py.bak')
    if not backup.exists():
        backup.write_bytes(current)
    temporary = path.with_suffix('.py.tmp')
    temporary.write_bytes(current.replace(token, b'response=False,'))
    temporary.replace(path)


def choose_address(python, root, supplied=None):
    if supplied:
        return address(supplied)
    for name in ('hardware.json', 'uploader_settings.json'):
        saved = read_object(root / name)
        if saved.get('address'):
            return address(saved['address'])
    if not sys.stdin.isatty():
        raise ValueError('Noninteractive setup needs --address AA:BB:CC:DD:EE:FF.')
    print('Power on the display and disconnect other uploaders. Scanning for 15 seconds...')
    result = subprocess.run([str(python), str(SOURCE / 'tools/scan_displays.py')],
                            capture_output=True, text=True, timeout=30)
    devices = []
    if result.returncode == 0:
        devices = json.loads(result.stdout)
        for number, device in enumerate(devices, 1):
            print(f"  {number}. {device['name']}  {device['address']}")
    else:
        print(result.stderr.strip() or 'Scan failed. Check that Bluetooth is enabled.')
    if not devices:
        print('No named CoolLED display found. You can enter its Bluetooth address manually.')
    value = input('Display number or Bluetooth address (blank cancels): ').strip()
    if value.isdecimal() and 1 <= int(value) <= len(devices):
        return address(devices[int(value) - 1]['address'])
    return address(value)


def stage_player(root, windows):
    """Stage complete code before replacing an installed app; retain a backup."""
    destination = root / 'Player'
    with tempfile.TemporaryDirectory(prefix='.player-', dir=root) as temp:
        staged = Path(temp) / 'Player'
        source = SOURCE / ('windows' if windows else 'pi')
        staged.mkdir()
        names = ['CoolLED_Uploader.py', 'README.txt'] if windows else [
            'player.py', 'README.txt', 'requirements.txt', 'templates', 'static']
        for name in names:
            item = source / name
            if item.is_dir():
                shutil.copytree(item, staged / name)
            else:
                shutil.copy2(item, staged / name)
        for name in ('LICENSE', 'NOTICE', 'ATTRIBUTION.md', 'LICENSE_SOURCES.json'):
            shutil.copy2(SOURCE / name, staged / name)
        shutil.copytree(SOURCE / 'LICENSES', staged / 'LICENSES')
        for path in staged.glob('*.py'):
            compile(path.read_text(encoding='utf-8'), str(path), 'exec')
        backup = None
        if destination.exists():
            stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup = root / f'Player.before-{stamp}'
            destination.rename(backup)
        try:
            staged.rename(destination)
        except OSError:
            if backup is not None:
                backup.rename(destination)
            raise
    if backup is not None:
        print(f'Previous application retained at: {backup}')


def seed_files(root, windows, selected_address):
    animations = root / 'animations'
    animations.mkdir(exist_ok=True)
    sample = SOURCE / 'windows/animations/CoolLED_RGB_Test.gif'
    if not (animations / sample.name).exists():
        shutil.copy2(sample, animations / sample.name)
    selected_address = address(selected_address)
    back_up_file(root / 'hardware.json')
    write_object(root / 'hardware.json', {'address': selected_address})
    if windows:
        path = root / 'uploader_settings.json'
        saved = read_object(path)
        saved.update(address=selected_address, driver=str(root / 'driver'),
                     python=str(python_path(root, windows=True)))
        saved.setdefault('minutes', 5.0)
        saved.setdefault('items', [{'path': str(animations / sample.name),
                                    'timing': 128, 'fit': 'Fill panel'}])
        back_up_file(path)
        write_object(path, saved)


def quote_unit(value, exec_arg=False):
    """Escape systemd syntax, including literal percent specifiers and $ in ExecStart."""
    value = str(value)
    if any(c in value for c in '\n\r\0'):
        raise ValueError('Service values may not contain control characters.')
    value = value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
    if exec_arg:
        value = value.replace('$', '$$')
    return '"' + value + '"'


def service_units(root, username, rfkill, bluetoothctl):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*\$?', username):
        raise ValueError('Unsupported system account name.')
    bluetooth = f'''[Unit]
Description=Enable Bluetooth for LED Marquee Animator
Wants=bluetooth.service
After=bluetooth.service
StartLimitIntervalSec=0

[Service]
Type=oneshot
ExecStart={quote_unit(rfkill, True)} unblock bluetooth
ExecStart={quote_unit(bluetoothctl, True)} power on
RemainAfterExit=yes
Restart=on-failure
RestartSec=5
TimeoutStartSec=30

[Install]
WantedBy=multi-user.target
'''
    player = f'''[Unit]
Description=LED Marquee Animator and local controls
Wants=coolled-bluetooth.service
After=coolled-bluetooth.service
StartLimitIntervalSec=0

[Service]
Type=simple
User={username}
WorkingDirectory={str(root / 'Player').replace('%', '%%')}
Environment={quote_unit('COOLLED_ROOT=' + str(root))}
Environment=PYTHONUNBUFFERED=1
ExecStart={quote_unit(python_path(root))} {quote_unit(root / 'Player/player.py', True)}
Restart=on-failure
RestartSec=5
TimeoutStopSec=10
KillMode=control-group
Nice=10
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
RestrictSUIDSGID=yes
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
'''
    return {'coolled-bluetooth.service': bluetooth, 'coolled-player.service': player}


def install_services(root):
    import pwd
    username = pwd.getpwuid(os.getuid()).pw_name
    units = service_units(root, username, find_tool('rfkill'), find_tool('bluetoothctl'))
    with tempfile.TemporaryDirectory(prefix='.services-', dir=root) as temp:
        for name, content in units.items():
            path = Path(temp) / name
            path.write_text(content, encoding='utf-8')
            run(['sudo', 'install', '-m', '644', path, f'/etc/systemd/system/{name}'])
    run(['sudo', 'systemctl', 'daemon-reload'])
    run(['sudo', 'systemctl', 'enable', '--now', 'bluetooth.service'])
    run(['sudo', 'systemctl', 'enable', 'coolled-bluetooth.service', 'coolled-player.service'])
    run(['sudo', 'systemctl', 'restart', 'coolled-bluetooth.service'])
    run(['sudo', 'systemctl', 'restart', 'coolled-player.service'])
    run(['systemctl', 'is-active', '--quiet', 'coolled-player.service'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.home() / 'CoolLED',
                        help='Data and application directory (default: ~/CoolLED)')
    parser.add_argument('--address', help='BLE address; otherwise use saved configuration or scan interactively')
    parser.add_argument('--no-service', action='store_true', help='Linux: install files without systemd startup')
    args = parser.parse_args(argv)
    windows = sys.platform == 'win32'
    if sys.platform != 'win32' and not sys.platform.startswith('linux'):
        parser.error('This installer supports Windows and Linux only.')
    if not (3, 11) <= sys.version_info[:2] <= (3, 13):
        parser.error('Use Python 3.11, 3.12 or 3.13. The personal setup used 3.13.')
    if not windows and os.geteuid() == 0:
        parser.error('Run as your normal account, without sudo. Service setup requests sudo when needed.')
    root = args.root.expanduser().resolve()
    if root == Path(root.anchor) or any(c in str(root) for c in '\n\r\0'):
        parser.error('Choose a normal application directory, not a filesystem root.')
    if root == SOURCE or SOURCE in root.parents or root in SOURCE.parents:
        parser.error('Choose an installation directory separate from the source checkout.')
    if args.address:
        args.address = address(args.address)
    requirements = ['git']
    if not windows and not args.no_service:
        requirements += ['sudo', 'systemctl', 'rfkill', 'bluetoothctl']
    missing = [name for name in requirements if not find_tool(name)]
    if missing:
        raise ValueError('Missing commands: ' + ', '.join(missing) + '. See docs/SETUP.md.')
    root.mkdir(parents=True, exist_ok=True)
    # Fail on malformed user settings before doing network or service operations.
    read_object(root / 'hardware.json')
    if windows:
        read_object(root / 'uploader_settings.json')
    print(f'Installing to {root}. Close other uploaders before continuing.')
    prepare_driver(root)
    venv.EnvBuilder(with_pip=True).create(root / '.venv')
    python = python_path(root, windows)
    requirements_file = SOURCE / ('windows/requirements.txt' if windows else 'pi/requirements.txt')
    run([python, '-m', 'pip', 'install', '-r', requirements_file])
    if windows:
        run([python, '-c', 'import tkinter; from PIL import ImageTk'])
    selected_address = choose_address(python, root, args.address)
    if not windows and not args.no_service:
        run(['sudo', '-v'])
        active = subprocess.run(['systemctl', 'is-active', '--quiet', 'coolled-player.service'])
        if active.returncode == 0:
            run(['sudo', 'systemctl', 'stop', 'coolled-player.service'])
    stage_player(root, windows)
    seed_files(root, windows, selected_address)
    if windows:
        shutil.copy2(SOURCE / 'windows/Start_CoolLED.cmd', root / 'Start_CoolLED.cmd')
        print(f'Installed. Double-click {root / "Start_CoolLED.cmd"} to open the player.')
    elif args.no_service:
        print('Installed without startup. Run:')
        print(shlex.join(['env', f'COOLLED_ROOT={root}', str(python), str(root / 'Player/player.py')]))
    else:
        install_services(root)
        print('Service installed. Open http://<your-linux-host-ip>:8080 on your trusted LAN.')
    print('Setup completed. No animation was uploaded; verify playback on the physical sign.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f'Setup failed: {exc}', file=sys.stderr)
        raise SystemExit(1)
