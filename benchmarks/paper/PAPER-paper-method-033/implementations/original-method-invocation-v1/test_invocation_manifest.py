"""Invented invocation metadata controls; no original script is executed."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shlex
from string import Template
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import invocation_manifest as m


def fixture():
    author = '/work/operator/source/official'
    def ckpt(role, model):
        return {'role': role, 'model_name': model, 'tag': 'last',
                'path': f'{author}/train_logs/{model}/last.pth', 'bytes': 16,
                'sha256': 'a' * 64, 'training_receipt_sha256': 'b' * 64}
    rows = []
    for arm, mode in m.ARMS.items():
        for budget in m.BUDGETS:
            cid = f'adapt_{mode}_s07_k{budget:04d}'
            model = f'mindbridge_subj125_a7_l{budget}' if arm == 'mindbridge' else f'vanilla_s07_k{budget:04d}'
            rows.append({'case_id': cid, 'arm': arm, 'budget': budget, 'target_subject': 7,
                'source_subjects': [1, 2, 5] if arm == 'mindbridge' else [],
                'checkpoint': ckpt(cid, model), 'view_root': '/work/views/' + cid,
                'view_pin_file': '/work/pins/' + cid + '-view.json',
                'checkpoint_pin_file': '/work/pins/' + cid + '-checkpoint.json',
                'capture_output': '/work/captured/' + cid, 'capture_max_bytes': 30000000000,
                'transport': {'producer': 'native_predict_eight_draws', 'producer_sha256': m.CAPTURE_HELPER_SHA, 'generated_draws': 8,
                              'retained_draws': 8, 'selection_stage': 'operator_after_freeze'}})
    return {'schema': 'mindbridge-invocation-bindings/v1', 'source_kind': 'generated_engineering_control',
        'source_bindings_sha256': m.SOURCE_BINDINGS_SHA,
        'information_condition': 'paper_data', 'composition_sha256': 'c' * 64,
        'locations': {'python': '/python', 'author_root': author, 'operator_root': '/work/operator/private',
            'reference_data_root': '/work/grader/reference', 'vd_cache_dir': '/work/cache/vd',
            'cache_manifest': '/work/cache/MANIFEST.json', 'cache_manifest_pin': '/work/pins/cache.json'},
        'source_pretrain': {'subjects': [1, 2, 5], 'excluded_target': 7, 'train_per_subject': 8559,
                           'validation_per_subject': 300, 'checkpoint': ckpt('source125_pretrain', 'mindbridge_subj125')},
        'conditions': rows}


def expanded_checked_in_adapt():
    """Independent tiny expansion of this fixed simple shell script, never shell eval."""
    p = Path(os.environ['MINDBRIDGE_AUTHOR_SOURCE']) / 'scripts/adapt_bridge.sh'
    raw = p.read_bytes()
    assert len(raw) == 831 and hashlib.sha256(raw).hexdigest() == '5219d2306d780bbad48ff3ce351fee50d732077d653141f076d5da073aea9293'
    variables, commands = {}, []
    # A backslash inside a shell comment does not continue that comment onto the
    # following live command; remove fixed-script comments before joining lines.
    active = '\n'.join(line for line in raw.decode().splitlines() if not line.lstrip().startswith('#'))
    for line in active.replace('\\\n', ' ').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line == 'cd src/':
            continue
        if line.startswith('CUDA_VISIBLE_DEVICES='):
            commands = shlex.split(Template(line).substitute(variables))
        else:
            key, value = line.split('=', 1)
            variables[key] = ''.join(shlex.split(Template(value).substitute(variables)))
    assert commands[0] == 'CUDA_VISIBLE_DEVICES=0' and commands[1] == 'python'
    return commands[1:]


class InvocationControls(unittest.TestCase):
    def setUp(self):
        self.value = fixture()

    def invalid(self):
        with self.assertRaises(m.BindingError):
            m.build(self.value)

    def test_complete_roles_and_unresolved_training_are_distinct(self):
        before = copy.deepcopy(self.value)
        result = m.build(self.value)
        self.assertEqual(self.value, before)
        self.assertEqual(len(result['conditions']), 6)
        self.assertIsNone(result['pretraining']['argv'])
        self.assertEqual(sum(r['training']['argv'] is not None for r in result['conditions']), 1)
        for row in result['conditions']:
            self.assertEqual(row['test_images'], 982)
            self.assertEqual(row['validation_images_per_included_subject'], 300)
            if row['arm'] == 'mindbridge':
                self.assertEqual(row['training']['paper_supported_condition']['epochs'], 200)
                self.assertEqual(row['training']['paper_supported_condition']['same_train_only_length_per_source_and_target'], row['budget'])
            else:
                self.assertIsNone(row['training']['argv'])
                self.assertNotIn('paper_supported_condition', row['training'])
        for key in ('launched', 'execution_authorized', 'checkpoint_bytes_verified',
                    'checkpoint_state_compatibility_verified', 'training_exposure_authenticated',
                    'source_lookup_verified', 'scientific_qualification'):
            self.assertIs(result[key], False)
        self.assertLess(len(json.dumps(result).encode()), 65536)

    def test_reset4000_argv_matches_fixed_author_script(self):
        result = m.build(self.value)
        job = next(r['training'] for r in result['conditions'] if r['arm'] == 'mindbridge' and r['budget'] == 4000)
        self.assertEqual(job['checked_in_expanded_argv'], expanded_checked_in_adapt())
        self.assertEqual(job['argv'], ['/python', *job['checked_in_expanded_argv'][1:],
                         '--data_path', '/work/views/adapt_reset_s07_k4000'])
        self.assertEqual(job['environment'], {'CUDA_VISIBLE_DEVICES': '0'})
        self.assertIs(job['wandb_default'], True)
        self.assertNotIn('--no-wandb_log', job['argv'])
        self.assertNotIn('accelerate', job['argv'])

    def test_target_contaminated_pretrain_declarations_rejected(self):
        self.value['source_pretrain']['subjects'] = [1, 2, 5, 7]
        self.invalid()
        self.value = fixture()
        pre = self.value['source_pretrain']['checkpoint']
        pre['model_name'] = 'mindbridge_subj1257'
        pre['path'] = '/work/operator/source/official/train_logs/mindbridge_subj1257/last.pth'
        self.invalid()

    def test_checkpoint_case_and_path_contradictions_rejected(self):
        self.value['conditions'][0]['checkpoint']['role'] = 'adapt_scratch_s07_k1500'
        self.invalid()
        self.value = fixture()
        self.value['conditions'][0]['checkpoint']['path'] = self.value['conditions'][1]['checkpoint']['path']
        self.invalid()

    def test_outcome_selected_checkpoint_and_alias_types_rejected(self):
        self.value['conditions'][0]['checkpoint']['tag'] = 'best'
        self.invalid()
        self.value = fixture()
        self.value['conditions'][0]['checkpoint']['bytes'] = True
        self.invalid()
        self.value = fixture()
        self.value['conditions'][0]['budget'] = 500.0
        self.invalid()

    def test_missing_duplicate_and_cross_arm_conditions_rejected(self):
        self.value['conditions'].pop()
        self.invalid()
        self.value = fixture()
        self.value['conditions'][1] = copy.deepcopy(self.value['conditions'][0])
        self.invalid()
        self.value = fixture()
        self.value['conditions'][0]['source_subjects'] = [1, 2, 5]
        self.invalid()

    def test_selected_only_reference_cannot_be_capture(self):
        self.value['conditions'][0]['transport']['producer'] = 'original_recon_selected'
        self.invalid()
        self.value = fixture()
        self.value['conditions'][0]['transport']['retained_draws'] = 1
        self.invalid()
        self.value = fixture()
        self.value['conditions'][0]['transport']['selection_stage'] = 'candidate_before_freeze'
        self.invalid()

    def test_changed_source_contract_or_capture_helper_pin_rejected(self):
        self.value['source_bindings_sha256'] = 'f' * 64
        self.invalid()
        self.value = fixture()
        self.value['conditions'][0]['transport']['producer_sha256'] = 'f' * 64
        self.invalid()

    def test_reference_and_eight_draw_routes_have_distinct_contracts(self):
        result = m.build(self.value)
        for row in result['conditions']:
            ref, cap = row['original_reference'], row['eight_draw_capture']
            self.assertEqual((ref['generated_draws'], ref['retained_draws']), (8, 1))
            self.assertIs(ref['panel_capture_compatible'], False)
            self.assertEqual((cap['generated_draws'], cap['retained_draws']), (8, 8))
            self.assertIs(cap['source_equivalence_or_publication_parity_verified'], False)
            self.assertEqual(ref['argv'][ref['argv'].index('--test_end') + 1], '982')
            self.assertEqual(ref['argv'][ref['argv'].index('--subj_load') + 1], '7')
            self.assertEqual(ref['autoencoder_presence_dependency'],
                             '/work/operator/source/official/train_logs/None/epoch120.pth')
            self.assertTrue(cap['argv'][1].endswith('/private/native_predict.py'))
            self.assertEqual(cap['argv'][cap['argv'].index('--checkpoint') + 1], row['checkpoint']['path'])

    def test_private_reference_and_view_boundaries(self):
        self.value['conditions'][0]['view_root'] = self.value['locations']['reference_data_root']
        self.invalid()
        self.value = fixture()
        self.value['conditions'][1]['capture_output'] = self.value['conditions'][0]['capture_output']
        self.invalid()
        self.value = fixture()
        self.value['locations']['author_root'] = '/invented/unsupported/layout'
        self.invalid()

    def test_access_condition_is_not_method_arm(self):
        self.value['information_condition'] = 'paper_data_author_code'
        result = m.build(self.value)
        self.assertEqual(result['information_condition'], 'paper_data_author_code')
        self.assertEqual({r['arm'] for r in result['conditions']}, {'vanilla', 'mindbridge'})
        self.value['information_condition'] = 'mindbridge'
        self.invalid()

    def test_builder_never_reads_declared_models_or_inputs(self):
        with patch('builtins.open', side_effect=AssertionError('opened an input')):
            result = m.build(self.value)
        self.assertIs(result['checkpoint_bytes_verified'], False)
        self.assertIs(result['training_exposure_authenticated'], False)

    def test_cli_rejects_duplicate_metadata_keys_before_output(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            root = Path(folder)
            (root / 'binding.json').write_text('{"schema":"first","schema":"second"}')
            with patch.object(sys, 'argv', ['builder', str(root / 'binding.json'), str(root / 'output.json')]):
                with self.assertRaisesRegex(m.BindingError, 'duplicate JSON key'):
                    m.main()
            self.assertFalse((root / 'output.json').exists())


if __name__ == '__main__':
    class Capped:
        used = 0
        truncated = False
        def write(self, text):
            raw = text.encode(); keep = raw[:max(0, 16383 - self.used)]
            self.truncated |= len(raw) != len(keep); self.used += len(keep)
            sys.__stderr__.buffer.write(keep)
        def flush(self):
            sys.__stderr__.flush()
    stream = Capped(); sys.stdout = sys.stderr = stream
    result = unittest.main(verbosity=2, exit=False).result
    raise SystemExit(0 if result.wasSuccessful() and not stream.truncated else 1)
