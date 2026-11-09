"""Concrete minimal source views and actual immutable-ID worker execution."""
from pathlib import Path
import hashlib
from core import need,encoded,pin,parse,publish,fresh,integer,relative
from artifacts import worker_mount
from worker_common import recipe

BASE=('core','contracts','artifacts','views','numeric_io','worker_common')
ENTRIES={'candidate':'candidate_worker','candidate_features':'candidate_worker','analysis':'analysis_worker',
         'reference_person':'reference_worker','reference_group':'reference_worker','aggregate':'aggregate_worker'}
class Transport:
    def __init__(self,a,captured,budget,record,public,private,artifacts,private_artifacts):
        self.a=a;self.captured=captured;self.b=budget;self.record=record;self.engines={False:public,True:private}
        self.art={False:artifacts,True:private_artifacts};self.operations=[]
    def source(self,worker,tool,reference=None):
        names=set(BASE)|{ENTRIES[worker]};names|={'journal'}if worker.startswith('reference_')else set()
        if tool=='T1':names.add('pac_tool')
        files={name+'.py':self.captured['manifest']['files']['program/'+name+'.py']for name in sorted(names)}
        originals={name+'.py':'program/'+name+'.py'for name in sorted(names)}
        if reference:
            prefix='references/'+reference.lower()+'/'
            for name,desc in self.captured['manifest']['files'].items():
                if name.startswith(prefix)and name.endswith('.py'):files[name]=desc;originals[name]=name
        return files,originals
    def invoke(self,identity,worker,profile,cutoff,*,case=None,method=None,tool='T0',provider_values=None,reference=None,person_results=None,people=None,world=None):
        a=self.a;r=a['resources'];private=worker.startswith('reference_');eng=self.engines[private];art=self.art[private]
        operation=hashlib.sha256(identity.encode()).hexdigest();need(operation not in self.operations,'unique actual operation')
        self.operations.append(operation);limits=a['phase_limits'][profile];cutoff=min(cutoff,self.b.tick(cutoff)+limits['cpu_ns']/limits['cpu_rate_ns'])
        root=Path(a['roots']['private']if private else a['roots']['output'])/'operations';folder=fresh(root/operation,self.b)
        output=fresh(Path(eng.selection['output_root'])/operation,self.b)
        files,originals=self.source(worker,tool,reference);source_pin=pin(encoded(files));mounts=[]
        for name,orig in originals.items():mounts.append(worker_mount(Path(a['roots']['source'])/orig,files[name],'/inputs/source/'+name))
        launcher='program/sandbox_launcher.py';launch_pin=self.captured['manifest']['files'][launcher]
        mounts.append(worker_mount(Path(a['roots']['source'])/launcher,launch_pin,'/inputs/launcher.py'))
        if case:mounts.extend(case['mounts'])
        if method:mounts.append(worker_mount(method['source']['path'],method['source']['pin'],'/inputs/method.py'))
        if person_results:
            for item in person_results:mounts.append(worker_mount(item['path'],item['pin'],'/inputs/people/'+item['person']+'.json'))
        caps={'RECEIPT.json':r['operation_bytes']}
        if worker=='candidate':caps['RESULT.json']=r['candidate_report_bytes']
        elif worker=='candidate_features':caps['FEATURES.json']=limits['response_bytes']
        elif worker=='analysis':caps['FEEDBACK.json']=limits['analysis_bytes']
        elif worker=='aggregate':caps['REPORT.json']=r['candidate_report_bytes']
        elif worker=='reference_person':caps.update({'RESULT.json':r['reference_report_bytes'],'PERSON_EVENT.json':r['reference_event_bytes'],'EVIDENCE.jsonl':r['reference_journal_bytes']})
        else:caps.update({'REPORT.json':r['reference_report_bytes'],'EVIDENCE.jsonl':r['reference_journal_bytes']})
        seed_identity=identity.rsplit('/',1)[0]if worker in('candidate','candidate_features')else identity
        seed_material=['neural042-case-rng-v2',seed_identity,None if method is None else method['source']['pin']]
        phase_seed=int.from_bytes(hashlib.sha256(encoded(seed_material)).digest()[:4],'big')
        req={'schema':'neural042_worker_request_v1','worker':worker,'operation':operation,'source_manifest':source_pin,
             'original_origin':self.b.origin,'deadline':cutoff,'read_bytes':r['host_read_bytes'],'write_bytes':sum(caps.values())+65536,
             'seed':phase_seed,'seed_identity':seed_identity,'rng_contract':'python_random_and_numpy_legacy_global_explicit_seed_v2','tool':tool,
             'case':None if case is None else {k:case[k]for k in('world','person','pin')},
             'limits':{'metadata_bytes':r['view_metadata_bytes'],'metadata_live_bytes':4<<20,'array_bytes':r['channel_bytes'],'case_live_bytes':limits['memory_bytes']},
             'method':None if method is None else {'source':method['source']['pin'],'recipe':method['recipe']['pin'],'admission':method.get('admission')},
             'recipe':{'provider_slots':{}}if method is None else method['recipe_value'],'provider_values':provider_values or {},
             'source_bytes':r['candidate_source_bytes'],'tool_elements':r['reference_elements'],'output_caps':caps,
             'feedback_bytes':limits['analysis_bytes'],'reference':reference,'person_results':person_results,'people':people,'world':world,
             'event_bytes':r['reference_event_bytes'],'planned_group_live_bytes':20<<20,
             'reference_limits':{k:r['reference_'+k]for k in('elements','work_units','serialized_bytes','events','live_bytes')},
             'lineage':None if case is None else {'packet':case['pin'],'source':self.captured['pin'],
                'environment':pin(encoded({'image':eng.selection['image_id'],'clock_domain':eng.selection['clock_domain']})),
                'reference_source':pin(encoded({k:v for k,v in files.items()if k.startswith('references/')}))if private else(method['source']['pin']if method is not None else source_pin),
                'protocol':a['preparation']['protocol']}}
        raw=encoded(req);need(len(raw)<=r['operation_bytes'],'full bounded actual request');rp=publish(folder/'REQUEST.json',raw,self.b,readonly=True)
        mounts.append(worker_mount(folder/'REQUEST.json',rp,'/inputs/REQUEST.json'))
        config={'schema':'neural042_sandbox_v1','clock_domain':eng.selection['clock_domain'],'original_origin':self.b.origin,
                'deadline':cutoff,'files':files,'source_manifest':source_pin,'source_read_bytes':r['source_bytes'],
                'entry':ENTRIES[worker],'request':rp}
        lp=publish(folder/'LAUNCH.json',encoded(config),self.b,readonly=True);mounts.append(worker_mount(folder/'LAUNCH.json',lp,'/inputs/LAUNCH.json'))
        argv=['python','-I','-B','/inputs/launcher.py','/inputs/LAUNCH.json',str(lp['bytes']),lp['sha256'],repr(self.b.origin),repr(cutoff)]
        # Request, launcher and every input/source are physically individual readonly binds.
        result=eng.execute(operation,argv,mounts,output,limits,cutoff,source_pin,caps)
        receipt=art.json(output/'RECEIPT.json',result['artifacts']['RECEIPT.json'],r['operation_bytes'])
        need(receipt['operation']==operation and receipt['request']==rp and receipt['worker']==worker
             and receipt['source_manifest']==source_pin and receipt['original_origin']==self.b.origin
             and receipt['deadline']==cutoff and receipt['observed_end']<cutoff,'actual worker request/source/clock closure')
        need(receipt['rng']=={'seed':req['seed'],'identity':req['seed_identity'],'contract':req['rng_contract']},'actual initialized RNG request join')
        need(receipt['outputs']=={k:v for k,v in result['artifacts'].items()if k!='RECEIPT.json'},'all output pins independently join')
        row={'identity':identity,'operation':operation,'worker':worker,'request':{'path':str(folder/'REQUEST.json'),'pin':rp},
             'launch':{'path':str(folder/'LAUNCH.json'),'pin':lp},'source':source_pin,'native':result,
             'receipt':{'path':str(output/'RECEIPT.json'),'pin':result['artifacts']['RECEIPT.json']},'role':'private'if private else'public'}
        desc=publish(folder/'OPERATION.json',encoded(row),self.b,readonly=True);row['descriptor']={'path':str(folder/'OPERATION.json'),'pin':desc}
        self.record({'kind':'operation_consumed','identity':identity,'operation':operation,'descriptor':row['descriptor'],'worker':worker})
        return row
    def result(self,row,name):
        return {'path':row['native']['output']+'/'+name,'pin':row['native']['artifacts'][name]}
    def json(self,row,name):
        d=self.result(row,name);return self.art[row['role']=='private'].json(d['path'],d['pin'],self.a['resources']['reference_report_bytes']if row['role']=='private'else self.a['resources']['candidate_report_bytes'])
