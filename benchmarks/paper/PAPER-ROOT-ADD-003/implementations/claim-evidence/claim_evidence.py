"""Post-O26 claim checking: source-owned outputs, not candidate-supplied results.

No fit, target, scientific library, process, file, or network operation. This is
an additive operator API; it does not modify S8 or grant execution/qualification.
"""
import copy
import math
from scope_contract import HANDLES, SCOPE


class ContractError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise ContractError(code)


def number(value):
    require(type(value) in (int, float) and math.isfinite(value), 'FINITE_NUMBER_REQUIRED')
    return value


def near(a, b):
    # Fixed floating-point consistency tolerance, never a practical-effect margin.
    return math.isclose(number(a), number(b), rel_tol=1e-12, abs_tol=1e-12)


def keys(value, expected, code):
    require(type(value) is dict and set(value) == set(expected), code)


def identical(left, right):
    """Typed metadata identity (Python's True == 1 is not a group match)."""
    if type(left) is not type(right): return False
    if type(left) is dict:
        return set(left) == set(right) and all(identical(left[k],right[k]) for k in left)
    if type(left) is list: return len(left) == len(right) and all(identical(a,b) for a,b in zip(left,right))
    return left == right


def text(value):
    require(type(value) is str and 0 < len(value) <= 4096, 'NONEMPTY_BOUNDED_TEXT')
    return value


def _report(products, report_node):
    record = products[report_node]['all_main_and_SI_obligation_reports']
    require(record['operator'] == 'O26' and record['status'] == 'complete', 'COMPLETE_O26_REQUIRED')
    require(record['cell'] in SCOPE['cells'] and record['profile'] == record['cell'][:-2], 'O26_CELL_PROFILE')
    report = record['data']
    require(report['schema'] == 'language_complete_scientific_report_v2', 'ACTUAL_O26_SCHEMA')
    require(identical(report['scope'],SCOPE) and report['scientific_qualification'] is False, 'FULL_S8_SCOPE')
    rows = report['all_family_handle_statuses']
    require(type(rows) is list and [r['family']+'/'+r['handle'] for r in rows] == list(HANDLES), 'EXACT_ORDERED_184_HANDLES')
    allowed = {'complete','scientific_disagreement','reference_complete','unavailable_dependency','engineering_structure_complete'}
    require(all(r['status'] in allowed for r in rows), 'KNOWN_HANDLE_STATUS')
    return record, report, dict(zip(HANDLES, rows))


def _evidence(products, report_record, row, product_key):
    if row['status'] in ('unavailable_dependency','engineering_structure_complete'):
        return None, 'HANDLE_UNAVAILABLE_OR_ENGINEERING'
    require(type(product_key) is str and '.' in product_key, 'PRODUCT_LOCATOR')
    node, role = product_key.rsplit('.', 1)
    if node not in products or role not in products[node]:
        return None, 'MISSING_COLLECTED_PRODUCT'
    product = products[node][role]
    if product_key not in row.get('source_products', {}) or row['source_products'][product_key] != product.get('pin'):
        return None, 'PRODUCT_NOT_BOUND_BY_THIS_O26_HANDLE'
    require(type(product.get('pin')) is dict and product['pin'], 'NONEMPTY_PRODUCT_PIN')
    if product['status'] != 'complete' or product.get('scientific_execution') is not True or report_record.get('scientific_execution') is not True:
        return None, 'PRODUCT_NOT_SCIENTIFICALLY_EXECUTED'
    require(product['cell'] in SCOPE['cells'] or product['cell'] == 'shared', 'SOURCE_PRODUCT_CELL')
    require(product['profile'] in ('R_historical','I_fixed','I_representation','I_offline_selection','shared'), 'SOURCE_PRODUCT_PROFILE')
    return product, None


def _metric(product, selection):
    require(product['operator'] == 'O14', 'O14_CORRELATION_REQUIRED')
    require(type(selection['group']) is dict, 'EXACT_METRIC_GROUP')
    rows = product['data']
    require(type(rows) is list, 'O14_METRIC_ROWS')
    matches = [r for r in rows if identical(r['group'],selection['group'])]
    require(len(matches) == 1, 'UNIQUE_EXACT_METRIC_GROUP')
    row = matches[0]
    require(type(row['rows']) is int and row['rows'] > 0, 'METRIC_SUPPORT_COUNT')
    return row


def _correlation(metric):
    require(type(metric) is dict and 'status' in metric and 'r' in metric, 'CORRELATION_OUTPUT')
    if metric['status'] == 'undefined_constant':
        require(metric['r'] is None, 'UNDEFINED_IS_NOT_ZERO')
        return None
    require(metric['status'] == 'valid' and -1 <= number(metric['r']) <= 1, 'DEFINED_CORRELATION_OUTPUT')
    return metric['r']


def _point(summary):
    """Check loss/support arithmetic without accessing predictions or targets."""
    points = summary['point']
    require(type(points) is dict and points, 'POINT_METHOD_ROSTER')
    common = None
    for method, result in points.items():
        text(method)
        if result['status'] != 'valid':
            return None, 'POINT_UNAVAILABLE'
        require(result['equal_cohort_weight'] is True, 'EQUAL_COHORT_ESTIMAND')
        require(type(result['original_row_count']) is int and result['original_row_count'] > 0, 'ORIGINAL_ROW_SUPPORT')
        strata = result['strata']; require(type(strata) is list and strata, 'POINT_STRATA')
        ids = [(r['cohort'], r['person'], r['condition']) for r in strata]
        require(len(ids) == len(set(ids)), 'DUPLICATE_PERSON_CONDITION')
        people = {c:sorted({r['person'] for r in strata if r['cohort'] == c}) for c in ('search_event','modify_event')}
        require({c:len(v) for c,v in people.items()} == {'search_event':3,'modify_event':2}, 'FULL_THREE_TWO_BIOLOGICAL_PEOPLE')
        require(not set(people['search_event']) & set(people['modify_event']), 'DISJOINT_COHORT_PEOPLE')
        require(set(ids) == {(c,p,k) for c,ps in people.items() for p in ps for k in ('D','S')}, 'FULL_PERSON_CONDITION_SUPPORT')
        require(all(r['status'] == 'valid' and type(r['P']) is int and r['P'] == 1 and number(r['denominator']) > 0 for r in strata), 'POINT_STRATA_AVAILABLE')
        require(all(number(r['loss']) >= 0 for r in strata), 'NONNEGATIVE_LOSS')
        support = (tuple(ids), tuple(r['denominator'] for r in strata), result['original_row_count'])
        if common is None: common = support
        require(support == common, 'SAME_ALL_METHOD_SUPPORT')
        cohorts = result['cohorts'];require(len(cohorts) == 2 and {r['cohort'] for r in cohorts} == set(people), 'COMPLETE_COHORT_RESULTS')
        for row in cohorts:
            losses = [r['loss'] for r in strata if r['cohort'] == row['cohort']]
            require(row['status'] == 'valid' and near(row['loss'], math.fsum(losses)/len(losses)), 'COHORT_LOSS_CONSISTENCY')
        require(near(result['aggregate'], math.fsum(r['loss'] for r in cohorts)/2), 'AGGREGATE_LOSS_CONSISTENCY')
    require(summary['biological_people'] == {'search_event':3,'modify_event':2}, 'BIOLOGICAL_COUNTS_NOT_ROWS')
    return points, None


def _comparison(product, node, reference_selections):
    require(product['operator'] in ('O27','O28'), 'COMPARISON_PRODUCER')
    summary = product['data']
    scope = node['reference_selection_scope']
    ref = reference_selections[scope]['selection']['reference_id']
    points, unavailable = _point(summary)
    if unavailable: return summary, ref, None, unavailable
    inference = node['config']['inference']
    require(len(inference['method_roster']) == len(set(inference['method_roster'])) and set(points) == set(inference['method_roster']), 'FULL_PLANNED_METHOD_ROSTER')
    require(set(inference['cohort_people']) == {'search_event','modify_event'}, 'FULL_PLANNED_COHORTS')
    for result in points.values():
        require(all({r['person'] for r in result['strata'] if r['cohort'] == c} == set(ids) for c,ids in inference['cohort_people'].items()), 'EXACT_PLANNED_PEOPLE')
    require(ref in points and set(summary['point_gains']) == set(points), 'ACTUAL_SELECTED_REFERENCE_AND_METHODS')
    for method, result in points.items():
        require(near(summary['point_gains'][method]['aggregate'], points[ref]['aggregate'] - result['aggregate']), 'SIGNED_GAIN_CONSISTENCY')
        cohorts = {r['cohort']:r['loss'] for r in result['cohorts']}
        ref_cohorts = {r['cohort']:r['loss'] for r in points[ref]['cohorts']}
        require(set(summary['point_gains'][method]['cohorts']) == set(cohorts), 'GAIN_COHORT_ROSTER')
        require(all(near(summary['point_gains'][method]['cohorts'][c], ref_cohorts[c]-v) for c,v in cohorts.items()), 'COHORT_GAIN_CONSISTENCY')
    return summary, ref, points, None


KNOWN_UPGRADES = {
    'population_generalization':'Current 3/2-person conditional analysis has no independent population replication.',
    'causal_code_benefit':'A descriptive A/B output difference does not establish randomized replicated agent access-treatment causality.',
    'neural_understanding':'Prediction or changed available supervision does not establish use, independence, or neural understanding.',
    'novel_intervention_gain':'Unmeasured generated strings have no empirical neural outcome in this contract.',
    'model_independent_ceiling':'The retained simulation is model-conditional, not an independent universal ceiling.',
    'formal_significance':'The existing comparison p-value remains unqualified until independent calibration.',
    'meaningful_improvement':'A positive point gain alone is not a qualified practical improvement or population result.',
}
EXPERT_CRITERIA = {
    'R_historical':('complete_scope','selection_split','units_aggregation','metric_decomposition','historical_formula','dependence_sensitivity','claim_interpretation'),
    'I_fixed':('complete_scope','prespecified_change','selection_split','fixed_support_comparator','signed_outcome','biological_exposure_limits'),
    'I_representation':('complete_scope','prespecified_change','selection_split','fixed_support_comparator','signed_outcome','biological_exposure_limits'),
    'I_offline_selection':('complete_scope','prespecified_change','selection_split','fixed_support_comparator','signed_outcome','biological_exposure_limits'),
}


def _objective(kind, selection, asserted, product, node, reference_selections, resampling):
    if kind in KNOWN_UPGRADES:
        keys(selection, (), 'NO_CANDIDATE_UPGRADE_OPERANDS')
        require(asserted is True, 'UPGRADE_ASSERTION')
        return 'unsupported', None, KNOWN_UPGRADES[kind]
    if kind in ('correlation','positive_within_condition_correlation'):
        keys(selection, ('group','metric') if kind == 'correlation' else ('group',), 'METRIC_SELECTION_SCHEMA')
        row = _metric(product, selection); metrics = row['metrics']
        if kind == 'correlation':
            metric = selection['metric'];require(metric in ('pooled','condition_centered','B','D','S'), 'KNOWN_CORRELATION_COMPONENT')
            value = _correlation(metrics[metric] if metric in ('pooled','condition_centered') else metrics['by_condition'][metric])
            if value is None:
                return ('supported' if asserted is None else 'unsupported'), None, 'Undefined correlation is retained, not converted to zero.'
            return ('supported' if near(asserted,value) else 'unsupported'), value, 'Descriptive correlation on the exact selected group; no significance or new-person generalization follows.'
        require(asserted is True, 'POSITIVE_WITHIN_ASSERTION')
        values = {c:_correlation(metrics['by_condition'][c]) for c in ('D','S')}
        if any(v is None for v in values.values()):return 'blocked', values, 'Required within-condition correlation is undefined.'
        return ('supported' if all(v > 0 for v in values.values()) else 'unsupported'), values, 'Both D and S are checked separately; pooled correlation cannot substitute. Positivity has no significance/practical-effect implication.'
    require(kind in ('point_gain','biological_participant_counts','conditional_interval','descriptive_A_B_difference'), 'UNKNOWN_CLAIM_KIND')
    summary, ref, points, unavailable = _comparison(product, node, reference_selections)
    if unavailable:return 'blocked', None, unavailable
    if kind == 'biological_participant_counts':
        keys(selection, (), 'COUNT_SELECTION')
        return ('supported' if asserted == summary['biological_people'] and type(asserted) is dict and all(type(v) is int for v in asserted.values()) else 'unsupported'), summary['biological_people'], 'Counts are unique people from complete D/S strata, not trials, subregions, draws or item rows.'
    if kind == 'descriptive_A_B_difference':
        keys(selection, ('contrast',), 'A_B_SELECTION');name=selection['contrast']
        pairs = node['config']['inference']['A_B_pairs']
        require(name in pairs and set(summary['point_A_B']) == set(pairs), 'PREDECLARED_A_B_ROSTER')
        for pair_id,pair in pairs.items():
            require(set(pair) == {'A','B'} and all(x in points for x in pair.values()), 'ACTUAL_A_B_METHODS')
            a,b = (summary['point_gains'][pair[x]]['aggregate'] for x in ('A','B'))
            require(near(summary['point_A_B'][pair_id], b-a), 'A_B_DIFFERENCE_CONSISTENCY')
        value=summary['point_A_B'][name]
        return ('supported' if near(asserted,value) else 'unsupported'), value, 'Observed paired difference only; no agent/code-access causal effect is inferred.'
    keys(selection, ('method',), 'METHOD_SELECTION');method=selection['method'];require(method in points, 'METHOD_PRESENT')
    if kind == 'point_gain':
        value=summary['point_gains'][method]['aggregate']
        return ('supported' if near(asserted,value) else 'unsupported'), value, 'Selected-reference MSE minus candidate MSE; zero and negative gains remain valid outcomes.'
    require(product['operator'] == 'O28', 'O28_INTERVAL_REQUIRED')
    keys(asserted, ('low','high','interpretation'), 'INTERVAL_ASSERTION')
    draws=summary['draws'];manifest=summary['manifest'];n=summary['planned_draws']
    require(type(resampling) is dict and type(resampling.get('manifest')) is dict, 'ACTUAL_GLOBAL_RESAMPLING_REQUIRED')
    require(identical(manifest,resampling['manifest']), 'ACTUAL_GLOBAL_RESAMPLING_MANIFEST')
    inference=node['config']['inference']
    global_plan=node['config']['global_resampling']
    require(type(global_plan['B']) is int and n == global_plan['B'], 'FROZEN_PLANNED_DRAW_COUNT')
    require(manifest['support_identity'] == global_plan['support_identity'] == inference['support_identity'], 'FROZEN_RESAMPLING_SUPPORT')
    require(type(n) is int and n > 0 and len(draws) == n == len(manifest['draws']) == manifest['B'], 'ALL_PLANNED_DRAWS')
    require([d['draw'] for d in draws] == list(range(n)) and [d['draw'] for d in manifest['draws']] == list(range(n)), 'PLANNED_DRAW_ORDER')
    if summary['interval_status'] != 'conditional_valid' or any(d['joint_status'] != 'valid' or d.get('global_joint_status','valid') != 'valid' for d in draws):
        return 'blocked', None, 'Any planned joint draw failure keeps the interval unavailable; no finite-case deletion or redraw.'
    require(summary['valid_draws'] == n and set(summary['intervals']) == set(points), 'COMPLETE_INTERVAL_METHODS')
    require(all(set(d['losses']) == set(points) and set(d['gains']) == set(points) for d in draws), 'COMPLETE_DRAW_METHODS')
    for draw in draws:
        require(all(v['status'] == 'valid' for v in draw['losses'].values()), 'VALID_DRAW_LOSSES')
        reference_loss = number(draw['losses'][ref]['aggregate'])
        require(all(near(draw['gains'][m], reference_loss-number(draw['losses'][m]['aggregate'])) for m in points), 'DRAW_SIGNED_GAIN_CONSISTENCY')
    bounds=summary['intervals'][method];require(number(bounds['low']) <= number(bounds['high']), 'ORDERED_BOUNDS')
    valid = near(asserted['low'],bounds['low']) and near(asserted['high'],bounds['high']) and asserted['interpretation'] == 'conditional_sensitivity'
    return ('supported' if valid else 'unsupported'), {'low':bounds['low'],'high':bounds['high']}, 'Source-produced conditional interval only; quantile correctness and calibrated population coverage are not established by this checker.'


def adjudicate_collected(products, nodes, reference_selections, report_node, claims, expert_reviews=(), *, resampling=None):
    """Trusted operator inputs are existing Engine products/plan/selections.

    Only claims are candidate assertions. Never pass candidate-supplied product
    tables or treat source fields/pins as issuer authentication or qualification.
    """
    record, report, rows = _report(products, report_node)
    require(type(claims) is list and len(claims) <= 128, 'BOUNDED_CLAIMS')
    seen=set();out=[]
    for claim in claims:
        keys(claim, ('id','kind','handle','product','selection','asserted'), 'CLAIM_SCHEMA')
        ident=text(claim['id']);require(ident not in seen, 'UNIQUE_CLAIM_ID');seen.add(ident)
        require(claim['handle'] in rows, 'KNOWN_REPORT_HANDLE');text(claim['kind'])
        row=rows[claim['handle']]; product, reason=_evidence(products,record,row,claim['product'])
        if product is None:
            status,value,why='blocked',None,reason
        else:
            node_id,role=claim['product'].rsplit('.',1)
            roles={'correlation':'pooled_and_within_condition_metrics','positive_within_condition_correlation':'pooled_and_within_condition_metrics',
                   'point_gain':'candidate_reference_summary','biological_participant_counts':'candidate_reference_summary',
                   'conditional_interval':'paired_intervals','descriptive_A_B_difference':'candidate_reference_summary'}
            try:
                require(claim['kind'] in KNOWN_UPGRADES or roles.get(claim['kind']) == role, 'ACTUAL_ROLE_FOR_CLAIM')
                node=nodes[node_id];require(node['operator'] == product['operator'] and node['cell'] == product['cell'] and node['profile'] == product['profile'], 'ACTUAL_PLAN_PRODUCT_JOIN')
                status,value,why=_objective(claim['kind'],claim['selection'],claim['asserted'],product,node,reference_selections,resampling)
            except (ContractError,KeyError,TypeError,ArithmeticError) as e:
                status,value,why='blocked',None,'SOURCE_OUTPUT_INCONSISTENT_OR_UNAVAILABLE: '+str(e)
        out.append({'id':ident,'kind':claim['kind'],'handle':claim['handle'],'product':claim['product'],
                    'status':status,'observed':value,'reason':why})
    criteria=EXPERT_CRITERIA[record['profile']];expert={}
    for review in expert_reviews:
        keys(review, ('criterion','status','reviewer_ref','rationale','handles'), 'EXPERT_RECORD_SCHEMA')
        criterion=review['criterion'];require(criterion in criteria and criterion not in expert,'EXACT_UNIQUE_EXPERT_CRITERION')
        require(review['status'] in ('supported','unsupported','not_completed_with_blocker','requires_adjudication'), 'RUBRIC_STATUS')
        text(review['reviewer_ref']);text(review['rationale'])
        require(type(review['handles']) is list and review['handles'] and len(set(review['handles'])) == len(review['handles']) and all(h in rows for h in review['handles']), 'EXPERT_SOURCE_CITATIONS')
        expert[criterion]=dict(review)
    result = {'schema':'language_claim_evidence_adjudication_v1','scope':SCOPE,'report_cell':record['cell'],
            'report_profile':record['profile'],'upstream_table_agreement':report['full_scientific_completion'],
            'all184_handle_statuses':[{'handle':h,'status':rows[h]['status']} for h in HANDLES],
            'claim_results':out,'recorded_external_expert_assessments':list(expert.values()),
            'expert_criteria_not_recorded':[c for c in criteria if c not in expert],
            'expert_record_authenticity':'External operator responsibility; records are not machine-certified scientific approval.',
            'machine_scope':'Numerical/support/report consistency of cited collected outputs, not raw-data validity, method-policy enforcement or truth of free text.',
            'scientific_task_completion':'External scientific adjudication remains separate from table agreement and signed outcomes.',
            'scientific_qualification':False,'benchmark_count_delta':0}
    # No returned scope, observed support count, or expert citation list aliases
    # the source-owned Engine or the canonical module contract.
    return copy.deepcopy(result)


def adjudicate_engine(engine, report_node, claims, expert_reviews=()):
    """Concrete additive post-O26 caller; no Engine execution or output mutation."""
    require(engine.targets_open and engine.collector.seal is not None, 'AFTER_EXISTING_GLOBAL_BARRIER_ONLY')
    nodes={n['id']:n for n in engine.plan['nodes']}
    require(len(nodes) == len(engine.plan['nodes']) and report_node in nodes and nodes[report_node]['operator'] == 'O26','ACTUAL_O26_NODE')
    record=engine.products[report_node]['all_main_and_SI_obligation_reports']
    require(all(record[k] == nodes[report_node][k] for k in ('operator','cell','profile')), 'ACTUAL_O26_PLAN_JOIN')
    return adjudicate_collected(engine.products,nodes,engine.reference_selections,report_node,claims,expert_reviews,
                               resampling=engine.resampling)
