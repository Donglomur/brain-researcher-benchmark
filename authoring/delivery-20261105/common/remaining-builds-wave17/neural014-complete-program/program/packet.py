"""Full45 sanitized packet and one-phase views. No gold or original inputs opened."""
import ast,hashlib,io,os,re,stat,struct,math
from pathlib import Path

JSON_CAP=64_000_000
ARRAY_CAP=409_601_024
NEURAL_CAP=12_000_000_000
MODEL_CAP=268_435_456
PRED_CAP=32768
NATIVE_CAP=262144
PANELS=('candidate','independent_reference')
NEURAL_ARMS=('full_fixed','full_adapt','loss_fixed','loss_adapt','shuffle_adapt','zero_adapt')
PLAN_FIELDS={'cases','query_count','total_feature_bytes','fit_feature_bytes','calibration_feature_bytes','query_feature_bytes','max_feature_bytes','max_calibration_feature_bytes','permutation_bytes','max_permutation_bytes'}

def sessions():
    return [{'session_id':f'session-{i:03d}','role':'train' if i<=27 else 'development' if i<=36 else 'query'} for i in range(1,46)]

def project_pool(pool,permutation_pins):
    """Operator-only metadata projection after original preparation; no array read.

    The original validation is inherited. This is not proof of its native lineage.
    A future separate input admission must verify source priority and no refill.
    """
    science.validate_pool(pool)
    rows=[]
    for r in pool['rows']:
        row={k:r[k] for k in ('id','session','role','steps','features')}
        if r['role']!='query':row['tokens']=science.normalize_tokens(r['tokens'])
        else:row['permutation']=permutation_pins[r['id']]
        rows.append(row)
    c.need(set(permutation_pins)=={r['id'] for r in rows if r['role']=='query'},'all and only query permutations')
    out=dict(schema='neural014-program-panel-v1',generation=pool['generation'],sessions=sessions(),rows=rows)
    admit(out)
    return out

def admit(public):
    c.need(type(public)is dict and set(public)=={'schema','generation','sessions','rows'} and public['schema']=='neural014-program-panel-v1','exact sanitized complete panel')
    c.need(type(public['generation'])is str and re.fullmatch('[a-f0-9]{64}',public['generation']),'exact generation')
    c.need(public['sessions']==sessions(),'all45 chronological session aliases')
    rows=public['rows'];c.need(type(rows)is list and 0<len(rows)<=50000,'full bounded retained roster')
    seen=set();support={};total=0;fit=[];cal=[];queries=[]
    roles={s['session_id']:s['role'] for s in sessions()}
    for r in rows:
        c.need(type(r)is dict and set(r)==({'id','session','role','steps','features','permutation'} if r.get('role')=='query' else {'id','session','role','steps','features','tokens'}),'no transcript, target, ordinal or lineage in query/predictor row')
        c.need(type(r['id'])is str and re.fullmatch('[a-f0-9]{64}',r['id']) and r['id'] not in seen,'unique opaque row')
        c.need(r['session'] in roles and r['role'] in (('calibration','query') if roles[r['session']]=='query' else (roles[r['session']],)),'exact chronological role')
        c.need(type(r['steps'])is int and 0<r['steps']<=100000,'complete bounded time extent')
        p=r['features'];c.need(type(p)is dict and set(p)=={'path','bytes','sha256'} and p['path']=='arrays/'+r['id']+'.npy','exact primitive array identity')
        c.only_pin(p);c.need(0<p['bytes']<=ARRAY_CAP,'full array size bound')
        total+=p['bytes'];c.need(total<=NEURAL_CAP,'original prepared full-array bound; no subsampling')
        seen.add(r['id']);support[(r['session'],r['role'])]=support.get((r['session'],r['role']),0)+1
        if r['role']!='query':c.need(bool(science.normalize_tokens(r['tokens'])),'complete nonempty allowed labels')
        else:
            pp=r['permutation'];c.need(type(pp)is dict and set(pp)=={'path','bytes','sha256'} and pp['path']=='permutations/'+r['id']+'.bin' and pp['bytes']==12+4*r['steps'],'full exact permutation index extent')
            c.only_pin(pp)
        (queries if r['role']=='query' else cal if r['role']=='calibration' else fit).append(r)
    for s in sessions():
        for role in (('calibration','query') if s['role']=='query' else (s['role'],)):
            c.need(support.get((s['session_id'],role),0)>0,'every45 session/role retained')
        if s['role']=='query':c.need(support[(s['session_id'],'calibration')]<=20,'no refilled calibration')
    return dict(cases=len(rows),query_count=len(queries),total_feature_bytes=total,
        fit_feature_bytes=sum(r['features']['bytes'] for r in fit),calibration_feature_bytes=sum(r['features']['bytes'] for r in cal),
        query_feature_bytes=sum(r['features']['bytes'] for r in queries),max_feature_bytes=max(r['features']['bytes'] for r in rows),permutation_bytes=sum(r['permutation']['bytes'] for r in queries),max_permutation_bytes=max(r['permutation']['bytes'] for r in queries),
        max_calibration_feature_bytes=max(sum(r['features']['bytes'] for r in cal if r['session']==f'session-{i:03}') for i in range(37,46)),
        fit=sorted(fit,key=lambda r:r['id']),calibration=sorted(cal,key=lambda r:r['id']),queries=sorted(queries,key=lambda r:(r['session'],r['id'])),
        query_by_id={r['id']:r for r in queries},calibration_by_session={f'session-{i:03}':sorted([r for r in cal if r['session']==f'session-{i:03}'],key=lambda r:r['id']) for i in range(37,46)},
        training_tokens=[{'role':'train','tokens':r['tokens']} for r in sorted(fit,key=lambda r:r['id']) if r['role']=='train'])

def suite(public):
    p=admit(public);contexts=[]
    for i in range(37,46):
        s=f'session-{i:03}';ids=sorted(r['id'] for r in p['queries'] if r['session']==s)
        for arm in science.ARMS:contexts.append(dict(session=s,arm=arm,query_ids=ids,context_id=science.context_id(public['generation'],s,arm,ids)))
    return dict(schema='neural014-suite-v1',generation=public['generation'],contexts=contexts)

def phases(public,plan=None):
    """Private schedule; treatment labels never enter candidate-facing metadata."""
    p=admit(public) if plan is None else plan;out=[]
    for panel in PANELS:
        out.append(dict(panel=panel,kind='fit',session=None,treatment=None,arm=None,case_id=None,model_key=None,result_key=panel+'/base'))
        for i in range(37,46):
            session=f'session-{i:03}'
            for treatment in ('full','loss'):
                out.append(dict(panel=panel,kind='adapt',session=session,treatment=treatment,arm=None,case_id=None,model_key=panel+'/base',result_key=panel+'/'+session+'/'+treatment))
            out.append(dict(panel=panel,kind='prior',session=session,treatment=None,arm='language_prior',case_id=None,model_key=None,result_key=None))
            for arm in NEURAL_ARMS:
                key=panel+'/base' if arm.endswith('_fixed') else panel+'/'+session+('/loss' if arm=='loss_adapt' else '/full')
                for r in p['queries']:
                    if r['session']==session:out.append(dict(panel=panel,kind='infer',session=session,treatment=None,arm=arm,case_id=r['id'],model_key=key,result_key=None))
    c.need(len(out)==56+12*p['query_count'],'complete phase schedule')
    return [dict(x,ordinal=i,phase_id=f'phase-{i:07d}') for i,x in enumerate(out)]

def request(public,phase,plan=None):
    """Strict model-side fields only; prior has no IDs, durations or features."""
    p=admit(public) if plan is None else plan;kind=phase['kind'];session=phase['session']
    if kind=='fit':rows=p['fit']
    elif kind=='adapt':rows=p['calibration_by_session'][session]
    elif kind=='infer':rows=[{k:v for k,v in p['query_by_id'][phase['case_id']].items() if k!='permutation'}]
    elif kind=='prior':rows=p['training_tokens']+[{'role':'calibration','tokens':r['tokens']} for r in p['calibration_by_session'][session]]
    else:raise ValueError('unknown phase')
    return dict(schema='neural014-program-input-v1',mode=kind,generation=public['generation'],rows=rows)

def limits(p,times):
    c.need(set(times)=={'fit','adapt','infer','prior'} and all(type(v)is int and 0<v<=31_536_000 for v in times.values()),'operator-selected finite seconds; no default runtime claim')
    c.need(set(p)==PLAN_FIELDS and all(type(v)is int and v>0 for v in p.values()),'exact full support scalar plan')
    q=p['query_count'];n=56+12*q;model_count=38
    # Complete retained models, every raw/native/request/seal and final answers.
    # One view at a time; transforms allocate at most one complete original trial.
    view=max(p['fit_feature_bytes'],p['max_calibration_feature_bytes'],p['max_feature_bytes'])
    metadata=16*JSON_CAP+n*(NATIVE_CAP+PRED_CAP+65536+3*8192)
    allocation=4096*(p['cases']+12*n+300)
    retained=view+model_count*MODEL_CAP+metadata+allocation+64_000_000
    feature_work=2*p['fit_feature_bytes']+4*p['calibration_feature_bytes']+12*p['query_feature_bytes']
    # Includes initial/final manifests, repeated input identity capture, model
    # readbacks, bounded Docker responses and observer. No retirement refunds.
    reads=3*feature_work+4*p['permutation_bytes']+6*model_count*MODEL_CAP+38*500_000_000+(18+12*q)*16_000_000+4*metadata+64_000_000
    writes=2*feature_work+2*model_count*MODEL_CAP+2*metadata+64_000_000
    observer_reads=4*metadata+2*model_count*MODEL_CAP+64_000_000
    observer_seconds=600+(observer_reads+999999)//1000000
    whole_seconds=600+2*times['fit']+36*times['adapt']+18*times['prior']+12*q*times['infer']+150*n+observer_seconds
    return dict(retained=retained,reads=reads,writes=writes,observer_reads=observer_reads,observer_seconds=observer_seconds,whole_seconds=whole_seconds,max_entries=p['cases']+12*n+300,phase_count=n,query_count=q,total_managed_reads=reads+observer_reads+4_000_000)

def npy(raw,steps):
    c.need(type(raw)is bytes and 0<len(raw)<=ARRAY_CAP and raw[:6]==b'\x93NUMPY','complete primitive feature')
    version=raw[6:8];c.need(version in (b'\x01\x00',b'\x02\x00'),'original NPY version')
    width=2 if version==b'\x01\x00' else 4;off=8+width;size=int.from_bytes(raw[8:off],'little')
    c.need(0<size<=4096 and len(raw)>=off+size,'bounded NPY header')
    d=ast.literal_eval(raw[off:off+size].decode('latin1'))
    c.need(type(d)is dict and set(d)=={'descr','fortran_order','shape'} and d['fortran_order']is False and type(d['shape'])is tuple and all(type(x)is int for x in d['shape']) and d['shape']==(steps,512),'unchanged complete time by512')
    c.need(d['descr'] in ('<f4','>f4','<f8','>f8') and len(raw)==off+size+steps*512*int(d['descr'][-1]),'complete floating allocation')
    return d,off+size

def permutation(raw,steps):
    c.need(type(raw)is bytes and len(raw)==12+4*steps and raw[:8]==b'N014P1\0\0' and int.from_bytes(raw[8:12],'little')==steps,'exact prepared permutation geometry')
    values=[n[0] for n in struct.iter_unpack('<I',raw[12:])]
    c.need(len(set(values))==steps and all(0<=i<steps for i in values),'complete query row bijection')
    return values

def transform(raw,row,phase,permutation_raw=None):
    """Exact original raw-value perturbation; no normalization or target access."""
    d,off=npy(raw,row['steps']);item=int(d['descr'][-1]);width=512*item
    c.need(all(math.isfinite(x[0]) for x in struct.iter_unpack(d['descr'][0]+('f' if item==4 else 'd'),memoryview(raw)[off:])),'finite whole source feature; no imputation')
    loss=phase['treatment']=='loss' or phase['arm'] in ('loss_fixed','loss_adapt')
    if loss:
        y=bytearray(raw[off:])
        for t in range(row['steps']):
            for col in science.LOSS_COLUMNS:y[t*width+col*item:t*width+(col+1)*item]=b'\0'*item
        body=bytes(y)
    elif phase['arm']=='zero_adapt':body=b'\0'*(len(raw)-off)
    elif phase['arm']=='shuffle_adapt':
        indices=permutation(permutation_raw,row['steps'])
        body=b''.join(raw[off+i*width:off+(i+1)*width] for i in indices)
    else:return raw
    # Retain source NPY header and original float endian/shape, change only
    # declared raw values. Native original np.save may normalize header bytes;
    # scientific identity is exact feature values/order, not new header parity.
    out=raw[:off]+body
    c.need(len(out)==len(raw),'unchanged full array extent');return out

def view(root,source_root,public,phase,budget,plan=None):
    root=c.path(root);source_root=c.path(source_root);c.need(not root.exists(),'fresh single phase view')
    budget.capacity(32768);root.mkdir(mode=0o700);(root/'arrays').mkdir(mode=0o700)
    req=request(public,phase,plan);expected={};output_rows=[]
    for original in req['rows']:
        row=dict(original)
        if phase['kind']!='prior':
            p=row['features'];raw=c.capture(source_root/p['path'],ARRAY_CAP,c.only_pin(p),budget.tick,budget.read)
            index=None
            if phase['arm']=='shuffle_adapt':
                pp=(admit(public) if plan is None else plan)['query_by_id'][row['id']]['permutation']
                index=c.capture(source_root/pp['path'],400012,c.only_pin(pp),budget.tick,budget.read)
            raw=transform(raw,row,phase,index);pin=c.save(root/p['path'],raw,ARRAY_CAP,budget.tick,budget.write);c.readable(root/p['path'],budget.tick)
            expected[p['path']]=pin;row['features']=dict(pin,path=p['path'])
        output_rows.append(row)
    req=dict(req,rows=output_rows);raw=c.encoded(req);expected['INPUT.json']=c.save(root/'INPUT.json',raw,JSON_CAP,budget.tick,budget.write);c.readable(root/'INPUT.json',budget.tick)
    os.chmod(root/'arrays',0o555);os.chmod(root,0o555);c.sync_dir(root,budget.tick)
    return expected

def verify_view(root,expected,budget):
    files,dirs,_=c.inventory(root,budget.limits['retained'],50010)
    c.need(set(files)==set(expected) and {d.relative_to(root).as_posix() for d in dirs}=={'.','arrays'},'exact restricted phase tree')
    for name,(_,stamp) in files.items():c.need(stamp[4]==expected[name]['bytes'] and stat.S_IMODE(stamp[2])==0o444,'readonly ordinary view')
    c.need(all(stat.S_IMODE(d.lstat().st_mode)==0o555 for d in dirs),'readonly view directories');budget.tick()
    return {name:stamp for name,(_,stamp) in files.items()}

def retire(root,expected,stamps,budget):
    c.need(verify_view(root,expected,budget)==stamps,'view unchanged through exposure')
    os.chmod(root,0o700);os.chmod(root/'arrays',0o700)
    for name in expected:budget.tick();(root/name).unlink()
    (root/'arrays').rmdir();root.rmdir();c.sync_dir(root.parent,budget.tick)
    c.need(not os.path.lexists(root),'view retired')
