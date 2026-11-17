"""Source-owned joins for actual completed campaign products; no numeric proxies."""
import copy
from .contracts import need, descriptor, canonical, digest, closed, integer
from .programme import expected_groups, group_id, CONDITIONS, allowed_references, bank_id

CASE_TEMPLATE_KEYS = {'binding','references','states','training','query','support','mode','agent_seed',
    'stage','initial_messages','initial_context_sha256','public_members','public_member_roles',
    'produced_predictions','shared_preparation_frozen','prior_case_answers'}


def selected_case_context(config,gid,index):
    """Expand one immutable wire template into an independently mutable case."""
    integer(index,0,573)
    need(gid in {group_id(g)for g in expected_groups()if g['mode']=='I'},'registered investigating group')
    if 'case_context_template'in config or 'case_count'in config:
        need('case_contexts'not in config and type(config.get('case_count'))is int and config['case_count']==574,
             'one exact full574 case representation')
        template=config['case_context_template'];closed(template,CASE_TEMPLATE_KEYS)
        need(template['binding']['group']==gid and template['mode']=='I'and template['stage']=='S09'and
             template['produced_predictions']==[]and template['prior_case_answers']==[]and
             template['shared_preparation_frozen']is False,'fresh original case template')
        return {**copy.deepcopy(template),'case_index':index,'job_prefix':gid+'/case-%04d'%index}
    rows=config['case_contexts']
    need(type(rows)is list and len(rows)==574,'legacy full case list')
    need(all(row['case_index']==i and row['job_prefix']==gid+'/case-%04d'%i for i,row in enumerate(rows)),
         'complete unique legacy index and original job order')
    return copy.deepcopy(rows[index])


def development_output_binding(campaign):
    """Bind an independent E09/E10 report to this actual completed stage."""
    need(campaign.evidence.active=='S05'and campaign.collector is not None,'original pending training stage')
    expected={job for job,row in campaign.jobs.items()if row['stage']=='S05'}
    need(len(expected)==11 and expected<=set(campaign.collector.products)and not campaign.collector.failures,
         'all eleven actual original training/development outputs')
    result={}
    for job in sorted(expected):
        row=campaign.collector.products[job]
        original=campaign.originals[job]
        need(original.job==job and original.custody.complete and original.exit_code==0 and
             original.reaped and original.absence is True and
             row['terminal']==original.persistence['process']and
             row['original_worker_result']==original.persistence['worker_result'],
             'same original complete training producer')
        result[job]={'process':row['terminal'],'worker_result':row['original_worker_result'],
                     'selected_product':row['product'],'bindings':row['bindings']}
    return result


def register_collection_predictions(campaign, collection_pin):
    from .controller import Artifact
    need(campaign.evidence.active == 'S11' and campaign.collector.closed and
         not campaign.collector.failures, 'original complete collection only')
    doc = campaign.store.json(collection_pin, 64 * 2**20)
    expected = {group_id(g) for g in expected_groups()} | {
        bank_id(c, r) for c in CONDITIONS for r in allowed_references(c)} | {'TOOL_ONLY_BATCH','TOOL_ONLY_CASE'}
    need(doc['schema'] == 'NLB017_collection_commit_v1' and doc['programme'] == campaign.identity and
         doc['complete'] is True and not doc['failures'] and set(doc['prediction_groups']) == expected,
         'complete exact original prediction union')
    for key, pin in doc['prediction_groups'].items():
        descriptor(pin); name = 'collected/' + key
        need(name not in campaign.artifacts, 'one immutable collection registration')
        campaign.artifacts[name] = Artifact(pin,'S11','prediction','collector')
    # Only the protected action receives the full union. Actual native() still
    # resolves every descriptor under the original role and release barrier.
    from .native_selection import worker_context
    action = worker_context(campaign.selection['worker_contexts'],'assessment/grade',campaign.executor.selected)
    need(action['declared_inputs'] == [{'artifact': 'collected/' + key} for key in sorted(expected)],
         'exact frozen complete assessment input recipe')


def capture_actual_costs(campaign):
    need(campaign.evidence.active == 'S15' and {'S12','S13','S14'} <= set(campaign.evidence.done),
         'cost report only after original protected completion')
    need(set(campaign.group_budgets) == {group_id(g) for g in expected_groups()}, 'complete original group ledger census')
    processes = {}
    for job, observation in campaign.executor.originals.items():
        need(observation.custody.complete and observation.exit_code == 0 and observation.reaped and
             observation.absence is True and all(observation.stream_eof.values()) and
             observation.costs['cpu_seconds'] is not None, 'known complete original process costs')
        processes[job] = {'process': observation.persistence['process'], 'costs': dict(observation.costs)}
    body = {'schema': 'NLB017_original_prefinal_report_costs_v1', 'programme': campaign.identity,
            'measurement_point': 'after_S14_before_S15_aggregate_and_model',
            'group_budgets': {gid: budget.snapshot() for gid,budget in campaign.group_budgets.items()},
            'reference_budget': campaign.reference_budget.snapshot(),
            'root_budget': campaign.store.budget.snapshot(), 'original_processes': processes,
            'F_authoring_joins': campaign.f_authoring_joins,
            'external_reference_terminals': sorted(campaign.external_reference_costs),
            'subsequent_report_costs': 'Retained in original reporting/model/root ledgers; not yet incurred at this snapshot.',
            'no_sum_of_overlapping_parent_child_ledgers': True}
    original=campaign.store.write('reports/ACTUAL_PREFINAL_COSTS_FULL.json', canonical(body), 64 * 2**20)
    summary={k:body[k]for k in ('schema','programme','measurement_point','group_budgets','reference_budget',
                               'root_budget','subsequent_report_costs','no_sum_of_overlapping_parent_child_ledgers')}
    summary.update(schema='NLB017_original_prefinal_report_cost_summary_v1',
        complete_private_original=original, original_process_count=len(processes),
        full_F_authoring_count=len(campaign.f_authoring_joins),
        external_reference_terminal_count=len(campaign.external_reference_costs))
    return campaign.store.write('reports/ACTUAL_PREFINAL_COSTS.json', canonical(summary), 2 * 2**20)
