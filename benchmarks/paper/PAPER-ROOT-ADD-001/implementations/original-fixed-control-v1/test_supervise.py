"""Generated supervisor controls: all launch/pipe/signal paths are simulated."""
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

PATH = Path(__file__).with_name('supervise.py')
spec = importlib.util.spec_from_file_location('fixed_control_supervisor_tested', PATH)
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)


class Stream:
    def __init__(self, fd): self.fd, self.closed = fd, False
    def fileno(self): return self.fd
    def close(self): self.closed = True


class FakeSelector:
    def __init__(self): self.rows, self.closed = {}, False
    def register(self, stream, event, data): self.rows[stream] = types.SimpleNamespace(fileobj=stream, data=data)
    def get_map(self): return self.rows
    def unregister(self, stream): del self.rows[stream]
    def select(self, timeout): return [(v, 1) for v in list(self.rows.values())]
    def close(self): self.closed = True


class Process:
    def __init__(self, mode, events):
        self.stdout, self.stderr = Stream(10), Stream(11)
        self.pid, self.returncode, self.mode, self.events, self.waits = 4401, None, mode, events, 0
    def wait(self, timeout):
        self.waits += 1; self.events.append(('wait', self.returncode))
        if self.mode == 'term_then_kill' and self.waits <= 2:
            raise S.subprocess.TimeoutExpired('simulated', timeout)
        self.returncode = 3 if self.mode == 'nonzero' else (-9 if self.mode == 'term_then_kill' else 0)
        return self.returncode
    def poll(self): raise AssertionError('poll is not a safe ownership observation')


class SupervisorTests(unittest.TestCase):
    def execute(self, root, *, mode='natural', chunks=None, prepare_error=None, selector_error=None):
        events=[]; proc=Process(mode,events); sel=FakeSelector(); reads=[]
        chunks = {10:[b'hello',b''], 11:[b'warning',b'']} if chunks is None else chunks
        def read(fd, count):
            reads.append((fd,count)); value=chunks[fd].pop(0)
            self.assertLessEqual(len(value),count)
            return value
        def killpg(pid, sig):
            self.assertEqual(pid,proc.pid); events.append(('signal',sig,proc.returncode))
            if sig==0: raise ProcessLookupError('simulated absent group')
            self.assertIsNone(proc.returncode,'never signal a reaped identity')
        proof={'protocol_whole_seconds':10,'verified_source_bytes_executed':True}
        with patch.object(S,'prepare_command',side_effect=prepare_error,return_value=(('not-executed',),proof)), \
             patch.object(S.subprocess,'Popen',return_value=proc) as popen, \
             patch.object(S.selectors,'DefaultSelector',return_value=sel), \
             patch.object(S.os,'set_blocking',return_value=None), \
             patch.object(S.os,'read',side_effect=read), \
             patch.object(S.os,'killpg',side_effect=killpg), \
             patch.object(S.signal,'signal',return_value=S.signal.SIG_DFL), \
             patch.object(S.signal,'getsignal',return_value=S.signal.SIG_DFL), \
             patch.object(S.threading,'active_count',return_value=1):
            if selector_error is not None:
                sel.select=lambda timeout: (_ for _ in ()).throw(selector_error)
            result=S.supervise(['simulated'],deadline_seconds=10,grace_seconds=2,
                receipt=str(root/'receipt.json'),log=str(root/'log.bin'))
            called=popen.call_count
            if called:
                args,kwargs=popen.call_args
                self.assertTrue(kwargs['close_fds']);self.assertTrue(kwargs['start_new_session'])
                self.assertEqual(kwargs['stdin'],S.subprocess.DEVNULL)
                self.assertNotIn('shell',kwargs);self.assertNotIn('preexec_fn',kwargs)
                self.assertEqual(kwargs['env'],S.ENVIRONMENT)
        saved=json.loads((root/'receipt.json').read_bytes())
        self.assertEqual(saved,result)
        self.assertLessEqual((root/'receipt.json').stat().st_size,S.MAX_RECEIPT_BYTES)
        self.assertLessEqual((root/'log.bin').stat().st_size,S.MAX_LOG_BYTES)
        return result,events,reads,called

    def test_natural_exit_preserves_separate_framed_streams_and_limits(self):
        with tempfile.TemporaryDirectory(dir=PATH.parent) as tmp:
            root=Path(tmp);result,events,reads,called=self.execute(root)
            self.assertEqual(result['status'],'succeeded');self.assertEqual(called,1)
            self.assertEqual((root/'log.bin').read_bytes(),b'O'+struct.pack('<I',5)+b'hello'+b'E'+struct.pack('<I',7)+b'warning')
            self.assertEqual(result['log']['observed_pipe_bytes'],{'stdout':5,'stderr':7})
            self.assertFalse(result['descendant_closure_verified'])
            self.assertEqual(events,[('wait',None),('signal',0,0)])

    def test_timeout_uses_term_then_kill_and_reaps_with_bounded_cleanup(self):
        with tempfile.TemporaryDirectory(dir=PATH.parent) as tmp:
            result,events,_,_=self.execute(Path(tmp),mode='term_then_kill')
            self.assertEqual(result['status'],'failed')
            self.assertTrue(result['cleanup']['term_sent']);self.assertTrue(result['cleanup']['kill_sent'])
            self.assertTrue(result['child_reaped']);self.assertTrue(result['driver_group_absent'])
            self.assertFalse(result['descendant_closure_verified'])
            self.assertEqual([e[1] for e in events if e[0]=='signal'],[S.signal.SIGTERM,S.signal.SIGKILL,0])

    def test_interrupt_preserves_failure_log_and_receipt(self):
        with tempfile.TemporaryDirectory(dir=PATH.parent) as tmp:
            result,events,_,_=self.execute(Path(tmp),selector_error=KeyboardInterrupt('simulated interruption'))
            self.assertEqual(result['status'],'interrupted')
            self.assertEqual(result['error_type'],'KeyboardInterrupt')
            self.assertTrue(result['child_reaped']);self.assertTrue(result['pipes_closed'])
            self.assertFalse(result['complete_driver_exit_zero'])

    def test_nonzero_natural_exit_is_not_success_and_is_never_killed_after_reap(self):
        with tempfile.TemporaryDirectory(dir=PATH.parent) as tmp:
            result,events,_,_=self.execute(Path(tmp),mode='nonzero')
            self.assertEqual(result['status'],'failed');self.assertEqual(result['exit_code'],3)
            self.assertFalse(any(e[0]=='signal' and e[1]!=0 for e in events))

    def test_authentication_failure_does_not_launch_and_retains_failure(self):
        with tempfile.TemporaryDirectory(dir=PATH.parent) as tmp:
            result,_,_,called=self.execute(Path(tmp),prepare_error=ValueError('bad exact source pin'))
            self.assertEqual(result['status'],'failed');self.assertEqual(called,0)
            self.assertEqual(result['log']['bytes'],0)

    def test_small_generated_stream_cap_refuses_before_unbounded_read(self):
        with tempfile.TemporaryDirectory(dir=PATH.parent) as tmp,patch.object(S,'MAX_STREAM_BYTES',8):
            result,_,reads,_=self.execute(Path(tmp),chunks={10:[b'123456789'],11:[b'']})
            self.assertEqual(result['status'],'failed')
            self.assertEqual(reads,[(10,9)])
            self.assertEqual(result['log']['observed_pipe_bytes']['stdout'],9)
            self.assertEqual(result['log']['retained_pipe_bytes']['stdout'],8)
            self.assertEqual(result['log']['discarded_overflow_bytes'],1)

    def test_total_log_cap_counts_record_headers(self):
        stream=io.BytesIO();log=S.Log(stream)
        with patch.object(S,'MAX_LOG_BYTES',12):
            allowed=log.allowance('stdout');self.assertEqual(allowed,7)
            with self.assertRaisesRegex(ValueError,'overflow'):log.consume('stdout',b'12345678',allowed)
        self.assertEqual(log.bytes,12);self.assertEqual(len(stream.getvalue()),12)
        self.assertEqual(log.discarded,1)

    def test_existing_output_refuses_overwrite_and_deadline_caps_precede_artifacts(self):
        with tempfile.TemporaryDirectory(dir=PATH.parent) as tmp:
            root=Path(tmp);path=root/'kept';path.write_bytes(b'keep')
            with self.assertRaises(FileExistsError):S.fresh_file(str(path))
            self.assertEqual(path.read_bytes(),b'keep')
            for seconds,grace in ((601,5),(600,6),(0,5)):
                with self.assertRaises(ValueError):S.supervise([],deadline_seconds=seconds,grace_seconds=grace,
                    receipt=str(root/'not-created'),log=str(root/'also-not-created'))
            self.assertFalse((root/'not-created').exists())

    def test_command_rejects_arbitrary_programme_flags_and_missing_supervisor_pin(self):
        py=str(Path(sys.executable).resolve())
        argv=[py,'-I','-B',str(S.HERE/'fixed_control.py'),'--protocol','/p','--protocol-sha256','1'*64,
            '--admission','/a','--admission-sha256','2'*64]
        for wrong in (['sh'],[py,'-c','print(1)'],argv[:3]+['/wrong.py']+argv[4:]):
            with self.assertRaises(ValueError):S.prepare_command(wrong)
        p={'schema':'language-selected-fixed-control-protocol/v1','activity':'trusted_fixed_time_only_programme_pipeline_control',
           'whole_seconds':10,'source_pins':{'fixed_control.py':'3'*64}}
        with patch.object(S,'read_verified',side_effect=[S.encoded(p),S.encoded({})]):
            with self.assertRaisesRegex(ValueError,'pins driver and this supervisor'):S.prepare_command(argv)

    def test_exact_source_wrapper_and_runtime_bindings_without_executing_it(self):
        py=str(Path(sys.executable).resolve());source=b'print("never executed")\n';own=b'own source'
        runtime={'path':py,'bytes':12,'sha256':'4'*64,'version':sys.version.split()[0]}
        config={'python':runtime}
        p={'schema':'language-selected-fixed-control-protocol/v1','activity':'trusted_fixed_time_only_programme_pipeline_control',
            'whole_seconds':10,'provider_config':config,'source_pins':{'fixed_control.py':S.sha(source),'supervise.py':S.sha(own)}}
        a={'schema':'language-fixed-control-admission/v1','protocol_sha256':S.sha(S.encoded(p)),
           'config_sha256':S.sha(S.encoded(config)),'admitted_until_unix':int(time.time())+1000}
        argv=[py,'-I','-B',str(S.HERE/'fixed_control.py'),'--protocol','/p','--protocol-sha256',S.sha(S.encoded(p)),
            '--admission','/a','--admission-sha256',S.sha(S.encoded(a))]
        with patch.object(S,'read_verified',side_effect=[S.encoded(p),S.encoded(a),own,source,12]) as read:
            command,proof=S.prepare_command(argv)
        self.assertEqual(command[:4],(py,'-I','-B','-c'))
        self.assertIn(repr(source),command[4]);self.assertIn('__file__=',command[4])
        self.assertEqual(proof['driver_sha256'],S.sha(source))
        self.assertEqual(proof['supervisor_sha256'],S.sha(own))
        self.assertTrue(proof['verified_source_bytes_executed']);self.assertEqual(read.call_count,5)


if __name__=='__main__': unittest.main(verbosity=2)
