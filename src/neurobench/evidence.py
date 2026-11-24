"""Project a small, explicit set of public evidence reports into navigation.

This reads reports, not raw receipts, data, submissions, environments or candidate
code. Report hashes identify the inspected publication; they do not authenticate
an experiment independently or qualify the currently checked-out implementation.
Counts apply only to the selected public reports and never promote task readiness.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import stat

PILOT = 'docs/science/difficulty-pilot-20261117.json'
ERP_PILOT = 'benchmarks/neural/NEURAL-077/docs/exploratory32-fixed-image-pilot-20261122.json'
ERP_NARRATIVE = ERP_PILOT.removesuffix('.json') + '.md'
ERP_REFERENCE_FAILURE = 'benchmarks/neural/NEURAL-077/docs/full32-image-reference-calibration-20261124.json'
ERP_REFERENCE_NARRATIVE = ERP_REFERENCE_FAILURE.removesuffix('.json') + '.md'
ERP_UNCERTAINTY_CALIBRATION = 'benchmarks/neural/NEURAL-077/docs/full32-image-uncertainty-calibration-20261124.json'
ERP_UNCERTAINTY_NARRATIVE = ERP_UNCERTAINTY_CALIBRATION.removesuffix('.json') + '.md'
LANGUAGE_REFERENCE_HOME = 'benchmarks/paper/PAPER-ROOT-ADD-001/docs/provenance/trusted-figure3b-reference-20261124/'
LANGUAGE_REFERENCE = LANGUAGE_REFERENCE_HOME + 'RESULT.json'
LANGUAGE_REFERENCE_PROVENANCE = LANGUAGE_REFERENCE_HOME + 'PROVENANCE.json'
LANGUAGE_REFERENCE_NARRATIVE = LANGUAGE_REFERENCE_HOME + 'README.md'
UMBRAE_RESCORE = 'benchmarks/paper/PAPER-paper-method-042/docs/released-author-reference-rescore-20261124.v1.json'
UMBRAE_RESCORE_NARRATIVE = 'benchmarks/paper/PAPER-paper-method-042/docs/released-author-reference-rescore-20261124.md'
ANNOTATION_PROVENANCE = 'benchmarks/paper/PAPER-paper-method-013/docs/provenance/annotation-comparison-20261124/PROVENANCE_RESULT.json'
ANNOTATION_NARRATIVE = ANNOTATION_PROVENANCE.removesuffix('.json') + '.md'
PUBLIC_JSON_ATTACHMENTS = (LANGUAGE_REFERENCE_PROVENANCE,)
PUBLIC_ATTACHMENTS = (ERP_NARRATIVE, ERP_REFERENCE_NARRATIVE, ERP_UNCERTAINTY_NARRATIVE,
                      LANGUAGE_REFERENCE_PROVENANCE, LANGUAGE_REFERENCE_NARRATIVE,
                      UMBRAE_RESCORE_NARRATIVE, ANNOTATION_NARRATIVE)
HISTORY = 'docs/provenance/execution/historical-evidence-v1/profiles.json'
DIRECT = 'benchmarks/neural/NEURAL-077/implementations/complete-direct-condition-v1/EVIDENCE.json'
VIEWER = 'benchmarks/neural/NEURAL-077/implementations/visual-viewer-v1/EVIDENCE.json'
NATIVE = 'docs/status/operator-controls-20261116.json'
TRANSPORT = 'benchmarks/neural/NEURAL-077/implementations/visual-transport-v1/EVIDENCE.json'
NATIVE_REPAIR = 'docs/status/operator-controls-rename-20261116.json'
REVE_PREPARATION = 'docs/status/reve-source-preparation-20261116.json'
DEEP_PREPARATION = 'docs/status/deepcaimx-source-preparation-20261116.json'
SMC_HOME = 'benchmarks/paper/PAPER-SMC-RNN-2024/'
SMC_PREPARATION = SMC_HOME + 'docs/source-preparation-evidence.json'
SMC_PROBES = SMC_HOME + 'docs/native-cost-characterization.json'
SMC_CALIBRATION = 'docs/science/smc-author-calibration-20261117.json'
SMC_RESCORE = 'docs/science/smc-historical-rescore-20261120.json'
SMC_MATERIALS = SMC_HOME + 'docs/official-assets-materials-v2-20261117.json'
NEURAL096_HOME = 'benchmarks/neural/NEURAL-096/implementations/full-set-go-v1/'
NEURAL096_PREPARATION = NEURAL096_HOME + 'AUTHENTIC_PREPARATION.json'
SMC_ACTUAL_PANEL = '3b160dfb4aef8c68cbae8d4a02d5933576a77e4bc47a7c3a5b484369caf95be5'
SMC_PUBLIC_PANEL = '209a15e2189499a9e68264df5c9f81057dd919564d98a46fb64d75b3f39af2f3'
PUBLIC_REPORTS = (PILOT, HISTORY, DIRECT, VIEWER, NATIVE, TRANSPORT, NATIVE_REPAIR, REVE_PREPARATION, DEEP_PREPARATION,
                  SMC_PREPARATION, SMC_PROBES, NEURAL096_PREPARATION, SMC_CALIBRATION, SMC_RESCORE, SMC_MATERIALS,
                  ERP_PILOT, ERP_REFERENCE_FAILURE, ERP_UNCERTAINTY_CALIBRATION,
                  LANGUAGE_REFERENCE, UMBRAE_RESCORE, ANNOTATION_PROVENANCE)
MEMBER_LIMIT = 1024 * 1024
SCOPE = ('Recorded within the selected public reports only. Reports are not current '
         'runtime verification, protected evaluation or complete scientific qualification.')
PILOT_TASKS = {
    'PAPER-paper-signal-add-021': ('paper_calibration_attempt', 'Complete accepted fixed-region derivative: 12 regions, 36 effects and 540 leave-one-out summaries; not the original primary cluster analysis.'),
    'PAPER-FIND-REP-013': ('paper_calibration_attempt', 'Source-assisted reconstruction of ten released trees and 13 components; not whole-paper reproduction or source-paper improvement.'),
    'NEURAL-007': ('neural_programme_attempt', 'Feature programme with shared pretrained YASA outputs: two exposed development people and all 5,450 epochs; not direct signal interpretation.'),
    'NEURAL-077': ('neural_programme_attempt', 'EEG and permitted nuisance-feature programme: two exposed development people and all 400 trials; not direct or viewer interpretation.'),
}


def require(condition, message):
    if not condition:
        raise ValueError('Invalid public evidence: ' + message)


def obj(value):
    require(type(value) is dict, 'expected object')
    return value


def text(value):
    require(type(value) is str and 0 < len(value) <= 8192, 'expected bounded text')
    return value


def texts(value):
    require(type(value) is list and len(value) <= 100, 'expected bounded text list')
    return [text(item) for item in value]


def integer(value, minimum=0):
    require(type(value) is int and minimum <= value <= 10000000, 'invalid count')
    return value


def number(value):
    require(type(value) in (int, float), 'nonfinite or nonnumeric metric')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    require(finite, 'nonfinite or nonnumeric metric')
    return value


def digest(value):
    require(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value), 'invalid digest')
    return value


def stamp(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def read_bytes(root, relative):
    """Read a fixed allowlisted report or narrative, never an embedded locator."""
    require(relative in PUBLIC_REPORTS + PUBLIC_ATTACHMENTS, 'report is not allowlisted')
    path = root / relative
    for component in (path, *path.parents):
        require(not component.is_symlink(), 'symlink report path')
        if component == root:
            break
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
            and 0 < before.st_size <= MEMBER_LIMIT, 'expected bounded single-link report')
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        require(stamp(opened) == stamp(before), 'report changed while opening')
        raw = stream.read(MEMBER_LIMIT + 1)
        require(stamp(opened) == stamp(os.fstat(stream.fileno())) == stamp(path.lstat()),
                'report changed during read')
    require(len(raw) == before.st_size, 'report length changed')
    return raw, {'path': relative, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def read(root, relative):
    """Read a JSON report from the fixed projection allowlist."""
    require(relative in PUBLIC_REPORTS, 'JSON report is not allowlisted')
    return decode_public_document(read_bytes(root, relative))


def read_json_attachment(root, relative):
    """Parse only explicitly named JSON support; never an embedded locator."""
    require(relative in PUBLIC_JSON_ATTACHMENTS, 'JSON attachment is not allowlisted')
    return decode_public_document(read_bytes(root, relative))


def decode_public_document(captured):
    if captured is None:
        return None
    raw, source = captured
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Invalid public evidence: nonfinite JSON value ' + value)
    document = json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=invalid,
                          parse_float=lambda token: number(float(token)))
    return obj(document), source


def metric(name, value, direction, comparators=None):
    result = {'name': name, 'value': number(value), 'direction': direction}
    if comparators is not None:
        result['comparators'] = {text(key): number(item) for key, item in obj(comparators).items()}
    return result


def record(identifier, task, category, source, pointer, scope, condition, limits):
    return {'id': identifier, 'task_id': task, 'category': category,
            'source': source, 'source_pointer': pointer, 'scope': text(scope),
            'condition': text(condition), 'limits': texts(limits), 'qualification_effect': 'none'}


def pilot_records(doc, source):
    require(type(doc.get('schema_version')) is int and doc['schema_version'] == 1
            and doc.get('kind') == 'trusted_development_difficulty_pilot',
            'unsupported pilot report')
    attempts, declared = doc['attempts'], obj(doc['counts'])
    require(type(attempts) is list and 0 < len(attempts) <= 1000, 'bounded pilot attempts required')
    limits = texts(doc['limits'])
    require(bool(limits), 'pilot interpretation limits required')
    references = obj(doc['reference_scores'])
    require(set(references) == {'NEURAL-007', 'NEURAL-077'}
            and set(obj(references['NEURAL-007'])) == {'YASA', 'RF'}
            and set(obj(references['NEURAL-077'])) == {'prior', 'eeg', 'eog_site', 'gross_amplitude', 'behavioral_history', 'eeg_history'},
            'complete pilot comparator sets required')
    result, identities, tasks = [], set(), set()
    for index, attempt in enumerate(attempts):
        obj(attempt)
        identifier, task = text(attempt['attempt_id']), text(attempt['task_id'])
        require(identifier not in identities and task in PILOT_TASKS, 'duplicate attempt or unknown pilot task')
        identities.add(identifier)
        tasks.add(task)
        require(attempt['status'] == 'complete_scored', 'unsupported pilot outcome; do not omit failed attempts')
        category, scope = PILOT_TASKS[task]
        condition = text(attempt['condition'])
        expected = {'paper_data_shared_method', 'paper_data_shared_method_official_code'} if category == 'paper_calibration_attempt' else {
            'features_and_shared_pretrained_YASA' if task == 'NEURAL-007' else 'EEG_and_permitted_nuisance_features_program'}
        require(condition in expected, 'pilot access condition differs')
        row = record('difficulty-pilot-20261117:' + identifier, task, category, source,
                     '/attempts/' + str(index), scope, condition, limits)
        row.update(attempt_id=identifier, status='complete_scored',
                   authoring_wall_seconds=number(attempt['authoring_wall_seconds']))
        require(row['authoring_wall_seconds'] >= 0, 'negative authoring time')
        if task == 'PAPER-paper-signal-add-021':
            metrics = obj(attempt['metrics'])
            require(metrics['valid_submission'] is True, 'invalid scored TMS submission')
            require(all(type(metrics.get(key)) is int and metrics[key] == expected
                        for key, expected in (('all_regions', 12), ('all_effects', 36), ('all_leave_one_out', 540)))
                    and integer(attempt['numeric_fields']) == 4320, 'TMS pilot scope differs')
            row['metrics'] = [metric('reconstruction_fidelity_score', metrics['score'], 'higher')]
            row['coverage'] = {'numeric_fields': integer(attempt['numeric_fields'], 1)}
        elif task == 'PAPER-FIND-REP-013':
            tables = obj(attempt['tables'])
            require(all(integer(obj(tables[name])['required_rows']) == expected
                        for name, expected in (('cells.csv', 10), ('components.csv', 13),
                                               ('branches.csv', 21116), ('author_sections.csv', 12603))),
                    'Purkinje pilot scope differs')
            row['metrics'] = [metric('cell_equal_branch_length_rmse_um', attempt['primary_equal_cell_branch_length_rmse_um'], 'lower')]
            row['coverage'] = {'summary_scalar_count': integer(attempt['summary_scalar_count'], 1)}
        elif task == 'NEURAL-007':
            require(integer(attempt['scored_epochs']) == 5450, 'sleep pilot scope differs')
            row['metrics'] = [metric('person_mean_macro_f1', obj(attempt['metrics'])['person_mean_macro_f1'], 'higher', references[task])]
            row['coverage'] = {'scored_epochs': integer(attempt['scored_epochs'], 1)}
            row['protocol_note'] = text(attempt['protocol_note'])
        else:
            metrics = obj(attempt['metrics'])
            require(attempt['all400_trials_validated'] is True, 'EEG complete population not validated')
            row['metrics'] = [metric(name, metrics[name], direction, {key: obj(value)[name] for key, value in obj(references[task]).items()})
                              for name, direction in (('participant_macro_balanced_accuracy', 'higher'), ('participant_macro_log_loss', 'lower'))]
            row['coverage'] = {'validated_trials': 400}
            row['scoring_release'] = text(attempt['scoring_release'])
        for measured in row['metrics']:
            values = [measured['value'], *measured.get('comparators', {}).values()]
            maximum = 1 if measured['direction'] == 'higher' else math.inf
            require(all(0 <= value <= maximum for value in values), 'metric outside declared domain')
        result.append(row)
    require(integer(declared['fresh_solver_attempts']) == len(attempts)
            and integer(declared['scored_complete_submissions']) == len(attempts)
            and integer(declared['existing_endpoints']) == len(tasks)
            and integer(declared['new_benchmark_ids']) == 0, 'pilot declared counts disagree')
    return result


def exploratory_erp_records(doc, source, narrative):
    """Project aggregate observations without treating applications as authorships."""
    require(type(doc.get('schema_version')) is int and doc['schema_version'] == 1
            and doc.get('kind') == 'exploratory_fixed_image_erp_pilot'
            and doc.get('task_id') == 'NEURAL-077'
            and doc.get('evidence_role') == 'public_aggregate_transcription',
            'unsupported exploratory ERP report')
    require(narrative is not None, 'exploratory ERP narrative is missing')
    declared = obj(doc['narrative'])
    require(declared == narrative[1] and declared['path'] == ERP_NARRATIVE,
            'exploratory ERP narrative pin mismatch')
    require(all(doc.get(key) is False for key in (
        'original_records_in_publication', 'full_task_completed', 'paper_reproduction',
        'paper_improvement', 'sota_claim')), 'exploratory report cannot promote qualification')
    cohort = exact_counts(doc['cohort'], {'query_cases': 32, 'people': 32, 'demonstrations': 4,
                                        'target_events': 4, 'standard_events': 28}, 'exploratory cohort')
    protocol = obj(doc['protocol'])
    require(protocol['target'] == 'experimental_target_versus_standard_event_identity',
            'exploratory ERP target differs')
    require(all(protocol.get(key) is True for key in (
        'same_images_and_demonstrations', 'answers_frozen_before_gold',
        'programme_frozen_before_queries', 'errors_counted_incorrect'))
        and all(protocol.get(key) is False for key in (
        'failed_cases_retried_or_replaced', 'enforced_tool_sandbox',
        'exact_model_snapshot_available', 'complete_tool_traces_available',
        'matched_compute_budgets', 'established_model_or_human_baseline_run')),
        'exploratory ERP protocol or limitations differ')
    protocol = {key: protocol[key] for key in (
        'target', 'same_images_and_demonstrations', 'answers_frozen_before_gold',
        'programme_frozen_before_queries', 'errors_counted_incorrect',
        'failed_cases_retried_or_replaced', 'enforced_tool_sandbox',
        'exact_model_snapshot_available', 'complete_tool_traces_available',
        'matched_compute_budgets', 'established_model_or_human_baseline_run')}
    limits = texts(doc['limits'])
    require(bool(limits), 'exploratory interpretation limits required')
    arms = obj(doc['arms'])
    require(set(arms) == {'direct', 'programme'}, 'paired exploratory arms required')
    def interval(values, lower, upper):
        require(type(values) is list and len(values) == 2, 'two interval bounds required')
        checked = [number(value) for value in values]
        require(lower <= checked[0] <= checked[1] <= upper, 'invalid reported interval')
        return checked
    rows = []
    for name, condition, category, valid, errors, error_kind in (
            ('direct', 'instruction_restricted_direct_fixed_image',
             'exploratory_direct_interpretation', 31, 1, 'demonstration_image_delivery_error'),
            ('programme', 'one_frozen_generated_image_programme',
             'exploratory_frozen_programme', 26, 6, 'runtime_trace_coverage_errors')):
        arm = obj(arms[name])
        require(arm['condition'] == condition and arm['error_kind'] == error_kind,
                'exploratory arm condition or error type differs')
        coverage = exact_counts(arm, {'query_applications': 32, 'valid_outputs': valid,
                                     'errors': errors}, 'exploratory application counts')
        count_key, expected = ('episode_attempts', 32) if name == 'direct' else ('authoring_attempts', 1)
        coverage[count_key] = integer(arm[count_key])
        require(coverage[count_key] == expected, 'episodes, authorship and applications differ')
        value = number(arm['balanced_accuracy_percent'])
        require(0 <= value <= 100, 'balanced accuracy outside percentage domain')
        uncertainty = interval(arm['conditional_95_interval_percent'], 0, 100)
        expected_value, expected_interval = (57.1429, [30.357, 76.786]) if name == 'direct' else (26.7857, [17.857, 35.714])
        require(value == expected_value and uncertainty == expected_interval,
                'frozen exploratory report aggregates differ')
        row = record('exploratory-fixed-image-erp-20261122:' + name, 'NEURAL-077', category,
                     source, '/arms/' + name,
                     'One shared 32-image cohort, one image per person; errors remain in all denominators.',
                     condition, limits)
        row.update(coverage=coverage, cohort=cohort, protocol=protocol,
                   metrics=[metric('balanced_accuracy_percent', value, 'higher')],
                   conditional_95_interval_percent=uncertainty, narrative=narrative[1],
                   error_kind=error_kind, original_records_in_publication=False,
                   full_task_completed=False, evidence_role='public_aggregate_transcription')
        rows.append(row)
    comparison = obj(doc['paired_comparison'])
    require(comparison['direction'] == 'direct_minus_programme'
            and comparison['significance_or_pass_threshold_selected'] is False
            and integer(comparison['bootstrap_resamples']) == 10000
            and type(comparison['seed']) is int and comparison['seed'] == 20261122
            and comparison['bootstrap_rng'] == 'NumPy PCG64'
            and comparison['resampling'] == 'shared_observed_class_stratified'
            and comparison['quantiles'] == 'linear_percentile', 'paired uncertainty method differs')
    difference = number(comparison['difference_percentage_points'])
    require(abs(difference - (arms['direct']['balanced_accuracy_percent']
                             - arms['programme']['balanced_accuracy_percent'])) <= 0.001,
            'reported paired difference is inconsistent with rounded arm scores')
    bounds = interval(comparison['conditional_95_interval_percentage_points'], -100, 100)
    require(difference == 30.357 and bounds == [1.786, 53.571], 'frozen paired report aggregates differ')
    comparison = {key: comparison[key] for key in (
        'direction', 'difference_percentage_points', 'conditional_95_interval_percentage_points',
        'bootstrap_resamples', 'bootstrap_rng', 'seed', 'resampling', 'quantiles',
        'significance_or_pass_threshold_selected')}
    diagnostic = obj(doc['posthoc_diagnostic'])
    require(diagnostic['role'] == 'label_free_error_diagnosis_only'
            and diagnostic['performance_gain_claim'] is False,
            'error diagnosis cannot become performance evidence')
    exact_counts(diagnostic, {'decoded_pngs': 7, 'failed_applications_reproduced': 6,
                             'fixed_success_control_passed': 1, 'new_predictions': 0,
                             'rescoring_runs': 0}, 'error diagnosis')
    text(diagnostic['finding'])
    diagnostic = {key: diagnostic[key] for key in (
        'role', 'decoded_pngs', 'failed_applications_reproduced', 'fixed_success_control_passed',
        'finding', 'new_predictions', 'rescoring_runs', 'performance_gain_claim')}
    for row in rows:
        row['paired_comparison'] = comparison
    rows[1]['posthoc_diagnostic'] = diagnostic
    return rows


def historical_records(doc, source):
    require(type(doc.get('schema_version')) is int and doc['schema_version'] == 1
            and doc.get('kind') == 'maintainer_derived_historical_receipt_projection'
            and doc.get('not_a_new_runtime_receipt') is True and doc.get('raw_receipts_published') is False
            and type(doc.get('new_executions')) is int and doc['new_executions'] == 0,
            'unsupported historical projection')
    profiles, items = doc['profiles'], doc['evidence']
    require(type(profiles) is list and 0 < len(profiles) <= 100
            and type(items) is list and 0 < len(items) <= 100, 'bounded historical projections required')
    by_id = {}
    for item in items:
        obj(item)
        identifier = text(item['evidence_id'])
        require(identifier not in by_id, 'duplicate historical evidence identity')
        original = obj(item['original_record'])
        require(original['included_in_publication'] is False, 'historical raw receipt policy differs')
        integer(original['bytes'], 1)
        digest(original['sha256'])
        obj(item['selected_fields'])
        by_id[identifier] = item
    result, seen = [], set()
    for index, profile in enumerate(profiles):
        obj(profile)
        task = text(profile['canonical_task_id'])
        require(task in {'PAPER-FIND-REP-013', 'PAPER-paper-signal-add-021', 'NEURAL-023'} and task not in seen,
                'unknown or duplicate historical profile task')
        seen.add(task)
        identifiers = texts(profile['evidence'])
        require(identifiers and len(set(identifiers)) == len(identifiers) and set(identifiers) <= by_id.keys(),
                'missing or repeated historical evidence reference')
        for identifier in identifiers:
            require(by_id[identifier]['selected_fields'].get('/candidate_id') == task,
                    'historical evidence belongs to another task')
        category = 'historical_programme_control' if task == 'NEURAL-023' else 'historical_paper_calibration'
        row = record('historical-projection-20261116:' + task, task, category, source,
                     '/profiles/' + str(index), profile['scope'], profile['historical_profile_label'], profile['limits'])
        row.update(interpretation=text(profile['interpretation']), metric_description=text(profile['metric']),
                   evidence_ids=identifiers, original_records_in_publication=False,
                   epistemic_limit=text(doc['epistemic_limit']))
        if task == 'NEURAL-023':
            require('rtt-program-controls' in identifiers, 'historical controls must belong to selected profile evidence')
            fields = by_id['rtt-program-controls']['selected_fields']
            controls = []
            for control_index in range(4):
                prefix = '/controls/' + str(control_index) + '/'
                require(type(fields[prefix + 'passed']) is bool, 'invalid historical control outcome')
                controls.append({'name': text(fields[prefix + 'name']), 'passed': fields[prefix + 'passed']})
            row['controls'] = controls
        result.append(row)
    return result


def engineering_records(doc, source, viewer=False):
    schema = 'neural077_visual_viewer_engineering_v1' if viewer else 'neural077_complete_condition_delivery_v1'
    require(doc.get('schema') == schema and doc.get('task_id') == 'NEURAL-077'
            and doc.get('scientific_result') is False and type(doc.get('new_benchmark_ids')) is int
            and doc['new_benchmark_ids'] == 0, 'unsupported engineering report')
    require(type(doc.get('private_target_reads')) is int and doc['private_target_reads'] == 0,
            'engineering report private-access scope differs')
    model_key = 'model_trials' if viewer else 'model_calls'
    require(type(doc.get(model_key)) is int and doc[model_key] == 0, 'engineering report cannot assert model performance')
    if viewer:
        require(doc.get('status') == 'reviewed_source_and_authentic_rendering_no_model_trial'
                and doc.get('scoring_performed') is False and doc.get('transport_isolation_qualified') is False,
                'viewer report scope differs')
        verification = obj(doc['verification'])
        require(integer(verification['packet_query_records_authenticated']) == 400
                and integer(verification['training_demonstrations_authenticated']) == 4,
                'viewer authenticated population differs')
        ordinals = verification['authentic_query_ordinals_rendered']
        require(type(ordinals) is list and len(set(ordinals)) == len(ordinals)
                and all(type(item) is int and 0 <= item < 400 for item in ordinals), 'invalid rendered query ordinals')
        row = record('neural077-authentic-viewer-rendering-v1', 'NEURAL-077', 'authentic_viewer_rendering', source, '',
                     'Authentic packet authentication and selected visual rendering; no evaluated viewer-model episode.',
                     'zero_shot / four_demo engineering controls', doc['limitations'])
        row['coverage'] = {key: integer(verification[key]) for key in ('packet_query_records_authenticated', 'training_demonstrations_authenticated', 'direct_authentic_frames', 'cli_authentic_frames')}
        row['coverage']['query_ordinals_rendered'] = ordinals
        row['software_controls'] = {key: integer(verification[key]) for key in ('portable_generated_tests', 'complete400_native_collection_tests')}
        row['reported_implementation_sha256'] = {text(key): digest(value) for key, value in obj(doc['implementation_sha256']).items()}
    else:
        require(doc.get('status') == 'authentic_materialization_no_model_execution'
                and doc.get('exact_float64_sample_equality') is True
                and doc.get('no_tools_transport_qualified') is False
                and doc.get('per_query_programme_isolation_qualified') is False,
                'direct materialization report scope differs')
        require(all(integer(doc[key]) == expected for key, expected in
                    (('queries', 400), ('demonstrations', 4), ('raw_waveforms_checked', 404),
                     ('feature_training_cases', 6), ('feature_training_labels', 1200))),
                'direct materialization population differs')
        row = record('neural077-authentic-materialization-v1', 'NEURAL-077', 'authentic_input_materialization', source, '',
                     'Complete waveform delivery independently compared with pinned raw samples; no model execution or scoring.',
                     'legacy_waveform_no_tools / matched_waveform_programme input preparation', doc['limits'])
        row['coverage'] = {key: integer(doc[key]) for key in ('queries', 'demonstrations', 'raw_waveforms_checked', 'feature_training_cases', 'feature_training_labels')}
        controls = obj(doc['software_controls'])
        row['software_controls'] = {key: integer(controls[key]) for key in ('generated_standard_library', 'generated_native_numpy')}
    row['model_attempts_recorded'] = 0
    return [row]


def viewer_transport_records(doc, source):
    """Record scripted local transport controls without treating them as model trials."""
    require(doc.get('schema') == 'neural077_visual_transport_evidence_v1'
            and doc.get('scoring_performed') is False
            and doc.get('authentic_data_predictions_or_paths_in_public_git') is False,
            'unsupported viewer transport engineering report')
    require(all(integer(doc[key]) == 0 for key in
                ('new_download_bytes', 'new_model_trials', 'paid_api_calls', 'query_target_reads')),
            'viewer transport control cannot claim model trials, targets or acquisitions')
    verification = obj(doc['verification'])
    require(all(integer(verification[key]) == expected for key, expected in
                (('authentic_final_source_queries', 400), ('authentic_final_source_valid_unscored', 400),
                 ('authentic_control_checks', 15), ('generated_subprocess_tests_passed', 9)))
            and verification['authentic_four_demo_control'] is True
            and verification['unchanged_npz_validator_passed'] is True,
            'viewer transport complete population or controls differ')
    implementation = obj(doc['implementation_sha256'])
    require(set(implementation) == {'SOURCE_BINDINGS.json', 'scripted_client.py', 'transport.py'},
            'viewer transport implementation identity set differs')
    implementation = {name: digest(value) for name, value in implementation.items()}
    boundary = obj(doc['actual_boundary'])
    denials = texts(boundary['tested_denials'])
    require(len(denials) == 7 and set(denials) == {
        'authentic public packet reads', 'operator session reads', 'file writes', 'network socket',
        'child process', 'parent argv/environment KERN_PROCARGS2', 'inherited secret environment'},
        'viewer transport tested boundary differs')
    boundary = {key: text(boundary[key]) for key in ('first_final', 'macos_profile', 'participant_process',
                                                   'population_collection', 'wire_capture')}
    boundary['tested_denials'] = denials
    reuse = obj(doc['source_reuse'])
    require(reuse['normalizer_parser_scorer_copied'] is False and reuse['viewer'] == '../visual-viewer-v1',
            'viewer transport source reuse differs')
    counterexamples = texts(doc['preserved_counterexamples'])
    require(len(counterexamples) == 2 and len(set(counterexamples)) == 2,
            'both viewer transport counterexamples must remain recorded')
    row = record('neural077-authentic-viewer-transport-v1', 'NEURAL-077', 'authentic_viewer_transport', source, '',
                 doc['scope'], 'scripted local macOS complete collection and four-demo boundary controls', doc['limitations'])
    row.update(coverage={'scripted_queries': 400, 'valid_unscored_sessions': 400},
               software_controls={'authentic_boundary_checks': 15, 'generated_subprocess_tests': 9},
               reported_implementation_sha256=implementation, actual_boundary=boundary,
               source_reuse={'normalizer_parser_scorer_copied': False, 'viewer': reuse['viewer'],
                             'complete_collection': text(reuse['complete_collection'])},
               preserved_counterexamples=counterexamples, model_attempts_recorded=0,
               scoring_performed=False, original_records_in_publication=False,
               retained_receipt_sha256={key: digest(verification[key]) for key in (
                   'authentic_controls_receipt_sha256', 'complete_transport_receipt_sha256',
                   'frozen_control_protocol_sha256', 'sandbox_counterexample_receipt_sha256')})
    return [row]


def checked_native_repair(doc):
    require(doc.get('report_role') == 'rename_repair_validation', 'native repair report role differs')
    repair = obj(doc['repair'])
    require(all(repair.get(key) is True for key in (
        'previous_evidence_preserved', 'fresh_checkout',
        'exact_source_checked_before_and_after_each_native_attempt', 'direct_task_validator_import_regression_passed')),
        'native repair evidence or source checks contradicted')
    previous = obj(repair['previous_report'])
    require(set(previous) == {'path', 'bytes', 'sha256'} and previous['path'] == NATIVE,
            'native repair predecessor path differs')
    integer(previous['bytes'], 1)
    digest(previous['sha256'])
    require(repair['public_entrypoint'] == ['python3', '-I', '-S', '-B', 'scripts/neurobench.py', 'operator'],
            'native repair must exercise actual public entrypoint')
    dispatch = obj(repair['dispatch_source'])
    require(set(dispatch) == {'scripts/neurobench.py', 'src/neurobench/cli.py',
                             'src/neurobench/catalog.py', 'src/neurobench/operator_routes.py'},
            'native repair dispatch source identity set differs')
    for pin in dispatch.values():
        obj(pin)
        require(set(pin) == {'bytes', 'sha256'}, 'native repair dispatch pin has unexpected locator')
        integer(pin['bytes'], 1)
        digest(pin['sha256'])
    return {'problem': text(repair['problem']), 'change': text(repair['change']),
            'previous_report': dict(previous), 'previous_evidence_preserved': True,
            'public_entrypoint': list(repair['public_entrypoint']), 'dispatch_source': dispatch,
            'fresh_checkout': True, 'exact_source_checked_before_and_after_each_native_attempt': True,
            'direct_task_validator_import_regression_passed': True, 'protocol_sha256': digest(repair['protocol_sha256'])}


def checked_native_repair_lineage(doc, previous):
    """Join only the two explicit public reports, not historical source locators."""
    require(previous is not None, 'native repair requires the preserved original report')
    original_doc, original_source = previous
    require(doc['repair']['previous_report'] == original_source, 'native repair predecessor report pin mismatch')
    require(doc['source_commit'] != original_doc['source_commit']
            and doc['operator_source_inventory'] == original_doc['operator_source_inventory']
            and doc['sleep_adapter_commit'] == original_doc['sleep_adapter_commit'],
            'native repair changed original grader source or lacks a new dispatch revision')
    prior_receipts = {row['retained_receipt']['sha256'] for row in original_doc['controls']}
    require(all(row['retained_receipt']['sha256'] not in prior_receipts for row in doc['controls']),
            'native repair repeats a previous control receipt')
    totals = obj(doc['totals'])
    require(integer(totals['cumulative_native_attempts_including_previous_report'])
            == len(original_doc['controls']) + len(doc['controls'])
            and integer(totals['cumulative_owned_containers_including_previous_report'])
            == sum(row['owned_containers'] for report in (original_doc, doc) for row in report['controls'])
            and totals['cumulative_owned_container_absence_verified'] is True,
            'native repair cumulative totals disagree with distinct report rows')


def native_operator_records(doc, source):
    """Summarize the executed source revision without inspecting private receipts."""
    require(type(doc.get('schema_version')) is int and doc['schema_version'] == 1
            and doc.get('kind') == 'authentic_development_operator_controls'
            and doc.get('purpose') == 'development-control', 'unsupported native operator control report')
    is_repair = source['path'] == NATIVE_REPAIR
    repair = checked_native_repair(doc) if is_repair else None
    require(is_repair or ('report_role' not in doc and 'repair' not in doc),
            'original native report cannot assert a repair role')
    source_commit = text(doc['source_commit'])
    require(len(source_commit) == 40 and all(c in '0123456789abcdef' for c in source_commit),
            'invalid native control source revision')
    sleep_commit = text(doc['sleep_adapter_commit'])
    require(10 <= len(sleep_commit) <= 40 and all(c in '0123456789abcdef' for c in sleep_commit),
            'invalid native sleep adapter revision')
    inventory = obj(doc['operator_source_inventory'])
    require(set(inventory) == {'path', 'bytes', 'sha256'}
            and inventory['path'] == 'src/neurobench/operator-sources.json', 'native operator source inventory differs')
    integer(inventory['bytes'], 1)
    digest(inventory['sha256'])
    environment = obj(doc['native_environment'])
    expected_environment = {'local_unix_socket': True, 'pull': 'never', 'network': 'none',
                            'read_only': True, 'non_root': True,
                            'memory_bytes_per_container': 4294967296, 'cpus_per_container': 2,
                            'serialized_shared_lease': True}
    require(all(type(environment.get(key)) is type(value) and environment[key] == value
                for key, value in expected_environment.items()), 'native control environment boundary differs')
    image = text(environment['image'])
    require(image.startswith('sha256:'), 'native control image must be digest identified')
    digest(image[7:])
    environment = {**expected_environment, 'image': image,
                   'docker_server': text(environment['docker_server']),
                   'host_dispatch_python': text(environment['host_dispatch_python'])}
    definitions = {
        'NEURAL-077': {'prefix': 'eeg', 'rows': 400, 'files': 8,
                       'condition': 'feature_programme_input_packet; fixed p=0.5 scorer control',
                       'primary': 'equal-person balanced accuracy',
                       'companion': 'equal-person natural log loss',
                       'references': ['prior', 'eeg', 'eog_site', 'gross_amplitude', 'behavioral_history', 'eeg_history']},
        'NEURAL-007': {'prefix': 'sleep', 'rows': 5450, 'files': 24,
                       'condition': 'feature/common-model programme input packet; fixed uniform five-class scorer control',
                       'primary': 'equal-person fixed-five-class macro-F1',
                       'companion': 'balanced accuracy and signed reference differences',
                       'references': ['YASA', 'RF']},
    }
    panels, controls = doc['panels'], doc['controls']
    require(type(panels) is list and len(panels) == 2 and type(controls) is list and len(controls) == 8,
            'complete two-panel native control report required')
    panel_rows, seen = {}, set()
    for panel in panels:
        obj(panel)
        task = text(panel['task_id'])
        require(task in definitions and task not in panel_rows, 'unknown or duplicate native panel')
        definition = definitions[task]
        require(integer(panel['development_people']) == 2 and integer(panel['training_people']) == 6
                and integer(panel['development_rows']) == definition['rows']
                and integer(panel['public_input_files']) == definition['files'], 'native panel coverage differs')
        references = texts(panel['fixed_reference_arms'])
        require(len(references) == len(set(references)) and set(references) == set(definition['references'])
                and panel['primary_metric'] == definition['primary']
                and panel['companion_metric'] == definition['companion']
                and panel['condition'] == definition['condition'], 'native panel metric, condition or references differ')
        panel_rows[task] = panel
    controls_by_task = {task: [] for task in definitions}
    for control in controls:
        obj(control)
        task, identifier = text(control['task_id']), text(control['id'])
        require(task in definitions and identifier not in seen, 'unknown task or repeated native control')
        seen.add(identifier)
        definition = definitions[task]
        expected = {
            'validate': (0, 'valid_prediction_contract', False, 0, 1),
            'incomplete': (2, 'invalid_submission', False, 0, 1),
            'score': (0, 'scored', True, 2 if task == 'NEURAL-077' else 1, 2),
            'wrong-target': (3, 'scoring_error' if task == 'NEURAL-077' else 'operator_error', True, 1, 2),
        }
        prefix = definition['prefix'] + '-'
        require(identifier.startswith(prefix) and identifier[len(prefix):] in expected, 'unknown native control case')
        case = identifier[len(prefix):]
        exit_code, status, private, loaders, containers = expected[case]
        require(integer(control['expected_exit']) == exit_code and integer(control['observed_exit']) == exit_code
                and control['status'] == status and control['private_stage_dispatched'] is private
                and integer(control['target_loader_attempts']) == loaders
                and integer(control['owned_containers']) == containers
                and control['all_owned_containers_absent'] is True, 'native control outcome or access expectation contradicted')
        require(integer(control['population_rows']) == definition['rows']
                and control['condition'] == 'fixed_probability_software_control', 'native control population or condition differs')
        selected = {key: control[key] for key in ('id', 'task_id', 'population_rows', 'condition', 'expected_exit',
                    'observed_exit', 'status', 'private_stage_dispatched', 'target_loader_attempts',
                    'owned_containers', 'all_owned_containers_absent')}
        selected['expected_refusal'] = case in ('incomplete', 'wrong-target')
        if is_repair:
            require(control.get('source_unchanged_before') is True and control.get('source_unchanged_after') is True,
                    'native repair source stability contradicted')
            selected.update(source_unchanged_before=True, source_unchanged_after=True)
        for name in ('retained_result', 'retained_receipt'):
            pin = obj(control[name])
            require(set(pin) == {'bytes', 'sha256'}, 'native retained evidence must have no locator')
            selected[name] = {'bytes': integer(pin['bytes'], 1), 'sha256': digest(pin['sha256'])}
        controls_by_task[task].append(selected)
    require(len({row['retained_receipt']['sha256'] for row in controls}) == len(controls),
            'native controls must retain distinct attempt receipts')
    totals = obj(doc['totals'])
    require(integer(totals['native_attempts']) == len(controls)
            and integer(totals['owned_containers']) == sum(row['owned_containers'] for row in controls)
            and totals['owned_container_absence_verified'] is True, 'native control totals disagree')
    require(all(integer(totals[key]) == 0 for key in
                ('new_solver_attempts', 'new_model_calls', 'fits', 'acquisitions', 'environment_installs')),
            'native software controls cannot claim new models, fits or acquisition')
    result = []
    for index, panel in enumerate(panels):
        task = panel['task_id']
        require(len(controls_by_task[task]) == 4, 'native panel controls incomplete')
        row = record('native-' + Path(source['path']).stem + ':' + task, task, 'native_operator_control', source,
                     '/panels/' + str(index), doc['scope'], panel['condition'], doc['limits'])
        row.update(coverage={key: panel[key] for key in ('development_people', 'development_rows', 'public_input_files', 'training_people')},
                   primary_metric=panel['primary_metric'], companion_metric=panel['companion_metric'],
                   fixed_reference_arms=list(panel['fixed_reference_arms']),
                   controls=sorted(controls_by_task[task], key=lambda item: item['id']),
                   native_environment=environment,
                   source_provenance={'source_commit': source_commit, 'sleep_adapter_commit': sleep_commit,
                                      'operator_source_inventory': dict(inventory)},
                   execution_utc_date=text(doc['execution_utc_date']), report_date=text(doc['report_date']),
                   public_input_observation=text(doc['public_input_observation']),
                   counterexamples_preserved=texts(doc['counterexamples_preserved']),
                   evidence_custody=text(doc['evidence_custody']), model_attempts_recorded=0,
                   original_records_in_publication=False,
                   report_role='rename_repair_validation' if is_repair else 'original_operator_controls')
        if repair is not None:
            row['repair'] = repair
        result.append(row)
    return result


def revision(value):
    require(type(value) is str and len(value) == 40 and all(c in '0123456789abcdef' for c in value),
            'invalid recorded source revision')
    return value


def source_snapshot(value, expected_paths, *, execution=False):
    """Validate published source descriptors, without opening their paths."""
    value = obj(value)
    pins = value['files']
    require(type(pins) is list and len(pins) == len(expected_paths), 'source snapshot file count differs')
    seen, selected = set(), []
    for pin in pins:
        obj(pin)
        require(set(pin) == {'path', 'bytes', 'sha256'} and pin['path'] in expected_paths
                and pin['path'] not in seen, 'source snapshot path differs or repeats')
        seen.add(pin['path'])
        selected.append({'path': pin['path'], 'bytes': integer(pin['bytes'], 1), 'sha256': digest(pin['sha256'])})
    result = {'commit': None if execution and value['commit'] is None else revision(value['commit']),
              'files': selected}
    for key in ('publication_commit', 'verified_in_checkout_commit'):
        if key in value:
            result[key] = revision(value[key])
    for key in ('binding_status', 'identity_basis', 'relationship_to_execution', 'comparison_to_execution_source'):
        if key in value:
            result[key] = text(value[key])
    if 'executed_members' in value:
        members = texts(value['executed_members'])
        require(len(members) == len(set(members)) and set(members) <= expected_paths,
                'executed source member escapes the published snapshot')
        result['executed_members'] = members
    return result


def paper_preparation_records(doc, source):
    require(type(doc.get('schema_version')) is int and doc['schema_version'] == 1
            and doc.get('kind') == 'paper_source_preparation'
            and doc.get('author_baseline_qualified') is False and doc.get('scientific_result') is False
            and integer(doc['model_trials']) == 0 and integer(doc['solver_attempts']) == 0,
            'source preparation cannot assert model or scientific qualification')
    expected_task = 'PAPER-paper-method-003' if source['path'] == REVE_PREPARATION else 'PAPER-paper-method-013'
    require(doc.get('task_id') == expected_task, 'paper preparation report belongs to another task')
    for key in ('fits', 'new_benchmark_ids'):
        if key in doc:
            require(integer(doc[key]) == 0, 'paper preparation cannot claim fitting or additional tasks')
    home = 'benchmarks/paper/' + expected_task + '/implementations/'
    is_reve = expected_task == 'PAPER-paper-method-003'
    paths = {home + 'original-physionet/' + name for name in ('README.md', 'author_adapter.py', 'metrics.py', 'panel.py')} if is_reve else {
        home + 'source-panel-v1/' + name for name in ('source_panel.py', 'roi_sources.json', 'range_source.py', 'checkpoint.py')
    } | {home + 'initial-evaluator-v1/evaluator.py'}
    executed = source_snapshot(doc['source_execution'], paths, execution=True)
    current = source_snapshot(doc['current_source'], paths)
    before, after = ({pin['path']: pin for pin in snapshot['files']} for snapshot in (executed, current))
    require(text(executed['identity_basis']) and doc['limits'], 'source lineage and interpretation limits required')
    coverage, controls = obj(doc['coverage']), obj(doc['software_controls'])
    if is_reve:
        require(executed['commit'] is not None and executed.get('binding_status') == 'recorded_execution_source_revision'
                and set(executed.get('executed_members', [])) == {home + 'original-physionet/panel.py', home + 'original-physionet/metrics.py'},
                'REVE execution source binding differs')
        require(all(before[path] == after[path] for path in paths if not path.endswith('/README.md')),
                'REVE current executable source differs from reported execution snapshot')
        require(all(integer(coverage[key]) == expected for key, expected in
                    (('edf_files', 654), ('participants', 109), ('epochs', 9837), ('native_boundary_dropped_annotations', 1)))
                and coverage['imagery_runs'] == [4, 6, 8, 10, 12, 14]
                and all(type(item) is int for item in coverage['imagery_runs']), 'REVE source population differs')
        for key, expected in (('split_epochs', {'train': 6300, 'validation': 1734, 'test': 1803}),
                              ('split_participants', {'train': 70, 'validation': 19, 'test': 20}),
                              ('raw_sampling_hz_file_counts', {'160': 636, '128': 18})):
            require(set(obj(coverage[key])) == set(expected)
                    and all(integer(coverage[key][name]) == count for name, count in expected.items()),
                    'REVE split or recording census differs')
        coverage = {key: coverage[key] for key in ('edf_files', 'participants', 'imagery_runs', 'epochs', 'split_epochs',
                                                  'split_participants', 'raw_sampling_hz_file_counts', 'native_boundary_dropped_annotations')}
        require(controls['kind'] == 'fixed_output_full_original_test_panel'
                and integer(controls['test_events']) == 1803 and integer(controls['test_participants']) == 20
                and controls['targets_used_for_control_selection'] is False and controls['trained_model_execution'] is False
                and all(controls[key] is True for key in ('event_identity_join_exercised', 'original_metric_path_exercised',
                    'paired_comparator_path_exercised', 'expected_metric_and_paired_difference_checks_passed', 'scoring_performed')),
                'REVE software control scope or outcome differs')
        controls = {key: controls[key] for key in ('kind', 'test_events', 'test_participants', 'targets_used_for_control_selection',
                    'trained_model_execution', 'event_identity_join_exercised', 'original_metric_path_exercised',
                    'paired_comparator_path_exercised', 'expected_metric_and_paired_difference_checks_passed', 'scoring_performed')}
        controls['prediction_policy'] = text(doc['software_controls']['prediction_policy'])
        condition = 'released-code full-panel preparation and fixed-output full-test scorer control'
    else:
        require(executed['commit'] is None and 'publication_commit' in executed
                and executed.get('binding_status') == 'reviewed_post_execution_source_identity',
                'DeepCaImX must preserve its unrecorded execution revision')
        require(before == after, 'DeepCaImX current source differs from reviewed publication snapshot')
        require(all(integer(coverage[key]) == expected for key, expected in
                    (('manual_roi_files', 10), ('recordings', 10), ('manual_rois', 1563), ('donors', 8),
                     ('movie_headers_inspected', 10), ('source_movie_intervals_acquired', 0), ('model_inference_tiles', 0)))
                and coverage['image_shape'] == [488, 488] and all(type(item) is int for item in coverage['image_shape'])
                and coverage['complete_original_roi_panel'] is True, 'DeepCaImX source population or execution scope differs')
        coverage = {key: coverage[key] for key in ('manual_roi_files', 'recordings', 'manual_rois', 'donors', 'image_shape',
                    'complete_original_roi_panel', 'movie_headers_inspected', 'source_movie_intervals_acquired', 'model_inference_tiles')}
        require(integer(controls['authentic_target_controls_passed']) == 2
                and controls['conditions'] == ['identity_software_control', 'empty_software_control']
                and integer(controls['generated_source_controls_passed']) == 30
                and integer(controls['retained_evaluator_controls_passed']) == 18,
                'DeepCaImX source control coverage differs')
        controls = {key: controls[key] for key in ('authentic_target_controls_passed', 'conditions',
                                                  'generated_source_controls_passed', 'retained_evaluator_controls_passed')}
        controls.update(population=text(doc['software_controls']['population']),
                        interpretation=text(doc['software_controls']['interpretation']))
        condition = 'manual ROI conversion and complete-panel identity/empty scorer controls'
    retained, identifiers = [], set()
    require(type(doc['retained_evidence']) is list and 0 < len(doc['retained_evidence']) <= 100,
            'bounded retained evidence identities required')
    for pin in doc['retained_evidence']:
        obj(pin)
        identifier = text(pin['id'])
        require(set(pin) == {'id', 'bytes', 'sha256'} and identifier not in identifiers
                and all(c.isascii() and (c.isalnum() or c in '_-') for c in identifier),
                'retained evidence identity repeats or carries a locator')
        identifiers.add(identifier)
        retained.append({'id': identifier, 'bytes': integer(pin['bytes'], 1), 'sha256': digest(pin['sha256'])})
    row = record(Path(source['path']).stem, expected_task, 'paper_source_preparation', source, '',
                 doc['scope'], condition, doc['limits'])
    row.update(coverage=coverage, preparation_controls=controls, source_execution=executed,
               current_source=current, input_exposure=text(doc['input_exposure']), retained_evidence=retained,
               model_attempts_recorded=0, solver_attempts_recorded=0, author_baseline_qualified=False,
               scientific_result=False, original_records_in_publication=False)
    if not is_reve:
        row['source_parity'] = {key: text(obj(doc['source_parity'])[key]) for key in
                              ('checkpoint_architecture', 'crop_mapping', 'frame_mapping', 'tiling_assembly_trace')}
    for key in ('report_date', 'execution_utc_date'):
        if key in doc:
            row[key] = text(doc[key])
    return [row]


def exact_counts(value, expected, label):
    value = obj(value)
    require(all(integer(value[key]) == count for key, count in expected.items()), label + ' counts differ')
    return {key: value[key] for key in expected}


def extent(value):
    require(type(value) is int and 0 < value <= 1024 ** 4, 'invalid published byte extent')
    return value


def pin_map(value, expected_names):
    value = obj(value)
    require(set(value) == set(expected_names), 'published pin inventory differs')
    result = {}
    for name, pin in value.items():
        obj(pin)
        require(set(pin) == {'bytes', 'sha256'}, 'published pin must not carry an extra locator')
        result[name] = {'bytes': extent(pin['bytes']), 'sha256': digest(pin['sha256'])}
    return result


def smc_preparation_records(doc, source):
    require(type(doc.get('schema_version')) is int and doc['schema_version'] == 1
            and doc.get('schema') == 'smc_source_preparation_evidence_v1'
            and doc.get('kind') == 'paper_source_preparation' and doc.get('task_id') == 'PAPER-SMC-RNN-2024'
            and all(doc[key] is False for key in ('author_baseline_calibration_complete', 'author_baseline_qualified',
                'candidate_improvement_evaluated', 'participant_episode_executed', 'scientific_qualification', 'scientific_result'))
            and integer(doc['model_trials']) == 0 and integer(doc['solver_attempts']) == 0,
            'SMC preparation cannot inherit model execution or qualification')
    coverage = exact_counts(doc['coverage'], {'bin_ms': 20, 'forward_bins': 10, 'heldin_neurons': 137,
        'heldout_neurons': 45, 'observation_bins': 35, 'source_conditions': 108, 'source_excluded_rows': 0,
        'source_neurons': 182, 'source_trials': 2869}, 'SMC source population')
    coverage['test'] = exact_counts(doc['coverage']['test'], {'train': 2295, 'eval': 574}, 'SMC test')
    coverage['validation'] = exact_counts(doc['coverage']['validation'], {'train': 1721, 'eval': 574}, 'SMC validation')
    coverage['condition_scope'] = text(doc['coverage']['condition_scope'])
    references = obj(doc['coverage']['reference_manifests'])
    require(set(references) == {'reference_panel.json', 'reference_validation_panel.json'}, 'SMC reference set differs')
    for name, expected_hash in (('reference_panel.json', SMC_PUBLIC_PANEL),
                               ('reference_validation_panel.json', '772123900caed9a8fdfc7799cb5496e70ff89620cbb01d271afb960ef86ed54a')):
        require(obj(references[name]) == {'path': 'implementations/source-matched-nlb-v1/' + name, 'sha256': expected_hash},
                'SMC public reference projection identity differs')
    prefix = 'implementations/source-matched-nlb-v1/'
    executed_names = {prefix + name for name in ('prepare.py', 'memory_prepare.py', 'preparation_memory.patch', 'control_memory_preparation.py')}
    current_names = executed_names | {prefix + name for name in ('delivery.py', 'scorer.py', 'reference_panel.json',
                                                                 'reference_validation_panel.json', 'control_temporal_access.py')}
    def normalized(snapshot, names, execution=False):
        snapshot = obj(snapshot)
        require(type(snapshot['files']) is list and {obj(pin)['path'] for pin in snapshot['files']} == names,
                'SMC task-relative source inventory differs')
        expanded = {**snapshot, 'files': [{**pin, 'path': SMC_HOME + pin['path']} for pin in snapshot['files']]}
        return source_snapshot(expanded, {SMC_HOME + name for name in names}, execution=execution)
    executed = normalized(doc['source_execution'], executed_names, True)
    current = normalized(doc['current_source'], current_names)
    require(executed['commit'] is None and 'publication_commit' in executed
            and executed.get('binding_status') == 'reviewed_post_execution_source_identity',
            'SMC preparation must preserve its uncommitted execution source')
    current_pins = {pin['path']: pin for pin in current['files']}
    require(all(current_pins[pin['path']] == pin for pin in executed['files']), 'SMC executed preparation source changed')
    require(all(current_pins[SMC_HOME + reference['path']]['sha256'] == reference['sha256']
                for reference in references.values()),
            'SMC reference snapshot contradicts coverage')
    delivery = obj(doc['paired_delivery'])
    delivery_counts = exact_counts(delivery, {'shared_files': 12, 'code_only_source_files': 28,
        'code_condition_additions': 29, 'total_files': 56}, 'SMC paired material')
    require(extent(delivery['total_payload_bytes']) == 27828070 and delivery['audit_passed'] is True
            and delivery['status'] == 'participant_materials_prepared'
            and all(delivery[key] is False for key in ('checkpoints_included', 'operator_predictions_included',
                'episode_executed', 'temporal_access_enforced', 'test_target_payloads_included')),
            'SMC paired material access or execution scope differs')
    require(obj(delivery['phase_counts']) == {'test': coverage['test'], 'val': coverage['validation']}
            and obj(delivery['dimensions']) == {'forward_bins': 10, 'heldin': 137, 'heldout': 45, 'observation_bins': 35},
            'SMC paired material dimensions differ')
    preparation = obj(doc['preparation'])
    versions = {text(key): text(value) for key, value in obj(preparation['versions']).items()}
    require(preparation['python'] == '3.9.6' and versions.get('pandas') == '1.3.4'
            and preparation['complete_original_fields_preserved'] is True and preparation['test_target_accessed'] is False,
            'SMC original preparation environment or exposure differs')
    retained = []
    seen = set()
    for pin in doc['retained_evidence']:
        obj(pin)
        identifier = text(pin['id'])
        require(set(pin) == {'id', 'bytes', 'sha256'} and identifier not in seen
                and all(c.isascii() and (c.isalnum() or c in '._-') for c in identifier), 'SMC retained identity invalid')
        seen.add(identifier)
        retained.append({'id': identifier, 'bytes': extent(pin['bytes']), 'sha256': digest(pin['sha256'])})
    require('smc.preparation_environment-json' in seen and len(retained) == 8, 'SMC retained preparation evidence incomplete')
    row = record('smc-original-source-preparation', 'PAPER-SMC-RNN-2024', 'paper_source_preparation', source, '',
                 doc['scope'], 'complete original MC_Maze 20-ms preparation and paired materials', doc['limits'])
    row.update(coverage=coverage, source_execution=executed, current_source=current, retained_evidence=retained,
               preparation_controls={key: text(obj(doc['software_controls'])[key]) for key in ('mandatory_scorer', 'preparation_parity', 'temporal_access')},
               preparation_environment={'python': '3.9.6', 'machine': text(preparation['machine']), 'versions': versions,
                                       'role': 'Original NWB preparation; pandas 1.5.3 preparation was rejected.'},
               paired_delivery={**delivery_counts, 'total_payload_bytes': 27828070, 'audit_passed': True,
                                'participant_episode_executed': False, 'temporal_access_enforced': False,
                                'test_target_payloads_included': False, 'pair_manifest_sha256': digest(delivery['pair_manifest_sha256'])},
               input_exposure={key: text(obj(doc['input_exposure'])[key]) for key in ('boundary', 'original_test_targets', 'validation')},
               model_attempts_recorded=0, solver_attempts_recorded=0, author_baseline_qualified=False,
               scientific_result=False, original_records_in_publication=False)
    return [row]


def smc_probe_records(doc, source, preparation):
    require(preparation is not None, 'SMC author probes require their preparation report')
    prepared, preparation_pin = preparation
    require(doc.get('schema') == 'smc_native_cost_characterization_v1' and doc.get('task_id') == 'PAPER-SMC-RNN-2024'
            and all(doc[key] is False for key in ('author_baseline_qualified', 'complete_predictions', 'scientific_result', 'test_targets_accessed')),
            'SMC partial author probes cannot assert complete calibration or scientific results')
    require(revision(doc['source_commit']) == obj(prepared['source'])['author_commit']
            and doc['panel_sha256'] == SMC_ACTUAL_PANEL
            and prepared['coverage']['reference_manifests']['reference_panel.json']['sha256'] == SMC_PUBLIC_PANEL,
            'SMC author source or actual/public panel identity differs')
    arms = obj(doc['arms'])
    require(set(arms) == {'causal', 'noncausal'}, 'both SMC author inference probes required')
    allocation = obj(doc['full_repeat_memory_control'])
    require(all(allocation[key] is True for key in ('generated_only', 'arithmetic_checks_passed'))
            and allocation['model_executed'] is False and allocation['target_access'] is False
            and integer(allocation['repeats']) == 32 and allocation['train_shape'] == [2295, 45, 182]
            and allocation['eval_shape'] == [574, 45, 182], 'generated allocation control must remain separate from model inference')
    allocation_summary = {'generated_only': True, 'model_executed': False, 'target_access': False, 'repeats': 32,
                          'control_sha256': digest(allocation['control_sha256']), 'source_sha256': digest(allocation['source_sha256'])}
    result = []
    for arm, values in arms.items():
        values = obj(values)
        require(integer(values['particles']) == 192 and integer(values['source_requested_repeats']) == 32
                and values['smooth'] is False, 'SMC author inference recipe differs')
        require(type(values['seed']) is int and 0 <= values['seed'] < 2 ** 32,
                'invalid SMC inference seed')
        versions = {text(key): text(value) for key, value in obj(values['versions']).items()}
        require(versions.get('pandas') == '1.5.3' and versions.get('torch') == '2.3.1', 'SMC frozen-H5 inference environment differs')
        timings = values['timings']
        require(type(timings) is list and len(timings) == 2, 'SMC probe requires one train and one eval chunk')
        seen, observed = set(), []
        for timing in timings:
            timing = obj(timing)
            split = timing['split']
            require(split in ('train', 'eval') and split not in seen, 'duplicate or unknown SMC probe split')
            seen.add(split)
            trials, chunk, chunks, source_chunks = (2295, 33, 70, 71) if split == 'train' else (574, 34, 17, 17)
            exact_counts(timing, {'n_trials': trials, 'chunk_trials': chunk, 'actual_chunks': chunks,
                                 'source_chunks': source_chunks, 'full_repeats': 32}, 'SMC chunk coverage')
            require(timing['full_array_shape'] == [chunk, 182, 45, 192] and timing['finite_nonnegative'] is True,
                    'SMC native chunk output shape or finite check differs')
            observed.append({'split': split, 'observed_chunk_trials': chunk, 'complete_split_trials': trials,
                             'wall_seconds': number(timing['wall_seconds']), 'cpu_seconds': number(timing['cpu_seconds'])})
            require(observed[-1]['wall_seconds'] > 0 and observed[-1]['cpu_seconds'] > 0, 'invalid measured native chunk cost')
        row = record('smc-author-inference-probe:' + arm, 'PAPER-SMC-RNN-2024', 'author_model_inference_probe', source,
                     '/arms/' + arm, 'Actual selected author-checkpoint inference on the first train and eval chunks only; no complete predictions, scores or 32-repeat baseline.',
                     arm + ' author model, 192 particles, filtered outputs', [
                         'Two partial author-model probes are not candidate or solver attempts.',
                         'These historical probes do not establish full-panel, all-repeat author calibration or printed-score linkage.',
                         'Full-run time and memory projections are estimates; generated allocation controls are not model inference.',
                         'Original test targets were publicly exposed, but were not accessed by these probes.'])
        row.update(model_executed=True, author_model_probe_count=1, native_inference_calls=2,
                   observed_chunks=observed, particles=192, source_requested_repeats=32, seed=values['seed'],
                   author_source_commit=doc['source_commit'], source_snapshot_sha256=digest(doc['source_snapshot_sha256']),
                   source_postcheck_sha256=digest(doc['source_postcheck_sha256']),
                   panel_identity_roles={'actual_prepared_panel_sha256': SMC_ACTUAL_PANEL,
                       'public_reference_projection_sha256': SMC_PUBLIC_PANEL,
                       'relationship': 'The public reference is an independently reviewed exact metadata subset of the same native panel, preserving H5 file/content, order and count identities; the distinct hashes identify different JSON bodies.',
                       'relationship_review': {'bytes': 5312, 'sha256': '736add808b2d29fd321cb291069de0a9318e89bcaf0815b28b0e100428b7fe68'}},
                   preparation_report=preparation_pin,
                   inference_environment={'python': '3.11', 'machine': 'arm64', 'versions': versions,
                       'role': 'Reads frozen prepared H5 inputs only; does not perform NWB preparation.',
                       'identity_basis': 'Separately retained preparation-environment receipt and independent native/public panel relationship review.'},
                   preparation_environment={'python': prepared['preparation']['python'], 'pandas': prepared['preparation']['versions']['pandas'],
                                            'role': 'Original NWB preparation, separately executed under Python 3.9 and pandas 1.3.4.'},
                   generated_allocation_control=allocation_summary, complete_predictions=False, scoring_performed=False,
                   solver_attempts_recorded=0, candidate_attempts_recorded=0, author_baseline_calibration_complete=False,
                   author_baseline_qualified=False, scientific_result=False, original_records_in_publication=False)
        result.append(row)
    return result


def smc_original_panels(phases):
    phases = obj(phases)
    require(set(phases) == {'test', 'val'}, 'SMC complete original panel phases required')
    result = {}
    for phase, n_train in (('test', 2295), ('val', 1721)):
        panel = obj(phases[phase])
        result[phase] = exact_counts(panel, {'bin_ms': 20, 'condition_count': 108,
            'forward_bins': 10, 'n_bins': 35, 'n_eval': 574, 'n_heldin': 137,
            'n_heldout': 45, 'n_train': n_train}, 'SMC original panel')
        require(panel['phase'] == phase and panel['dataset'] == 'mc_maze_20',
                'SMC original panel identity differs')
    return result


def smc_calibration_records(doc, source):
    require(doc.get('schema') == 'smc_source_calibration_report_draft_v1'
            and doc.get('task_id') == 'PAPER-SMC-RNN-2024'
            and doc.get('status') == 'author_reference_calibration_outputs_accepted_with_recovered_noncausal_aggregate_publication_review_pending'
            and doc['ready_for_publication'] is False, 'unsupported SMC calibration report')
    completion = obj(doc['completion'])
    require(all(completion[key] is True for key in ('all_four_metrics_per_arm_reviewed',
        'author_reference_calibration_outputs_accepted', 'both_aggregates_authenticated',
        'both_original_scoring_children_completed', 'both_predictions_frozen'))
        and all(completion[key] is False for key in ('both_supervised_scoring_stages_passed',
        'candidate_episode_executed', 'controlled_ai_pass', 'llm_study_executed'))
        and completion['full_source_qualification'] is None
        and completion['publication_review_accepted'] is None
        and doc['execution_counts']['llm_study_executed'] is False,
        'SMC accepted reference outputs cannot imply full supervision or candidate qualification')
    exact_counts(doc['execution_counts'], {'candidate_runs': 0, 'completed_full_author_prediction_runs': 2,
        'original_scoring_children': 2, 'scoring_retries': 0, 'supervised_scoring_failures': 1,
        'supervised_scoring_stage_attempts': 2}, 'SMC calibration execution scope')
    disposition = obj(doc['root_disposition'])
    require(disposition['status'] == 'accepted_existing_recovered_reference_calibration_output_only'
        and disposition['accepted_existing_noncausal_aggregate'] is True
        and disposition['failure_receipt_preserved'] is True
        and disposition['fully_successful_noncausal_supervised_stage_claimed'] is False
        and disposition['retry_authorized'] is False,
        'SMC recovered output requires the preserved failed-stage disposition')
    scoring = obj(doc['scoring'])
    names = ['co-bps', 'vel R2', 'psth R2', 'fp-bps']
    require(scoring['required_metrics'] == names and scoring['tolerance_is_success_criterion'] is False
        and number(scoring['diagnostic_tolerance']) == 0.01
        and scoring['input_group'] == 'mc_maze_20' and scoring['result_group'] == 'mc_maze_20_split',
        'SMC diagnostic tolerance is not a reproduction success rule')
    require(doc['data']['full_panel_only'] is True and doc['data']['data_values_in_report'] is False,
            'SMC calibration report must retain its complete metadata-only scope')
    panels = smc_original_panels(doc['data']['phases'])
    arms = obj(doc['arms'])
    require(set(arms) == {'causal', 'noncausal'}, 'both SMC calibration arms required')
    limits = texts(doc['claim_limits'])
    require(bool(limits), 'SMC calibration interpretation limits required')
    limits = limits + ['The 108 conditions describe the source cohort, not 108 nonempty scored PSTHs.']
    rows = []
    for arm in ('causal', 'noncausal'):
        values = obj(arms[arm])
        causal = arm == 'causal'
        expected_status = ('authenticated_aggregate_supervision_succeeded' if causal
                           else 'accepted_recovered_reference_calibration_aggregate_supervision_failed')
        require(values['status'] == expected_status and values['native_prediction_complete'] is True
                and values['all_four_metrics_finite'] is True and values['source_chain_after_run_verified'] is True
                and integer(values['particles']) == 192 and integer(values['repeats']) == 32
                and values['smooth'] is False and values['independent_repeat_uncertainty'] is None,
                'SMC calibration arm scope differs')
        execution = obj(values['scoring_execution'])
        require(integer(execution['scorer_child_exit_code']) == 0
                and integer(execution['supervisor_exit_code']) == (0 if causal else 1)
                and execution['supervisor_success'] is causal
                and execution['native_ledger_status'] == ('succeeded' if causal else 'failed'),
                'SMC scorer output and supervisor lifecycle must remain distinct')
        if not causal:
            require(execution['failure'] == 'ValueError: Scorer identity changed'
                    and execution['existing_aggregate_root_admitted'] is True,
                    'SMC noncausal failure and recovered-output acceptance required')
        else:
            require(execution['failure'] is None, 'SMC causal successful supervisor has a failure')
        observed, published, deltas = (obj(values[key]) for key in
            ('observed_metrics', 'published_metrics', 'signed_delta_observed_minus_published'))
        require(all(set(group) == set(names) for group in (observed, published, deltas)),
                'SMC all four original metrics required')
        metrics = []
        for name in names:
            value, reference, delta = number(observed[name]), number(published[name]), number(deltas[name])
            require(delta == value - reference, 'SMC observed-minus-published delta differs')
            metrics.append({**metric(name, value, 'higher', {'published_same_method': reference}),
                            'signed_delta_observed_minus_published': delta})
        row = record('smc-author-reference-calibration:' + arm, 'PAPER-SMC-RNN-2024',
            'author_reference_calibration', source, '/arms/' + arm,
            'Complete selected author predictions and four original aggregate metrics; recovered noncausal output retains its failed supervisor.',
            arm + ' released author model, 192 particles and 32 averaged repeats', limits)
        row.update(metrics=metrics, original_panels=panels, scored_phase='test',
            validation_panel_role='Original input metadata only; no validation scoring is inferred.', status=expected_status,
            particles=192, repeats=32, scoring_execution={key: execution[key] for key in
                ('scorer_child_exit_code', 'supervisor_exit_code', 'supervisor_success', 'native_ledger_status', 'failure')},
            diagnostic_tolerance=0.01, tolerance_is_success_criterion=False,
            independent_repeat_uncertainty=None, candidate_attempts_recorded=0, solver_attempts_recorded=0,
            recovered_output_accepted=not causal,
            original_report_state={'schema': doc['schema'], 'status': text(doc['status']),
                'ready_for_publication': doc['ready_for_publication'],
                'publication_review_accepted': completion['publication_review_accepted'],
                'meaning': 'Preserved report-assembly state, not a new publication or qualification decision.'},
            retained_evidence={key: digest(values[key]) for key in
                ('prediction_sha256', 'freeze_receipt_sha256', 'score_report_sha256',
                 'score_supervisor_receipt_sha256', 'aggregate_authentication_review_sha256')})
        rows.append(row)
    return rows


def smc_rescore_records(doc, source, calibration):
    """Project the accepted later score-only run without replacing prior failures."""
    require(calibration is not None, 'SMC rescore requires the historical calibration report')
    prior, prior_source = calibration
    # Validate the predecessor's failed noncausal supervision as well as its values.
    smc_calibration_records(prior, prior_source)
    require(doc.get('schema') == 'smc_frozen_reference_rescore_public_result_v1'
            and doc.get('result_kind') == 'successful_bounded_historical_reference_scoring'
            and doc.get('task_id') == 'PAPER-SMC-RNN-2024'
            and doc.get('date_utc') == '2026-11-20'
            and doc.get('original_task') == 'MC_Maze, 20 ms bins; complete original prepared test panel'
            and doc.get('models') == ['causal', 'noncausal'], 'unsupported SMC rescore report')
    interpretation = obj(doc['interpretation'])
    require(all(interpretation[key] is False for key in ('AI_or_candidate_trial',
        'new_author_model_inference_or_training', 'exact_checkpoint_to_Table2_mapping_established',
        'exact_original_DANDI_revision_established', 'exact_paper_reproduction_claim',
        'improvement_or_SOTA_claim', 'matched_paper_only_vs_code_assisted_experiment'))
        and interpretation['no_arbitrary_0_01_or_rounding_tolerance'] is True,
        'SMC rescoring cannot become inference, a participant attempt or paper success')
    old = obj(doc['historical_noncausal_supervision'])
    require(integer(old['child_exit_code']) == 0 and integer(old['supervisor_exit_code']) == 1
            and old['supervisor_success'] is False and old['preserved_as_failed'] is True
            and old['current_success_does_not_rewrite_history'] is True
            and old['failure'] == 'ValueError: Scorer identity changed',
            'SMC rescore must preserve the earlier noncausal supervisor failure')
    closure = obj(doc['closure'])
    exact_counts(closure, {'Docker_CLI_calls': 12, 'Docker_CLI_calls_closed': 12,
        'explicitly_owned_groups_observed_absent': 14, 'known_host_PIDs_observed_absent': 15,
        'native_exit_code': 0}, 'SMC rescore owned closure')
    require(all(closure[key] is True for key in ('grader_container_removed_and_absence_observed',
        'native_lease_released', 'outer_full_EOF')) and closure['escaped_descendant_containment_claim'] is False,
        'SMC rescore cannot omit known closure or assert escaped-descendant containment')
    limits = obj(doc['whole_two_score_limits'])
    # These byte/CPU extents exceed the generic small population-count bound.
    expected_limits = {'child_CPU_hard_seconds': 605, 'child_CPU_soft_seconds': 600,
        'child_memory_bytes': 2147483648, 'child_numerical_CPU_quota': 1,
        'cleanup_seconds': 60, 'host_declared_memory_bytes': 536870912, 'work_seconds': 720}
    require(all(type(limits[key]) is int and limits[key] == value for key, value in expected_limits.items())
            and limits['host_hard_memory_guarantee'] is False and limits['one_budget_no_per_model_reset'] is True,
            'SMC rescore shared two-score resource limits differ')
    resources = obj(doc['observed_resources'])
    require(integer(resources['child_exit_code']) == 0 and resources['child_OOMKilled'] is False
            and resources['current_child_CPU_seconds'] is None
            and resources['current_child_peak_RSS_bytes'] is None,
            'SMC rescore unmeasured CPU/RSS cannot become observations')
    walls = {key: number(resources[key]) for key in ('host_wall_seconds', 'native_wall_seconds', 'outer_wall_seconds')}
    require(all(value > 0 for value in walls.values()), 'SMC rescore wall times must be positive')
    versions = {'h5py': '3.10.0', 'numpy': '1.26.3', 'scikit-learn': '1.5.0', 'scipy': '1.12.0'}
    require(doc['numerical_versions'] == versions
            and doc['historical_numerical_versions'] == {**versions, 'h5py': '3.11.0'}
            and doc['intentional_runtime_variant'] == {'historical': '3.11.0', 'package': 'h5py', 'selected': '3.10.0'},
            'SMC rescore must preserve its declared h5py runtime variant')
    identities = pin_map(doc['software_identities'],
        {'original_nlb_tools_0_0_3_evaluator', 'original_score_predictions_source'})
    names = ('co-bps', 'vel R2', 'psth R2', 'fp-bps')
    vectors = obj(doc['metrics'])
    require(set(vectors) == {'causal', 'noncausal'}, 'SMC rescore requires both complete metric vectors')
    claim_limits = [text(interpretation[key]) for key in ('canonical_evaluator_fit', 'target_exposure',
        'trajectory_sets', 'paper_comparison', 'prior_failed_attempt')]
    claim_limits += ['This is the recorded November 20 score-only operation, not a fresh runtime verification.',
                     'Historical/current-release checkpoint scoring does not prove exact Table 2 checkpoint or data-revision linkage.']
    rows = []
    for arm in ('causal', 'noncausal'):
        groups = obj(vectors[arm])
        require(set(groups) == {'current', 'historical', 'paper_printed',
            'current_minus_historical', 'current_minus_paper_printed'}, 'SMC rescore metric groups differ')
        require(all(set(obj(group)) == set(names) for group in groups.values()),
                'SMC rescore requires all four original metrics for each model')
        metrics = []
        for name in names:
            current, historical, printed, delta_old, delta_paper = (number(groups[key][name]) for key in
                ('current', 'historical', 'paper_printed', 'current_minus_historical', 'current_minus_paper_printed'))
            require(historical == number(prior['arms'][arm]['observed_metrics'][name])
                    and printed == number(prior['arms'][arm]['published_metrics'][name]),
                    'SMC rescore historical/printed values disagree with preserved calibration')
            require(delta_old == current - historical and delta_paper == current - printed,
                    'SMC rescore signed metric differences disagree')
            metrics.append({**metric(name, current, 'higher', {'historical_same_prediction': historical,
                                                             'paper_printed_same_method': printed}),
                'signed_delta_current_minus_historical': delta_old,
                'signed_delta_current_minus_paper_printed': delta_paper})
        row = record('smc-historical-reference-rescore:' + arm, 'PAPER-SMC-RNN-2024',
            'historical_reference_rescore', source, '/metrics/' + arm,
            'Successful bounded rescoring of a complete previously frozen author prediction; no new author-model inference or AI candidate.',
            arm + ' frozen historical/current-release author prediction, original MC_Maze 20 ms scoring', claim_limits)
        row.update(metrics=metrics, execution_date_utc=doc['date_utc'],
            status='reported_successful_bounded_historical_reference_scoring',
            historical_calibration_source=prior_source, whole_two_score_limits={**expected_limits,
                'host_hard_memory_guarantee': False, 'one_budget_no_per_model_reset': True},
            observed_resources={**walls, 'child_exit_code': 0, 'child_OOMKilled': False,
                'current_child_CPU_seconds': None, 'current_child_peak_RSS_bytes': None},
            historical_noncausal_supervisor_success=False, historical_failure_preserved=True,
            reported_known_owned_closure=True, canonical_train_decoder_fitting=True,
            software_identities=identities, numerical_versions=versions,
            new_author_model_inference_or_training=False, solver_attempts_recorded=0,
            candidate_attempts_recorded=0, model_attempts_recorded=0,
            exact_paper_reproduction_claim=False, improvement_or_SOTA_claim=False)
        rows.append(row)
    return rows


def smc_material_records(doc, source):
    require(doc.get('schema') == 'smc_official_assets_material_validation_receipt_v2'
        and doc.get('task_id') == 'PAPER-SMC-RNN-2024'
        and doc.get('status') == 'complete_current_participant_materials_prepared_and_independently_verified'
        and integer(doc['registered_benchmark_count_delta']) == 0,
        'unsupported SMC material preparation report')
    interpretation = obj(doc['interpretation'])
    require(all(interpretation[key] is False for key in ('AI_execution', 'checkpoint_deserialization',
        'model_loading_training_inference_or_scoring', 'original_test_target_access'))
        and interpretation['reproduction_result'] == interpretation['improvement_result'] == 'not_attempted',
        'SMC material preparation cannot imply participant execution or results')
    materials = obj(doc['materials'])
    conditions = ['paper_data', 'paper_data_author_code_and_weights']
    require(materials['conditions'] == conditions and integer(materials['file_count']) == 71
        and extent(materials['total_bytes']) == 31393479 and integer(materials['official_asset_count']) == 10
        and materials['published_payload'] is False
        and all(materials[key] is True for key in ('all_assets_assisted_only', 'shared_materials_identical',
            'unknown_files_original_test_targets_and_operator_predictions_absent')),
        'SMC material inventory or access separation differs')
    require(set(obj(materials['condition_manifest_sha256'])) == set(conditions), 'SMC material conditions differ')
    panels = smc_original_panels(materials['original_source_panels'])
    validation = obj(doc['validation'])
    exact_counts(validation, {'failed_or_retried_attempts': 0, 'inspect_attempts': 1, 'prepare_attempts': 1},
                 'SMC material validation attempts')
    require(set(obj(validation['stages'])) == {'inspect', 'prepare'}
            and all(integer(obj(stage)['exit_code']) == 0 for stage in validation['stages'].values()),
            'SMC material stages must preserve successful completion')
    review_pins = {key: digest(validation[key]) for key in
                  ('independent_final_review_sha256', 'independent_saved_file_review_sha256')}
    row = record('smc-official-assets-materials-v2', 'PAPER-SMC-RNN-2024',
        'participant_material_preparation', source, '/materials',
        'Complete external 71-file paper/data and author-code/released-model material pair; payloads are not published in this report.',
        'paper_data versus paper_data_author_code_and_weights; version2 material preparation',
        [text(interpretation['scientific_limits']), text(interpretation['participant_runtime_enforcement']),
         'This receipt records its original material pair and resource profiles; later exports remain separate.'])
    row.update(coverage={'files': 71, 'total_bytes': 31393479, 'official_assets': 10},
        original_panels=panels, conditions=conditions,
        condition_manifest_sha256={key: digest(value) for key, value in materials['condition_manifest_sha256'].items()},
        pair_manifest_sha256=digest(materials['pair_manifest_sha256']), published_payload=False,
        independent_review_sha256=review_pins,
        participant_episode_executed=False, model_attempts_recorded=0, solver_attempts_recorded=0,
        reproduction_result='not_attempted', improvement_result='not_attempted')
    return [row]


def neural096_preparation_records(doc, source):
    require(doc.get('schema') == 'neural096_authentic_source_preparation_summary_v1' and doc.get('task_id') == 'NEURAL-096'
            and doc.get('status') == 'complete_declared_source_observations_prepared' and doc.get('execution_commit') is None
            and all(doc[key] is False for key in ('full_task_completed', 'scientific_qualified'))
            and all(integer(doc[key]) == 0 for key in ('fits', 'new_model_trials', 'reference_contrasts')),
            'NEURAL-096 source preparation cannot claim contrasts, models or qualification')
    coverage = exact_counts(doc['observations'], {'empty_support_cells_preserved': 3, 'excluded_selected_trials': 0,
        'nlb_heldin_units': 40, 'nlb_heldout_units': 14, 'packet_bytes': 640017, 'phase_bins': 20,
        'recording_observation_segments': 6, 'retained_spikes': 81311, 'source_train': 150,
        'source_validation': 54, 'trials': 204, 'units': 54, 'unsupported_selected_trials': 0}, 'NEURAL-096 preparation')
    require(all(doc['observations'][key] is True for key in ('all_native_timestamps_retained', 'source_sha256_verified')),
            'NEURAL-096 source timestamp or identity check differs')
    verification = obj(doc['verification'])
    require(verification['authentic_preparation_success'] is True and verification['independent_saved_packet_audit'] == 'passed'
            and verification['prior_cue_metadata_roster_match'] is True
            and verification['independent_source_spike_reread'] is False
            and verification['additional_14_unit_ids_independently_recovered'] is False,
            'NEURAL-096 saved-packet audit cannot become independent NWB or held-out-unit recovery')
    exact_counts(verification, {'generated_passed': 33, 'generated_platform_skipped': 1,
                               'independently_recounted_trial_unit_bins': 220320}, 'NEURAL-096 verification')
    sources = pin_map(doc['executed_source_files'], {'PROTOCOL.json', 'core.py', 'prepare.py'})
    retained = pin_map(doc['evidence_receipt_pins'], {'SOURCE_FREEZE.json', 'audit-run.json', 'native-run.json',
        'numerical-review/FINAL_REVIEW.json', 'numerical-review/GENERATED_CONTROLS-02.json', 'numerical-review/REVIEW.json',
        'numerical-review/SAVED_PACKET_AUDIT-01.json', 'prepared-v1/receipt.json', 'source-review/DOCUMENTATION_REVIEW.json',
        'source-review/PREPARATION_SCIENCE_REVIEW.json', 'source-review/REVIEW.json'})
    original = obj(doc['source'])
    require(integer(original['animal_count']) == 1 and integer(original['session_count']) == 1
            and original['previously_exposed'] is True, 'NEURAL-096 source population/exposure differs')
    row = record('neural096-authentic-source-preparation', 'NEURAL-096', 'neural_source_preparation', source, '',
                 'Complete declared Set–Go source observations prepared; saved-packet recount checks internal consistency, not an independent reread of all NWB spikes or a scientific contrast.',
                 'one exposed source session; full retained spike timestamps and count packet',
                 texts(doc['remaining']) + texts(verification['audit_limits']))
    row.update(coverage=coverage, execution_commit=None, execution_attestation=text(doc['execution_attestation']),
               executed_source_files=[{'path': NEURAL096_HOME + name, **pin} for name, pin in sorted(sources.items())],
               retained_evidence=[{'id': name.replace('/', '-'), **pin} for name, pin in sorted(retained.items())],
               source_identity={'sha256': digest(original['sha256']), 'bytes': extent(original['bytes']),
                   'dandiset': text(original['dandiset']), 'version': text(original['version']), 'asset_id': text(original['asset_id']),
                   'animal_count': 1, 'session_count': 1, 'previously_exposed': True},
               verification={'independent_saved_packet_audit': 'passed', 'independently_recounted_trial_unit_bins': 220320,
                   'independent_source_spike_reread': False, 'additional_14_unit_ids_independently_recovered': False,
                   'generated_passed': 33, 'generated_platform_skipped': 1, 'platform_skip': text(verification['platform_skip'])},
               model_attempts_recorded=0, solver_attempts_recorded=0, reference_contrasts=0,
               full_task_completed=False, scientific_result=False, original_records_in_publication=False)
    return [row]


def erp_reference_failure_records(doc, source, narrative):
    """Keep failed fixed-reference execution separate from scored/AI evidence."""
    require(doc.get('schema') == 'neural077-image-reference-calibration-report/v1'
            and doc.get('date') == '2026-11-24' and doc.get('task_id') == 'NEURAL-077'
            and doc.get('evidence_role') == 'public_aggregate_transcription'
            and doc.get('status') == 'incomplete_no_performance_result'
            and doc.get('condition') == 'fixed_initial_image_four_demo_reference',
            'unsupported image-reference failure report')
    require(narrative is not None, 'image-reference narrative is missing')
    require(obj(doc['narrative']) == narrative[1] and narrative[1]['path'] == ERP_REFERENCE_NARRATIVE,
            'image-reference narrative pin mismatch')
    cohort = exact_counts(doc['cohort'], {'people': 32, 'queries_per_person': 200,
        'selected_queries': 6400, 'training_demonstrations': 4}, 'image-reference cohort')
    require(doc['cohort'].get('scope') == 'predefined_full32_complement'
            and doc['cohort'].get('original_registered_development_condition_is_different') is True,
            'image-reference cohort interpretation differs')
    method = obj(doc['method'])
    require(method.get('sha256') == '08286eaab4be66d2dc66f646f475a851ab861ac0337279a5696faefbd9c8bfd6'
            and method.get('unchanged_between_attempts') is True,
            'historical image reference changed')
    display = obj(method['display'])
    require(display.get('channels') == ['Cz', 'Pz'] and display.get('filter') == 'none'
            and type(display.get('start_sample')) is int and display['start_sample'] == -256
            and display.get('amplitude_units') == 'native_stored_units_physical_calibration_unresolved',
            'historical fixed observation differs')
    exact_counts(display, {'stop_sample_exclusive': 768, 'sampling_hz': 1024,
                          'units_per_division': 20}, 'image-reference display')
    attempts = doc['attempts']
    require(type(attempts) is list and len(attempts) == 2, 'both image-reference failures required')
    expected = ({'attempt': 1, 'fitted_models': 0, 'attempted_queries': 0,
                 'complete_query_captures': 0, 'target_body_reads': 0, 'scored_queries': 0},
                {'attempt': 2, 'fitted_models': 1, 'attempted_queries': 62,
                 'complete_query_captures': 61, 'failed_query_attempts': 1,
                 'unattempted_queries': 6338, 'target_body_reads': 0, 'scored_queries': 0,
                 'owned_capture_children_reaped': 62, 'capture_streams_closed': 62})
    projected = []
    for index, (attempt, counts) in enumerate(zip(attempts, expected)):
        checked = exact_counts(attempt, counts, 'image-reference attempt')
        status = ('failed_runtime_preflight', 'failed_no_partial_qualification')[index]
        require(attempt.get('status') == status, 'image-reference failure cannot become success')
        wall = number(attempt['native_wall_seconds'])
        require(wall == (0.099, 15.806)[index], 'frozen image-reference wall time differs')
        projected.append(dict(checked, status=status, native_wall_seconds=wall))
    require(attempts[1].get('full_arm_admitted') is False
            and attempts[1].get('automatic_retry') is False,
            'image-reference partial arm or retry cannot be admitted')
    diagnostic = obj(doc['label_free_diagnostic'])
    visible = exact_counts(diagnostic, {'images': 5, 'query_images': 1, 'fixed_demo_images': 4,
        'unchanged_extractor_calls': 5, 'fit_calls': 0, 'prediction_calls': 0, 'score_calls': 0,
        'private_target_reads': 0, 'postmarker_columns_per_channel': 840,
        'query_defined_features': 0, 'query_missing_features': 30,
        'demo_defined_features_total': 120, 'demo_missing_features_total': 0}, 'visibility diagnostic')
    visible['query_postmarker_visible_columns'] = exact_counts(
        diagnostic['query_postmarker_visible_columns'], {'Cz': 0, 'Pz': 0}, 'visible post-marker columns')
    require(all(diagnostic.get(key) is True for key in ('visible_query_baselines_present',
        'exact_renderer_color_and_extractor_column_masks_agree',
        'decoded_query_scanlines_match_original_projection_identity')),
        'recorded visibility diagnosis differs')
    limits = obj(doc['scientific_limits'])
    require(limits.get('performance_metrics') is None
            and integer(limits['completed_benchmarks_added']) == 0
            and all(limits.get(key) is False for key in ('full_population_run_completed',
                'independent_generalization', 'native_ai_understanding_assessed', 'paper_improvement_assessed'))
            and limits.get('no_inference_of_raw_amplitude_or_query_label') is True,
            'failed reference report cannot promote scientific qualification')
    followup = obj(doc['followup_status'])
    require(followup.get('historical_failures_preserved') is True
            and followup.get('existing_algorithm_and_condition_unchanged') is True
            and followup.get('new_authentic_run_selected_by_this_report') is False,
            'historical failure or execution boundary changed')
    row = record('full32-image-reference-failure-20261124', 'NEURAL-077',
        'image_reference_engineering_failure', source, '/attempts',
        'Two failed engineering executions for the full32 fixed-image reference: one preflight-only; '
        'one four-demo fit and 62 query attempts with 61 complete captures. Zero scoring; no complete calibration.',
        'fixed_initial_image_four_demo_reference', [
            'Exposed-development evidence, not independent generalization or AI/native understanding.',
            'The diagnostic covers one failed image and four fixed demos, not the full population.',
            'Both failures and all cases remain; no partial score or scientific-readiness promotion.',
            'Known owned cleanup closed; escaped-descendant containment and full-arm admission are not claimed.'])
    row.update(status='incomplete_no_performance_result', cohort=cohort, attempts=projected,
        coverage={'engineering_execution_attempts': 2, 'preflight_only_failures': 1,
                  'reference_fits': 1, 'query_capture_attempts': 62, 'complete_query_captures': 61,
                  'failed_query_attempts': 1, 'unattempted_queries': 6338, 'scored_queries': 0},
        diagnostic=visible, metrics=[], narrative=narrative[1], full_task_completed=False,
        solver_attempts_recorded=0, evidence_role='public_aggregate_transcription')
    return [row]


def erp_uncertainty_coverage(value):
    """Validate full-denominator aggregate diagnostics, never per-case payloads."""
    value = obj(value)
    counts = exact_counts(value, {'queries': 6400, 'features_per_query': 30}, 'uncertainty coverage')
    for key in ('no_shared_support_queries', 'positive_shared_support_queries'):
        counts[key] = integer(value[key])
    require(counts['no_shared_support_queries'] + counts['positive_shared_support_queries'] == 6400,
            'uncertainty support denominator differs')
    expected = {'feature_defined_queries': 30, 'feature_mean_coverage': 30,
                'feature_mean_shared_weight': 30, 'baseline_mean_coverage': 2}
    for key, length in expected.items():
        values = value[key]
        require(type(values) is list and len(values) == length, 'uncertainty diagnostic length differs')
        counts[key] = [integer(item) if key == 'feature_defined_queries' else number(item) for item in values]
        ceiling = 6400 if key == 'feature_defined_queries' else 1
        require(all(0 <= item <= ceiling for item in counts[key]), 'uncertainty diagnostic range differs')
    require(all((n > 0) == (mean > 0) and mean <= n / 6400 + 1e-12
                for n, mean in zip(counts['feature_defined_queries'], counts['feature_mean_coverage'])),
            'uncertainty defined-count and mean-coverage contradiction')
    positive_fraction = counts['positive_shared_support_queries'] / 6400
    require(all(weight <= min(coverage, counts['baseline_mean_coverage'][index // 15], positive_fraction) + 1e-12
                for index, (weight, coverage) in enumerate(zip(
                    counts['feature_mean_shared_weight'], counts['feature_mean_coverage']))),
            'uncertainty shared weight exceeds observed support')
    fraction = number(value['mean_shared_support_fraction'])
    require(0 <= fraction <= positive_fraction + 1e-12
            and abs(fraction - sum(counts['feature_mean_shared_weight']) / 30) <= 1e-12,
            'uncertainty shared-weight units differ')
    require((counts['positive_shared_support_queries'] > 0) == (fraction > 0),
            'uncertainty support-count and mean contradiction')
    counts['mean_shared_support_fraction'] = fraction
    counts['feature_order'] = 'Cz fifteen postmarker50ms bins, then Pz fifteen postmarker50ms bins'
    require(value.get('feature_order') == counts['feature_order'], 'uncertainty feature order differs')
    return counts


def erp_uncertainty_records(doc, source, narrative):
    """Index closed reference operations without pooling their qualification units."""
    require(doc.get('schema') == 'neural077-image-uncertainty-calibration-report/v1'
            and doc.get('date') == '2026-11-24' and doc.get('task_id') == 'NEURAL-077'
            and doc.get('status') == 'closed'
            and doc.get('evidence_role') == 'public_aggregate_transcription'
            and doc.get('condition') == 'fixed_initial_image_four_demo_uncertainty_reference',
            'unsupported uncertainty-reference report')
    require(narrative is not None, 'uncertainty-reference narrative is missing')
    require(obj(doc['narrative']) == narrative[1] and narrative[1]['path'] == ERP_UNCERTAINTY_NARRATIVE,
            'uncertainty-reference narrative pin mismatch')
    cohort = exact_counts(doc['cohort'], {'people': 32, 'queries_per_person': 200,
        'selected_queries': 6400, 'training_demonstrations': 4}, 'uncertainty-reference cohort')
    require(doc['cohort'].get('scope') == 'predefined_full32_complement'
            and doc['cohort'].get('exposed_development') is True,
            'uncertainty-reference cohort interpretation differs')
    method = obj(doc['method'])
    require(method.get('algorithm_sha256') == 'c4024cbc5cd2283f1246ff2c99008a212a70689de9e3d410d7ff7f4a49e5cf64'
            and number(method['zero_shared_support_probability']) == .5
            and method.get('positive_support_arithmetic_unchanged') is True,
            'uncertainty-reference method differs')
    policy = obj(doc['metric_policy'])
    require(policy.get('aggregation') == 'equal_person_macro' and policy.get('log_base') == 'natural'
            and number(policy['positive_threshold_inclusive']) == .5
            and number(policy['log_loss_clip']) == 1e-15,
            'uncertainty-reference original metric policy differs')
    display = obj(method['display'])
    require(display.get('channels') == ['Cz', 'Pz'] and display.get('filter') == 'none'
            and type(display.get('start_sample')) is int and display['start_sample'] == -256
            and display.get('amplitude_units') == 'native_stored_units_physical_calibration_unresolved',
            'uncertainty-reference fixed observation differs')
    exact_counts(display, {'stop_sample_exclusive': 768, 'sampling_hz': 1024,
                          'units_per_division': 20}, 'uncertainty-reference display')
    disclosure = obj(doc['root_operator_disclosure'])
    search = exact_counts(disclosure['metadata_hash_search'],
        {'protected_json_files_machine_read': 33, 'protected_json_bytes_machine_read': 756023},
        'root metadata-search disclosure')
    require(disclosure.get('prior_full_population_exposure') is True
            and disclosure.get('global_targets_unopened') is False
            and disclosure.get('isolated_target_last_is_global_custody') is False
            and disclosure['metadata_hash_search'].get('scope') == 'old_materialization'
            and disclosure['metadata_hash_search'].get('matches_or_values_emitted') is False,
            'global disclosure cannot be replaced by isolated worker custody')
    search.update(scope='old_materialization', matches_or_values_emitted=False,
                  read_accounting_basis='conservative_file_extent_accounting', kernel_file_read_census=False)
    limits = obj(doc['scientific_limits'])
    require(all(limits.get(key) is False for key in ('independent_generalization',
        'native_ai_understanding_assessed', 'trained_competency_baseline_established',
        'human_competency_baseline_established', 'paper_improvement_assessed'))
        and integer(limits['completed_benchmarks_added']) == 0
        and integer(limits['solver_attempts_added']) == 0
        and limits.get('historical_failures_preserved') is True,
        'uncertainty-reference report cannot promote scientific qualification')
    operations = doc['operations']
    require(type(operations) is list and len(operations) == 2, 'both closed uncertainty operations required')
    identifiers = ('erp-uncertainty-calibration-20261124-v1',
                   'erp-measured-uncertainty-calibration-20261124-v1')
    rows = []
    for index, (operation, identifier) in enumerate(zip(operations, identifiers)):
        obj(operation)
        require(operation.get('id') == identifier and operation.get('closed') is True,
                'uncertainty operation identity or closure differs')
        counts = obj(operation['counts'])
        keys = ('engineering_executions', 'reference_fits', 'query_capture_attempts',
                'complete_query_captures', 'interrupted_query_captures', 'failed_query_captures',
                'unattempted_queries', 'score_operations', 'scored_queries', 'complete_reference_calibrations')
        counts = {key: integer(counts[key]) for key in keys}
        require(counts['engineering_executions'] == 1 and counts['reference_fits'] <= 1
                and counts['query_capture_attempts'] == counts['complete_query_captures']
                    + counts['interrupted_query_captures'] + counts['failed_query_captures']
                and counts['query_capture_attempts'] + counts['unattempted_queries'] == 6400
                and (counts['query_capture_attempts'] == 0 or counts['reference_fits'] == 1),
                'uncertainty execution, fit and capture units contradict')
        authority = obj(operation['reported_authority'])
        # Publication review is pinned by the handoff; embedding its digest here
        # would make the review and the report depend on each other's hashes.
        authority = {'root_owner_closure_sha256': digest(authority['root_owner_closure_sha256']),
                     'aggregate_or_owner_result_sha256': digest(authority['aggregate_or_owner_result_sha256'])}
        closure = obj(operation['closure'])
        require(all(closure.get(key) is True for key in ('root_owner_closed',
            'all_known_owned_processes_absent', 'all_attempted_capture_streams_closed'))
            and closure.get('escaped_descendant_containment_claim') is False,
            'uncertainty known-owned closure required without stronger containment claim')
        custody = obj(operation['worker_custody'])
        require(custody.get('prediction_worker_query_target_access') == 'not_permitted_by_isolated_protocol'
                and custody.get('basis') == 'root_owner_attestation_and_unchanged_isolated_protocol'
                and custody.get('isolated_target_last') is True
                and custody.get('global_target_unopened_claim') is False,
                'uncertainty worker custody cannot erase global disclosure')
        wall = number(operation['native_wall_seconds'])
        require(wall >= 0, 'uncertainty native wall time must be nonnegative')
        status = operation['status']
        metrics, coverage = [], None
        if index == 0:
            require(status == 'root_early_stopped_unscored', 'U must retain its root early-stop outcome')
            exact_counts(counts, {'engineering_executions': 1, 'reference_fits': 1,
                'query_capture_attempts': 2123, 'complete_query_captures': 2122,
                'interrupted_query_captures': 1, 'failed_query_captures': 0,
                'unattempted_queries': 4277, 'score_operations': 0, 'scored_queries': 0,
                'complete_reference_calibrations': 0}, 'U early-stop')
            require(wall == 904.478, 'frozen U native wall time differs')
            stop = obj(operation['stop'])
            require(stop.get('reason') == 'root_projected_collection_exceeds_frozen_run_allowance'
                    and stop.get('actual_deadline_failure') is False
                    and stop.get('classifier_failure') is False
                    and stop.get('native_ledger_status') == 'failed'
                    and stop.get('empty_response_error_followed_interruption') is True
                    and number(stop['projected_collection_seconds']) == 2813.35991702751
                    and number(stop['frozen_run_work_seconds']) == 2400
                    and number(stop['measured_captures_per_second']) == 2.2832334517236963,
                    'U projected timing stop is not an observed deadline or classifier failure')
        else:
            require(status in ('complete_scored', 'failed_unscored'), 'K requires an actual closed result')
            require(operation.get('fresh_collection_no_reuse_or_resume') is True,
                    'K cannot reuse U partial captures')
        complete = status == 'complete_scored'
        if complete:
            exact_counts(counts, {'reference_fits': 1, 'query_capture_attempts': 6400,
                'complete_query_captures': 6400, 'interrupted_query_captures': 0,
                'failed_query_captures': 0, 'unattempted_queries': 0, 'score_operations': 1,
                'scored_queries': 6400, 'complete_reference_calibrations': 1}, 'complete uncertainty calibration')
            require(custody.get('scorer_gate') == 'all_6400_first_captures_admitted_before_private_access',
                    'complete uncertainty score requires target-last admission')
            scores = obj(operation['aggregate_metrics'])
            ba, loss = number(scores['participant_macro_balanced_accuracy']), number(scores['participant_macro_natural_log_loss'])
            require(0 <= ba <= 1 and loss >= 0, 'invalid uncertainty-reference aggregate metric')
            comparators = obj(operation['analytic_comparators'])
            half, prior = obj(comparators['constant_half']), obj(comparators['constant_source_prior'])
            require(number(half['probability']) == .5 and number(half['balanced_accuracy']) == .5
                    and abs(number(half['natural_log_loss']) - math.log(2)) <= 1e-12
                    and number(prior['probability']) == .2 and number(prior['balanced_accuracy']) == .5
                    and abs(number(prior['natural_log_loss']) - .5004024235381879) <= 1e-12
                    and prior.get('used_by_classifier') is False,
                    'analytic comparators cannot be fitted or substituted into classifier')
            metrics = [metric('participant_macro_balanced_accuracy', ba, 'higher',
                        {'constant_half_analytic': .5, 'constant_source_prior_analytic': .5}),
                       metric('participant_macro_natural_log_loss', loss, 'lower',
                        {'constant_half_analytic': half['natural_log_loss'],
                         'constant_source_prior_analytic': prior['natural_log_loss']})]
            coverage = erp_uncertainty_coverage(operation['support_diagnostics'])
        else:
            require(all(counts[key] == 0 for key in ('score_operations', 'scored_queries',
                                                    'complete_reference_calibrations'))
                    and operation.get('aggregate_metrics') is None
                    and operation.get('analytic_comparators') is None
                    and operation.get('support_diagnostics') is None
                    and custody.get('scorer_gate') == 'not_reached',
                    'unscored uncertainty operation cannot acquire a partial metric or calibration')
        scope = ('Root timing-based early stop: 2,122 complete captured responses, one interrupted and 4,277 unattempted; '
                 'no score, observed deadline failure or classifier failure.' if index == 0 else
                 ('Complete measured-budget fixed-view reference calibration on all 6,400 queries; '
                  'exposed-development aggregate result, not an AI attempt or competence qualification.' if complete else
                  'Closed measured-budget reference execution without a complete score; no partial calibration.'))
        row = record(identifier, 'NEURAL-077', 'image_uncertainty_reference_operation', source,
            '/operations/' + str(index), scope, doc['condition'], [
                'Both operations use the same previously exposed 32-person population; capture totals across operations are not unique cases.',
                'The four-demo image reference is not a trained or human competency baseline and is not an AI solver.',
                'Root machine-search exposure is disclosed separately from isolated target-last prediction/scorer custody.',
                'No independent generalization, physiological P3-presence endpoint, new benchmark or readiness promotion.'])
        row.update(status=status, cohort=cohort, coverage=counts, metrics=metrics, reported_authority=authority,
            support_diagnostics=coverage, native_wall_seconds=wall, narrative=narrative[1],
            reference_calibration_complete=complete, full_task_completed=False, solver_attempts_recorded=0,
            worker_custody={'prediction_worker_query_target_access': 'not_permitted_by_isolated_protocol',
                            'basis': 'root_owner_attestation_and_unchanged_isolated_protocol', 'isolated_target_last': True,
                            'global_target_unopened_claim': False, 'scorer_gate': custody['scorer_gate']},
            root_operator_disclosure={'prior_full_population_exposure': True, 'global_targets_unopened': False,
                'isolated_target_last_is_global_custody': False, 'metadata_hash_search': search})
        if index == 0:
            row['stop'] = {key: operation['stop'][key] for key in (
                'reason', 'actual_deadline_failure', 'classifier_failure', 'native_ledger_status',
                'empty_response_error_followed_interruption', 'projected_collection_seconds',
                'frozen_run_work_seconds', 'measured_captures_per_second')}
        rows.append(row)
    return rows


def bound_public_narrative(captured, relative, size, sha256):
    require(captured is not None, 'reference/provenance narrative is missing')
    require(captured[1] == {'path': relative, 'bytes': size, 'sha256': sha256},
            'reference/provenance narrative pin mismatch')
    return captured[1]


def bounded_public_metric(value, lower=0, upper=1):
    value = number(value)
    require(lower <= value <= upper, 'reference/provenance metric outside its units')
    return value


def language_reference_records(doc, source, provenance, narrative):
    require(doc.get('schema') == 'language-trusted-figure3b-public-aggregate/v1'
            and doc.get('task_id') == 'PAPER-ROOT-ADD-001' and doc.get('attempt') == '003'
            and doc.get('status') == 'complete_trusted_selected_reference'
            and doc.get('scientific_role') == 'trusted_operator_author_reference'
            and doc.get('measured_date') == '2026-11-24', 'unsupported trusted language reference')
    narrative = bound_public_narrative(narrative, LANGUAGE_REFERENCE_NARRATIVE, 4122,
        '1de2ee174e50fe50d1e94088ca80bfaf580cfc81596192af66c5652cc28b889c')
    require(provenance is not None, 'trusted language lifecycle provenance is missing')
    prior, prior_source = provenance
    require(prior_source['path'] == LANGUAGE_REFERENCE_PROVENANCE
            and prior.get('schema') == 'language-trusted-figure3b-public-provenance/v1'
            and prior.get('task_id') == doc['task_id'] and prior.get('measured_date') == doc['measured_date'],
            'trusted language provenance association differs')
    scope = obj(doc['scope'])
    coverage = exact_counts(scope, {'cells': 42, 'sessions': 14, 'people': 8,
        'fresh_Ridge_fits': 5685, 'feature_columns': 30, 'layer_zero_based': 5}, 'trusted language scope')
    require(scope.get('original_figure') == '3b' and scope.get('family') == 'context'
            and scope.get('field') == 'population' and number(scope['Ridge_alpha']) == .01
            and scope.get('lag_indices') == [17, 18, 19] and scope.get('lag_bins') == [-3, -2, -1],
            'trusted language original endpoint differs')
    exact_counts(doc, {'defined_cell_pairs': 42, 'cell_receipts_verified': 42,
                      'fresh_prediction_files_verified': 42, 'defined_session_pairs': 14}, 'trusted language completion')
    require(doc.get('aggregation') == 'Pooled Pearson across original held-qid prediction rows per cell; mean three fixed lags per session; equal mean of all14sessions.'
            and all(doc.get(key) is True for key in ('all_contexts_and_fit_totals_verified',
                'prediction_and_receipt_sha256_verification', 'source_reference_read_after_all_fits')),
            'trusted language original aggregation or fit admission differs')
    claims = obj(doc['claims'])
    require(claims.get('complete_selected_trusted_Figure3b_reference') is True
            and all(claims.get(key) is False for key in ('AI_improvement', 'AI_result', 'SOTA',
                'arbitrary_participant_isolation_exercised', 'full224_array_or_whole_paper_reproduction',
                'matched_AI_information_arms_compared', 'participant_NativeProvider_qualified')),
            'trusted operator result cannot promote participant or whole-paper qualification')
    attempts = prior['attempt_history']
    require(type(attempts) is list and len(attempts) == 3, 'all three language execution attempts required')
    projected = []
    for index, (attempt, fits) in enumerate(zip(attempts, (0, 0, 5685)), 1):
        attempt = obj(attempt)
        require(attempt.get('attempt') == f'{index:03d}' and integer(attempt['fits']) == fits
                and attempt.get('all_spawned_process_scopes_closed') is True,
                'trusted language attempt identity, fit or closure differs')
        if index < 3:
            require(integer(attempt['authentic_scientific_input_body_reads']) == 0,
                    'pre-worker language failures cannot acquire scientific reads')
        if index == 1:
            require(attempt.get('container_created') is False, 'first language failure was before container creation')
        if index == 2:
            require(attempt.get('container_created') is True and attempt.get('container_started') is False
                    and attempt.get('owned_container_removed_absent') is True,
                    'second language failure must remain a closed prestart refusal')
        if index == 3:
            require(attempt.get('scientific_source_retuned') is False
                    and attempt.get('owned_container_removed_absent') is True,
                    'completed language replay cannot retune scientific source')
        projected.append({'attempt': f'{index:03d}', 'estimator_fits': fits,
            'status': ('failed_before_container', 'failed_before_worker', 'complete_trusted_reference')[index - 1]})
    author = obj(prior['provided_author_reference'])
    require(author.get('read_into_predictor') is False and author.get('read_only_after_all5685fits') is True
            and author.get('sha256') == 'd822f284c2d781f920841705a63fec38d3267ee5c62e5dd5635272cf087e49c9',
            'trusted language reference must remain outside predictor inputs')
    completion = obj(doc['completion'])
    require(completion.get('inner_owner') == completion.get('outer_owner') == 'complete'
            and completion.get('native_controller') == 'succeeded'
            and completion.get('oom_killed') is False
            and all(completion.get(key) is True for key in ('all_bounded_stdout_stderr_streams_closed',
                'controller_reaped_and_process_group_absent', 'owned_container_removed_and_absent')),
            'trusted language owned closure differs')
    exact_counts(completion, {'scientific_worker_exit_code': 0, 'owned_Docker_CLI_scopes_closed': 8},
                 'trusted language owned closure')
    fresh = bounded_public_metric(doc['fresh_reference_equal_session_mean'], -1, 1)
    provided = bounded_public_metric(doc['provided_author_equal_session_mean'], -1, 1)
    paired = bounded_public_metric(doc['equal_session_paired_mean_delta'], -2, 2)
    maximum = bounded_public_metric(doc['max_absolute_cell_difference'], 0, 2)
    require(abs(fresh - provided) <= maximum + 1e-15 and abs(paired) <= maximum,
            'trusted language paired/grand mean discrepancies contradict cell bounds')
    worker, outer = number(doc['worker_elapsed_seconds']), number(doc['outer_elapsed_seconds'])
    require(0 <= worker <= outer, 'trusted language worker/outer clocks differ')
    runtime = obj(prior['numerical_runtime'])
    require(runtime.get('python') == '3.11.3'
            and runtime.get('versions') == {'numpy': '1.24.3', 'scipy': '1.10.1', 'sklearn': '1.2.2'}
            and type(runtime.get('loaded_pools')) is list and len(runtime['loaded_pools']) == 3
            and all(integer(pool['num_threads']) == 1 for pool in runtime['loaded_pools']),
            'trusted language historical runtime differs')
    row = record('language-trusted-figure3b-reference-20261124', 'PAPER-ROOT-ADD-001',
        'trusted_operator_reference', source, '/',
        'Complete selected Figure 3b trusted reference: 42 cells, 14 sessions, eight people and 5,685 fresh Ridge fits; '
        'two earlier zero-fit failures remain. Numerical reference agreement is not participant or whole-paper qualification.',
        'trusted_operator_original_contextual_population_figure3b', [
            'Eight people are the clusters; cells, sessions and fits are distinct units.',
            'Original retrospective preprocessing, public exposure and the 579-versus-567 unit issue remain.',
            'The paired mean difference has its own reduction; it is not subtraction of serialized grand means.',
            'No participant NativeProvider, fresh-exec isolation, full224-array reconstruction, AI improvement or readiness claim.'])
    row.update(coverage=dict(coverage, engineering_execution_attempts=3, preworker_failures=2,
                            complete_reference_endpoints=1), attempts=projected,
        metrics=[metric('equal_session_mean_Pearson', fresh, 'higher', {'provided_author_reference': provided})],
        comparison={'equal_session_paired_mean_delta': paired, 'max_absolute_cell_difference': maximum,
                    'new_acceptance_tolerance_or_improvement_margin': False},
        timing={'worker_seconds': worker, 'outer_seconds': outer},
        reference_read_after_all_fits=True, attachments=[prior_source, narrative], narrative=narrative,
        solver_attempts_recorded=0, full_task_completed=False, participant_provider_qualified=False)
    return [row]


def umbrae_reference_records(doc, source, narrative):
    require(doc.get('schema') == 'umbrae-released-author-reference-rescore-evidence/v1'
            and doc.get('task_id') == 'PAPER-paper-method-042'
            and doc.get('experiment_id') == 'umbrae-author-reference-rescore-20261124-001'
            and doc.get('status') == 'complete_released_author_output_rescore',
            'unsupported UMBRAE released-output reference')
    narrative = bound_public_narrative(narrative, UMBRAE_RESCORE_NARRATIVE, 3028,
        '36264bc9267ee88b04c1d2253170569e8579b961798ad96f52620f1098ed69ba')
    subjects = ['S1', 'S2', 'S5', 'S7']
    groups = {'All': 2419, 'Salient': 1343, 'Salient Creatures': 700, 'Salient Objects': 643, 'Inconspicuous': 1076}
    missing = {'S1': 8, 'S2': 1, 'S5': 2, 'S7': 1}
    thresholds = ('0.3', '0.5', '0.7')
    require(doc.get('subject_order') == subjects and doc.get('source_seeds') == [0, 1]
            and all(type(seed) is int for seed in doc['source_seeds'])
            and integer(doc['canonical_keyed_seed']) == 0 and doc.get('thresholds') == [.3, .5, .7]
            and doc.get('threshold_comparison') == 'strict greater-than'
            and doc.get('box_selection') == 'First reference box and first extracted prediction; original within-category order unchanged.',
            'UMBRAE source/keyed selection differs')
    population = obj(doc['population'])
    exact_counts(population, {'images': 982, 'boxes': 5829, 'queries': 2419}, 'UMBRAE population')
    exact_counts(population['group_counts'], groups, 'UMBRAE overlapping groups')
    require(set(population['group_counts']) == set(groups)
            and population.get('native_index_join_only') is True
            and population.get('NSD_COCO_stimulus_join_authenticated') is False
            and doc.get('source_commit_dates_not_proof_of_public_release_or_table_production') is True,
            'UMBRAE released-output result cannot resolve historical/stimulus lineage')
    require(integer(doc['source_metric_cells_per_seed']) == 80 and doc.get('round_to_published_two_decimal_percent') is True,
            'complete UMBRAE source panels required')
    panels, keyed, diagnostics = obj(doc['source_panels']), obj(doc['canonical_keyed_float64_panel']), obj(doc['canonical_keyed_float32_diagnostics'])
    require(set(panels) == {'0', '1'} and set(keyed) == set(diagnostics) == set(subjects),
            'complete source seeds and keyed subject panels required')
    primary, reported = obj(doc['recovered_primary_percent_by_seed']), obj(doc['published_v2_primary_percent'])
    require(set(primary) == {'0', '1'} and set(reported) == set(subjects), 'UMBRAE primary vector differs')
    for panel in (*panels.values(), keyed, diagnostics):
        require(set(obj(panel)) == set(subjects), 'complete UMBRAE subject panel required')
        require(all(set(obj(panel[subject])) == set(groups) for subject in subjects), 'complete overlapping group panel required')
    seed_differences, keyed64_differences, precision_differences = [], [], []
    for subject in subjects:
        for group, count in groups.items():
            left, right, canonical, diag = (obj(value) for value in (panels['0'][subject][group],
                panels['1'][subject][group], keyed[subject][group], diagnostics[subject][group]))
            accuracy = []
            for cell in (left, right, canonical):
                require(integer(cell['query_count']) == count, 'UMBRAE failed outputs must stay in full denominators')
                bounded_public_metric(cell['mean_iou'])
                values = obj(cell['accuracy']); require(set(values) == set(thresholds), 'all UMBRAE thresholds required')
                accuracy.append({key: bounded_public_metric(values[key]) for key in thresholds})
                require(accuracy[-1]['0.3'] >= accuracy[-1]['0.5'] >= accuracy[-1]['0.7'],
                        'UMBRAE threshold accuracy is not monotone')
            for cell in (left, right):
                require(cell.get('status') == 'scored' and integer(cell['target_failed']) == 0
                        and integer(cell['failed']) <= count, 'UMBRAE source panel status or failure denominator differs')
            invalid = integer(canonical['missing_or_invalid'])
            require(invalid == integer(left['failed']) == integer(right['failed']) <= count,
                    'UMBRAE missing/empty outputs differ across scoring views')
            require(diag.get('source_positional_pairing_compatible') is True, 'UMBRAE pair alignment differs')
            bounds = obj(diag['threshold_decision_disagreements_float32_vs_float64'])
            exact_counts(bounds, {key: 0 for key in thresholds}, 'UMBRAE precision decisions')
            require(set(bounds) == set(thresholds), 'complete UMBRAE precision thresholds required')
            keyed32 = {key: bounded_public_metric(obj(diag['keyed_float32_accuracy'])[key]) for key in thresholds}
            require(set(diag['keyed_float32_accuracy']) == set(thresholds)
                    and accuracy[0] == accuracy[1] == accuracy[2] == keyed32,
                    'reported UMBRAE accuracy agreement contradicts panels')
            bounded_public_metric(diag['keyed_float32_mean_iou'])
            statuses = obj(diag['keyed_prediction_status_counts'])
            require(set(statuses) <= {'valid', 'empty_extraction'} and 'valid' in statuses
                    and integer(statuses['valid']) + integer(statuses.get('empty_extraction', 0)) == count
                    and integer(statuses.get('empty_extraction', 0)) == invalid,
                    'UMBRAE empty answers cannot disappear from keyed counts')
            if group == 'All':
                require(invalid == missing[subject], 'UMBRAE full-denominator empty-answer count differs')
            seed_differences.append(abs(left['mean_iou'] - right['mean_iou']))
            keyed64_differences.append(abs(left['mean_iou'] - canonical['mean_iou']))
            precision_differences.append(bounded_public_metric(diag['max_abs_iou_float32_minus_float64']))
        for seed in ('0', '1'):
            require(set(obj(primary[seed])) == set(subjects), 'complete UMBRAE primary subject vector required')
            percent = bounded_public_metric(primary[seed][subject], 0, 100)
            require(abs(percent - 100 * panels[seed][subject]['All']['accuracy']['0.5']) <= 1e-12
                    and round(percent, 2) == bounded_public_metric(reported[subject], 0, 100),
                    'UMBRAE fraction/percent primary result mismatch')
    comparison = obj(doc['ordering_and_precision_comparison'])
    comparison_counts = exact_counts(comparison, {'source_accuracy_cells_compared': 60,
        'source_seed_accuracy_cell_differences': 0, 'source_seed0_vs_keyed_float32_accuracy_cell_differences': 0,
        'float32_vs_float64_threshold_decision_differences_across_overlapping_groups': 0,
        'subject_group_traversals_changed_between_seeds': 20}, 'UMBRAE ordering/precision comparison')
    exact_counts(comparison['all_subject_missing_or_invalid_counts'], missing, 'UMBRAE missing outputs')
    require(comparison.get('all_query_pairs_aligned_both_seeds') is True
            and number(comparison['maximum_source_seed_mean_iou_difference']) == max(seed_differences) > 0
            and number(comparison['maximum_source_seed0_vs_keyed64_mean_iou_difference']) == max(keyed64_differences)
            and number(comparison['maximum_individual_iou_float32_vs_float64_difference']) == max(precision_differences),
            'UMBRAE mean/precision summary contradicts complete panels')
    runtime = obj(doc['runtime'])
    require(runtime.get('all_owned_scopes_closed') is True and integer(runtime['retries']) == 0
            and runtime.get('historical_runtime_authenticated') is False
            and runtime.get('RAM_is_cooperative_plan_not_measured_peak_or_OS_limit') is True,
            'UMBRAE runtime scope cannot become historical or hard-quota qualification')
    wall = number(runtime['elapsed_complete_operation_seconds']); require(wall >= 0, 'invalid UMBRAE wall time')
    row = record('umbrae-released-output-rescore-20261124', 'PAPER-paper-method-042',
        'released_output_scoring_reference', source, '/recovered_primary_percent_by_seed',
        'Complete released-output scoring for four subjects and 2,419 query identities per subject: two source-seed '
        '80-cell panels plus one keyed float64 panel. Rounding agreement is not new fMRI inference or universal scorer equivalence.',
        'trusted_released_author_outputs_category_conditioned_grounding', [
            'The five category groups overlap; source seeds and panels are repeated diagnostics, not independent biological replicates.',
            'All empty outputs remain in denominators. No model inference, fitting, candidate/AI result or readiness increment.',
            'All 60 accuracy cells agree, while mean-IoU reduction differences remain; not all 80 cells are bit-identical.',
            'Agreement is specific to these released outputs and does not prove interchangeable scoring for future candidates.',
            'Historical table-producing identity, native stimulus joins and participant isolation remain unresolved.'])
    row.update(coverage={'rescore_operations': 1, 'subjects': 4, 'query_identities_per_subject': 2419,
        'subject_query_evaluations': 9676, 'source_seed_passes': 2, 'source_metric_cells_per_pass': 80,
        'source_metric_cells_across_passes': 160, 'keyed_float64_panels': 1, 'keyed_metric_cells': 80},
        metrics=[metric(subject + '_All_IoU_gt_0.5_percent', primary['0'][subject], 'higher',
                        {'paper_rounded_percent': reported[subject]}) for subject in subjects],
        diagnostics=dict(comparison_counts, maximum_source_seed_mean_iou_difference=max(seed_differences),
            maximum_source_vs_keyed64_mean_iou_difference=max(keyed64_differences), empty_answers_by_subject=missing,
            all_80_cells_bit_identical=False, universal_scorer_equivalence=False),
        narrative=narrative, native_wall_seconds=wall, solver_attempts_recorded=0,
        reference_fits=0, new_model_inference_runs=0, full_task_completed=False)
    return [row]


def annotation_provenance_records(doc, source, narrative):
    require(doc.get('schema') == 'deepcaimx-four-pair-annotation-provenance-result/v1'
            and doc.get('task') == 'PAPER-paper-method-013' and doc.get('date') == '2026-11-24'
            and doc.get('result') == 'complete_exact_binary_annotation_relation',
            'unsupported annotation provenance result')
    narrative = bound_public_narrative(narrative, ANNOTATION_NARRATIVE, 2666,
        'e7f45da139ac7e0e1cb212823ebbd996e250cb337b7e9c6ccb84eb5c7e6e108a')
    population = obj(doc['population'])
    exact_counts(population, {'recording_count': 4, 'original_paper_recording_count': 10,
                             'ROIs_per_source_population': 1050}, 'annotation population')
    require(population.get('full_original_paper_cohort_qualified') is False
            and doc.get('reproduction_or_improvement_success') is False
            and integer(doc['benchmark_ready_increment']) == 0,
            'annotation relation cannot promote model or whole-paper qualification')
    recordings = {'501271265': 237, '501704220': 176, '524691284': 355, '531006860': 282}
    declared = population['recordings']
    require(type(declared) is list and len(declared) == 4
            and {text(item['recording_id']): integer(item['ROIs_per_source']) for item in declared} == recordings,
            'complete selected annotation recording counts required')
    conditions = [(orientation, x, y) for orientation in ('as_stored', 'spatial_axes_swapped')
                  for x, y in ((0, 0), (0, 1), (1, 0), (1, 1))]
    def condition_key(row):
        offset = row['zero_padding_offset']
        require(type(offset) is list and len(offset) == 2 and all(type(x) is int for x in offset),
                'annotation offsets must be exact integer pairs')
        key = (row['orientation'], *offset)
        require(key in conditions, 'annotation condition outside prespecified set')
        return key
    cohort = doc['prespecified_conditions']
    require(type(cohort) is list and len(cohort) == 8 and [condition_key(x) for x in cohort] == conditions,
            'all eight unique annotation conditions required')
    pairs = doc['complete_per_recording_conditions']
    require(type(pairs) is list and len(pairs) == 4
            and [item['recording_id'] for item in pairs] == list(recordings), 'all four unique annotation pairs required')
    totals = {key: [0, 0] for key in conditions}
    for pair in pairs:
        count = recordings[pair['recording_id']]
        require(integer(pair['ROIs_per_source']) == count, 'annotation pair denominator differs')
        rows = pair['conditions']
        require(type(rows) is list and len(rows) == 8 and [condition_key(x) for x in rows] == conditions,
                'all 32 unique annotation pair-conditions required')
        for cell, key in zip(rows, conditions):
            expected = count if key == ('spatial_axes_swapped', 0, 0) else 0
            exact_counts(cell, {'roi_count_per_source': count, 'ordered_matching_roi_count': expected,
                'multiset_matching_roi_count_per_source': expected, 'ordered_nonmatching_roi_count': count - expected,
                'deep_nonmatching_roi_count': count - expected, 'st_nonmatching_roi_count': count - expected},
                'annotation exact relation')
            require(cell.get('ordered_whole_mask_equal') is (expected == count)
                    and cell.get('multiplicity_preserving_multiset_equal') is (expected == count),
                    'annotation equality flags contradict exact counts')
            for family in ('deep_duplicates', 'st_duplicates'):
                exact_counts(cell[family], {'unique_mask_count': count, 'duplicate_excess_count': 0,
                    'duplicate_mask_class_count': 0, 'rois_in_duplicate_classes_count': 0}, 'annotation multiplicity')
            totals[key][0] += cell['ordered_matching_roi_count']
            totals[key][1] += cell['multiset_matching_roi_count_per_source']
    projected = []
    for item, key in zip(cohort, conditions):
        ordered, multiset = totals[key]
        exact_counts(item, {'ordered_exact_matches': ordered, 'multiset_exact_matches_per_source': multiset},
                     'annotation cohort relation')
        require(item.get('whole_cohort_ordered_equal') is (ordered == 1050)
                and item.get('whole_cohort_multiset_equal') is (multiset == 1050),
                'annotation cohort equality contradicts complete pair sums')
        projected.append({'orientation': key[0], 'zero_padding_offset': list(key[1:]),
            'ordered_exact_matches': ordered, 'multiset_exact_matches_per_source': multiset})
    validity = obj(doc['validity'])
    require(all(validity.get(key) is True for key in ('all8sources_complete_finite_exact_binary',
        'equality_is_complete_bytes_not_IoU_or_digest_only', 'every_prespecified_condition_retained',
        'no_normalization_or_threshold', 'no_posthoc_condition_selection')),
        'annotation exact binary/multiplicity/condition scope differs')
    exact_counts(validity, {'duplicate_excess_per_source_pair': 0, 'nonfinite_or_nonbinary_values': 0}, 'annotation validity')
    verification = obj(doc['verification'])
    require(verification.get('native_complete') is True and integer(verification['native_attempts']) == 1,
            'annotation operation must be complete and separate from model execution')
    row = record('deepcaimx-annotation-representation-20261124', 'PAPER-paper-method-013',
        'annotation_representation_provenance', source, '/prespecified_conditions',
        'Four annotation pairs and all 1,050 ROIs per source match in order and multiplicity under axes swap plus '
        'zero padding at (0,0); all eight declared conditions remain. This is annotation correspondence, not model performance.',
        'operator_only_exact_annotation_representation_comparison', [
            'The transform describes stored annotations, not raw movie coordinates or causal lineage.',
            'The six other recordings, full ten-video endpoint, original frames/crop and N15/P9 checkpoint assembly remain open.',
            'No segmentation F1, model fit, prediction, paper reproduction/improvement or readiness increment.'])
    row.update(coverage={'native_comparisons': 1, 'recording_pairs': 4, 'source_arrays': 8,
        'ROIs_per_source': 1050, 'cohort_conditions': 8, 'pair_conditions': 32},
        conditions=projected, metrics=[], narrative=narrative, solver_attempts_recorded=0,
        model_performance_assessed=False, causal_lineage_established=False, full_task_completed=False)
    return [row]


def load(root, task_ids=None):
    """Read optional known reports; reject malformed present reports.

    If task_ids is supplied, it is the current registered-ID allowlist, not an
    output filter. A report cannot silently attach evidence to an unknown task.
    Missing reports yield no records, useful for minimal checkout/test fixtures.
    """
    root = Path(root).resolve()
    require(root.is_dir(), 'repository root must be a directory')
    if task_ids is not None:
        require(not isinstance(task_ids, str), 'task ID allowlist must be a collection')
        task_ids = set(task_ids)
        require(all(type(item) is str and item for item in task_ids), 'invalid task ID allowlist')
    records, reports, captured_reports = {}, [], {}
    for relative, project in ((PILOT, pilot_records), (HISTORY, historical_records),
                              (DIRECT, engineering_records), (VIEWER, lambda doc, source: engineering_records(doc, source, True)),
                              (NATIVE, native_operator_records), (TRANSPORT, viewer_transport_records),
                              (NATIVE_REPAIR, native_operator_records),
                              (REVE_PREPARATION, paper_preparation_records), (DEEP_PREPARATION, paper_preparation_records),
                              (SMC_PREPARATION, smc_preparation_records),
                              (SMC_PROBES, lambda doc, source: smc_probe_records(doc, source, captured_reports.get(SMC_PREPARATION))),
                              (NEURAL096_PREPARATION, neural096_preparation_records),
                              (SMC_CALIBRATION, smc_calibration_records),
                              (SMC_RESCORE, lambda doc, source: smc_rescore_records(doc, source, captured_reports.get(SMC_CALIBRATION))),
                              (SMC_MATERIALS, smc_material_records),
                              (ERP_PILOT, lambda doc, source: exploratory_erp_records(
                                  doc, source, read_bytes(root, ERP_NARRATIVE))),
                              (ERP_REFERENCE_FAILURE, lambda doc, source: erp_reference_failure_records(
                                  doc, source, read_bytes(root, ERP_REFERENCE_NARRATIVE))),
                              (ERP_UNCERTAINTY_CALIBRATION, lambda doc, source: erp_uncertainty_records(
                                  doc, source, read_bytes(root, ERP_UNCERTAINTY_NARRATIVE))),
                              (LANGUAGE_REFERENCE, lambda doc, source: language_reference_records(doc, source,
                                  read_json_attachment(root, LANGUAGE_REFERENCE_PROVENANCE),
                                  read_bytes(root, LANGUAGE_REFERENCE_NARRATIVE))),
                              (UMBRAE_RESCORE, lambda doc, source: umbrae_reference_records(doc, source,
                                  read_bytes(root, UMBRAE_RESCORE_NARRATIVE))),
                              (ANNOTATION_PROVENANCE, lambda doc, source: annotation_provenance_records(doc, source,
                                  read_bytes(root, ANNOTATION_NARRATIVE)))):
        try:
            captured = read(root, relative)
            if captured is None:
                continue
            doc, source = captured
            projected = project(doc, source)
            if relative == NATIVE_REPAIR:
                checked_native_repair_lineage(doc, captured_reports.get(NATIVE))
            captured_reports[relative] = (doc, source)
            reports.append(source)
            for row in projected:
                require(task_ids is None or row['task_id'] in task_ids, 'report names unregistered task: ' + row['task_id'])
                records.setdefault(row['task_id'], []).append(row)
        except (KeyError, TypeError, IndexError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError('Invalid public evidence report: ' + relative + ': ' + str(exc)) from exc
    records = {task: sorted(items, key=lambda item: item['id']) for task, items in sorted(records.items())}
    categories = Counter(row['category'] for items in records.values() for row in items)
    result_counts = {
        'tasks_with_recorded_evidence': len(records), 'public_reports': len(reports),
        'pilot_attempts': categories['paper_calibration_attempt'] + categories['neural_programme_attempt'],
        'paper_calibration_attempts': categories['paper_calibration_attempt'],
        'neural_programme_attempts': categories['neural_programme_attempt'],
        'direct_interpretation_attempts': sum(row['coverage']['episode_attempts'] for items in records.values()
                                              for row in items if row['category'] == 'exploratory_direct_interpretation'),
        'exploratory_programme_authoring_attempts': sum(row['coverage']['authoring_attempts'] for items in records.values()
                                                       for row in items if row['category'] == 'exploratory_frozen_programme'),
        'exploratory_programme_query_applications': sum(row['coverage']['query_applications'] for items in records.values()
                                                       for row in items if row['category'] == 'exploratory_frozen_programme'),
        'exploratory_fixed_image_pilot_reports': categories['exploratory_direct_interpretation'],
        'viewer_interpretation_attempts': 0,
        'image_reference_failed_calibration_reports': categories['image_reference_engineering_failure'],
        **{'image_reference_' + suffix: sum(row['coverage'][key] for items in records.values() for row in items
                                           if row['category'] == 'image_reference_engineering_failure')
           for suffix, key in (('engineering_execution_attempts', 'engineering_execution_attempts'),
                               ('preflight_only_failures', 'preflight_only_failures'), ('fits', 'reference_fits'),
                               ('query_capture_attempts', 'query_capture_attempts'),
                               ('complete_query_captures', 'complete_query_captures'), ('scored_queries', 'scored_queries'))},
        'uncertainty_reference_reports': len({row['source']['path'] for items in records.values() for row in items
                                              if row['category'] == 'image_uncertainty_reference_operation'}),
        'uncertainty_reference_operations': categories['image_uncertainty_reference_operation'],
        'uncertainty_reference_root_early_stops': sum(row['status'] == 'root_early_stopped_unscored'
            for items in records.values() for row in items if row['category'] == 'image_uncertainty_reference_operation'),
        **{'uncertainty_reference_' + key: sum(row['coverage'][key] for items in records.values() for row in items
                                              if row['category'] == 'image_uncertainty_reference_operation')
           for key in ('engineering_executions', 'reference_fits', 'query_capture_attempts',
                       'complete_query_captures', 'interrupted_query_captures', 'failed_query_captures',
                       'unattempted_queries', 'score_operations', 'scored_queries', 'complete_reference_calibrations')},
        'trusted_operator_reference_reports': categories['trusted_operator_reference'],
        **{'trusted_operator_reference_' + key: sum(row['coverage'][field] for items in records.values() for row in items
                                                   if row['category'] == 'trusted_operator_reference')
           for key, field in (('execution_attempts', 'engineering_execution_attempts'), ('preworker_failures', 'preworker_failures'),
                              ('estimator_fits', 'fresh_Ridge_fits'), ('complete_endpoints', 'complete_reference_endpoints'),
                              ('cells', 'cells'), ('sessions', 'sessions'), ('people', 'people'))},
        'released_output_rescore_reports': categories['released_output_scoring_reference'],
        **{'released_output_rescore_' + key: sum(row['coverage'][field] for items in records.values() for row in items
                                                if row['category'] == 'released_output_scoring_reference')
           for key, field in (('operations', 'rescore_operations'), ('subjects', 'subjects'),
                              ('source_passes', 'source_seed_passes'), ('keyed_panels', 'keyed_float64_panels'),
                              ('subject_query_evaluations', 'subject_query_evaluations'))},
        'annotation_provenance_reports': categories['annotation_representation_provenance'],
        **{'annotation_provenance_' + key: sum(row['coverage'][key] for items in records.values() for row in items
                                              if row['category'] == 'annotation_representation_provenance')
           for key in ('recording_pairs', 'ROIs_per_source', 'cohort_conditions', 'pair_conditions')},
        'authentic_engineering_reports': categories['authentic_input_materialization'] + categories['authentic_viewer_rendering'] + categories['authentic_viewer_transport'],
        'authentic_viewer_transport_reports': categories['authentic_viewer_transport'],
        'paper_source_preparation_reports': categories['paper_source_preparation'],
        'neural_source_preparation_reports': categories['neural_source_preparation'],
        'author_model_inference_probes': categories['author_model_inference_probe'],
        'author_reference_calibration_arms': categories['author_reference_calibration'],
        'author_reference_calibration_reports': len({row['source']['path'] for items in records.values() for row in items
                                                   if row['category'] == 'author_reference_calibration'}),
        'historical_reference_rescore_models': categories['historical_reference_rescore'],
        'historical_reference_rescore_operations': len({row['source']['path'] for items in records.values() for row in items
                                                       if row['category'] == 'historical_reference_rescore'}),
        'participant_material_preparation_reports': categories['participant_material_preparation'],
        'author_model_inference_probe_reports': len({row['source']['path'] for items in records.values() for row in items
                                                   if row['category'] == 'author_model_inference_probe'}),
        'paper_source_preparation_tasks': sum(any(row['category'] == 'paper_source_preparation' for row in items)
                                             for items in records.values()),
        'scripted_viewer_sessions': sum(row['coverage']['valid_unscored_sessions'] for items in records.values() for row in items
                                        if row['category'] == 'authentic_viewer_transport'),
        'historical_profiles': categories['historical_paper_calibration'] + categories['historical_programme_control'],
        'historical_programme_controls': sum(len(row.get('controls', [])) for items in records.values() for row in items
                                            if row['category'] == 'historical_programme_control'),
        'native_operator_controls': sum(len(row['controls']) for items in records.values() for row in items
                                        if row['category'] == 'native_operator_control'),
        'native_operator_control_reports': len({row['source']['path'] for items in records.values() for row in items
                                               if row['category'] == 'native_operator_control'}),
        'native_control_tasks': sum(any(row['category'] == 'native_operator_control' for row in items)
                                    for items in records.values()),
        'engineering_reports_with_generated_controls': sum('software_controls' in row for items in records.values() for row in items),
    }
    return {'schema_version': 1, 'kind': 'public_recorded_evidence_summary',
            'records': records, 'reports': reports, 'counts': result_counts, 'scope': SCOPE,
            'count_definitions': {
                'pilot_attempts': 'Attempts in the historical November 17 difficulty pilot only.',
                'neural_programme_attempts': 'Programme attempts in the historical November 17 difficulty pilot only.',
                'direct_interpretation_attempts': 'Fresh direct-image episode attempts, including delivery failures.',
                'historical_reference_rescore_models': 'Previously frozen author predictions scored again; not new model or AI attempts.',
                'historical_reference_rescore_operations': 'Shared score-only operations; each may score multiple frozen models.',
                'image_reference_engineering_execution_attempts': 'Failed reference executions, including preflight-only failure; not AI attempts or successful calibration arms.',
                'image_reference_fits': 'Authentic four-demo reference fits; separate from query applications and scored results.',
                'image_reference_query_capture_attempts': 'First query capture attempts, including refused output; not completed scientific benchmarks.',
                'uncertainty_reference_operations': 'Closed fixed-view reference executions; repeated exposed-development cohort, not AI attempts.',
                'uncertainty_reference_reference_fits': 'Four-demo fits across the closed uncertainty-reference operations; not independently authored methods.',
                'uncertainty_reference_query_capture_attempts': 'Capture attempts summed across operations, including interrupted/failed captures; not unique cases.',
                'uncertainty_reference_scored_queries': 'Queries in complete scored reference calibrations only; unscored captures remain separate.',
                'uncertainty_reference_complete_reference_calibrations': 'Complete exposed-development reference calibrations; not completed benchmarks or competence qualifications.',
                'trusted_operator_reference_execution_attempts': 'Engineering attempts for the fixed trusted reference, including zero-fit pre-worker failures; not participant or AI attempts.',
                'trusted_operator_reference_estimator_fits': 'Fresh Ridge estimator fits across 42 cells; eight people are the clusters, not 5685 independent people.',
                'trusted_operator_reference_complete_endpoints': 'Complete selected trusted reference endpoints; not whole-paper or participant qualification.',
                'released_output_rescore_subject_query_evaluations': 'Four subject outputs for 2419 shared query identities; not 9676 unique stimuli and not a sum of overlapping groups.',
                'released_output_rescore_source_passes': 'Prespecified hash-seed scoring passes over frozen author outputs; no model inference or fits.',
                'annotation_provenance_ROIs_per_source': 'ROIs across four selected recordings in each of two annotation families; not model predictions or F1 scores.',
                'annotation_provenance_pair_conditions': 'All four pairs under eight prespecified representation conditions; repeated comparisons, not 32 recordings.',
                'exploratory_programme_authoring_attempts': 'Generated programmes authored; query applications are counted separately.',
                'exploratory_programme_query_applications': 'First applications of the frozen programme, including runtime failures.'}}
