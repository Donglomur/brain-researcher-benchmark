"""Independently selected reference policies join actual controller-owned producers."""
from .errors import require
from .objects import canonical,digest,fields


def reference_policies(rows,scope,candidate_sources):
    expected={(d['id'],c,m) for d in scope.panel['datasets'] for c in scope.panel['prospective_conditions'] for m in scope.panel['prospective_control_methods']}
    actual={};require(len(rows)==80,'80 reference families required')
    for row in rows:
        fields(row,('dataset','condition','method','source','environment','pretrained_assets','source_review','native_qualification','competence_evidence','search_policy','selection_metric','tie_rule','refit_validation','compute_budget','domain','producer_jobs','output_products','information_class'))
        key=(row['dataset'],row['condition'],row['method']);require(key in expected and key not in actual,'reference family census')
        require(row['source'] not in candidate_sources,'reference policy not independently owned')
        require(row['source_review'] and row['native_qualification'] and row['competence_evidence'],'named baseline is not competent evidence')
        require(row['search_policy'] and row['compute_budget'] and row['producer_jobs'] and row['output_products'],'actual fit/predict reference route')
        require(row['tie_rule']=='first_chronological' and row['refit_validation'] is False,'fixed reference selection')
        if row['method']=='fixed_spectral_ridge':
            require(row['selection_metric']=='binary_AUROC_or_multiclass_kappa','spectral reference selection')
        else:require(row['selection_metric']=='balanced_accuracy','neural reference selection')
        actual[key]=digest(canonical(row))
    require(set(actual)==expected,'missing reference families')
    return actual


def close_reference_bank(policies,controller):
    validate_reference_bindings(controller.plan,controller.scope)
    out={}
    for policy in policies:
        controller.guard();key=family_key(policy);binding=controller.plan['reference_run_bindings'][key];runs=[]
        for run in binding['runs']:
            missing=[];products={};failures=[]
            for jid in run['producer_jobs']:
                require(jid in controller.collector.terminal,'reference job not terminal')
                terminal=controller.collector.terminal[jid]
                if terminal['status']!='closed':failures.append({'job':jid,'original_terminal':terminal})
            for name in run['output_products']:
                if name not in controller.collector.products:missing.append(name);continue
                owner=next(j for j in run['producer_jobs'] if name in controller.jobs[j]['expected_outputs'])
                products[name]=validate_original_product(controller,name,owner,policy,run['run'])
            runs.append({'run':run['run'],'programme':run['programme'],'domain':run['domain'],'producer_jobs':run['producer_jobs'],'prediction_groups':run['prediction_groups'],'products':products,'missing_outputs':missing,'original_failures':failures,'complete':not missing and not failures})
        out[key]={'policy':digest(canonical(policy)),'binding':digest(canonical(binding)),'runs':runs,'complete':all(r['complete'] for r in runs)}
    require(len(out)==80,'reference bank census')
    controller.guard();return out


def family_key(row):return '|'.join(row[k] for k in ('dataset','condition','method'))

def purpose_for(condition):
    require(condition in ('strict_person','strict_person_and_montage'),'protected condition')
    return 'I-person' if condition=='strict_person' else 'I-person-montage'

def validate_reference_bindings(plan,scope):
    policies={family_key(p):p for p in plan['reference_policies']}
    require(len(policies)==80 and set(plan['reference_run_bindings'])==set(policies),'all80 reference run bindings')
    jobs={j['id']:j for j in plan['jobs']};owners={out:j for j in plan['jobs'] for out in j['expected_outputs']}
    programmes={p['id']:p for p in plan['programmes']}
    for key,b in plan['reference_run_bindings'].items():
        fields(b,('policy','runs'))
        policy=policies[key];require(b['policy']==digest(canonical(policy)) and b['runs'],'exact reference policy binding')
        runs=b['runs'];names=[];all_jobs=set();all_outputs=set()
        for r in runs:
            fields(r,('run','programme','domain','producer_jobs','output_products','prediction_groups'))
            require(r['programme'] in programmes and programmes[r['programme']]['role']=='reference','reference programme identity')
            require(r['domain']==policy['domain'],'selected reference exposure domain')
            require(r['producer_jobs'] and len(set(r['producer_jobs']))==len(r['producer_jobs']),'reference job set')
            require(r['output_products'] and len(set(r['output_products']))==len(r['output_products']),'reference output set')
            for jid in r['producer_jobs']:
                j=jobs[jid]
                require(j['source']==policy['source'] and j['programme']==r['programme'] and j['domain']==r['domain'],'reference original job source/programme/domain')
                require(j['run']==r['run'] or j['run'] is None,'reference original run')
            require(set(r['output_products'])=={x for jid in r['producer_jobs'] for x in jobs[jid]['expected_outputs']},'complete original producer output union')
            require(len(r['prediction_groups'])==1,'one complete protected case group per reference run')
            for gid in r['prediction_groups']:
                g=plan['prediction_groups'][gid]
                require(all(g[k]==policy[k] for k in ('dataset','condition','method')) and g['purpose']==purpose_for(policy['condition']),'reference scientific group identity')
                require(g['programme']==r['programme'] and g['run']==r['run'],'reference group original run/programme')
                require(set(g['members'])<=set(r['output_products']),'reference group not from declared output union')
                require(all(owners[x]['id'] in r['producer_jobs'] and owners[x]['run']==r['run'] for x in g['members']),'reference query group producer/run')
            names.append((r['programme'],r['run']));all_jobs.update(r['producer_jobs']);all_outputs.update(r['output_products'])
        require(len(set(names))==len(names),'duplicate reference run')
        programmes_used={x[0] for x in names};require(len(programmes_used)==1,'single reference family programme')
        programme=next(iter(programmes_used))
        require([r['run'] for r in runs]==plan['run_rosters'][programme],'complete ordered qualified reference runs')
        require(all_jobs==set(policy['producer_jobs']) and all_outputs==set(policy['output_products']),'whole reference policy producer/output closure')
    return True

def validate_original_product(controller,name,expected_job,policy,run):
    controller.guard()
    item=controller.collector.products[name];job=controller.jobs[expected_job]
    domain=controller.exposure.domains[job['domain']]
    require(domain['role']=='independent_reference' and domain['arm']=='reference' and domain['purpose']==purpose_for(policy['condition']),'original independent reference domain role/arm/purpose')
    require(name in job['expected_outputs'] and item['producer_job']==job['id'] and item['producer_job_identity']==digest(canonical(job)),'reference actual original job/output join')
    require(item['producer_programme']==job['programme'] and item['producer_domain']==job['domain'] and item['producer_run']==job['run'],'reference durable programme/domain/run')
    receipt=item['original_process']
    require(receipt['natural_completion'] and receipt['exit_code']==0 and receipt['scope_quiescent'],'reference original process incomplete')
    require(receipt['attempt_id']==job['id'] and receipt['source_id']==policy['source']==job['source'],'reference original process/source')
    require(receipt['environment']==policy['environment']==controller.authority.selection['environment'],'reference selected original environment')
    req=receipt['request_body']
    require(digest(canonical(req))==receipt['request']['sha256'] and item['producer_request']==receipt['request'],'reference original request custody')
    require(all(req[k]==job[j] for k,j in (('job_id','id'),('programme_id','programme'),('domain','domain'),('context','context'),('stage','stage'),('operation','operation'),('payload','payload'),('source_id','source'))),'reference actual request/job semantics')
    require(item['product']['source']==policy['source'] and item['product']['request']==receipt['request']['sha256'],'reference collected product source/request')
    if item['product']['kind']=='prediction':require(job['run']==run,'reference query output run')
    return item['identity']

def admit_contrast_runs(controller,item):
    key='|'.join(item[k] for k in ('dataset','condition','reference'))
    binding=controller.plan['reference_run_bindings'][key]
    expected_refs=[r['prediction_groups'][0] for r in binding['runs']]
    programmes={p['id']:p for p in controller.plan['programmes']}
    candidate_programmes=[p['id'] for p in programmes.values() if p['role']=='candidate' and p['arm']==item['arm']]
    require(len(candidate_programmes)==1,'one candidate arm programme')
    cp=candidate_programmes[0];qualified=controller.plan['run_rosters'][cp]
    require(len(item['runs'])==len(qualified)==len(expected_refs),'complete selected candidate/reference run-pair count')
    actual_candidates=[];actual_refs=[];candidate_runs=[]
    for pair in item['runs']:
        fields(pair,('candidate','reference'))
        a=controller.plan['prediction_groups'][pair['candidate']];b=controller.plan['prediction_groups'][pair['reference']]
        require(a['programme']==cp and a['dataset']==item['dataset'] and a['condition']==item['condition'] and a['purpose']==purpose_for(item['condition']),'candidate contrast original scientific identity')
        require(b['purpose']==a['purpose'],'cross-purpose contrast refused')
        actual_candidates.append(pair['candidate']);actual_refs.append(pair['reference']);candidate_runs.append(a['run'])
    require(len(set(actual_candidates))==len(actual_candidates) and len(set(actual_refs))==len(actual_refs),'duplicated contrast run')
    require(candidate_runs==qualified and actual_refs==expected_refs,'exact ordered complete qualified run pairs')
    return binding
