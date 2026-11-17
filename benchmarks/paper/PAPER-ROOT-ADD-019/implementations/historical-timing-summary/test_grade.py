"""Invented complete-report adapter controls; no authentic signal/reference data."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("portable_achda_grade", ROOT / "grade.py")
grade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade)
core, contract = grade.load_source(ROOT)

# Reused byte-for-byte hand-defined report fixture body from accepted generated_checks.py.
def fixture(contract):
    """A hand-defined report oracle, not simulated photometry or research cases."""
    dt=contract['sample_interval_seconds'];ms=dt*1000;physical=(-5+2409*15/7228)*1000
    d={'schema_version':1,'candidate_id':core.ID,'submission_status':'complete'}
    d['latency_ledger']=[dict(r,status='defined',segment_index1=1,absolute_sample_index0=2409,
        amplitude=1. if r['sensor']=='DA'else -1.,source_latency_ms=ms,scientific_latency_ms=ms,
        physical_grid_time_ms_separate_diagnostic=physical,finite_samples=242,nan_samples=0)
        for r in contract['rosters']['latency_ledger']]
    d['correlations']=[dict(r,status='defined',lags_samples=list(contract['lags_samples']),
        values=[0.]*483,pointwise_rat_counts={'DA':[10]*290,'ACh':[10]*290})for r in contract['rosters']['correlations']]
    d['rat_descriptions']=[dict(r,conditions=2 if r['datatype']=='volume'else 4,
        defined_conditions=2 if r['datatype']=='volume'else 4,source_equal_condition_mean_ms=ms,
        scientific_equal_condition_mean_ms=ms)for r in contract['rosters']['rat_descriptions']]
    d['matched_rat_descriptions']=[dict(r,DA_minus_ACh_ms=0.)for r in contract['rosters']['matched_rat_descriptions']]
    d['pooled_source_comparisons']=[]
    for r in contract['rosters']['pooled_source_comparisons']:
        n=contract['pooled_rows_per_sensor'][r['datatype']]
        d['pooled_source_comparisons'].append(dict(r,source_literal_pooled_DA_ms=[ms]*n,
            source_literal_pooled_ACh_ms=[ms]*n,source_literal_pooled_mean_DA_minus_ACh_ms=0.,
            ranks={'n_DA_condition_rows':n,'n_ACh_condition_rows':n,'DA_rank_sum':n*(2*n+1)/2,
                   'DA_U':n*n/2,'normal_variance':0.,'normal_continuity_corrected_z':None,
                   'normal_two_sided_p':None,'tie_group_sizes':[2*n],
                   'normal_status':'undefined_zero_rank_variance'}))
    return d


class AdapterControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.candidate = self.root / "candidate.json"
        self.reference = self.root / "reference.json"
        self.report = fixture(contract)
        self.save(self.candidate, self.report)
        self.save(self.reference, self.report)
        b = self.reference.read_bytes()
        self.pin = len(b), hashlib.sha256(b).hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, path, value):
        path.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False))

    def evaluate(self, reference=None, pin=None):
        return grade.evaluate(core, contract, self.candidate,
                              reference or self.reference, *(pin or self.pin))

    def test_complete_fixed_contract_forwarding(self):
        self.report['correlations'][0]['values'][0] = 1.
        self.save(self.candidate, self.report)
        out = self.evaluate()
        self.assertEqual(out['status'], 'scored')
        self.assertEqual(out['primary_metric']['value'], 0.)
        self.assertAlmostEqual(out['errors']['correlation.full_curve']['MAE'], 1/2898)
        self.assertEqual(out['private_reference_reads'], 1)

    def test_partial_preserves_fixed_denominator(self):
        self.report['latency_ledger'][0]['source_latency_ms'] = None
        self.report['submission_status'] = 'partial'
        self.save(self.candidate, self.report)
        out = self.evaluate()
        self.assertIsNone(out['primary_metric']['value'])
        self.assertEqual(out['primary_metric']['strata']['DA:volume']['reference_numeric_values'], 20)
        self.assertEqual(out['primary_metric']['strata']['DA:volume']['missing_expected_values'], 1)

    def test_malformed_candidate_never_loads_reference(self):
        self.candidate.write_bytes(b'{"x":1,"x":2}')
        out = self.evaluate(self.root / 'absent-reference')
        self.assertEqual((out['status'], out['private_reference_reads']), ('invalid_submission', 0))

    def test_abstention_never_loads_reference(self):
        value = {'schema_version':1,'candidate_id':core.ID,'submission_status':'abstain', **{k:[] for k in core.TABLES}}
        self.save(self.candidate, value)
        out = self.evaluate(self.root / 'absent-reference')
        self.assertEqual((out['status'], out['private_reference_reads']), ('abstained', 0))
        self.assertIsNone(out['primary_metric']['value'])

    def test_wrong_roster_never_loads_reference(self):
        self.report['latency_ledger'][0]['member_sha256'] = '0'*64
        self.save(self.candidate, self.report)
        out = self.evaluate(self.root / 'absent-reference')
        self.assertEqual((out['status'], out['private_reference_reads']), ('invalid_submission', 0))

    def test_reference_requires_independent_exact_pin(self):
        out = self.evaluate(pin=(self.pin[0], '0'*64))
        self.assertEqual((out['status'], out['private_reference_reads']), ('operator_error', 1))

    def test_candidate_fifo_refuses_before_open(self):
        self.candidate.unlink(); os.mkfifo(self.candidate)
        with patch.object(grade.os, 'open', side_effect=AssertionError('must not open FIFO')):
            out = self.evaluate()
        self.assertEqual((out['status'], out['private_reference_reads']), ('invalid_submission', 0))

    def test_reference_fifo_refuses_before_open(self):
        self.reference.unlink(); os.mkfifo(self.reference)
        original = grade.os.open
        seen = []
        def guarded(path, *args):
            seen.append(Path(path))
            if Path(path) == self.reference: raise AssertionError('must not open FIFO')
            return original(path, *args)
        with patch.object(grade.os, 'open', side_effect=guarded): out = self.evaluate()
        self.assertEqual(seen, [self.candidate])
        self.assertEqual((out['status'], out['private_reference_reads']), ('operator_error', 1))

    def test_symlink_hardlink_and_size_refusals(self):
        original = self.candidate.read_bytes()
        self.candidate.unlink(); self.candidate.symlink_to(self.reference)
        self.assertEqual(self.evaluate()['status'], 'invalid_submission')
        self.candidate.unlink(); os.link(self.reference, self.candidate)
        self.assertEqual(self.evaluate()['status'], 'invalid_submission')
        self.candidate.unlink(); self.candidate.write_bytes(b' '*(core.MAX_BYTES+1))
        self.assertEqual(self.evaluate()['status'], 'invalid_submission')
        self.candidate.write_bytes(b'')
        self.assertEqual(self.evaluate()['status'], 'invalid_submission')
        self.candidate.write_bytes(original)

    def test_observed_snapshot_change_refuses(self):
        original = grade.os.fstat
        calls = 0
        def changed(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                with self.candidate.open('ab') as stream: stream.write(b' ')
            return original(fd)
        with patch.object(grade.os, 'fstat', side_effect=changed): out = self.evaluate()
        self.assertEqual((out['status'], out['private_reference_reads']), ('invalid_submission', 0))

    def test_exclusive_output_and_alias_parent(self):
        target = self.root / 'grade.json'
        grade.write_report(target, {'status':'example'})
        saved = target.read_bytes()
        with self.assertRaises(FileExistsError): grade.write_report(target, {'status':'changed'})
        self.assertEqual(target.read_bytes(), saved)
        alias = self.root / 'alias'; alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): grade.write_report(alias / 'new.json', {'status':'x'})
        with self.assertRaises(ValueError): grade.write_report(self.root/'large.json', {'x':'x'*30000})
        self.assertFalse((self.root/'large.json').exists())

    def test_relocated_real_cli_and_pinned_source_refusal(self):
        portable = self.root / 'portable'; portable.mkdir()
        for name in ('grade.py','score_core.py','PUBLIC_CONTRACT.json'):
            shutil.copyfile(ROOT/name, portable/name)
        output = self.root/'cli-grade.json'
        cmd = [sys.executable,'-I','-S','-B',str(portable/'grade.py'),
               '--candidate',str(self.candidate),'--reference',str(self.reference),
               '--reference-bytes',str(self.pin[0]),'--reference-sha256',self.pin[1], '--output',str(output)]
        result = subprocess.run(cmd, cwd=self.root, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(output.read_text())['primary_metric']['value'], 0.)
        with (portable/'score_core.py').open('ab') as stream:stream.write(b'\n')
        with self.assertRaises(ValueError): grade.load_source(portable)
        shutil.copyfile(ROOT/'score_core.py', portable/'score_core.py')
        with (portable/'PUBLIC_CONTRACT.json').open('ab') as stream:stream.write(b' ')
        with self.assertRaises(ValueError): grade.load_source(portable)


if __name__ == '__main__':
    unittest.main(verbosity=2)
