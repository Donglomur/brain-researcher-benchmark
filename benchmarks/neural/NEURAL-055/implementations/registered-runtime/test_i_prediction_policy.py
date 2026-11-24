"""Generated I-program transport controls; no model, EEG, target or fit runs.

The actual renderer, emitted interpreter and public validator are used. Only
model dialogue, analysis execution and the resulting in-memory file read are
substituted. This does not qualify the Linux host or any scientific method.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import signal
import sys
import time
import types
import unittest
from unittest import mock


HERE = Path(__file__).absolute().parent
parser = argparse.ArgumentParser(allow_abbrev=False)
parser.add_argument('--profile', type=Path, default=HERE / 'postscore_system_v2')
parser.add_argument('--template', type=Path, help='Explicit candidate source for review controls only')
args, remaining = parser.parse_known_args()
PROFILE = args.profile
TEMPLATE = args.template or PROFILE / 'model_system/i-interpreter/participant_template.py'


def load(name, path):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


renderer = load('_generated_i_renderer', PROFILE / 'model_system/i_renderer.py')
public = load('_generated_i_public', PROFILE / 'complete_study/public/interface.py')
policy = json.loads((PROFILE / 'complete_study/public/POLICY.json').read_text())


def loop_spec():
    # Inert engineering operands, never a model or deployment selection.
    return {
        'schema': 'neural055-fixed-i-loop-v1', 'model_provider': 'generated_model',
        'tool_provider': None, 'fit_prompt': 'GENERATED', 'infer_prompt': 'GENERATED',
        'max_new_tokens': 1, 'phase_steps': {'fit': 2, 'infer': 2},
        'malformed_repair_slots': 0, 'dependencies': [],
        'row_sum_abs_tolerance': policy['row_sum_abs_tolerance'],
        'limits': {
            'context_bytes': 65536, 'decision_bytes': 1024,
            'analysis_source_bytes': 1024, 'analysis_seconds': 1,
            'closure_seconds': 1, 'stream_bytes': 1024,
            'workspace_bytes': 8192, 'workspace_files': 4,
            'artifact_bytes': 1024, 'seal_bytes': 4096,
            'seal_header_bytes': 1024, 'state_count': 1,
            'sealed_action_count': 1}}


def interface_fixture():
    # The renderer checks declaration shape; invented pins do not authenticate
    # a runtime. The inference control below directly uses the real validator.
    names = ('TASK.md POLICY.json interface.py CASE_SCHEMA.json PREDICTION_SCHEMA.json '
             'PROGRAM_ABI_V3.md CELL_SCHEMA.json SELECTED_METHOD_SCHEMA.json '
             'OPERATIONS_SCHEMA.json BROKER_REQUEST_SCHEMA.json BROKER_RESPONSE_SCHEMA.json '
             'PREEXPOSURE_POLICY_SCHEMA.json RESOURCE_POLICY_V1.json').split()
    return {'schema': 'neural055-participant-interface-v4',
            'documents': {name: {'bytes': 1, 'sha256': '0' * 64} for name in names}}


def render(spec):
    return renderer.render_i_program(spec, interface_fixture(),
                                     read_source=lambda _path: TEMPLATE.read_bytes())


def emitted_program():
    rendered = render(loop_spec())
    module = types.ModuleType('_generated_emitted_i')
    module.__file__ = 'GENERATED_I.py'
    exec(compile(rendered['source_bytes'], module.__file__, 'exec'), module.__dict__)
    return module


def panel(delta=0.0):
    case = {'schema': 'neural055-public-case-v1', 'case_id': 'generated_case',
            'query_ids': ['q%03d' % i for i in range(200)],
            'candidate_ids': ['c%03d' % i for i in range(200)]}
    matrix = [[1 / 200] * 200 for _ in range(200)]
    matrix[0][0] += delta
    prediction = {'schema': 'neural055-prediction-v1', 'case_id': case['case_id'],
                  'query_ids': case['query_ids'][:], 'candidate_ids': case['candidate_ids'][:],
                  'probabilities': matrix, 'assignment': case['candidate_ids'][:]}
    return case, prediction


def infer(module, case, prediction):
    decisions = iter(['{"kind":"sealed_analysis","action":"generated"}',
                      '{"kind":"finish_infer"}'])
    raw = json.dumps(prediction, allow_nan=False).encode()
    ctx = {'spec': module.SPEC, 'case': case, 'public': vars(public),
           'input': '/input/query.json', 'phase': 'infer', 'cell': {}, 'tools': [],
           'records': [], 'work_end': time.monotonic() + 10}
    seal = {'context': {}, 'actions': {'generated': '# GENERATED; never executed'}, 'state': []}
    result = {'schema': 'neural055-i-infer-analysis-v1', 'observation': {},
              'prediction': 'artifacts/prediction.json'}
    # No candidate program or model runs, and no file with predictions is written.
    with mock.patch.object(module, 'dialogue', side_effect=lambda *_: next(decisions)), \
         mock.patch.object(module, 'execute_analysis', return_value=(result, Path('/GENERATED'))), \
         mock.patch.object(module, 'read', return_value=raw):
        return module.execute_sealed_inference(ctx, seal)


class FrozenPredictionPolicyTests(unittest.TestCase):
    def test_renderer_rejects_both_looser_and_stricter_conventions(self):
        for tolerance in (0.1, 0, 1e-7, 2e-6):
            with self.subTest(tolerance=tolerance):
                spec = loop_spec()
                spec['row_sum_abs_tolerance'] = tolerance
                with self.assertRaisesRegex(ValueError, 'row-sum tolerance.*1e-6'):
                    render(spec)

    def test_malformed_tolerances_remain_rejected(self):
        for tolerance in (True, False, float('nan'), float('inf'), '1e-6', None):
            with self.subTest(tolerance=tolerance):
                spec = loop_spec()
                spec['row_sum_abs_tolerance'] = tolerance
                with self.assertRaises(ValueError):
                    render(spec)

    def test_emitted_source_preserves_frozen_policy_and_rechecks_runtime_spec(self):
        module = emitted_program()
        self.assertEqual(module.SPEC['row_sum_abs_tolerance'], 1e-6)
        self.assertIs(module.validate_spec(module.SPEC), module.SPEC)
        altered = copy.deepcopy(module.SPEC)
        altered['row_sum_abs_tolerance'] = 0.1
        with self.assertRaisesRegex(ValueError, 'row-sum tolerance.*1e-6'):
            module.validate_spec(altered)

    def test_full_panel_inference_and_public_admission_agree(self):
        module = emitted_program()
        for delta in (0, 0.999e-6, -0.999e-6):
            with self.subTest(accepted_delta=delta):
                case, prediction = panel(delta)
                self.assertIs(public.validate_prediction(
                    case, prediction, row_sum_abs_tolerance=1e-6), prediction)
                self.assertEqual(infer(module, case, prediction), prediction)
        for delta in (1.001e-6, -1.001e-6, 0.05):
            with self.subTest(rejected_delta=delta):
                case, prediction = panel(delta)
                with self.assertRaisesRegex(public.ContractError, 'row not normalized'):
                    public.validate_prediction(case, prediction, row_sum_abs_tolerance=1e-6)
                with self.assertRaisesRegex(public.ContractError, 'row not normalized'):
                    infer(module, case, prediction)

    def test_complete_id_and_bijection_validation_remains_active(self):
        module = emitted_program()
        case, prediction = panel()
        prediction['assignment'][0] = prediction['assignment'][1]
        with self.assertRaisesRegex(public.ContractError, 'duplicate ID'):
            infer(module, case, prediction)


if __name__ == '__main__':
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('120-second generated control limit')))
    signal.alarm(120)
    print(json.dumps({'profile': str(PROFILE), 'template': str(TEMPLATE),
                      'template_sha256': hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(),
                      'scientific_execution': False}), flush=True)
    unittest.main(argv=[sys.argv[0]] + remaining)
