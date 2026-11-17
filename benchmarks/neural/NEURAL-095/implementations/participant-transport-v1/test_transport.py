"""Independent generated transport controls; no authentic data or model.

The bulk fixture uses a small valid 1400x820 PNG with metadata-bound text and an
explicit synthetic pixel commitment. One separate frame uses the original renderer.
This substitution tests transport/replay; it does not test scientific rendering.
"""
import base64
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import zlib

import numpy as np

HERE = Path(__file__).resolve().parent

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

t = load('neural095_transport_independent_test', HERE / 'transport.py')
original_tests = load('neural095_original_fixture_support', HERE.parent / 'count-viewer-v1/test_viewer.py')
original_tests.v = t.v
PYTHON = '/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11'
if not Path(PYTHON).is_file():
    PYTHON = sys.executable
LIMITS = t.Limits(1300, 1006, 32 * 1024**2, 30.)

def chunk(kind, body):
    return struct.pack('!I', len(body)) + kind + body + struct.pack('!I', zlib.crc32(kind + body))

PNG_HEADER = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 1400, 820, 8, 2, 0, 0, 0))
PNG_DATA = chunk(b'IDAT', zlib.compress(b'\x00' * (820 * (1400 * 3 + 1)), 6))
PNG_END = chunk(b'IEND', b'')

def generated_render(metadata, counts, units, raster):
    commitment = hashlib.sha256(t.encode({'metadata': metadata, 'counts': counts, 'units': units})).hexdigest().encode()
    image = PNG_HEADER + chunk(b'tEXt', b'generated-transport-fixture\x00' + commitment) + PNG_DATA + PNG_END
    return image, b'GENERATED_PIXEL_COMMITMENT:' + commitment

class Fixture(original_tests.Fixture):
    def __init__(self, root):
        super().__init__(root)
        self.sources.modules['render'] = types.SimpleNamespace(render=generated_render)

def put(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path

def json_at(path):
    return json.loads(Path(path).read_text())

@contextmanager
def changed(path, change):
    path = Path(path)
    original = path.read_bytes()
    mode = path.stat().st_mode & 0o777
    path.chmod(0o600)
    path.write_bytes(change(original))
    try:
        yield
    finally:
        path.write_bytes(original)
        path.chmod(mode)

def mutate_json(path, transform):
    return changed(path, lambda raw: t.encode(transform(json.loads(raw))))

CLIENT_WIRE = '''import json, struct, sys
P=struct.Struct('!II')
def exact(n):
 b=bytearray()
 while len(b)<n:
  x=sys.stdin.buffer.read(n-len(b))
  if not x: raise EOFError('operator closed')
  b.extend(x)
 return bytes(b)
def receive():
 h,p=P.unpack(exact(8)); assert 0<h<=32768 and 0<=p<=4194304
 return json.loads(exact(h)),exact(p)
def emit(a):
 b=json.dumps(a,separators=(',',':'),allow_nan=False).encode()
 sys.stdout.buffer.write(P.pack(len(b),0)+b);sys.stdout.buffer.flush()
def action(a):
 emit(a);return receive()
ready,png=receive()
assert ready['kind']=='instructions' and not png
'''

QUERY_LOOP = '''for i,case_id in enumerate(ready['query_ids']):
 row,png=action({'op':'show_query','index':i})
 assert row['kind']=='observation' and png.startswith(b'\\x89PNG\\r\\n\\x1a\\n')
 assert 'tp_ms' not in row['observation']['metadata'] and 'fold' not in row['observation']['metadata']
 ack,png=action({'op':'answer','case_id':case_id,'prediction_ms':-3.5 if i==0 else 800.0})
 assert ack=={'kind':'accepted','accepted':case_id,'answered':i+1} and not png
last,png=action({'op':'finish'})
assert last=={'kind':'complete','view':ready['view'],'answers':258} and not png
'''

def frames(path):
    result = []
    with (Path(path) / 'transport/wire.bin').open('rb') as stream:
        for line in (Path(path) / 'transport/journal.jsonl').read_bytes().splitlines():
            row = json.loads(line)
            raw = stream.read(row['bytes'])
            result.append((row, raw))
        assert stream.read(1) == b''
    return result

class FullPair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='.generated-participant-pair-', dir=HERE)
        cls.root = Path(cls.temp.name)
        cls.f = Fixture(cls.root / 'inputs')
        source = (HERE / 'scripted_client.py').read_text()
        # Real child-local persistence is exercised without adding host data.
        source = source.replace('import json\n', 'import json\nimport os\nfrom pathlib import Path\nassert not Path("local-sentinel").exists()\nPath("local-sentinel").write_text("fresh-view")\nassert "HOME" not in os.environ\n')
        source += '\nassert Path("local-sentinel").read_text()=="fresh-view"\n'
        cls.client = put(cls.root / 'client.py', source.encode())
        cls.sessions = {}
        for view in t.v.VIEWS:
            path = cls.root / view
            result = t.run_view(cls.f.packets[view], path, cls.client, PYTHON, 'protocol_only', LIMITS)
            if result['status'] != 'complete_unscored':
                raise AssertionError(result)
            cls.sessions[view] = path
        cls.collection = cls.root / 'collection'
        cls.collected = t.collect(cls.f.packets, cls.sessions, cls.collection)

    @classmethod
    def tearDownClass(cls):
        print('GENERATED_FULL_PAIR_RETAINED_BYTES_BEFORE_CLEANUP=' + str(sum(p.stat().st_size for p in cls.root.rglob('*') if p.is_file())))
        cls.temp.cleanup()

    def test_full_pair_original_collector_and_population(self):
        self.assertEqual(self.collected['status'], 'both_closed_views_collected')
        for view in t.v.VIEWS:
            result = json_at(self.sessions[view] / 'RESULT.json')
            self.assertEqual((result['actions'], result['images']), (1265, 1006))
            self.assertEqual(result['process_group_cleanup'], 'absent')
            self.assertFalse(result['scientific_qualification'])
            with np.load(self.collection / (view + '.npz'), allow_pickle=False) as data:
                self.assertEqual(set(data.files), {'case_id', 'prediction_ms'})
                self.assertEqual(data['case_id'].tolist(), self.f.packets[view].ids)
                self.assertTrue(np.all(data['prediction_ms'] == 800.))
        self.assertNotEqual(json_at(self.sessions['cue_only'] / 'BOUNDARY.json')['episode_id'],
                            json_at(self.sessions['neural'] / 'BOUNDARY.json')['episode_id'])

    def test_only_allowed_metadata_and_image_bytes_reach_participant(self):
        for view in t.v.VIEWS:
            outbound = [t.unpack(raw) for row, raw in frames(self.sessions[view]) if row['direction'] == 'out']
            ready, image = outbound[0]
            self.assertEqual((ready['train_n'], ready['query_n']), (748, 258))
            self.assertEqual(len(ready['unit_ids']), 40)
            self.assertFalse(image)
            self.assertFalse({'source', 'runtime', 'inputs', 'common_members'} & set(ready))
            counts = {'train': 0, 'query': 0}
            for header, png in outbound[1:]:
                if header['kind'] == 'observation':
                    o = header['observation']; m = o['metadata']; counts[m['split']] += 1
                    self.assertNotIn('counts', o); self.assertNotIn('counts', m)
                    self.assertEqual(t.pin(png), o['image'])
                    self.assertEqual(struct.unpack('!II', png[16:24]), (1400, 820))
                    self.assertEqual('tp_ms' in m, m['split'] == 'train')
                    self.assertEqual('fold' in m, m['split'] == 'train')
                    self.assertEqual(o['representation'], 'cues_only' if view == 'cue_only' else 'four_by_forty_uint32_count_table')
            self.assertEqual(counts, {'train': 748, 'query': 258})

    def test_corrupt_wire_rejected_without_changing_answers(self):
        path = self.sessions['cue_only'] / 'transport/wire.bin'
        with path.open('r+b') as stream:
            stream.seek(15); old = stream.read(1); stream.seek(15); stream.write(bytes([old[0] ^ 1]))
        try:
            with self.assertRaises(ValueError):
                t.audit_view(self.sessions['cue_only'], self.f.packets['cue_only'])
        finally:
            with path.open('r+b') as stream:
                stream.seek(15); stream.write(old)

    def test_changed_request_history_rejected(self):
        path = self.sessions['cue_only'] / 'viewer-history.jsonl'
        def change(raw):
            lines = raw.splitlines(keepends=True)
            row = json.loads(lines[1]); row['action']['index'] = 1
            lines[1] = t.v.encoded(row)
            return b''.join(lines)
        with changed(path, change):
            with self.assertRaises(ValueError):
                t.audit_view(self.sessions['cue_only'], self.f.packets['cue_only'])

    def test_client_source_limits_and_failed_marker_rejected(self):
        path = self.sessions['cue_only']
        with changed(path / 'client.py', lambda b: b + b'\n# changed\n'):
            with self.assertRaises(ValueError): t.audit_view(path, self.f.packets['cue_only'])
        with mutate_json(path / 'BOUNDARY.json', lambda d: dict(d, source={})):
            with self.assertRaises(ValueError): t.audit_view(path, self.f.packets['cue_only'])
        with mutate_json(path / 'BOUNDARY.json', lambda d: dict(d, limits=dict(d['limits'], max_actions=1299))):
            with self.assertRaises(ValueError): t.audit_view(path, self.f.packets['cue_only'])
        marker = put(path / 'FAILED.json', b'{}\n')
        try:
            with self.assertRaises(ValueError): t.audit_view(path, self.f.packets['cue_only'])
        finally: marker.unlink()

    def test_both_distinct_views_required_before_collection(self):
        for sessions in ({'cue_only': self.sessions['cue_only']},
                         dict.fromkeys(t.v.VIEWS, self.sessions['cue_only']),
                         {'cue_only': self.sessions['neural'], 'neural': self.sessions['cue_only']}):
            with self.assertRaises(ValueError):
                t.collect(self.f.packets, sessions, self.root / 'must-not-exist')
            self.assertFalse((self.root / 'must-not-exist').exists())

    def test_collection_mutation_refused_before_any_private_loader(self):
        calls = []
        reference = lambda: calls.append('reference')
        private = lambda: calls.append('private')
        with changed(self.collection / 'TRANSPORT_COMPLETE.json', lambda b: b.replace(b'both_closed_views_collected', b'altered_closure')):
            with self.assertRaises(ValueError):
                t.evaluate(self.f.packets, self.sessions, self.collection, reference, private)
        self.assertEqual(calls, [])
        with changed(self.collection / 'cue_only.npz', lambda b: b[:-1]):
            with self.assertRaises(ValueError):
                t.evaluate(self.f.packets, self.sessions, self.collection, reference, private)
        self.assertEqual(calls, [])

    def test_complete_original_five_reference_and_exact_pair_grade_on_generated_only(self):
        calls = []
        def references(): calls.append('references'); return self.f.references()
        def private(): calls.append('private'); return self.f.truth()
        result = t.evaluate(self.f.packets, self.sessions, self.collection, references, private)
        self.assertEqual(calls, ['references', 'private'])
        self.assertEqual(result['original_grade']['cases_per_view'], 258)
        self.assertFalse(result['scientific_qualification'])
        for arm in result['original_grade']['arms'].values():
            self.assertEqual(set(arm['candidate']['by_condition']), {str(i) for i in range(40)})
            self.assertEqual(set(arm['candidate']['by_context']), {str(i) for i in range(8)})

class FailureControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='.generated-participant-failures-', dir=HERE)
        cls.root = Path(cls.temp.name); cls.f = Fixture(cls.root / 'inputs'); cls.counter = 0
    @classmethod
    def tearDownClass(cls):
        print('GENERATED_FAILURE_RETAINED_BYTES_BEFORE_CLEANUP=' + str(sum(p.stat().st_size for p in cls.root.rglob('*') if p.is_file())))
        cls.temp.cleanup()
    def run_child(self, body, *, limits=LIMITS, prefix=True):
        type(self).counter += 1
        folder = self.root / f'child-{self.counter}'
        client = put(self.root / f'client-{self.counter}.py', ((CLIENT_WIRE if prefix else '') + body).encode())
        result = t.run_view(self.f.packets['cue_only'], folder, client, PYTHON, 'protocol_only', limits)
        return folder, result
    def assert_failed(self, folder, result):
        self.assertEqual(result['status'], 'failed')
        self.assertTrue((folder / 'FAILED.json').is_file())
        with self.assertRaises(ValueError): t.audit_view(folder, self.f.packets['cue_only'])
    def test_partial_oversized_duplicate_and_unknown_requests_fail(self):
        bodies = ["sys.stdout.buffer.write(b'\\x00\\x00\\x00');sys.stdout.buffer.flush()\n",
                  "sys.stdout.buffer.write(P.pack(16385,0));sys.stdout.buffer.flush()\n",
                  "b=b'{\\\"op\\\":\\\"finish\\\",\\\"op\\\":\\\"show_query\\\"}';sys.stdout.buffer.write(P.pack(len(b),0)+b);sys.stdout.buffer.flush()\n",
                  "emit({'op':'execute','code':'1+1'})\n"]
        for body in bodies:
            with self.subTest(body=body):
                folder, result = self.run_child(body); self.assert_failed(folder, result)
        partial = frames(self.root / f'child-{self.counter - 3}')[-1]
        self.assertFalse(partial[0]['complete']); self.assertEqual(len(partial[1]), 3)
    def test_unseen_query_duplicate_answer_and_early_finish_fail(self):
        bodies = ["emit({'op':'answer','case_id':ready['query_ids'][0],'prediction_ms':800.})\n",
                  "action({'op':'show_query','index':0});action({'op':'answer','case_id':ready['query_ids'][0],'prediction_ms':800.});emit({'op':'answer','case_id':ready['query_ids'][0],'prediction_ms':801.})\n",
                  "emit({'op':'finish'})\n"]
        for body in bodies:
            with self.subTest(body=body):
                folder, result = self.run_child(body); self.assert_failed(folder, result)
    def test_partial_output_retains_actual_delivered_prefix(self):
        original = t.write_frame
        def fail_after_prefix(fd, body, deadline):
            os.write(fd, body[:17]); raise t.WireFailure('injected_partial', body[:17])
        with patch.object(t, 'write_frame', side_effect=fail_after_prefix):
            folder, result = self.run_child('')
        self.assert_failed(folder, result)
        row, raw = frames(folder)[0]
        self.assertFalse(row['complete']); self.assertEqual(len(raw), 17)
    def test_hung_child_deadline_owned_cleanup(self):
        started = time.monotonic()
        folder, result = self.run_child('import time\ntime.sleep(10)\n', limits=replace(LIMITS, wall_seconds=.3))
        self.assert_failed(folder, result); self.assertLess(time.monotonic() - started, 3)
        self.assertTrue(result['forced_stop'])
        with self.assertRaises(ProcessLookupError): os.kill(result['client_pid'], 0)
    def test_terminal_nonzero_and_live_group_leave_original_history_incomplete(self):
        other_history = put(self.root / 'valid-other-history.jsonl', self.f.history('neural'))
        for tail in ('raise SystemExit(9)\n',
                     "import os,time\nchild=os.fork()\nif child==0:\n time.sleep(10);os._exit(0)\n"):
            with self.subTest(tail=tail):
                folder, result = self.run_child(QUERY_LOOP + tail)
                self.assert_failed(folder, result)
                history = (folder / 'viewer-history.jsonl').read_bytes()
                with self.assertRaises(ValueError): t.v.replay(self.f.packets['cue_only'], history)
                with self.assertRaises(ValueError):
                    t.v.collect(self.f.packets, {'cue_only': folder / 'viewer-history.jsonl', 'neural': other_history},
                                self.root / 'must-not-collect-failed-client')
                self.assertFalse((self.root / 'must-not-collect-failed-client').exists())
    def test_journal_failure_prevents_ack_and_later_response(self):
        original = t.os.fsync
        def fail_answer(fd):
            try:
                info = os.fstat(fd)
                # The history file is the only append fd with an answer JSON row.
                for path in self.root.glob('child-*/viewer-history.jsonl'):
                    if path.stat().st_ino == info.st_ino and b'"answer_index":0' in path.read_bytes():
                        raise OSError('injected fsync failure')
            except FileNotFoundError:
                pass
            return original(fd)
        body = "action({'op':'show_query','index':0});emit({'op':'answer','case_id':ready['query_ids'][0],'prediction_ms':800.});receive()\n"
        with patch.object(t.os, 'fsync', side_effect=fail_answer):
            folder, result = self.run_child(body)
        self.assert_failed(folder, result)
        outbound = [t.unpack(raw)[0] for row, raw in frames(folder) if row['direction'] == 'out' and row['complete']]
        self.assertFalse(any(row.get('kind') == 'accepted' for row in outbound))
    def test_all_training_available_but_optional_and_negative_predictions_preserved(self):
        folder, result = self.run_child(QUERY_LOOP)
        self.assertEqual((result['status'], result['images'], result['actions']), ('complete_unscored', 258, 517))
        t.audit_view(folder, self.f.packets['cue_only'])
        answers = t.v.replay(self.f.packets['cue_only'], (folder / 'viewer-history.jsonl').read_bytes())
        self.assertEqual(answers[0], -3.5)
    def test_actual_original_renderer_png_crosses_process_boundary(self):
        original = self.f.sources.modules['render']
        actual = t.v.Sources().modules['render']
        seen = []
        def first_actual(metadata, counts, units, raster):
            if metadata['split'] == 'query' and metadata['index'] == 0:
                image, pixels = actual.render(metadata, counts, units, raster); seen.append(t.pin(image)); return image, pixels
            return generated_render(metadata, counts, units, raster)
        self.f.sources.modules['render'] = types.SimpleNamespace(render=first_actual)
        try:
            folder, result = self.run_child(QUERY_LOOP)
            self.assertEqual(result['status'], 'complete_unscored')
            image_frames = [(t.unpack(raw)[0], t.unpack(raw)[1]) for row, raw in frames(folder)
                            if row['direction'] == 'out' and t.unpack(raw)[1]]
            self.assertEqual(t.pin(image_frames[0][1]), seen[0])
            pixels = original_tests.unpack_png(image_frames[0][1])
            self.assertEqual(t.pin(pixels), image_frames[0][0]['observation']['pixels'])
        finally:
            self.f.sources.modules['render'] = original
    def test_explicit_full_offering_limits_required(self):
        for limits in (replace(LIMITS, max_actions=1264), replace(LIMITS, max_images=1005),
                       replace(LIMITS, wall_seconds=float('nan')), replace(LIMITS, max_output_bytes=100)):
            with self.assertRaises(ValueError): limits.validate()
    def test_output_capacity_refuses_before_any_image_render(self):
        limits = replace(LIMITS, max_output_bytes=t.PNG_MAX + t.HEADER_MAX + 4096)
        with patch.object(self.f.packets['cue_only'], 'show', side_effect=AssertionError('must not render')) as show:
            folder, result = self.run_child("emit({'op':'show_query','index':0})\n", limits=limits)
        self.assert_failed(folder, result); show.assert_not_called()

if __name__ == '__main__':
    unittest.main(verbosity=2)
