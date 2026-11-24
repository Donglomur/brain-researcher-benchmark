"""Generated correctness controls; no authentic packet/model/target access."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import resource
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('adaptive_observation_test_subject', HERE / 'observation.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
MODULES = None
SCRATCH = None
WRITE_BYTES = READ_BYTES = 0


IDS = tuple(f'q-{i:032x}' for i in range(6400))


def ids():
    return IDS


def record(cz=0, pz=0, demonstration=None):
    out = {'trial_id': ids()[0], 'channels': [[cz] * 1024, [pz] * 1024]}
    if demonstration is not None:
        out.update(trial_id=f'generated-demo-{demonstration}', target=a.DEMO_LABELS[demonstration])
    return out


def write_generated(path, body):
    global WRITE_BYTES
    if path.exists():
        path.chmod(0o600)
    path.write_bytes(body)
    WRITE_BYTES += len(body)


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.root = Path(self.temp.name)
        self.budget = a.Budget(64 * 1024**2, 4 * 1024**2, 40)

    def tearDown(self):
        global WRITE_BYTES, READ_BYTES
        WRITE_BYTES += self.budget.written
        READ_BYTES += self.budget.read
        self.temp.cleanup()

    def observe(self, source, demo=None, name='record'):
        path = self.root / name
        value, expected = a.observe_record(source, demo, path, MODULES, self.budget)
        audited, _ = a.audit_record(path, expected, source['trial_id'], demo, MODULES, self.budget)
        self.assertEqual(value, audited)
        return path, value, expected

    def test_exact_boundary_is_unclipped_first20(self):
        path, result, expected = self.observe(record(60, -60))
        self.assertEqual(result['selected_gain'], 20)
        self.assertEqual(len(result['attempts']), 1)
        projection = a.participant_projection(path, expected, ids()[0], None, MODULES, self.budget)
        self.assertEqual(projection['outcome'], 'unclipped')
        self.assertEqual(projection['attempts'][0]['resolution']['native_units_per_vertical_pixel'], 20 / 30)

    def test_one_channel_clipping_and_first50(self):
        path, result, _ = self.observe(record(61, 0))
        self.assertEqual([r['index'] for r in result['attempts']], [0, 1])
        self.assertEqual(result['selected_gain'], 50)
        view = a.decode((path / 'VIEW-0.json').read_bytes())
        self.assertEqual([c['clipped'] for c in view['warning_evidence']['channels']], [True, False])

    def test_other_channel_requires_all_prior_gains(self):
        _, result, _ = self.observe(record(0, 301))
        self.assertEqual(result['selected_gain'], 200)
        self.assertEqual(len(result['attempts']), 4)

    def test_cap_retains_clipped_terminal_and_all_six_images(self):
        path, result, _ = self.observe(record(3001, -1e308))
        self.assertEqual(result['selected_gain'], 1000)
        self.assertEqual(result['outcome'], 'cap_clipped')
        self.assertEqual(len(result['attempts']), 6)
        self.assertTrue((path / 'FRAME-5.png').exists())

    def test_same_rule_for_four_known_demo_labels_and_unlabelled_query(self):
        choices = [self.observe(record(61, 0, i), i, f'demo-{i}')[1]['selected_gain'] for i in range(4)]
        choices.append(self.observe(record(61, 0), name='query')[1]['selected_gain'])
        self.assertEqual(choices, [50] * 5)

    def test_warning_pixel_corruption_refuses_instead_of_assuming_visibility(self):
        path, _, _ = self.observe(record(61, 0))
        codec = MODULES['codec']
        scan = bytearray(codec.scanlines((path / 'FRAME-0.png').read_bytes()))
        scan[185 * 4201 + 1 + 1030 * 3] = 0
        png = a.original_png(scan, codec)
        with self.assertRaisesRegex(ValueError, 'warning pixels'):
            a.warning_evidence(png, MODULES)

    def test_png_decoder_rejects_crc_shape_and_trailing_payload(self):
        path, _, _ = self.observe(record())
        body = (path / 'FRAME-0.png').read_bytes()
        for bad in (b'not png', body + b'raw payload', body[:30] + bytes([body[30] ^ 1]) + body[31:]):
            with self.subTest(size=len(bad)), self.assertRaises(ValueError):
                a.warning_evidence(bad, MODULES)

    def test_image_and_action_pins_are_not_optional(self):
        path, _, expected = self.observe(record())
        write_generated(path / 'FRAME-0.png', b'changed')
        with self.assertRaisesRegex(ValueError, 'Frozen content'):
            a.audit_record(path, expected, ids()[0], None, MODULES, self.budget)

    def test_changed_metadata_rebound_in_inventory_still_refuses(self):
        path, result, _ = self.observe(record())
        view = a.decode((path / 'VIEW-0.json').read_bytes())
        view['display']['units_per_division'] = 50
        body = a.encode(view)
        write_generated(path / 'VIEW-0.json', body)
        result['attempts'][0]['view'] = a.pin(body)
        body = a.encode(result)
        write_generated(path / 'RECORD.json', body)
        with self.assertRaisesRegex(ValueError, 'metadata/pixel custody'):
            a.audit_record(path, a.pin(body), ids()[0], None, MODULES, self.budget)

    def test_selected_gain_and_omitted_attempt_refuse(self):
        path, result, _ = self.observe(record(61, 0))
        for mutation in ('selected', 'omitted', 'shortened'):
            bad = copy.deepcopy(result)
            if mutation == 'selected':
                bad['selected_gain'] = 100
            elif mutation == 'omitted':
                bad['attempts'] = bad['attempts'][1:]
            else:
                bad['attempts'] = bad['attempts'][:1]
            body = a.encode(bad)
            write_generated(path / 'RECORD.json', body)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                a.audit_record(path, a.pin(body), ids()[0], None, MODULES, self.budget)

    def test_projection_contains_images_metadata_only(self):
        path, _, expected = self.observe(record(61, 0))
        projection = a.participant_projection(path, expected, ids()[0], None, MODULES, self.budget)
        self.assertEqual(set(projection), {'condition', 'trial_id', 'demonstration', 'attempts',
                                          'selected_index', 'selected_gain', 'outcome'})
        text = a.encode(projection).decode()
        for forbidden in ('target_probability', 'roster', 'public_root', 'query_count', 'channels":[['):
            self.assertNotIn(forbidden, text)
        self.assertEqual(projection['attempts'][0]['state']['channels'], ['Cz', 'Pz'])

    def test_malformed_raw_inputs_fail_before_any_render_or_directory(self):
        sources = []
        for value in (float('nan'), float('inf'), True, '0'):
            sources.append(record(value, 0))
        bad = record(); bad['channels'][0].pop(); sources.append(bad)
        bad = record(); bad['target'] = 0; sources.append(bad)
        bad = record(); bad['trial_id'] = '../outside'; sources.append(bad)
        for i, source in enumerate(sources):
            with self.subTest(i=i), self.assertRaises(ValueError):
                a.observe_record(source, None, self.root / f'bad-{i}', MODULES, self.budget)
            self.assertFalse((self.root / f'bad-{i}').exists())
        for body in (b'{"a":1,"a":2}', b'{"a":NaN}'):
            with self.assertRaises(ValueError): a.decode(body)

    def test_complete_inventory_admits_only_original6400_and_four(self):
        p = a.pin(b'generated')
        value = {'schema': 'erp-adaptive-observation-complete-v1', 'status': 'complete_observation_only',
                 'condition': a.CONDITION, 'intent': p,
                 'demos': [{'ordinal': i, 'trial_id': f'd-{i}', 'record': p} for i in range(4)],
                 'queries': [{'ordinal': i, 'trial_id': key, 'record': p} for i, key in enumerate(ids())],
                 'private_target_reads': 0, 'predictions': 0, 'scoring_performed': False}
        a.validate_inventory(value)
        for mutation in ('subset400', 'missing_demo', 'duplicate', 'order', 'extra', 'prediction'):
            bad = copy.deepcopy(value)
            if mutation == 'subset400': bad['queries'] = bad['queries'][:400]
            elif mutation == 'missing_demo': bad['demos'].pop()
            elif mutation == 'duplicate': bad['queries'][3]['trial_id'] = bad['queries'][2]['trial_id']
            elif mutation == 'order': bad['queries'][3]['ordinal'] = 4
            elif mutation == 'extra': bad['queries'][3]['target'] = 0
            else: bad['predictions'] = 1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): a.validate_inventory(bad)

    def test_original_manifest_admission_failure_retained_without_queries(self):
        public = self.root / 'public'; public.mkdir()
        write_generated(public / 'PACKET.json', b'{}')
        with self.assertRaises(ValueError):
            a.capture(public, self.root / 'capture', MODULES, self.budget)
        failed = a.decode((self.root / 'capture' / 'FAILED.json').read_bytes())
        self.assertEqual(failed['completed_queries'], 0)
        self.assertEqual(failed['uncompleted_queries'], 6400)
        self.assertFalse((self.root / 'capture' / 'COMPLETE.json').exists())

    def test_real_packet_metadata_and_single_query_path_generated_only(self):
        # Full32 metadata/spans are real-path. Other generated spans are newline
        # placeholders, deliberately malformed on access; never a valid population.
        c = MODULES['consumer']
        public = self.root / 'public'; public.mkdir(); (public / 'queries').mkdir()
        members = {'demonstrations.json': a.encode([record(0, 0, i) for i in range(4)]),
                   'prompt.txt': (c.NO_TOOLS + ' {{demonstrations_json}} {{query_json}}').encode(),
                   'response_schema.json': b'{}'}
        files = {name: a.pin(body) for name, body in members.items()}
        rows = []
        one = a.encode(record())
        for person in range(32):
            name = f'queries/p-{person:024x}.jsonl'
            body = (one + b'\n' * 199) if person == 0 else b'\n' * 200
            files[name] = a.pin(body)
            write_generated(public / name, body)
            offset = 0
            for j in range(200):
                part = one if person == 0 and j == 0 else b'\n'
                rows.append({'trial_id': ids()[person * 200 + j], 'path': name, 'offset': offset, **a.pin(part)})
                offset += len(part)
        members['roster.json'] = a.encode(rows)
        files['roster.json'] = a.pin(members['roster.json'])
        manifest = {'schema': 'erp-core-full32-public-packet-v1', 'benchmark_id': 'NEURAL-077',
                    'condition_id': c.CONDITION_ID, 'people': 32, 'query_count': 6400, 'demonstration_count': 4,
                    'natural_class_prior_supplied': False, 'files': files}
        body = a.encode(manifest); write_generated(public / 'PACKET.json', body)
        for name, content in members.items(): write_generated(public / name, content)
        generated_pins = {name: files[name] for name in c.LEGACY_PINS}
        with patch.object(c, 'LEGACY_PINS', generated_pins):
            with c.PacketSession(public, a.pin(body), budget=self.budget) as session:
                self.assertEqual(session.trial_ids, ids())
                self.assertEqual(len(session.demonstration_records()), 4)
                self.observe(session.query_record(ids()[0]))
                with self.assertRaises(ValueError): session.query_record(ids()[1])
            # A missing second query must preserve all previous real renders.
            with patch.object(a, 'MANIFEST', a.pin(body)), self.assertRaises(ValueError):
                a.capture(public, self.root / 'capture', MODULES, self.budget)
        failed = a.decode((self.root / 'capture' / 'FAILED.json').read_bytes())
        self.assertEqual((failed['completed_demonstrations'], failed['completed_queries']), (4, 1))
        self.assertEqual(failed['uncompleted_queries'], 6399)
        self.assertTrue((self.root / 'capture' / 'query-0000' / 'RECORD.json').exists())
        self.assertFalse((self.root / 'capture' / 'COMPLETE.json').exists())

    def test_symlink_and_file_pin_and_resource_limits(self):
        file = self.root / 'file'; write_generated(file, b'data')
        link = self.root / 'link'; link.symlink_to(file)
        with self.assertRaises(ValueError): a.read(link, 100)
        with self.assertRaises(ValueError): a.read(file, 100, a.pin(b'changed'))
        budget = a.Budget(3, 8192, 1)
        with self.assertRaisesRegex(ValueError, 'read cap'): a.read(file, 100, budget=budget)
        with self.assertRaisesRegex(ValueError, 'Artifact cap'): a.write(self.root / 'refused', b'x', budget)
        self.assertFalse((self.root / 'refused').exists())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository-root', required=True)
    parser.add_argument('--scratch-root', required=True)
    args = parser.parse_args()
    SCRATCH = str(Path(args.scratch_root).resolve(strict=True))
    startup = a.Budget(4 * 1024**2, 8192, 10)
    MODULES = a.dependencies(args.repository_root, startup)
    READ_BYTES += startup.read
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    print(json.dumps({'generated_only': True, 'tests': result.testsRun, 'failures': len(result.failures),
        'errors': len(result.errors), 'skipped': len(result.skipped), 'cumulative_written_bytes': WRITE_BYTES,
        'named_read_bytes': READ_BYTES, 'peak_rss_platform_units': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'platform': sys.platform, 'python': sys.version, 'authentic_inputs': 0, 'predictions': 0, 'private_targets': 0}))
    raise SystemExit(not result.wasSuccessful())
