"""Generated controls only; authentic packets/images/targets are never opened."""
import argparse
import copy
import contextlib
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import zlib

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('erp_image_adapter_test_subject', HERE / 'adapter.py')
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
MODULES = None
SCRATCH_ROOT = None
WRITE_BYTES = 0


def generated_png(post):
    w, h = 1400, 820
    pixels = bytearray(b'\xff' * (w * h * 3))
    for top in (205, 465):
        for x in range(180, 1300):
            if post is None and x >= 460: continue
            y = top + 90 - (post if x >= 460 else 0)
            p = (y * w + x) * 3; pixels[p:p+3] = b'\x14\x4b\xaa'
    raw = b''.join(b'\x00' + pixels[y*w*3:(y+1)*w*3] for y in range(h))
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind+body))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def ids():
    return tuple(f'q-{i:032x}' for i in range(6400))


def arm(identifiers):
    descriptor = {'bytes': 1, 'sha256': '0'*64}
    return {'schema': 'erp-full32-image-uncertainty-arm-v1', 'status': 'complete_unscored_reference',
        'contract': descriptor, 'condition': a.CONDITION, 'query_count': 6400, 'private_target_reads': 0,
        'scoring_performed': False, 'automatic_retry': False, 'read_bytes_charged': 1,
        'written_bytes_charged_before_receipt': 1,
        'rows': [{'ordinal': i, 'trial_id': key, 'image': descriptor, 'view': descriptor, 'end': descriptor,
                  'quality': descriptor, 'target_probability': .5} for i, key in enumerate(identifiers)]}


def write(path, body):
    global WRITE_BYTES
    path.write_bytes(body); WRITE_BYTES += len(body)


class AdmissionControls(unittest.TestCase):
    def test_complete6400_unique_inventory_and_no_subset(self):
        value = arm(ids()); a.validate_arm(value, value['contract'], ids())
        for mutation in ('missing', 'duplicate', 'invalid', 'wrong_order', 'retry', 'wrong_count'):
            changed = copy.deepcopy(value)
            if mutation == 'missing': changed['rows'].pop()
            elif mutation == 'duplicate': changed['rows'][3]['trial_id'] = changed['rows'][2]['trial_id']
            elif mutation == 'invalid': changed['rows'][3]['target_probability'] = float('nan')
            elif mutation == 'wrong_order': changed['rows'][3]['ordinal'] = 4
            elif mutation == 'retry': changed['automatic_retry'] = True
            else: changed['query_count'] = 400
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                a.validate_arm(changed, value['contract'], ids())

    def test_audit_mutation_and_legacy_response_refused(self):
        quality = {'coverage': [0.] * 30, 'baseline_coverage': [1., 1.],
            'shared_weights': [0.] * 30, 'shared_support_fraction': 0., 'no_shared_support': True}
        response = {'trial_id': ids()[0], 'target_probability': .5, 'quality': quality}
        self.assertEqual(a.parse_response(a.encode(response), ids()[0]), response)
        for field, bad in (('no_shared_support', False), ('coverage', [0.] * 29),
                           ('shared_support_fraction', float('nan')), ('shared_weights', [1.] * 30)):
            changed = copy.deepcopy(response); changed['quality'][field] = bad
            with self.assertRaises(ValueError): a.parse_response(json.dumps(changed), ids()[0])
        with self.assertRaises(ValueError): a.parse_response('{"trial_id":"x","target_probability":0.5}', 'x')
        summary = a.coverage_summary([quality] * 6400)
        self.assertEqual(summary['no_shared_support_queries'], 6400)
        self.assertEqual(summary['feature_defined_queries'], [0] * 30)
        with self.assertRaises(ValueError): a.coverage_summary([quality] * 6399)

    def test_any_admission_failure_leaves_private_loader_unopened(self):
        events = []
        def rejected(): events.append('admission'); raise ValueError('bad first response')
        def labels(_): events.append('private'); return {}
        with self.assertRaises(ValueError): a.ordered_metrics(rejected, labels, None)
        self.assertEqual(events, ['admission'])
        with self.assertRaises(ValueError): a.ordered_metrics(lambda: {ids()[0]: .5}, labels, None)
        self.assertEqual(events, ['admission'])

    def test_original_equal_person_metrics_after_full_admission(self):
        identifiers = ids(); values = dict.fromkeys(identifiers, .5); events = []
        def admit(): events.append('all6400'); return values
        def labels(keys):
            events.append('private'); self.assertEqual(keys, set(identifiers))
            return {f'p-{i:02d}': [(identifiers[i*200+j], int(j < 40)) for j in range(200)] for i in range(32)}
        result = a.ordered_metrics(admit, labels, MODULES['capture']['core'])
        self.assertEqual(events, ['all6400', 'private'])
        self.assertEqual(len(result['participants']), 32)
        self.assertEqual(result['participant_macro_balanced_accuracy'], .5)
        self.assertAlmostEqual(result['participant_macro_natural_log_loss'], math.log(2))

    def test_duplicate_private_join_rejected_before_metrics(self):
        identifiers = ids(); values = dict.fromkeys(identifiers, .5)
        people = {f'p-{i}': [(identifiers[i*200+j], int(j < 40)) for j in range(200)] for i in range(32)}
        people['p-1'][40] = people['p-0'][40]
        called = []
        core = types.SimpleNamespace(metric_rows=lambda *_: called.append('metrics'))
        with self.assertRaises(ValueError): a.ordered_metrics(lambda: values, lambda _: people, core)
        self.assertEqual(called, [])

    def test_generated_query_and_demo_equal_original_session_pngs(self):
        global WRITE_BYTES
        viewer = MODULES['visual']['transport'].v
        waveform = [0.2 * math.sin(i / 30) + (2.0 if i >= 300 else 0.0) for i in range(1024)]
        record = {'trial_id': ids()[0], 'channels': [waveform, waveform]}
        demos = [dict(record, trial_id=f'd-generated-{i}', target=y) for i, y in enumerate((0, 1, 0, 1))]
        dataset = {'profile': a.PROFILE, 'profile_commitment': viewer.profile_binding(a.PROFILE, MODULES['root']/a.PREFIX),
            'rows': [record] * 6400, 'trial_ids': ids(), 'demos': demos,
            'packet': {'generated_control': 'not_authentic'}, '_implementation_root': MODULES['root']/a.PREFIX}
        with tempfile.TemporaryDirectory(dir=HERE.parent) as temp:
            session = viewer.Session(dataset, 0, 'four_demo', Path(temp)/'view')
            raw = session.handle(b'{"action":"inspect"}')
            projection, expected = MODULES['visual']['transport'].projection(raw)
            actual, metadata = a.render(record, MODULES)
            self.assertEqual(actual, expected); self.assertEqual(metadata['display'], projection['display'])
            raw = session.handle(b'{"action":"select","record":"demo1"}')
            projection, expected = MODULES['visual']['transport'].projection(raw)
            actual, metadata = a.render(demos[0], MODULES, demonstration=0)
            self.assertEqual(actual, expected); self.assertEqual(metadata['display'], projection['display'])
            WRITE_BYTES += sum(p.stat().st_size for p in Path(temp).rglob('*') if p.is_file())

    def test_image_cap_refuses_without_reencoding_or_resampling(self):
        codec = types.SimpleNamespace(encode_transport_image=lambda _: (b'x'*65537, {}),
                                      verify_equivalence=lambda *_: None)
        raster = types.SimpleNamespace(render=lambda *_: b'original')
        viewer = types.SimpleNamespace(initial_state=lambda: {'record': 'query'})
        modules = {'visual': {'transport': types.SimpleNamespace(v=viewer)}, 'raster': raster, 'codec': codec}
        with self.assertRaisesRegex(ValueError, '64KiB'): a.render({}, modules)

    def test_demo_source_pixel_mismatch_closes_packet_before_query_access(self):
        opened = []
        viewer = types.SimpleNamespace(ordered_ids=lambda _: ids(), close_source=lambda _: opened.append('closed'))
        data = {'demos': [{}, {}, {}, {}]}
        modules = {'visual': {'transport': types.SimpleNamespace(v=viewer),
            'provider': types.SimpleNamespace(dataset_for=lambda *_, **__: data)}}
        contract = {'public_root': '/generated', 'public_manifest': a.MANIFEST,
            'demos': [{'file': {'bytes': 1, 'sha256': '0'*64}} for _ in range(4)]}
        with patch.object(a, 'render', return_value=(b'wrong', {})), self.assertRaisesRegex(ValueError, 'demo PNG'):
            a.open_data(contract, modules, None, ids())
        self.assertEqual(opened, ['closed'])

    def test_protected_inputs_cannot_overlap_runtime_readable_roots(self):
        for path in ('/', '/usr', '/usr/generated-private', '/System/generated', '/Library/Frameworks/generated'):
            with self.subTest(path=path), self.assertRaises(ValueError): a.protected(path)
        self.assertEqual(a.protected(HERE), HERE)

    def test_only_three_input_literals_extend_original_sandbox(self):
        wire = types.SimpleNamespace(WireFailure=Exception, read_frame=None, write_frame=None,
                                     sandbox_profile=lambda _: '(version 1) (deny default) (deny network* process-fork)')
        result = a.image_wire(wire, ['/generated/reference.py', '/generated/MODEL.json', '/generated/QUERY.png'])
        policy = result.sandbox_profile('/generated/CLIENT.py')
        self.assertEqual(policy.count('(literal '), 3)
        self.assertNotIn('(subpath "/generated")', policy)
        self.assertIn('(deny network* process-fork)', policy)
        with self.assertRaises(ValueError): a.image_wire(wire, ['/usr/x', '/generated/m', '/generated/q'])

    def test_ordinary_file_capture_rejects_changed_pin_and_links(self):
        with tempfile.TemporaryDirectory(dir=HERE.parent) as temp:
            root = Path(temp); write(root/'file', b'original'); (root/'link').symlink_to(root/'file')
            with self.assertRaises(ValueError): a.read(root/'link', 100)
            with self.assertRaises(ValueError): a.read(root/'file', 100, a.pin(b'changed'))
            self.assertEqual(a.read(root/'file', 100, a.pin(b'original')), b'original')


class EvaluationControls(unittest.TestCase):
    def exercise(self, tamper=False):
        identifiers = ids(); quality = {'coverage': [0.] * 30, 'baseline_coverage': [1., 1.],
            'shared_weights': [0.] * 30, 'shared_support_fraction': 0., 'no_shared_support': True}
        events = []; projection = {'generated': True}; png = b'generated-rendered-png'
        # Evaluation output must be outside the protected source checkout.
        with tempfile.TemporaryDirectory(dir=SCRATCH_ROOT) as temp:
            root = Path(temp); frozen = root/'frozen'; public = root/'private/public'; arm_root = root/'arm'
            descriptor = a.pin(b'generated')
            limit = {'read_bytes': 64*1024**2, 'write_bytes': 1024**2, 'work_seconds': 60,
                'closure_seconds': 10, 'episode_work_seconds': 5, 'episode_cleanup_seconds': 3}
            contract = {'schema': 'erp-full32-image-uncertainty-contract-v1', 'policy': a.POLICY,
                'metrics': a.METRICS, 'repository_root': str(MODULES['root']), 'source_bindings': MODULES['binding'],
                'public_root': str(public), 'public_manifest': a.MANIFEST, 'roster': descriptor,
                'demos': [{'path': str(root/'demos'/str(i)), 'file': descriptor, 'record': f'demo{i+1}',
                           'label': (0, 1, 0, 1)[i]} for i in range(4)],
                'model': {'path': str(frozen/'MODEL.json'), 'file': descriptor},
                'algorithm': {'path': str(MODULES['algorithm_path']), 'file': a.ALGORITHM},
                'client': {'path': str(frozen/'CLIENT.py'), 'file': descriptor},
                'interpreter': {'path': sys.executable, **descriptor},
                'sandbox': {'path': '/usr/bin/sandbox-exec', **descriptor},
                'limits': {name: dict(limit) for name in ('freeze', 'run', 'evaluate')},
                'freeze_stage': {'fit_calls': 1, 'query_images_processed': 0, 'private_targets_opened': False},
                'demo_export_provenance': descriptor}
            committed = a.pin(a.encode(contract)); value = arm(identifiers); value['contract'] = committed
            for row in value['rows']:
                row.update(image=a.pin(png), view=a.pin(a.encode(projection)), quality=a.pin(a.encode(quality)))
            if tamper: value['rows'][-1]['quality'] = a.pin(b'tampered')
            arm_bytes = a.encode(value); budget = MODULES['pair'].Budget(64*1024**2, 1024**2, time.monotonic()+30)
            def read(path, *args, **kwargs):
                name = Path(path).name
                if name == 'ARM.json': return arm_bytes
                if name == 'INITIAL.json': return a.encode({'trial_ids': list(identifiers), 'contract': committed})
                index = int(Path(path).parent.name); row = value['rows'][index]
                if name == 'START.json': return a.encode({'ordinal': index, 'trial_id': identifiers[index], 'attempt': 1})
                if name == 'QUERY.png': return png
                if name == 'VIEW.json': return a.encode(projection)
                if name == 'COMPLETE.json': return a.encode(row)
                self.fail('Unexpected read '+str(path))
            def episode(path, context, *args):
                index = int(Path(path).parent.name); events.append(('admitted', index))
                return {'trial_id': context['trial_id'], 'target_probability': .5, 'quality': quality}, value['rows'][index]['end']
            people = {f'p-{i}': [(identifiers[i*200+j], int(j < 40)) for j in range(200)] for i in range(32)}
            def private():
                events.append(('private', len(events)))
                return {'root': str(public.parent), 'complete': descriptor}
            core = types.SimpleNamespace(metric_rows=MODULES['capture']['core'].metric_rows,
                                         load_private_people=lambda *_: people)
            modules = dict(MODULES); modules['capture'] = dict(MODULES['capture'], core=core)
            modules['visual_pair'] = types.SimpleNamespace(deadline=lambda _: contextlib.nullcontext())
            modules['visual'] = {'transport': types.SimpleNamespace(v=types.SimpleNamespace(close_source=lambda _: events.append(('closed', 0))))}
            with patch.multiple(a, dependencies=lambda *_: modules, new_budget=lambda *_: budget,
                verify_frozen=lambda *_: identifiers, check_runtime=lambda *_: None,
                open_data=lambda *_: {'rows': [None]*6400}, render=lambda *_: (png, projection),
                episode_files=episode, read=read):
                if tamper:
                    with self.assertRaisesRegex(ValueError, 'score and coverage'):
                        a.evaluate(contract, committed, arm_root, a.pin(arm_bytes), private, root/'result')
                    self.assertFalse(any(event[0] == 'private' for event in events))
                    self.assertFalse((root/'result').exists())
                else:
                    result = a.evaluate(contract, committed, arm_root, a.pin(arm_bytes), private, root/'result')
                    self.assertEqual(events[6400], ('private', 6400))
                    self.assertEqual(result['scores']['participant_macro_balanced_accuracy'], .5)
                    self.assertAlmostEqual(result['scores']['participant_macro_natural_log_loss'], math.log(2))
                    self.assertEqual(result['coverage_summary']['no_shared_support_queries'], 6400)
                    self.assertEqual(result['coverage_summary']['baseline_mean_coverage'], [1., 1.])
                    self.assertEqual(result['coverage_summary']['feature_defined_queries'], [0]*30)
                    global WRITE_BYTES
                    WRITE_BYTES += (root/'result/RESULT.json').stat().st_size
            self.assertEqual(sum(event[0] == 'admitted' for event in events), 6400)
            self.assertEqual(events[-1], ('closed', 0))

    def test_evaluate_all6400_admitted_before_private_with_coverage(self):
        self.exercise()

    def test_last_case_quality_tamper_keeps_lazy_private_unopened(self):
        self.exercise(tamper=True)


class CapturedChildControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=HERE.parent)
        cls.root = Path(cls.temp.name)
        cls.ref = MODULES['reference']
        demos = [generated_png(v) for v in (-20, 20, -20, 20)]
        features = [cls.ref.extract_features(cls.ref.decode_png(b)) for b in demos]
        model = cls.ref.fit_features(features, [a.pin(b)['sha256'] for b in demos], profile=a.IMAGE_PROFILE)
        cls.model = cls.root/'MODEL.json'; write(cls.model, cls.ref.json_bytes(model))
        cls.query = cls.root/'QUERY.png'; write(cls.query, generated_png(20))
        cls.client = cls.root/'CLIENT.py'; write(cls.client, (HERE/'client.py').read_bytes())
        cls.contract = {'algorithm': {'path': str(MODULES['algorithm_path']), 'file': a.ALGORITHM},
            'model': {'path': str(cls.model), 'file': a.pin(cls.model.read_bytes())},
            'client': {'path': str(cls.client), 'file': a.pin(cls.client.read_bytes())},
            'limits': {'run': {'episode_work_seconds': 5, 'episode_cleanup_seconds': 3}}}
        cls.counter = 0

    @classmethod
    def tearDownClass(cls):
        global WRITE_BYTES
        WRITE_BYTES += sum(p.stat().st_size for p in cls.root.rglob('*') if p.is_file())
        cls.temp.cleanup()

    def capture(self, context, client=None, *, generated=False):
        type(self).counter += 1; directory = self.root/f'capture-{self.counter}'
        budget = MODULES['pair'].Budget(16*1024**2, 1024**2, time.monotonic()+20)
        modules = dict(MODULES['capture'])
        modules['wire'] = a.image_wire(modules['wire'], [self.contract['algorithm']['path'],
            self.contract['model']['path'], a.decode(context['body'])['image']['path']])
        facade = types.SimpleNamespace(ordinary_path=a.ordinary, context_frame=a.context_frame,
            PREFIX=struct.Struct('>I'), need=a.need, pin=a.pin, encode=a.encode, write=a.write)
        envelope, end = modules['episode'].episode(facade, context, a.CONDITION, directory,
            client or self.client, sys.executable, {'episode_work_seconds': 5, 'episode_cleanup_seconds': 3},
            time.monotonic()+10, modules, budget, generated_protocol_only=generated)
        return directory, envelope, end, budget

    def context(self):
        return a.image_context(ids()[0], self.query, a.pin(self.query.read_bytes()), self.contract)

    @unittest.skipUnless(sys.platform == 'darwin' and Path('/usr/bin/sandbox-exec').exists(), 'macOS sandbox only')
    def test_generated_pixels_use_real_sandbox_capture_and_successor_cli(self):
        context = self.context(); directory, envelope, end, budget = self.capture(context)
        p, end_pin = a.episode_files(directory, context, self.contract, MODULES, budget)
        self.assertGreater(p['target_probability'], .5);
        self.assertFalse(p['quality']['no_shared_support']); self.assertEqual(end_pin, a.pin((directory/'END.json').read_bytes()))
        self.assertTrue(end['owned_cleanup']['cleanup_complete'])
        self.assertFalse(end['generated_protocol_only'])
        # A content/identity mismatch is rejected even though process closure is valid.
        changed = dict(context, context_sha256='0'*64)
        with self.assertRaises(ValueError): a.episode_files(directory, changed, self.contract, MODULES, budget)

    @unittest.skipUnless(sys.platform == 'darwin' and Path('/usr/bin/sandbox-exec').exists(), 'macOS sandbox only')
    def test_zero_support_real_capture_retains_30feature_audit(self):
        query = self.root/'ZERO.png'; write(query, generated_png(None))
        context = a.image_context(ids()[1], query, a.pin(query.read_bytes()), self.contract)
        directory, envelope, end, budget = self.capture(context)
        response, _ = a.episode_files(directory, context, self.contract, MODULES, budget)
        self.assertEqual(response['target_probability'], .5)
        self.assertIs(response['quality']['no_shared_support'], True)
        self.assertEqual(response['quality']['coverage'], [0.] * 30)
        self.assertEqual(response['quality']['baseline_coverage'], [1., 1.])
        self.assertEqual(end['returncode'], 0)

    def test_invalid_model_refuses_before_nonexistent_query_access(self):
        bad = self.root/'BAD_MODEL.json'; write(bad, b'{}')
        bad_contract = copy.deepcopy(self.contract)
        bad_contract['model'] = {'path': str(bad), 'file': a.pin(b'{}')}
        context = a.image_context(ids()[0], self.root/'NONEXISTENT.png', a.pin(b'x'), bad_contract)
        directory, envelope, end, _ = self.capture(context, generated=True)
        stderr = (directory/'STDERR.bin').read_text()
        self.assertEqual(envelope['status'], 'error')
        self.assertIn('invalid model fields', stderr)
        self.assertNotIn('FileNotFoundError', stderr)
        self.assertTrue(end['owned_cleanup']['cleanup_complete'])

    def test_extra_stdout_rejected_and_owned_child_reaped(self):
        client = self.root/'EXTRA.py'
        quality = {'coverage': [0.] * 30, 'baseline_coverage': [1., 1.],
            'shared_weights': [0.] * 30, 'shared_support_fraction': 0., 'no_shared_support': True}
        code = ('import sys,struct,json\nh=sys.stdin.buffer.read(4);n=struct.unpack(">I",h)[0];'
            'c=json.loads(sys.stdin.buffer.read(n));r=json.dumps({"trial_id":c["trial_id"],'
            '"target_probability":0.5,"quality":' + repr(quality) + '}).encode();'
            'sys.stdout.buffer.write(struct.pack(">I",len(r))+r+b"X");sys.stdout.buffer.flush()\n')
        write(client, code.encode())
        directory, envelope, end, _ = self.capture(self.context(), client, generated=True)
        self.assertEqual(envelope['status'], 'error'); self.assertIsNone(envelope['response'])
        self.assertEqual(envelope['error'], 'extra_stdout_after_first_response')
        self.assertTrue(end['owned_cleanup']['cleanup_complete'])

    def test_generated_capture_can_never_enter_authentic_admission(self):
        context = self.context(); directory, envelope, end, budget = self.capture(context, generated=True)
        self.assertEqual(envelope['status'], 'ok')
        with self.assertRaisesRegex(ValueError, 'closure'):
            a.accept_capture(context, envelope, end, (directory/'INPUT.bin').read_bytes(),
                (directory/'OUTPUT.bin').read_bytes(), (directory/'STDERR.bin').read_bytes(), b'', b'', MODULES)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--repository-root', required=True)
    parser.add_argument('--scratch-root', type=Path, required=True)
    parser.add_argument('--case', action='append')
    args = parser.parse_args()
    MODULES = a.dependencies(args.repository_root)
    a.need(args.scratch_root.is_absolute(), 'Absolute scratch directory required')
    SCRATCH_ROOT = a.ordinary(args.scratch_root.resolve(strict=True))
    a.need(SCRATCH_ROOT.is_dir() and all(
        not SCRATCH_ROOT.is_relative_to(root) and not root.is_relative_to(SCRATCH_ROOT)
        for root in (HERE, MODULES['root'])), 'Scratch directory must be disjoint from source roots')
    suite = (unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name, sys.modules[__name__])
             for name in args.case) if args.case else unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'generated_only': True, 'tests': result.testsRun, 'failures': len(result.failures),
        'errors': len(result.errors), 'skipped': len(result.skipped), 'cumulative_generated_write_upper_bytes': WRITE_BYTES,
        'authentic_packets_opened': 0, 'authentic_predictions': 0, 'private_targets_opened': 0}))
    raise SystemExit(not result.wasSuccessful())
