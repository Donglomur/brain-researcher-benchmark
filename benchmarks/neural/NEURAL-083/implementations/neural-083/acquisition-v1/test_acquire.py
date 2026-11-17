"""Generated interface controls only: no network, original MAT or scientific import."""
import hashlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location('n083_acquisition_under_test', HERE/'acquire.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def row(body=b'generated-neural083-input', person=1, session=1):
    path = f'session{session}/s{person}/sess{session:02d}_subj{person:02d}_EEG_MI.mat'
    return dict(person=person, session=session, path=path, bytes=len(body),
                url=a.BASE+path, publisher_md5=hashlib.md5(body).hexdigest())


class Response:
    def __init__(self, body, *, status=200, pairs=None, interruption=None):
        self.body = io.BytesIO(body)
        self.status = status
        self.pairs = pairs if pairs is not None else [('Content-Length', str(len(body)))]
        self.interruption = interruption
        self.reads = []
        self.closed = False

    def getheaders(self):
        return self.pairs

    def read(self, maximum):
        self.reads.append(maximum)
        if self.interruption is not None:
            value, self.interruption = self.interruption, None
            raise value
        return self.body.read(maximum)

    def close(self):
        self.closed = True


class Connector:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.closed = 0

    def __call__(self, host, timeout):
        owner = self
        response = next(self.responses)
        class Connection:
            def request(self, method, path, headers):
                owner.calls.append((host, timeout, method, path, headers))
            def getresponse(self):
                return response
            def close(self):
                owner.closed += 1
        return Connection()


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='n083-invented-')
        # macOS exposes its temporary root through /var -> /private/var. Resolve
        # this newly owned generated fixture; production still refuses aliases.
        self.root = Path(self.temp.name).resolve()
        self.output = a.Output(str(self.root/'output'))
        self.limits = dict(request_seconds=10, socket_seconds=1, whole_seconds=100)

    def tearDown(self):
        self.output.close()
        self.temp.cleanup()

    def fetch(self, selected, response, ops=None):
        if ops:
            self.output.ops = ops
        connector = Connector([response])
        result = a.fetch(selected, self.output, 1, self.limits, a.time.monotonic()+100,
                         connector=connector)
        return result, connector

    def receipt(self):
        return json.loads((self.output.path/'receipts/001.json').read_text())

    def test_full_pinned_roster(self):
        selected = a.roster(str(HERE/'publisher_roster.json'))
        self.assertEqual(len(selected['files']), 108)
        self.assertEqual(sum(r['bytes'] for r in selected['files']), a.TOTAL_BYTES)
        self.assertEqual(selected['files'][50]['path'], 'session1/s26/sess01_subj26_EEG_MI.mat')

    def test_success_short_writes_hash_actual_bytes_and_close(self):
        body = b'abcdefghijk'*7000
        operations = a.Ops()
        operations.write = lambda fd, view: os.write(fd, view[:37])
        response = Response(body)
        (receipt, _), connector = self.fetch(row(body), response, operations)
        self.assertEqual(receipt['status'], 'DURABLE_COMPLETE')
        self.assertEqual(receipt['confirmed_write_sha256'], hashlib.sha256(body).hexdigest())
        self.assertEqual(receipt['written_bytes'], len(body))
        self.assertEqual((self.output.path/row(body)['path']).read_bytes(), body)
        self.assertFalse((self.output.path/(row(body)['path']+'.partial')).exists())
        self.assertTrue(response.closed)
        self.assertEqual(connector.closed, 1)
        self.assertLessEqual(max(response.reads), a.CHUNK)
        self.assertEqual(receipt['publication']['nlink'], 1)

    def test_corruption_preserves_partial_no_success(self):
        selected = row(b'correct')
        with self.assertRaises(a.Refused):
            self.fetch(selected, Response(b'corrupt'))
        self.assertEqual(self.receipt()['status'], 'FAILED')
        self.assertFalse((self.output.path/selected['path']).exists())
        self.assertEqual((self.output.path/(selected['path']+'.partial')).read_bytes(), b'corrupt')

    def test_truncated_body_preserves_prefix(self):
        selected = row(b'complete')
        with self.assertRaises(a.Refused):
            self.fetch(selected, Response(b'co', pairs=[('Content-Length','8')]))
        self.assertEqual(self.receipt()['written_bytes'], 2)
        self.assertEqual((self.output.path/(selected['path']+'.partial')).read_bytes(), b'co')

    def test_incomplete_read_partial_is_written_before_failure(self):
        selected = row(b'complete')
        response = Response(b'', pairs=[('Content-Length','8')],
                            interruption=http.client.IncompleteRead(b'com',5))
        with self.assertRaises(a.Refused):
            self.fetch(selected, response)
        self.assertEqual(self.receipt()['written_bytes'], 3)
        self.assertEqual((self.output.path/(selected['path']+'.partial')).read_bytes(), b'com')

    def test_keyboard_interrupt_preserves_partial_and_failure(self):
        body = b'x'*(a.CHUNK+10)
        response = Response(body)
        original = response.read
        def read(n):
            if response.body.tell():
                raise KeyboardInterrupt('generated interruption')
            return original(n)
        response.read = read
        with self.assertRaises(a.Refused):
            self.fetch(row(body), response)
        self.assertEqual(self.receipt()['written_bytes'], a.CHUNK)
        self.assertEqual(self.receipt()['status'], 'FAILED')

    def test_partial_write_failure_hashes_only_confirmed_prefix(self):
        body = b'0123456789'
        operations = a.Ops()
        calls = [0]
        def write(fd, view):
            calls[0] += 1
            if calls[0] == 1:
                return os.write(fd, view[:4])
            if calls[0] == 2:
                raise OSError('generated disk failure')
            return os.write(fd, view)
        operations.write = write
        with self.assertRaises(a.Refused):
            self.fetch(row(body), Response(body), operations)
        receipt = self.receipt()
        self.assertEqual(receipt['received_bytes'], 10)
        self.assertEqual(receipt['written_bytes'], 4)
        self.assertEqual(receipt['confirmed_write_sha256'], hashlib.sha256(body[:4]).hexdigest())
        self.assertEqual((self.output.path/(row(body)['path']+'.partial')).read_bytes(), body[:4])

    def test_zero_write_refused(self):
        operations = a.Ops()
        calls = [0]
        def write(fd, view):
            calls[0] += 1
            return 0 if calls[0] == 1 else os.write(fd, view)
        operations.write = write
        with self.assertRaises(a.Refused):
            self.fetch(row(), Response(b'generated-neural083-input'), operations)
        self.assertEqual(self.receipt()['written_bytes'], 0)

    def test_redirect_rejected_without_body_or_second_request(self):
        response = Response(b'ignored', status=302, pairs=[('Location','https://evil.invalid/')])
        connector = Connector([response])
        with self.assertRaises(a.Refused):
            a.fetch(row(), self.output, 1, self.limits, a.time.monotonic()+100, connector=connector)
        self.assertEqual(len(connector.calls), 1)
        self.assertEqual(response.reads, [])

    def test_duplicate_length_rejected_before_body(self):
        response = Response(b'x', pairs=[('Content-Length','1'),('Content-Length','1')])
        with self.assertRaises(a.Refused):
            self.fetch(row(b'x'), response)
        self.assertEqual(response.reads, [])

    def test_chunked_encoding_rejected_before_body(self):
        response = Response(b'x', pairs=[('Content-Length','1'),('Transfer-Encoding','chunked')])
        with self.assertRaises(a.Refused):
            self.fetch(row(b'x'), response)
        self.assertEqual(response.reads, [])

    def test_compressed_encoding_rejected_before_body(self):
        response = Response(b'x', pairs=[('Content-Length','1'),('Content-Encoding','gzip')])
        with self.assertRaises(a.Refused):
            self.fetch(row(b'x'), response)
        self.assertEqual(response.reads, [])

    def test_roster_pin_rejects_tampered_metadata(self):
        p = self.root/'modified-roster.json'
        body = (HERE/'publisher_roster.json').read_bytes()
        p.write_bytes(body.replace(b'"person": 1,', b'"person": 9,', 1))
        with self.assertRaises(a.Refused):
            a.roster(str(p))

    def test_oversized_connector_block_rejected(self):
        response = Response(b'x')
        response.read = lambda n: b'xx'
        with self.assertRaises(a.Refused):
            self.fetch(row(b'x'), response)
        self.assertEqual(self.receipt()['written_bytes'], 0)
        self.assertEqual(self.receipt()['received_bytes'], 2)

    def test_existing_destination_not_clobbered(self):
        selected = row()
        fd = self.output.subdir(str(Path(selected['path']).parent))
        os.close(fd)
        target = self.output.path/selected['path']
        target.write_bytes(b'existing')
        with self.assertRaises(a.Refused):
            self.fetch(selected, Response(b'generated-neural083-input'))
        self.assertEqual(target.read_bytes(), b'existing')
        self.assertTrue(Path(str(target)+'.partial').exists())

    def test_file_fsync_failure_never_successful_receipt(self):
        body = b'xyz'
        operations = a.Ops()
        def fsync(fd):
            st = os.fstat(fd)
            if a.stat.S_ISREG(st.st_mode) and st.st_size == len(body):
                raise OSError('generated fsync failure')
            return os.fsync(fd)
        operations.fsync = fsync
        with self.assertRaises(a.Refused):
            self.fetch(row(body), Response(body), operations)
        self.assertEqual(self.receipt()['status'], 'FAILED')
        self.assertFalse((self.output.path/row(body)['path']).exists())

    def test_publication_directory_fsync_failure_never_success(self):
        operations = a.Ops()
        linked = [False]
        def link(*args, **kw):
            value = os.link(*args, **kw)
            linked[0] = True
            return value
        def fsync(fd):
            if linked[0] and a.stat.S_ISDIR(os.fstat(fd).st_mode):
                linked[0] = False
                raise OSError('generated directory fsync failure')
            return os.fsync(fd)
        operations.link, operations.fsync = link, fsync
        with self.assertRaises(a.Refused):
            self.fetch(row(), Response(b'generated-neural083-input'), operations)
        self.assertEqual(self.receipt()['status'], 'FAILED')
        self.assertTrue((self.output.path/(row()['path']+'.partial')).exists())

    def test_symlink_parent_refused(self):
        (self.root/'alias').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            a.Output(str(self.root/'alias/escape'))
        self.assertFalse((self.root/'escape').exists())

    def test_existing_output_root_refused(self):
        with self.assertRaises(FileExistsError):
            a.Output(str(self.output.path))

    def test_path_traversal_refused(self):
        selected = row()
        selected['path'] = '../escape.mat'
        selected['url'] = a.BASE+selected['path']
        with self.assertRaises(a.Refused):
            self.fetch(selected, Response(b'generated-neural083-input'))
        self.assertFalse((self.root/'escape.mat').exists())

    def test_wrong_origin_refused(self):
        selected = row()
        selected['url'] = 'https://evil.invalid/a'
        with self.assertRaises(a.Refused):
            self.fetch(selected, Response(b'generated-neural083-input'))

    def test_expired_deadline_never_opens_network(self):
        connector = Connector([])
        with self.assertRaises(a.Refused):
            a.fetch(row(), self.output, 1, self.limits, 0, connector=connector)
        self.assertEqual(connector.calls, [])

    def test_full108_generated_completion(self):
        bodies = [f'invented-{p}-{s}'.encode() for p in range(1,55) for s in (1,2)]
        rows = [row(b,p,s) for b,(p,s) in zip(bodies, ((p,s) for p in range(1,55) for s in (1,2)))]
        a._acquire_rows(rows, self.output, self.limits, connector=Connector([Response(b) for b in bodies]))
        manifest = json.loads((self.output.path/'generated-sources.json').read_text())
        complete = json.loads((self.output.path/'COMPLETE.json').read_text())
        self.assertEqual(len(manifest['files']), 108)
        self.assertEqual(complete['records'], 108)
        self.assertFalse(complete['scientific_qualified'])
        self.assertEqual(complete['status'], 'GENERATED_CONTROL_ONLY')
        self.assertIsNone(complete['roster'])
        self.assertFalse((self.output.path/'verified-sources.json').exists())
        self.assertEqual([x['sha256'] for x in manifest['files']],
                         [hashlib.sha256(b).hexdigest() for b in bodies])

    def test_missing108_refused_before_transport(self):
        connector = Connector([])
        with self.assertRaises(a.Refused):
            a.acquire([row()], self.output, self.limits, connector=connector)
        self.assertEqual(connector.calls, [])

    def test_late_failure_never_emits_full_manifest(self):
        rows = [row(b'x',p,s) for p in range(1,55) for s in (1,2)]
        responses = [Response(b'x') for _ in range(107)] + [Response(b'bad',status=500)]
        with self.assertRaises(a.Refused):
            a._acquire_rows(rows, self.output, self.limits, connector=Connector(responses))
        self.assertFalse((self.output.path/'verified-sources.json').exists())
        self.assertFalse((self.output.path/'COMPLETE.json').exists())
        self.assertEqual(json.loads((self.output.path/'FAILED.json').read_text())['completed_objects'],107)

    def test_invented108_cannot_enter_publisher_route(self):
        rows = [row(b'x',p,s) for p in range(1,55) for s in (1,2)]
        connector = Connector([])
        with self.assertRaises(a.Refused):
            a.acquire(rows, self.output, self.limits, connector=connector)
        self.assertEqual(connector.calls, [])
        self.assertFalse((self.output.path/'verified-sources.json').exists())

    def test_inherited_limits_never_raised(self):
        unlimited = a.resource.RLIM_INFINITY
        cases = [(5,unlimited,3,5,None),(5,10,0,5,100),
                 (unlimited,unlimited,0,20,100),(25,30,0,20,100)]
        for soft,hard,timer,expected_cpu,expected_wall in cases:
            with mock.patch.object(a.resource,'getrlimit',return_value=(soft,hard)), \
                 mock.patch.object(a.resource,'setrlimit') as cpu, \
                 mock.patch.object(a.signal,'signal'), \
                 mock.patch.object(a.time,'monotonic',return_value=0), \
                 mock.patch.object(a.signal,'getitimer',return_value=(timer,0)), \
                 mock.patch.object(a.signal,'setitimer') as wall:
                a.install_limits(20,100)
                cpu.assert_called_once_with(a.resource.RLIMIT_CPU,(expected_cpu,hard))
                if expected_wall is None:
                    wall.assert_not_called()
                else:
                    wall.assert_called_once_with(a.signal.ITIMER_REAL,expected_wall)

    def test_replaced_directory_closes_new_traversal_descriptor(self):
        fd = self.output.subdir('session1/s1')
        os.close(fd)
        (self.output.path/'session1/s1').rename(self.output.path/'session1/old')
        (self.output.path/'session1/s1').mkdir()
        real_open, real_close = os.open, os.close
        live_opened = set()
        def opened_fd(*args, **kwargs):
            fd = real_open(*args, **kwargs)
            live_opened.add(fd)
            return fd
        def closed_fd(fd):
            live_opened.discard(fd)
            return real_close(fd)
        with mock.patch.object(a.os,'open',side_effect=opened_fd), \
             mock.patch.object(a.os,'close',side_effect=closed_fd):
            with self.assertRaises(a.Refused):
                self.output.subdir('session1/s1')
        self.assertEqual(live_opened, set())

    def test_trailing_sentinel_charged_without_written_digest(self):
        body = b'abc'
        response = Response(body+b'Z', pairs=[('Content-Length','3')])
        with self.assertRaises(a.Refused):
            self.fetch(row(body),response)
        receipt = self.receipt()
        self.assertEqual(receipt['status'],'FAILED')
        self.assertEqual(receipt['received_bytes'],4)
        self.assertEqual(receipt['written_bytes'],3)
        self.assertEqual(receipt['eof_probe_bytes'],1)
        self.assertEqual(receipt['confirmed_write_sha256'],hashlib.sha256(body).hexdigest())
        self.assertEqual(receipt['confirmed_write_md5'],hashlib.md5(body).hexdigest())
        self.assertEqual((self.output.path/(row(body)['path']+'.partial')).read_bytes(),body)
        self.assertFalse((self.output.path/row(body)['path']).exists())

    def test_elapsed_setup_subtracted_before_timer_arm(self):
        with mock.patch.object(a.resource,'getrlimit',return_value=(100,100)), \
             mock.patch.object(a.resource,'setrlimit'), mock.patch.object(a.signal,'signal'), \
             mock.patch.object(a.signal,'getitimer',return_value=(0,0)), \
             mock.patch.object(a.time,'monotonic',side_effect=[10,20,35]), \
             mock.patch.object(a.signal,'setitimer') as wall:
            a.install_limits(20,100)
            wall.assert_called_once_with(a.signal.ITIMER_REAL,75)

    def test_elapsed_setup_refuses_expired_allowance(self):
        with mock.patch.object(a.resource,'getrlimit',return_value=(100,100)), \
             mock.patch.object(a.resource,'setrlimit'), mock.patch.object(a.signal,'signal'), \
             mock.patch.object(a.signal,'getitimer',return_value=(0,0)), \
             mock.patch.object(a.time,'monotonic',side_effect=[10,20,111]), \
             mock.patch.object(a.signal,'setitimer') as wall:
            with self.assertRaises(TimeoutError):
                a.install_limits(20,100)
            wall.assert_not_called()

    def test_delayed_inherited_timer_cases_refuse_without_rearming(self):
        # The inherited expiry cannot be proven inside requested deadline110.
        # A returned85 could mean earlier105; returned90 could mean later125.
        # Refusing both preserves the existing timer without guessing syscall latency.
        for inherited in (85,90):
            with mock.patch.object(a.resource,'getrlimit',return_value=(100,100)), \
                 mock.patch.object(a.resource,'setrlimit'), mock.patch.object(a.signal,'signal'), \
                 mock.patch.object(a.signal,'getitimer',return_value=(inherited,0)), \
                 mock.patch.object(a.time,'monotonic',side_effect=[10,35]), \
                 mock.patch.object(a.signal,'setitimer') as wall:
                with self.assertRaises(TimeoutError):
                    a.install_limits(20,100)
                wall.assert_not_called()

    def test_original_phase_deadline_not_reset(self):
        rows = [row(b'x',p,s) for p in range(1,55) for s in (1,2)]
        connector = Connector([])
        with self.assertRaises(a.Refused):
            a._acquire_rows(rows,self.output,self.limits,connector=connector,
                            clock=lambda:5,deadline=4)
        self.assertEqual(connector.calls,[])

    def test_deadline_checked_immediately_before_request(self):
        now = [0]
        connector = Connector([Response(b'generated-neural083-input')])
        def connect(host,timeout):
            connection = connector(host,timeout)
            now[0] = 6
            return connection
        with self.assertRaises(a.Refused):
            a.fetch(row(),self.output,1,self.limits,5,connector=connect,clock=lambda:now[0])
        self.assertEqual(connector.calls,[])
        self.assertEqual(connector.closed,1)

    def test_deadline_checked_before_EOF_probe(self):
        now = [0]
        body = b'abc'
        response = Response(body)
        connector = Connector([response])
        operations = a.Ops()
        def write(fd,view):
            value = os.write(fd,view)
            now[0] = 6
            return value
        operations.write = write
        self.output.ops = operations
        with self.assertRaises(a.Refused):
            a.fetch(row(body),self.output,1,self.limits,5,connector=connector,clock=lambda:now[0])
        self.assertEqual(response.reads,[3])
        self.assertEqual(self.receipt()['status'],'FAILED')

    def test_inert_cli_refuses_without_output(self):
        request = dict(schema='neural083_acquisition_request_v1', execution_authorized=False,
                       output_root=str(self.root/'must-not-exist'), whole_seconds=100,
                       request_seconds=10, socket_seconds=1, cpu_seconds=10,
                       minimum_free_bytes=a.TOTAL_BYTES+a.METADATA_CAP, owner_receipt=None)
        p = self.root/'inert.json'
        body = a.encoded(request)
        p.write_bytes(body)
        result = subprocess.run([sys.executable,'-I','-S','-B',str(HERE/'acquire.py'),
                  '--roster',str(HERE/'publisher_roster.json'),'--request',str(p),
                  '--request-bytes',str(len(body)),'--request-sha256',hashlib.sha256(body).hexdigest()],
                  capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode,0)
        self.assertIn(b'separate actual root execution selection', result.stderr)
        self.assertFalse((self.root/'must-not-exist').exists())


if __name__ == '__main__':
    signal.alarm(30)
    unittest.main(verbosity=2)
