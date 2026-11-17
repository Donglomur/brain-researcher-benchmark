"""Actual-source AST, shape-only dispatch and metadata controls; no NumPy or data I/O.

No numeric grade, signal interpolation, model fit, native execution or authentic
input inspection is performed. Source fixture coordinates are invented metadata.
"""
import ast
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core
from source_identity_join import bind_public_identity, support_report, validate_source_index
from timing import fixed_warp_mean, source_times


def raw_fixture():
    census = []
    for session in range(1, 7):
        delay = 1 if session in (1, 4) else 2
        has = session != 6
        census.append({'session_index1': session, 'is_grc': True, 'delay_s': delay,
                       'has_chronic_green': has, 'disposition': 'not_two_second_target' if delay == 1
                       else 'required_registered_target' if has else 'no_chronicGreen_registration'})
    pairs = []
    for ordinal, (source, target, mouse) in enumerate([(1, 2, 'A'), (1, 3, 'A'), (4, 5, 'B')], 1):
        row = {'pair_index1': ordinal, 'source_session_index1': source, 'target_session_index1': target,
               'mouse_id': mouse, 'reward_type': 'DAT', 'source_cells_index1': [1],
               'target_cells_index1': [1], 'source_shape': [5, 1, 2], 'target_shape': [2, 1, 2],
               'source_time_seconds': [0, 3], 'target_time_seconds': [0, 3],
               'registration_rows_source_target': [[1, 1], [0, 2]]}
        for side, extent in [('source', 80), ('target', 32)]:
            row[side + '_file'] = {'path': f'pair{ordinal:04d}_{side}.f64', 'bytes': extent, 'sha256': '0' * 64}
        pairs.append(row)
    return {'schema': 'neural029-raw-projection-v2', 'source_record': '21645651',
            'complete_selected_cohort': True, 'source_part_count': 2, 'source_session_count': 6,
            'selected_target_session_indices1': [2, 3, 5], 'cohort_dispositions': census, 'pairs': pairs,
            'scientific_fits': 0, 'scientific_scores': 0}


def run():
    checks = []
    def ck(name, value):
        if not value:
            raise AssertionError(name)
        checks.append(name)
    def refuses(name, call):
        try:
            call()
        except (ValueError, TypeError):
            checks.append(name)
        else:
            raise AssertionError(name)
    root = Path(__file__).resolve().parent
    for file in sorted(root.glob('*.py')):
        ast.parse(file.read_text(), filename=str(file))
    checks.append('all_python_sources_parse_without_importing_numpy')
    public = {'pairs': [{'pair_id': str(i), 'query_ids': ['q0', 'q1'], 'cell_ids': ['c0'],
               'calibration_trials': 4, 'validation_trials': 1, 'source_delay_seconds': 1,
               'target_delay_seconds': 2, 'reward_type': 'DAT'} for i in range(3)]}
    raw = raw_fixture()
    bound = bind_public_identity(raw, public, '0' * 64)
    report = support_report(bound, public)
    ck('complete_census_retained', len(report['cohort_dispositions']) == 6)
    ck('complete_graph_counts', report['counts'] == {'mice': 2, 'pairs': 3, 'selected_sessions': 5,
       'registered_components': 2, 'cell_pair_appearances': 3, 'recurrent_components': 1,
       'source_unique_trials': 10, 'target_unique_trials': 6,
       'source_repeated_trial_appearances_beyond_first': 5, 'structurally_unmatched_registration_rows': 3})
    ck('no_scientific_truth_or_component_estimator_claim', report['source_truth_verified'] is False and
       report['scientific_execution_qualified'] is False and
       report['component_balanced_sensitivity']['status'] == 'not_implemented')
    for name, mutation in [
        ('census_omission_refused', lambda x: x['cohort_dispositions'].pop()),
        ('required_target_omission_refused', lambda x: x['cohort_dispositions'][5].update(has_chronic_green=True, disposition='required_registered_target')),
        ('registration_omission_refused', lambda x: x['pairs'][0]['registration_rows_source_target'].append([3, 3])),
        ('recurrent_clock_disagreement_refused', lambda x: x['pairs'][1].update(source_time_seconds=[0, 4])),
        ('recurrent_trial_disagreement_refused', lambda x: (x['pairs'][1].update(source_shape=[6, 1, 2]), x['pairs'][1]['source_file'].update(bytes=96))),
        ('cross_mouse_component_refused', lambda x: x['pairs'][1].update(mouse_id='B'))]:
        wrong = copy.deepcopy(raw); mutation(wrong)
        refuses(name, lambda: validate_source_index(wrong))
    wrong = copy.deepcopy(bound); wrong['public_axes'][-1]['query_ids'][0] = 'wrong'
    refuses('bound_public_axis_mismatch_refused', lambda: support_report(wrong, public))
    mapped = source_times([0, 1, 1.999, 2, 2.001, 3])
    ck('fixed_warp_boundary_and_endpoints', mapped == [0, 0.5, 0.9995, 1, 1.001, 2])
    for value in ([-0.01], [3.01], [True], [float('nan')]):
        refuses('invalid_query_time_refused_' + str(len(checks)), lambda: source_times(value))
    # Shape-only collaborators observe the actual interpolation dispatch without signal arithmetic.
    class Finite:
        def all(self): return True
    class Mean:
        ndim = 2
        shape = (2, 3)
        def __getitem__(self, key): return ('source_row', key)
    class Sink:
        def __init__(self): self.rows = []
        def __setitem__(self, key, value): self.rows.append((key, value))
    class Inert:
        float64 = 'float64'
        def __init__(self): self.calls = []; self.sink = Sink()
        def isfinite(self, value): return Finite()
        def empty(self, shape, dtype): self.geometry = (shape, dtype); return self.sink
        def interp(self, times, clock, row):
            self.calls.append((times, clock, row)); return ('interpolation-dispatch', row)
    inert = Inert(); result = fixed_warp_mean(Mean(), [0, 1, 3], [0, 2, 3], inert)
    ck('source_only_interpolation_dispatch', inert.geometry == ((2, 3), 'float64') and
       inert.calls == [([0, 1, 2], [0, 1, 3], ('source_row', c)) for c in range(2)] and result is inert.sink)
    inert = Inert()
    refuses('extrapolation_refused_before_dispatch', lambda: fixed_warp_mean(Mean(), [0, 1, 1.5], [0, 2, 3], inert))
    ck('refused_extrapolation_did_not_interpolate', inert.calls == [])
    calls = []
    refuses('invalid_submission_refused_before_private', lambda: core.grade({'schema': 'wrong'}, public, lambda: calls.append(1), None))
    ck('private_callback_unreached', calls == [])
    tree = ast.parse((root / 'core.py').read_text())
    assignments = {n.targets[0].id: ast.unparse(n.value) for n in ast.walk(tree)
                   if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)}
    ck('primary_pooled_pair_expression_preserved', assignments['mse'] == 'float(np.mean((x - y) ** 2))' and
       assignments['normalized'] == 'math.sqrt(mse / scale) if scale else None')
    returns = [n.value for n in ast.walk(tree) if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict)]
    final = next(v for v in returns if any(isinstance(k, ast.Constant) and k.value == 'primary_nrmse' for k in v.keys))
    primary = {k.value: ast.unparse(v) for k, v in zip(final.keys, final.values) if isinstance(k, ast.Constant)}
    ck('primary_equal_mouse_expression_preserved', primary['primary_nrmse'] == "mean([m['nrmse'] for m in mice])")
    prepare_tree = ast.parse((root / 'prepare.py').read_text())
    scales = [ast.unparse(n.value) for n in ast.walk(prepare_tree) if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'scale' for t in n.targets)]
    ck('pooled_training_scale_expression_preserved', scales == ['float(np.mean((train - train.mean(axis=(0, 2), keepdims=True)) ** 2))'])
    for file in sorted(root.glob('*.json')):
        if file.name != 'INERT_CHECKS.json':
            json.loads(file.read_text())
    checks.append('all_json_source_contracts_parse')
    ck('numpy_never_imported', 'numpy' not in sys.modules)
    return {'schema': 'neural029-inert-source-controls-v2', 'status': 'passed', 'checks': checks,
            'count': len(checks), 'authentic_inputs_read': 0, 'numpy_imports': 0, 'native_runs': 0,
            'model_fits': 0, 'numeric_grades': 0, 'scientific_execution_qualified': False,
            'submission_ready': False}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, allow_nan=False))
