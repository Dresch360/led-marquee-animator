"""Dedicated CoolLEDX player: one upload worker, a local control page and saved rotation."""
from __future__ import annotations

import copy
from collections import deque
from dataclasses import dataclass
import fcntl
import json
import logging
import math
import os
from pathlib import Path
import random
import re
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
import time

from flask import Flask, abort, jsonify, render_template, request, send_file
from PIL import Image, ImageOps, GifImagePlugin
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

WIDTH, HEIGHT, MAX_FRAMES = 96, 16, 113
SPEEDS = (32, 64, 128, 256, 512)
FITS = ('Fill panel', 'Fit entire image', 'Stretch to panel')
RETRY_SECONDS = 30
SUCCESS = 'LED sign update completed successfully'
LOG = logging.getLogger('coolled')


def load_address(root: Path):
    try:
        data = json.loads((root / 'hardware.json').read_text(encoding='utf-8-sig'))
        value = data.get('address', '') if isinstance(data, dict) else ''
        if not isinstance(value, str) or not re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', value):
            raise ValueError('Invalid Bluetooth address')
        return value.upper()
    except (OSError, ValueError) as exc:
        raise ValueError('Display setup is missing or invalid. Run setup_player.py with your display address.') from exc


def describe_gif(path: Path):
    with Image.open(path) as gif:
        if gif.format != 'GIF':
            raise ValueError('Choose an animated GIF.')
        if gif.width * gif.height > 1024 * 1024:
            raise ValueError('Resize the source GIF to at most 1 megapixel before adding it.')
        count = gif.n_frames
        if not 2 <= count <= MAX_FRAMES:
            raise ValueError(f'Use an animated GIF with 2–{MAX_FRAMES} frames.')
        return {'frames': count, 'width': gif.width, 'height': gif.height}


def prepare_gif(source: Path, fit: str, target: Path):
    """Match the desktop transformations, keeping every source frame, even duplicates."""
    info = describe_gif(source)
    if fit not in FITS:
        raise ValueError('Unknown image fit.')
    palette = Image.new('P', (1, 1))
    colors = [(r, g, b) for r in (0, 255) for g in (0, 255) for b in (0, 255)]
    palette.putpalette([v for c in colors for v in c] + [0] * 744)
    with Image.open(source) as gif, target.open('wb') as output:
        for i in range(info['frames']):
            gif.seek(i)
            rgba = gif.convert('RGBA')
            rgb = Image.alpha_composite(Image.new('RGBA', rgba.size, (0, 0, 0, 255)), rgba).convert('RGB')
            if fit == 'Fill panel':
                rgb = ImageOps.fit(rgb, (WIDTH, HEIGHT), method=Image.Resampling.NEAREST)
            elif fit == 'Fit entire image':
                rgb = ImageOps.pad(rgb, (WIDTH, HEIGHT), method=Image.Resampling.NEAREST, color='black')
            else:
                rgb = rgb.resize((WIDTH, HEIGHT), Image.Resampling.NEAREST)
            rgb = rgb.point([0 if p < 128 else 255 for p in range(256)] * 3)
            indexed = rgb.quantize(palette=palette, dither=Image.Dither.NONE)
            if i == 0:
                for chunk in GifImagePlugin.getheader(indexed, info={'loop': 0})[0]:
                    output.write(chunk)
            duration = max(20, min(1000, int(gif.info.get('duration', 120))))
            for chunk in GifImagePlugin.getdata(indexed, duration=duration, disposal=2):
                output.write(chunk)
        output.write(b';')
    with Image.open(target) as check:
        if check.n_frames != info['frames'] or check.size != (WIDTH, HEIGHT):
            raise ValueError('Prepared GIF did not preserve its frames; upload cancelled.')


def connection_issue(lines):
    text = '\n'.join(line.lower() for line in lines if not re.search(r'(?:^| - )info - ', line, re.I))
    # Failures caused by content or code should stop, rather than retry forever.
    if any(word in text for word in ('checksum', 'invalid attribute', 'invalid value', 'data length',
                                     'payload', 'importerror', 'modulenotfounderror', 'syntaxerror')):
        return False
    return any(word in text for word in (
        'unable to locate a coolled', 'timeouterror', 'connection timed out', 'timed out while connecting',
        'device is not connected', 'device not connected', 'device disconnected', 'not connected',
        'disconnected unexpectedly', 'connection lost', 'failed to connect', 'could not connect',
        'device was not found', 'device not found', 'unreachable', 'no bluetooth adapters',
        'bluetooth is turned off', 'bluetooth is not available', 'org.bluez.error.notready',
        'org.bluez.error.failed', 'org.bluez.error.inprogress', 'software caused connection abort',
        'connection reset', 'le-connection-abort', 'br-connection', 'org.bluez.error.notconnected'))


@dataclass
class Result:
    success: bool = False
    link_error: bool = False
    cancelled: bool = False
    detail: str = ''


class DriverUpload:
    def __init__(self, root: Path, timeout_seconds=180):
        self.root = root
        self.timeout_seconds = timeout_seconds

    def __call__(self, item, log, stage, cancelled, register):
        try:
            target_address = load_address(self.root)
        except ValueError as exc:
            return Result(detail=str(exc))
        repo = self.root / 'driver'
        script = repo / 'utils/tweak_sign.py'
        code = repo / 'src/coolledx/client.py'
        if not script.is_file() or not code.is_file():
            return Result(detail='Working driver was not found in the CoolLED/driver folder.')
        if not re.search(r'response\s*=\s*False', code.read_text(encoding='utf-8-sig')):
            return Result(detail='The Bluetooth write patch is missing from the driver.')
        proc = None
        try:
            with tempfile.TemporaryDirectory(prefix='coolled-pi-') as work:
                prepared = Path(work) / 'animation.gif'
                stage('Preparing animation')
                prepare_gif(self.root / 'animations' / item['name'], item['fit'], prepared)
                if cancelled.is_set():
                    return Result(cancelled=True)
                env = os.environ.copy()
                env.update(PYTHONPATH=str(repo / 'src'), PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8')
                cmd = [sys.executable, '-u', str(script), '-a', target_address, '-n', str(prepared),
                       '-N', str(item['timing']), '-w', 'scale', '-g', 'scale',
                       '--connection-timeout', '20', '--connection-retries', '1']
                stage('Connecting to display')
                proc = subprocess.Popen(cmd, cwd=repo, env=env, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding='utf-8', errors='replace')
                register(proc)
                # Bound a stuck uploader so rotation can recover without user intervention.
                timed_out = threading.Event()
                def timeout():
                    timed_out.set()
                    if proc.poll() is None:
                        proc.kill()
                watchdog = threading.Timer(self.timeout_seconds, timeout)
                watchdog.daemon = True
                watchdog.start()
                lines, completed = [], False
                try:
                    with proc.stdout:
                        for line in proc.stdout:
                            line = line.rstrip()
                            lines.append(line)
                            log(line)
                            if 'Sending animation command' in line:
                                stage('Uploading animation')
                            if SUCCESS in line:
                                completed = True
                    status = proc.wait()
                finally:
                    watchdog.cancel()
                if cancelled.is_set():
                    return Result(cancelled=True)
                if timed_out.is_set():
                    return Result(link_error=True, detail='Uploader timed out; waiting to reconnect.')
                if status == 0 and completed:
                    return Result(success=True)
                return Result(link_error=connection_issue(lines),
                              detail='Upload did not complete. Open Activity for the driver output.')
        except Exception as exc:
            log(str(exc))
            return Result(detail=str(exc), cancelled=cancelled.is_set())
        finally:
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait()
            register(None)


class Player:
    def __init__(self, root: Path, runner=None, retry_seconds=RETRY_SECONDS, start_thread=True, rng=None):
        self.root = Path(root)
        self.directory = self.root / 'animations'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.config_path = self.root / 'pi_player_settings.json'
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.closing = False
        self.cancel = threading.Event()
        self.process = None
        self.runner = runner or DriverUpload(self.root)
        self.rng = rng if rng is not None else random.Random()
        self.retry_seconds = retry_seconds
        self.logs = deque(maxlen=120)
        self.running = self.busy = self.retrying = False
        self.deadline = None
        self.queued = None
        self.position = 0
        self.round_items = []
        self.current = self.last_sent = ''
        self.last_sent_at = ''
        self.phase = 'Stopped'
        self.error = ''
        self.config = {'version': 1, 'minutes': 5.0, 'enabled': False, 'shuffle': False, 'items': []}
        if self.config_path.exists():
            # Keep an unreadable config intact and report it; never silently replace it.
            saved = json.loads(self.config_path.read_text(encoding='utf-8'))
            self.config = self.validate_config(saved)
        self.refresh(save=False)
        resume = self.config['enabled']
        self.thread = threading.Thread(target=self._worker, daemon=True, name='LED-upload')
        if start_thread:
            self.thread.start()
            if resume:
                try:
                    self.start()
                except ValueError as exc:
                    self.error = str(exc)
        self.log('Player ready. Rotation resumes after boot only when it was left running.')

    def log(self, message):
        with self.lock:
            self.logs.append(time.strftime('%H:%M:%S ') + str(message))
        LOG.info('%s', message)

    def _safe_path(self, name):
        if not isinstance(name, str) or Path(name).name != name or not name.lower().endswith('.gif'):
            raise ValueError('Invalid animation name.')
        path = self.directory / name
        if path.is_symlink() or path.resolve().parent != self.directory.resolve():
            raise ValueError('Animation must be stored in the animations folder.')
        return path

    def validate_config(self, data):
        if not isinstance(data, dict):
            raise ValueError('Settings must be an object.')
        minutes = float(data.get('minutes', 5))
        if not math.isfinite(minutes) or not 0 < minutes <= 1440:
            raise ValueError('Set an interval greater than 0 and at most 1440 minutes.')
        result, seen = [], set()
        for value in data.get('items', []):
            name = value['name']
            self._safe_path(name)
            if name in seen:
                raise ValueError('Each animation can appear only once in the list.')
            seen.add(name)
            timing = int(value.get('timing', 128))
            fit = value.get('fit', FITS[0])
            if timing not in SPEEDS or fit not in FITS:
                raise ValueError('Choose a supported speed and fit.')
            result.append({'name': name, 'timing': timing, 'fit': fit,
                           'selected': bool(value.get('selected', True))})
        return {'version': 1, 'minutes': minutes, 'enabled': bool(data.get('enabled', False)),
                'shuffle': bool(data.get('shuffle', False)), 'items': result}

    def _save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.config_path.with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8') as file:
            json.dump(self.config, file, indent=2)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(self.config_path)

    def require_idle(self):
        if self.busy or self.running:
            raise ValueError('Stop rotation or the current upload before changing the playlist.')

    def refresh(self, save=True):
        with self.lock:
            if save:
                self.require_idle()
            known = {item['name'] for item in self.config['items']}
            for path in sorted(self.directory.iterdir(), key=lambda p: p.name.casefold()):
                if (path.name.startswith('.') or not path.is_file() or path.is_symlink()
                        or path.suffix.lower() != '.gif' or path.name in known):
                    continue
                self.config['items'].append({'name': path.name, 'timing': 128, 'fit': FITS[0],
                                             'selected': not path.name.lower().startswith('frame_test_')})
            if save:
                self._save()

    def set_config(self, data):
        with self.lock:
            self.require_idle()
            updated = self.validate_config(data)
            # The browser edits existing files; rescan/upload is how new files are added.
            existing = {item['name'] for item in self.config['items']}
            if {item['name'] for item in updated['items']} != existing:
                raise ValueError('File list changed. Refresh the page and try again.')
            updated['enabled'] = False
            self.config = updated
            self._save()
            self.error = ''

    def playlist(self):
        return [item for item in self.config['items'] if item['selected']]

    def _new_round(self, previous_name=None):
        items = self.playlist()
        if self.config['shuffle']:
            self.rng.shuffle(items)
            # Retain every selected item once while avoiding a boundary repeat.
            if len(items) > 1 and items[0]['name'] == previous_name:
                other = self.rng.randrange(1, len(items))
                items[0], items[other] = items[other], items[0]
        return items

    def _enqueue(self, item, mode):
        self.cancel = threading.Event()
        self.busy = True
        self.current = item['name']
        self.phase = 'Preparing animation'
        self.queued = (copy.deepcopy(item), mode, self.cancel)
        self.condition.notify_all()

    def start(self):
        with self.condition:
            self.require_idle()
            playlist = self.playlist()
            if not playlist:
                raise ValueError('Select at least one animation for rotation.')
            for item in playlist:
                describe_gif(self._safe_path(item['name']))
            self.running = True
            self.position = 0
            self.round_items = self._new_round(self.last_sent or None)
            self.retrying = False
            self.error = ''
            self.config['enabled'] = True
            self._save()
            self._enqueue(self.round_items[0], 'rotation')

    def send_once(self, name):
        with self.condition:
            self.require_idle()
            item = next((i for i in self.config['items'] if i['name'] == name), None)
            if item is None:
                raise ValueError('Animation was not found.')
            describe_gif(self._safe_path(name))
            self.error = ''
            self._enqueue(item, 'manual')

    def stop(self):
        with self.condition:
            self.running = False
            self.config['enabled'] = False
            self._save()
            self.deadline = None
            self.retrying = False
            self.cancel.set()
            if self.queued:
                self.queued = None
                self.busy = False
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
            self.phase = 'Stopping upload' if self.busy else 'Stopped'
            self.condition.notify_all()

    def _register(self, process):
        with self.lock:
            self.process = process
            if process is not None and self.cancel.is_set() and process.poll() is None:
                process.terminate()

    def _stage(self, value):
        with self.lock:
            self.phase = value

    def _worker(self):
        while True:
            with self.condition:
                while not self.closing and self.queued is None:
                    if self.running and self.deadline is not None and self.deadline <= time.monotonic():
                        if not self.retrying:
                            self.position += 1
                            if self.position >= len(self.round_items):
                                previous_name = self.round_items[-1]['name']
                                self.round_items = self._new_round(previous_name)
                                self.position = 0
                        self.deadline = None
                        self._enqueue(self.round_items[self.position], 'rotation')
                        break
                    wait = max(0.01, self.deadline - time.monotonic()) if self.deadline is not None else None
                    self.condition.wait(timeout=wait)
                if self.closing:
                    return
                item, mode, cancelled = self.queued
                self.queued = None
            try:
                self.log('Sending: ' + item['name'])
                result = self.runner(item, self.log, self._stage, cancelled, self._register)
            except Exception as exc:
                self.log('Upload error: ' + str(exc))
                result = Result(detail=str(exc))
            with self.condition:
                self.busy = False
                self.process = None
                if cancelled.is_set() or result.cancelled:
                    self.phase = 'Stopped'
                elif result.success:
                    self.last_sent = item['name']
                    self.last_sent_at = time.strftime('%Y-%m-%d %H:%M:%S')
                    self.retrying = False
                    self.phase = 'Playing' if self.running else 'Sent once'
                    if self.running and mode == 'rotation':
                        self.deadline = time.monotonic() + self.config['minutes'] * 60
                elif self.running and mode == 'rotation' and result.link_error:
                    self.retrying = True
                    self.deadline = time.monotonic() + self.retry_seconds
                    self.phase = 'Waiting for display'
                    self.log(f'Display unavailable; retrying {item["name"]} in {self.retry_seconds:g} seconds.')
                else:
                    self.running = False
                    self.config['enabled'] = False
                    self.deadline = None
                    self.retrying = False
                    self.error = result.detail or 'Upload failed. Check Activity.'
                    self.phase = 'Upload failed'
                    self._save()
                self.condition.notify_all()

    def snapshot(self):
        with self.lock:
            return {'config': copy.deepcopy(self.config), 'running': self.running, 'busy': self.busy,
                    'retrying': self.retrying, 'phase': self.phase, 'current': self.current,
                    'last_sent': self.last_sent, 'last_sent_at': self.last_sent_at, 'error': self.error,
                    'remaining': max(0, math.ceil(self.deadline - time.monotonic())) if self.deadline else None,
                    'log': list(self.logs)}

    def shutdown(self):
        with self.condition:
            # Preserve enabled in the saved config so a boot/service restart can resume rotation.
            self.closing = True
            self.cancel.set()
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
            self.condition.notify_all()
        if self.thread.is_alive():
            self.thread.join(timeout=6)


def create_app(player: Player):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    token = secrets.token_urlsafe(32)

    @app.before_request
    def protect_changes():
        if request.method == 'POST' and not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), token):
            abort(403, description='Refresh the page before making changes.')

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; frame-ancestors 'none'"
        return response

    @app.errorhandler(Exception)
    def error(exc):
        if isinstance(exc, HTTPException):
            return jsonify(error=exc.description), exc.code
        if isinstance(exc, (ValueError, KeyError, TypeError, OSError)):
            return jsonify(error=str(exc)), 400
        LOG.exception('Request failed')
        return jsonify(error='Request failed. Check the service log.'), 500

    @app.get('/')
    def index():
        return render_template('index.html', token=token)

    @app.get('/api/state')
    def state():
        return jsonify(player.snapshot())

    @app.get('/api/files')
    def files():
        result = []
        with player.lock:
            for item in player.config['items']:
                row = copy.deepcopy(item)
                try:
                    row.update(describe_gif(player._safe_path(item['name'])))
                    row['warning'] = ('Diagnostic file: leave out of normal rotation.'
                                      if item['name'].lower().startswith('frame_test_') else
                                      'More than the 48 frames verified on this panel.' if row['frames'] > 48 else '')
                except (ValueError, OSError) as exc:
                    row.update(frames=0, width=0, height=0, warning=str(exc))
                result.append(row)
        return jsonify(files=result)

    @app.get('/animations/<name>')
    def animation(name):
        path = player._safe_path(name)
        if not path.is_file():
            abort(404)
        return send_file(path, mimetype='image/gif', conditional=True)

    @app.post('/api/settings')
    def settings():
        player.set_config(request.get_json())
        return jsonify(ok=True)

    @app.post('/api/start')
    def start():
        player.start()
        return jsonify(ok=True)

    @app.post('/api/stop')
    def stop():
        player.stop()
        return jsonify(ok=True)

    @app.post('/api/send')
    def send():
        player.send_once(request.get_json()['name'])
        return jsonify(ok=True)

    @app.post('/api/rescan')
    def rescan():
        player.refresh()
        return jsonify(ok=True)

    @app.post('/api/upload')
    def upload():
        with player.lock:
            player.require_idle()
            incoming = request.files.get('file')
            if incoming is None or not incoming.filename:
                raise ValueError('Choose a GIF to add.')
            name = secure_filename(incoming.filename)
            destination = player._safe_path(name)
            if destination.exists():
                raise ValueError('That filename already exists. Rename the new GIF before adding it.')
            fd, tempname = tempfile.mkstemp(dir=player.directory, prefix='.incoming-', suffix='.gif')
            os.close(fd)
            temp = Path(tempname)
            try:
                incoming.save(temp)
                describe_gif(temp)
                temp.replace(destination)
            finally:
                temp.unlink(missing_ok=True)
            player.refresh()
        return jsonify(ok=True, name=name)

    return app


def main():
    from waitress import serve
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    root = Path(os.environ.get('COOLLED_ROOT', str(Path.home() / 'CoolLED'))).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    load_address(root)
    with (root / 'pi_player.lock').open('w') as instance:
        try:
            fcntl.flock(instance, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another Pi player instance is already running.')
        player = Player(root)
        def stop_service(*_):
            player.shutdown()
            raise SystemExit(0)
        signal.signal(signal.SIGTERM, stop_service)
        signal.signal(signal.SIGINT, stop_service)
        try:
            serve(create_app(player), host='0.0.0.0', port=8080, threads=4,
                  max_request_body_size=16*1024*1024, channel_timeout=60)
        finally:
            player.shutdown()


if __name__ == '__main__':
    main()
