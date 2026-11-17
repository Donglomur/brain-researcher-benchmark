"""All selected public source/operation/row/finite-output checks before target bodies."""
from pathlib import Path
import hashlib
from core import need, canonical, relative, encoded, pin, integer
from artifacts import Artifacts
from records import Records
from bank import Bank
from views import packet
from contracts import PEOPLE, ENDPOINTS, CONFIGS, FAMILIES, identity, cells, roster
from schedule import graph, census, support
from journal_audit import audit
from reference_adapter import primitive, host_descriptor, join_output, configuration
from array_io import Limits, load
from transport import COMMON, ENTRIES
from edges import view_authority, selection_edges, investigation, candidate, tools
from operative import source as effective_source
from reference_adapter import reference_dtype


def indexed(index, root, a, budget, artifacts):
    need(type(index) is dict and len(index) <= a['resources']['max_operations'], 'bounded complete metadata index')
    for key,d in index.items():
        need(type(key) is str and len(key) == 64 and canonical(d['path']) == canonical(root)/(key+'.json'), 'exact fixed indexed file path')
        artifacts.allowed(d['path'])
    return Records(root,budget,a['resources']['record_bytes'],a['resources']['index_bytes'],index)


def native_configuration(a, p, i):
    role = 'private' if p['role'] in ('reference','selection') else 'public'; selected = a['native_'+role]; limits = i['limits']
    nonce = hashlib.sha256(encoded([selected['study'],p['operation'],i['source']])).hexdigest()
    binds = [{'Type':'bind','Source':m['source'],'Target':m['destination'],'ReadOnly':True,
              'BindOptions':{'Propagation':'rprivate'}} for m in p['mounts']]
    binds.append({'Type':'bind','Source':p['output'],'Target':p['container_output'],'ReadOnly':False,
                  'BindOptions':{'Propagation':'rprivate'}})
    return {'Image':selected['image_id'],'Cmd':p['argv'],'Env':['PYTHONHASHSEED=0','OMP_NUM_THREADS=1',
        'OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1','HOME=/scratch'],'WorkingDir':'/scratch','User':selected['uid_gid'],
        'AttachStdout':False,'AttachStderr':False,'NetworkDisabled':True,
        'Labels':{'neural049.study':selected['study'],'neural049.operation':p['operation'],'neural049.nonce':nonce},
        'HostConfig':{'NetworkMode':'none','ReadonlyRootfs':True,'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges:true'],
        'Privileged':False,'PidsLimit':limits['pids'],'Memory':limits['memory_bytes'],'MemorySwap':limits['memory_bytes'],
        'NanoCpus':limits['cpu_rate_ns'],'AutoRemove':False,'Mounts':binds,
        'DeviceRequests':[{'Driver':'nvidia','DeviceIDs':selected['gpu_ids'],'Capabilities':[['gpu']]}] if selected['gpu_ids'] else [],
        'Tmpfs':{'/scratch':'rw,noexec,nosuid,nodev,size='+str(limits['scratch_bytes'])},
        'LogConfig':{'Type':'local','Config':{'max-size':'1m','max-file':'1'}},'Ulimits':[{'Name':'nofile','Soft':1024,'Hard':1024}]}}


def operation(a, captured, p, native, artifacts, bank):
    i = native['intent']; need(p['mounts'] == i['mounts'] and p['argv'] == i['argv']
        and pin(encoded(native_configuration(a,p,i))) == i['config'], 'actual immutable Engine config/argv/mount reconstruction')
    req = artifacts.json(p['request']['path'],p['request']['pin'],a['resources']['view_bytes'])
    launch = artifacts.json(p['launch']['path'],p['launch']['pin'],a['resources']['source_bytes'])
    need(req == p['request_value'] and launch['request'] == p['request']['pin']
         and launch['source_manifest'] == captured['pin'] and launch['entry'] == ENTRIES[p['role']]
         and launch['deadline'] == i['cutoff'] and launch['original_origin'] == a['clock']['origin'], 'actual request/source/clock launch body')
    aliases = p['source_aliases']; expected = {n:'program/'+n for n in (*COMMON,ENTRIES[p['role']]+'.py')}
    if p['role'] == 'reference':
        impl = launch['worker_config']['implementation']; prefix = 'references/'+impl+'/'
        need(impl in ('r1','r2'), 'exact bank source role')
        expected = {'core.py':'program/core.py','reference_worker.py':'program/reference_worker.py'}
        expected.update({k:k for k in captured['manifest']['files'] if k.startswith(prefix) and k.endswith('.py')})
    expected = {alias:effective_source(captured['manifest'],logical)[0] for alias,logical in expected.items()}
    need(aliases == expected and launch['files'] == {alias:captured['manifest']['files'][source] for alias,source in expected.items()},
         'minimal exact source role closure; no reference capability in actors')
    mounts = {m['destination']:m for m in p['mounts']}; need(len(mounts) == len(p['mounts']), 'unique native mount destinations')
    for target,desc in [('/inputs/REQUEST.json',p['request']),('/inputs/LAUNCH.json',p['launch'])]:
        need(mounts[target]['source'] == desc['path'] and mounts[target]['pin'] == desc['pin'], 'request/config actual mount edge')
    for alias,source in expected.items():
        m = mounts['/inputs/source/'+alias]
        need(canonical(m['source']) == canonical(a['roots']['source'])/source and m['pin'] == captured['manifest']['files'][source], 'actual exact source mount')
    launcher = mounts['/inputs/LAUNCHER.py']; wc = launch['worker_config']; profile = a['profiles'][p['profile']]
    need(canonical(launcher['source']) == canonical(a['roots']['source'])/'program/sandbox_launcher.py'
         and launcher['pin'] == captured['manifest']['files']['program/sandbox_launcher.py'], 'original authenticated sandbox entry')
    expected_argv = [a['native_python'],'-I','-B','/inputs/LAUNCHER.py','/inputs/LAUNCH.json',
                     str(p['launch']['pin']['bytes']),p['launch']['pin']['sha256'],repr(a['clock']['origin']),repr(i['cutoff'])]
    need(p['argv'] == expected_argv and wc['request_path'] == '/inputs/REQUEST.json'
         and wc['request_pin'] == p['request']['pin'] and wc['source_manifest'] == captured['pin']
         and wc['origin'] == a['clock']['origin'] and wc['deadline'] == i['cutoff'] and wc['operation'] == p['operation']
         and wc['output'] == p['container_output'] and wc['qualified_execution'] is True
         and wc['read_cap'] == profile['numeric_read_bytes'] and wc['write_cap'] == profile['numeric_write_bytes'],
         'actual fixed worker argv/source/original clock/resource bridge')
    for m in p['mounts']:
        if bank.contains(m['source']):
            # Independent production measurement chain is joined; private label
            # bytes are deliberately NOT recaptured in pre-target admission.
            row = bank.by_path.get(str(canonical(m['source'])))
            need(row is not None and row['pin'] == m['pin'], 'admitted bank file, not neighbouring or protected metadata')
        else: artifacts.capture(m['source'],m['pin'],m['bytes_cap'],retain=False)
    for name,d in p['native']['artifacts'].items():
        artifacts.capture(Path(p['output'])/relative(name),d,max(a['resources']['array_bytes'],a['resources']['state_bytes']),retain=False)
    if p['role'] != 'reference':
        receipt = artifacts.json(Path(p['output'])/'RECEIPT.json',p['native']['artifacts']['RECEIPT.json'],a['resources']['state_bytes'])
        need(receipt['schema'] == 'neural049_worker_receipt_v1' and receipt['operation'] == p['operation']
             and receipt['request'] == p['request']['pin'] and receipt['source'] == captured['pin']
             and receipt['artifacts'] == {k:v for k,v in p['native']['artifacts'].items() if k != 'RECEIPT.json'}
             and receipt['origin'] == a['clock']['origin'] and receipt['deadline'] == i['cutoff'], 'actual trusted worker receipt/artifact closure')
    return req,launch,mounts


def batch_edges(request, job, packet_value, bank, mounts, fitting):
    table = packet_value['manifest']['days']; parts = request['batch']['parts']; assigned = job['training'] if fitting else job['query']
    need(request['batch']['schema'] == 'neural049_numeric_parts_v1'
         and [x['day'] for x in parts] == request['assigned_days'] == assigned, 'full original assigned day list')
    ids = []; allowed = set()
    for part in parts:
        original = next(x for x in table if x['person'] == job['person'] and x['day'] == part['day'])
        need(part['ids'] == original['ids'] and part['axis'] == original['axis'], 'full original part/axis')
        ids += part['ids']; arrays = dict(original['arrays'])
        if job['view'] == 'NC_D':
            need(original['disrupted_arrays'] is not None, 'complete disrupted source bundle'); arrays.update(original['disrupted_arrays'])
        if job['view'] == 'C': del arrays['x']
        if job['view'] == 'N': del arrays['context']
        need(set(part['arrays']) == set(arrays), 'exact C/N/NC fields')
        pairs = [(part['arrays'][k],v) for k,v in arrays.items()]
        if fitting: pairs.append((part['labels'],original['labels'][job['endpoint']]))
        else: need('labels' not in part, 'no query label descriptor')
        for d,actual in pairs:
            expected = {'bytes':actual['bytes'],'sha256':actual['sha256']}
            m = mounts[d['path']]; allowed.add(d['path'])
            need(d['pin'] == expected and d['shape'] == actual['shape'] and d['dtype'] == reference_dtype(actual['dtype'])
                 and m['pin'] == expected and m['source'] == bank.source(actual['path'],expected), 'complete same original/D physical part')
    need(ids == request['assigned_ids'], 'all assigned original rows')
    for target,m in mounts.items():
        if bank.contains(m['source']): need(target in allowed, 'no extra bank/label/day mount')
    return ids


def projected(raw, pred, endpoint):
    import numpy as np
    need(raw.shape == pred.shape and raw.dtype.str == pred.dtype.str == '<f8'
         and bool(np.isfinite(raw).all()) and bool(np.isfinite(pred).all()), 'all raw/projected finite double outputs')
    expected = np.clip(raw,-90.,90.) if endpoint == 'angle' else np.maximum(raw,0.)
    need(bool(np.array_equal(pred,expected)), 'same fixed target-blind projection')


def semantic_method(a, method, mode, identity_key, artifacts):
    from authority import selection_pin
    source = artifacts.capture(method['source']['path'],method['source']['pin'],131072)
    recipe = artifacts.json(method['recipe_descriptor']['path'],method['recipe_descriptor']['pin'],65536)
    claim = artifacts.json(method['claim']['path'],method['claim']['pin'],32768)
    need(recipe == method['recipe'], 'actual submitted recipe body')
    q = artifacts.json(method['admission']['path'],method['admission']['pin'],a['resources']['qualification_bytes'])
    need(q.get('schema') == 'neural049_method_admission_v1' and q.get('qualified') is True
         and q.get('realm') == 'actual_external_evidence' and q.get('issuer') == a['operator_identity']
         and q.get('identity') == identity_key and q.get('mode') == mode and q.get('selection') == selection_pin(a)
         and q.get('source_manifest') == a['source_manifest'] and q.get('source') == method['source']['pin']
         and q.get('recipe') == method['recipe_descriptor']['pin'] and q.get('claim') == method['claim']['pin']
         and q.get('source_context') == method['source_context'],
         'independent exact operative method review')
    for field in ('input_scope','state_isolation','no_hidden_labels','fixed_provider_grammar','full_output_support','query_batch_parity','source_only_global_authorship'):
        need(q.get(field) is True, 'actual semantic qualification '+field)
    need(q['evidence'], 'method evidence')
    for d in q['evidence']: artifacts.capture(Path(a['roots']['operator'])/relative(d['path']),d['pin'],a['resources']['qualification_bytes'],retain=False)


def actor_view(a, job, row, prepared, bank, artifacts):
    result = row['view']; root = canonical(result['root'])
    visible = artifacts.json(root/relative(result['view']['path']),result['view']['pin'],a['resources']['view_bytes'])
    plan = artifacts.json(root/relative(result['mounts']['path']),result['mounts']['pin'],a['resources']['view_bytes'])
    selection = row['selection']; cell = job['cell']
    view_authority(a,selection,artifacts)
    need(plan['selection'] == selection and selection['person'] == job['person']
         and selection['train_days'] == job['training'] and selection['query_days'] == [job['held']]
         and selection['view'] == ('NC_D' if cell['disrupted'] else cell['view']) and selection['role'] == 'outer'
         and selection['source_policy'] == row['policy']['source']['pin'] and selection['packet_pin'] == a['packet']['complete']['pin'],
         'exact complete actor fold and paired policy selection')
    need(visible['schema'] == 'neural049_case_view_v1' and visible['view'] == cell['view'], 'positive public actor view schema')
    expected_mounts = {}
    for role,key,days in (('train','train_parts',job['training']),('query','query_parts',[job['held']])):
        private = [x for x in plan['parts'] if x['role'] == role]
        need([x['day'] for x in private] == days and len(private) == len(visible[key]), 'complete original actor day membership')
        for part,meta in zip(visible[key],private):
            original = next(x for x in prepared['manifest']['days'] if x['person'] == job['person'] and x['day'] == meta['day'])
            need(part['ids'] == meta['ids'] == original['ids'] and part['axis'] == original['axis'], 'all actor rows/axes preserved')
            arrays = dict(original['arrays'])
            if cell['disrupted']: arrays.update(original['disrupted_arrays'])
            if cell['view'] == 'C': del arrays['x']
            if cell['view'] == 'N': del arrays['context']
            need(set(part['arrays']) == set(arrays), 'positive C/N/NC array exposure')
            pairs = [(part['arrays'][k],v) for k,v in arrays.items()]
            if role == 'train':
                need(set(part['labels']) == set(ENDPOINTS), 'all and only training endpoints')
                pairs += [(part['labels'][k],original['labels'][k]) for k in ENDPOINTS]
            else: need('labels' not in part, 'held actor labels absent')
            for d,actual in pairs:
                expected = {'bytes':actual['bytes'],'sha256':actual['sha256']}
                need({k:d[k] for k in ('bytes','sha256')} == expected and d['shape'] == actual['shape'] and d['dtype'] == actual['dtype'], 'same exact prepared original/D values')
                expected_mounts['/inputs/case/'+str(relative(d['path']))] = (bank.source(actual['path'],expected),expected)
    analyses = row['method'].get('analyses',[]) if cell['mode'] == 'I' else []
    for produced in (row['fit'],row['predict'],*analyses):
        req = produced['request_value']; mounts = {m['destination']:m for m in produced['mounts']}
        need(req['view'] == {'path':'/inputs/case/VIEW.json','pin':result['view']['pin']}, 'same complete view supplied to investigation and final computation')
        actual_bank = {k:m for k,m in mounts.items() if bank.contains(m['source'])}
        need(set(actual_bank) == set(expected_mounts), 'no extra query/other-fold label or bank capability')
        for target,(source,desc) in expected_mounts.items():
            need(actual_bank[target]['source'] == source and actual_bank[target]['pin'] == desc, 'actual individual immutable fold mount')
        need((req.get('tool_bank') is not None) is cell['tool'], 'tool access only in selected T1 cell')
    return visible


def admit(a, captured, producer_descriptor, budget):
    forbidden = [a['roots']['secrets'],str(Path(a['roots']['store'])/'private')]
    artifacts = Artifacts(budget,[a['roots'][k] for k in ('source','output','reference','operator','observation')],a['roots']['targets'],forbidden)
    need(canonical(producer_descriptor['path']) == canonical(a['roots']['output'])/'PRODUCER.json', 'fixed producer path before capture')
    p = artifacts.json(producer_descriptor['path'],producer_descriptor['pin'],a['resources']['producer_bytes'])
    need(p['schema'] == 'neural049_complete_collection_v1' and p['status'] == 'complete'
         and p['source'] == captured['pin'] and p['authority'] == captured['authority_pin']
         and p['modules'] == a['modules'] and p['cache'] is a['cache'] and p['original_origin'] == budget.origin,
         'exact complete selected producer')
    prepared, table = packet(a,budget); need(p['table'] == table and p['packet'] == a['packet'], 'same complete private metadata, no target body')
    need(p['census'] == census(table,a['modules'],a['cache']), 'full symbolic/actual support counts')
    bank = Bank(a,budget,prepared['manifest'])
    indexes = {'operations':(p['operations'],Path(a['roots']['output'])/'operations'),
               'phases':(p['phases'],Path(a['roots']['output'])/'phases'),
               'references':(p['references'],Path(a['roots']['reference'])/'records'),
               'actors':(p['actors'],Path(a['roots']['output'])/'actor-records')}
    records = {k:indexed(index,root,a,budget,artifacts) for k,(index,root) in indexes.items()}
    raw = artifacts.capture(p['journal']['path'],p['journal']['pin'],a['resources']['journal_bytes'])
    closure = audit(raw,p,a,records)
    for op in records['operations']:
        operation(a,captured,records['operations'][op],closure['native'][op],artifacts,bank)
    profile = a['profiles']['audit']
    limits = Limits(budget,{k:profile['numeric_'+k] for k in ('allocation_bytes','elements','serialized_bytes','files','work')})
    reference_rows = {}; selections = {}; candidate_rows = {}
    expected_references = set(); expected_actors = set()
    for job in graph(table,a['modules'],a['cache']):
        budget.tick(); phase = records['phases'][job['id']]
        if job['kind'].startswith('reference_') or job['kind'] == 'tool_bank':
            expected_references.add(job['id']); row = records['references'][job['id']]
            actual_job = row['job']; produced = row['produced']
            need(produced == records['operations'][job['id']], 'reference phase to original operation')
            if job['kind'] == 'reference_select':
                need(actual_job == job, 'exact selection job')
                selection_edges(a,job,produced,records,prepared,bank)
                req = produced['request_value']; value = artifacts.json(Path(produced['output'])/'SELECTION.json',produced['native']['artifacts']['SELECTION.json'],a['resources']['selection_bytes'])
                need(value == row['value'] and value['scope'] == req['scope'] and value['consumer_rows'] == req['rows']
                     and value['targets'] == req['targets'] and value['held_day'] == job['outer'], 'actual selection artifact/request edges')
                selections[(job['implementation'],job['endpoint'],job['view'],job['person'],job['outer'])] = value
                continue
            if job['kind'] != 'tool_bank': need(actual_job == job, 'exact complete reference job')
            else:
                selection_id = identity(['selection','r1',job['endpoint'],'NC',job['person'],job['outer']])
                winner = records['references'][selection_id]['value']['strongest']
                fit_id = identity(['final-fit','r1',job['endpoint'],'NC',job['person'],job['outer'],winner])
                need(actual_job == {**job,'fit':fit_id,'selection':selection_id,'implementation':'r1','view':'NC'}, 'exact selected NC R1 tool state, no substitute bank')
            impl = actual_job['implementation']; req = produced['request_value']; fitting = job['kind'] in ('reference_fit','reference_final_fit')
            view_authority(a,row['view_selection'],artifacts)
            joined = join_output(produced,req,artifacts,impl,a['resources']['state_bytes'])
            mounts = {m['destination']:m for m in produced['mounts']}
            ids = batch_edges(req,actual_job,prepared,bank,mounts,fitting)
            if fitting:
                need(req['scope']['training_days'] == job['training'] and req['scope']['training_ids'] == ids
                     and req['scope']['view'] == job['view'] and req['scope']['endpoint'] == job['endpoint'], 'actual fitted training scope')
                ordinal = job.get('configuration')
                if ordinal is None:
                    selected = records['references'][job['selection']]['value']; ordinal = selected['selected'][job['family']]
                need(req['configuration'] == configuration(impl,ordinal), 'actual selected full configuration')
            else:
                fitted = records['references'][actual_job['fit']]
                need(req['state'] == fitted['joined']['container_document'], 'prediction uses actual exact original fit state')
                tree = joined['tree']; r = host_descriptor(primitive(tree['raw'],impl),produced); d = host_descriptor(primitive(tree['projected'],impl),produced)
                x,y = load(r,[a['roots']['reference']],limits),load(d,[a['roots']['reference']],limits)
                need(x.shape == y.shape == (len(ids),), 'complete scalar reference rows before target')
                projected(x,y,job['endpoint'])
                key = (job['kind'],actual_job['endpoint'],actual_job['view'],actual_job['person'],
                       actual_job.get('outer'),tuple(actual_job['query']),actual_job.get('configuration'),actual_job.get('family'),actual_job.get('axis'))
                if impl == 'r1': reference_rows[key] = {'ids':ids,'raw':r,'projected':d,'operation':job['id']}
                else:
                    need(key in reference_rows and reference_rows[key]['ids'] == ids, 'complete independent reference counterpart')
                    anchor = load(reference_rows[key]['raw'],[a['roots']['reference']],limits)
                    import numpy as np
                    tol = a['reference_tolerance']
                    need(bool(np.all(np.abs(x-anchor) <= tol['absolute']+tol['relative']*np.abs(anchor))), 'preselected full independent raw numerical agreement')
        elif job['kind'] == 'actor_case':
            expected_actors.add(job['id']); row = records['actors'][job['id']]
            need(row['job'] == job and row['case_state_shared'] is False, 'complete fresh actor case')
            visible = actor_view(a,job,row,prepared,bank,artifacts)
            tools(a,job,row,records)
            candidate(a,job,row,visible,closure,records,artifacts)
            if job['cell']['mode'] == 'I': semantic_method(a,row['method'],'I',job['id'],artifacts)
            fit,pred = row['fit'],row['predict']
            need(fit == records['operations'][fit['operation']] and pred == records['operations'][pred['operation']], 'actor actual operation records')
            result = artifacts.json(Path(pred['output'])/'RESULT.json',pred['native']['artifacts']['RESULT.json'],a['resources']['state_bytes'])
            need(result == row['result'] and result['ids'] == support(table,job['person'],[job['held']])
                 and pred['request_value']['state']['pin'] == fit['native']['artifacts']['STATE.json'], 'actual fitted state and all held rows')
            rawdesc = {**result['raw'],'path':str(Path(pred['output'])/'raw.npy')}
            desc = {**result['projected'],'path':str(Path(pred['output'])/'projected.npy')}
            need(rawdesc['pin'] == pred['native']['artifacts']['raw.npy'] and desc['pin'] == pred['native']['artifacts']['projected.npy'], 'prediction files join original native capture')
            x,y = load(rawdesc,[a['roots']['output']],limits),load(desc,[a['roots']['output']],limits)
            need(x.shape == y.shape == (len(result['ids']),3), 'all three complete candidate endpoint columns')
            for column,endpoint in enumerate(ENDPOINTS): projected(x[:,column],y[:,column],endpoint)
            policy = p['policies'][job['cell']['policy']]
            need(row['policy'] == policy and row['paired_provider_seed_identity'] == [job['cell']['policy'],job['case_id'],'author-01'], 'exact source-only paired policy/seed')
            if job['cell']['mode'] == 'F': need(row['method'] == policy, 'frozen source/recipe unchanged after query')
            else:
                policy_body = artifacts.capture(policy['source']['path'],policy['source']['pin'],131072)
                investigation(a,job,row['method'],closure,records,artifacts,policy=policy_body.decode(),visible=visible,tool=row['tool'])
            candidate_rows[(job['cell']['id'],job['person'],job['held'])] = {'ids':result['ids'],'array':desc,'operation':job['id']}
        elif job['kind'] == 'global_author':
            policy = p['policies'][job['policy']]
            need(policy == phase and policy['source_only'] is True and policy['policy_identity'] == job['policy'], 'exact complete source-only global policy realization')
            semantic_method(a,policy,'I_policy' if job['mode'] == 'I' else 'F',job['id'],artifacts)
            investigation(a,job,policy,closure,records,artifacts)
    need(set(records['references']) == expected_references and set(records['actors']) == expected_actors, 'no extra/missing graph records')
    for (impl,endpoint,view,person,held),value in selections.items():
        if impl == 'r1':
            other = selections[('r2',endpoint,view,person,held)]
            need(value['selected'] == other['selected'] and value['strongest'] == other['strongest'], 'independent exact selected-configuration identity')
    budget.tick()
    return {'producer':p,'closure':closure,'packet':prepared,'table':table,'records':records,
            'candidate_rows':candidate_rows,'reference_rows':reference_rows,'selections':selections,
            'public_output_admission_complete':True,'protected_target_bodies_read':False,'limits':limits}
