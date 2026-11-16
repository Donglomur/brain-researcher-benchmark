"""Relocation checks only; no external assets, native runtime or original targets."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def encoded(value):
    return (json.dumps(value, allow_nan=False, separators=(',', ':')) + '\n').encode()


def fixture():
    # Public structural roster, invented partitions/probabilities/labels/provenance.
    manifest = json.loads((HERE / 'public/SESSION_MANIFEST.json').read_bytes())
    pairs = []
    expected = {'actual_index': {'invented': 'index'}, 'joined_scalars': {'invented': 'scalars'},
                'image': {'invented': 'image'}, 'protocol': {'invented': 'protocol'}, 'cells': []}
    reference = {'schema': 'thalamus_figure3C_fixed_reference_v1',
                 'source_actual_index': expected['actual_index'], 'source_joined_scalars': expected['joined_scalars'],
                 'reference_image': expected['image'], 'protocol': expected['protocol'],
                 'native_model_fits': 0, 'assembled_from_saved_outputs': True, 'cells': []}
    for session in manifest['sessions']:
        pair = {'schema': 'thalamus_figure3C_candidate_pair_v1', 'cohort_index': session['cohort_index'],
                'experiment_id': session['experiment_id'], 'conditions': []}
        for condition in manifest['conditions']:
            count = session['condition_specs'][condition]
            cell = {'condition': condition, 'feature_order': ['uuid_invented'],
                    'training_rows': list(range(1, count['training_rows'] + 1)),
                    'test_rows': list(range(count['training_rows'] + 1, count['trial_rows'] + 1)),
                    'probability_randomised': [.5] * count['test_rows']}
            source = {'predictions': {'invented': [session['cohort_index'], condition]},
                      'split': {'invented': 'first rows, not authentic source partition'}}
            expected['cells'].append(source)
            pair['conditions'].append(cell)
            labels = ['Randomised'] * count['test_class_counts']['Randomised'] + ['Regular'] * count['test_class_counts']['Regular']
            reference['cells'].append(dict(copy.deepcopy(cell), cohort_index=session['cohort_index'],
                experiment_id=session['experiment_id'], labels=labels,
                source_predictions=source['predictions'], source_split=source['split']))
        pairs.append(pair)
    return pairs, expected, reference


class DeliveryChecks(unittest.TestCase):
    def test_complete_source_and_external_partition(self):
        source = json.loads((HERE / 'SOURCE.json').read_bytes())
        actual = {str(p.relative_to(HERE)) for p in HERE.rglob('*') if p.is_file()}
        self.assertEqual(actual, {r['path'] for r in source['files']} | {'SOURCE.json'})
        for row in source['files']:
            raw = (HERE / row['path']).read_bytes()
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (row['bytes'], row['sha256']))
        external = json.loads((HERE / 'EXTERNAL_ASSETS.json').read_bytes())['files']
        self.assertEqual(len(external), 6)
        self.assertTrue(all(not (HERE / row['path']).exists() for row in external))
        closure = json.loads((HERE / 'private/package_files.json').read_bytes())['files']
        self.assertEqual(len(closure), 51)
        for row in external:
            self.assertEqual(closure[row['path']], {k: row[k] for k in ('bytes', 'sha256')})
        for omitted in ('private/ENVIRONMENT_BUILD.json', 'private/RUNTIME_ARCHIVE_BUILD.json', 'private/SOFTWARE_CHECKS.json'):
            self.assertNotIn(omitted, closure)
        for path, expected in closure.items():
            if path not in {row['path'] for row in external}:
                raw = (HERE / path).read_bytes()
                self.assertEqual({'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}, expected)

    def invoke_generated(self, malformed):
        wrapper = module('thalamus_relocated_delivery', HERE / 'private/grader.py')
        pairs, expected, reference = fixture()
        if malformed:
            pairs[-1]['conditions'][-1]['probability_randomised'].pop()
        raw_reference = encoded(reference)
        actual_read = wrapper.read_regular
        actual_module = wrapper.source_module
        reference_calls, r_calls = [], []
        def supplied(path, cap, pin=None):
            try:
                name = Path(path).relative_to(HERE).as_posix()
            except ValueError:
                return actual_read(path, cap, pin)
            if name == 'private/core/REFERENCE_EXPECTATIONS.json':
                return encoded(expected)
            if name == 'private/reference_pin.json':
                return encoded({'bytes': len(raw_reference), 'sha256': hashlib.sha256(raw_reference).hexdigest()})
            if name == 'private/fixed_reference.json':
                reference_calls.append(name)
                return raw_reference
            return actual_read(path, cap, pin)
        def captured_module(name, filename):
            value = actual_module(name, filename)
            if filename == 'grader.py':
                def no_native(values, script, core, state):
                    self.assertEqual(len(values['candidate']), 17)
                    self.assertEqual(len(values['reference']), 17)
                    self.assertEqual(len(script), 7721)
                    r_calls.append(True)
                    state.update(started=False, generated_stub=True)
                    return {'generated_boundary_stub': True, 'native_execution': False}
                value.r_diagnostics = no_native
            return value
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index, pair in enumerate(pairs, 1):
                (root / ('pair%03d.json' % index)).write_bytes(encoded(pair))
            with patch.object(wrapper, 'read_regular', supplied), patch.object(wrapper, 'source_module', captured_module):
                result, code = wrapper.grade_directory(root)
        return result, code, reference_calls, r_calls

    def test_complete_relocated_artifact_path_with_explicit_private_and_R_stubs(self):
        result, code, references, diagnostics = self.invoke_generated(False)
        self.assertEqual(code, 0)
        self.assertEqual(len(references), 1)
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual((result['primary_denominator'], len(result['sessions'])), (34, 17))
        self.assertEqual(sum(c['reference_test_rows'] for c in result['cells']), 4895)
        self.assertEqual(result['primary_metric'], 0)
        self.assertTrue(result['statistics']['generated_boundary_stub'])
        self.assertFalse(result['candidate_program_executed'])

    def test_last_malformed_pair_never_reaches_reference_or_R(self):
        result, code, references, diagnostics = self.invoke_generated(True)
        self.assertEqual(code, 2)
        self.assertEqual(result['status'], 'invalid_submission')
        self.assertEqual(references, [])
        self.assertEqual(diagnostics, [])
        self.assertEqual(result['private_reference_reads'], 0)

    def test_private_image_ownership_preserves_restrictive_input_modes(self):
        body = (HERE / 'private/Dockerfile').read_bytes()
        historical = body.replace(b'COPY --chown=65534:65534 ', b'COPY ')
        self.assertEqual((len(historical), hashlib.sha256(historical).hexdigest()),
                         (424, 'c2b94a54c7f085483f9f78962b15f7e59f670acde80fb8b60cfa8dba3f7609a8'))
        lines = body.decode().splitlines()
        copies = [line.split() for line in lines if line.startswith('COPY ')]
        self.assertEqual(len(copies), 3)
        self.assertTrue(all(row[1] == '--chown=65534:65534' for row in copies))
        self.assertEqual([row[-1] for row in copies],
                         ['/package/private/', '/package/private/core/', '/package/public/SESSION_MANIFEST.json'])
        self.assertGreater(lines.index('USER 65534:65534'), max(i for i, line in enumerate(lines) if line.startswith('COPY ')))
        # Source-policy witness, not a Docker execution: COPY preserves source mode,
        # defaults to owner0 without --chown, and numeric chown avoids name lookup.
        def available(mode, owner, process_uid, required):
            bits = (mode >> 6) & 7 if owner == process_uid else mode & 7
            return bits & required == required
        self.assertFalse(available(0o600, 0, 65534, 4))
        self.assertFalse(available(0o700, 0, 65534, 1))
        self.assertTrue(available(0o600, 65534, 65534, 4))
        self.assertTrue(available(0o700, 65534, 65534, 1))

    def test_real_CLI_from_unrelated_directory_refuses_missing_operator_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); submissions = root / 'submissions'; submissions.mkdir()
            result = subprocess.run([sys.executable, '-I', '-S', '-B', str(HERE / 'private/grader.py'),
                '--submission-dir', str(submissions), '--output', str(root / 'report.json')],
                cwd=root, capture_output=True, timeout=10, umask=0o077)
            self.assertEqual(result.returncode, 3)
            report = json.loads((root / 'report.json').read_bytes())
            self.assertEqual(report['status'], 'operator_error')
            self.assertIsNone(report['primary_metric'])
            self.assertEqual(stat.S_IMODE((root / 'report.json').stat().st_mode), 0o600)


if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('assertions must remain enabled')
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DeliveryChecks))
    raise SystemExit(0 if result.testsRun == 5 and result.wasSuccessful() and not
                     (result.skipped or result.expectedFailures or result.unexpectedSuccesses) else 1)
