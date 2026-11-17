"""Generated full-support metadata controls; no authentic signal or native code.

One immutable in-memory fixture contains all 686 public source filenames, 23
generated person identities, all 529 original-view pins, and generated journal
metadata. Only selected original view bodies are retained in memory. Admission
must never open any target, key, signal or training/validation body.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bridge as b

ROOT = Path(os.environ['NEURAL010_COMPAT_CONTROL_ROOT']) if 'NEURAL010_COMPAT_CONTROL_ROOT' in os.environ else Path(tempfile.mkdtemp(prefix='neural010-compat-generated-'))
ROOT.mkdir(exist_ok=True)
FIXTURE_WRITES = 0


def file_write(p, raw):
    global FIXTURE_WRITES
    p.write_bytes(raw)
    FIXTURE_WRITES += len(raw)


class MemoryIO:
    def __init__(self, files, stats, limit=256 * 1048576):
        self.files, self.stats = dict(files), dict(stats)
        self.limit, self.used, self.accesses = limit, 0, []

    def charge(self, amount):
        b.integer(amount)
        b.need(self.used + amount <= self.limit, 'generated pre-read bound')
        self.used += amount

    def prohibited(self, path):
        p = Path(path)
        return (p.name in ('assessment.json', 'TRAIN.json', 'VALIDATION.json', 'identity.key', 'source_annotations.json', 'RECEIPT.json')
                or p.suffix == '.h5')

    def capture(self, desc, role, cap=b.META_CAP):
        b.descriptor(desc, True)
        b.need(desc['bytes'] <= cap, 'bounded operand extent')
        self.charge(desc['bytes'] + 1)
        p = desc['path']
        if self.prohibited(p):
            raise AssertionError('protected body opened: ' + p)
        raw = self.files[p]
        b.need(type(raw) is bytes and b.same(b.pin(raw), b.bare(desc)), 'generated exact metadata bytes')
        self.accesses.append({'path': p, 'role': role})
        return raw

    def journal_body(self, p, role):
        p = str(p)
        raw = self.files[p]
        b.need(type(raw) is bytes and 0 < len(raw) <= b.EVENT_CAP, 'bounded journal metadata')
        self.charge(len(raw) + 1)
        self.accesses.append({'path': p, 'role': role})
        return raw

    def names(self, p):
        parent = str(p) + '/'
        return sorted(k[len(parent):] for k in self.files if k.startswith(parent) and '/' not in k[len(parent):])

    def stat_only(self, desc, role):
        b.descriptor(desc, True)
        b.need(desc['path'] in self.stats and b.same(self.stats[desc['path']], b.bare(desc)), 'generated materialized extent')
        self.accesses.append({'path': desc['path'], 'role': role, 'body_opened': False})


class Fixture:
    def __init__(self):
        self.original_root = Path(os.environ.get('NEURAL010_ORIGINAL_ROOT', str(HERE.parent / 'programme-source/implementation-v1/program/preparation')))
        self.detection_root = Path(os.environ.get('NEURAL010_DETECTION_ROOT', str(HERE.parent / 'detection-interface-v1')))
        self.streaming_root = Path(os.environ.get('NEURAL010_STREAMING_ROOT', str(HERE.parent / 'streaming-preparation-v1')))
        spec = importlib.util.spec_from_file_location('generated_original_streaming_adapter', self.streaming_root / 'original.py')
        original = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(original)
        manifest_raw = (self.original_root / 'SOURCE_MANIFEST.json').read_bytes()
        assert b.same(b.pin(manifest_raw), b.ORIGINAL_MANIFEST)
        manifest = b.parse(manifest_raw)
        bodies = {r['name']: (self.original_root / r['name']).read_bytes() for r in manifest['files']}
        for r in manifest['files']:
            assert b.same(b.pin(bodies[r['name']]), b.bare(r))
        entry = types.ModuleType('generated_preparation_entry')
        entry.__file__ = str(self.original_root / 'entry.py')
        exec(compile(bodies['entry.py'], entry.__file__, 'exec'), entry.__dict__)
        modules = entry.compile_captured(bodies, self.original_root)
        self.roster_raw = (self.detection_root / 'fixtures/CHBMIT_RECORDS.txt').read_bytes()
        self.roster = b.roster(self.roster_raw)
        self.roster_desc = {'path': '/generated/RECORDS', **b.RECORDS_PIN}
        adapter = object.__new__(original.Original)
        adapter.views = modules['views']
        adapter.rows = [{'path': p, **b.pin(('GENERATED SOURCE:' + p).encode())} for p in self.roster]
        adapter.annotations = {p: {'events': [[0.0, 1.0]], 'evidence': {'generated_only': True}} for p in self.roster}
        records, bindings = [], []
        for row in adapter.rows:
            binding = {'source_path': row['path'],
                'recording_id': hashlib.sha256(row['path'].encode()).hexdigest()[:24],
                'patient_id': hashlib.sha256(self.roster[row['path']].encode()).hexdigest()[:24]}
            bindings.append(binding)
            header = {'duration_seconds': 2, 'selected_channels': [{'label': 'FP1-F7'}, {'label': 'FP1-F7'}]}
            records.append(adapter.record(row, binding, header, b.pin(b'GENERATED PROJECTION')))
        self.payloads = adapter.payloads(records)
        self.view_doc = b.parse(self.payloads['private/VIEWS.json'])
        self.views = self.view_doc['views']
        self.selected_names = [self.views[0]['name'], self.views[1]['name']]
        self.selected_bodies = {}
        for view in adapter.view_documents(records):
            if view['name'] in self.selected_names:
                self.selected_bodies[view['name']] = view
            if len(self.selected_bodies) == 2:
                break
        self.files, self.stats = {'/generated/RECORDS': self.roster_raw}, {}
        for route, root in [('original', Path('/generated/original')), ('streaming', Path('/generated/stream/prepared'))]:
            for name, raw in self.payloads.items():
                self.files[str(root / name)] = raw
            for view in self.views:
                for name, pin in view['artifacts'].items():
                    self.stats[str(root / 'private/views' / view['name'] / name)] = pin
        self.original_receipt = {'schema': 'neural010-original-preparation-v1',
            'status': 'prepared_not_runtime_or_scientifically_qualified', 'records': 686, 'people': 23, 'source_folders': 24,
            'source_manifest': b.ORIGINAL_MANIFEST, 'source_roster': b.LOCK, 'global_assessment_release_authorized': False,
            'panel': b.pin(self.payloads['public/panel.json']), 'metadata': b.pin(self.payloads['public/metadata.json']),
            'assessment': b.pin(self.payloads['private/assessment.json']),
            'source_provenance': b.pin(self.payloads['private/SOURCE_PROVENANCE.json']), 'views': self.views,
            'vendor_sources': b.VENDOR_PIN, 'annotation_reads': b.pin(b'UNOPENED GENERATED ANNOTATION RECEIPT'),
            'actual_models_or_scores': 0, 'cost_snapshot': {'original_origin': 1.0, 'deadline': 1001.0,
                'logical_reserved_read_bytes': 1000, 'logical_reserved_write_bytes': 1000,
                'limits': {'read_bytes': 10**12, 'write_bytes': 10**12, 'whole_seconds': 1000.0,
                           'project_peak_bytes': 10**12}, 'physical_IO_or_RSS_measured': False}}
        raw = b.encoded(self.original_receipt)
        self.files['/generated/original/private/PREPARATION.json'] = raw
        common = {'schema': 'neural010-preparation-compatibility-selection-v1',
                  'records': self.roster_desc, 'selected_source_manifest': b.ORIGINAL_MANIFEST,
                  'selected_original_roster': b.LOCK}
        self.original_selection = {**common, 'route': 'original', 'public_root': '/generated/original/public',
            'private_root': '/generated/original/private',
            'receipt': {'path': '/generated/original/private/PREPARATION.json', **b.pin(raw)}}
        cases = {p.split('/')[0] for p in self.roster}
        metadata_names = {'RECORDS', 'RECORDS-WITH-SEIZURES', 'chb07_19.edf.seizures'}
        metadata_names.update(c + '-summary.txt' for c in cases)
        metadata_names.update(c + '-index.html' for c in cases)
        request = {'original_source_root': '/generated/source', 'lock_path': '/generated/lock.json',
                   'metadata_root': '/generated/metadata', 'key_path': '/generated/private/identity.key',
                   'metadata_pins': {n: b.pin(b'GENERATED METADATA') for n in metadata_names}}
        request['metadata_pins']['RECORDS'] = dict(b.RECORDS_PIN)
        identity = {'route': 'neural010-streaming-original-semantics-v1', 'lock': b.LOCK,
                    'original_source_manifest': b.ORIGINAL_MANIFEST, 'request': request, 'bindings': bindings,
                    'annotation_bytes': b.pin(b'GENERATED ANNOTATIONS')}
        limits = {k: 10**12 for k in b.COUNTERS}
        limits.update(operation_seconds=1000, whole_seconds=1000, project_peak_bytes=10**12,
                      minimum_free_bytes=1, max_events=10000)
        self.config = {'schema': 'neural010-streaming-config-v1', 'root': '/generated/stream',
            'anchor': '/generated/anchor', 'clock_domain': 'generated-clock', 'monotonic_start': 1.0,
            'monotonic_end': 1001.0, 'limits': limits, 'backend_identity': identity,
            'invocation_ledger': '/generated/invocations'}
        config_raw = b.encoded(self.config)
        self.config_pin = b.pin(config_raw)
        self.files['/generated/stream/CONFIG.json'] = config_raw
        self.files['/generated/anchor/CONFIG.json'] = config_raw
        self.events = []
        self.total = {k: 0 for k in b.COUNTERS}
        self.tip = self.config_pin['sha256']
        self.add_event('genesis', {'configuration': self.config_pin})
        for i, row in enumerate(adapter.rows):
            attempt = str(len(self.events) + 1)
            self.add_event('begin', {'record': row['path'], 'external_source': '/generated/incoming.edf'})
            source = b.bare(row)
            stamp = [1, i + 1, row['bytes'], 1, 1]
            self.add_event('staged', {'attempt': attempt, 'source': source, 'stamp': stamp})
            self.add_event('commit', {'attempt': attempt, 'receipt': b.pin(b'UNOPENED GENERATED TARGET RECEIPT')})
            self.add_event('cleanup_intent', {'attempt': attempt, 'source': source, 'stamp': stamp})
            self.add_event('cleaned', {'attempt': attempt})
        payload_pins = {k: b.pin(v) for k, v in self.payloads.items()}
        final = {'payloads': payload_pins, 'records': 686, 'people': 23, 'views': 529}
        self.add_event('final_intent', final)
        self.streaming_receipt = {'schema': 'neural010-streaming-preparation-v1',
            'status': 'complete_source_preparation_not_execution_or_scientific_qualification',
            'configuration': self.config_pin, 'records': 686, 'people': 23, 'views': 529,
            'view_materialization': 'lazy_exact_original_bytes', 'payloads': payload_pins,
            'final_intent': b.pin(b.encoded(final)), 'models_or_scores': 0,
            'legacy_prepare_executed': False, 'assessment_release_authorized': False}
        receipt_raw = b.encoded(self.streaming_receipt)
        self.files['/generated/stream/prepared/private/STREAMING_PREPARATION.json'] = receipt_raw
        self.add_event('published', {'receipt': b.pin(receipt_raw)})
        for v in self.views[:2]:
            self.add_event('view_intent', v)
            self.add_event('view_complete', v)
        self.streaming_selection = {**common, 'route': 'streaming', 'public_root': '/generated/stream/prepared/public',
            'private_root': '/generated/stream/prepared/private',
            'receipt': {'path': '/generated/stream/prepared/private/STREAMING_PREPARATION.json', **b.pin(receipt_raw)},
            'configuration': {'path': '/generated/stream/CONFIG.json', **self.config_pin},
            'workspace_root': '/generated/stream', 'anchor_root': '/generated/anchor',
            'checkpoint': {'sequence': len(self.events), 'sha256': self.tip, 'total': dict(self.total)}}
        for n, pin in b.REFERENCE_SOURCES.items():
            source_path = self.original_root.parent / n
            raw = source_path.read_bytes()
            assert b.same(b.pin(raw), pin)
            self.files[str(source_path)] = raw
        for source_path, pin in [(self.detection_root / 'interface.py', b.DETECTION_PIN),
                                 (self.detection_root.parent / 'scientific-scorer-v2/scorer.py', b.SCORER_PIN)]:
            raw = source_path.read_bytes()
            assert b.same(b.pin(raw), pin)
            self.files[str(source_path)] = raw

    def add_event(self, kind, data):
        n = len(self.events) + 1
        charge = {k: 0 for k in b.COUNTERS}
        charge['write_bytes'] = 2 * b.EVENT_CAP
        for k in b.COUNTERS: self.total[k] += charge[k]
        event = {'sequence': n, 'previous': self.tip, 'kind': kind, 'data': data,
                 'charge': charge, 'total': dict(self.total), 'clock': 1.0 + n / 10000}
        raw = b.encoded(event)
        self.files[f'/generated/stream/journal/{n:08d}.json'] = raw
        self.files[f'/generated/anchor/journal/{n:08d}.json'] = raw
        self.events.append(event)
        self.tip = b.pin(raw)['sha256']

    def io(self):
        return MemoryIO(self.files, self.stats)


FIXTURE = None


class Compatibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global FIXTURE
        if FIXTURE is None:
            FIXTURE = Fixture()

    def test_both_routes_preserve_actual_receipt_and_descriptor_geometry(self):
        for selection in (FIXTURE.original_selection, FIXTURE.streaming_selection):
            io = FIXTURE.io()
            prepared = b.admit(selection, io)
            self.assertEqual(len(prepared['rows']), 686)
            self.assertEqual(len(prepared['people']), 23)
            self.assertEqual(len(prepared['views']), 529)
            self.assertEqual(prepared['receipt_pin'], selection['receipt'])
            self.assertEqual(b.pin(b.encoded(prepared['receipt'])), b.bare(selection['receipt']))
            self.assertEqual(prepared['assessment_pin'], b.pin(FIXTURE.payloads['private/assessment.json']))
            self.assertFalse(prepared['runtime_or_scientific_qualification'])
            self.assertFalse(any(io.prohibited(r['path']) for r in io.accesses))

    def test_wrong_receipt_path_rejected_before_protected_body(self):
        for route_selection in (FIXTURE.original_selection, FIXTURE.streaming_selection):
            for filename in ('assessment.json', 'views/person/TRAIN.json', 'views/person/VALIDATION.json'):
                selection = copy.deepcopy(route_selection)
                selection['receipt']['path'] = selection['private_root'] + '/' + filename
                io = FIXTURE.io()
                with self.assertRaisesRegex(ValueError, 'receipt path before capture'):
                    b.admit(selection, io)
                self.assertEqual(io.accesses, [])

    def test_target_free_resolver_never_reads_view_labels(self):
        io = FIXTURE.io()
        prepared = b.admit(FIXTURE.streaming_selection, io)
        for name in FIXTURE.selected_names:
            descriptors = prepared['views'][name]
            self.assertIn('TRAIN.json', descriptors)
        self.assertTrue(any(r.get('body_opened') is False and r['path'].endswith('TRAIN.json') for r in io.accesses))
        with self.assertRaisesRegex(ValueError, 'materialization completion'):
            prepared['views'][FIXTURE.views[2]['name']]

    def test_require_all_views_refuses_only_two_materialized(self):
        with self.assertRaisesRegex(ValueError, 'materialization completion'):
            b.admit(FIXTURE.streaming_selection, FIXTURE.io(), require_all_views=True)

    def test_actual_reference_request_consumes_bridge_and_keeps_training_opaque(self):
        io = FIXTURE.io()
        prepared = b.admit(FIXTURE.streaming_selection, io)
        outer, _, inner = FIXTURE.selected_names[1].split('/')
        job_id = '/'.join((outer, 'matched_no_eeg', inner, '0', 'fit'))
        result = b.compose_reference_request(prepared, job_id, FIXTURE.original_root.parent,
            b.pin(b'GENERATED WORKER SOURCE'), {'max_input_bytes': 10**9}, io)
        self.assertEqual(result['request']['command'], 'fit')
        self.assertEqual(result['request']['condition'], 'matched_no_eeg')
        self.assertEqual(result['request']['records'], prepared['views'][FIXTURE.selected_names[1]]['TRAIN.json'])
        self.assertEqual(result['opaque_inputs'], [result['request']['records']['path']])
        self.assertFalse(result['native_execution_performed'])

    def test_actual_detection_interface_join_has_no_public_labels(self):
        for selection in (FIXTURE.original_selection, FIXTURE.streaming_selection):
            io = FIXTURE.io()
            prepared = b.admit(selection, io)
            result = b.export_detection(prepared, FIXTURE.detection_root, io)
            public = b.parse(result['projection']['support'])
            self.assertEqual(len(public['records']), 686)
            self.assertEqual(len({r['patient_id'] for r in public['records']}), 23)
            self.assertNotIn(b'events', result['projection']['support'])
            self.assertNotIn(b'chb01_', result['projection']['support'])
            self.assertEqual(public['records'][0]['channel_labels'], ['FP1-F7', 'FP1-F7'])
            self.assertEqual(result['preparation_receipt'], selection['receipt'])

    def test_current_checkpoint_rollback_refused(self):
        selection = copy.deepcopy(FIXTURE.streaming_selection)
        selection['checkpoint']['sequence'] -= 1
        with self.assertRaisesRegex(ValueError, 'current journal inventory'):
            b.admit(selection, FIXTURE.io())

    def test_anchor_frame_disagreement_refused(self):
        io = FIXTURE.io()
        p = '/generated/anchor/journal/00000002.json'
        io.files[p] = io.files[p].replace(b'"begin"', b'"other"')
        with self.assertRaisesRegex(ValueError, 'exact metadata bytes'):
            b.admit(FIXTURE.streaming_selection, io)

    def test_partial_or_boolean_receipt_count_refused(self):
        for value in (685, True):
            selection = copy.deepcopy(FIXTURE.streaming_selection)
            receipt = copy.deepcopy(FIXTURE.streaming_receipt)
            receipt['records'] = value
            raw = b.encoded(receipt)
            io = FIXTURE.io()
            io.files[selection['receipt']['path']] = raw
            selection['receipt'].update(b.pin(raw))
            with self.assertRaisesRegex(ValueError, 'truthful complete streaming route'):
                b.admit(selection, io)

    def test_original_receipt_requires_complete_zero_model_producer_contract(self):
        variants = []
        missing = copy.deepcopy(FIXTURE.original_receipt); missing.pop('annotation_reads'); variants.append(missing)
        extra = copy.deepcopy(FIXTURE.original_receipt); extra['invented_field'] = True; variants.append(extra)
        for count in (True, 1):
            variant = copy.deepcopy(FIXTURE.original_receipt); variant['actual_models_or_scores'] = count; variants.append(variant)
        for receipt in variants:
            raw = b.encoded(receipt)
            io = FIXTURE.io()
            selection = copy.deepcopy(FIXTURE.original_selection)
            selection['receipt'].update(b.pin(raw)); io.files[selection['receipt']['path']] = raw
            with self.assertRaises(ValueError): b.admit(selection, io)

    def test_streaming_wrong_original_roster_pin_refused_before_journal(self):
        config = copy.deepcopy(FIXTURE.config)
        config['backend_identity']['request']['metadata_pins']['RECORDS'] = b.pin(b'WRONG PUBLIC ROSTER')
        raw = b.encoded(config)
        io = FIXTURE.io(); selection = copy.deepcopy(FIXTURE.streaming_selection)
        selection['configuration'].update(b.pin(raw))
        io.files['/generated/stream/CONFIG.json'] = raw
        io.files['/generated/anchor/CONFIG.json'] = raw
        with self.assertRaisesRegex(ValueError, 'constructor public roster pin'):
            b.admit(selection, io)
        self.assertFalse(any('/journal/' in r['path'] for r in io.accesses))

    def test_view_traversal_duplicate_and_final_validation_refused(self):
        base = copy.deepcopy(FIXTURE.original_receipt)
        mutations = [lambda views: views[0].update(name='../escape'),
                     lambda views: views[1].update(name=views[0]['name']),
                     lambda views: views[0]['artifacts'].update({'VALIDATION.json': b.pin(b'GENERATED')})]
        for mutation in mutations:
            receipt = copy.deepcopy(base)
            mutation(receipt['views'])
            raw = b.encoded(receipt)
            selection = copy.deepcopy(FIXTURE.original_selection)
            selection['receipt'].update(b.pin(raw))
            io = FIXTURE.io(); io.files[selection['receipt']['path']] = raw
            with self.assertRaises(ValueError):
                b.admit(selection, io)

    def test_pre_read_budget_refuses_without_capture(self):
        io = FIXTURE.io(); io.limit = 1
        with self.assertRaisesRegex(ValueError, 'pre-read bound'):
            b.admit(FIXTURE.original_selection, io)
        self.assertEqual(io.accesses, [])

    def test_bytearray_metadata_rejected(self):
        io = FIXTURE.io()
        io.files[FIXTURE.original_selection['receipt']['path']] = bytearray(b'{}')
        with self.assertRaisesRegex(ValueError, 'exact metadata bytes'):
            b.admit(FIXTURE.original_selection, io)

    def test_fileio_rejects_symlink_before_body(self):
        directory = ROOT / self._testMethodName
        directory.mkdir()
        original = directory / 'plain.json'
        file_write(original, b'{}')
        linked = directory / 'linked.json'
        linked.symlink_to(original)
        io = b.FileIO([directory], 100)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            io.capture({'path': str(linked), **b.pin(b'{}')}, 'generated')
        self.assertEqual(io.accesses, [])


if __name__ == '__main__':
    result = unittest.main(exit=False, verbosity=2).result
    report = {'schema': 'neural010-generated-compatibility-controls-v1',
        'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'generated_fixture_payload_storage': 'in-memory only', 'generated_files_written_bytes_before_report': FIXTURE_WRITES,
        'authentic_signal_or_label_payloads_opened': 0, 'native_jobs': 0, 'models': 0}
    body = b.encoded(report)
    (ROOT / 'RESULTS.json').write_bytes(body)
    print(json.dumps({'artifact_bytes_including_result': FIXTURE_WRITES + len(body)}, sort_keys=True))
    sys.exit(not result.wasSuccessful())
