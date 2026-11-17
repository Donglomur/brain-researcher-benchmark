"""Complete selected scope, including unresolved historical producers."""
from .common import require, unique

PROFILES = ('R_source20','R_paper40','I_bijective_full')


def obligation_ids(catalog):
    scope = catalog['scope']
    panels = [r['obligation_id'] for r in scope['panels']]
    # Use the exact accepted legacy inverse, not a new count-based surrogate.
    from k4bench.admission import scope_inventory
    ids = scope_inventory(catalog)
    require(len(ids)==121 and len(panels)==71, 'complete-original-scope-changed')
    return tuple(sorted(ids))


def check_plan(plan, catalog):
    require(plan['canonical_id']=='PAPER-paper-method-006', 'canonical-task-mismatch')
    require(plan['profile'] in PROFILES, 'unknown-numerical-profile')
    require(plan['construction_profile'] in {'author_commit_v4_0_2','paper_methods_v1'},
            'unknown-construction-profile')
    require(plan['arm'] in {'paper-data','paper-data-plus-author-code'},'A-B-arm-required')
    jobs = unique(plan['jobs'],'id')
    coverage = unique(plan['coverage'],'obligation_id')
    require(set(coverage)==set(obligation_ids(catalog)), 'full-obligation-coverage-required')
    require(set(plan['families'])=={f'G{i:02}' for i in range(1,23)}, 'job-family-loss')
    require({j['family'] for j in jobs.values()}==set(plan['families']), 'family-without-job-disposition')
    for job in jobs.values():
        require(job['family'] in plan['families'], 'unknown-job-family')
        require(set(job['depends_on'])<=set(jobs) and job['id'] not in job['depends_on'],
                'invalid-dependency')
        require(job['status'] in {'concrete-consumer','unresolved-original-producer'}, 'invalid-source-status')
        if job['status']=='unresolved-original-producer':
            require(bool(job['missing']), 'missing-producer-without-reason')
        else:
            require(job['operation'] in __import__('k4programme.dispatch',fromlist=['OPERATIONS']).OPERATIONS,
                    'unknown-concrete-operation',job['operation'])
            for binding in job['inputs'].values():
                require(binding['source'] in {'external','job'},'invalid-input-source')
                if binding['source']=='job':
                    require(binding['job_id'] in job['depends_on'],'unplanned-producer-edge')
                    require(type(binding['result_path']) is list,'invalid-result-path')
            from .waveform_chain import validate_waveform_edges
            validate_waveform_edges(job,jobs)
            require(plan['construction_profile']=='paper_methods_v1' or job['operation'].startswith('legacy_'),
                    'new-consumer-cannot-be-literal-author-code',job['id'])
    for row in coverage.values():
        require(bool(row['job_ids']) and set(row['job_ids'])<=set(jobs), 'obligation-has-no-producer')
    order, pending = [], set(jobs)
    while pending:
        next_ids = sorted(i for i in pending if set(jobs[i]['depends_on'])<=set(order))
        require(bool(next_ids), 'cyclic-programme-graph')
        order.extend(next_ids); pending.difference_update(next_ids)
    return jobs, coverage, order


def complete_report(plan, catalog, results):
    jobs, coverage, order = check_plan(plan,catalog)
    require(set(results)==set(jobs), 'missing-planned-job-disposition')
    rows=[]
    for identity in obligation_ids(catalog):
        row=coverage[identity]
        dependencies=[results[j] for j in row['job_ids']]
        # Worker return is NEVER native validation, paper reproduction or bank parity.
        ready=all(r['status']=='worker-returned-unqualified' for r in dependencies)
        rows.append({'obligation_id':identity,'job_ids':list(row['job_ids']),
                     'source_consumer_outputs_present':ready,
                     'status':'awaiting-protected-validation' if ready else 'required-unscorable',
                     'missing_or_failed':[{ 'job_id':j,'status':results[j]['status'],
                                           'reason':results[j].get('reason')}
                                          for j in row['job_ids']
                                          if results[j]['status']!='worker-returned-unqualified']})
    return {'canonical_id':plan['canonical_id'],'profile':plan['profile'],
            'construction_profile':plan['construction_profile'],'arm':plan['arm'],
            'obligations':rows,'jobs':results,'whole_paper_reproduced':None,
            'scientific_ready':False,'complete_software':False,
            'independent_validation':'unchanged original R1/R2 required; local output is not authority',
            'count_delta':0,'scope_counts':{'obligations':121,'panels_GUI':71,
                                          'main_figures':5,'extended_figures':7,'supplement':13}}
