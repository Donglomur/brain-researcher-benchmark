"""New stream/isolation controls only; never read authentic packet or answers."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import route_binding as r

class FakeEngine:
    DOCKER=sys.executable
    DOCKER_ARGV=[sys.executable]
    COMMAND_ENV={}
    def __init__(self,path):
        self.OUT=path;self.EVENTS=[];self.END=time.monotonic()+10;self.WORK_END=self.END-1
    def save(self,name,value):
        body=value if isinstance(value,bytes) else json.dumps(value).encode()
        p=self.OUT/name
        with p.open('xb') as stream:stream.write(body)
        return {'path':str(p),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}

class Controls(unittest.TestCase):
    def run_stream(self,code,limit=100,timeout=1):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);engine=FakeEngine(p);destination=p/'submission.jsonl'
            error=None
            try:pin,event=r.stream_candidate(engine,['-I','-S','-c',code],timeout,destination,limit)
            except RuntimeError as caught:error=caught
            return error,destination.read_bytes(),engine.EVENTS

    def test_complete_stdout_and_stderr_are_separate(self):
        error,body,events=self.run_stream("import sys;sys.stdout.write('one\\ntwo\\n');sys.stderr.write('diagnostic')")
        self.assertIsNone(error);self.assertEqual(body,b'one\ntwo\n')
        self.assertEqual(events[0]['observed_EOF'],['stderr','stdout']);self.assertTrue(events[0]['reaped'])
        self.assertEqual(events[0]['received'],{'stdout':8,'stderr':10})

    def test_overflow_preserves_prefix_and_fails(self):
        error,body,events=self.run_stream("import sys;sys.stdout.write('x'*101)")
        self.assertIsNotNone(error);self.assertEqual(body,b'x'*100)
        self.assertFalse(events[0]['complete']);self.assertEqual(events[0]['received']['stdout'],101)

    def test_nonzero_exit_preserves_complete_stream(self):
        error,body,events=self.run_stream("import sys;sys.stdout.write('partial');sys.exit(7)")
        self.assertIsNotNone(error);self.assertEqual(body,b'partial')
        self.assertTrue(events[0]['complete']);self.assertEqual(events[0]['returncode'],7)

    def test_hanging_child_is_reaped_and_never_complete(self):
        error,body,events=self.run_stream("import time;time.sleep(10)",timeout=.1)
        self.assertIsNotNone(error);self.assertEqual(body,b'')
        self.assertTrue(events[0]['reaped']);self.assertFalse(events[0]['complete'])

    def test_candidate_mounts_never_include_write_or_owner_paths(self):
        request={'programs':{'A':{'path':'/safe/a'},'B':{'path':'/safe/b'}}}
        policy={'packet':{'path':'/safe/data'},'common_assistance':{'TASK.md':{'path':'/safe/task'}},
                'additional_B_assistance':{'category_matching.py':{'path':'/safe/code'},'LICENSE':{'path':'/safe/license'}}}
        a=r.candidate_mounts(request,policy,'A');b=r.candidate_mounts(request,policy,'B')
        self.assertTrue(all(not writable for _,_,writable in a+b))
        self.assertFalse(any(dst.startswith('/official') for _,dst,_ in a))
        self.assertEqual({dst for _,dst,_ in b}-{dst for _,dst,_ in a},{'/official/category_matching.py','/official/LICENSE'})
        self.assertFalse(any(dst.startswith(('/scoring','/submission','/output','/binding')) for _,dst,_ in a+b))

    def test_fresh_submission_never_overwrites(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);destination=p/'submission.jsonl';destination.write_bytes(b'prior')
            with self.assertRaises(FileExistsError):
                r.stream_candidate(FakeEngine(p),['-c',"print('new')"],1,destination,100)
            self.assertEqual(destination.read_bytes(),b'prior')

    def test_capture_publication_does_not_mask_original_overflow(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);engine=FakeEngine(p)
            def rejected_save(*args):raise OSError('invented receipt failure')
            engine.save=rejected_save
            with self.assertRaises(r.StreamFailure) as caught:
                r.stream_candidate(engine,['-c',"print('x'*101,end='')"],1,p/'submission.jsonl',100)
            detail=caught.exception.stream_failure_custody
            self.assertIn('stdout cap',detail['primary']['message'])
            self.assertEqual(detail['secondary'][0]['phase'],'capture_publication')
            self.assertEqual((p/'submission.jsonl').read_bytes(),b'x'*100)

    def test_pipe_and_selector_close_failures_preserve_overflow_and_receipts(self):
        original_popen=r.subprocess.Popen
        original_selector=r.selectors.DefaultSelector
        original_fsync=r.os.fsync
        fsync_calls=[]
        class ClosingPipe:
            def __init__(self,wrapped,name):self.wrapped=wrapped;self.name=name
            def __getattr__(self,name):return getattr(self.wrapped,name)
            def close(self):
                self.wrapped.close()
                raise OSError('invented '+self.name+' close failure')
        class ClosingSelector:
            def __init__(self):self.wrapped=original_selector()
            def __getattr__(self,name):return getattr(self.wrapped,name)
            def close(self):
                self.wrapped.close()
                raise OSError('invented selector close failure')
        def spawned(*args,**kwargs):
            child=original_popen(*args,**kwargs)
            child.stdout=ClosingPipe(child.stdout,'stdout')
            child.stderr=ClosingPipe(child.stderr,'stderr')
            return child
        def synced(fd):
            fsync_calls.append(fd);return original_fsync(fd)
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);engine=FakeEngine(p)
            with patch.object(r.subprocess,'Popen',spawned),patch.object(r.selectors,'DefaultSelector',ClosingSelector),patch.object(r.os,'fsync',synced):
                with self.assertRaises(r.StreamFailure) as caught:
                    r.stream_candidate(engine,['-c',"import sys,time;sys.stdout.write('x'*101);sys.stdout.flush();time.sleep(10)"],1,p/'submission.jsonl',100)
            detail=caught.exception.stream_failure_custody
            self.assertIn('stdout cap',detail['primary']['message'])
            self.assertEqual([row['phase'] for row in detail['secondary']],['stdout_pipe_close','stderr_pipe_close','selector_close'])
            self.assertEqual(len(fsync_calls),1)
            self.assertEqual((p/'submission.jsonl').read_bytes(),b'x'*100)
            self.assertTrue((p/'command-01.stderr').exists())
            self.assertTrue((p/'command-01.overflow').exists())
            self.assertTrue((p/'CALL-01.json').exists())
            self.assertTrue(engine.EVENTS[0]['reaped'])

if __name__=='__main__':unittest.main(verbosity=2)
