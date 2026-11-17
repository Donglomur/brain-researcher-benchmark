"""Actual N041 worker/source/mount/capture joins using selected native Engine."""
from pathlib import Path
import hashlib
from core import need,encoded,pin,parse,publish,capture,fresh,descriptor

BASE=('core.py','schema.py','epoch_io.py','actor_api.py','reasoning.py','worker.py')

def mount(path,desc,target):
    descriptor(desc)
    return {'source':str(path),'destination':target,'pin':desc,'bytes_cap':desc['bytes']}

class Transport:
    def __init__(self,selection,source,budget,engine):
        self.selection=selection;self.source=source;self.budget=budget;self.engine=engine
        self.operations=[];self.receipts=[]
    def run(self,cell,stage,view,method,recipe,model=None):
        s=self.selection;b=self.budget;identity=cell['identity']+'/'+stage
        op=hashlib.sha256(identity.encode()).hexdigest();need(op not in self.operations,'unique operation identity');self.operations.append(op)
        root=fresh(Path(s['operations_root'])/op,b);output=fresh(Path(self.engine.selection['output_root'])/op,b)
        selected=BASE+(('reference.py',) if cell['tool']=='decoder' else ())
        source={name:self.source[name] for name in selected};sp=pin(encoded(source));mounts=[]
        for name,desc in source.items():mounts.append(mount(Path(s['source_root'])/name,desc,'/inputs/source/'+name))
        lp=self.source['launcher.py'];mounts.append(mount(Path(s['source_root'])/'launcher.py',lp,'/inputs/launcher.py'))
        public={'schema':'n041_view_v1','training':view['training'] if stage in('fit','investigate') else [],'query':view['query'] if stage=='predict' else [],'regions':view['regions'],'protocol':s['protocol']}
        vp=publish(root/'VIEW.json',encoded(public),b,readonly=True);mounts.append(mount(root/'VIEW.json',vp,'/inputs/VIEW.json'))
        for row in public['training']+public['query']:
            ep=row['epoch'];mounts.append(mount(Path(cell['epoch_root'])/ep['path'],ep['pin'],'/inputs/epochs/'+ep['path']))
        mounts.append(mount(method['path'],method['pin'],'/inputs/METHOD.py'))
        if stage in('fit','investigate'):need(model is None,'no inherited model in fresh training attempt')
        else:
            need(model is not None,'captured fitted state required');mounts.append(mount(model['path'],model['pin'],'/inputs/MODEL.bin'))
        cutoff=min(b.deadline,b.tick()+s['phase_seconds'])
        req={'schema':'n041_worker_v1','operation':op,'stage':stage,'mode':cell['mode'],'tool':cell['tool'],'method':method['pin'],
            'recipe':recipe,'view':vp,'model':None if model is None else model['pin'],'source':sp,'protocol':s['protocol'],
            'origin':b.origin,'deadline':cutoff,'limits':s['worker_limits']}
        req['request_identity']=pin(encoded(req));rp=publish(root/'REQUEST.json',encoded(req),b,readonly=True)
        mounts.append(mount(root/'REQUEST.json',rp,'/inputs/REQUEST.json'))
        cfg={'schema':'n041_launch_v1','origin':b.origin,'deadline':cutoff,'files':source,'request':rp,'source_read_bytes':s['source_read_bytes'],'entry':'worker'}
        cp=publish(root/'LAUNCH.json',encoded(cfg),b,readonly=True);mounts.append(mount(root/'LAUNCH.json',cp,'/inputs/LAUNCH.json'))
        caps={'RECEIPT.json':s['worker_limits']['metadata_bytes']}
        caps.update({'MODEL.bin':s['worker_limits']['model_bytes'],'TRAINING.json':s['worker_limits']['metadata_bytes'],'REASONING.json':s['worker_limits']['metadata_bytes']} if stage=='fit' else
            {'METHOD.py':s['worker_limits']['source_bytes'],'RECIPE.json':s['worker_limits']['metadata_bytes'],'RATIONALE.json':s['worker_limits']['metadata_bytes']} if stage=='investigate' else
            {'PREDICTIONS.json':s['worker_limits']['metadata_bytes']})
        argv=['python','-I','-B','/inputs/launcher.py','/inputs/LAUNCH.json',str(cp['bytes']),cp['sha256'],repr(b.origin),repr(cutoff)]
        native=self.engine.execute(op,argv,mounts,output,s['native_limits'],cutoff,sp,caps)
        raw,_=capture(output/'RECEIPT.json',native['artifacts']['RECEIPT.json'],caps['RECEIPT.json'],b,readonly=True);receipt=parse(raw)
        need(receipt['schema']=='n041_worker_receipt_v1' and receipt['operation']==op and receipt['stage']==stage and receipt['source']==sp
            and receipt['request']==req['request_identity'] and receipt['origin']==b.origin and receipt['deadline']==cutoff
            and receipt['observed_end']<cutoff,'actual worker request/source/clock closure')
        need(receipt['outputs']=={k:v for k,v in native['artifacts'].items() if k!='RECEIPT.json'},'all independently captured outputs join worker')
        result={'cell':cell['identity'],'stage':stage,'native':native,'receipt':receipt,'request':rp,
            'artifacts':{name:{'path':str(output/name),'pin':desc} for name,desc in native['artifacts'].items()}}
        self.receipts.append(result);publish(root/'COMPLETE.json',encoded(result),b,readonly=True)
        return result

def prepare_native(selection,source,budget,engine):
    """Full evaluator capsule, before actor views. Private mount namespace only.

    The exact output plan is made by an independently reviewed cohort/clinical
    producer before execution. It is not fabricated from declared 44/36 counts.
    Absent or inconsistent source/clinical/output plans are admission failures.
    """
    s=selection;p=s['preparation'];b=budget;op='neural041-full-preparation'
    folder=fresh(Path(s['operations_root'])/'preparation',b);output=fresh(Path(engine.selection['output_root'])/'preparation',b)
    names=('core.py','schema.py','roster.py','nwb.py','preparation.py','preparation_worker.py')
    files={n:source[n] for n in names};sp=pin(encoded(files));mounts=[mount(Path(s['source_root'])/n,d,'/inputs/source/'+n) for n,d in files.items()]
    mounts.append(mount(Path(s['source_root'])/'launcher.py',source['launcher.py'],'/inputs/launcher.py'))
    inputs={}
    for name in('ROSTER.json','REVIEW.json','IDENTITY.key'):
        d=p['inputs'][name];inputs[name]=d['pin'];mounts.append(mount(d['path'],d['pin'],'/inputs/'+name))
    from roster import declared,LOCK
    need(inputs['ROSTER.json']==LOCK,'exact retained source roster, no substitute cohort')
    raw,_=capture(p['inputs']['ROSTER.json']['path'],LOCK,LOCK['bytes'],b,readonly=True)
    original=declared(raw)
    need(len(p['assets'])==44,'complete declared source slot plan')
    need({(d['relative'],d['pin']['bytes'],d['pin']['sha256']) for d in p['assets']}=={(d['path'],d['bytes'],d['sha256']) for d in original},'exact full declared asset mount set, no extras or omissions')
    for d in p['assets']:
        from core import relative
        relative(d['relative']);mounts.append(mount(d['path'],d['pin'],'/inputs/raw/'+d['relative']))
    cutoff=min(b.deadline,b.tick()+p['phase_seconds'])
    req={'schema':'n041_preparation_request_v1','operation':op,'origin':b.origin,'deadline':cutoff,'source':sp,'inputs':inputs,
        'limits':p['worker_limits'],'preparation_limits':p['limits']}
    req['request_identity']=pin(encoded(req));rp=publish(folder/'REQUEST.json',encoded(req),b,readonly=True);mounts.append(mount(folder/'REQUEST.json',rp,'/inputs/REQUEST.json'))
    cfg={'schema':'n041_launch_v1','origin':b.origin,'deadline':cutoff,'files':files,'request':rp,'source_read_bytes':s['source_read_bytes'],'entry':'preparation_worker'}
    cp=publish(folder/'LAUNCH.json',encoded(cfg),b,readonly=True);mounts.append(mount(folder/'LAUNCH.json',cp,'/inputs/LAUNCH.json'))
    caps=dict(p['output_plan']);need('prepared/PRIVATE.json' in caps and all(n=='prepared/PRIVATE.json' or n.startswith('prepared/epochs/') for n in caps),'fixed private output plan')
    caps['RECEIPT.json']=p['worker_limits']['metadata_bytes']
    argv=['python','-I','-B','/inputs/launcher.py','/inputs/LAUNCH.json',str(cp['bytes']),cp['sha256'],repr(b.origin),repr(cutoff)]
    native=engine.execute(op,argv,mounts,output,p['native_limits'],cutoff,sp,caps)
    raw,_=capture(output/'RECEIPT.json',native['artifacts']['RECEIPT.json'],caps['RECEIPT.json'],b,readonly=True);receipt=parse(raw)
    need(receipt['schema']=='n041_preparation_receipt_v1' and receipt['operation']==op and receipt['request']==req['request_identity'] and receipt['source']==sp,'actual preparation producer/source/request join')
    need(receipt['outputs']=={k:v for k,v in native['artifacts'].items() if k!='RECEIPT.json'},'complete private output capture')
    need(receipt['origin']==b.origin and receipt['deadline']==cutoff and receipt['observed_end']<cutoff,'full preparation clock')
    result={'path':str(output/'prepared/PRIVATE.json'),'pin':native['artifacts']['prepared/PRIVATE.json']}
    return result,str(output/'prepared/epochs'),{'native':native,'receipt':receipt}
