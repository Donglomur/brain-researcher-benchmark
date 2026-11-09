"""Complete module accounting: omissions/failures never improve a mean score."""
from . import catalog, numerics
from .validation import need, exact, digest


def aggregate(plan, assessed, executions, attempts, external_authoring_attempts, *, numerical_bytes=2*1024*1024, aggregate_uncertainty=None, schedule=None):
    from .admission import validate_plan
    validate_plan(plan)
    case_map = {c['id']: c for c in plan['cases']}
    need(len({x['case'] for x in assessed}) == len(assessed), 'assessment case duplicates')
    by_case = {x['case']: x for x in assessed}
    need(set(by_case) <= set(case_map), 'no unplanned cases')
    rows=module_rows(plan,by_case)
    all_costs = attempts + external_authoring_attempts
    missing_cost = [a['id'] for a in all_costs if any(a.get(k) is None for k in
                    ('wall_seconds', 'cpu_seconds', 'gpu_seconds', 'token_count', 'bytes_written', 'peak_rss_bytes'))]
    cost = numerics.evaluate('cost', {'attempts': all_costs}, maximum_bytes=numerical_bytes) if all_costs and not missing_cost else None
    failed = [f for run in executions for f in run['failures']]
    return {'schema': 'motormint_full_report_v1', 'task': 'PAPER-paper-method-011',
            'plan_sha256': digest(plan), 'modules': rows, 'failures': failed,
            'complete_artifact_coverage': all(r['complete_assessment'] for r in rows) and not failed and aggregate_uncertainty is not None and aggregate_uncertainty['complete'],
            'all_attempt_costs': cost, 'unmeasured_attempt_costs': missing_cost,
            'original_attempts': all_costs,'aggregate_uncertainty':aggregate_uncertainty,'selected_and_realized_schedule':schedule, 'gate_status': catalog.gaps(),
            'scientific_qualification': False, 'current_SOTA_claim': False,
            'historical_reproduction_claim': False,
            'claim_policy': 'Independent source/native/input/evaluator and scientific review required; no scalar across incompatible estimands.',
            'uncertainty_policy': 'Only prespecified operator-bound groups; seeds/milliseconds are not independent animals.'}


def render_markdown(report):
    lines = ['# MotorMINT complete-paper assessment', '',
             'This report records execution evidence; it does not confer scientific qualification.', '',
             '| Module | Required | Observed | Complete artifacts |', '|---|---:|---:|---|']
    for row in report['modules']:
        lines.append(f"| {row['module']} | {row['required_outputs']} | {row['observed_outputs']} | {row['complete_artifacts']} |")
    lines += ['', f"Failures: {len(report['failures'])}.",
              f"Original scientific evidence gates retained: {len(report['gate_status']['gaps'])}.",
              'Consult the JSON report for per-output signed/absolute deviations, missing support and complete attempt costs.']
    return '\n'.join(lines) + '\n'


def module_rows(plan,by_case):
    rows = []
    for module in catalog.MODULES:
        cases = [c for c in plan['cases'] if c['module'] == module]
        missing = [c['id'] for c in cases if c['id'] not in by_case]
        outputs = [row for case in cases if case['id'] in by_case for row in by_case[case['id']]['outputs']]
        expected = next(r['required_keys'] for r in plan['module_support'] if r['module'] == module)
        keys = [r['key'] for r in outputs]
        need(len(set(keys)) == len(keys) and set(keys) <= set(expected), 'no duplicate or extraneous scored output')
        missing_keys = sorted(set(expected) - set(keys))
        documentary = [r['key'] for r in outputs if r['status'] == 'requires_independent_scientific_review']
        deviations = [r['absolute_deviation'] for r in outputs if r.get('absolute_deviation') is not None]
        uncertainty=[u for c in cases if c['id'] in by_case for u in by_case[c['id']].get('uncertainty',[])]
        required_uncertainty=[u['id'] for c in cases for u in c['uncertainty_requirements']]
        assessed_uncertainty={u['id']:u for u in uncertainty}
        incomplete_uncertainty=[key for key in required_uncertainty if key not in assessed_uncertainty or assessed_uncertainty[key]['status']!='complete']
        invalid=[r['key'] for r in outputs if r['status']!='numerically_assessed']
        rows.append({'module': module, 'required_outputs': len(expected), 'observed_outputs': len(keys),
                     'missing_cases': missing, 'missing_outputs': missing_keys,
                     'documentary_review_pending': documentary,
                     'complete_artifacts': not missing_keys and not missing,'complete_assessment':not missing_keys and not missing and not invalid and not incomplete_uncertainty,
                     'undefined_invalid_or_review_outputs':invalid,'required_uncertainty':required_uncertainty,'incomplete_uncertainty':incomplete_uncertainty,'uncertainty':uncertainty,
                     'mean_absolute_deviation': None if missing_keys or not deviations else sum(deviations)/len(deviations),
                     'outputs': outputs})
    return rows
