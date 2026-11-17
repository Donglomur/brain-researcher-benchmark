"""Protected full-study admission and target-last decimal metrics.

No provider/candidate/runtime controller receives this module or a target callback.
This module's actual scoring is unexecuted during source construction.
"""
from decimal import Decimal, localcontext
from pathlib import Path
import unicodedata

from core import capture, descriptor, encoded, finite, need, parse, pin
from packet import body_pin, prediction, context
from schedule import full, MODES, REPLICATES, ARMS, FAMILIES
import reference_engine


class AdmissionCapture:
    """Per-grade protected-root exclusion, applied before every admission read.

    Canonicalization is lexical only: no target stat, resolution or body access.
    Core capture independently rejects symlink parents and multi-link files.
    Case-folding/NFC deliberately overexclude equivalent spellings on Mac filesystems.
    """
    def __init__(self, target_path):
        target = self.canonical(target_path)
        self.protected_root = target[:-1]
        need(self.protected_root, 'explicit protected target parent')

    @staticmethod
    def canonical(path):
        need(isinstance(path, (str, Path)), 'ordinary admission path')
        value = Path(path)
        need(value.is_absolute() and not str(path).startswith('//')
             and str(path) == str(value) and '..' not in value.parts and '\x00' not in str(value),
             'canonical absolute admission path; no double-leading or redundant separators/traversal')
        return tuple(unicodedata.normalize('NFC', part).casefold() for part in value.absolute().parts)

    def read(self, path, expected, cap, budget, **kwargs):
        parts = self.canonical(path)
        need(parts[:len(self.protected_root)] != self.protected_root,
             'protected private root is excluded before admission capture')
        return capture(path, expected, cap, budget, **kwargs)


def same_pin(left, right, reason):
    need(descriptor(left) == descriptor(right), reason)


def request_lineage(request, native, session, role, kind, source_pins, reference):
    """Join the captured request body to this exact native role/source/clock."""
    expected = {'schema', 'kind', 'role', 'environment', 'files', 'unit_count', 'clock'}
    if reference:
        expected |= {'task_id', 'session_ordinal', 'session_id', 'unit_axis_sha256', 'engine_source', 'limits'}
    else:
        expected |= {'source', 'recipe', 'seed', 'output_caps', 'input_cap', 'model_cap'}
    if kind == 'infer':
        expected.add('model')
    need(type(request) is dict and set(request) == expected
         and request['schema'] == ('neural060-reference-request-v1' if reference else 'neural060_worker_request_v1')
         and request['kind'] == kind and request['role'] == role, 'exact captured phase request schema')
    environment = request['environment']
    need(type(environment) is dict and set(environment) == {'python', 'numpy', 'scikit_learn', 'h5py'}
         and all(type(v) is str and v for v in environment.values()), 'explicit request numerical environment')
    clock = request['clock']
    need(type(clock) is dict and set(clock) == {'original_origin', 'phase_deadline', 'local_duration_cap'},
         'exact inherited request clock')
    origin, cutoff = finite(clock['original_origin']), finite(clock['phase_deadline'])
    need(origin == finite(native['original_origin']) and cutoff == finite(native['requested_cutoff'])
         and 0 < finite(clock['local_duration_cap']) <= cutoff-origin,
         'request retains exact original native origin/cutoff; local clock is supplementary')
    if reference:
        need(request['task_id'] == 'NEURAL-060' and request['session_id'] == session['session_id']
             and type(request['session_ordinal']) is int and request['session_ordinal'] == session['ordinal']
             and request['unit_axis_sha256'] == (session['unit_axis_sha256'] if role == 'joint' else None),
             'exact reference task/session/native unit-axis request')
        same_pin(request['engine_source'], mounted(native, '/trusted/reference_engine.py')['pin'],
                 'reference request names its actual engine mount')
        same_pin(request['engine_source'], source_pins['references/engine.py'], 'independently frozen reference engine')
    else:
        same_pin(request['source'], mounted(native, '/trusted/method.py')['pin'], 'candidate request names actual method mount')
        need(type(request['seed']) is int and 0 <= request['seed'] < 2**32, 'ordinary frozen numerical seed')
    if kind == 'infer':
        same_pin(request['model'], mounted(native, '/model/model.pkl')['pin'], 'inference request names actual readonly model mount')


def fit_lineage(fit, fitted_request, request, source_pins, *, reference=False, authored=None):
    """Model/selection pins must originate in actual closed-fit artifacts."""
    native = fit['native']
    same_pin(fit['pin'], native['artifacts']['model.pkl'], 'sealed model is actual closed-fit model artifact')
    same_pin(fit['request'], mounted(native, '/input/REQUEST.json')['pin'], 'fit request is actual captured fit REQUEST mount')
    same_pin(request['model'], fit['pin'], 'replay request reuses exact original fitted model')
    need(encoded(request['environment']) == encoded(fitted_request['environment']), 'fit/inference numerical environment unchanged')
    if reference:
        same_pin(fit['selection'], native['artifacts']['SELECTION.json'], 'reference selection is actual closed-fit artifact')
        same_pin(fitted_request['engine_source'], source_pins['references/engine.py'], 'fit request uses independently frozen reference source')
        same_pin(request['engine_source'], fitted_request['engine_source'], 'reference fit/inference engine source unchanged')
        need(request['session_id'] == fitted_request['session_id']
             and type(request['session_ordinal']) is int and request['session_ordinal'] == fitted_request['session_ordinal']
             and request['role'] == fitted_request['role']
             and type(request['unit_count']) is int and request['unit_count'] == fitted_request['unit_count']
             and request['unit_axis_sha256'] == fitted_request['unit_axis_sha256'],
             'reference original fit/replay session and all-unit identity unchanged')
    else:
        need(type(authored) is dict, 'independent authored source required')
        same_pin(mounted(native, '/trusted/method.py')['pin'], authored['source'], 'fit executed actual independently authored method')
        same_pin(fit['source'], authored['source'], 'sealed model source equals authored source')
        same_pin(fitted_request['source'], authored['source'], 'fitter request/source join')
        need(encoded(fitted_request['recipe']) == encoded(authored['recipe'])
             and encoded(request['recipe']) == encoded(fitted_request['recipe'])
             and type(fit['seed']) is int and fitted_request['seed'] == fit['seed'] == request['seed'],
             'fit and replay retain exact typed recipe/RNG policy')


def reference_selection_lineage(selected, fit, fitted_request, session, role):
    need(type(selected) is dict and set(selected) == {'schema', 'request', 'engine_source', 'model', 'environment', 'selection'}
         and selected['schema'] == 'neural060-reference-selection-file-v1', 'exact captured reference selection envelope')
    same_pin(selected['model'], fit['native']['artifacts']['model.pkl'], 'selection names actual original fitted model artifact')
    same_pin(selected['request'], mounted(fit['native'], '/input/REQUEST.json')['pin'], 'selection names actual original fit request mount')
    same_pin(selected['engine_source'], fitted_request['engine_source'], 'selection names original fitter engine source')
    need(encoded(selected['environment']) == encoded(fitted_request['environment']), 'selection retains original fitter environment')
    report = selected['selection']
    need(report['schema'] == reference_engine.SCHEMA+'/selection'
         and report['design_sha256'] == reference_engine.DESIGN_SHA256
         and report['role'] == role and report['session_id'] == session['session_id']
         and type(report['session_ordinal']) is int and report['session_ordinal'] == session['ordinal']
         and type(report['unit_count']) is int and report['unit_count'] == (session['unit_count'] if role == 'joint' else 0)
         and type(report['train_cases']) is int and report['train_cases'] == len(session['splits']['train']['case_ids'])
         and type(report['validation_cases']) is int and report['validation_cases'] == len(session['splits']['val']['case_ids']),
         'reference selection preserves exact original session/all-unit/full fitting support')


def native_closed(value, phase_id, origin, deadline):
    need(type(value) is dict and value.get('schema') == 'neural060_native_v1'
         and value.get('phase') == phase_id and value.get('closed_and_removed') is True
         and type(value.get('exit_code')) is int and value['exit_code'] == 0,
         'actual successful owned native closure')
    need(finite(value['original_origin']) == finite(origin) and origin <= finite(value['natural_end'])
         < finite(value['cutoff']) <= finite(value['requested_cutoff']) <= finite(deadline),
         'original native clock and effective/requested cutoff algebra')
    need(type(value['cpu_nanoseconds']) is int and value['cpu_nanoseconds'] > 0
         and type(value['peak_memory_bytes']) is int and value['peak_memory_bytes'] > 0,
         'measured native CPU/peak memory, not unknown or bool')
    plan = value['cpu_reservation']
    need(type(plan) is dict and set(plan) == {'cpu_period_us', 'cpu_quota_us', 'cpu_reserved_nanoseconds',
         'cpu_limit_nanoseconds', 'execution_cutoff', 'cleanup_seconds', 'quota_burst_allowance_nanoseconds'},
         'exact prospective aggregate CPU reservation')
    for key in ('cpu_period_us', 'cpu_quota_us', 'cpu_reserved_nanoseconds', 'cpu_limit_nanoseconds', 'cleanup_seconds',
                'quota_burst_allowance_nanoseconds'):
        need(type(plan[key]) is int and plan[key] > 0, 'ordinary positive CPU reservation field:' + key)
    need(plan['cpu_period_us'] == 100000 and plan['quota_burst_allowance_nanoseconds'] == 200000000
         and finite(plan['execution_cutoff']) == finite(value['cutoff'])
         and value['cpu_nanoseconds'] <= plan['cpu_reserved_nanoseconds'] <= plan['cpu_limit_nanoseconds'],
         'measured CPU is bounded by original effective execution plan')
    watchdog = value['watchdog']
    need(type(watchdog) is dict and watchdog.get('timer_or_failure_stop_triggered') is False
         and watchdog.get('watchdog_joined') is True and watchdog.get('events') == []
         and type(watchdog.get('stop')) is dict and watchdog['stop'].get('attempted') is False
         and watchdog['stop'].get('cancelled_after_natural_retirement') is True,
         'independent watchdog joined after natural retirement without triggered stop')
    ledger = watchdog['ledger']
    need(type(ledger) is dict and finite(ledger['origin']) == finite(origin)
         and finite(ledger['deadline']) == finite(value['cutoff']) + plan['cleanup_seconds']
         and finite(ledger['observed']) >= finite(value['natural_end'])
         and ledger.get('logical_reservations_not_measured_physical_usage') is True,
         'watchdog retains original origin and selected effective cleanup envelope')
    if ledger['observed'] >= ledger['deadline']:
        need(ledger.get('passive_closeout_snapshot_may_be_after_deadline') is True,
             'late watchdog observation is explicitly passive closeout, not extra action time')
    for direction in ('read', 'write'):
        reserved = value['cleanup_reserved_' + direction + '_bytes']
        observed = ledger[direction + '_reserved_bytes']
        need(type(reserved) is int and reserved >= 0 and type(observed) is int and 0 <= observed <= reserved,
             'watchdog logical usage remains inside pre-reserved cleanup allowance')
    descriptor(value['config']); descriptor(value['stats'])
    need(type(value['source_inputs']) is list and value['source_inputs'], 'native input custody records')
    need(type(value['container']) is str and len(value['container']) == 64, 'owned native container identity')
    return value


def mounted(native, target):
    rows = [r for r in native['source_inputs'] if r['target'] == target]
    need(len(rows) == 1, 'one exact readonly native mount:' + target)
    descriptor(rows[0]['pin'])
    return rows[0]


def full_rows(rows, ids):
    need(type(rows) is list and len(rows) == len(ids), 'complete reference query support')
    result = {}
    for row in rows:
        need(type(row) is dict and set(row) == {'case_id', 'prediction'} and row['case_id'] in ids
             and row['case_id'] not in result, 'known unique reference output case')
        need(type(row['prediction']) is list and len(row['prediction']) == 50, 'full50 reference output')
        result[row['case_id']] = [finite(x) for x in row['prediction']]
    need(set(result) == set(ids), 'full reference case join')
    return result


def _load(path, expected, cap, budget, guard):
    need(isinstance(guard, AdmissionCapture), 'explicit protected-root admission context')
    raw, _ = guard.read(path, expected, cap, budget, readonly=True)
    return parse(raw)


def admit_view(native, session, role, kind, shifted, source_pins, limits, budget, guard, reference=False):
    request_row = mounted(native, '/input/REQUEST.json')
    request = _load(request_row['source'], request_row['pin'], limits['request_bytes'], budget, guard)
    need(request['kind'] == kind and request['role'] == role, 'fixed phase and information role')
    need(type(request['unit_count']) is int and request['unit_count'] == (session['unit_count'] if role == 'joint' else 0),
         'complete all-unit or nuisance-only view')
    splits = ('train', 'val') if kind == 'fit' else ('test',)
    expected_files = {s+'/context.json' for s in splits} | ({s+'/neural.h5' for s in splits} if role == 'joint' else set())
    need(set(request['files']) == expected_files, 'no test in fit/no training labels in replay')
    allowed_targets = {'/input/REQUEST.json'} | {'/input/'+x for x in expected_files}
    if reference:
        allowed_targets |= {'/trusted/reference_worker.py', '/trusted/reference_engine.py'}
        need(mounted(native, '/trusted/reference_worker.py')['pin'] == source_pins['references/worker.py']
             and mounted(native, '/trusted/reference_engine.py')['pin'] == source_pins['references/engine.py'],
             'exact independently frozen reference source')
    else:
        allowed_targets |= {'/trusted/worker.py', '/trusted/method.py'}
        need(mounted(native, '/trusted/worker.py')['pin'] == source_pins['worker.py'], 'exact candidate worker source')
    if kind == 'infer':
        allowed_targets.add('/model/model.pkl')
    need(len(native['source_inputs']) == len(allowed_targets)
         and {x['target'] for x in native['source_inputs']} == allowed_targets,
         'no hidden native input/other arm/reference/target mount')
    request_lineage(request, native, session, role, kind, source_pins, reference)
    for split in splits:
        row = session['splits'][split]
        actual = mounted(native, '/input/'+split+'/context.json')
        need(actual['pin'] == request['files'][split+'/context.json'], 'context request/mount join')
        if role == 'joint':
            need(actual['pin'] == body_pin(row['context']), 'unchanged original joint context')
        else:
            value = _load(actual['source'], actual['pin'], limits['context_bytes'], budget, guard)
            context(value, session, split, nuisance=True)
        if role == 'joint':
            key = 'neural_shift10' if shifted else 'neural'
            actual = mounted(native, '/input/'+split+'/neural.h5')
            need(actual['pin'] == body_pin(row[key]) == request['files'][split+'/neural.h5'],
                 'exact original fit or test-only shifted neural stream')
    return request


def admit(producer, outer, projection, runtime_pin, source_pins, limits, budget, guard):
    """All candidate/reference values and lineage admitted before any gold access."""
    need(isinstance(guard, AdmissionCapture), 'protected-root admission context required')
    schedule, schedule_pin = full(projection['sessions'])
    need(producer.get('schema') == 'neural060_producer_complete_v1'
         and producer.get('task_id') == 'NEURAL-060' and producer.get('runtime_source') == runtime_pin
         and producer.get('schedule') == schedule_pin and producer.get('private_targets_opened') is False,
         'exact full selected producer source/schedule')
    need(outer.get('schema') == 'neural060_outer_observation_v1' and outer.get('runtime_source') == runtime_pin
         and outer.get('study_id') == producer['study_id'] and outer.get('natural_exit') is True
         and type(outer.get('exit_code')) is int and outer['exit_code'] == 0
         and outer.get('timer_fired') is False and outer.get('owned_containers_after') == []
         and outer.get('study_admitted') is True and 'failure' in outer and outer['failure'] is None
         and type(outer.get('event_closure')) is dict and outer['event_closure'].get('all_required_phases_closed') is True,
         'independent actual natural worker and all-native closure')
    origin, deadline = producer['original_origin'], producer['original_deadline']
    need(outer['original_origin'] == origin and outer['original_deadline'] == deadline
         and origin <= outer['worker_start'] <= outer['worker_end'] < deadline,
         'independent original enclosing clock')
    need(type(producer['candidate_fit_count']) is int and producer['candidate_fit_count'] == 348
         and type(producer['reference_fit_process_count']) is int and producer['reference_fit_process_count'] == 58
         and type(producer['reference_constituent_fits']) is int and producer['reference_constituent_fits'] == 928
         and type(producer['reference_family_inferences']) is int and producer['reference_family_inferences'] == 261,
         'full fit/inference workload counts')
    authors = producer['authors']; expected_episodes = [list(e) for e in schedule['author_episodes']]
    need(type(authors) is list and [x['episode'] for x in authors] == expected_episodes, 'all180 ordered author episodes')
    author_by_episode = {}
    for row in authors:
        record = row['record']; final = record['final']
        need(record['episode'] == row['episode'] and record.get('completed') is True
             and record.get('source_sealed') is True and record.get('independent_method_reviewed') is True
             and origin <= record['observed_start'] <= record['observed_end'] < record['cutoff'] <= deadline,
             'source authoring/sealing/method-admission clock')
        for key in ('source', 'recipe_pin', 'claim_pin', 'method_admission'):
            descriptor(final[key])
        guard.read(final['path'], final['source'], 131072, budget, retain=False, readonly=True)
        need(pin(encoded(final['recipe'])) == final['recipe_pin'] and pin(encoded(final['claim'])) == final['claim_pin'],
             'sealed recipe and pre-outcome claim')
        author_by_episode[tuple(row['episode'])] = record
    fixed_end = max(x['record']['observed_end'] for x in authors if x['episode'][0] == 'frozen_program')
    adaptive_start = min(x['record']['observed_start'] for x in authors if x['episode'][0] != 'frozen_program')
    need(fixed_end <= adaptive_start, 'all global fixed sources precede any adaptive query investigation')
    sessions = {row['session_id']: row for row in projection['sessions']}
    candidates = {}; references = {}; selected_families = {}; native_ids = set(); fit_ids = {}; fit_requests = {}
    expected = [p for p in schedule['candidate_phases'] if p['kind'] == 'infer']
    rows = producer['candidate_outputs']
    need(type(rows) is list and len(rows) == len(expected) == 522, 'all522 candidate per-session outputs')
    for row, phase in zip(rows, expected):
        need(row['phase'] == phase, 'exact ordered candidate schedule, no substitutions')
        current = sessions[phase['session_id']]
        episode = (phase['mode'], phase['replicate'], phase['role'],
                   'global' if phase['mode'] == 'frozen_program' else current['ordinal'])
        authored = author_by_episode[episode]['final']
        need(row['episode'] == list(episode) and row['source'] == authored['source']
             and row['method_admission'] == authored['method_admission'], 'independent source/method lineage')
        phase_index = schedule['candidate_phases'].index(phase)+1
        native = native_closed(row['native'], 'candidate-'+str(phase_index), origin, deadline)
        request = admit_view(native, current, phase['role'], 'infer', phase['arm'] == 'joint_test_shift10',
                             source_pins, limits, budget, guard)
        need(native['container'] not in native_ids, 'distinct fresh replay producer'); native_ids.add(native['container'])
        need(mounted(native, '/input/REQUEST.json')['pin'] == row['request']
             and mounted(native, '/trusted/method.py')['pin'] == row['source']
             and mounted(native, '/model/model.pkl')['pin'] == row['model'], 'source/request/model readonly mount join')
        fit = row['fit']; need(fit['pin'] == row['model'] and fit['source'] == row['source'], 'sealed fitted-state lineage')
        fit_key = (phase['mode'], phase['replicate'], current['ordinal'], phase['role'])
        if fit_key in fit_ids:
            need(encoded(fit_ids[fit_key]) == encoded(fit), 'joint original/shift uses identical fit/model/RNG')
        else:
            expected_fit = dict(phase, kind='fit', arm=None)
            fit_index = schedule['candidate_phases'].index(expected_fit)+1
            fit_native = native_closed(fit['native'], 'candidate-'+str(fit_index), origin, deadline)
            fitted_request = admit_view(fit_native, current, phase['role'], 'fit', False, source_pins, limits, budget, guard)
            need(fitted_request['source'] == authored['source'] and fitted_request['recipe'] == authored['recipe']
                 and fitted_request['seed'] == fit['seed'], 'original supervised fitter source/recipe/RNG')
            need(fit_native['container'] not in native_ids, 'distinct original fit producer')
            native_ids.add(fit_native['container']); fit_ids[fit_key] = fit; fit_requests[fit_key] = fitted_request
        fit_lineage(fit, fit_requests[fit_key], request, source_pins, authored=authored)
        need(fit['native']['natural_end'] <= native['natural_end'], 'fitted-state seal precedes replay')
        need(request['source'] == authored['source'] and request['recipe'] == authored['recipe']
             and request['seed'] == fit['seed'], 'same original/shifted method recipe and RNG')
        guard.read(fit['path'], fit['pin'], limits['model_bytes'], budget, retain=False, readonly=True)
        need(native['artifacts']['PREDICTIONS.json'] == row['prediction'], 'closed output captured identity')
        value = _load(row['path'], row['prediction'], limits['prediction_bytes'], budget, guard)
        values = prediction(value, current['splits']['test']['case_ids'], row['source'], row['model'])
        need(value['request'] == row['request'], 'exact candidate request body')
        panel = (phase['mode'], phase['replicate'], phase['arm'])
        candidates.setdefault(panel, {}).update(values)
    need(len(fit_ids) == 348, 'all original candidate fits independently joined')
    expected = [p for p in schedule['reference_phases'] if p['kind'] == 'reference_infer']
    rows = producer['reference_outputs']; ref_fits = {}; ref_fit_requests = {}
    need(type(rows) is list and len(rows) == len(expected) == 87, 'all87 three-family reference outputs')
    for row, phase in zip(rows, expected):
        need(row['phase'] == phase, 'exact independent reference schedule')
        current = sessions[phase['session_id']]
        phase_index = schedule['reference_phases'].index(phase)+1
        native = native_closed(row['native'], 'reference-'+str(phase_index), origin, deadline)
        request = admit_view(native, current, phase['role'], 'infer', phase['arm'] == 'joint_test_shift10',
                            source_pins, limits, budget, guard, reference=True)
        need(native['container'] not in native_ids, 'independent reference producer identity'); native_ids.add(native['container'])
        fit = row['fit']; key = (current['ordinal'], phase['role'])
        need(fit['pin'] == row['model'] and fit['selection'] == row['selection'], 'separate reference model/selection lineage')
        if key in ref_fits:
            need(encoded(ref_fits[key]) == encoded(fit), 'same joint reference state across original/shift')
        else:
            expected_fit = dict(phase, kind='reference_fit', arm=None)
            fit_index = schedule['reference_phases'].index(expected_fit)+1
            fit_native = native_closed(fit['native'], 'reference-'+str(fit_index), origin, deadline)
            fitted_request = admit_view(fit_native, current, phase['role'], 'fit', False, source_pins, limits, budget, guard, reference=True)
            need(fit_native['container'] not in native_ids, 'independent original reference fit')
            native_ids.add(fit_native['container']); ref_fits[key] = fit; ref_fit_requests[key] = fitted_request
        fit_lineage(fit, ref_fit_requests[key], request, source_pins, reference=True)
        need(fit['native']['natural_end'] <= native['natural_end'], 'original reference fit closure precedes replay completion')
        guard.read(fit['path'], fit['pin'], limits['reference_model_bytes'], budget, retain=False, readonly=True)
        need(mounted(native, '/model/model.pkl')['pin'] == row['model']
             and mounted(native, '/input/REQUEST.json')['pin'] == row['request']
             and native['artifacts']['PREDICTIONS.json'] == row['prediction'], 'reference readonly mounts/output')
        selected = _load(row['selection_path'], row['selection'], limits['selection_bytes'], budget, guard)
        reference_selection_lineage(selected, fit, ref_fit_requests[key], current, phase['role'])
        report = selected['selection']
        winners, strongest = reference_engine.select(report['validation'])
        need(report['selected'] == winners and report['strongest_family'] == strongest
             and report['training_shift'] == 0 and report['test_exposed'] is False
             and report['role'] == phase['role'] and report['session_id'] == current['session_id'],
             'train-validation-only full13 grid and selected family')
        work = report['work']
        work_expected = {'expected': 16, 'entered': 16, 'completed': 16, 'entered_failed': 0,
                         'entered_incomplete': 0, 'unentered': 0}
        need(all(type(work[k]) is int and work[k] == v for k, v in work_expected.items()),
             'all16 reference constituent fits')
        value = _load(row['path'], row['prediction'], limits['prediction_bytes'], budget, guard)
        need(type(value) is dict and set(value) == {'schema', 'request', 'engine_source', 'model', 'environment', 'inference', 'families'}
             and value['schema'] == 'neural060-reference-predictions-file-v1' and value['request'] == row['request']
             and value['model'] == row['model'] and value['engine_source'] == selected['engine_source']
             and value['engine_source'] == mounted(native, '/trusted/reference_engine.py')['pin']
             and value['engine_source'] == request['engine_source']
             and encoded(value['environment']) == encoded(selected['environment']) == encoded(request['environment']),
             'independent reference source/environment lineage')
        info = value['inference']
        need(info['schema'] == reference_engine.SCHEMA+'/inference' and info['design_sha256'] == reference_engine.DESIGN_SHA256
             and info['role'] == phase['role'] and info['session_id'] == current['session_id']
             and type(info['session_ordinal']) is int and info['session_ordinal'] == current['ordinal']
             and type(info['fits_during_inference']) is int and info['fits_during_inference'] == 0 and info['strongest_family'] == strongest
             and info['selected'] == winners and info['case_ids'] == current['splits']['test']['case_ids'],
             'fixed reference prediction-only complete test support')
        need(all(type(info['work'][k]) is int and info['work'][k] == v for k, v in
                 {'expected': 3, 'entered': 3, 'completed': 3, 'entered_failed': 0, 'entered_incomplete': 0, 'unentered': 0}.items()),
             'all three actual reference family inferences complete')
        need(type(value['families']) is dict and set(value['families']) == set(FAMILIES), 'every reference family')
        for family in FAMILIES:
            references.setdefault((family, phase['arm']), {}).update(full_rows(value['families'][family], current['splits']['test']['case_ids']))
        selected_families[(current['session_id'], phase['arm'])] = strongest
    need(len(ref_fits) == 58 and len(native_ids) == 1015, 'all870 candidate and145 reference process closures')
    index = {case: row['session_id'] for row in projection['sessions'] for case in row['splits']['test']['case_ids']}
    need(len(candidates) == 18 and len(references) == 9
         and all(set(v) == set(index) for v in [*candidates.values(), *references.values()]), 'all complete panels before gold')
    return candidates, references, selected_families, index


def mean(values):
    return sum(values, Decimal(0))/len(values)


def evaluate(candidates, references, strongest, index, gold):
    need(type(gold) is dict and set(gold) == {'schema', 'cases', 'hierarchy'}
         and gold['schema'] == 'neural060_gold_v1', 'original protected target schema')
    hierarchy = gold['hierarchy']
    need(type(hierarchy) is dict and set(hierarchy) == set(index.values()) and len(hierarchy) == 29,
         'all29 protected session identities')
    for row in hierarchy.values():
        need(type(row) is dict and set(row) == {'animal_id', 'lab_id'}
             and all(type(x) is str and x for x in row.values()), 'protected biological hierarchy')
    animals = sorted({row['animal_id'] for row in hierarchy.values()})
    labs = sorted({row['lab_id'] for row in hierarchy.values()})
    need(len(animals) == 13 and len(labs) == 7 and all(len({h['lab_id'] for h in hierarchy.values()
         if h['animal_id'] == a}) == 1 for a in animals), 'exact13 animals/7 labs')
    need(type(gold['cases']) is list and len(gold['cases']) == len(index), 'complete target support')
    targets = {}
    for row in gold['cases']:
        need(type(row) is dict and set(row) == {'case_id', 'session_id', 'wheel_speed'} and row['case_id'] in index
             and row['case_id'] not in targets and row['session_id'] == index[row['case_id']], 'exact target join')
        values = row['wheel_speed']
        need(type(values) is list and len(values) == 50 and all(finite(x) >= 0 for x in values), 'original50 absolute targets')
        targets[row['case_id']] = [finite(x) for x in values]
    panels = {('candidate',)+k: v for k, v in candidates.items()}
    panels.update({('reference',)+k: v for k, v in references.items()})
    for arm in ARMS:
        panels[('reference_selected', arm)] = {case: references[(strongest[(session, arm)], arm)][case]
                                              for case, session in index.items()}
    metrics = {}
    with localcontext() as ctx:
        ctx.prec = 80
        for key, panel in panels.items():
            losses = {session: [] for session in hierarchy}
            for case, values in panel.items():
                errors = [Decimal.from_float(v)-Decimal.from_float(y) for v, y in zip(values, targets[case])]
                losses[index[case]].append({'mse': mean([e*e for e in errors]), 'mae': mean([abs(e) for e in errors])})
            session_values = {s: {metric: mean([r[metric] for r in rows]) for metric in ('mse', 'mae')}
                              for s, rows in losses.items()}
            animal_values = {a: {metric: mean([session_values[s][metric] for s, h in hierarchy.items() if h['animal_id'] == a])
                                  for metric in ('mse', 'mae')} for a in animals}
            lab_values = {lab: {metric: mean([animal_values[a][metric] for a in animals if any(
                                 h['animal_id'] == a and h['lab_id'] == lab for h in hierarchy.values())])
                                for metric in ('mse', 'mae')} for lab in labs}
            overall = {metric: mean([row[metric] for row in animal_values.values()]) for metric in ('mse', 'mae')}
            metrics[key] = {'overall': overall, 'sessions': session_values, 'animals': animal_values, 'labs': lab_values}
        contrasts = {}
        for prefix in [('candidate', m, r) for m in MODES for r in REPLICATES] + [('reference', f) for f in FAMILIES] + [('reference_selected',)]:
            nuis, joint, shift = [metrics[prefix+(arm,)] for arm in ARMS]
            contrasts['/'.join(prefix)] = {'nuisance_minus_joint_mse': nuis['overall']['mse']-joint['overall']['mse'],
                'shift_minus_joint_mse': shift['overall']['mse']-joint['overall']['mse'],
                'animal_pairs': {a: {'nuisance_minus_joint_mse': nuis['animals'][a]['mse']-joint['animals'][a]['mse'],
                                    'shift_minus_joint_mse': shift['animals'][a]['mse']-joint['animals'][a]['mse']} for a in animals}}
        def render(value):
            if isinstance(value, Decimal):
                try:
                    number = float(value)
                    import math
                    return number if math.isfinite(number) and (number != 0 or value == 0) else str(value)
                except (OverflowError, ValueError):
                    return str(value)
            if isinstance(value, dict):
                return {('/'.join(k) if isinstance(k, tuple) else k): render(v) for k, v in value.items()}
            return value
        return render({'schema': 'neural060_full_score_v1', 'metrics': metrics, 'descriptive_contrasts': contrasts,
                       'primary': {m+'/'+r: metrics[('candidate', m, r, 'joint')]['overall']['mse'] for m in MODES for r in REPLICATES},
                       'ranking_metric': 'joint_equal_mouse_mse_lower_is_better', 'mice': 13, 'sessions': 29, 'labs': 7,
                       'qualified_neural_contribution': None, 'eligible_for_contribution_ranking': False,
                       'reference_competence_qualified': False, 'causal_or_native_understanding_claim': False,
                       'uncertainty': '13 retained animal-paired values; no training/authoring uncertainty estimate',
                       'selected_reference_interpretation': 'different validation-selected procedures may use different families'})


def execute(*, producer_path, producer_pin, outer_path, outer_pin, projection, projection_pin,
            runtime_pin, source_pins, target_path, target_pin, limits, budget):
    guard = AdmissionCapture(target_path)
    producer = _load(producer_path, producer_pin, limits['producer_bytes'], budget, guard)
    outer = _load(outer_path, outer_pin, limits['outer_bytes'], budget, guard)
    need(outer['producer'] == producer_pin and producer['projection'] == projection_pin,
         'independent outer producer and original input identity')
    need(target_pin == body_pin(projection['protected_gold']), 'original prepared target binding before read')
    admitted = admit(producer, outer, projection, runtime_pin, source_pins, limits, budget, guard)
    # This is the first and only target-body access. No invalid candidate,
    # reference, lineage, original clock or closure may reach it.
    raw, _ = capture(target_path, target_pin, limits['target_bytes'], budget)
    return evaluate(*admitted, parse(raw))
