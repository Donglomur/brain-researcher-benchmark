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
NEURAL096_HOME = 'benchmarks/neural/NEURAL-096/implementations/full-set-go-v1/'
NEURAL096_PREPARATION = NEURAL096_HOME + 'AUTHENTIC_PREPARATION.json'
SMC_ACTUAL_PANEL = '3b160dfb4aef8c68cbae8d4a02d5933576a77e4bc47a7c3a5b484369caf95be5'
SMC_PUBLIC_PANEL = '209a15e2189499a9e68264df5c9f81057dd919564d98a46fb64d75b3f39af2f3'
PUBLIC_REPORTS = (PILOT, HISTORY, DIRECT, VIEWER, NATIVE, TRANSPORT, NATIVE_REPAIR, REVE_PREPARATION, DEEP_PREPARATION,
                  SMC_PREPARATION, SMC_PROBES, NEURAL096_PREPARATION)
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


def read(root, relative):
    """Read one allowlisted ordinary report without resolving embedded locators."""
    require(relative in PUBLIC_REPORTS, 'report is not allowlisted')
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
    return obj(document), {'path': relative, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


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
                         'Full-panel, all-repeat author calibration and printed-score linkage remain unqualified.',
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
                              (NEURAL096_PREPARATION, neural096_preparation_records)):
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
        'direct_interpretation_attempts': 0, 'viewer_interpretation_attempts': 0,
        'authentic_engineering_reports': categories['authentic_input_materialization'] + categories['authentic_viewer_rendering'] + categories['authentic_viewer_transport'],
        'authentic_viewer_transport_reports': categories['authentic_viewer_transport'],
        'paper_source_preparation_reports': categories['paper_source_preparation'],
        'neural_source_preparation_reports': categories['neural_source_preparation'],
        'author_model_inference_probes': categories['author_model_inference_probe'],
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
            'records': records, 'reports': reports, 'counts': result_counts, 'scope': SCOPE}
