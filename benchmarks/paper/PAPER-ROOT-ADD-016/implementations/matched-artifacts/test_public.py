"""Composition-only controls: generated operands, no original payload or fit."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(path):
    spec = importlib.util.spec_from_file_location('relocated_cardiac_pair', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class PublicComposition(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name).resolve()
        self.checkout = self.root / 'relocated checkout with spaces'
        self.component = self.checkout / 'components/cardiac-matched-artifacts'
        shutil.copytree(HERE, self.component, ignore=shutil.ignore_patterns('__pycache__'))
        dep = self.checkout / 'components/cardiac-six-model-summary'; dep.mkdir()
        for name in ('summary_score.py', 'submission_schema.json'):
            shutil.copyfile(HERE.parent / 'cardiac-six-model-summary' / name, dep / name)
        self.api = load(self.component / 'paired.py')
        self.operands = self.root / 'operands'; self.operands.mkdir()
        self.binding = self.root / 'operator-binding.json'
        self.value = {'schema': 'cardiac_private_reference_binding_v1', 'benchmark_id': 'PAPER-ROOT-ADD-016',
            'input_sha256': '6d122f256863197e49e9f7b39420cfe1c46741b3efa1fa66a6ec364337e48f11',
            'reference': {'path': 'private/reference.json', 'bytes': 12345, 'sha256': 'a' * 64}}
        self.binding.write_text(json.dumps(self.value))

    def tearDown(self):
        for folder, _, files in os.walk(self.root):
            os.chmod(folder, 0o700)
            for name in files: os.chmod(Path(folder) / name, 0o600)
        self.temp.cleanup()

    def test_relocation_and_every_provided_dependency_without_payload_reads(self):
        p = self.api.configured(self.operands, self.binding)
        self.assertEqual(p.roots['repository'], self.checkout)
        self.assertEqual(p.roots['operands'], self.operands)
        self.assertFalse((self.operands / 'private/reference.json').exists())
        self.assertEqual(len(p.members('A')), 41); self.assertEqual(len(p.members('B')), 46)
        public = self.api.decode((self.component / 'PACKET_SPEC.json').read_bytes())
        self.assertNotIn('reference', public)
        for name, item in p.members('B').items():
            if item['root'] != 'operands':
                raw = p.checked_read(item, 100000)
                self.assertEqual(self.api.pin(raw), {k: item[k] for k in ('bytes', 'sha256')}, name)
        self.assertEqual(p.spec['scorer']['path'], 'components/cardiac-six-model-summary/summary_score.py')
        self.assertEqual(len(self.api.S.MODELS), 6); self.assertEqual(len(self.api.S.VARIABLES), 5)
        self.assertFalse((self.component / 'summary_score.py').exists())
        self.assertFalse((self.component / 'submission_schema.json').exists())
        for forbidden in (b'/Users/', b'artifacts-build/'):
            self.assertNotIn(forbidden, (self.component / 'PACKET_SPEC.json').read_bytes())

    def test_binding_validation_before_any_target_open_and_pair_identity(self):
        original = self.api.F.read
        def only_metadata(path, cap=250000):
            self.assertIn(Path(path), (self.component / 'PACKET_SPEC.json', self.binding))
            return original(path, cap)
        cases = []
        for key, value in [('path', '../escape.json'), ('path', '/absolute.json'), ('bytes', True),
                           ('bytes', 200001), ('sha256', 'invalid')]:
            x = copy.deepcopy(self.value); x['reference'][key] = value; cases.append(x)
        x = copy.deepcopy(self.value); x['input_sha256'] = '0' * 64; cases.append(x)
        x = copy.deepcopy(self.value); x['unexpected'] = True; cases.append(x)
        with patch.object(self.api.F, 'read', only_metadata):
            first = self.api.configured(self.operands, self.binding)
            for bad in cases:
                self.binding.write_text(json.dumps(bad))
                with self.assertRaises(ValueError): self.api.configured(self.operands, self.binding)
            changed = copy.deepcopy(self.value); changed['reference']['sha256'] = 'b' * 64
            self.binding.write_text(json.dumps(changed)); second = self.api.configured(self.operands, self.binding)
        self.assertNotEqual(first.spec_pin, second.spec_pin)
        self.assertNotEqual(first.request('A', '1' * 32), second.request('A', '1' * 32))

    def test_dependency_drift_rejected_at_import_before_operator_inputs(self):
        helper = self.checkout / 'components/cardiac-six-model-summary/summary_score.py'
        helper.write_bytes(helper.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'Exact trusted module'):
            load(self.component / 'paired.py')

    def test_generated_operands_root_and_fixed_reference_pair_end_to_end(self):
        P = self.api
        def asset(name, raw):
            path = self.operands / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
            return {'root': 'operands', 'path': name, **P.pin(raw)}
        data = asset('complete-input.csv', b'generated fixture; no authentic data\n')
        spec = P.decode((self.component / 'PACKET_SPEC.json').read_bytes())
        spec['common'] = {'data.csv': data, 'paper.txt': asset('paper.txt', b'generated paper')}
        spec['B_only'] = {'official/code.txt': asset('code.txt', b'generated code assistance')}
        spec['scope']['input_sha256'] = data['sha256']
        value = {'schema_version': 1, 'input_sha256': data['sha256'],
                 'target': 'salzburg_bambi091_six_student_t_targets', 'models': {}}
        for model in P.S.MODELS:
            value['models'][model] = {'summary': {v: dict(mean=2., sd_population=1., hdi_94_low=1., hdi_94_high=3., mcse_mean_batch=None) for v in P.S.VARIABLES},
                'diagnostics': dict(chains=4, draws_per_chain=2000, tune_per_chain=2000, divergences=0, max_rhat=None, min_ess_bulk=None, min_ess_tail=None)}
        spec['reference'] = asset('private/reference.json', P.encoded(value))
        p = P.Packet(spec, self.checkout, self.component, self.operands)
        pair = self.root / 'pair'; p.build(pair)
        program = self.root / 'program.py'; program.write_bytes(b'# generated and never executed\n')
        summary = self.root / 'summary.json'; summary.write_bytes(P.encoded(value))
        caps = []
        for c in ('A', 'B'):
            cap = self.root / ('capture-' + c); caps.append(cap)
            p.capture(pair, c, pair / (c + '.request.json'), program, summary, cap)
        out = self.root / 'scores.json'; old = os.umask(0)
        try: scored = p.score_pair(pair, *caps, out)
        finally: os.umask(old)
        self.assertEqual(scored['scores']['A'], scored['scores']['B'])
        self.assertEqual(scored['scores']['A']['primary_beta_mean_rmse_reference_sd'], 0.)
        self.assertEqual(sum(len(m['parameters']) for m in scored['scores']['A']['models'].values()), 30)
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)
        changed = copy.deepcopy(spec); changed['reference']['sha256'] = 'c' * 64
        other = P.Packet(changed, self.checkout, self.component, self.operands)
        with patch.object(other, 'checked_read', side_effect=AssertionError('target must not open')):
            with self.assertRaisesRegex(ValueError, 'pair/scorer/reference binding'):
                other.score_pair(pair, *caps, self.root / 'wrong-reference.json')
        self.assertFalse((self.root / 'wrong-reference.json').exists())


if __name__ == '__main__': unittest.main(verbosity=2)
