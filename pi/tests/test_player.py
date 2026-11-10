import io
import json
from pathlib import Path
import re
import random
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from player import Player, Result, DriverUpload, create_app, prepare_gif, describe_gif, connection_issue
from PIL import Image, GifImagePlugin


def gif(path, count=48, duplicate=False):
    frames=[]
    for i in range(count):
        im=Image.new('P',(96,16),0)
        im.putpalette([0,0,0,255,255,255]+[0]*762)
        im.putpixel((2 if duplicate else i,7),1)
        frames.append(im)
    with Path(path).open('wb') as file:
        for chunk in GifImagePlugin.getheader(frames[0], info={'loop':0})[0]:
            file.write(chunk)
        for frame in frames:
            for chunk in GifImagePlugin.getdata(frame,duration=120,disposal=2):
                file.write(chunk)
        file.write(b';')


def wait_for(condition, timeout=3):
    stop=time.monotonic()+timeout
    while time.monotonic()<stop:
        if condition(): return
        time.sleep(.005)
    raise AssertionError('Condition was not reached')


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        (self.root/'hardware.json').write_text(json.dumps({'address':'AA:BB:CC:DD:EE:FF'}))
        (self.root/'animations').mkdir()
        gif(self.root/'animations/A.gif')
        gif(self.root/'animations/B.gif')
        gif(self.root/'animations/Frame_Test_64.gif',64)
        self.players=[]

    def tearDown(self):
        for player in self.players:
            player.shutdown()
        self.temp.cleanup()

    def player(self, runner=None, **kwargs):
        p=Player(self.root, runner or (lambda *_:Result(success=True)), **kwargs)
        self.players.append(p)
        return p

    def configure(self,p,minutes=.001):
        data=p.snapshot()['config']
        data['minutes']=minutes
        p.set_config(data)

    def test_diagnostic_retained_but_not_selected(self):
        p=self.player()
        self.assertEqual([i['name'] for i in p.playlist()],['A.gif','B.gif'])
        self.assertEqual(len(p.config['items']),3)
        self.assertTrue((p.directory/'Frame_Test_64.gif').is_file())

    def test_full_frame_preservation_including_identical_frames(self):
        original=self.root/'identical.gif'
        gif(original,48,duplicate=True)
        prepared=self.root/'prepared.gif'
        prepare_gif(original,'Fill panel',prepared)
        with Image.open(prepared) as im:
            self.assertEqual(im.n_frames,48)
            self.assertEqual(im.size,(96,16))
            self.assertEqual(im.info['loop'],0)
            for f in range(48):
                im.seek(f)
                self.assertEqual(im.convert('RGB').getpixel((2,7)),(255,255,255))

    def test_all_fit_modes_work(self):
        for fit in ('Fill panel','Fit entire image','Stretch to panel'):
            target=self.root/'fit.gif'
            prepare_gif(self.root/'animations/A.gif',fit,target)
            self.assertEqual(describe_gif(target)['frames'],48)

    def test_retry_same_file_then_advance(self):
        calls=[]
        def run(item,*_):
            calls.append(item['name'])
            return Result(link_error=True) if len(calls)==1 else Result(success=True)
        p=self.player(run,retry_seconds=.025)
        self.configure(p)
        p.start()
        wait_for(lambda:len(calls)>=3)
        p.stop()
        self.assertEqual(calls[:3],['A.gif','A.gif','B.gif'])

    def test_interval_starts_after_completed_upload(self):
        calls=[]
        done=[]
        def run(item,*_):
            calls.append(time.monotonic())
            time.sleep(.04)
            done.append(time.monotonic())
            return Result(success=True)
        p=self.player(run)
        self.configure(p)
        p.start()
        wait_for(lambda:len(calls)>=2)
        p.stop()
        self.assertGreaterEqual(calls[1]-done[0],.055)

    def test_stop_cancels_wait_and_retries(self):
        calls=[]
        def run(item,*_):
            calls.append(item['name'])
            return Result(link_error=True)
        p=self.player(run,retry_seconds=.15)
        p.start()
        wait_for(lambda:p.snapshot()['retrying'])
        p.stop()
        time.sleep(.2)
        self.assertEqual(len(calls),1)
        self.assertFalse(p.snapshot()['running'])
        self.assertFalse(json.loads(p.config_path.read_text())['enabled'])

    def test_stop_cancels_active_task(self):
        entered=threading.Event()
        def run(item,log,stage,cancel,register):
            entered.set()
            cancel.wait(2)
            return Result(cancelled=cancel.is_set())
        p=self.player(run)
        p.start()
        self.assertTrue(entered.wait(1))
        p.stop()
        wait_for(lambda:not p.snapshot()['busy'])
        self.assertEqual(p.snapshot()['phase'],'Stopped')

    def test_content_error_stops_instead_of_looping(self):
        p=self.player(lambda *_:Result(detail='Invalid payload'))
        p.start()
        wait_for(lambda:p.snapshot()['phase']=='Upload failed')
        self.assertFalse(p.snapshot()['running'])
        self.assertFalse(json.loads(p.config_path.read_text())['enabled'])

    def test_boot_resume_and_stop_persistence(self):
        first=self.player()
        first.start()
        wait_for(lambda:first.snapshot()['last_sent']=='A.gif')
        first.shutdown()
        sent=[]
        def run(item,*_):
            sent.append(item['name'])
            return Result(success=True)
        second=self.player(run)
        wait_for(lambda:bool(sent))
        self.assertEqual(sent[0],'A.gif')
        second.stop()
        second.shutdown()
        third=self.player(run)
        self.assertFalse(third.snapshot()['running'])

    def test_manual_send_does_not_start_rotation(self):
        p=self.player()
        p.send_once('B.gif')
        wait_for(lambda:p.snapshot()['last_sent']=='B.gif')
        self.assertFalse(p.snapshot()['running'])
        self.assertFalse(p.snapshot()['config']['enabled'])

    def test_edit_blocked_while_running(self):
        p=self.player()
        p.start()
        with self.assertRaisesRegex(ValueError,'Stop rotation'):
            p.set_config(p.snapshot()['config'])

    def test_bad_interval_and_path_rejected(self):
        p=self.player()
        for value in (float('nan'),0,-1,2000):
            data=p.snapshot()['config'];data['minutes']=value
            with self.assertRaises(ValueError):p.set_config(data)
        with self.assertRaises(ValueError):p._safe_path('../secret.gif')

    def client(self,p):
        c=create_app(p).test_client()
        page=c.get('/')
        self.assertEqual(page.status_code,200)
        token=re.search(r'name="csrf-token" content="([^"]+)"',page.get_data(as_text=True))[1]
        return c,{'X-CSRF-Token':token}

    def test_api_csrf_and_escaped_state(self):
        p=self.player()
        c,h=self.client(p)
        self.assertEqual(c.post('/api/start',json={}).status_code,403)
        self.assertEqual(c.get('/api/state').status_code,200)
        self.assertEqual(c.post('/api/start',json={},headers=h).status_code,200)
        self.assertEqual(c.post('/api/stop',json={},headers=h).status_code,200)

    def test_invalid_upload_does_not_leave_partial_file(self):
        p=self.player();c,h=self.client(p)
        r=c.post('/api/upload',data={'file':(io.BytesIO(b'not a gif'),'New.gif')},headers=h)
        self.assertEqual(r.status_code,400)
        self.assertFalse((p.directory/'New.gif').exists())
        self.assertFalse(list(p.directory.glob('.incoming-*')))

    def test_upload_and_duplicate_protection(self):
        p=self.player();c,h=self.client(p)
        data=(p.directory/'A.gif').read_bytes()
        r=c.post('/api/upload',data={'file':(io.BytesIO(data),'New.gif')},headers=h)
        self.assertEqual(r.status_code,200)
        self.assertIn('New.gif',[i['name'] for i in p.config['items']])
        again=c.post('/api/upload',data={'file':(io.BytesIO(b'wrong'),'New.gif')},headers=h)
        self.assertEqual(again.status_code,400)
        self.assertEqual((p.directory/'New.gif').read_bytes(),data)

    def test_reorder_and_speed_saved(self):
        p=self.player();c,h=self.client(p)
        data=p.snapshot()['config']
        data['items'][0],data['items'][1]=data['items'][1],data['items'][0]
        data['items'][0]['timing']=64
        self.assertEqual(c.post('/api/settings',json=data,headers=h).status_code,200)
        self.assertEqual(p.playlist()[0]['name'],'B.gif')
        self.assertEqual(p.playlist()[0]['timing'],64)

    def test_link_error_classification(self):
        self.assertTrue(connection_issue(['TimeoutError']))
        self.assertTrue(connection_issue(['org.bluez.Error.NotReady']))
        self.assertFalse(connection_issue(['INFO - Device disconnected']))
        self.assertFalse(connection_issue(['Invalid payload; connection lost']))
        self.assertFalse(connection_issue(['ImportError: cannot import symbol']))

    def driver(self,script):
        repo=self.root/'driver'
        (repo/'src/coolledx').mkdir(parents=True,exist_ok=True)
        (repo/'utils').mkdir(exist_ok=True)
        (repo/'src/coolledx/client.py').write_text('response=False')
        (repo/'utils/tweak_sign.py').write_text(script)

    def test_real_child_process_success_requires_marker(self):
        self.driver("print('Sending animation command: animation.gif'); print('LED sign update completed successfully')")
        p=self.player()
        item=p.config['items'][0]
        logs=[]
        run=DriverUpload(self.root)
        result=run(item,logs.append,lambda _:None,threading.Event(),lambda _:None)
        self.assertTrue(result.success)
        self.driver("print('No success marker')")
        result=run(item,logs.append,lambda _:None,threading.Event(),lambda _:None)
        self.assertFalse(result.success)

    def test_driver_uses_configured_address(self):
        self.driver("import sys; assert sys.argv[sys.argv.index('-a')+1]=='AA:BB:CC:DD:EE:FF'; print('LED sign update completed successfully')")
        p=self.player()
        result=DriverUpload(self.root)(p.config['items'][0],lambda _:None,
                    lambda _:None,threading.Event(),lambda _:None)
        self.assertTrue(result.success)

    def test_missing_address_stops_without_a_bluetooth_attempt(self):
        (self.root/'hardware.json').unlink()
        p=self.player()
        result=DriverUpload(self.root)(p.config['items'][0],lambda _:None,
                    lambda _:None,threading.Event(),lambda _:None)
        self.assertFalse(result.success)
        self.assertFalse(result.link_error)
        self.assertIn('setup', result.detail)

    def test_stuck_child_is_bounded_and_retriable(self):
        self.driver('import time; time.sleep(30)')
        p=self.player()
        result=DriverUpload(self.root,timeout_seconds=.05)(p.config['items'][0],lambda _:None,
                    lambda _:None,threading.Event(),lambda _:None)
        self.assertTrue(result.link_error)
        self.assertFalse(result.success)

    def test_shuffle_plays_every_selected_file_once_per_round(self):
        for name in ('C.gif','D.gif','E.gif'):
            gif(self.root/'animations'/name)
        calls=[]
        def run(item,*_):
            calls.append(item['name'])
            return Result(success=True)
        p=self.player(run,rng=random.Random(17))
        data=p.snapshot()['config'];data.update(shuffle=True,minutes=.0001)
        p.set_config(data);p.start()
        wait_for(lambda:len(calls)>=15)
        p.stop()
        expected={'A.gif','B.gif','C.gif','D.gif','E.gif'}
        for offset in (0,5,10):
            self.assertEqual(set(calls[offset:offset+5]),expected)
            self.assertEqual(len(set(calls[offset:offset+5])),5)
        self.assertNotEqual(calls[4],calls[5])
        self.assertNotEqual(calls[9],calls[10])

    def test_shuffle_boundary_repeat_is_explicitly_avoided(self):
        class Reverse:
            def shuffle(self,items):items.reverse()
            def randrange(self,start,stop):return start
        p=self.player(rng=Reverse())
        data=p.snapshot()['config'];data['shuffle']=True;p.set_config(data)
        order=p._new_round(previous_name='B.gif')
        self.assertEqual([i['name'] for i in order],['A.gif','B.gif'])

    def test_shuffle_retry_keeps_same_pending_file(self):
        calls=[]
        def run(item,*_):
            calls.append(item['name'])
            return Result(link_error=True) if len(calls)==1 else Result(success=True)
        p=self.player(run,retry_seconds=.01,rng=random.Random(2))
        data=p.snapshot()['config'];data.update(shuffle=True,minutes=.0001)
        p.set_config(data);p.start()
        wait_for(lambda:len(calls)>=4)
        p.stop()
        self.assertEqual(calls[0],calls[1])
        self.assertNotEqual(calls[1],calls[2])
        self.assertNotEqual(calls[2],calls[3])

    def test_shuffle_single_file_is_supported(self):
        calls=[]
        def run(item,*_):
            calls.append(item['name']);return Result(success=True)
        p=self.player(run)
        data=p.snapshot()['config'];data.update(shuffle=True,minutes=.0001)
        for item in data['items']:item['selected']=item['name']=='A.gif'
        p.set_config(data);p.start()
        wait_for(lambda:len(calls)>=3)
        p.stop()
        self.assertEqual(calls[:3],['A.gif']*3)

    def test_shuffle_setting_saved_and_loaded(self):
        p=self.player();c,h=self.client(p)
        data=p.snapshot()['config'];data['shuffle']=True
        self.assertEqual(c.post('/api/settings',json=data,headers=h).status_code,200)
        p.shutdown()
        other=self.player()
        self.assertTrue(other.snapshot()['config']['shuffle'])

    def test_older_settings_default_to_sequential(self):
        p=self.player()
        data=p.snapshot()['config'];data.pop('shuffle')
        p.config_path.write_text(json.dumps(data));p.shutdown()
        other=self.player()
        self.assertFalse(other.snapshot()['config']['shuffle'])
        self.assertEqual([i['name'] for i in other._new_round()],['A.gif','B.gif'])


if __name__=='__main__':
    unittest.main(verbosity=2)
