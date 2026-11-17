"""Generated relocation/admission controls only. No authentic packet or runtime."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import types
import unittest
from unittest import mock

PACKAGE = Path(__file__).absolute().parents[1]


def imported(path, name):
    m = types.ModuleType(name)
    m.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), m.__dict__)
    return m


class Portable(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.pkg = self.root / 'relocated package'
        shutil.copytree(PACKAGE, self.pkg)
        self.digest = hashlib.sha256((self.pkg / 'SOURCE_MANIFEST.json').read_bytes()).hexdigest()
        self.b = imported(self.pkg / 'bootstrap.py', '_generated_rep012_bootstrap')
        self.block_process = mock.patch.object(subprocess, 'Popen', side_effect=AssertionError('no child'))
        self.block_network = mock.patch.object(socket, 'socket', side_effect=AssertionError('no network'))
        self.block_process.start()
        self.block_network.start()

    def tearDown(self):
        self.block_network.stop()
        self.block_process.stop()
        self.temp.cleanup()

    def candidate(self):
        return {
            'schema_version': 1, 'task_id': 'PAPER-FIND-REP-012',
            'analysis_id': 'released_source_four_pooled_pearson_v1',
            'input_manifest_sha256': 'd5f1d739eb1da61e01c2bb2e510dbd85d1c958f8243bc4b653c087a8c118cb1e',
            'cohort': {'member_count': 0, 'raw_rows': 0, 'unique_mice': 0,
                       'shared_mouse_ids': [], 'raw_row_ids_sha256': '0' * 64},
            'endpoints': [{'endpoint_id': endpoint, 'status': 'abstained',
                           'reason': 'generated boundary fixture', 'result': None}
                          for endpoint in ('apical_local', 'basal_local',
                                           'apical_coincident', 'basal_coincident')]
        }

    def test_relocated_full_graph_no_external_reads_or_dispatch(self):
        api = self.b.load(self.digest)
        self.assertEqual(api.controller.IMAGE,
                         'sha256:9aaf44dc64d85d0bbb0ffdd75ff5190ad94eff91d76849d14aea859c930955ff')
        self.assertEqual(api.core.ENDPOINT_IDS,
                         ('apical_local', 'basal_local', 'apical_coincident', 'basal_coincident'))
        self.assertEqual(len(api.core.NUMERIC_FIELDS) * 4, 16)
        self.assertEqual(len(api.core.SUPPORT_FIELDS) * 4, 24)
        self.assertEqual(len(api.core.COHORT_FIELDS), 5)
        receipt = api.controller.validate_receipt(json.loads(api.packet_binding.read_bytes()))
        self.assertEqual((len(receipt['views']['A']), len(receipt['views']['B'])), (9, 17))
        self.assertFalse((self.root / 'artifacts-build').exists())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(self.b.main(['--manifest-sha256', self.digest, 'check']), 0)

    def test_manifest_tamper_extra_source_and_symlink_refuse(self):
        with self.assertRaises(ValueError):
            self.b.verify('0' * 64)
        p = self.pkg / 'controller.py'
        original = p.read_bytes()
        p.write_bytes(original + b'\n')
        with self.assertRaises(ValueError):
            self.b.load(self.digest)
        p.write_bytes(original)
        q = self.pkg / 'extra.py'
        q.write_text('pass\n')
        with self.assertRaises(ValueError):
            self.b.load(self.digest)
        q.unlink()
        saved = self.root / 'saved-controller.py'
        p.rename(saved)
        p.symlink_to(saved)
        with self.assertRaises(ValueError):
            self.b.load(self.digest)

    def test_capture_dependency_is_source_local_and_environment_is_explicit(self):
        api = self.b.load(self.digest)
        # This repository does not exist and contains no donor source. Loading
        # the selected engine still uses only the authenticated package member.
        c = api.controller
        env = c.engine_class(self.root / 'absent-data-repository')
        out = self.root / 'generated-owner'
        out.mkdir()
        budget = types.SimpleNamespace(engines=[])
        engine = env['Engine'](out, budget, 1.0)
        self.assertEqual(engine.env, {})
        pair = types.SimpleNamespace(
            root=out, budget=budget,
            environment={'PATH': '/usr/bin:/bin', 'DOCKER_CONFIG': '/generated/config',
                         'DOCKER_HOST': 'unix:///generated/socket', 'PYTHON_DOTENV_DISABLED': '1'},
            engine=lambda *args: engine
        )
        condition = c.Condition(pair, 'A')
        self.assertEqual(condition.engine.env, pair.environment)
        self.assertIsNone(condition.thread)
        self.assertEqual(condition.engine.sequence, 0)

    def test_opaque_staging_accepts_distinct_programs_without_host_execution(self):
        api = self.b.load(self.digest)
        one = api.staging.stage_commands(b'raise RuntimeError("not executed on host")\n', api.controller.PYTHON)
        two = api.staging.stage_commands(b'print("different submitted program")\n', api.controller.PYTHON)
        self.assertNotEqual(one, two)
        self.assertTrue(all(len(x.encode()) <= 16384 for x in one + two))
        self.assertEqual(len(one), 3)
        self.assertFalse(any(self.root.glob('**/oracle.py')))

    def test_public_validation_precedes_any_private_reference_read(self):
        submission = self.root / 'generated-submission.json'
        submission.write_text(json.dumps(self.candidate()))
        with contextlib.redirect_stdout(io.StringIO()) as text:
            status = self.b.main(['--manifest-sha256', self.digest, 'validate',
                                  '--submission', str(submission)])
        self.assertEqual(status, 0)
        self.assertFalse(json.loads(text.getvalue())['private_reference_read'])
        submission.write_text('{}')
        output = self.root / 'invalid-grade.json'
        status = self.b.main(['--manifest-sha256', self.digest, 'score',
                              '--submission', str(submission),
                              '--reference', str(self.root / 'absent-reference'),
                              '--output', str(output)])
        self.assertEqual(status, 2)
        grade = json.loads(output.read_bytes())
        self.assertEqual(grade['status'], 'invalid_submission')
        self.assertIsNone(grade['reference_pin'])
        self.assertFalse(grade['private_reference_decoded'])

    def test_relocated_artifact_scorer_keeps_exact_reference_pin(self):
        submission = self.root / 'generated-submission.json'
        submission.write_text(json.dumps(self.candidate()))
        wrong = self.root / 'generated-wrong-reference.json'
        wrong.write_text('{}')
        output = self.root / 'operator-error.json'
        status = self.b.main(['--manifest-sha256', self.digest, 'score',
                              '--submission', str(submission), '--reference', str(wrong),
                              '--output', str(output)])
        self.assertEqual(status, 1)
        grade = json.loads(output.read_bytes())
        self.assertEqual(grade['status'], 'operator_error')
        self.assertIn('Approved fixed private reference bytes changed', grade['reason'])
        self.assertIsNone(grade['score'])

    def test_noncanonical_reference_cannot_bypass_fixed_pin(self):
        api = self.b.load(self.digest)
        directory = self.root / 'generated-dir'
        directory.mkdir()
        reference = self.root / 'generated-reference.json'
        reference.write_text('{}')
        submission = self.root / 'generated-submission.json'
        submission.write_text(json.dumps(self.candidate()))
        alias = str(directory) + '/../generated-reference.json'
        with self.assertRaisesRegex(ValueError, 'Canonical absolute external reference'):
            api.scorer.trusted_facade(api.root, Path(alias))
        with self.assertRaisesRegex(ValueError, 'Canonical absolute external reference'):
            self.b.main(['--manifest-sha256', self.digest, 'score',
                         '--submission', str(submission), '--reference', alias,
                         '--output', str(self.root / 'must-not-exist.json')])
        self.assertFalse((self.root / 'must-not-exist.json').exists())
        # Canonical spelling still reaches the unchanged exact-reference guard.
        facade = api.scorer.trusted_facade(api.root, reference)
        with self.assertRaisesRegex(ValueError, 'Approved fixed private reference bytes changed'):
            facade.read_bounded(reference, 32768)

    def test_all_external_operands_stay_inert_and_complete(self):
        api = self.b.load(self.digest)
        operands = json.loads((self.pkg / 'EXTERNAL_OPERANDS.json').read_bytes())
        self.assertFalse(operands['execution_authority'])
        self.assertFalse(operands['owner']['actual_selected'])
        self.assertFalse(operands['runtime']['qualified'])
        self.assertEqual(operands['runtime']['image'], api.controller.IMAGE)
        self.assertEqual(operands['packet_repository']['physical_files'], 26)
        self.assertEqual(operands['packet_repository']['complete_copy_bytes'], 998141)
        self.assertEqual(operands['scientific_scope']['raw_rows'], 1143)
        self.assertEqual(set(operands['programs']), {'A', 'B'})
        self.assertTrue(all(v['path'] is None for v in operands['programs'].values()))
        self.assertIsNone(operands['private_reference']['path'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
