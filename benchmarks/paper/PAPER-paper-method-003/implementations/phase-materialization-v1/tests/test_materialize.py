"""Full-census metadata plus separate tiny physical copy controls, never EEG.

The full orchestration control replaces ONLY phase body staging with a recorder.
Tiny physical controls exercise the unchanged real copying/staging primitive.
No full 4 GB phase export, actual arrays, Docker or candidate is executed.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


x = load('reve_phase_materializer_control', HERE / 'materialize.py')
fixture_path = HERE.parent / 'opaque-submission-v1/tests/test_adapter.py'
assert hashlib.sha256(fixture_path.read_bytes()).hexdigest() == 'de716dd790fa9e6e9456e5e66dfd0ccf1a068813a17dde26fd7734095a1dbbcf'
fixture = load('reve_phase_materializer_fixture', fixture_path)
SIZES = {row['signal']: row['shape'][0] * 64 * 800 * 8 + 128
         for row in fixture.DOCS[0]['data']['records']}
CREATED = 0
CAP = 3 * 1024**2


def write(path, body):
    global CREATED
    CREATED += len(body)
    assert CREATED <= CAP, 'focused generated fixture allocation exceeded'
    path.write_bytes(body)


def planned(destination='/generated/output', document=None):
    document = fixture.DOCS[0] if document is None else document
    return x.plan(document, document['materials_identity'], fixture.PANEL['panel_identity'], SIZES, destination)


class MetadataPlan(unittest.TestCase):
    def test_full_original_census_and_exact_physical_cost(self):
        p = planned()
        self.assertEqual([len(p['phases'][name]['mount']['files']) for name in ('development', 'test')], [536, 1805])
        self.assertEqual(p['copy_source_bytes'], 9837 * 64 * 800 * 8 + 2337 * 128 + 2 * 59729)
        self.assertEqual(p['phase_output_bytes'], p['copy_source_bytes'] + sum(
            q['mount']['files']['view.json']['bytes'] for q in p['phases'].values()))
        self.assertFalse(p['runtime_qualified']); self.assertFalse(p['scientific_qualification'])

    def test_literal_access_arms_produce_identical_phase_data(self):
        a, b = planned(), planned(document=fixture.DOCS[1])
        self.assertNotEqual(a['materials_identity'], b['materials_identity'])
        self.assertEqual(a['phases'], b['phases'])
        for phase in a['phases'].values():
            self.assertNotIn('materials_identity', phase['view'])
            self.assertNotIn('paper.pdf', phase['mount']['files'])
            self.assertNotIn('official-code.tar.gz', phase['mount']['files'])
        self.assertTrue(all('labels' not in row and 'participant' not in row
                            for row in a['phases']['test']['view']['records']))

    def test_selected_identity_and_extent_roster_refusal(self):
        for material, panel in [('0' * 64, fixture.PANEL['panel_identity']),
                                (fixture.DOCS[0]['materials_identity'], '0' * 64)]:
            with self.assertRaises(ValueError):
                x.plan(fixture.DOCS[0], material, panel, SIZES, '/generated/output')
        for changed in ({**SIZES, 'private/labels': 1}, {k: v for i, (k, v) in enumerate(SIZES.items()) if i}):
            with self.assertRaises(ValueError):
                x.plan(fixture.DOCS[0], fixture.DOCS[0]['materials_identity'], fixture.PANEL['panel_identity'], changed, '/generated/output')

    def test_full_orchestration_binds_exact_two_phases_without_copying_arrays(self):
        global CREATED
        with tempfile.TemporaryDirectory(prefix='reve-phase-metadata-') as temp:
            root = Path(temp).resolve(); source = root / 'input'; source.mkdir()
            body = x.canonical(fixture.DOCS[0]); write(source / 'materials.json', body)
            output = root / 'output'; calls = []
            original = x.ordinary
            def sizes_only(path):
                if path.parent == source / 'signals':
                    return SimpleNamespace(st_size=SIZES[str(path.relative_to(source))])
                return original(path)
            def record_phase(src, dst, phase, meter):
                calls.append((src, dst, deepcopy(phase)))
            with patch.object(x, 'ordinary', side_effect=sizes_only), patch.object(x, '_stage_phase', side_effect=record_phase):
                result = x.materialize(source, output, expected_materials_identity=fixture.DOCS[0]['materials_identity'],
                    expected_panel_identity=fixture.PANEL['panel_identity'], read_bytes=10*1024**3,
                    write_bytes=10*1024**3, wall_seconds=120)
            receipt_bytes = (output / 'MANIFEST.json').read_bytes(); CREATED += len(receipt_bytes)
            self.assertLessEqual(CREATED, CAP)
            self.assertEqual([c[1].name for c in calls], ['development', 'test'])
            self.assertEqual([len(c[2]['mount']['files']) for c in calls], [536, 1805])
            self.assertEqual(result['manifest'], x.pin(receipt_bytes))
            self.assertEqual(result['logical_read_bytes'], len(body))
            self.assertEqual(result['logical_write_bytes'], len(receipt_bytes))
            self.assertFalse((output / 'MANIFEST.pending.json').exists())
            self.assertEqual((output / 'MANIFEST.json').stat().st_nlink, 1)
            receipt = json.loads(receipt_bytes)
            self.assertEqual(receipt['counts']['test'], 1803)
            self.assertFalse(receipt['runtime_qualified'])
            self.assertFalse(receipt['participant_execution_performed'])
            failed = root / 'failed-output'
            with (patch.object(x, 'ordinary', side_effect=sizes_only),
                  patch.object(x, '_stage_phase', side_effect=record_phase),
                  patch.object(x.os, 'rename', side_effect=OSError(5, 'generated publication I/O failure')),
                  self.assertRaises(x.MaterializationFailure) as raised):
                x.materialize(source, failed, expected_materials_identity=fixture.DOCS[0]['materials_identity'],
                    expected_panel_identity=fixture.PANEL['panel_identity'], read_bytes=10*1024**3,
                    write_bytes=10*1024**3, wall_seconds=120)
            pending = (failed / 'MANIFEST.pending.json').read_bytes(); CREATED += len(pending)
            self.assertLessEqual(CREATED, CAP)
            self.assertFalse((failed / 'MANIFEST.json').exists())
            self.assertEqual(raised.exception.detail['logical_read_bytes'], len(body))
            self.assertEqual(raised.exception.detail['logical_write_bytes'], len(pending))
            self.assertTrue(raised.exception.detail['partial_output_must_not_be_used'])
            self.assertEqual(raised.exception.detail['errno'], 5)
            self.assertEqual(raised.exception.detail['strerror'], 'generated publication I/O failure')
            self.assertEqual(raised.exception.detail['stage'], 'completion_publication')


class PhysicalCopy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='reve-phase-files-')
        self.root = Path(self.tmp.name).resolve()
        self.src = self.root / 'source'; self.src.mkdir()
        self.dest = self.root / 'dest'; self.dest.mkdir()

    def tearDown(self):
        for path in self.root.rglob('*'):
            if path.is_dir() and not path.is_symlink(): path.chmod(0o700)
        self.tmp.cleanup()

    def test_real_streaming_copy_checks_hash_extent_and_private_publication(self):
        global CREATED
        body = bytes(range(256)) * 517
        write(self.src / 'signal', body)
        meter = x.Meter(len(body), len(body), 30)
        x._copy_verified(self.src / 'signal', self.dest / 'signal', x.pin(body), meter)
        CREATED += len(body)
        self.assertEqual((self.dest / 'signal').read_bytes(), body)
        self.assertEqual((meter.read_used, meter.write_used), (len(body), len(body)))
        self.assertEqual(stat.S_IMODE((self.dest / 'signal').stat().st_mode), 0o444)

    def test_hash_failure_retains_partial_output_and_cost(self):
        global CREATED
        body = b'actual generated file, not EEG'
        write(self.src / 'signal', body); meter = x.Meter(1000, 1000, 30)
        with self.assertRaisesRegex(x.Refusal, 'hash mismatch'):
            x._copy_verified(self.src / 'signal', self.dest / 'signal', {'bytes': len(body), 'sha256': '0'*64}, meter)
        CREATED += len(body)
        self.assertEqual((self.dest / 'signal').read_bytes(), body)
        self.assertEqual((meter.read_used, meter.write_used), (len(body), len(body)))
        self.assertEqual(stat.S_IMODE((self.dest / 'signal').stat().st_mode), 0o600)

    def test_source_aliases_and_destination_collision_are_refused(self):
        body = b'generated'; write(self.src / 'signal', body)
        (self.src / 'symlink').symlink_to(self.src / 'signal')
        with self.assertRaises(x.Refusal):
            x._copy_verified(self.src / 'symlink', self.dest / 'signal', x.pin(body), x.Meter(100,100,30))
        os.link(self.src / 'signal', self.src / 'alias')
        with self.assertRaises(x.Refusal):
            x._copy_verified(self.src / 'signal', self.dest / 'signal', x.pin(body), x.Meter(100,100,30))
        (self.src / 'alias').unlink()
        write(self.dest / 'signal', b'existing')
        with self.assertRaises(FileExistsError):
            x._copy_verified(self.src / 'signal', self.dest / 'signal', x.pin(body), x.Meter(100,100,30))
        self.assertEqual((self.dest / 'signal').read_bytes(), b'existing')

    def test_source_change_is_detected_before_acceptance(self):
        global CREATED
        body = b'generated'; write(self.src / 'signal', body)
        meter = x.Meter(100,100,30); original = meter.write
        def mutate(count):
            write(self.src / 'signal', b'mutated!!'); original(count)
        with patch.object(meter, 'write', side_effect=mutate), self.assertRaisesRegex(x.Refusal, 'mutated during copy'):
            x._copy_verified(self.src / 'signal', self.dest / 'signal', x.pin(body), meter)
        CREATED += len(body)
        self.assertEqual(meter.write_used, len(body))

    def test_no_copy_when_cumulative_budget_or_clock_exhausted(self):
        body = b'generated'; write(self.src / 'signal', body)
        for meter in (x.Meter(len(body)-1,100,30), x.Meter(100,len(body)-1,30)):
            with self.assertRaisesRegex(x.Refusal, 'I/O allowance'):
                x._copy_verified(self.src / 'signal', self.dest / 'signal', x.pin(body), meter)
        meter = x.Meter(100,100,30); meter.deadline = 0
        with self.assertRaisesRegex(x.Refusal, 'wall allowance'):
            x._copy_verified(self.src / 'signal', self.dest / 'signal', x.pin(body), meter)
        self.assertFalse((self.dest / 'signal').exists())

    def test_actual_small_phase_has_only_closed_files(self):
        global CREATED
        (self.src / 'signals').mkdir()
        blobs = {'positions.json': b'generated geometry', 'signals/a.npy': b'generated first bytes',
                 'signals/b.npy': b'generated distinct second bytes'}
        for name, body in blobs.items(): write(self.src / name, body)
        write(self.src / 'private-labels.json', b'must not copy')
        view = {'generated_primitive_control': True}
        phase_root = self.dest / 'phase'
        phase = {'view': view, 'mount': {'path': str(phase_root),
                 'files': {'view.json': x.pin(x.canonical(view)), **{n: x.pin(b) for n,b in blobs.items()}}}}
        meter = x.Meter(10000,10000,30)
        x._stage_phase(self.src, phase_root, phase, meter)
        CREATED += meter.write_used
        self.assertEqual({str(p.relative_to(phase_root)) for p in phase_root.rglob('*') if p.is_file()}, set(phase['mount']['files']))
        self.assertEqual(stat.S_IMODE(phase_root.stat().st_mode), 0o555)
        self.assertEqual(stat.S_IMODE((phase_root/'signals').stat().st_mode), 0o555)
        self.assertFalse((phase_root/'private-labels.json').exists())
        self.assertEqual(meter.read_used, sum(len(b) for b in blobs.values()))

    def test_phase_path_or_view_pin_change_refused_before_creation(self):
        target = self.dest / 'phase'
        for p in ({'view': {}, 'mount': {'path': '/different', 'files': {'view.json': x.pin(b'{}\n')}}},
                  {'view': {'changed': True}, 'mount': {'path': str(target), 'files': {'view.json': x.pin(b'{}\n')}}}):
            with self.assertRaises(x.Refusal): x._stage_phase(self.src, target, p, x.Meter(1000,1000,30))
        self.assertFalse(target.exists())

    def test_manifest_duplicate_keys_and_failed_operation_cost_retained(self):
        write(self.src / 'materials.json', b'{"duplicate":1,"duplicate":2}')
        target = self.dest / 'output'
        self.dest.chmod(0o700)
        with self.assertRaises(x.MaterializationFailure) as raised:
            x.materialize(self.src, target, expected_materials_identity='0'*64,
                          expected_panel_identity='0'*64, read_bytes=1000,write_bytes=1000,wall_seconds=30)
        self.assertEqual(raised.exception.detail['logical_read_bytes'], 29)
        self.assertEqual(raised.exception.detail['logical_write_bytes'], 0)
        self.assertTrue(raised.exception.detail['partial_output_must_not_be_used'])
        self.assertFalse(target.exists())

    def test_symlink_ancestor_and_nonprivate_output_parent_refused(self):
        link = self.root / 'linked'; link.symlink_to(self.src, target_is_directory=True)
        with self.assertRaises(x.Refusal): x.directory(link)
        self.dest.chmod(0o755)
        with self.assertRaises(x.MaterializationFailure) as raised:
            x.materialize(self.src, self.dest/'output', expected_materials_identity='0'*64,
                          expected_panel_identity='0'*64, read_bytes=1000,write_bytes=1000,wall_seconds=30)
        self.assertIn('private parent', raised.exception.detail['reason'])
        self.assertEqual(raised.exception.detail['logical_read_bytes'], 0)

    def test_double_root_slash_alias_refused_before_any_read(self):
        with self.assertRaises(x.Refusal): x.directory('//' + str(self.src).lstrip('/'))
        self.src.chmod(0o700)
        with self.assertRaises(x.MaterializationFailure) as raised:
            x.materialize(self.src, Path('//' + str(self.src/'nested').lstrip('/')),
                          expected_materials_identity='0'*64, expected_panel_identity='0'*64,
                          read_bytes=1000,write_bytes=1000,wall_seconds=30)
        self.assertEqual(raised.exception.detail['logical_read_bytes'], 0)
        self.assertFalse((self.src/'nested').exists())

    def test_physical_parent_alias_refused_despite_distinct_spelling(self):
        source_stat = self.src.stat()
        original = Path.stat
        def alias(path, *args, **kwargs):
            return source_stat if path == self.dest else original(path, *args, **kwargs)
        with patch.object(Path, 'stat', alias), self.assertRaisesRegex(x.Refusal, 'physical descendants'):
            x.disjoint_parent(self.src, self.dest)


if __name__ == '__main__':
    try:
        unittest.main(verbosity=2)
    finally:
        print(json.dumps({'generated_cumulative_file_write_bytes': CREATED,
                          'full_phase_body_copy_executed': False, 'authentic_arrays_read': 0}))
