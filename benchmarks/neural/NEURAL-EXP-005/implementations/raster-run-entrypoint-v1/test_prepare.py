"""Changed prepare command only: generated in-memory sources, no authentic EEG.

The full Reference is compared at the writer boundary without being persisted.
SourceCorpus admission/census is explicitly stubbed for generated 30/31-second
fixtures; a separate control exercises the real coordinate/description refusal.
No prior optimizer or participant-process suite is replayed.
"""
import argparse
from contextlib import contextmanager, redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
R = F = None
SCRATCH = PROOF = None
WRITTEN = 0
NOTES = []
FIXTURE_SHA256 = 'd02c90329a83434894fba93ebe40baa91a0692b5de698668db2b120ce685dcf1'


def put(path, body):
    global WRITTEN
    WRITTEN += len(body)
    path.write_bytes(body)


@contextmanager
def generated_admission(*, unsupported=False, real_description=False):
    """Stub only authentic admission; retain exact checked reader functions."""
    state = {'order': [], 'owners': []}
    original_load = R._load
    patches = []

    def load(relative, imports=None):
        module = original_load(relative, imports)
        if relative == 'source-admission-v1/source_adapter.py':
            state['adapter'] = module
            F.A, F.SOURCES = module, module.load_sources()
            F.P = F.SOURCES.current

            def initialize(owner, source_root):
                state['order'].append('source_admission_fixture')
                generated = F.corpus(longer={'eeg1': 31})
                owner.__dict__.update(generated.__dict__)
                owner.reader = module.IntervalReader(owner._lookup, F.SOURCES.intake.MONTAGE)
                owner._corpus.close = lambda: state['order'].append('close')
                if unsupported:
                    owner.read_samples = lambda *args: module.SourceCorpus.read_samples(owner, *args)
                state['owners'].append(owner)

            def census(owner):
                state['order'].append('census_fixture')
                return {}

            def description(census_value, policy):
                state['order'].append('description_fixture')
                assert census_value == {} and policy == Controls.policy
                return F.description(state['owners'][-1])

            for target, name, value in ((module.SourceCorpus, '__init__', initialize),
                                        (module.SourceCorpus, 'private_census', census)):
                item = patch.object(target, name, value); item.start(); patches.append(item)
            if not real_description:
                item = patch.object(module, 'current_description', description)
                item.start(); patches.append(item)
        if relative == 'source-admission-v1/rolling_reference.py':
            state['rolling'] = module
        return module

    try:
        with patch.object(R, '_load', side_effect=load):
            yield state
    finally:
        for item in reversed(patches):
            item.stop()


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='generated-preparation-', dir=SCRATCH)
        cls.root = Path(cls.temp.name)
        adapter, rolling = R._preparation_modules()
        F.A, F.SOURCES, F.R = adapter, adapter.load_sources(), rolling
        F.P = F.SOURCES.current
        owner = F.corpus(longer={'eeg1': 31})
        desc = F.description(owner)
        cls.baseline = F.P.prepare_reference(desc, owner.read_samples, F.KEY)
        cls.policy = {'schema': 'helsinki-source-preparation-policy-v1',
                      'assessment_id': desc['assessment_id'], 'fold_seed': desc['fold_seed'],
                      'development_by_fold': desc['development_by_fold']}
        cls.policy_path, cls.key_path = cls.root / 'policy.json', cls.root / 'key.bin'
        put(cls.policy_path, R._bytes(cls.policy))
        put(cls.key_path, F.KEY)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def argv(self, output=None):
        return ['prepare', '--source-root', str(self.root / 'invented-source-not-opened'),
                '--policy', str(self.policy_path), '--policy-sha256', R.digest(self.policy),
                '--case-key', str(self.key_path), '--read-limit', '1048576',
                '--output', str(output or self.root / 'reference-not-persisted.json')]

    def test_eligible_real_command_reaches_rolling_and_preserves_full_reference_schedule(self):
        saved = []
        output = io.StringIO()
        with generated_admission() as state, redirect_stdout(output), patch.object(
                R, 'write_prepared_new', side_effect=lambda path, doc, limit: saved.append((path, deepcopy(doc), limit))):
            self.assertEqual(R.main(self.argv()), 0)
        self.assertEqual(len(saved), 1)
        report = json.loads(output.getvalue())
        self.assertEqual(report['preparation_path'], 'pinned_source_rolling')
        self.assertFalse(report['scientific_qualification'])
        self.assertEqual(report['reference_sha256'], self.baseline.reference_sha256)
        self.assertEqual(R._bytes(saved[0][1]), F.P.canonical_bytes(self.baseline.document))
        restored = R.protocol.Reference(saved[0][1], F.KEY)
        self.assertEqual(list(restored.case_rows()), list(self.baseline.case_rows()))
        self.assertEqual(R.collector.freeze_reference(restored), R.collector.freeze_reference(self.baseline))
        for fold in range(5):
            self.assertEqual(restored.partition(fold), self.baseline.partition(fold))
        self.assertEqual(state['order'], ['source_admission_fixture', 'census_fixture', 'description_fixture', 'close'])
        owner = state['owners'][0]
        self.assertIs(owner.sources, state['adapter'].load_sources())
        self.assertIs(owner.sources.current, F.P)
        self.assertTrue(owner._closed)
        NOTES.append({'control': self._testMethodName, 'path': report['preparation_path'],
                      'reference_sha256': report['reference_sha256'], 'cases': len(list(restored.case_rows())),
                      'canonical_reference_bytes': len(R._bytes(saved[0][1])),
                      'writer': 'captured in memory; no generated complete Reference persisted',
                      'admission': 'explicit generated constructor/census/description stubs; no authentic admission claim'})

    def test_unsupported_bound_reader_keeps_original_generic_result(self):
        saved = []
        output = io.StringIO()
        with generated_admission(unsupported=True), redirect_stdout(output), patch.object(
                R, 'write_prepared_new', side_effect=lambda path, doc, limit: saved.append(deepcopy(doc))):
            self.assertEqual(R.main(self.argv()), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report['preparation_path'], 'unchanged_generic')
        self.assertEqual(saved, [self.baseline.document])
        self.assertEqual(report['reference_sha256'], self.baseline.reference_sha256)
        NOTES.append({'control': self._testMethodName, 'path': report['preparation_path'], 'cases': 80})

    def test_actual_coordinate_binding_and_description_refusal_precede_helper_use(self):
        with generated_admission(real_description=True) as state, patch.object(R, 'write_prepared_new') as write:
            with self.assertRaisesRegex(ValueError, 'source census identity or scope differs'):
                R.main(self.argv())
            write.assert_not_called()
        self.assertEqual(state['order'], ['source_admission_fixture', 'census_fixture', 'close'])
        self.assertTrue(all(asset.handle.reads == 0 for asset in state['owners'][0]._corpus.assets.values()))
        self.assertFalse((self.root / 'reference-not-persisted.json').exists())
        NOTES.append({'control': self._testMethodName,
                      'binding': 'actual nested coordinate module/task/understanding/source-profile pins read; empty census rejected',
                      'generated_sample_reads': 0})

    def test_policy_key_existing_output_and_helper_pin_fail_before_source_admission(self):
        with patch.object(R, '_preparation_modules') as modules:
            with self.assertRaisesRegex(R.RunError, 'preparation_policy_changed'):
                R.prepare('unused', self.policy, F.KEY, '0' * 64)
            modules.assert_not_called()
        with generated_admission() as state:
            with self.assertRaisesRegex(ValueError, 'case key'):
                R.prepare('unused', self.policy, b'short', R.digest(self.policy))
            self.assertEqual(state['owners'], [])
        existing = self.root / 'existing.txt'; put(existing, b'keep')
        with patch.object(R, '_preparation_modules') as modules:
            with self.assertRaisesRegex(R.RunError, 'preparation_output_already_exists'):
                R.main(self.argv(existing))
            modules.assert_not_called()
        self.assertEqual(existing.read_bytes(), b'keep')
        with patch.dict(R.PREPARATION_PINS, {'source-admission-v1/rolling_reference.py': '0' * 64}):
            with self.assertRaisesRegex(ValueError, 'source hash differs'):
                R.prepare('unused', self.policy, F.KEY, R.digest(self.policy))

    def test_preparation_persistence_failure_removes_only_owned_file(self):
        global WRITTEN
        document = {'generated_only': True}
        body = R._bytes(document) + b'\n'
        failed = self.root / 'failed-write.json'
        WRITTEN += len(body)
        with patch.object(R.os, 'fsync', side_effect=OSError('generated fsync failure')):
            with self.assertRaisesRegex(OSError, 'generated fsync failure'):
                R.write_prepared_new(failed, document, 1024)
        self.assertFalse(failed.exists())
        replaced = self.root / 'replaced-write.json'

        def replace_before_failure(fd):
            replaced.unlink()
            put(replaced, b'replacement-owned-by-someone-else')
            raise OSError('generated replacement then failure')

        WRITTEN += len(body)
        with patch.object(R.os, 'fsync', side_effect=replace_before_failure):
            with self.assertRaisesRegex(OSError, 'generated replacement then failure'):
                R.write_prepared_new(replaced, document, 1024)
        self.assertEqual(replaced.read_bytes(), b'replacement-owned-by-someone-else')
        with self.assertRaises(FileExistsError):
            R.write_prepared_new(replaced, document, 1024)
        output = io.StringIO()
        with patch.object(R, 'prepare', return_value=self.baseline), patch.object(
                R, 'write_prepared_new', side_effect=OSError('generated write refusal')), redirect_stdout(output):
            with self.assertRaisesRegex(OSError, 'generated write refusal'):
                R.main(self.argv())
        self.assertEqual(output.getvalue(), '')


def main():
    global R, F, SCRATCH, PROOF
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-rolling-root', type=Path,
                        help='Construction-only accepted source locator; omit in composed-tree CI.')
    parser.add_argument('--scratch-root', type=Path)
    parser.add_argument('--proof-output', type=Path)
    parser.add_argument('--tests', nargs='*')
    args = parser.parse_args()
    SCRATCH, PROOF = args.scratch_root, args.proof_output
    spec = importlib.util.spec_from_file_location('_helsinki_preparation_controls', HERE / 'run.py')
    R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
    rolling_root = args.private_rolling_root or HERE.parent / 'source-admission-v1'
    fixture_path = rolling_root / 'test_rolling_reference.py'
    F = R.loader._module(fixture_path, R.loader.read_pinned(fixture_path, FIXTURE_SHA256),
                         '_helsinki_preparation_fixture', {})
    original_read = R.loader.read_pinned
    selected_virtual = HERE.parent / 'source-admission-v1/rolling_reference.py'

    def read_selected(path, expected):
        if args.private_rolling_root is not None and Path(path) == selected_virtual:
            return original_read(rolling_root / 'rolling_reference.py', expected)
        return original_read(path, expected)

    suite = (unittest.TestSuite(Controls(name) for name in args.tests) if args.tests
             else unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    with patch.object(R.loader, 'read_pinned', side_effect=read_selected):
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    if PROOF:
        proof = {'schema': 'nexp005-changed-preparation-controls/v1',
                 'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
                 'temporary_fixture_bytes_written': WRITTEN, 'notes': NOTES,
                 'private_optimizer_locator': str(args.private_rolling_root) if args.private_rolling_root else None,
                 'scope': 'Generated-only changed preparation route. No authentic source admission, EEG, full Reference persistence, performance measurement or old16 replay.'}
        body = (json.dumps(proof, indent=2) + '\n').encode()
        assert len(body) <= 8192
        with PROOF.open('xb') as output:
            output.write(body)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
