"""Join every selected fit to independent reference and full private support.

All I/O adapters are operator infrastructure, not candidate callbacks. Candidate
outputs are admitted completely before any reference/query loader is invoked.
Each fit set/control/branch remains an explicit result; no success subset or
cross-representation scalar is manufactured.
"""
from core import HMM, BRANCHES, CONTROLS, ROLES, need, native_jobs, held_jobs, identity
from workflow import group_selection
from score import held, aggregate_folds
from native_compare import compare


def evaluate(execution, admit, query, static, scales, scale_pins, diagnostics):
    """Future authenticated operator dependencies; never supplied by submissions.

    admit(disposition) uses admission.native/held and pinned operator contexts.
    query(branch,fold) and static(branch,fold) read the same frozen preparation;
    diagnostics(admitted_native) retains complete native/corrected-unit outputs.
    Their source/image/pins belong to the policy's reviewed provider closure.
    """
    need(len(execution['phases']) == 6, 'Both phases and three roles')
    phases, dispositions = {}, {}
    for phase in execution['phases']:
        s = phase['selection']
        key = (s['phase'], s['role'])
        need(key not in phases, 'Unique complete phase/role')
        computed = group_selection(phase['dispositions'], *key)
        need(computed == s, 'Recompute source training-only selection from all dispositions')
        phases[key] = phase
        for r in phase['dispositions']:
            need(r['job']['id'] not in dispositions, 'Unique attempt identity')
            dispositions[r['job']['id']] = r
    need(set(phases) == {(p, r) for p in ('native', 'held_hmm') for r in ROLES}, 'All453 and5400 attempt roles')
    admitted, invalid = {}, {}
    # This order is intentional: no private reference arrays are loaded until
    # all completed candidate output artifacts have passed full admission.
    for role in ROLES:
        for phase in ('native', 'held_hmm'):
            for r in phases[(phase, role)]['dispositions']:
                if r['status'] != 'completed':
                    continue
                try:
                    a = admit(r)
                    need(a['job_id'] == r['job']['id'] and a['role'] == role
                         and a['external_closure_pin'] == r['capture_pin'], 'Actual external output binding')
                    admitted[r['job']['id']] = a
                except (ValueError, KeyError, TypeError, OSError) as error:
                    invalid[r['job']['id']] = type(error).__name__
        if role in ('A', 'B') and invalid:
            return {'complete': False, 'reason': 'invalid_candidate_output', 'invalid': invalid,
                    'reference_or_query_loaded': False, 'scientific_qualification': False}
    def selected(phase, role, key, fit_set):
        p = phases[(phase, role)]
        if key == 'ctf_static':
            row = p['selection']['static'][0]
        else:
            s = p['selection']['groups'][key]['sets'][fit_set]
            if s is None:
                return None
            matches = [r for r in p['dispositions'] if r['capture_pin'] == s['capture_pin']]
            need(len(matches) == 1, 'Selected closure resolves exactly one original attempt')
            row = matches[0]
        return admitted.get(row['job']['id'])
    native_reports, held_reports, diagnostic_reports = [], [], []
    for role in ('A', 'B'):
        for branch in BRANCHES:
            for fit_set in ([None] if branch == 'ctf_static' else range(3)):
                c, r = selected('native', role, branch, fit_set), selected('native', 'reference', branch, fit_set)
                entry = {'role': role, 'branch': branch, 'fit_set': fit_set}
                if c is None or r is None:
                    native_reports.append({**entry, 'available': False, 'reason': 'missing_selected_fit'})
                    continue
                try:
                    value = compare(c['assembled'], r['assembled'], c['load'], r['load'],
                                    scales[branch], scale_pins[branch])
                    native_reports.append({**entry, **value})
                except (ValueError, FloatingPointError) as error:
                    native_reports.append({**entry, 'available': False,
                                           'reason': 'undefined_or_unequal_full_native_support', 'detail': str(error)})
    for role in ROLES:
        for branch in BRANCHES:
            for fit_set in ([None] if branch == 'ctf_static' else range(3)):
                a = selected('native', role, branch, fit_set)
                diagnostic_reports.append({'role': role, 'branch': branch, 'fit_set': fit_set,
                    'result': None if a is None else diagnostics(a)})
    for role in ('A', 'B'):
        for branch in HMM:
            for control in CONTROLS:
                for fit_set in range(3):
                    fold_reports, missing = [], []
                    for fold in range(5):
                        key = f'{branch}:{fold}:{control}'
                        c = selected('held_hmm', role, key, fit_set)
                        r = selected('held_hmm', 'reference', key, fit_set)
                        if c is None or r is None:
                            missing.append(fold)
                            continue
                        need(c['representation_id'] == r['representation_id'], 'One same frozen real-training representation')
                        fold_reports.append(held(c['parameters'], r['parameters'], static(branch, fold),
                                                 query(branch, fold), branch, fold))
                    held_reports.append({'role': role, 'branch': branch, 'control': control,
                        'fit_set': fit_set, 'available': not missing, 'missing_folds': missing,
                        'result': None if missing else aggregate_folds(fold_reports, branch)})
    return {'complete': execution['complete'] and not invalid and
            all(r['available'] for r in native_reports + held_reports) and
            all(r['result'] is not None and r['result']['available'] for r in diagnostic_reports),
            'native': native_reports, 'held_person': held_reports,
            'biological_sensitivities': diagnostic_reports, 'invalid_reference_outputs': invalid,
            'all_attempt_dispositions_retained_in_execution': True,
            'scientific_qualification': False, 'whole_paper_reproduced': False,
            'cross_representation_scalar': None, 'historical_seed_parity': False}
