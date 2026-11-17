"""Independent full-output closure checks; no labels, fitting or grading."""
import math
import os
import re


def native(c, directory, expected, source, kind, ordinal, read, tick, selection, program, origin, worker_end):
    value = c.parse(c.capture(directory / 'NATIVE.json', 262144, expected, tick, read))
    c.need(value['schema'] == 'neural083-sequential-native-phase-v2' and value['source'] == source and
           value['kind'] == kind and type(value['ordinal']) is int and value['ordinal'] == ordinal and
           value['status'] == 'captured', 'Exact native phase identity')
    for key in ('all_native_resources_closed', 'cli_reaped', 'producer_closed_before_capture'):
        c.need(value[key] is True, 'Complete native lifecycle')
    c.need(value['private_scoring_called'] is False and value['error_type'] is None and
           len(value['closures']) == 3 and all(row['closed'] is True for row in value['closures']) and
           sorted(row['kind'] for row in value['closures']) == ['container', 'container', 'volume'],
           'Every native resource closed')
    prefixes = set()
    roles = set()
    for row in value['closures']:
        match = re.fullmatch(r'neural083-([a-f0-9]{24})-(candidate|holder|volume)', row.get('name', ''))
        c.need(match is not None, 'Exact named native resource')
        prefix, role = match.groups()
        c.need(role not in roles and row['kind'] == ('volume' if role == 'volume' else 'container'),
               'Distinct native resource roles')
        prefixes.add(prefix)
        roles.add(role)
        c.need(row.get('absence_observed') is True and row.get('creation_outcome_unknown') is False and
               row.get('removed') is True and row.get('closed') is True, 'Known creation, actual removal and observed absence')
    c.need(len(prefixes) == 1 and roles == {'candidate', 'holder', 'volume'}, 'One complete owned resource family')
    c.validate_natural_exit(value['natural_exit'])
    c.validate_cli_commands(value['command_metadata'], 715840000 if kind == 'fit' else 400000)
    c.need(value['image'] == selection['image'] and type(value['producer_memory_bytes']) is int and
           value['producer_memory_bytes'] == selection['memory_bytes'] and
           type(value['producer_seconds']) in (int, float) and
           value['producer_seconds'] == selection[kind + '_seconds'] and value['program'] == program,
           'Exact selected producer/image/program and resource receipt')
    for key in ('phase_started_monotonic', 'phase_deadline', 'worker_deadline'):
        c.need(type(value[key]) in (int, float) and math.isfinite(value[key]), 'Finite original phase clock')
    c.need(origin <= value['phase_started_monotonic'] < value['phase_deadline'] <= value['worker_deadline'] == worker_end,
           'Original worker deadline bounds phase')
    return value


def admit(c, contracts, expected_reference, root, terminal, source, selection, deadline, read):
    tick = lambda: c.before(deadline)
    def get(path, expected=None, cap=2000000):
        return c.parse(c.capture(path, cap, expected, tick, read))
    c.need(type(terminal) is dict and terminal.get('schema') == 'neural083_full_worker_v1' and
           terminal.get('status') == 'complete_unqualified' and terminal.get('source') == source and
           type(terminal.get('prediction_values')) is int and terminal['prediction_values'] == 259200,
           'Full both-panel terminal scope')
    c.need(not os.path.lexists(root / 'FAILURE.json') and not os.path.lexists(root / 'current'), 'No failure or live view')
    done = get(root / 'COMPLETE.json', terminal['complete'])
    bundle = get(root / 'submission.json', terminal['submission'])
    c.need(done['schema'] == 'neural083_full_complete_v1' and done['source'] == source and
           done['candidate'] == c.only_pin(selection['program']) and done['canonical'] == c.only_pin(selection['canonical']) and
           done['submission'] == terminal['submission'] and done['reference'] == expected_reference,
           'Same source, inputs, submitted program and independently captured reference')
    for key, number in (('conditions', 2592), ('native_phases', 5184), ('prediction_values', 259200)):
        c.need(type(done[key]) is int and done[key] == number, 'Full condition cardinality')
    c.need(done['all_views_models_retired'] is True, 'All temporary state retired')
    counters = terminal['costs_after_complete']
    c.need(type(counters) is dict and set(counters) == {'read_reservations', 'write_reservations', 'native_phases'} and
           all(type(number) is int and number >= 0 for number in counters.values()) and
           counters['read_reservations'] == done['costs']['read_reservations'] and
           counters['write_reservations'] == done['costs']['write_reservations'] + terminal['complete']['bytes'] and
           counters['native_phases'] == 5184, 'Prepublication counters plus exact COMPLETE debit')
    for key in ('query_truth_opened', 'scoring_performed', 'scientific_qualified', 'runtime_qualified'):
        c.need(done[key] is False, 'Unscored source-only status')
    commitment = get(root / 'COMMITMENT.json')
    origin = commitment['origin']
    worker_end = deadline - selection['limits']['observer_seconds']
    c.need(commitment['schema'] == 'neural083_full_commitment_v1' and commitment['source'] == source and
           commitment['candidate'] == done['candidate'] and commitment['reference'] == done['reference'] and
           commitment['canonical'] == done['canonical'] and
           type(commitment['origin']) in (int, float) and math.isfinite(commitment['origin']) and
           type(commitment['worker_end']) in (int, float) and math.isfinite(commitment['worker_end']) and
           origin + selection['limits']['whole_seconds'] == deadline and commitment['worker_end'] == worker_end and
           commitment['programs_fixed_before_operator_staging'] is True, 'Same original enclosing clock and program commitment')
    canonical = get(selection['canonical']['path'], c.only_pin(selection['canonical']), 4000000)
    panel = contracts.canonical(canonical)
    c.need(get(root / 'PANEL.json') == panel, 'Exact canonical query panel')
    c.need(bundle['schema'] == 'neural083_full_program_submission_v1' and bundle['source'] == source and
           bundle['canonical'] == c.only_pin(selection['canonical']), 'Submission identities')
    rows = bundle['conditions']
    c.need(type(rows) is list and len(rows) == 2592, 'Every condition in both panels')
    cases = {row['case']: row for row in panel['cases']}
    for expected, row in zip(contracts.schedule(panel), rows):
        ordinal = expected['ordinal']
        c.need(row['condition'] == expected and type(row['ordinal']) is int and row['ordinal'] == ordinal,
               'Exact full schedule without duplicate/extra conditions')
        folder = root / 'conditions' / ('condition%04d' % ordinal)
        closed = get(folder / 'CLOSED.json', row['closed'])
        c.need(closed['schema'] == 'neural083_closed_condition_v1' and closed['condition'] == expected and
               closed['all_views_models_and_native_resources_closed'] is True, 'Source-bound complete condition')
        program = done['candidate'] if expected['panel'] == 'candidate' else done['reference']
        c.need(closed['program'] == program, 'Independent selected program identity')
        c.need(not os.path.lexists(folder / 'model.bin') and not os.path.lexists(folder / 'fit' / 'model.bin'),
               'No accumulated condition models')
        seal = get(folder / 'MODEL_SEAL.json', closed['seal'])
        train = get(folder / 'TRAIN_RETIRED.json', closed['train_retired'])
        query = get(folder / 'QUERY_RETIRED.json', closed['query_retired'])
        model = get(folder / 'MODEL_RETIRED.json', closed['model_retired'])
        metadata = get(folder / 'QUERY_METADATA.json', closed['query_metadata'])
        c.need(seal['condition'] == expected and seal['program'] == program and seal['model'] == closed['model'] and
               seal['native'] == closed['fit_native'] and seal['fit_closed'] is True and seal['query_exposed'] is False,
               'Closed fitting sealed before query visibility')
        c.need(train['condition'] == expected and train['model_seal'] == closed['seal'] and
               train['absent'] is True and train['parent_fsynced'] is True and train['query_exposed'] is False and
               set(train['training']) == {'training.npy', 'case.json'}, 'Complete training retirement')
        c.need(query['condition'] == expected and query['metadata'] == closed['query_metadata'] and
               query['native'] == closed['infer_native'] and query['absent'] is True and
               query['parent_fsynced'] is True and set(query['query']) == {'query.npy', 'case.json'}, 'Complete query retirement')
        c.need(model['condition'] == expected and model['model'] == closed['model'] and model['model_seal'] == closed['seal'] and
               model['absent'] is True and model['parent_fsynced'] is True, 'Same model retired')
        c.need(metadata['generation'] == panel['generation'] and metadata['case'] == expected['case'] and
               metadata['setting'] == expected['setting'] and metadata['arm'] == expected['arm'] and
               metadata['query'] == cases[expected['case']]['query'] and metadata['model'] == closed['model'] and
               metadata['fitted_program'] == program, 'Exact original query order, model and condition')
        c.need(query['query']['case.json'] == closed['query_metadata'] and
               query['query']['query.npy'] == metadata['query_pin'], 'Retired query pin joins')
        fit = native(c, folder / 'fit', closed['fit_native'], source, 'fit', ordinal, read, tick, selection, program, origin, worker_end)
        inferred = native(c, folder / 'infer', closed['infer_native'], source, 'infer', ordinal, read, tick, selection, program, origin, worker_end)
        c.need(fit['output'] == closed['model'] and inferred['output'] == closed['output'], 'Captured model/output identity')
        prediction = get(folder / 'infer' / 'predictions.json', closed['output'], 100000)
        contracts.prediction(prediction, metadata)
    c.need(set(path.name for path in (root / 'conditions').iterdir()) ==
           {'condition%04d' % number for number in range(2592)}, 'Exact condition directories')
    handoff = get(root / 'GRADE_HANDOFF.json', done['grade_handoff'])
    c.need(handoff['target_access_authorized'] is False and handoff['independent_external_closure_required'] is True and
           handoff['complete_panels_required'] == 2 and handoff['conditions_per_panel'] == 1296,
           'Separate future protected grading')
    c.need(c.inventory(root, selection['limits']['retained'], 500000)[2] <= selection['limits']['retained'] - 16384,
           'All retained outputs plus independent closure slot')
    tick()
    return terminal['submission'], terminal['complete']
