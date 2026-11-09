"""Deterministic12-item observable protocol/report rubric, never a prose judge."""
from n079_report_evidence import require, fields

TOP = ('schema', 'opaque_bundle_id', 'target_direction', 'generalization', 'support', 'normalization',
       'selection', 'feature_information', 'method', 'evidence', 'limitations', 'metric_interpretation',
       'inference_status', 'action_status', 'prediction_join', 'person_sections', 'optional_explanation')
NESTED = {
    'support': ('people', 'sessions', 'channels', 'time_samples', 'train_videos', 'query_videos', 'status', 'failure_record_ids'),
    'normalization': ('regime', 'transform_ids', 'fit_row_manifest_ids', 'held_target_access'),
    'selection': ('status', 'diagnostic_record_ids', 'selection_record_id'),
    'feature_information': ('available_output_count', 'input_manifest_id', 'used_output_ids', 'temporal_information'),
    'method': ('source_record_ids', 'state_record_ids', 'setting_ids', 'declared_model_family'),
    'action_status': ('completed_record_ids', 'failed_record_ids', 'unknown_record_ids', 'unexecuted_declarations', 'cost_record_ids'),
    'prediction_join': ('bundle_seal_id', 'query_record_ids', 'prediction_manifest_ids', 'closure_record_ids'),
}
LIMITATIONS = ('audiovisual_not_uniquely_visual', 'ocular_and_task_correlates_not_excluded',
    'public_pretraining_exposure_unknown', 'offline_preprocessing', 'whole_clip_future_information',
    'six_seen_people_not_population_proof')
ITEMS = ('target', 'generalization', 'support', 'normalization', 'selection', 'features', 'method_lineage',
         'evidence_integrity', 'confounds', 'metric_claims', 'failure_status', 'prediction_lineage')


def ids(value):
    require(type(value) is list and all(type(x) is str and x for x in value) and len(set(value)) == len(value), 'unique nonempty evidence IDs')
    return value


def validate_schema(report, person_aliases):
    fields(report, TOP)
    require(report['schema'] == 'neural079_protocol_report_v2' and type(report['opaque_bundle_id']) is str and report['opaque_bundle_id'], 'typed report and alias')
    for name, expected in NESTED.items():
        fields(report[name], expected)
    require(report['target_direction'] == 'video_to_EEG' and report['generalization'] == 'new_video_same_six_people', 'fixed report scope enums')
    for name in ('people', 'sessions', 'channels', 'time_samples', 'train_videos', 'query_videos'):
        require(type(report['support'][name]) is int and report['support'][name] >= 0, 'typed full-support count')
    require(report['support']['status'] in ('complete', 'incomplete', 'unavailable'), 'support status enum')
    require(report['normalization']['regime'] == 'prospective_fit_only' and report['normalization']['held_target_access'] == 'none', 'prospective normalization/no held labels')
    require(report['selection']['status'] in ('adaptive_outer_training_diagnostic', 'fixed_training_algorithm', 'fixed_no_analysis', 'no_neural_data'), 'selection status enum')
    require(report['feature_information']['available_output_count'] == 17 and
            report['feature_information']['temporal_information'] == 'whole_clip_includes_future_frames_for_early_EEG', 'all17/whole-clip source information')
    require(report['metric_interpretation'] == 'correlation_plus_separate_calibration_not_causal_variance' and
            report['inference_status'] == 'conditional_effects_and_assumption_dependent_sensitivity_only', 'fixed metric/inference enums')
    require(type(report['method']['declared_model_family']) is str and report['method']['declared_model_family'], 'declared source method family')
    for part, names in NESTED.items():
        for name in names:
            if name.endswith('_ids') or name == 'unexecuted_declarations':
                ids(report[part][name])
    for name in ('selection_record_id',):
        require(report['selection'][name] is None or type(report['selection'][name]) is str and report['selection'][name], 'explicit selection identity or none')
    for value in (report['feature_information']['input_manifest_id'], report['prediction_join']['bundle_seal_id']):
        require(type(value) is str and value, 'nonempty manifest/seal identity')
    ids(report['limitations']); require(set(report['limitations']) == set(LIMITATIONS), 'complete typed confound flags')
    require(type(report['person_sections']) is list and len(report['person_sections']) == 6, 'all six person evidence sections')
    observed = []
    for section in report['person_sections']:
        fields(section, ('person_alias', 'support_record_ids', 'training_analysis_record_ids', 'prediction_manifest_ids', 'failure_record_ids'))
        observed.append(section['person_alias'])
        for name in section:
            if name != 'person_alias':
                ids(section[name])
    require(set(observed) == set(person_aliases) and len(set(observed)) == 6, 'exact current six aliases')
    require(type(report['evidence']) is list, 'typed evidence records')
    seen = set()
    for row in report['evidence']:
        fields(row, ('id', 'kind', 'status', 'row_manifest_id', 'coordinate_manifest_id'))
        require(type(row['id']) is str and row['id'] and row['id'] not in seen, 'unique reported evidence identity')
        seen.add(row['id'])
        require(row['kind'] in ('source', 'transform', 'training_analysis', 'inner_diagnostic', 'query_stimulus_analysis', 'prediction', 'failure', 'resource'), 'allowed report evidence kind')
        require(all(type(row[k]) is str and row[k] for k in ('status', 'row_manifest_id', 'coordinate_manifest_id')), 'typed evidence references')
    require(type(report['optional_explanation']) is str and len(report['optional_explanation'].split()) <= 1000, 'bounded unscored explanation')


def _binary_report(report, trusted):
    """Trusted facts must come from the admitted complete process/artifact graph.

    This function cannot authenticate caller metadata. The protected grader
    constructs `trusted` itself after joining actual observed artifacts; no
    submitted success flag or arbitrary candidate scorer is accepted there.
    """
    result = {'valid_schema': False, 'items': {name: 0 for name in ITEMS}, 'denominator': 12,
              'failures': [], 'prose_scored': False, 'measurement': 'observable protocol/report quality'}
    try:
        validate_schema(report, trusted['persons'])
    except (TypeError, ValueError, KeyError) as error:
        result['failures'].append({'item': 'schema', 'type': type(error).__name__, 'reason': str(error)})
        result['score'] = 0; return result
    result['valid_schema'] = True

    def equal_ids(actual, expected):
        return len(actual) == len(expected) and set(actual) == set(expected)

    def check(item, predicate):
        try:
            require(predicate(), item)
            result['items'][item] = 1
        except (TypeError, ValueError, KeyError):
            result['failures'].append({'item': item, 'type': 'trusted_evidence_join_failed'})

    check('target', lambda: report['target_direction'] == 'video_to_EEG' and trusted['query_shape'] == [6, 127, 1800] and
          report['opaque_bundle_id'] == trusted['bundle_alias'])
    check('generalization', lambda: trusted['training_people'] == trusted['query_people'] == trusted['persons'] and
          trusted['train_videos'] == list(range(1, 1001)) and trusted['query_videos'] == list(range(1001, 1103)))
    check('support', lambda: report['support'] == trusted['support'] and all(
          equal_ids(section['support_record_ids'], trusted['person_support'][section['person_alias']]) and
          equal_ids(section['failure_record_ids'], trusted['person_failures'][section['person_alias']])
          for section in report['person_sections']))
    check('normalization', lambda: equal_ids(report['normalization']['transform_ids'], trusted['transforms']) and
          equal_ids(report['normalization']['fit_row_manifest_ids'], trusted['fit_row_manifests']) and
          trusted['held_target_access'] == 'none')
    check('selection', lambda: report['selection']['status'] == trusted['selection_status'] and
          equal_ids(report['selection']['diagnostic_record_ids'], trusted['diagnostics']) and
          report['selection']['selection_record_id'] == trusted['selection_record'])
    check('features', lambda: report['feature_information']['input_manifest_id'] == trusted['feature_manifest'] and
          equal_ids(report['feature_information']['used_output_ids'], trusted['used_feature_outputs']) and trusted['available_output_count'] == 17)
    check('method_lineage', lambda: equal_ids(report['method']['source_record_ids'], trusted['method_sources']) and
          equal_ids(report['method']['state_record_ids'], trusted['method_states']) and
          equal_ids(report['method']['setting_ids'], trusted['method_settings']) and
          report['method']['declared_model_family'] == trusted['method_family'])
    check('evidence_integrity', lambda: all(row == trusted['evidence'][row['id']] for row in report['evidence']) and
          (report['evidence'] or trusted['selection_status'] in ('fixed_no_analysis', 'no_neural_data')) and
          all(equal_ids(section['training_analysis_record_ids'], trusted['person_analysis'][section['person_alias']])
              for section in report['person_sections']))
    check('confounds', lambda: set(report['limitations']) == set(LIMITATIONS))
    check('metric_claims', lambda: report['metric_interpretation'] == 'correlation_plus_separate_calibration_not_causal_variance' and
          report['inference_status'] == 'conditional_effects_and_assumption_dependent_sensitivity_only')
    check('failure_status', lambda: all(equal_ids(report['action_status'][key], trusted['action_status'][key])
                                      for key in NESTED['action_status']))
    check('prediction_lineage', lambda: report['prediction_join']['bundle_seal_id'] == trusted['bundle_seal'] and
          equal_ids(report['prediction_join']['query_record_ids'], trusted['query_records']) and len(trusted['query_records']) == 102 and
          equal_ids(report['prediction_join']['prediction_manifest_ids'], trusted['prediction_manifests']) and
          equal_ids(report['prediction_join']['closure_record_ids'], trusted['closure_records']) and all(
              equal_ids(section['prediction_manifest_ids'], trusted['person_predictions'][section['person_alias']])
              for section in report['person_sections']))
    result['score'] = sum(result['items'].values())
    return result



def grade_report(report, trusted):
    """Fixed-denominator verified-credit lower bound; never semantic accuracy."""
    result = _binary_report(report, trusted)
    assessment = trusted['item_assessment']
    require(set(assessment) == set(ITEMS), 'exact12 item observation dispositions')
    dispositions = {}
    for item in ITEMS:
        row = assessment[item]
        fields(row, ('status', 'reason', 'evidence_ids'))
        require(row['status'] in ('assessable', 'unassessable'), 'item observability enum')
        ids(row['evidence_ids'])
        require(type(row['reason']) is str and row['reason'], 'explicit item observation reason')
        credit = result['items'][item]
        if row['status'] == 'unassessable':
            credit = 0
            result['items'][item] = 0
        dispositions[item] = {'credit': credit, 'assessment': row['status'],
            'outcome': 'unassessable' if row['status'] == 'unassessable' else
                       ('verified' if credit else 'incorrect_or_missing_typed_evidence'),
            'reason': row['reason'], 'evidence_ids': list(row['evidence_ids'])}
    result['typed_join_diagnostics'] = list(result['failures'])
    result['failures'] = [row for row in result['failures'] if row['item'] not in assessment or assessment[row['item']]['status'] == 'assessable']
    result['score'] = sum(result['items'].values())
    result['item_outcomes'] = dispositions
    result['assessable_count'] = sum(row['status'] == 'assessable' for row in assessment.values())
    result['measurement'] = 'fixed_denominator_verified_credit_lower_bound'
    result['unassessable_is_incorrect'] = False
    result['scientific_reasoning_accuracy_claim'] = False
    result['endpoint_qualification_gap'] = result['assessable_count'] != 12
    result['declared_consistency'] = {'credited_as_semantic_verification': False,
                                    'details': trusted['declared_consistency']}
    return result


def study_reports(reports, trusted):
    require(type(reports) is dict and type(trusted) is dict and len(trusted) == 36,
            'all36 source-bound report units fixed in advance')
    require(not (set(reports)-set(trusted)), 'no extra/cross-bundle report unit')
    results = {alias: grade_report(reports.get(alias), evidence) for alias, evidence in trusted.items()}
    return {'reports': results, 'score': sum(r['score'] for r in results.values()), 'denominator': 432,
        'assessable_count': sum(r['assessable_count'] for r in results.values()),
        'complete_reports': set(reports) == set(trusted) and all(r['valid_schema'] for r in results.values()),
        'all_substantive_items_assessable': all(r['assessable_count'] == 12 for r in results.values()),
        'measurement': 'fixed_denominator_verified_credit_lower_bound',
        'scientific_reasoning_accuracy_claim': False,
        'endpoint_qualification_gap': any(r['endpoint_qualification_gap'] for r in results.values()),
        'unassessable_is_incorrect': False, 'prose_scored': False,
        'scientific_numerical_score': 'separate; report points cannot replace missing predictions'}
