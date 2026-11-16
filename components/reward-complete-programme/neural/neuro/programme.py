"""Complete programme obligations remain visible when native science is unavailable."""
from .base import read_json, require, digest
from .contracts import SPEC, specifications, gate_report


def required_scope():
    design = read_json(SPEC / 'DESIGN.json')
    census = read_json(SPEC / 'INDEPENDENT_CENSUS.json')
    matrix, _ = specifications()
    return {'schema': 'joint_neural_full_programme_scope_v1',
            'canonical_ids': ['NEURAL-045', 'NEURAL-046'], 'new_ids': 0,
            'independent_corpora': 1, 'scientific_runs': 0,
            'listed_assets': census['total_assets'], 'listed_directories': census['source_directories'],
            'listed_bytes': census['listed_bytes'], 'inventory_is_biological_verification': False,
            'conditions': census['rows'],
            'N045_views': design['tasks']['NEURAL-045']['required_views'],
            'N046_endpoints': [design['tasks']['NEURAL-046']['primary_endpoint']] +
                              design['tasks']['NEURAL-046']['mandatory_secondary_endpoints'],
            'N046_splits': ['within_condition_leave_animal_out', 'leave_condition_out'],
            'cells': [{'cell_id': c['cell_id'], 'tier': c['tier'], 'mode': c['mode'],
                       'control': c['control'], 'applicability': c['intentional_cell_applicability'],
                       'is_task_or_run': False} for c in matrix['cells']],
            'reference_obligations': {
                'N045': ['R0_cue_time', 'R1_metadata', 'R2_count_history', 'R3_full_history',
                         'nonlinear_training_selected', 'ANCCR', 'microstimulus_TDRL', 'IRI_TDRL', 'SOP'],
                'N046': ['M0', 'ME', 'MN', 'MEN', 'MEN_independently_tuned',
                         'legacy_fixed_lambda_linear', 'matched_untransformed_learning_curves',
                         'matched_saturating_learning_curves', 'matched_history_kernels',
                         'full_nonlinear_history', 'ANCCR', 'microstimulus_TDRL', 'IRI_TDRL', 'SOP']},
            'required_sensitivities': ['native_mean_vs_AUC', 'baseline_span_corrected_AUC',
                'delivery_vs_consumption_anchor', 'active_time_vs_chamber_exposure',
                'calendar_progression_where_verified', 'cue_vs_delivered_vs_all_reward_vs_consumption_count',
                'past_vs_concurrent_behavior', 'first_six_trials', 'reward_vs_omission',
                'equal_session_vs_equal_trial', 'equal_condition_vs_equal_animal',
                'refitted_animal_resampling', 'protected_fixed_model_cluster_resampling',
                'native_vs_paper_interpolation_future_normalization_descriptive_only'],
            'qualification_gates': design['required_open_gates'], 'submission_ready': False}


def source_obligation_report(statuses):
    """Missing required rows remain required-unscorable, never apparent completion."""
    scope = required_scope()
    obligations = ['N045/' + x for x in scope['N045_views']]
    obligations += ['N046/' + x for x in scope['N046_endpoints'] + scope['N046_splits']]
    obligations += [task + '/reference/' + x for task, names in scope['reference_obligations'].items() for x in names]
    obligations += ['sensitivity/' + x for x in scope['required_sensitivities']]
    require(set(statuses) <= set(obligations), 'unknown_scientific_obligation')
    rows = {}
    for name in obligations:
        record = statuses.get(name, {'state': 'required_unscorable',
            'reason': 'No authentic native/reference/scientific qualification is authorized or established.'})
        require(record['state'] in ('source_implemented_engineering_only', 'required_unscorable') and
                bool(record['reason']), 'unsupported_qualification_claim')
        rows[name] = record
    return {'schema': 'source_obligations_not_scientific_results_v1', 'scope_digest': digest(scope),
            'obligations': rows, 'all_scientific_obligations_qualified': False,
            'scientific_runs': 0, 'new_tasks': 0, 'ready_tasks': 0}
