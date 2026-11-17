"""Generated software controls. No EDF/H5 parser, scientific array, or model.

Generic kernel fixtures are deliberately two-record/two-person worlds. A
separate in-memory control uses all 686 public filenames with generated values
through the unchanged original view code and actual detector projection seam.
Neither is evidence of authentic preparation or EEG detection performance.
"""
import copy
import hashlib
import hmac
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import original
import stream

_control_path = os.environ.get('NEURAL010_CONTROL_ROOT')
CONTROL_ROOT = Path(_control_path if _control_path else tempfile.mkdtemp(prefix='neural010-generated-')).resolve()
CONTROL_ROOT.mkdir(exist_ok=True)
WRITES = {'os_write_bytes': 0, 'fixture_write_bytes': 0}
REAL_WRITE = os.write


def counted_write(fd, body):
    n = REAL_WRITE(fd, body)
    WRITES['os_write_bytes'] += n
    return n


def fixture_write(p, body):
    p.write_bytes(body)
    WRITES['fixture_write_bytes'] += len(body)


class Generated:
    expected_records = 2
    expected_people = 2
    expected_views = 2
    def __init__(self):
        self.data = [b'generated input A\n', b'generated input B\n']
        self.rows = [{'path': f'generated{i}/record', **original.pin(body)} for i, body in enumerate(self.data)]
        self.bindings = [{'source_path': r['path'], 'recording_id': f'{i + 1:024x}',
                          'patient_id': f'{i + 10:024x}'} for i, r in enumerate(self.rows)]
        self.annotations = {r['path']: {'events': [[0.0, 1.0]], 'evidence': {'generated': True}} for r in self.rows}
        self.identity = {'generated_only': True, 'rows': self.rows, 'bindings': self.bindings,
                         'annotations': original.pin(original.encoded(self.annotations))}

    def project(self, source, destination, row):
        # Synthetic text is never an EDF or H5. Production CLI has no selection
        # option for this backend and cannot accept these source hashes.
        stream.put(destination, b'GENERATED PROJECTION\n' + source.read_bytes())
        return {'duration_seconds': 2, 'selected_channels': [{'label': 'FP1-F7'}, {'label': 'FP1-F7'}]}

    record = original.Original.record

    def view_documents(self, records):
        for i in range(2):
            yield {'name': f'{i + 10:024x}/final', 'TRAIN.json': original.encoded({'generated_training': 1 - i}),
                   'QUERY.json': original.encoded({'generated_query': i}), 'SUPPORT.json': b'{}', 'VALIDATION.json': None}

    def payloads(self, records):
        original.need(len(records) == 2, 'generated complete scope')
        return {'public/panel.json': original.encoded({'records': [r['panel'] for r in records]}),
                'public/metadata.json': original.encoded({'records': [r['metadata'] for r in records]}),
                'private/assessment.json': original.encoded({'records': [r['target'] for r in records]}),
                'private/SOURCE_PROVENANCE.json': original.encoded({'records': [r['provenance'] for r in records]}),
                'private/VIEWS.json': original.encoded({'views': [{'name': v['name'], 'artifacts': {
                    k: original.pin(v[k]) for k in ('TRAIN.json', 'QUERY.json', 'SUPPORT.json')
                }} for v in self.view_documents(records)]})}


class Kernel(unittest.TestCase):
    def setUp(self):
        self.base = CONTROL_ROOT / self._testMethodName
        self.base.mkdir()
        self.root, self.anchor = self.base / 'work', self.base / 'anchor'
        self.backend = Generated()
        self.inputs = []
        for i, body in enumerate(self.backend.data):
            p = self.base / f'input{i}.generated'
            fixture_write(p, body)
            self.inputs.append(p)
        self.now = [100.0]
        self.clock = lambda: self.now[0]
        self.limits = {'read_bytes': 10**10, 'write_bytes': 10**10, 'input_bytes': 10**6,
                       'attempts': 10, 'whole_seconds': 1000, 'operation_seconds': 1000,
                       'project_peak_bytes': 10**8, 'minimum_free_bytes': 1, 'max_events': 1000}
        self.pin = stream.Journal.initialize(self.root, self.anchor, self.backend, self.limits,
                                              'generated-clock', self.clock)
        self.reload()

    def reload(self):
        self.j = stream.Journal(self.root, self.anchor, self.pin, 'generated-clock', self.clock)
        self.e = stream.Engine(self.j, self.backend)

    def one(self, i=0):
        self.e.process(self.backend.rows[i]['path'], self.inputs[i])

    def all(self):
        self.one(0)
        self.one(1)

    def test_complete_publish_preserves_inputs_and_duplicates(self):
        self.all()
        self.assertFalse((self.root / 'prepared').exists())
        result = self.e.finalize()
        self.assertEqual(result['records'], 2)
        self.assertFalse(result['legacy_prepare_executed'])
        self.assertEqual(len(self.e.cleaned), 2)
        self.assertTrue(all(p.exists() for p in self.inputs))
        metadata = original.strict((self.root / 'prepared/public/metadata.json').read_bytes())
        self.assertEqual(metadata['records'][0]['channel_labels'], ['FP1-F7', 'FP1-F7'])
        self.reload()
        self.assertEqual(len(self.e.verify_completed()), 2)

    def test_partial_cannot_publish(self):
        self.one()
        with self.assertRaisesRegex(ValueError, 'complete prepared'):
            self.e.finalize()
        self.assertFalse((self.root / 'prepared').exists())
        self.assertFalse((self.root / 'pending/public/panel.json').exists())

    def test_resume_preserves_costs_and_refuses_duplicate_record(self):
        self.one()
        old = dict(self.j.total)
        self.reload()
        self.assertEqual(self.j.total, old)
        self.e.open()
        self.assertGreater(self.j.total['write_bytes'], old['write_bytes'])
        with self.assertRaisesRegex(ValueError, 'uncompleted'):
            self.one()

    def test_projection_failure_explicit_abort_fresh_attempt_and_no_refund(self):
        project = self.backend.project
        def fail(src, dst, row):
            stream.put(dst, b'generated partial')
            raise RuntimeError('injected producer failure')
        with patch.object(self.backend, 'project', fail):
            with self.assertRaises(RuntimeError):
                self.one()
        charged = dict(self.j.total)
        self.reload()
        with self.assertRaisesRegex(ValueError, 'pending attempt'):
            self.one(1)
        attempt = next(iter(self.e.attempts))
        proof = self.base / 'quiescence.generated.json'
        fixture_write(proof, b'{"generated_control_returned":true}\n')
        self.e.abort(attempt, proof, original.pin(proof.read_bytes()))
        self.assertTrue((self.root / 'work' / attempt / 'aborted-projection.h5').exists())
        self.assertTrue((self.root / 'work' / attempt / 'source.edf').exists())
        self.one()
        self.assertEqual(self.j.total['attempts'], charged['attempts'] + 1)
        self.assertGreater(self.j.total['write_bytes'], charged['write_bytes'])

    def test_wrong_source_hash_is_not_negative_or_completed(self):
        fixture_write(self.inputs[0], b'X' * len(self.backend.data[0]))
        with self.assertRaisesRegex(ValueError, 'locked source authentication'):
            self.one()
        self.reload()
        self.assertEqual(self.e.completed, {})
        attempt = next(iter(self.e.attempts))
        with self.assertRaisesRegex(ValueError, 'only committed'):
            self.e.cleanup(attempt)
        self.assertEqual(self.j.total['attempts'], 1)

    def test_cleanup_crash_after_unlink_can_resume(self):
        real_unlink = os.unlink
        def interrupt(p, *args, **kwargs):
            real_unlink(p, *args, **kwargs)
            raise RuntimeError('injected after unlink')
        with patch.object(stream.os, 'unlink', interrupt):
            with self.assertRaises(RuntimeError):
                self.one()
        self.reload()
        attempt = self.e.completed[self.backend.rows[0]['path']]
        self.assertIsNotNone(self.e.attempts[attempt]['cleanup_intent'])
        self.e.cleanup(attempt)
        self.assertIn(attempt, self.e.cleaned)

    def test_changed_owned_source_cannot_be_cleaned(self):
        with patch.object(self.e, 'cleanup', lambda _: None):
            self.one()
        self.reload()
        attempt = next(iter(self.e.completed.values()))
        p = self.root / 'work' / attempt / 'source.edf'
        p.chmod(0o600)
        fixture_write(p, b'X' * p.stat().st_size)
        with self.assertRaisesRegex(ValueError, 'exact original owned staging inode'):
            self.e.cleanup(attempt)
        self.assertTrue(p.exists())

    def test_retained_projection_tampering_fails_resume(self):
        self.one()
        p = self.e.projection(self.backend.rows[0]['path'])
        p.chmod(0o600)
        fixture_write(p, b'Y' * p.stat().st_size)
        self.reload()
        with self.assertRaisesRegex(ValueError, 'projection reauthentication'):
            self.e.verify_completed()

    def test_backend_annotation_or_key_drift_fails(self):
        changed = Generated()
        changed.identity = copy.deepcopy(changed.identity)
        changed.identity['annotations']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'same sources'):
            stream.Engine(self.j, changed)

    def test_local_prefix_rollback_rejected_by_external_anchor(self):
        self.e.open()
        final = sorted((self.root / 'journal').iterdir())[-1]
        os.rename(final, self.base / 'preserved-rolled-back-frame.json')
        with self.assertRaisesRegex(ValueError, 'anchor mismatch'):
            self.reload()

    def test_torn_frame_fails_closed(self):
        p = self.root / 'journal/00000002.json'
        fixture_write(p, b'{')
        fixture_write(self.anchor / 'journal/00000002.json', b'{')
        with self.assertRaises((ValueError, json.JSONDecodeError)):
            self.reload()

    def test_clock_domain_and_expiration_cannot_reset(self):
        with self.assertRaisesRegex(ValueError, 'clock domain'):
            stream.Journal(self.root, self.anchor, self.pin, 'different-boot', self.clock)
        self.now[0] = 1101
        with self.assertRaisesRegex(ValueError, 'deadline'):
            self.reload()

    def test_stale_writer_replay_rejected(self):
        old = stream.Journal(self.root, self.anchor, self.pin, 'generated-clock', self.clock)
        self.e.open()
        with self.assertRaisesRegex(ValueError, 'stale journal'):
            with old.locked():
                self.fail('stale lock admitted')

    def test_dangling_projection_symlink_never_writes_outside(self):
        outside = self.base / 'outside-generated'
        destination = self.e.projection(self.backend.rows[0]['path'])
        destination.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.one()
        self.assertFalse(outside.exists())

    def test_replaced_work_parent_never_creates_outside(self):
        original_work = self.root / 'work'
        os.rename(original_work, self.base / 'preserved-work')
        outside = self.base / 'outside-dir'
        outside.mkdir()
        original_work.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.one()
        self.assertEqual(list(outside.iterdir()), [])

    def test_final_rename_crash_recovery_and_view_export(self):
        self.all()
        real_append = self.j.append
        def interrupt(kind, *args, **kwargs):
            if kind == 'published':
                raise RuntimeError('injected after publication rename')
            return real_append(kind, *args, **kwargs)
        with patch.object(self.j, 'append', interrupt):
            with self.assertRaises(RuntimeError):
                self.e.finalize()
        self.reload()
        self.assertTrue((self.root / 'prepared').is_dir())
        self.assertIsNone(self.e.published)
        self.e.finalize()
        names = [v['name'] for v in self.backend.view_documents([])]
        result = self.e.export_views(names)
        self.assertEqual(len(result), 2)
        self.assertTrue((self.root / 'prepared/private/views' / names[0] / 'TRAIN.json').exists())

    def test_unknown_signal_prevents_publication(self):
        self.all()
        fixture_write(self.root / 'pending/public/signals/unexpected.generated', b'extra')
        with self.assertRaisesRegex(ValueError, 'signal publication namespace'):
            self.e.finalize()

    def test_invocation_receipt_is_create_only_and_separate(self):
        directory = self.base / 'invocations'
        directory.mkdir()
        result = stream.invocation_receipt(directory, 'one', self.root, self.anchor, 'check',
            original.pin(b'{}'), self.pin, 'generated-clock', self.clock)
        saved = original.strict((directory / 'one.json').read_bytes())
        self.assertEqual(saved['preflight_read_reserved_bytes'], 43 * 1048576)
        with self.assertRaises(FileExistsError):
            stream.invocation_receipt(directory, 'one', self.root, self.anchor, 'check',
                original.pin(b'{}'), self.pin, 'generated-clock', self.clock)
        self.assertEqual(original.pin((directory / 'one.json').read_bytes()), result)

    def test_stream_lines_are_charged_before_read_and_full_scope_publishes(self):
        body = b''.join(original.encoded({'record': r['path'], 'source': str(self.inputs[i])})
                        for i, r in enumerate(self.backend.rows))
        engine = self.e
        class CheckedInput(io.BytesIO):
            def readline(self, n):
                self.last = engine.j.events[-1]
                assert self.last['data'].get('operator_input_line') is not None
                assert self.last['charge']['read_bytes'] == 16385
                return super().readline(n)
        acknowledgments = []
        result = stream.consume_stream(self.e, CheckedInput(body), acknowledgments.append)
        self.assertEqual(result['records'], 2)
        self.assertEqual(len(acknowledgments), 2)
        old_read = self.j.total['read_bytes']
        self.e.finalize()
        self.assertGreater(self.j.total['read_bytes'], old_read)
        self.assertTrue(any('final_payloads' in e['data'] and e['charge']['read_bytes'] > 0
                            for e in self.j.events))

    def test_stream_partial_eof_retains_record_but_no_success(self):
        body = original.encoded({'record': self.backend.rows[0]['path'], 'source': str(self.inputs[0])})
        with self.assertRaisesRegex(ValueError, 'stream ended before full cohort'):
            stream.consume_stream(self.e, io.BytesIO(body), lambda _: None)
        self.assertEqual(len(self.e.completed), 1)
        self.assertFalse((self.root / 'prepared').exists())


class FullScope(unittest.TestCase):
    def test_original_semantics_full686_lazy529_and_actual_detection_projection(self):
        original_root = Path(os.environ.get('NEURAL010_ORIGINAL_ROOT',
            str(HERE.parent / 'programme-source/implementation-v1/program/preparation')))
        detection_root = Path(os.environ.get('NEURAL010_DETECTION_ROOT', str(HERE.parent / 'detection-interface-v1')))
        manifest_body = (original_root / 'SOURCE_MANIFEST.json').read_bytes()
        self.assertEqual(original.pin(manifest_body), original.MANIFEST)
        manifest = original.strict(manifest_body)
        bodies = {r['name']: (original_root / r['name']).read_bytes() for r in manifest['files']}
        for row in manifest['files']:
            self.assertEqual(original.pin(bodies[row['name']]), {k: row[k] for k in ('bytes', 'sha256')})
        entry = types.ModuleType('generated_original_entry')
        entry.__file__ = str(original_root / 'entry.py')
        exec(compile(bodies['entry.py'], entry.__file__, 'exec'), entry.__dict__)
        modules = entry.compile_captured(bodies, original_root)
        fixture = (detection_root / 'fixtures/CHBMIT_RECORDS.txt').read_bytes()
        self.assertEqual(hashlib.sha256(fixture).hexdigest(), '72b640d6a3fef4b40de255933d1403823d1655c56f93d69761105a653798fc08')
        paths = fixture.decode().splitlines()
        # Explicitly generated numerical source descriptors; production Original
        # construction and EDF conversion are never called in this control.
        backend = object.__new__(original.Original)
        backend.views = modules['views']
        backend.rows = [{'path': p, **original.pin(('GENERATED:' + p).encode())} for p in paths]
        backend.annotations = {p: {'events': [[0.0, 1.0]], 'evidence': {'generated': True}} for p in paths}
        records = []
        for row in backend.rows:
            folder = row['path'].split('/')[0]
            person = 'chb01' if folder == 'chb21' else folder
            binding = {'recording_id': hashlib.sha256(row['path'].encode()).hexdigest()[:24],
                       'patient_id': hashlib.sha256(person.encode()).hexdigest()[:24]}
            header = {'duration_seconds': 2, 'selected_channels': [{'label': 'FP1-F7'}, {'label': 'FP1-F7'}]}
            records.append(backend.record(row, binding, header, original.pin(b'GENERATED PROJECTION')))
        payloads = backend.payloads(records)
        index = original.strict(payloads['private/VIEWS.json'])
        self.assertEqual(len(index['views']), 529)
        self.assertEqual(sum('/final' in r['name'] for r in index['views']), 23)
        assessment = original.strict(payloads['private/assessment.json'])
        self.assertIs(type(assessment['records'][0]['events'][0][0]), float)
        spec = importlib.util.spec_from_file_location('generated_detection_interface', detection_root / 'interface.py')
        interface = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(interface)
        expected = {'panel': original.pin(payloads['public/panel.json']),
                    'metadata': original.pin(payloads['public/metadata.json']),
                    'provenance': original.pin(payloads['private/SOURCE_PROVENANCE.json'])}
        projected = interface.project_preparation(records_bytes=fixture,
            panel_bytes=payloads['public/panel.json'], metadata_bytes=payloads['public/metadata.json'],
            provenance_bytes=payloads['private/SOURCE_PROVENANCE.json'], expected=expected)
        support = original.strict(projected['support'])
        self.assertEqual(len(support['records']), 686)
        self.assertEqual(len({r['patient_id'] for r in support['records']}), 23)
        self.assertNotIn(b'events', projected['support'])
        self.assertNotIn(b'chb01_', projected['support'])
        self.assertEqual(original.Original.expected_records, 686)
        self.assertEqual(original.Original.expected_people, 23)


if __name__ == '__main__':
    with patch.object(stream.os, 'write', counted_write):
        program = unittest.main(exit=False, verbosity=2)
    report = {'schema': 'neural010-generated-write-accounting-v1', 'scope': 'generated-only controls',
              'writes': WRITES, 'cumulative_bytes_before_accounting_receipt': sum(WRITES.values()),
              'failures': len(program.result.failures), 'errors': len(program.result.errors),
              'tests_run': program.result.testsRun, 'authentic_payloads_read': 0, 'native_jobs': 0}
    body = original.encoded(report)
    (CONTROL_ROOT / 'WRITE_ACCOUNTING.json').write_bytes(body)
    print(json.dumps({'generated_artifact_writes_including_accounting': sum(WRITES.values()) + len(body)}, sort_keys=True))
    sys.exit(not program.result.wasSuccessful())
