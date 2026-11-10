"""Installer integration checks without Bluetooth, network downloads or sudo."""
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import setup_player as setup


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.work = Path(self.temp.name)
        self.root = self.work / 'other user' / 'Cool LED'
        self.root.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def fixture_driver(self):
        source = self.work / 'upstream'
        (source / 'src/coolledx').mkdir(parents=True)
        (source / setup.CLIENT_PATH).write_bytes(b'write(data, response=expect_response,)\n')
        self.git('init', '-q', source)
        self.git('-C', source, 'add', '.')
        self.git('-C', source, '-c', 'user.name=Fixture', '-c',
                 'user.email=fixture@example.invalid', 'commit', '-qm', 'Fixture')
        revision = self.git('-C', source, 'rev-parse', 'HEAD').stdout.strip()
        return source, revision

    def git(self, *args):
        return subprocess.run(['git', *map(str, args)], check=True, capture_output=True, text=True)

    def test_address_validation(self):
        self.assertEqual(setup.address(' aa:bb:cc:dd:ee:ff '), 'AA:BB:CC:DD:EE:FF')
        for value in ('', 'aabbccddeeff', 'AA:BB:CC:DD:EE:FF\nunsafe', 'AA:BB:CC:DD:EE:GG'):
            with self.assertRaises(ValueError):
                setup.address(value)

    def test_driver_clone_pin_and_patch_are_repeatable(self):
        source, revision = self.fixture_driver()
        with patch.object(setup, 'DRIVER_URL', str(source)), patch.object(setup, 'REVISION', revision):
            setup.prepare_driver(self.root)
            client = self.root / 'driver' / setup.CLIENT_PATH
            self.assertEqual(client.read_bytes(), b'write(data, response=False,)\n')
            self.assertIn(b'response=expect_response,', client.with_suffix('.py.bak').read_bytes())
            setup.prepare_driver(self.root)
            client.write_text('user changes\n')
            with self.assertRaisesRegex(ValueError, 'other edits'):
                setup.prepare_driver(self.root)
            self.assertEqual(client.read_text(), 'user changes\n')
        with patch.object(setup, 'REVISION', '0' * 40):
            with self.assertRaisesRegex(ValueError, 'different revision'):
                setup.prepare_driver(self.root)

    def test_missing_and_saved_address_do_not_scan(self):
        with patch.object(sys.stdin, 'isatty', return_value=False):
            with self.assertRaisesRegex(ValueError, '--address'):
                setup.choose_address(Path('/unused'), self.root)
            setup.write_object(self.root / 'hardware.json', {'address': 'aa:bb:cc:dd:ee:ff'})
            self.assertEqual(setup.choose_address(Path('/unused'), self.root), 'AA:BB:CC:DD:EE:FF')
            self.assertEqual(setup.choose_address(Path('/unused'), self.root,
                                                  '11:22:33:44:55:66'), '11:22:33:44:55:66')

    def test_windows_git_line_endings_preserved_during_patch(self):
        source, revision = self.fixture_driver()
        self.git('clone', '-q', source, self.root / 'driver')
        client = self.root / 'driver' / setup.CLIENT_PATH
        client.write_bytes(b'write(data, response=expect_response,)\r\n')
        with patch.object(setup, 'REVISION', revision):
            setup.prepare_driver(self.root)
            setup.prepare_driver(self.root)
        self.assertEqual(client.read_bytes(), b'write(data, response=False,)\r\n')
        self.assertEqual(client.with_suffix('.py.bak').read_bytes(), b'write(data, response=expect_response,)\r\n')

    def test_interactive_selection_uses_the_selected_display(self):
        found = [{'name':'CoolLEDX-A','address':'AA:BB:CC:DD:EE:FF'},
                 {'name':'CoolLEDX-B','address':'11:22:33:44:55:66'}]
        result = subprocess.CompletedProcess([], 0, json.dumps(found), '')
        with patch.object(sys.stdin, 'isatty', return_value=True), \
             patch.object(subprocess, 'run', return_value=result), \
             patch('builtins.input', return_value='2'), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(setup.choose_address(Path('/unused'), self.root), '11:22:33:44:55:66')

    def test_settings_and_existing_animation_survive_windows_setup(self):
        original = {'minutes':17, 'items':[{'path':'D:/my clip.gif','timing':64,'fit':'Fill panel'}]}
        setup.write_object(self.root / 'uploader_settings.json', original)
        (self.root / 'animations').mkdir()
        sample = self.root / 'animations/CoolLED_RGB_Test.gif'
        sample.write_bytes(b'keep my file')
        setup.seed_files(self.root, True, 'AA:BB:CC:DD:EE:FF')
        saved = setup.read_object(self.root / 'uploader_settings.json')
        self.assertEqual(saved['items'], original['items'])
        self.assertEqual(saved['minutes'], 17)
        self.assertEqual(saved['driver'], str(self.root / 'driver'))
        self.assertEqual(saved['python'], str(self.root / '.venv/Scripts/python.exe'))
        self.assertEqual(sample.read_bytes(), b'keep my file')
        backup = next(self.root.glob('uploader_settings.json.before-*'))
        self.assertEqual(json.loads(backup.read_text()), original)

    def test_pi_settings_and_animation_files_are_not_replaced(self):
        config = self.root / 'pi_player_settings.json'
        config.write_text('{"enabled": true, "shuffle": true, "minutes": 17, "items": []}\n')
        before = config.read_bytes()
        setup.seed_files(self.root, False, 'AA:BB:CC:DD:EE:FF')
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(setup.read_object(self.root / 'hardware.json')['address'], 'AA:BB:CC:DD:EE:FF')

    def test_stage_keeps_previous_code_and_notice_files(self):
        (self.root / 'Player').mkdir()
        (self.root / 'Player/old.py').write_text('old code')
        with contextlib.redirect_stdout(io.StringIO()):
            setup.stage_player(self.root, False)
        self.assertTrue((self.root / 'Player/player.py').is_file())
        self.assertTrue((self.root / 'Player/NOTICE').is_file())
        self.assertEqual((self.root / 'Player/LICENSE').read_bytes(), (setup.SOURCE / 'LICENSE').read_bytes())
        self.assertEqual(len(list(self.root.glob('Player.before-*/old.py'))), 1)

    def test_stage_failure_restores_previous_application(self):
        (self.root / 'Player').mkdir()
        (self.root / 'Player/old.py').write_text('old code')
        rename = Path.rename
        def fail_staged(path, target):
            if path.parent.name.startswith('.player-'):
                raise OSError('simulated rename failure')
            return rename(path, target)
        with patch.object(Path, 'rename', fail_staged), self.assertRaises(OSError):
            setup.stage_player(self.root, False)
        self.assertEqual((self.root / 'Player/old.py').read_text(), 'old code')

    def test_service_units_use_actual_user_and_escape_paths(self):
        root = Path('/home/other user/LED %100 $cash "quoted"')
        units = setup.service_units(root, 'alex', '/usr/sbin/rfkill', '/usr/bin/bluetoothctl')
        text = units['coolled-player.service']
        self.assertIn('User=alex\n', text)
        self.assertNotIn('/home/pi/', text)
        self.assertIn('%%100', text)
        self.assertIn('$$cash', text)
        self.assertIn('\\"quoted\\"', text)
        with self.assertRaises(ValueError):
            setup.quote_unit('/unsafe\nExecStart=other')

    def test_malformed_settings_are_not_overwritten(self):
        path = self.root / 'uploader_settings.json'
        path.write_text('["not an object"]')
        with self.assertRaises(ValueError):
            setup.read_object(path)
        self.assertEqual(path.read_text(), '["not an object"]')

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux installer flow')
    def test_linux_setup_flow_without_network_sudo_or_bluetooth(self):
        source, revision = self.fixture_driver()
        original_run = setup.run
        pip_calls = []
        def controlled_run(args, **kwargs):
            if '-m' in args and 'pip' in args:
                pip_calls.append(args)
                return subprocess.CompletedProcess(args, 0)
            return original_run(args, **kwargs)
        class Environment:
            def create(self, env):
                (env / 'bin').mkdir(parents=True)
                (env / 'bin/python').symlink_to(sys.executable)
        with patch.object(setup, 'DRIVER_URL', str(source)), patch.object(setup, 'REVISION', revision), \
             patch.object(setup, 'run', controlled_run), patch.object(setup.venv, 'EnvBuilder', return_value=Environment()), \
             patch.object(os, 'geteuid', return_value=1000), contextlib.redirect_stdout(io.StringIO()):
            setup.main(['--root', str(self.root), '--address', 'AA:BB:CC:DD:EE:FF', '--no-service'])
        self.assertEqual(len(pip_calls), 1)
        self.assertTrue((self.root / 'Player/templates/index.html').is_file())
        self.assertTrue((self.root / 'animations/CoolLED_RGB_Test.gif').is_file())
        self.assertEqual(setup.read_object(self.root / 'hardware.json')['address'], 'AA:BB:CC:DD:EE:FF')
        self.assertEqual((self.root / 'Player/player.py').read_bytes(), (setup.SOURCE / 'pi/player.py').read_bytes())


if __name__ == '__main__':
    unittest.main()
