"""Generated software controls only: no R, authentic workbook, or fitting."""
import argparse
import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('replay', ROOT / 'replay_primary_dl.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)
CONTRACT = replay.public_contract()
SCHEMA = json.loads(CONTRACT['schema'])
INTERFACE = json.loads(CONTRACT['interface'])


def generated_document():
    contrasts = []
    for contrast in ('quest_self', 'amy_quest', 'amy_self'):
        members = []
        for ordinal in range(1, 41):
            if ordinal == 6:
                continue
            members.append({'source_id': 'Morawetz2016b' if ordinal == 5 else f'generated{ordinal}',
                            'source_rows': [5, 6] if ordinal == 5 else [ordinal],
                            'retained_row': ordinal, 'author_label': f'Generated label {ordinal}',
                            'n_column': 'sample size rating' if contrast == 'amy_self' else 'sample size quest',
                            'contributes_to_k': True})
        fields = {x['field']: {'state': 'finite', 'value': 0.25} for x in SCHEMA['fields_per_contrast']}
        for name in ('k', 'k_all', 'k_TE', 'k_study', 'submitted_rows'):
            fields[name]['value'] = 39
        fields['df_Q']['value'] = 38
        fields['N_author_sum']['value'] = 390
        contrasts.append({'contrast': contrast, 'settings': copy.deepcopy(INTERFACE['settings']),
                          'tau_interval': {'method': 'J', 'lower_sign': '<', 'upper_sign': '>'},
                          'membership': members, 'fields': fields})
    return {'schema': INTERFACE['document_schema'], 'task': INTERFACE['task'], 'arm': 'A',
            'workbook_sha256': replay.PINS['workbook'][0], 'contrasts': contrasts}


class GeneratedControls(unittest.TestCase):
    def validate(self, doc):
        return replay.validate_output(replay.json_bytes(doc), 'A', CONTRACT)

    def test_complete_generated_document(self):
        doc = generated_document()
        self.validate(doc)
        self.assertEqual(sum(len(c['fields']) for c in doc['contrasts']), 120)
        self.assertLess(len(replay.json_bytes(doc)), 65536)

    def test_nonfinite_states_have_no_payload(self):
        for state in ('NA', 'NaN', '+Inf', '-Inf'):
            with self.subTest(state=state):
                doc = generated_document()
                doc['contrasts'][0]['fields']['Q'] = {'state': state}
                self.validate(doc)
                doc['contrasts'][0]['fields']['Q']['value'] = 1
                with self.assertRaises(Exception):
                    self.validate(doc)

    def test_missing_fields_rejected(self):
        for contrast in range(3):
            for field in SCHEMA['fields_per_contrast']:
                with self.subTest(contrast=contrast, field=field['field']):
                    doc = generated_document()
                    del doc['contrasts'][contrast]['fields'][field['field']]
                    with self.assertRaises(Exception):
                        self.validate(doc)

    def test_identity_and_settings_rejected(self):
        mutations = [('arm', 'B'), ('workbook_sha256', '0' * 64), ('schema', 'wrong'), ('task', 'wrong')]
        for key, value in mutations:
            doc = generated_document(); doc[key] = value
            with self.assertRaises(Exception):
                self.validate(doc)
        for key, value in [('sm', 'COR'), ('method_tau', 'REML'), ('method_random_ci', 'HK'),
                           ('level', '0.9'), ('cluster_supplied', True), ('three_level', True)]:
            doc = generated_document(); doc['contrasts'][0]['settings'][key] = value
            with self.assertRaises(Exception):
                self.validate(doc)

    def test_membership_order_is_stricter_than_old_comparator(self):
        doc = generated_document()
        doc['contrasts'][0]['membership'].reverse()
        with self.assertRaisesRegex(ValueError, 'ordered_membership'):
            self.validate(doc)

    def test_membership_lineage_and_counts(self):
        for key, value in [('source_rows', [6, 5]), ('retained_row', 6), ('n_column', 'sample size amygdala'),
                           ('contributes_to_k', False)]:
            doc = generated_document(); doc['contrasts'][0]['membership'][4][key] = value
            with self.assertRaises(Exception):
                self.validate(doc)

    def test_invalid_numeric_and_json(self):
        for value in ('0.25', True, None):
            doc = generated_document(); doc['contrasts'][0]['fields']['Q']['value'] = value
            with self.assertRaises(Exception):
                self.validate(doc)
        for raw in (b'{"schema":"a","schema":"b"}', b'{"x":NaN}', b' ' * 65537):
            with self.assertRaises(Exception):
                replay.validate_output(raw, 'A', CONTRACT)

    def test_comparator_tampering_fails_before_exec(self):
        for key in ('comparator', 'reporting_core'):
            contract = CONTRACT.copy(); contract[key] += b'\nraise RuntimeError("should not execute")\n'
            with self.assertRaisesRegex(ValueError, 'validator_identity'):
                replay.load_validator(contract)

    def test_no_import_shadowing_or_module_pollution(self):
        sentinel = object()
        with patch.dict(sys.modules, {'reporting_core': sentinel}):
            self.validate(generated_document())
            self.assertIs(sys.modules['reporting_core'], sentinel)

    def test_wrong_source_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'bad'; path.write_bytes(b'generated wrong bytes')
            for key in replay.PINS:
                with self.assertRaisesRegex(ValueError, 'source_identity'):
                    replay.read_pinned(path, key)
            link = Path(tmp) / 'link'; link.symlink_to(path)
            with self.assertRaisesRegex(ValueError, 'regular_input'):
                replay.read_pinned(link, 'workbook')

    def test_exact_spans_and_manifest(self):
        self.assertEqual(len(replay.SPANS), 23)
        self.assertEqual(replay.SPANS[-6:], ((149,149),(153,153),(216,216),(219,219),(262,262),(265,265)))
        self.assertFalse(any(a <= 470 <= b or a <= 474 <= b for a,b in replay.SPANS))
        raw = ''.join(f'# generated line {i}\n' for i in range(1, 626)).encode()
        with patch.dict(replay.PINS, {'script': (replay.sha(raw), len(raw))}):
            manifest = replay.expression_manifest(raw)
            self.assertEqual(len(manifest), 23)
            self.assertEqual(manifest[0]['sha256'], replay.sha(b'# generated line 13\n'))
            with self.assertRaisesRegex(ValueError, 'source_identity'):
                replay.expression_manifest(raw + b' ')

    def test_clean_environment_removes_R_hooks(self):
        with patch.dict(os.environ, {'R_PROFILE_USER': 'bad', 'R_LIBS': 'bad', 'RENV_PROJECT': 'bad',
                                     'OMP_NUM_THREADS': '8'}):
            env = replay.clean_environment()
            self.assertNotIn('R_PROFILE_USER', env)
            self.assertNotIn('R_LIBS', env)
            self.assertNotIn('RENV_PROJECT', env)
            self.assertEqual(env['OMP_NUM_THREADS'], '1')

    def test_publish_is_complete_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'result'
            replay.publish_new(path, b'first')
            with self.assertRaises(FileExistsError):
                replay.publish_new(path, b'second')
            self.assertEqual(path.read_bytes(), b'first')
            self.assertEqual(len(list(Path(tmp).iterdir())), 1)

    def test_missing_runtime_fails_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(output=str(Path(tmp)/'out'), provenance=str(Path(tmp)/'prov'),
                original_workbook='generated', official_script='generated', renv_lock='generated',
                rscript='definitely-not-an-installed-Rscript', runtime_identity='generated-test', arm='A', timeout=1)
            with patch.object(replay, 'read_pinned', return_value=b'generated'), \
                 patch.object(replay, 'expression_manifest', return_value=[]), \
                 patch.object(replay.subprocess, 'run') as launch:
                with self.assertRaisesRegex(ValueError, 'Rscript_missing'):
                    replay.run(args)
                launch.assert_not_called()
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def run_mock_process(self, mode):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'result'; provenance = Path(tmp) / 'provenance'
            args = argparse.Namespace(output=str(output), provenance=str(provenance),
                original_workbook='generated', official_script='generated', renv_lock='generated',
                rscript=sys.executable, runtime_identity='GENERATED MOCK ONLY', arm='A', timeout=1)
            manifest = [{'start': a, 'end': b, 'sha256': 'a'*64} for a,b in replay.SPANS]
            full120 = replay.json_bytes(generated_document())

            def fake_launch(command, *, cwd, env, **kwargs):
                self.assertEqual(command[1], '--vanilla')
                self.assertEqual((cwd / 'data/studyInformation/studyInformation_publication.xlsx').read_bytes(),
                                 b'GENERATED SOURCE BYTES')
                self.assertEqual(len(json.loads((cwd / 'job.json').read_text())['expressions']), 23)
                self.assertEqual(env['OMP_NUM_THREADS'], '1')
                (cwd / 'full120.json').write_bytes(b'INVALID GENERATED JSON' if mode == 'invalid' else full120)
                (cwd / 'runtime.json').write_text(json.dumps({'R_version': '4.3.2', 'evaluated_expression_count': 23}))
                if mode == 'timeout':
                    raise subprocess.TimeoutExpired(command, 1, output=b'partial stdout', stderr=b'partial stderr')
                if mode == 'launch_error':
                    raise OSError('generated launch failure')
                if mode == 'publication_race':
                    output.write_bytes(b'previous writer')
                return subprocess.CompletedProcess(command, 1 if mode == 'nonzero' else 0, b'generated stdout', b'generated stderr')

            with patch.object(replay, 'public_contract', return_value=CONTRACT), \
                 patch.object(replay, 'read_pinned', return_value=b'GENERATED SOURCE BYTES'), \
                 patch.object(replay, 'expression_manifest', return_value=manifest), \
                 patch.object(replay.subprocess, 'run', side_effect=fake_launch):
                if mode == 'success':
                    record = replay.run(args)
                    self.assertTrue(record['output_published'])
                    self.assertEqual(output.read_bytes(), full120)
                    self.assertEqual(record['output']['sha256'], replay.sha(full120))
                else:
                    with self.assertRaises(Exception):
                        replay.run(args)
                    record = json.loads(provenance.read_text())
                    self.assertFalse(record['output_published'])
                    self.assertFalse(record['complete_primary_success'])
                    expected = {'timeout':'native_process_timeout', 'launch_error':'native_launch_failed',
                                'nonzero':'native_process_failed', 'invalid':'output_validation_failed',
                                'publication_race':'output_publication_failed'}
                    self.assertEqual(record['status'], expected[mode])
                    retained = record['rejected_native_files']['full120.json']
                    self.assertEqual(base64.b64decode(retained['base64']),
                                     b'INVALID GENERATED JSON' if mode == 'invalid' else full120)
                    self.assertFalse(retained['truncated'])
                    if mode == 'publication_race':
                        self.assertEqual(output.read_bytes(), b'previous writer')
                    else:
                        self.assertFalse(output.exists())
                    if mode == 'timeout':
                        self.assertEqual(base64.b64decode(record['stdout']['base64']), b'partial stdout')
                self.assertEqual(record, json.loads(provenance.read_text()))

    def test_mocked_pipeline_success(self):
        self.run_mock_process('success')

    def test_mocked_pipeline_failure_evidence(self):
        for mode in ('timeout', 'launch_error', 'nonzero', 'invalid', 'publication_race'):
            with self.subTest(mode=mode):
                self.run_mock_process(mode)

    def test_retention_is_explicitly_bounded(self):
        retained = replay.retained_bytes(b'0123456789', limit=4)
        self.assertEqual(retained['bytes'], 10)
        self.assertEqual(retained['retained_bytes'], 4)
        self.assertTrue(retained['truncated'])
        self.assertEqual(base64.b64decode(retained['base64']), b'0123')


if __name__ == '__main__':
    unittest.main(verbosity=2)
