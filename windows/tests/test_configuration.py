import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from CoolLED_Uploader import Settings, data_root, load_settings, validate_setup


class ConfigurationTests(unittest.TestCase):
    def test_configured_root_and_driver_are_used_without_personal_defaults(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'COOLLED_ROOT':temp}):
            root = Path(temp)
            (root/'hardware.json').write_text(json.dumps({'address':'AA:BB:CC:DD:EE:FF'}))
            self.assertEqual(data_root(), root.resolve())
            settings = Settings.defaults()
            self.assertEqual(settings.address, 'AA:BB:CC:DD:EE:FF')
            self.assertEqual(Path(settings.driver), root/'driver')
            self.assertEqual(Path(settings.python), root/'.venv/Scripts/python.exe')

    def test_existing_playlist_and_paths_are_retained(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'settings.json'
            saved = {'address':'AA:BB:CC:DD:EE:FF','driver':'D:/my driver','python':'D:/env/python.exe',
                     'minutes':7,'items':[{'path':'D:/animation.gif','timing':64,'fit':'Fit entire image'}]}
            path.write_text(json.dumps(saved))
            settings, warning = load_settings(path)
            self.assertEqual(warning, '')
            self.assertEqual(settings.driver, saved['driver'])
            self.assertEqual(settings.python, saved['python'])
            self.assertEqual(settings.minutes, 7)
            self.assertEqual(settings.items[0].path, 'D:/animation.gif')
            self.assertEqual(settings.items[0].timing, 64)

    def test_unconfigured_installation_never_targets_a_personal_sign(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = Settings.defaults(Path(temp))
            self.assertEqual(settings.address, '')
            with self.assertRaisesRegex(ValueError, 'Bluetooth address'):
                validate_setup(settings)


if __name__ == '__main__':
    unittest.main()
