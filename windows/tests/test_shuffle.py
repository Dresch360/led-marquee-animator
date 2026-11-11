import json
import os
from pathlib import Path
import random
import shutil
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import CoolLED_Uploader as desktop
from CoolLED_Uploader import Item, Rotation, Settings, load_settings, save_settings


class ShuffleTests(unittest.TestCase):
    def test_each_file_once_per_round_and_no_boundary_repeat(self):
        rotation = Rotation(rng=random.Random(23))
        rotation.start(length=5, shuffle=True)
        played = [rotation.index]
        for _ in range(29):
            rotation.uploaded(0, 1)
            played.append(rotation.due(60, 5))
        for offset in range(0, 30, 5):
            self.assertEqual(set(played[offset:offset+5]), set(range(5)))
        for boundary in range(5, 30, 5):
            self.assertNotEqual(played[boundary-1], played[boundary])

    def test_boundary_repeat_is_swapped_when_rng_picks_it(self):
        class Reverse:
            def shuffle(self, items): items.reverse()
            def randrange(self, start, stop): return start
        rotation = Rotation(rng=Reverse())
        self.assertEqual(rotation._round(3, previous=2), [1, 2, 0])

    def test_failed_upload_retries_same_item_without_consuming_round(self):
        rotation = Rotation(rng=random.Random(7))
        rotation.start(length=4, shuffle=True)
        pending, order = rotation.index, list(rotation.order)
        for now in (0, 30, 60):
            rotation.retry_after(now)
            self.assertIsNone(rotation.due(now+29, 4))
            self.assertEqual(rotation.due(now+30, 4), pending)
            self.assertEqual(rotation.position, 0)
            self.assertEqual(rotation.order, order)
        rotation.uploaded(90, 1)
        self.assertIsNone(rotation.due(149, 4))
        self.assertEqual(rotation.due(150, 4), order[1])

    def test_sequential_order_starts_at_selected_file(self):
        rotation = Rotation()
        rotation.start(2, length=4)
        played = [rotation.index]
        for _ in range(4):
            rotation.uploaded(0, 1)
            played.append(rotation.due(60, 4))
        self.assertEqual(played, [2, 3, 0, 1, 2])

    def test_stop_cancels_retries_and_restart_starts_new_round(self):
        rotation = Rotation(rng=random.Random(8))
        rotation.start(length=3, shuffle=True)
        rotation.retry_after(0)
        rotation.stop()
        self.assertIsNone(rotation.due(100, 3))
        rotation.start(length=3, shuffle=True)
        self.assertEqual(rotation.position, 0)
        self.assertIsNone(rotation.deadline)
        self.assertEqual(set(rotation.order), {0, 1, 2})

    def test_one_file_is_safe_and_empty_playlist_rejected(self):
        rotation = Rotation()
        rotation.start(length=1, shuffle=True)
        for _ in range(3):
            rotation.uploaded(0, 1)
            self.assertEqual(rotation.due(60, 1), 0)
        with self.assertRaises(ValueError):
            rotation.start(length=0, shuffle=True)

    def test_shuffle_saved_without_reordering_playlist(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'settings.json'
            items = [Item('B.gif', 64), Item('A.gif', 256)]
            settings = Settings('AA:BB:CC:DD:EE:FF','driver','python',items=items,shuffle=True)
            save_settings(path, settings)
            loaded, warning = load_settings(path)
            self.assertEqual(warning, '')
            self.assertTrue(loaded.shuffle)
            self.assertEqual([item.path for item in loaded.items], ['B.gif', 'A.gif'])
            self.assertEqual([item.timing for item in loaded.items], [64, 256])
            self.assertEqual(json.loads(path.read_text())['shuffle'], True)

    def test_old_settings_keep_sequential_default(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'settings.json'
            path.write_text(json.dumps({'minutes':2,'items':[]}))
            settings, warning = load_settings(path)
            self.assertEqual(warning, '')
            self.assertFalse(settings.shuffle)


@unittest.skipUnless(os.environ.get('DISPLAY') or sys.platform == 'win32', 'Needs a graphical display')
class ShuffleWindowTests(unittest.TestCase):
    def test_checkbox_saves_survives_setup_and_locks_during_playback(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            driver=folder/'driver'
            (driver/'utils').mkdir(parents=True)
            (driver/'src/coolledx').mkdir(parents=True)
            (driver/'utils/tweak_sign.py').write_text('')
            (driver/'src/coolledx/client.py').write_text('response=False')
            (driver/'src/coolledx/commands.py').write_text('def create_command(): pass')
            source=Path(desktop.__file__).parent/'animations/CoolLED_RGB_Test.gif'
            items=[]
            for name in ('A.gif','B.gif'):
                target=folder/name
                shutil.copy2(source,target)
                items.append(Item(str(target)))
            config=folder/'settings.json'
            save_settings(config,Settings('AA:BB:CC:DD:EE:FF',str(driver),sys.executable,items=items))
            window=tk.Tk()
            errors=[]
            window.report_callback_exception=lambda *args:errors.append(args)
            calls=[]
            class HoldUpload:
                def __init__(self,settings,item,emit,**kwargs):
                    self.emit=emit
                    calls.append(item.path)
                def start(self): pass
                def cancel(self):
                    self.emit('done',{'success':False,'cancelled':True})
            try:
                app=desktop.Uploader(window,config_path=config)
                window.update()
                self.assertTrue(app.shuffle_box.winfo_ismapped())
                self.assertLess(app.shuffle_box.winfo_rooty()+app.shuffle_box.winfo_height(),
                                window.winfo_rooty()+window.winfo_height())
                app.shuffle_box.invoke()
                self.assertTrue(app.settings.shuffle)
                self.assertTrue(load_settings(config)[0].shuffle)
                app.setup_button.invoke()
                window.update()
                def descendants(widget):
                    for child in widget.winfo_children():
                        yield child
                        yield from descendants(child)
                save=next(widget for widget in descendants(window)
                          if isinstance(widget,desktop.ttk.Button) and widget.cget('text')=='Save setup')
                save.invoke()
                self.assertTrue(app.settings.shuffle)
                with patch.object(desktop,'UploadJob',HoldUpload):
                    app.start_button.invoke()
                    self.assertTrue(app.rotation.shuffle)
                    self.assertIn('disabled',app.shuffle_box.state())
                    app.events.put(('done',{'success':False,'cancelled':False,'combined':False,
                                             'connection_issue':True,'detail':'Fixture disconnection'}))
                    app.poll()
                    retry=app.rotation.due(app.rotation.deadline,len(items))
                    app.begin_upload(retry)
                    self.assertEqual(calls[0],calls[1])
                    app.stop_button.invoke()
                    app.poll()
                    self.assertFalse(app.rotation.running)
                    self.assertNotIn('disabled',app.shuffle_box.state())
                    self.assertTrue(load_settings(config)[0].shuffle)
                self.assertEqual(errors,[])
            finally:
                for token in window.tk.call('after','info'):
                    window.after_cancel(token)
                window.destroy()


if __name__ == '__main__':
    unittest.main()
