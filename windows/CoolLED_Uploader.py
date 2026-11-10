"""Small desktop front end for the previously verified CoolLEDX driver.

The panel holds the last upload. Playlist rotation is performed by this PC.
No firmware changes, driver installation or automatic startup are performed.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import tempfile
import threading
import time
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from dataclasses import asdict, dataclass, field

from PIL import Image, ImageOps, ImageTk

WIDTH, HEIGHT = 96, 16
MAX_FRAMES = min(255, (65535 - 27) // (WIDTH * HEIGHT * 3 // 8))
# A conservative combined budget matching the 48-frame clips already played.
# This is not a claim about the controller's maximum memory capacity.
REEL_FRAME_BUDGET = 48
PANEL_RETRY_SECONDS = 30
REVISION = 'abf781b671b7a89571711127be0094b308e7f722'
SPEEDS = {'Very fast (32)': 32, 'Fast (64)': 64, 'Normal (128)': 128,
          'Slow (256)': 256, 'Very slow (512)': 512}
FITS = ('Fill panel', 'Fit entire image', 'Stretch to panel')
SUCCESS_MARKER = 'LED sign update completed successfully'
BACKGROUND_HINT = 'X minimizes to the taskbar. Exit quits. Keep the PC awake during rotation.'


@dataclass
class Item:
    path: str
    timing: int = 128
    fit: str = 'Fill panel'


@dataclass
class Settings:
    address: str
    driver: str
    python: str
    minutes: float = 5.0
    items: list[Item] = field(default_factory=list)

    @classmethod
    def defaults(cls, home: Path | None = None):
        root = (home or Path.home()) / 'CoolLED'
        samples = [root / 'Pitfall_Jungle_Swing.gif', root / 'CoolLED_RGB_Test.gif']
        bundled = Path(__file__).resolve().parent / 'animations'
        items = [Item(str(p)) for p in samples if p.is_file()]
        if not items:
            items = [Item(str(p)) for p in sorted(bundled.glob('*.gif'))]
        return cls('FF:FF:00:00:9E:3F',
                   str(root / 'September' / ('coolledx-driver-' + REVISION)),
                   str(root / 'coolledx-driver-main' / '.venv' / 'Scripts' / 'python.exe'),
                   items=items)


def load_settings(path: Path):
    default = Settings.defaults()
    if not path.exists():
        return default, ''
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('Expected a settings object')
        items = []
        for entry in data.get('items', []):
            if not isinstance(entry, dict) or not isinstance(entry.get('path'), str):
                raise ValueError('Invalid playlist entry')
            timing = int(entry.get('timing', 128))
            if timing not in SPEEDS.values():
                timing = 128
            fit = entry.get('fit', FITS[0])
            items.append(Item(entry['path'], timing, fit if fit in FITS else FITS[0]))
        minutes = validate_interval(data.get('minutes', 5))
        return Settings(str(data.get('address', default.address)),
                        str(data.get('driver', default.driver)),
                        str(data.get('python', default.python)), minutes, items), ''
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        return default, f'Settings could not be read; defaults loaded. {exc}'


def save_settings(path: Path, settings: Settings):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(asdict(settings), indent=2), encoding='utf-8')
    temp.replace(path)


def validate_interval(value):
    minutes = float(value)
    if not math.isfinite(minutes) or not 0 < minutes <= 1440:
        raise ValueError('Enter an interval greater than 0 and no more than 1440 minutes.')
    return minutes


def validate_setup(settings: Settings):
    if not re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}', settings.address):
        raise ValueError('Check the Bluetooth address in Setup.')
    if not Path(settings.python).is_file():
        raise ValueError('The saved Python program was not found. Open Setup to select it.')
    repo = Path(settings.driver)
    for relative in ('utils/tweak_sign.py', 'src/coolledx/client.py', 'src/coolledx/commands.py'):
        if not (repo / relative).is_file():
            raise ValueError('The driver folder was not found. Select the verified September folder in Setup.')
    commands = (repo / 'src/coolledx/commands.py').read_text(encoding='utf-8-sig')
    client = (repo / 'src/coolledx/client.py').read_text(encoding='utf-8-sig')
    if 'def create_command(' not in commands or not re.search(r'response\s*=\s*False', client):
        raise ValueError('Select the verified September driver with the Bluetooth write fix in Setup.')


def read_animation(path: Path, fit: str):
    """Prepare exactly the same 96x16, eight-colour frames for preview/upload."""
    if fit not in FITS:
        raise ValueError('Choose a valid fit option.')
    frames, durations = [], []
    with Image.open(path) as gif:
        count = getattr(gif, 'n_frames', 1)
        if gif.format != 'GIF' or count < 2:
            raise ValueError('Choose an animated GIF with at least two frames.')
        if count > MAX_FRAMES:
            raise ValueError(f'This GIF has {count} frames. Use {MAX_FRAMES} or fewer for this panel.')
        original_size = gif.size
        for index in range(count):
            gif.seek(index)
            rgba = gif.convert('RGBA')
            background = Image.new('RGBA', rgba.size, (0, 0, 0, 255))
            rgb = Image.alpha_composite(background, rgba).convert('RGB')
            if fit == 'Fill panel':
                rgb = ImageOps.fit(rgb, (WIDTH, HEIGHT), method=Image.Resampling.NEAREST)
            elif fit == 'Fit entire image':
                rgb = ImageOps.pad(rgb, (WIDTH, HEIGHT), method=Image.Resampling.NEAREST, color='black')
            else:
                rgb = rgb.resize((WIDTH, HEIGHT), Image.Resampling.NEAREST)
            frames.append(rgb.point([0 if x < 128 else 255 for x in range(256)] * 3))
            durations.append(max(20, min(1000, int(gif.info.get('duration', 120)))))
    return frames, durations, original_size


def write_prepared(frames, durations, path: Path):
    if not 2 <= len(frames) <= MAX_FRAMES:
        raise ValueError('The animation frame count is not supported.')
    # Same palette for every frame avoids per-frame colour changes on the panel.
    palette = Image.new('P', (1, 1))
    colors = [(r, g, b) for r in (0, 255) for g in (0, 255) for b in (0, 255)]
    palette.putpalette([v for c in colors for v in c] + [0] * (768 - 24))
    indexed = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in frames]
    indexed[0].save(path, save_all=True, append_images=indexed[1:],
                    duration=durations, loop=0, disposal=2, optimize=False)


def reel_frame_counts(lengths, budget=REEL_FRAME_BUDGET):
    """Allocate a bounded reel fairly, retaining at least two frames per scene."""
    if not lengths or any(n < 2 for n in lengths):
        raise ValueError('Every scene must be an animated GIF with at least two frames.')
    if not 2 <= budget <= MAX_FRAMES:
        raise ValueError('The combined frame budget is not supported.')
    if len(lengths) * 2 > budget:
        raise ValueError(f'Use at most {budget // 2} animations in a combined reel.')
    if sum(lengths) <= budget:
        return list(lengths)
    remaining = budget - 2 * len(lengths)
    weights = [n - 2 for n in lengths]
    total_weight = sum(weights)
    quotas = [remaining * w / total_weight for w in weights]
    counts = [2 + math.floor(q) for q in quotas]
    missing = budget - sum(counts)
    order = sorted(range(len(lengths)), key=lambda i: (quotas[i] - math.floor(quotas[i]), -i), reverse=True)
    for index in order[:missing]:
        counts[index] += 1
    return counts


def prepare_reel(items, budget=REEL_FRAME_BUDGET):
    if len(items) < 2:
        raise ValueError('Add at least two animations to combine.')
    if len(items) * 2 > budget:
        raise ValueError(f'Use at most {budget // 2} animations in a combined reel.')
    lengths = []
    for item in items:
        with Image.open(item.path) as gif:
            n = getattr(gif, 'n_frames', 1)
            if gif.format != 'GIF' or n < 2:
                raise ValueError(f'{Path(item.path).name} is not an animated GIF.')
            lengths.append(n)
    counts = reel_frame_counts(lengths, budget)
    combined, rows = [], []
    for item, original, count in zip(items, lengths, counts):
        frames, _, _ = read_animation(Path(item.path), item.fit)
        indices = [round(i * (len(frames) - 1) / (count - 1)) for i in range(count)]
        combined.extend(frames[i] for i in indices)
        rows.append((Path(item.path).name, original, count))
    # The verified wire format has one speed for the whole uploaded animation.
    return combined, [120] * len(combined), rows


def upload_command(settings: Settings, item: Item, prepared: Path):
    if item.timing not in SPEEDS.values():
        raise ValueError('Choose a valid playback speed.')
    return [settings.python, '-u', str(Path(settings.driver) / 'utils' / 'tweak_sign.py'),
            '-a', settings.address, '-n', str(prepared), '-N', str(item.timing),
            '-w', 'scale', '-g', 'scale', '--connection-retries', '1']


def is_connection_issue(line):
    """Recognize discovery/disconnection errors without hiding data/setup errors."""
    text = line.lower()
    if ' - info - ' in text:
        return False
    if any(word in text for word in ('checksum', 'invalid attribute', 'invalid value', 'data length', 'payload')):
        return False
    return any(phrase in text for phrase in (
        'unable to locate a coolled', 'connection timed out', 'timed out while connecting',
        'device is not connected', 'device not connected', 'device disconnected',
        'disconnected unexpectedly', 'connection lost', 'failed to connect',
        'could not connect', 'device was not found', 'device not found', 'unreachable',
        'bluetooth is turned off', 'bluetooth is not available', 'no bluetooth adapters'))


class UploadJob:
    """All subprocess IO is off the Tk thread. emit receives (kind, value)."""
    def __init__(self, settings, item, emit, *, frames=None, durations=None):
        self.settings, self.item, self.emit = settings, item, emit
        self.prepared_frames, self.prepared_durations = frames, durations
        self.cancelled = threading.Event()
        self.lock = threading.Lock()
        self.process = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self):
        self.thread.start()

    def cancel(self):
        self.cancelled.set()
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()

    def run(self):
        success, detail = False, ''
        connection_issue = False
        try:
            validate_setup(self.settings)
            self.emit('stage', 'Preparing animation…')
            if self.prepared_frames is None:
                frames, durations, _ = read_animation(Path(self.item.path), self.item.fit)
            else:
                frames, durations = self.prepared_frames, self.prepared_durations
                if durations is None or len(durations) != len(frames):
                    raise ValueError('The combined animation timing is incomplete.')
            with tempfile.TemporaryDirectory(prefix='coolled-upload-') as work:
                prepared = Path(work) / 'animation.gif'
                write_prepared(frames, durations, prepared)
                if self.cancelled.is_set():
                    return
                env = os.environ.copy()
                env['PYTHONPATH'] = str(Path(self.settings.driver) / 'src')
                env['PYTHONUNBUFFERED'] = '1'
                env['PYTHONIOENCODING'] = 'utf-8'
                self.emit('stage', 'Connecting to panel…')
                with self.lock:
                    if self.cancelled.is_set():
                        return
                    self.process = subprocess.Popen(
                        upload_command(self.settings, self.item, prepared),
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL, text=True, encoding='utf-8', errors='replace',
                        env=env, cwd=self.settings.driver,
                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                acknowledged = False
                assert self.process.stdout is not None
                for line in self.process.stdout:
                    self.emit('log', line.rstrip())
                    connection_issue = connection_issue or is_connection_issue(line)
                    if 'Sending animation command' in line:
                        self.emit('stage', 'Sending animation…')
                    if SUCCESS_MARKER in line:
                        acknowledged = True
                result = self.process.wait()
                self.process.stdout.close()
                success = result == 0 and acknowledged
                if not success:
                    detail = f'Upload did not complete (exit code {result}). See the activity log.'
        except Exception as exc:
            detail = str(exc)
            self.emit('log', detail)
        finally:
            self.emit('done', {'success': success, 'cancelled': self.cancelled.is_set(), 'detail': detail,
                               'combined': self.prepared_frames is not None,
                               'connection_issue': connection_issue and not success})


@dataclass
class Rotation:
    running: bool = False
    index: int = 0
    deadline: float | None = None
    waiting: bool = False

    def start(self, index=0):
        self.running, self.index, self.deadline = True, index, None
        self.waiting = False

    def uploaded(self, now, minutes):
        if self.running:
            self.waiting = False
            self.deadline = now + validate_interval(minutes) * 60

    def retry_after(self, now, seconds=PANEL_RETRY_SECONDS):
        if self.running:
            self.waiting = True
            self.deadline = now + seconds

    def due(self, now, length):
        if self.running and self.deadline is not None and now >= self.deadline:
            self.deadline = None
            if not self.waiting:
                self.index = (self.index + 1) % length
            return self.index
        return None

    def stop(self):
        self.running, self.deadline = False, None
        self.waiting = False


class Uploader:
    def __init__(self, root, config_path=None):
        self.root = root
        self.config_path = config_path or Path.home() / 'CoolLED' / 'uploader_settings.json'
        self.settings, warning = load_settings(self.config_path)
        self.events = queue.Queue()
        self.rotation = Rotation()
        self.job = None
        self.frames, self.durations = [], []
        self.preview_index = 0
        self.preview_token = 0
        self.preview_after = None
        self.preview_paused = False
        self.preview_timing_override = None
        self.reel_window = None
        self.reel_token = 0
        self.reel_result = None
        self.reel_after = None
        self.status = tk.StringVar(value='Ready')
        self.countdown = tk.StringVar(value=BACKGROUND_HINT)
        self.speed = tk.StringVar(value='Normal (128)')
        self.fit = tk.StringVar(value=FITS[0])
        self.minutes = tk.StringVar(value=f'{self.settings.minutes:g}')
        self.file_info = tk.StringVar(value='Choose an animation from the playlist.')
        self.build_ui()
        self.refresh_list()
        if warning:
            self.log(warning)
        if self.settings.items:
            self.tree.selection_set('0')
            self.selected()
        self.root.after(75, self.poll)
        self.root.after(250, self.tick)
        self.root.protocol('WM_DELETE_WINDOW', self.minimize)
        self.root.bind('<Unmap>', self.window_unmapped, add='+')
        self.root.bind('<Map>', self.window_mapped, add='+')

    def build_ui(self):
        root = self.root
        root.title('CoolLED Uploader')
        root.geometry('860x830')
        root.minsize(800, 790)
        root.configure(bg='#f3f5f7')
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10), background='#f3f5f7', foreground='#172434')
        style.configure('TButton', padding=(11, 7))
        style.configure('Accent.TButton', background='#147d66', foreground='white', font=('Segoe UI', 11, 'bold'))
        style.map('Accent.TButton', background=[('disabled', '#a5b6b0'), ('active', '#116b57')])
        style.configure('Treeview', rowheight=28, background='white', fieldbackground='white')
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), padding=5)
        outer = ttk.Frame(root, padding=22)
        outer.pack(fill='both', expand=True)
        header = ttk.Frame(outer)
        header.pack(fill='x')
        ttk.Label(header, text='CoolLED Uploader', font=('Segoe UI', 22, 'bold')).pack(side='left')
        self.exit_button = ttk.Button(header, text='Exit', command=self.close)
        self.exit_button.pack(side='right', padx=(8, 0))
        self.setup_button = ttk.Button(header, text='Setup', command=self.setup)
        self.setup_button.pack(side='right')
        ttk.Label(outer, text='Preview animations, send them to your panel and rotate a playlist.').pack(anchor='w', pady=(3, 16))
        list_frame = ttk.Frame(outer)
        list_frame.pack(fill='x')
        self.tree = ttk.Treeview(list_frame, columns=('name', 'speed'), show='headings', height=5, selectmode='browse')
        self.tree.heading('name', text='Animation')
        self.tree.heading('speed', text='Speed')
        self.tree.column('name', width=570)
        self.tree.column('speed', width=140, stretch=False)
        self.tree.pack(side='left', fill='x', expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.tree.yview)
        scrollbar.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind('<<TreeviewSelect>>', lambda _: self.selected())
        toolbar = ttk.Frame(outer)
        toolbar.pack(fill='x', pady=(8, 10))
        self.edit_buttons = []
        for label, action in [('Add GIFs…', self.add_files), ('Remove', self.remove), ('Move up', lambda: self.move(-1)), ('Move down', lambda: self.move(1))]:
            b = ttk.Button(toolbar, text=label, command=action)
            b.pack(side='left', padx=(0, 6))
            self.edit_buttons.append(b)
        self.canvas = tk.Canvas(outer, width=768, height=128, bg='#05090d', highlightthickness=0)
        self.canvas.pack(fill='x')
        self.canvas.create_text(384, 64, text='Animation preview', fill='#899aa7', font=('Segoe UI', 13), tags='placeholder')
        ttk.Label(outer, textvariable=self.file_info, font=('Segoe UI', 9)).pack(anchor='w', pady=(5, 10))
        controls = ttk.Frame(outer)
        controls.pack(fill='x')
        ttk.Label(controls, text='Selected animation speed').grid(row=0, column=0, sticky='w')
        ttk.Label(controls, text='Fit').grid(row=0, column=1, sticky='w', padx=(18, 0))
        self.speed_box = ttk.Combobox(controls, textvariable=self.speed, values=list(SPEEDS), state='readonly', width=22)
        self.speed_box.grid(row=1, column=0, sticky='w', pady=4)
        self.speed_box.bind('<<ComboboxSelected>>', lambda _: self.change_item(False))
        self.fit_box = ttk.Combobox(controls, textvariable=self.fit, values=FITS, state='readonly', width=24)
        self.fit_box.grid(row=1, column=1, sticky='w', padx=(18, 0), pady=4)
        self.fit_box.bind('<<ComboboxSelected>>', lambda _: self.change_item(True))
        ttk.Label(outer, text='Speed changes take effect when sent. Preview timing is approximate.', font=('Segoe UI', 9)).pack(anchor='w', pady=(1, 10))
        rotation_row = ttk.Frame(outer)
        rotation_row.pack(fill='x', pady=(0, 10))
        ttk.Label(rotation_row, text='Rotate every').pack(side='left')
        self.interval_box = ttk.Spinbox(rotation_row, textvariable=self.minutes, from_=0.1, to=1440, increment=0.5, width=7)
        self.interval_box.pack(side='left', padx=8)
        ttk.Label(rotation_row, text='minutes after each completed upload').pack(side='left')
        ttk.Label(rotation_row, text='Auto-reconnect enabled', font=('Segoe UI', 9)).pack(side='right')
        action_row = ttk.Frame(outer)
        action_row.pack(fill='x')
        self.send_button = ttk.Button(action_row, text='Send selected', style='Accent.TButton', command=self.send_selected)
        self.send_button.pack(side='left')
        self.start_button = ttk.Button(action_row, text='Start rotation', command=self.start_rotation)
        self.start_button.pack(side='left', padx=8)
        self.combined_button = ttk.Button(action_row, text='Upload combined reel…', command=self.open_combined)
        self.combined_button.pack(side='left', padx=(0, 8))
        self.stop_button = ttk.Button(action_row, text='Stop', command=self.stop, state='disabled')
        self.stop_button.pack(side='left')
        self.progress = ttk.Progressbar(action_row, mode='indeterminate', length=150)
        self.progress.pack(side='right', padx=(12, 0))
        ttk.Label(outer, textvariable=self.status, font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(12, 2))
        ttk.Label(outer, textvariable=self.countdown, font=('Segoe UI', 9)).pack(anchor='w')
        self.log_box = scrolledtext.ScrolledText(outer, height=4, font=('Consolas', 9), state='disabled', relief='flat', bg='#e6ebef')
        self.log_box.pack(fill='both', expand=True, pady=(10, 0))

    def log(self, value):
        self.log_box.configure(state='normal')
        self.log_box.insert('end', str(value) + '\n')
        if int(self.log_box.index('end-1c').split('.')[0]) > 300:
            self.log_box.delete('1.0', '100.0')
        self.log_box.see('end')
        self.log_box.configure(state='disabled')

    def persist(self):
        try:
            save_settings(self.config_path, self.settings)
        except OSError as exc:
            self.log(f'Could not save settings: {exc}')

    def selected_index(self):
        selected = self.tree.selection()
        return int(selected[0]) if selected else None

    def refresh_list(self, selected=None):
        self.tree.delete(*self.tree.get_children())
        for i, item in enumerate(self.settings.items):
            label = next((k for k, v in SPEEDS.items() if v == item.timing), 'Normal (128)')
            self.tree.insert('', 'end', iid=str(i), values=(Path(item.path).name, label))
        if selected is not None and 0 <= selected < len(self.settings.items):
            self.tree.selection_set(str(selected))

    def selected(self):
        index = self.selected_index()
        if index is None or index >= len(self.settings.items):
            return
        item = self.settings.items[index]
        self.preview_timing_override = None
        self.speed.set(next(k for k, v in SPEEDS.items() if v == item.timing))
        self.fit.set(item.fit)
        self.preview_token += 1
        token = self.preview_token
        self.file_info.set('Loading preview…')
        def work():
            try:
                result = read_animation(Path(item.path), item.fit)
                self.events.put(('preview', (token, result, '')))
            except Exception as exc:
                self.events.put(('preview', (token, None, str(exc))))
        threading.Thread(target=work, daemon=True).start()

    def animate(self):
        self.preview_after = None
        if not self.frames or self.preview_paused:
            return
        frame = self.frames[self.preview_index]
        available = max(96, self.canvas.winfo_width())
        scale = max(1, min(8, available // WIDTH))
        self.preview_photo = ImageTk.PhotoImage(frame.resize((WIDTH * scale, HEIGHT * scale), Image.Resampling.NEAREST))
        self.canvas.delete('all')
        self.canvas.create_image(available // 2, 64, image=self.preview_photo)
        index = self.selected_index()
        timing = self.preview_timing_override or (self.settings.items[index].timing if index is not None else 128)
        delay = max(20, int(self.durations[self.preview_index] * timing / 128))
        self.preview_index = (self.preview_index + 1) % len(self.frames)
        self.preview_after = self.root.after(delay, self.animate)

    def pause_preview(self):
        self.preview_paused = True
        if self.preview_after is not None:
            self.root.after_cancel(self.preview_after)
            self.preview_after = None

    def minimize(self):
        # Leave rotation and any upload running; stop rendering the hidden preview.
        self.pause_preview()
        self.root.iconify()

    def window_unmapped(self, event):
        if event.widget is self.root:
            self.pause_preview()

    def window_mapped(self, event):
        if event.widget is self.root and self.reel_window is None:
            self.preview_paused = False
            if self.frames and self.preview_after is None:
                self.animate()

    def add_files(self):
        if self.job or self.rotation.running:
            return
        paths = filedialog.askopenfilenames(title='Add animations', initialdir=Path.home() / 'CoolLED', filetypes=[('Animated GIFs', '*.gif')])
        existing = {os.path.normcase(str(Path(item.path).resolve())) for item in self.settings.items}
        first = len(self.settings.items)
        for path in paths:
            key = os.path.normcase(str(Path(path).resolve()))
            if key not in existing:
                self.settings.items.append(Item(path))
                existing.add(key)
        self.refresh_list(first if first < len(self.settings.items) else self.selected_index())
        self.persist()

    def remove(self):
        index = self.selected_index()
        if index is None or self.job or self.rotation.running:
            return
        self.settings.items.pop(index)
        self.refresh_list(min(index, len(self.settings.items) - 1))
        if not self.settings.items:
            self.frames = []
            self.preview_token += 1
            self.canvas.delete('all')
            self.file_info.set('Add an animated GIF to begin.')
        self.persist()

    def move(self, offset):
        index = self.selected_index()
        if index is None or self.job or self.rotation.running:
            return
        other = index + offset
        if 0 <= other < len(self.settings.items):
            self.settings.items[index], self.settings.items[other] = self.settings.items[other], self.settings.items[index]
            self.refresh_list(other)
            self.persist()

    def change_item(self, reload):
        index = self.selected_index()
        if index is None or self.job or self.rotation.running:
            return
        item = self.settings.items[index]
        item.timing, item.fit = SPEEDS[self.speed.get()], self.fit.get()
        self.tree.set(str(index), 'speed', self.speed.get())
        self.persist()
        if reload:
            self.selected()

    def set_controls(self):
        busy = self.job is not None or self.rotation.running
        state = 'disabled' if busy else 'normal'
        for button in self.edit_buttons + [self.setup_button, self.send_button, self.start_button, self.combined_button]:
            button.configure(state=state)
        self.interval_box.configure(state=state)
        for box in (self.speed_box, self.fit_box):
            box.configure(state='disabled' if busy else 'readonly')
        self.stop_button.configure(state='normal' if busy else 'disabled')

    def send_selected(self):
        index = self.selected_index()
        if index is None:
            messagebox.showinfo('Choose an animation', 'Add or select an animation first.')
            return
        self.begin_upload(index)

    def open_combined(self):
        if self.job or self.rotation.running or self.reel_window is not None:
            return
        if len(self.settings.items) < 2:
            messagebox.showinfo('Add animations', 'Add at least two GIFs to the playlist first.')
            return
        win = self.reel_window = tk.Toplevel(self.root)
        win.title('Combined reel · one upload')
        win.transient(self.root)
        win.grab_set()
        win.protocol('WM_DELETE_WINDOW', self.close_reel)
        self.pause_preview()
        self.reel_token += 1
        token = self.reel_token
        self.reel_result = None
        self.reel_index = 0
        self.reel_speed = tk.StringVar(value='Normal (128)')
        self.reel_info = tk.StringVar(value='Preparing all scenes…')
        body = ttk.Frame(win, padding=20)
        body.pack(fill='both', expand=True)
        ttk.Label(body, text='One reel. One upload.', font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(body, text='The panel repeats the complete reel after the upload; the PC can disconnect.').pack(anchor='w', pady=(4, 12))
        self.reel_canvas = tk.Canvas(body, width=672, height=112, bg='#05090d', highlightthickness=0)
        self.reel_canvas.pack(fill='x')
        self.reel_table = ttk.Treeview(body, columns=('scene', 'source', 'reel'), show='headings', height=5)
        for name, label, width in [('scene', 'Scene (playlist order)', 420), ('source', 'Source frames', 115), ('reel', 'Reel frames', 115)]:
            self.reel_table.heading(name, text=label)
            self.reel_table.column(name, width=width, stretch=name == 'scene')
        self.reel_table.pack(fill='x', pady=(12, 6))
        ttk.Label(body, textvariable=self.reel_info, wraplength=665).pack(anchor='w', pady=4)
        ttk.Label(body, text='48-frame budget. Longer clips use fewer frames, so motion may be choppier.\nEach scene plays once before the reel repeats. The minute interval is not used.', wraplength=665).pack(anchor='w', pady=(4, 12))
        speed_row = ttk.Frame(body)
        speed_row.pack(fill='x')
        ttk.Label(speed_row, text='One playback speed for the entire reel').pack(side='left', padx=(0, 12))
        ttk.Combobox(speed_row, textvariable=self.reel_speed, values=list(SPEEDS), state='readonly', width=22).pack(side='left')
        buttons = ttk.Frame(body)
        buttons.pack(fill='x', pady=(16, 0))
        ttk.Button(buttons, text='Cancel', command=self.close_reel).pack(side='right')
        self.reel_send_button = ttk.Button(buttons, text='Upload once', style='Accent.TButton', state='disabled', command=self.send_combined)
        self.reel_send_button.pack(side='right', padx=(0, 8))
        items = [Item(**asdict(item)) for item in self.settings.items]
        def build():
            try:
                self.events.put(('reel_ready', (token, prepare_reel(items), '')))
            except Exception as exc:
                self.events.put(('reel_ready', (token, None, str(exc))))
        threading.Thread(target=build, daemon=True).start()

    def animate_reel(self):
        self.reel_after = None
        if self.reel_window is None or self.reel_result is None:
            return
        if self.root.state() == 'iconic':
            self.reel_after = self.root.after(500, self.animate_reel)
            return
        frames, durations, _ = self.reel_result
        frame = frames[self.reel_index]
        self.reel_photo = ImageTk.PhotoImage(frame.resize((672, 112), Image.Resampling.NEAREST))
        self.reel_canvas.delete('all')
        self.reel_canvas.create_image(336, 56, image=self.reel_photo)
        delay = max(20, int(durations[self.reel_index] * SPEEDS[self.reel_speed.get()] / 128))
        self.reel_index = (self.reel_index + 1) % len(frames)
        self.reel_after = self.root.after(delay, self.animate_reel)

    def close_reel(self):
        self.reel_token += 1
        if self.reel_after is not None:
            self.root.after_cancel(self.reel_after)
            self.reel_after = None
        if self.reel_window is not None:
            self.reel_window.grab_release()
            self.reel_window.destroy()
            self.reel_window = None
        self.reel_result = None
        if self.root.state() != 'iconic':
            self.preview_paused = False
            if self.frames and self.preview_after is None:
                self.animate()

    def send_combined(self):
        if self.job or self.rotation.running or self.reel_result is None:
            return
        try:
            validate_setup(self.settings)
        except (ValueError, OSError) as exc:
            messagebox.showerror('Check setup', str(exc), parent=self.reel_window)
            return
        frames, durations, rows = self.reel_result
        timing = SPEEDS[self.reel_speed.get()]
        self.close_reel()
        if self.preview_after is not None:
            self.root.after_cancel(self.preview_after)
            self.preview_after = None
        self.preview_token += 1
        self.frames, self.durations = frames, durations
        self.preview_index, self.preview_timing_override = 0, timing
        self.file_info.set(f'Combined reel · {len(rows)} scenes · {len(frames)} frames · 96 × 16')
        self.animate()
        self.status.set('Preparing one combined upload…')
        self.log('Combined reel: ' + ' → '.join(row[0] for row in rows))
        self.job = UploadJob(Settings(**{**asdict(self.settings), 'items': []}), Item('Combined reel', timing),
                             lambda kind, value: self.events.put((kind, value)), frames=frames, durations=durations)
        self.set_controls()
        self.progress.start(12)
        self.persist()
        self.job.start()

    def start_rotation(self):
        if self.job or self.rotation.running:
            return
        try:
            if len(self.settings.items) < 2:
                raise ValueError('Add at least two different animations to rotate.')
            validate_setup(self.settings)
            self.settings.minutes = validate_interval(self.minutes.get())
            for item in self.settings.items:
                if not Path(item.path).is_file():
                    raise ValueError(f'File not found: {item.path}')
        except (ValueError, OSError) as exc:
            messagebox.showerror('Cannot start rotation', str(exc))
            return
        self.persist()
        index = self.selected_index() or 0
        self.rotation.start(index)
        self.begin_upload(index)

    def begin_upload(self, index):
        if self.job:
            return
        try:
            validate_setup(self.settings)
            item = self.settings.items[index]
            if not Path(item.path).is_file():
                raise ValueError(f'File not found: {item.path}')
        except (ValueError, OSError) as exc:
            self.rotation.stop()
            self.set_controls()
            messagebox.showerror('Cannot send animation', str(exc))
            return
        self.tree.selection_set(str(index))
        self.tree.see(str(index))
        self.status.set('Preparing ' + Path(item.path).name + '…')
        self.log('Sending: ' + item.path)
        self.job = UploadJob(Settings(**{**asdict(self.settings), 'items': []}), Item(**asdict(item)),
                             lambda kind, value: self.events.put((kind, value)))
        self.set_controls()
        self.progress.start(12)
        self.persist()
        self.job.start()

    def stop(self):
        self.rotation.stop()
        if self.job:
            self.status.set('Stopping upload…')
            self.job.cancel()
        else:
            self.status.set('Rotation stopped. Last uploaded animation stays on the panel.')
        self.countdown.set(BACKGROUND_HINT)
        self.set_controls()

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'log':
                    self.log(value)
                elif kind == 'stage':
                    self.status.set(value)
                elif kind == 'reel_ready':
                    token, result, error = value
                    if self.reel_window is None or token != self.reel_token:
                        continue
                    if error:
                        self.reel_info.set(error)
                    else:
                        self.reel_result = result
                        frames, _, rows = result
                        for row in rows:
                            self.reel_table.insert('', 'end', values=row)
                        reduced = any(source > kept for _, source, kept in rows)
                        self.reel_info.set(f'{len(rows)} scenes · {len(frames)} frames total' +
                                           (' · Frames reduced to fit; check the motion in the preview.' if reduced else ' · All source frames retained.'))
                        self.reel_send_button.configure(state='normal')
                        self.animate_reel()
                elif kind == 'preview':
                    token, result, error = value
                    if token != self.preview_token:
                        continue
                    if self.preview_after is not None:
                        self.root.after_cancel(self.preview_after)
                        self.preview_after = None
                    if error:
                        self.frames = []
                        self.canvas.delete('all')
                        self.file_info.set(error)
                    else:
                        self.frames, self.durations, size = result
                        self.preview_index = 0
                        self.file_info.set(f'{size[0]} × {size[1]} source · {len(self.frames)} frames · prepared at 96 × 16')
                        self.animate()
                elif kind == 'done':
                    self.job = None
                    self.progress.stop()
                    if value['cancelled']:
                        self.rotation.stop()
                        self.status.set('Upload stopped. Panel contents may be incomplete; send again to restore.')
                    elif value['success']:
                        if value.get('combined'):
                            self.status.set('Combined reel uploaded. Check all scenes on the panel.')
                        else:
                            self.status.set('Upload completed. Check playback on the panel.')
                        self.rotation.uploaded(time.monotonic(), self.settings.minutes)
                    elif self.rotation.running and value.get('connection_issue') and not value.get('combined'):
                        self.rotation.retry_after(time.monotonic(), PANEL_RETRY_SECONDS)
                        self.status.set('Display unavailable. Rotation is waiting to reconnect.')
                        self.log(f'Rotation paused; retrying the same animation after {PANEL_RETRY_SECONDS:g} seconds.')
                    else:
                        self.rotation.stop()
                        self.status.set('Upload failed. Rotation stopped.')
                        messagebox.showerror('Upload failed', value['detail'])
                    if not self.rotation.running:
                        self.countdown.set('The panel repeats the combined reel. You can Exit the app.'
                                           if value['success'] and value.get('combined') else BACKGROUND_HINT)
                    self.set_controls()
        except queue.Empty:
            pass
        self.root.after(100 if self.job else 500, self.poll)

    def tick(self):
        if self.rotation.running:
            index = self.rotation.due(time.monotonic(), len(self.settings.items))
            if index is not None and self.job is None:
                self.begin_upload(index)
            if self.rotation.deadline is not None:
                remaining = max(0, math.ceil(self.rotation.deadline - time.monotonic()))
                if self.rotation.waiting:
                    self.countdown.set(f'Waiting for display · Retry in {remaining // 60}:{remaining % 60:02d} · Stop cancels retries')
                else:
                    self.countdown.set(f'Playing {self.rotation.index + 1} of {len(self.settings.items)} · Next in {remaining // 60}:{remaining % 60:02d} · Keep this app open')
            elif self.job:
                self.countdown.set((f'Reconnecting · Pending animation {self.rotation.index + 1} of {len(self.settings.items)}'
                                    if self.rotation.waiting else
                                    f'Uploading {self.rotation.index + 1} of {len(self.settings.items)} · Rotation starts after upload completes'))
        self.root.after(1000, self.tick)

    def setup(self):
        if self.job or self.rotation.running:
            return
        win = tk.Toplevel(self.root)
        win.title('Panel setup')
        win.transient(self.root)
        win.grab_set()
        body = ttk.Frame(win, padding=20)
        body.pack(fill='both', expand=True)
        values = {name: tk.StringVar(value=getattr(self.settings, name)) for name in ('address', 'driver', 'python')}
        labels = [('Bluetooth address', 'address'), ('Verified driver folder', 'driver'), ('Python program', 'python')]
        for row, (label, name) in enumerate(labels):
            ttk.Label(body, text=label).grid(row=row * 2, column=0, sticky='w', pady=(7, 3))
            ttk.Entry(body, textvariable=values[name], width=70).grid(row=row * 2 + 1, column=0, sticky='ew')
            if name != 'address':
                def browse(key=name):
                    selected = filedialog.askdirectory(parent=win) if key == 'driver' else filedialog.askopenfilename(parent=win, filetypes=[('Python executable', '*.exe')])
                    if selected:
                        values[key].set(selected)
                ttk.Button(body, text='Browse…', command=browse).grid(row=row * 2 + 1, column=1, padx=(8, 0))
        ttk.Label(body, text='These defaults match the setup already tested with your panel.', font=('Segoe UI', 9)).grid(row=6, column=0, sticky='w', pady=12)
        def save():
            candidate = Settings(values['address'].get().strip(), values['driver'].get().strip(), values['python'].get().strip(), self.settings.minutes, self.settings.items)
            try:
                validate_setup(candidate)
            except (OSError, ValueError) as exc:
                messagebox.showerror('Check setup', str(exc), parent=win)
                return
            self.settings = candidate
            self.persist()
            win.destroy()
        ttk.Button(body, text='Save setup', command=save).grid(row=7, column=0, sticky='e')

    def close(self):
        if self.job and not messagebox.askyesno('Upload in progress', 'Stop the current upload and close?'):
            return
        self.rotation.stop()
        if self.job:
            self.job.cancel()
        try:
            self.settings.minutes = validate_interval(self.minutes.get())
        except ValueError:
            pass
        self.persist()
        self.root.destroy()


def main():
    try:
        if os.name == 'nt':
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    def report_error(error_type, error, tb):
        error_path = Path.home() / 'CoolLED' / 'uploader_error.log'
        try:
            error_path.parent.mkdir(parents=True, exist_ok=True)
            error_path.write_text(''.join(traceback.format_exception(error_type, error, tb)), encoding='utf-8')
            detail = f'{error}\n\nDetails saved to:\n{error_path}'
        except OSError:
            detail = str(error)
        messagebox.showerror('Uploader error', detail, parent=root)
    root.report_callback_exception = report_error
    Uploader(root)
    root.mainloop()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        details = traceback.format_exc()
        error_path = Path.home() / 'CoolLED' / 'uploader_error.log'
        try:
            error_path.parent.mkdir(parents=True, exist_ok=True)
            error_path.write_text(details, encoding='utf-8')
        except OSError:
            pass
        if os.name == 'nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, f'The uploader could not start.\n\nSee:\n{error_path}', 'CoolLED Uploader', 16)
        else:
            raise
