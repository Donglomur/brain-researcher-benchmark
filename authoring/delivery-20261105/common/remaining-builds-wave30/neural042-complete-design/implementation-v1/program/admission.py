"""All public/schema/native metadata admission precedes private numerical targets."""
from pathlib import Path
import hashlib
from core import need,capture,parse,pin,encoded,canonical,descriptor
from contracts import projection,report,CELLS
from schedule import schedule,cell_id
from artifacts import Artifacts
from journal_audit import audit
from transport import Transport

class Capture:
    def __init__(self,a,b):self.a=a;self.b=b
    def exact(self,path,expected_path,desc,cap):
        need(canonical(path)==canonical(expected_path),'fixed source-owned operand path before capture')
        return parse(capture(path,desc,cap,self.b,readonly=True)[0])

def admit(a,captured,producer_descriptor,b):
    r=a['resources'];root=Path(a['roots']['output']);priv=Path(a['roots']['private']);c=Capture(a,b)
    producer=c.exact(producer_descriptor['path'],root/'PRODUCER.json',producer_descriptor['pin'],r['producer_bytes'])
    need(producer['schema']=='neural042_full_producer_v1'and producer['source']==captured['pin']and producer['authority']==captured['authority_pin']
         and producer['projection']==a['projection']and producer['original_origin']==a['clock']['origin'],'exact full source/authority/input closure')
    proj=projection(c.exact(Path(a['roots']['packet'])/'PROJECTION.json',Path(a['roots']['packet'])/'PROJECTION.json',a['projection'],r['projection_bytes']))
    need(producer['people']==proj['people'],'complete prepared roster')
    jp=producer['journal'];need(canonical(jp['path'])==root/'JOURNAL.jsonl','fixed nonprivate journal before body')
    raw=capture(jp['path'],jp['pin'],r['journal_bytes'],b,readonly=True)[0];joined=audit(raw,producer,a)
    plan=schedule(proj['people']);need(set(producer['phases'])=={p['identity']for p in plan},'complete planned phases')
    seen={};requests={};expected_targets={};expected_reports={};methods={}
    # Meta-only private files have fixed distinct names. No REPORT, RESULT or
    # EVIDENCE private body can be selected through these capture routes.
    fake=Transport.__new__(Transport);fake.captured=captured
    for row in producer['operations']:
        op=row['operation'];role=row['role'];need(role in('public','private'),'source-owned role')
        parent=root if role=='public'else priv;folder=parent/'operations'/op;out=Path(a['native_'+role]['output_root'])/op
        stored=c.exact(row['descriptor']['path'],folder/'OPERATION.json',row['descriptor']['pin'],r['operation_bytes'])
        need(stored=={k:v for k,v in row.items()if k!='descriptor'},'actual operation envelope')
        req=c.exact(row['request']['path'],folder/'REQUEST.json',row['request']['pin'],r['operation_bytes'])
        launch=c.exact(row['launch']['path'],folder/'LAUNCH.json',row['launch']['pin'],r['operation_bytes'])
        worker=req['worker'];need(row['worker']==worker and (role=='private')==worker.startswith('reference_'),'reference privilege determined by worker')
        files,originals=fake.source(worker,req['tool'],req['reference']);need(launch['files']==files and row['source']==pin(encoded(files))==req['source_manifest']==launch['source_manifest'],'exact full role source closure')
        receipt=c.exact(row['receipt']['path'],out/'RECEIPT.json',row['receipt']['pin'],r['operation_bytes'])
        native=row['native'];intent=joined['events']['native'][op]['intent']
        need(native['output']==str(out)and receipt['outputs']=={k:v for k,v in native['artifacts'].items()if k!='RECEIPT.json'}and native['artifacts']['RECEIPT.json']==row['receipt']['pin'],'exact independent output pins')
        need(receipt['operation']==req['operation']==op and receipt['request']==row['request']['pin']and launch['request']==row['request']['pin']
             and receipt['source_manifest']==row['source']and receipt['worker']==worker,'request/source/worker receipt joins')
        seed_identity=row['identity'].rsplit('/',1)[0]if worker in('candidate','candidate_features')else row['identity']
        seed_material=['neural042-case-rng-v2',seed_identity,None if req['method']is None else req['method']['source']]
        expected_seed=int.from_bytes(hashlib.sha256(encoded(seed_material)).digest()[:4],'big')
        need(req['seed']==expected_seed and type(req['seed'])is int and req['seed_identity']==seed_identity
             and req['rng_contract']=='python_random_and_numpy_legacy_global_explicit_seed_v2'
             and receipt['rng']=={'seed':req['seed'],'identity':seed_identity,'contract':req['rng_contract']},'exact stable per-method/case seed and explicit RNG engines')
        need(receipt['original_origin']==req['original_origin']==launch['original_origin']==a['clock']['origin']
             and receipt['deadline']==req['deadline']==launch['deadline']==intent['cutoff']
             and receipt['observed_end']<receipt['deadline'],'all original phase clocks')
        expected_mounts={('/inputs/source/'+name,str(Path(a['roots']['source'])/originals[name])):desc for name,desc in files.items()}
        expected_mounts[('/inputs/launcher.py',str(Path(a['roots']['source'])/'program/sandbox_launcher.py'))]=captured['manifest']['files']['program/sandbox_launcher.py']
        expected_mounts[('/inputs/REQUEST.json',str(folder/'REQUEST.json'))]=row['request']['pin'];expected_mounts[('/inputs/LAUNCH.json',str(folder/'LAUNCH.json'))]=row['launch']['pin']
        if req['case']:
            case=req['case'];vr=next(v for v in proj['views']if(v['world'],v['person'])==(case['world'],case['person']));need(case['pin']==vr['pin'],'exact complete case input')
            path=Path(a['roots']['packet'])/vr['path'];from views import admit_view
            view=admit_view(c.exact(path,path,vr['pin'],r['view_metadata_bytes']),case['world'],case['person'])
            sessions=sorted(x['id']for x in proj['sessions']if x['person']==case['person'])
            channels=sorted(ch for x in proj['sessions']if x['person']==case['person']for ch in x['eligible_channels'])
            need(view['sessions']==sessions and [x['id']for x in view['channels']]==channels
                 and view['source']==proj['source']and view['protocol']==proj['protocol']and view['preparation']==proj['preparation'],
                 'all prepared sessions/channels and source lineage retained')
            expected_mounts[('/inputs/case/VIEW.json',str(path))]=vr['pin']
            expected_mounts.update({('/inputs/case/'+name,str(path.parent/name)):desc for name,desc in view['files'].items()})
        if req['method']:
            # Method source path is fixed by the entered phase's admitted record;
            # analysis sources are separately committed by their actual mount.
            candidates=[m for m in intent['mounts']if m['destination']=='/inputs/method.py'];need(len(candidates)==1,'one authored source')
            m=candidates[0];need(canonical(m['source']).parent==root/'methods'and m['pin']==req['method']['source'],'fixed public method namespace')
            expected_mounts[('/inputs/method.py',m['source'])]=m['pin']
        for person in req['person_results']or[]:
            need(person['person']in proj['people'],'same full people inputs')
            expected_mounts[('/inputs/people/'+person['person']+'.json',person['path'])]=person['pin']
        need(len(intent['mounts'])==len(expected_mounts)and {(m['destination'],m['source']):m['pin']for m in intent['mounts']}==expected_mounts,'no extra public/private capabilities or source files')
        seen[op]=row;requests[op]=req
    def output(op,name):
        row=seen[op];return {'path':row['native']['output']+'/'+name,'pin':row['native']['artifacts'][name]}
    def method_join(method,identity,mode):
        need(method['identity']==identity and method['mode']==mode,'exact author/method identity')
        name=pin(identity.encode())['sha256'];folder=root/'methods'
        sd=method['source'];need(canonical(sd['path'])==folder/(name+'.py'),'fixed authored source name')
        capture(sd['path'],sd['pin'],r['candidate_source_bytes'],b,retain=False,readonly=True)
        recipe=c.exact(method['recipe']['path'],folder/(name+'.recipe.json'),method['recipe']['pin'],r['candidate_recipe_bytes'])
        claim=c.exact(method['claim']['path'],folder/(name+'.claim.json'),method['claim']['pin'],32768)
        need(recipe==method['recipe_value'],'same immutable frozen recipe')
        from authority import method as recheck_method
        actual=recheck_method(a,identity,sd['pin'],method['recipe']['pin'],method['claim']['pin'],mode,b,b.deadline)
        need(actual==method['admission'],'same separately issued actual method admission')
        episode=joined['events']['episodes'][identity];need(episode['method']==method,'actual completed author episode/method')
        submissions=[x['complete']['action']for key,x in joined['events']['providers'].items()if key[0]==(identity,)and x['complete']['action'].get('action')=='submit']
        need(len(submissions)==1 and pin(submissions[0]['source'].encode())==sd['pin']
             and submissions[0]['recipe']==recipe and submissions[0]['claim']==claim,'actual provider source/recipe/claim submission lineage')
    for phase in plan:
        ident=phase['identity'];row=producer['phases'][ident];need(row['phase']==phase,'exact phase metadata');ops=row['operations'];kind=phase['kind'];v=row['value']
        for op in ops:
            req_child=requests[op];need(seen[op]['identity'].startswith(ident+'/'),'child operation identity belongs to exact phase')
            if kind=='author':need(req_child['worker']=='analysis'and req_child['case']is None,'data-free authorship has no case operand')
            elif kind=='case':
                mode,world,tool=phase['cell'];need(req_child['worker']in(('candidate','candidate_features')if mode=='F'else('candidate','candidate_features','analysis'))
                     and req_child['case']=={'person':phase['person'],'world':world,'pin':next(v['pin']for v in proj['views']if v['person']==phase['person']and v['world']==world)}and req_child['tool']==tool,
                     'every analysis/feature/solve uses only this mode/person/world/tool')
        if kind=='author':
            method_join(v['method'],ident,phase['mode']);methods[(phase['mode'],phase['tool'])]=v['method'];continue
        need(ops,'actual complete numerical operation, not callback')
        last=ops[-1];req=requests[last]
        if kind=='case':
            mode,world,tool=phase['cell'];need(req['worker']=='candidate'and req['case']['person']==phase['person']and req['case']['world']==world and req['tool']==tool,'exact actor condition')
            method=v['method'];need(req['method']['source']==method['source']['pin']and req['method']['recipe']==method['recipe']['pin']and req['recipe']==method['recipe_value'],'actual executed authored method')
            if mode=='F':need(method==methods[(mode,tool)],'one frozen F method across all cases/worlds')
            else:method_join(method,ident,mode)
            for child in ops:
                rq=requests[child]
                if rq['worker']=='candidate_features':need(rq['method']==req['method']and rq['case']==req['case']and rq['seed']==req['seed']and rq['lineage']==req['lineage'],'identical frozen method/case/declared RNG in preliminary and final workers')
            need(method['admission']is not None and req['method']['admission']==method['admission'],'actual independent method declaration')
            need({k:v['result'][k]for k in('path','pin')}==output(last,'RESULT.json'),'case result native edge')
        elif kind=='reference':
            need(req['worker']=='reference_person'and req['reference']==phase['reference']and req['case']['person']==phase['person']and req['case']['world']==phase['world'],'all independent O/D reference persons')
            need({k:v['person_event'][k]for k in('path','pin')}==output(last,'PERSON_EVENT.json'),'private event producer edge')
        else:
            need(req['people']==proj['people'],'all36 complete aggregation inputs')
            if kind=='group':
                cell=cell_id(phase['cell']);expected=[producer['phases']['case/'+cell+'/'+p]['value']['result']for p in proj['people']]
                need(req['worker']=='aggregate'and req['person_results']==expected and v['report']==output(last,'REPORT.json'),'source-owned full report composition')
                expected_reports[cell]=v['report']
            else:
                ref,w=phase['reference'],phase['world'];expected=[producer['phases']['reference/'+ref+'/'+w+'/'+p]['value']['person_event']for p in proj['people']]
                need(req['worker']=='reference_group'and req['reference']==ref and req['world']==w and req['person_results']==expected and v['target']==output(last,'REPORT.json'),'complete independent reference graph')
                expected_targets[ref+'/'+w]=v['target']
    need(producer['reports']==expected_reports and producer['reference_targets']==expected_targets,'complete exact8reports/fourtargets')
    reports={}
    for key,d in expected_reports.items():reports[key]=report(c.exact(d['path'],d['path'],d['pin'],r['candidate_report_bytes']),proj['people'])
    b.tick();return {'producer':producer,'projection':proj,'reports':reports,'targets':expected_targets,'closure':joined}
