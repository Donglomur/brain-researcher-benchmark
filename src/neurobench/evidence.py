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
PUBLIC_REPORTS = (PILOT, HISTORY, DIRECT, VIEWER)
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
    records, reports = {}, []
    for relative, project in ((PILOT, pilot_records), (HISTORY, historical_records),
                              (DIRECT, engineering_records), (VIEWER, lambda doc, source: engineering_records(doc, source, True))):
        try:
            captured = read(root, relative)
            if captured is None:
                continue
            doc, source = captured
            projected = project(doc, source)
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
        'authentic_engineering_reports': categories['authentic_input_materialization'] + categories['authentic_viewer_rendering'],
        'historical_profiles': categories['historical_paper_calibration'] + categories['historical_programme_control'],
        'historical_programme_controls': sum(len(row.get('controls', [])) for items in records.values() for row in items),
        'engineering_reports_with_generated_controls': sum('software_controls' in row for items in records.values() for row in items),
    }
    return {'schema_version': 1, 'kind': 'public_recorded_evidence_summary',
            'records': records, 'reports': reports, 'counts': result_counts, 'scope': SCOPE}
