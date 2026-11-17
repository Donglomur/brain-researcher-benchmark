"""Full executable operator chain. No runtime/data access on module import."""
import hashlib
import os
import time
from pathlib import Path
from .admission import Admission
from .artifacts import Journal, owned
from .controller import execute
from .data import PacketStore
from .observer import CgroupObserver
from .report import aggregate, render_markdown
from .scoring import load_predictions, assess_case
from .transport import DockerTransport
from .validation import exact, need, bound_json, bound_bytes, digest, encoded, decode


def verify_tree(root, files, file_cap):
    root = Path(root)
    need(root.is_absolute() and root.is_dir() and all(not p.is_symlink() for p in (root, *root.parents)), 'owned source/context tree')
    declared = {d['path'] for d in files}
    observed = set()
    for path in root.rglob('*'):
        need(not path.is_symlink(), 'no context symlink')
        if path.is_file():
            observed.add(path.relative_to(root).as_posix())
    need(observed == declared, 'exact admitted context membership')
    for desc in files:
        bound_bytes(root, desc, file_cap)


from .bindings import validate_bundle
from .schedule import validate as validate_schedule
from .custody import DiagnosticCapture
from .uncertainty import aggregate_assessments

def _prepare(admission_value,selected_admission_sha256,plan,campaign,selected_campaign_sha256,session):
    need(digest(campaign) == selected_campaign_sha256, 'independently selected whole campaign')
    admission = Admission(admission_value, selected_admission_sha256, plan)
    admission.require_authentic()
    exact(campaign, ('schema', 'admission_sha256', 'metadata_root', 'input_root', 'output_root',
                     'runtime_root', 'runtime_manifest', 'programs', 'indices', 'configs', 'recipes',
                     'trusted_payloads', 'external_authoring_attempts', 'docker', 'python', 'cgroup_path',
                     'memory_bytes', 'scratch_bytes', 'wire_bytes', 'journal_bytes', 'gpu_devices','schedule','ownership_token'), 'whole campaign')
    need(campaign['schema'] == 'motormint_full_campaign_v2' and
         campaign['admission_sha256'] == admission.commitment, 'campaign/admission identity')
    root, cap = Path(campaign['metadata_root']), admission.value['limits']['file_bytes']
    runtime = bound_json(root, campaign['runtime_manifest'], cap)
    need(digest(runtime) == admission.value['runtime_source_sha256'], 'selected complete runtime source manifest')
    exact(runtime, ('files',), 'runtime manifest')
    verify_tree(campaign['runtime_root'], runtime['files'], cap)
    for evidence in admission.value['bindings'] + list(admission.value['gate_evidence'].values()):
        bound_bytes(root, evidence, cap)
    ids = {case['id'] for case in plan['cases']}
    for field in ('indices', 'configs', 'recipes', 'trusted_payloads'):
        need(type(campaign[field]) is dict and set(campaign[field]) == ids, 'all-case bindings: ' + field)
    roles = tuple(validate_schedule(campaign['schedule']))
    need(set(campaign['programs']) == set(roles), 'independent reference plus paired A/B')
    need(campaign['programs']['candidate_A']['image'] == campaign['programs']['candidate_B']['image'], 'identical A/B immutable runtime image')
    need(len(plan['cases']) * len(roles) <= admission.value['limits']['attempts'], 'campaign-wide attempt ceiling')
    role_seconds = admission.value['context_pair']['A']['resources']['role_seconds']
    need(admission.value['limits']['normal_seconds'] >= 3*(role_seconds + admission.value['limits']['cleanup_seconds']), 'campaign capacity for equal original per-role clocks and cleanup')
    output = Path(campaign['output_root'])
    need(output==session.root and output.is_absolute() and output.is_dir(), 'owned outer-selected campaign output root')
    origins = [Path(campaign['programs'][r]['source_directory']).resolve() for r in roles]
    need(len(set(origins)) == 3 and all(a not in b.parents for a in origins for b in origins if a != b), 'independent code capture roots')
    for role in roles:
        p = campaign['programs'][role]
        exact(p, ('source_directory', 'source_sha256', 'worker_sha256', 'context_directory',
                  'context_files', 'image'), 'program runtime')
        context = p['context_files']
        if role.startswith('candidate_'):
            arm = admission.value['context_pair'][role[-1]]
            need(context == arm['common'] + arm['author_code'], 'exact A/B exposure inventory')
        verify_tree(p['context_directory'], context, cap)
        worker = Path(p['source_directory']) / 'worker.py'
        need(hashlib.sha256(worker.read_bytes()).hexdigest() == p['worker_sha256'] ==
             hashlib.sha256((Path(__file__).parent/'worker.py').read_bytes()).hexdigest(), 'selected worker source unchanged')
    need(campaign['programs']['reference']['context_directory'] not in
         [campaign['programs'][r]['context_directory'] for r in roles[1:]], 'reference context hidden from candidates')
    configs, indices, recipes, trusted = {}, {}, {}, {}
    for case in plan['cases']:
        key = case['id']
        configs[key] = bound_json(root, campaign['configs'][key], cap)
        indices[key] = bound_json(root, campaign['indices'][key], cap)
        recipes[key] = bound_json(root, campaign['recipes'][key], cap)
        trusted[key] = bound_json(root, campaign['trusted_payloads'][key], cap)
        validate_bundle(case,indices[key],configs[key],recipes[key])
        need(digest(configs[key]) == case['config_sha256'] and
             digest(indices[key]) == case['input_index_sha256'] and
             digest(recipes[key]) == case['metric_recipe_sha256'], 'original independent bindings before candidate execution')
    return admission,root,cap,roles,configs,indices,recipes,trusted


def run(admission_value,selected_admission_sha256,plan,campaign,selected_campaign_sha256,*,session):
    """Called only by concrete outer-observed campaign_child with original clock."""
    executions=[];reports={};fatal=None;journal=None;journal_receipt=None;attempts=[]
    with session.stage('preparation'):
        admission,root,cap,roles,configs,indices,recipes,trusted=_prepare(admission_value,selected_admission_sha256,plan,campaign,selected_campaign_sha256,session)
    output=session.root;observer=CgroupObserver(campaign['cgroup_path'],campaign['gpu_devices'])
    role_seconds=admission.value['context_pair']['A']['resources']['role_seconds']
    def packets(case):return PacketStore(campaign['input_root'],indices[case['id']],admission)
    try:
        journal=Journal(output,'all_attempts.jsonl',campaign['journal_bytes'],budget=session.budget)
        for role in roles:
            with session.stage('prediction:'+role):
                p=campaign['programs'][role];role_origin=time.monotonic();normal_end=role_origin+role_seconds
                cleanup_end=normal_end+admission.value['limits']['cleanup_seconds']
                need(cleanup_end<=session.end,'equal original role budget fits whole campaign clock')
                def transports(case,source_sha,started,end):
                    ordinal=next(i for i,c in enumerate(plan['cases']) if c['id']==case['id'])
                    capture=DiagnosticCapture(output,role+'-'+str(ordinal)+'-worker',65536,session.budget)
                    try:
                        return DockerTransport(docker=campaign['docker'],image=p['image'],python=campaign['python'],source_directory=p['source_directory'],source_sha=source_sha,worker_sha=p['worker_sha256'],context_directory=p['context_directory'],memory_bytes=campaign['memory_bytes'],scratch_bytes=campaign['scratch_bytes'],origin=started,normal_end=end,cleanup_end=cleanup_end,wire_cap_bytes=campaign['wire_bytes'],cgroup_parent=campaign['cgroup_path'][len('/sys/fs/cgroup'):],gpu_devices=campaign['gpu_devices'],diagnostics=capture,ownership_token=campaign['ownership_token'])
                    except BaseException as error:
                        session.persist(role+'-'+str(ordinal)+'-constructor-failure.json',{'reason':type(error).__name__+': '+str(error),'diagnostics':capture.close(),'launch_completed':False},final=True);raise
                result=execute(admission,role,packets,transports,lambda c:configs[c['id']],p['source_sha256'],output,journal,observer,origin=role_origin,normal_end=normal_end,budget=session.budget)
                executions.append(result)
    except BaseException as error:
        fatal={'stage':'prediction','reason':type(error).__name__+': '+str(error)}
    finally:
        if journal is not None:journal_receipt=journal.close()
    if journal_receipt is not None:
        chain='0'*64
        for i,line in enumerate((output/'all_attempts.jsonl').read_bytes().splitlines()):
            row=decode(line);observed=row.pop('sha256');need(row['sequence']==i and row['previous']==chain and digest(row)==observed,'retained complete attempt chain');chain=observed
            keys=('id','role','status','wall_seconds','cpu_seconds','gpu_seconds','token_count','bytes_written','peak_rss_bytes')
            attempts.append({k:row['attempt'][k] for k in keys})
        need(chain==journal_receipt['chain_sha256'],'attempt final commitment')
    by_role={r['role']:r for r in executions};refs={r['case']:r['artifact'] for r in by_role.get('reference',{}).get('outputs',[])}
    authoring=[]
    try:
        with session.stage('external_cost_inventory'):
            authoring=bound_json(root,campaign['external_authoring_attempts'],cap);need(type(authoring) is list,'external development/search attempts')
        for role in ('candidate_A','candidate_B'):
            assessed=[];counter=[0]
            def durable(row):
                counter[0]+=1;session.persist(role+'-outcome-'+str(counter[0])+'.json',row)
            artifacts={r['case']:r['artifact'] for r in by_role.get(role,{}).get('outputs',[])}
            with session.stage('assessment:'+role):
                for case in plan['cases']:
                    session.clock();key=case['id']
                    if key not in artifacts or key not in refs:continue
                    pins=[{k:record[k] for k in ('path','bytes','sha256')} for record in (artifacts[key],refs[key])]
                    try:
                        packet=packets(case);left=load_predictions(output,pins[0],case,cap);right=load_predictions(output,pins[1],case,cap)
                        result=assess_case(case,packet,left,right,recipes[key],trusted[key],clock=session.clock,persist=durable,artifact_commitments=pins)
                    except Exception as error:
                        result={'case':key,'module':case['module'],'outputs':[{'key':out,'kind':None,'status':'invalid_assessment','reason':type(error).__name__+': '+str(error),'commitments':pins,'absolute_deviation':None} for out in case['outputs']],'uncertainty':[{'id':r['id'],'status':'unscorable'} for r in case['uncertainty_requirements']]}
                        durable(result)
                    assessed.append(result)
                uncertainty=aggregate_assessments(plan,assessed,maximum_bytes=admission.value['limits']['numerical_bytes'],clock=session.clock)
            with session.stage('report:'+role):
                report=aggregate(plan,assessed,executions,attempts,authoring,numerical_bytes=admission.value['limits']['numerical_bytes'],aggregate_uncertainty=uncertainty,schedule=campaign['schedule'])
                report['prediction_attempt_costs_attribution']=report.pop('all_attempt_costs')
                report['inclusive_cost_witness']='outer-observation.json; nested stage/attempt counters must not be summed with it'
                report['whole_campaign_cost_complete']=False
                session.persist(role+'-report.json',report);reports[role]=report
    except BaseException as error:
        fatal={'stage':'assessment_or_publication','reason':type(error).__name__+': '+str(error)}
    result={'reports':list(reports),'executions':executions,'fatal':fatal,'journal':journal_receipt,'plan_sha256':digest(plan),'schedule':campaign['schedule'],'unassessed_support':'All planned outputs absent from durable outcome/report files remain unassessed; frozen plan defines every required item.','scientifically_qualified':False}
    session.persist('campaign-final.json',result,final=True)
    return result
