"""Generated complete-panel controls; no authentic signals or model execution.

One full fixture is shared by all ten methods. The documented CLI is exercised
in a small generated repository containing exact active source and accepted
dependencies, with only generated LOCK/PANEL content pins resealed. This tests
software transport; it does not establish provider isolation or scientific use.
"""
import base64
import copy
import hashlib
import io as streams
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import types
import unittest
import zlib

import numpy as np


HERE = Path(__file__).resolve().parent
NAMESPACE = Path('benchmarks/neural/NEURAL-037/implementations/condition-viewer-v1')


def captured_module(path, name):
    """Bootstrap exactly as serve.py does, without importing local modules."""
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


FIXTURES = captured_module(HERE / 'generated_fixtures.py', '_neural037_generated_fixtures')


def decoded_png(body):
    """Independent PNG framing/CRC/filter decoder for this fixed RGB format."""
    if body[:8] != b'\x89PNG\r\n\x1a\n':
        raise AssertionError('PNG signature')
    offset = 8
    chunks = []
    image = bytearray()
    width = height = None
    while offset < len(body):
        length = struct.unpack('>I', body[offset:offset + 4])[0]
        kind = body[offset + 4:offset + 8]
        payload = body[offset + 8:offset + 8 + length]
        crc = struct.unpack('>I', body[offset + 8 + length:offset + 12 + length])[0]
        if len(payload) != length or zlib.crc32(kind + payload) != crc:
            raise AssertionError('Complete PNG chunk and CRC')
        chunks.append(kind)
        if kind == b'IHDR':
            width, height, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', payload)
            if (depth, color, compression, filtering, interlace) != (8, 2, 0, 0, 0):
                raise AssertionError('Unchanged complete RGB pixels')
        elif kind == b'IDAT':
            image.extend(payload)
        offset += length + 12
    if chunks != [b'IHDR', b'IDAT', b'IEND'] or offset != len(body):
        raise AssertionError('No text, custom or trailing answer metadata')
    raw = zlib.decompress(bytes(image))
    stride = 1 + 3 * width
    if len(raw) != stride * height or any(raw[i * stride] != 0 for i in range(height)):
        raise AssertionError('Full native raster and declared filter')
    pixels = b''.join(raw[i * stride + 1:(i + 1) * stride] for i in range(height))
    return width, height, pixels


class ViewerControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='neural037-generated-viewer-')
        cls.root = Path(cls.temporary.name).resolve()
        cls.bootstrap = captured_module(HERE / 'source.py', '_neural037_generated_source')
        cls.original = cls.bootstrap.load()
        cls.bundle, cls.views = FIXTURES.build(cls.root / 'fixture', cls.original)
        cls.viewer = cls.original.local('viewer')
        cls.collector = cls.original.local('collect')
        cls.renderer = cls.original.local('render')
        cls.io = cls.bundle.io
        cls.records = []
        cls.results = {}
        cls.bodies = {}
        cls.reply_streams = {}
        cls.explicit_scalars = 0
        cls.explicit_rows = 0
        cls.cli_tree = None
        cls.png_byte_sizes = []
        cls.canonical_submission_bytes = None
        # One full-panel author-scripted response, not a model or fitted method.
        for context in cls.bundle.panel['contexts']:
            name = context['context_id']
            session = cls.viewer.Session(cls.views[name], name, bundle=cls.bundle)
            stream = []
            for index, key in enumerate(context['cell_keys']):
                values = [(index + frame) % 7 - 3 for frame in range(context['frames'])]
                raw = cls.io.canonical({'action': 'submit', 'cell_key': key, 'values': values})
                if len(raw) > cls.viewer.ROW_BYTES:
                    raise AssertionError('Every full-panel response row fits the real action envelope')
                answer = session.act(raw)
                if answer['accepted_cell_key'] != key:
                    raise AssertionError('Every original query row was explicitly accepted')
                stream.append(raw)
                cls.explicit_scalars += len(values)
                cls.explicit_rows += 1
            finish = cls.io.canonical({'action': 'finish'})
            session.act(finish)
            stream.append(finish)
            value = session.result()
            body = cls.io.canonical(value)
            path = cls.root / 'captures' / (name + '.json')
            pin = FIXTURES.write(path, body)
            cls.records.append({'context_id': name, 'path': str(path), **pin})
            cls.results[name] = value
            cls.bodies[name] = body
            cls.reply_streams[name] = b''.join(stream)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def session(self, index=0):
        name = self.bundle.lock['contexts'][index]
        return self.viewer.Session(self.views[name], name, bundle=self.bundle)

    def action(self, session, name, **fields):
        return session.act(self.io.canonical({'action': name, **fields}))

    def refused_terminal(self, session, raw):
        with self.assertRaises(ValueError):
            session.act(raw)
        self.assertTrue(session.closed)
        self.assertIsNone(session.outcome)
        with self.assertRaises(ValueError):
            session.result()
        with self.assertRaises(ValueError):
            self.action(session, 'describe')
        with self.assertRaises(ValueError):
            self.action(session, 'submit', cell_key=session.query['cell_keys'][0],
                        values=[0] * session.query['frames'])

    def changed_capture(self, value):
        name = self.bundle.lock['contexts'][0]
        path = self.root / 'mutations' / 'capture.json'
        pin = FIXTURES.write(path, self.io.canonical(value))
        records = copy.deepcopy(self.records)
        records[0] = {'context_id': name, 'path': str(path), **pin}
        return records

    def test_01_full_panel_collection_and_original_admission(self):
        self.assertEqual((self.explicit_rows, self.explicit_scalars), (2264, 509360))
        self.assertEqual(len(self.records), 12)
        result = self.collector.collect(self.records, self.bundle)
        predictions, abstained = self.bundle.core.admit(self.bundle.panel, result, np)
        self.assertEqual(abstained, [])
        self.assertEqual(set(predictions), set(self.bundle.lock['contexts']))
        self.assertEqual(sum(array.size for array in predictions.values()), 509360)
        for context in self.bundle.panel['contexts']:
            self.assertEqual(predictions[context['context_id']].shape,
                             (len(context['cell_keys']), context['frames']))
        self.assertEqual(self.collector.collect(list(reversed(self.records)), self.bundle), result)
        body = self.io.canonical(result)
        type(self).canonical_submission_bytes = len(body)
        FIXTURES.write(self.root / 'complete-submission.json', body)
        self.assertEqual(self.viewer.PANEL_BYTES, 64_000_000)

    def test_02_complete_menus_and_reachable_first_last_rows(self):
        for fold, query in enumerate(self.bundle.panel['contexts']):
            session = self.session(fold)
            menu = session.describe()
            expected = set(self.bundle.lock['contexts']) - {query['context_id']}
            self.assertEqual({x['condition'] for x in menu['training']}, expected)
            self.assertEqual(len(menu['training']), 11)
            self.assertEqual(menu['query']['cell_keys'], query['cell_keys'])
            self.assertEqual(menu['query']['frames'], query['frames'])
            self.assertEqual(menu['budgets']['observe_actions'], 2 * sum(x['cells'] for x in menu['training']))
            self.assertEqual(menu['budgets']['external_output_tokens_per_row'], 8192)
            self.assertEqual(menu['budgets']['native_study_admission'], 'unavailable')
            # The first complete view visits both ROI boundaries of all eleven
            # authorized conditions. Other views prove full structural menus.
            if fold == 0:
                for row in menu['training']:
                    key = row['condition']
                    target = self.bundle.fixture_targets['contexts'][key]
                    for index in (0, row['cells'] - 1):
                        value = self.action(session, 'observe', training_condition=key,
                                            cell_key='cell_%04d' % index)
                        self.assertEqual(len(value['means']), row['frames'])
                        self.assertTrue(np.array_equal(value['means'], target['means'][index]))
                        self.assertTrue(np.array_equal(value['counts'], target['counts'][index]))
                        self.png_byte_sizes.append(len(base64.b64decode(value['png_base64'], validate=True)))
                self.assertEqual(session.observations, 22)

    def test_03_exact_readout_gaps_png_and_absent_condition(self):
        session = self.session()
        key = session.describe()['training'][0]['condition']
        value = self.action(session, 'observe', training_condition=key, cell_key='cell_0000')
        self.assertEqual(value['counts'][:2], [0, 0])
        self.assertEqual(value['means'][:2], [0.0, 0.0])
        png = base64.b64decode(value['png_base64'], validate=True)
        self.png_byte_sizes.append(len(png))
        width, height, pixels = decoded_png(png)
        self.assertEqual((width, height), (960, 384))
        self.assertEqual(value['legend']['frame_indices'], [0, len(value['means']) - 1])
        pixel = lambda x, y: tuple(pixels[(y * width + x) * 3:(y * width + x) * 3 + 3])
        self.assertEqual(pixel(24, 274), (180, 60, 60))
        self.assertFalse(any(pixel(24, y) == (24, 63, 130) for y in range(24, 271)))
        empty_key = 'cell_%04d' % (session.arrays[key][0].shape[0] - 1)
        absent = self.action(session, 'observe', training_condition=key, cell_key=empty_key)
        self.png_byte_sizes.append(len(base64.b64decode(absent['png_base64'], validate=True)))
        self.assertTrue(all(x == 0 for x in absent['counts']))
        self.assertIsNone(absent['legend']['observed_mean_min'])
        self.assertIsNone(absent['legend']['observed_mean_max'])
        _, _, empty_pixels = decoded_png(base64.b64decode(absent['png_base64'], validate=True))
        self.assertFalse(any(empty_pixels[i:i + 3] == bytes((24, 63, 130))
                             for i in range(0, len(empty_pixels), 3)))
        # A re-pinned generated view with a wholly unavailable training condition
        # must still fail the real loader; zero masks are not evidence of data.
        name = self.bundle.lock['contexts'][0]
        view = self.views[name]
        raw_input = (view / 'input.json').read_bytes()
        metadata = self.io.decode(raw_input)
        altered = copy.copy(self.bundle)
        altered.lock = copy.deepcopy(self.bundle.lock)
        selected = [r for r in altered.lock['files'] if r['fold'] is None or r['fold'] == 0]
        rows = {r['target']: r for r in selected}
        originals = {view / 'input.json': raw_input}
        try:
            training = metadata['training'][0]
            for kind, dtype in (('means', '<f8'), ('counts', '<u2')):
                path = view / training[kind]['path']
                originals[path] = path.read_bytes()
                stream = streams.BytesIO()
                np.save(stream, np.zeros(training['shape'], dtype=dtype), allow_pickle=False)
                pin = FIXTURES.write(path, stream.getvalue())
                training[kind].update(pin)
                rows['view/' + training[kind]['path']].update(pin)
            pin = FIXTURES.write(view / 'input.json', self.io.canonical(metadata))
            rows['view/input.json'].update(pin)
            with self.assertRaises(ValueError):
                self.viewer.Session(view, name, bundle=altered)
        finally:
            for path, raw in originals.items():
                FIXTURES.write(path, raw)

    def test_04_query_unknown_condition_and_returned_metadata(self):
        for key in (self.bundle.lock['contexts'][0], 'acquisition_9_ABC'):
            with self.subTest(condition=key):
                session = self.session()
                self.refused_terminal(session, self.io.canonical({
                    'action': 'observe', 'training_condition': key, 'cell_key': 'cell_0000'}))
        session = self.session()
        menu = session.describe()
        menu['query']['cell_keys'].clear()
        self.assertEqual(len(session.query['cell_keys']), 251)
        self.assertFalse(session.arrays[next(iter(session.arrays))][0].flags.writeable)

    def test_05_malformed_duplicate_partial_and_oversized_fail_closed(self):
        invalid = {
            'malformed_json': b'{\n',
            'duplicate_json_field': b'{"action":"describe","action":"describe"}\n',
            'unsupported_analysis': self.io.canonical({'action': 'run_python', 'code': '1+1'}),
            'missing_native_frame': self.io.canonical({'action': 'submit', 'cell_key': 'cell_0000', 'values': [0] * 239}),
            'boolean_value': self.io.canonical({'action': 'submit', 'cell_key': 'cell_0000', 'values': [True] * 240}),
            'early_finish': self.io.canonical({'action': 'finish'}),
            'oversized': b' ' * (self.viewer.ROW_BYTES + 1),
            'wrong_raw_type': '{"action":"describe"}\n',
        }
        for reason, raw in invalid.items():
            with self.subTest(reason=reason):
                self.refused_terminal(self.session(), raw)
        session = self.session()
        raw = self.io.canonical({'action': 'submit', 'cell_key': 'cell_0000', 'values': [0] * 240})
        session.act(raw)
        self.refused_terminal(session, raw)

    def test_06_capture_identity_hash_lineage_and_full_membership(self):
        name = self.bundle.lock['contexts'][0]
        for case in ('missing', 'duplicate', 'swapped', 'old_digest'):
            with self.subTest(case=case):
                records = copy.deepcopy(self.records)
                if case == 'missing':
                    records.pop()
                elif case == 'duplicate':
                    records[-1] = copy.deepcopy(records[0])
                elif case == 'swapped':
                    records[0]['path'], records[1]['path'] = records[1]['path'], records[0]['path']
                    for row in records[:2]:
                        row.update(self.io.pin(Path(row['path']).read_bytes()))
                else:
                    records[0]['sha256'] = '0' * 64
                with self.assertRaises(ValueError):
                    self.collector.collect(records, self.bundle)
        for field in ('source_binding', 'instructions_pin', 'input_pin', 'provider_tokens_measured',
                      'external_model_state_reset_verified', 'runtime_qualified', 'scientific_qualified'):
            with self.subTest(field=field):
                value = copy.deepcopy(self.results[name])
                if field.endswith('_pin') or field == 'source_binding':
                    value[field]['sha256'] = '0' * 64
                else:
                    value[field] = True
                with self.assertRaises(ValueError):
                    self.collector.collect(self.changed_capture(value), self.bundle)

    def test_07_abstention_and_original_panel_byte_gate(self):
        session = self.session()
        self.action(session, 'abstain', reason='Generated whole-context abstention control')
        records = self.changed_capture(session.result())
        collected = self.collector.collect(records, self.bundle)
        calls = []
        def forbidden_target_read():
            calls.append(True)
            raise AssertionError('Abstention must stop before any private callback')
        report = self.bundle.core.score(self.bundle.panel, collected, forbidden_target_read, np)
        self.assertEqual(report['status'], 'abstained')
        self.assertIsNone(report['metric'])
        self.assertEqual(calls, [])
        # This verifies the existing byte comparison without writing a 64 MB
        # artifact or changing one frame of original public admission support.
        original = self.io.canonical
        class SizedOnly:
            def __init__(self, size):
                self.size = size
            def __len__(self):
                return self.size
        try:
            for size, refused in ((64_000_000, False), (64_000_001, True)):
                self.io.canonical = lambda value, size=size: (
                    SizedOnly(size) if isinstance(value, dict) and
                    value.get('schema') == 'neural037-predictions-v1' else original(value))
                if refused:
                    with self.assertRaises(ValueError):
                        self.collector.collect(self.records, self.bundle)
                else:
                    self.collector.collect(self.records, self.bundle)
        finally:
            self.io.canonical = original

    def test_08_extreme_finite_float_rows_and_exact_byte_limit(self):
        extremes = [sys.float_info.max, -sys.float_info.max,
                    float.fromhex('0x0.0000000000001p-1022'),
                    -float.fromhex('0x0.0000000000001p-1022'), 0.0, -0.0]
        for fold in (0, 8):
            session = self.session(fold)
            values = (extremes * 40)[:session.query['frames']]
            raw = self.io.canonical({'action': 'submit', 'cell_key': 'cell_0000', 'values': values})
            self.assertLessEqual(len(raw), self.viewer.ROW_BYTES)
            padded = raw[:-1] + b' ' * (self.viewer.ROW_BYTES - len(raw)) + b'\n'
            self.assertEqual(len(padded), 8192)
            accepted = session.act(padded)
            self.assertEqual(accepted['accepted_cell_key'], 'cell_0000')
            self.assertEqual(session.rows['cell_0000'], values)
            rejected = self.session(fold)
            self.refused_terminal(rejected, padded[:-1] + b' \n')

    @classmethod
    def generated_cli_tree(cls):
        if cls.cli_tree is not None:
            return cls.cli_tree
        repository = cls.root / 'generated-repository'
        here = repository / NAMESPACE
        manifest = cls.io.decode((HERE / 'SOURCE_BINDINGS.json').read_bytes())
        for name, pin in manifest['local_implementation'].items():
            raw = (HERE / name).read_bytes()
            if cls.io.pin(raw) != pin:
                raise AssertionError('Exact active source copied into generated CLI repository')
            FIXTURES.write(here / name, raw)
        for record in manifest['accepted_dependencies'].values():
            raw = (cls.bootstrap.REPOSITORY / record['path']).read_bytes()
            if cls.io.pin(raw) != record['pin']:
                raise AssertionError('Exact accepted dependency in generated CLI repository')
            FIXTURES.write(repository / record['path'], raw)
        FIXTURES.write(here / 'INSTRUCTIONS.md', (HERE / 'INSTRUCTIONS.md').read_bytes())
        for name, original_pin in tuple(manifest['original_metadata'].items()):
            if name == 'source/LOCK.json':
                raw = cls.io.canonical(cls.bundle.lock)
            elif name == 'source/PANEL.json':
                raw = cls.io.canonical(cls.bundle.panel)
            else:
                raw = (HERE / name).read_bytes()
                if cls.io.pin(raw) != original_pin:
                    raise AssertionError('Original context contract stays byte-identical')
            manifest['original_metadata'][name] = FIXTURES.write(here / name, raw)
        FIXTURES.write(here / 'SOURCE_BINDINGS.json', cls.io.canonical(manifest))
        clone_source = captured_module(here / 'source.py', '_neural037_generated_cli_source')
        clone_bundle = clone_source.load()
        cls.cli_tree = (here, clone_bundle)
        return cls.cli_tree

    def cli_command(self, output):
        here, _ = self.generated_cli_tree()
        name = self.bundle.lock['contexts'][0]
        return [sys.executable, '-I', '-B', str(here / 'serve.py'),
                '--view', str(self.views[name]), '--context', name,
                '--output', str(output), '--seconds', '20']

    def test_09_documented_isolated_python_cli_complete_context(self):
        _, clone = self.generated_cli_tree()
        name = self.bundle.lock['contexts'][0]
        output = self.root / 'actual-cli-complete.json'
        expected = copy.deepcopy(self.results[name])
        expected['source_binding'] = clone.source_binding
        expected_body = self.io.canonical(expected)
        def execute():
            result = subprocess.run(self.cli_command(output), input=self.reply_streams[name],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    timeout=25, check=False, cwd=self.root)
            if result.returncode != 0:
                raise AssertionError('Generated complete CLI failed: ' + result.stderr.decode('utf-8', 'replace')[-1500:])
            if output.read_bytes() != expected_body:
                raise AssertionError('Actual CLI artifact exactly matches precomputed complete response')
            return result
        result = FIXTURES.publication(expected_body, execute)
        messages = [self.io.decode(line) for line in result.stdout.splitlines()]
        self.assertEqual(messages[0]['query']['context_id'], name)
        self.assertEqual(messages[-1]['operator_result'], self.io.pin(expected_body))
        self.assertTrue(messages[-1]['unscored'])
        self.assertEqual(messages[-1]['native_study_admission'], 'unavailable')
        self.assertEqual(sum('accepted_cell_key' in x for x in messages), 251)
        self.assertEqual(result.stderr, b'')

    def test_10_documented_isolated_python_cli_early_eof_has_no_artifact(self):
        output = self.root / 'actual-cli-eof.json'
        result = subprocess.run(self.cli_command(output), input=b'', stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=25, check=False, cwd=self.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())
        self.assertIn(b'EOF is not a response', result.stderr)


def run_controls():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ViewerControls)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return {'status': 'passed' if result.wasSuccessful() else 'failed',
            'test_methods_executed': result.testsRun, 'test_methods_defined': 10,
            'failures': len(result.failures), 'errors': len(result.errors),
            'python': sys.version, 'numpy': np.__version__,
            'thread_environment': {k: os.environ.get(k) for k in
                ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS')},
            'writes': FIXTURES.snapshot(),
            'complete_generated_submission_bytes': ViewerControls.canonical_submission_bytes,
            'generated_png_count': len(ViewerControls.png_byte_sizes),
            'generated_png_total_bytes': sum(ViewerControls.png_byte_sizes),
            'generated_png_max_bytes': max(ViewerControls.png_byte_sizes, default=0),
            'temporary_fixtures_removed': not ViewerControls.root.exists(),
            'scope': 'invented full12 software controls; one full response panel plus one full-context CLI replay',
            'panel_cap_control': 'exact size gate with synthetic length sentinel; no64MB file',
            'authentic_payload_reads': 0, 'model_or_provider_calls': 0,
            'native_scientific_runs': 0, 'external_model_isolation_qualified': False}


if __name__ == '__main__':
    report = run_controls()
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report['status'] == 'passed' else 1)
