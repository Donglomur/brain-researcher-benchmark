"""Independent pre-target selection, authored-policy, fitted-state and tool edge joins."""
from pathlib import Path
from core import need, encoded, pin, parse, relative, canonical, finite
from contracts import CONFIGS, ENDPOINTS, identity, recipe
from reference_adapter import primitive, host_descriptor
from authority import selection_pin


def view_authority(a, selection, artifacts):
    d = selection['selection_authority']; path = canonical(d['root'])/relative(d['body']['path'])
    need(canonical(a['roots']['operator']) in path.parents, 'operator-only view authority')
    q = artifacts.json(path,d['body']['pin'],a['resources']['qualification_bytes'])
    body = {k:v for k,v in selection.items() if k != 'selection_authority'}
    need(q['schema'] == 'neural049_view_authority_v1' and q['status'] == 'selected_qualified_view'
         and q['selection'] == pin(encoded(body)) and q['packet'] == a['packet']
         and q['execution_selection'] == selection_pin(a) and q['issuer'] == a['operator_identity']
         and q['realm'] == 'actual_external_evidence', 'exact external view permission')
    for d in q['evidence']:
        artifacts.capture(Path(a['roots']['operator'])/relative(d['path']),d['pin'],a['resources']['qualification_bytes'],retain=False)


def selection_edges(a, job, produced, records, prepared, bank):
    r = produced['request_value']; days = [x['day'] for x in prepared['manifest']['days']
        if x['person'] == job['person'] and x['day'] != job['outer']]
    need(r['validation_days'] == days and r['held_day'] == job['outer']
         and r['scope'] == {k:job[k] for k in ('implementation','endpoint','view','person','outer')},
         'complete other-day selection, held day excluded')
    rows = []
    for ordinal in CONFIGS:
        for day in days:
            fid = identity(['inner-fit',[job['implementation'],job['endpoint'],job['view'],job['person'],
                                        sorted([job['outer'],day]),ordinal,None if a['cache'] else job['outer']]])
            pid = identity(['inner-predict',fid,job['outer'],day]); p = records['references'][pid]
            rows.append({'configuration':ordinal,'day':day,'ids':p['joined']['tree']['ids'],
                         'projected':primitive(p['joined']['tree']['projected'],job['implementation']),
                         'prediction_operation':pid,'fit_operation':fid})
    need(r['rows'] == rows and set(r['targets']) == {str(x) for x in days}, 'all 25 configurations and all ordered inner consumers')
    mounts = {x['destination']:x for x in produced['mounts']}; allowed_bank = set()
    for day in days:
        original = next(x for x in prepared['manifest']['days'] if x['person'] == job['person'] and x['day'] == day)
        d = original['labels'][job['endpoint']]; target = '/inputs/labels/'+str(day)+'.npy'; expected = {k:d[k] for k in ('bytes','sha256')}
        need(r['targets'][str(day)] == {'ids':original['ids'],'array':{'path':target,'pin':expected,'shape':d['shape'],'dtype':d['dtype']}},
             'only complete selected endpoint labels of other days')
        need(mounts[target]['source'] == bank.source(d['path'],expected) and mounts[target]['pin'] == expected,
             'actual original inner-selection target mount')
        allowed_bank.add(target)
    need({k for k,m in mounts.items() if bank.contains(m['source'])} == allowed_bank, 'no held/extra target capability in selection')
    for row in rows:
        p = records['references'][row['prediction_operation']]['produced']
        d = row['projected']; host = host_descriptor(d,p)
        need(mounts[d['path']]['source'] == host['path'] and mounts[d['path']]['pin'] == d['pin'],
             'inner consumer uses actual finite producer output')


def investigation(a, job, method, closure, records, artifacts, *, policy=None, visible=None, tool=None):
    """Reconstruct source-owned messages/actions, not arbitrary transcript callbacks."""
    from investigator import PROTOCOL
    from actor_context import setup
    source_only = job['kind'] == 'global_author'; mode = job['mode'] if source_only else 'I'
    view_name,tool_on = (job['view'],job['tool']) if source_only else (job['cell']['view'],job['cell']['tool'])
    disclosed = setup(a,view_name,tool_on)
    need(method['source_context'] == pin(encoded(disclosed)), 'actual exact source-only task/software/setting disclosure')
    initial = {'stage':'source_only_policy' if source_only and mode == 'I' else 'source_only_program' if source_only else 'fresh_case_method',
               'view':view_name,'tool_access':tool_on,'source_context':disclosed,
               'policy':policy,'same_complete_batch_access':True}
    messages = [{'role':'system','content':PROTOCOL},{'role':'user','content':encoded(initial).decode()}]
    calls = sorted((ordinal,row) for (episode,ordinal),row in closure['providers'].items() if episode == (job['id'],))
    need(calls, 'actual author/provider sequence'); transcript = []; analyses = []; submitted = False
    for position,(ordinal,row) in enumerate(calls):
        need(not submitted and row['attempt']['request_body']['messages'] == messages, 'exact original source-owned investigation transport')
        response = parse(row['complete']['response_utf8'].encode()); text = response['choices'][0]['message']['content']
        action = row['complete']['action']; transcript.append({'ordinal':position,'response':row['complete']['response'],'text':text})
        messages.append({'role':'assistant','content':text})
        if action['action'] == 'submit':
            need(pin(action['source'].encode()) == method['source']['pin'] and recipe(action['recipe']) == method['recipe']
                 and pin(encoded(action['recipe'])) == method['recipe_descriptor']['pin']
                 and pin(encoded(action['claim'])) == method['claim']['pin'], 'actual provider-authored source/recipe/claim seal')
            submitted = True
        else:
            need(action['action'] == 'python', 'no failed/stop action in complete method')
            op = identity(['analysis',job['id'],position]); produced = records['operations'][op]; req = produced['request_value']
            mounts = {m['destination']:m for m in produced['mounts']}
            need(req['source_only'] is source_only and req['code']['pin'] == pin(action['code'].encode())
                 and mounts['/inputs/ANALYSIS.py']['pin'] == req['code']['pin'], 'actual exact authored analysis source')
            if source_only:
                need(req['view'] is None and req['tool_bank'] is None, 'source-only author has no case/tool values')
                allowed = {'/inputs/REQUEST.json','/inputs/LAUNCH.json','/inputs/LAUNCHER.py','/inputs/ANALYSIS.py'}
                need(all(k in allowed or k.startswith('/inputs/source/') for k in mounts), 'no hidden value mount in global authorship')
            feedback = artifacts.json(Path(produced['output'])/'FEEDBACK.json',produced['native']['artifacts']['FEEDBACK.json'],36864)
            messages.append({'role':'user','content':encoded(feedback).decode()}); analyses.append(produced)
    need(submitted and method['analyses'] == analyses, 'complete exact method-analysis chain')
    actual = artifacts.json(method['transcript']['path'],method['transcript']['pin'],a['resources']['record_bytes'])
    need(actual == transcript, 'original provider response-to-retained transcript')


def state_arrays(value, out=None):
    out = {} if out is None else out
    if type(value) is dict:
        if set(value) == {'__primitive_array__'}:
            d = value['__primitive_array__']; path = str(relative(d['path']))
            need(path.startswith('arrays/') and path not in out, 'unique safe fitted-state array')
            out[path] = d
        else:
            for child in value.values(): state_arrays(child,out)
    elif type(value) is list:
        for child in value: state_arrays(child,out)
    return out


def candidate(a, job, row, visible, closure, records, artifacts):
    fit,pred,method = row['fit'],row['predict'],row['method']; f,q = fit['request_value'],pred['request_value']
    plan = recipe(method['recipe']); scope = {'case':visible['case'],
        'training_ids':[x for p in visible['train_parts'] for x in p['ids']],
        'query_ids':[x for p in visible['query_parts'] for x in p['ids']]}
    need(f['kind'] == 'fit' and q['kind'] == 'predict' and f['scope'] == q['scope'] == scope
         and f['recipe'] == q['recipe'] == plan and f['seed'] == q['seed']
         and f['method'] == q['method'] == {'path':'/inputs/METHOD.py','pin':method['source']['pin']},
         'same original method/recipe/scope/seed across fit and prediction')
    for p in (fit,pred):
        m = next(x for x in p['mounts'] if x['destination'] == '/inputs/METHOD.py')
        need(m['source'] == method['source']['path'] and m['pin'] == method['source']['pin'], 'actual authored method mount')
    sealed = artifacts.json(Path(fit['output'])/'STATE.json',fit['native']['artifacts']['STATE.json'],a['resources']['state_bytes'])
    need(sealed['schema'] == 'neural049_candidate_state_v1' and sealed['method'] == method['source']['pin']
         and sealed['recipe'] == pin(encoded(plan)) and sealed['view'] == f['view']['pin']
         and sealed['scope'] == scope and sealed['seed'] == f['seed'], 'actual complete fitted-state identity')
    members = state_arrays(sealed['state']); need(len(members) <= plan['state_array_cap'], 'safe fitted state member cap')
    need(set(fit['native']['artifacts']) == {'STATE.json','FEATURES.json','WORK.json','RECEIPT.json'}|set(members), 'exact actual fitted state artifact closure')
    mounts = {m['destination']:m for m in pred['mounts']}
    expected = {'STATE.json':fit['native']['artifacts']['STATE.json'],**{k:d['pin'] for k,d in members.items()}}
    need({k for k in mounts if k.startswith('/inputs/state/')} == {'/inputs/state/'+k for k in expected}, 'no alternate or extra fitted state')
    for name,d in expected.items():
        m = mounts['/inputs/state/'+name]
        need(m['source'] == str(Path(fit['output'])/name) and m['pin'] == d == fit['native']['artifacts'][name], 'fit-to-inference actual safe state edge')
    features = artifacts.json(Path(fit['output'])/'FEATURES.json',fit['native']['artifacts']['FEATURES.json'],a['resources']['view_bytes'])
    need(features['state'] == fit['native']['artifacts']['STATE.json'] and set(features['slots']) == {s['name'] for s in plan['provider_slots']}, 'same-state complete typed features')
    replies = {}; expected_calls = set()
    for i,slot in enumerate(plan['provider_slots']):
        rows = features['slots'][slot['name']]; n = 1 if slot['axis'] == 'one' else len(scope['training_ids' if slot['axis'] == 'training' else 'query_ids'])
        need(type(rows) is list and len(rows) == n and all(type(x) is list and len(x) == slot['input_width'] for x in rows), 'all fixed feature rows')
        for r in rows:
            for x in r: finite(x)
        episode = (job['id'],'fixed',i)
        found = [(key,r) for key,r in closure['providers'].items() if key[0] == episode]
        if n == 0:
            need(not found, 'empty fixed slot issues no request'); replies[slot['name']] = []; continue
        need(len(found) == 1, 'one fixed complete numerical response'); key,r = found[0]; expected_calls.add(key)
        messages = [{'role':'system','content':slot['prompt']+' Return only JSON {"values":[finite numbers]} in row-major order.'},
                    {'role':'user','content':encoded({'features':rows,'output_shape':[n,slot['output_width']]}).decode()}]
        need(r['attempt']['request_body']['messages'] == messages, 'fixed source prompt/features exact provider request')
        values = r['complete']['action']['values']; need(len(values) == n*slot['output_width'], 'complete numeric reply rows')
        replies[slot['name']] = [values[k*slot['output_width']:(k+1)*slot['output_width']] for k in range(n)]
    actual_calls = {key for key in closure['providers'] if len(key[0]) > 1 and key[0][0] == job['id']}
    need(actual_calls == expected_calls and replies == row['provider_values'] == q['provider_values'], 'only permitted frozen provider replies enter prediction')


def tools(a, job, row, records):
    if not job['cell']['tool']:
        need(row['tool'] is None, 'no tool in T0/D'); return
    expected = {}; source_paths = {}
    for role,axis in (('train','training'),('query','query')):
        columns = {}; ids = None
        for endpoint in ENDPOINTS:
            op = identity(['tool-bank',job['person'],job['held'],endpoint,axis]); r = records['references'][op]
            tree = r['joined']['tree']; ids = tree['ids'] if ids is None else ids
            need(ids == tree['ids'], 'full common three-endpoint tool support')
            d = host_descriptor(primitive(tree['projected'],'r1'),r['produced'])
            target = '/inputs/tool/'+role+'_'+endpoint+'.npy'; columns[endpoint] = {**d,'path':target}; source_paths[target] = d
        expected[role] = {'ids':ids,'columns':columns,'in_sample':role == 'train'}
    need(row['tool'] == expected, 'actual selected R1 NC tool producer, in-sample lineage explicit')
    analyses = row['method'].get('analyses',[]) if job['cell']['mode'] == 'I' else []
    for produced in (row['fit'],row['predict'],*analyses):
        need(produced['request_value']['tool_bank'] == expected, 'same complete numeric tool access in investigation/fit/infer')
        mounts = {m['destination']:m for m in produced['mounts'] if m['destination'].startswith('/inputs/tool/')}
        need(set(mounts) == set(source_paths), 'only numeric tool columns, no model/reference internals')
        for target,d in source_paths.items():
            need(mounts[target]['source'] == d['path'] and mounts[target]['pin'] == d['pin'], 'actual immutable tool-output mount')
