"""Future operator-only lossless original-HDF5 projection, never runtime staging.

Original source_rows contains query labels. This preparation may read that
explicitly pinned operator operand; none of it is mounted by the runtime.
This function is dormant and needs separate actual preparation authority and an
outer process observer. HDF5 internal physical I/O is not measured by this code.
"""
import hashlib, hmac, json, math, os, stat, time
from pathlib import Path

def need(ok,message):
    if not ok:raise ValueError(message)

def encoded(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def pin(body):return dict(bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
def ordinary(path):
    p=Path(path).absolute();need(not any(q.is_symlink() for q in (p,*p.parents)) and '..' not in p.parts,'ordinary owned path');return p
def stamp(p):
    s=p.stat();need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'ordinary singlelink file')
    return tuple(getattr(s,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))

class Meter:
    def __init__(self,limits,origin,deadline):
        need(type(origin)in(int,float) and type(deadline)in(int,float) and math.isfinite(origin) and math.isfinite(deadline) and 0<=origin<=time.monotonic()<deadline,'one actual root clock')
        need(set(limits)=={'reads','writes','retained'} and all(type(v)is int and v>0 for v in limits.values()),'explicit projection allowance')
        self.limits=limits;self.reads=0;self.writes=0;self.origin=origin;self.deadline=deadline
    def tick(self):need(time.monotonic()<self.deadline,'original projection deadline')
    def read(self,n):self.tick();need(type(n)is int and n>=0 and self.reads+n<=self.limits['reads'],'logical read allowance');self.reads+=n
    def write(self,n):self.tick();need(type(n)is int and n>=0 and self.writes+n<=self.limits['writes'],'logical write allowance');self.writes+=n

def read_json(p,expected,cap,meter):
    p=ordinary(p);s=stamp(p);need(0<s[2]<=cap and s[2]==expected['bytes'],'complete pinned metadata')
    meter.read(s[2]+1)
    with p.open('rb') as f:b=f.read(s[2]+1)
    need(pin(b)==expected and stamp(p)==s,'stable pinned metadata')
    def pairs(items):
        out={}
        for k,v in items:need(k not in out,'duplicate metadata key');out[k]=v
        return out
    return json.loads(b,object_pairs_hook=pairs,parse_constant=lambda _:need(False,'nonfinite metadata'))

def hash_file(p,expected,meter):
    p=ordinary(p);s=stamp(p);need(s[2]==expected['bytes'],'full source extent');meter.read(s[2]+1);h=hashlib.sha256();n=0
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):meter.tick();h.update(block);n+=len(block);need(n<=s[2],'stable source extent')
    need(n==s[2] and h.hexdigest()==expected['sha256'] and stamp(p)==s,'full source pin');return s

def write_bytes(p,body,meter):
    meter.write(len(body))
    with p.open('xb') as f:f.write(body);f.flush();os.fsync(f.fileno())
    p.chmod(0o444);return pin(body)

def npy_header(n):
    b=repr({'descr':'<f4','fortran_order':False,'shape':(n,306,125)}).encode('ascii');b+=b' '*((-10-len(b)-1)%64)+b'\n'
    return b'\x93NUMPY\x01\x00'+len(b).to_bytes(2,'little')+b

def source_join(lock,inputs,provenance,panel):
    """Operator-only join; output bindings contain no query labels."""
    need(lock.get('task_id')=='NEURAL-089' and lock.get('edition')=='2025-phoneme' and len(lock['runs'])==90,'full original edition')
    need(inputs.get('task_id')=='NEURAL-089' and len(inputs['runs'])==len(provenance['runs'])==90,'full prepared source rows')
    expected={tuple(r['run_key']):r for r in lock['runs']};need(len(expected)==90,'90 original keys')
    keys=[tuple(r['run_key']) for r in provenance['runs']];need(keys==[tuple(r['run_key']) for r in lock['runs']],'exact original keyset/order')
    seen=set();query=[];bindings=[]
    for original,view,prov in zip(lock['runs'],inputs['runs'],provenance['runs']):
        need(prov['source_sha256']==original['recording']['sha256'] and view['partition']==original['split'],'exact original run source/split')
        records=prov['records'];ids=[r['query_id'] for r in records]
        need(len(records)==view['windows']>0 and ids==sorted(ids) and len(set(ids))==len(ids) and not seen.intersection(ids),'full sorted source rows')
        need(all(set(r)=={'query_id','label','source_row0'} and type(r['label'])is int and 0<=r['label']<39 and type(r['source_row0'])is int and r['source_row0']>=0 for r in records),'original full event rows')
        need(len({r['source_row0'] for r in records})==len(records) and prov['accounting']['target_rows']==len(records),'complete source event accounting')
        seen.update(ids)
        if view['partition']=='query':query=ids
        bindings.append(dict(group_id=view['group_id'],run_key=original['run_key'],source_recording=original['recording'],source_events=original['events'],windows=len(records),source_event_identity_sha256=hashlib.sha256(encoded([{'query_id':r['query_id'],'source_row0':r['source_row0']} for r in records])).hexdigest()))
    need(panel=={'schema_version':1,'task_id':'NEURAL-089','query_ids':query} and 0<len(query)<=200000 and len(seen)<=2000000,'complete original heldrun panel')
    need(sum(r['split']=='train' for r in lock['runs'])==88 and sum(r['split']=='validation' for r in lock['runs'])==1 and sum(r['split']=='query' for r in lock['runs'])==1,'native88/1/1')
    return bindings

ORIGINAL_LOCK_PIN={'bytes': 91873, 'sha256': '23489ecda2cfb13fcb425593fa9370f64e4188c8aca7f5c9d79bb4343e0ddcba'}

def project(selection):
    """Never called automatically; authentic preparation remains separately unqualified."""
    import h5py
    import numpy as np
    need(np.__version__=='2.2.6' and h5py.__version__=='3.13.0','pinned future numerical environment')
    keys={'schema','selected_by_root','source_lock','original_inputs','original_panel','original_provenance','original_normalization','original_preparation','original_public_root','output','private_output','permutation_seed','limits','origin_monotonic','deadline_monotonic','original_lock_pin'}
    need(type(selection)is dict and set(selection)==keys and selection['schema']=='neural089-projection-selection-v1' and selection['selected_by_root']is True,'separate exact projection selection')
    s=selection;need(s['original_lock_pin']==ORIGINAL_LOCK_PIN,'exact frozen original90 source lock, not a replacement manifest');m=Meter(s['limits'],s['origin_monotonic'],s['deadline_monotonic'])
    loaded={}
    for key in ('source_lock','original_inputs','original_panel','original_provenance','original_normalization','original_preparation'):
        desc=s[key];need(set(desc)=={'path','bytes','sha256'},'exact original metadata operand')
        loaded[key]=read_json(desc['path'],{k:desc[k] for k in ('bytes','sha256')},256_000_000,m)
    lock=loaded['source_lock'];need({k:s['source_lock'][k] for k in ('bytes','sha256')}==s['original_lock_pin'],'fixed original90 source lock')
    prep=loaded['original_preparation'];need(prep['task_id']=='NEURAL-089' and prep['lock_sha256']==s['original_lock_pin']['sha256'] and prep['panel']=={k:s['original_panel'][k] for k in ('bytes','sha256')},'original preparation source/panel binding')
    norm=loaded['original_normalization'];need(norm['training_runs']==88 and norm['validation_or_query_statistics_used']is False and len(norm['mean'])==len(norm['population_std'])==306 and all(math.isfinite(x) for x in norm['mean']) and all(math.isfinite(x) and x>0 for x in norm['population_std']),'original training-only normalization')
    inputs=loaded['original_inputs'];prov=loaded['original_provenance'];panel=loaded['original_panel'];bindings=source_join(lock,inputs,prov,panel)
    out=ordinary(s['output']);priv=ordinary(s['private_output']);original=ordinary(s['original_public_root'])
    need(not out.exists() and not priv.exists() and out!=priv and not out.is_relative_to(priv) and not priv.is_relative_to(out) and not out.is_relative_to(original) and not original.is_relative_to(out) and not priv.is_relative_to(original) and not original.is_relative_to(priv),'fresh disjoint output trees')
    seeddesc=s['permutation_seed'];seedpath=ordinary(seeddesc['path']);need(seeddesc['bytes']==32 and stamp(seedpath)[2]==32,'private32byte permutation seed')
    m.read(33)
    with seedpath.open('rb') as f:seed=f.read(33)
    need(pin(seed)=={k:seeddesc[k] for k in ('bytes','sha256')},'exact private permutation seed')
    total=sum(r['windows'] for r in inputs['runs']);need(total*153000+total*40+20_000_000<=s['limits']['retained'],'prospective full output allowance')
    for d in (out,priv):d.mkdir(mode=0o700)
    for d in (out/'arrays',out/'labels',priv/'permutations'):d.mkdir(mode=0o700)
    publicrows=[];permutations=[];counts=np.zeros(39,dtype=np.int64)
    for row,records,binding in zip(inputs['runs'],[r['records'] for r in prov['runs']],bindings):
        m.tick();need(type(row['path'])is str and '/' not in row['path'] and '\\' not in row['path'],'ordinary original prepared basename')
        src=original/row['path'];before=hash_file(src,{k:row[k] for k in ('bytes','sha256')},m);n=row['windows'];alias=row['group_id']
        need(type(alias)is str and len(alias)==24 and all(q in '0123456789abcdef' for q in alias),'opaque original alias')
        path=out/'arrays'/f'{alias}.npy';head=npy_header(n);h=hashlib.sha256(head);m.write(len(head))
        with h5py.File(src,'r') as source,path.open('xb') as target:
            labeled=row['partition']!='query';need(set(source)==({'windows','ids','labels'} if labeled else {'windows','ids'}),'original query has no labels')
            x=source['windows'];ids=source['ids'];need(x.shape==(n,306,125) and x.dtype==np.dtype('<f4') and ids.shape==(n,) and ids.dtype==np.dtype('S24'),'original complete window geometry')
            m.read(n*24);actualids=[v.decode('ascii') for v in ids[:]];need(actualids==[r['query_id'] for r in records],'all original opaque rows aligned')
            target.write(head)
            for start in range(0,n,128):
                size=min(128,n-start)*153000;m.read(size);a=x[start:start+128];need(np.isfinite(a).all() and (np.abs(a)<=10).all(),'full finite prepared values')
                body=a.tobytes(order='C');need(len(body)==size,'exact normalized float32 bytes');m.write(size);target.write(body);h.update(body)
            target.flush();os.fsync(target.fileno())
            new=dict(partition=row['partition'],group_id=alias,windows=n,ids=actualids,features=dict(path='arrays/'+alias+'.npy',bytes=len(head)+n*153000,sha256=h.hexdigest(),offset=len(head)))
            if labeled:
                y=source['labels'];need(y.shape==(n,) and y.dtype==np.dtype('<i2'),'original int16 labels');m.read(n*2);labels=y[:]
                need(labels.tolist()==[r['label'] for r in records],'same permitted original labels')
                if row['partition']=='train':counts+=np.bincount(labels,minlength=39)
                permseed=int.from_bytes(hmac.new(seed,alias.encode(),hashlib.sha256).digest()[:8],'little');order=np.random.default_rng(permseed).permutation(n).astype('<u4')
                perm=labels[order];need(np.array_equal(np.bincount(labels,minlength=39),np.bincount(perm,minlength=39)),'within-run counts preserved')
                for kind,body,name in [('labels',labels.tobytes(),alias+'.bin'),('permuted_labels',perm.tobytes(),alias+'-permuted.bin')]:new[kind]=dict(path='labels/'+name,**write_bytes(out/'labels'/name,body,m))
                pp=write_bytes(priv/'permutations'/f'{alias}.bin',order.tobytes(),m);permutations.append(dict(group_id=alias,rows=n,path='permutations/'+alias+'.bin',**pp))
        need(stamp(src)==before,'original prepared file stable');path.chmod(0o444);publicrows.append(new)
    private=write_bytes(priv/'PERMUTATIONS.json',encoded(dict(schema='neural089-private-permutation-v1',seed_pin={k:seeddesc[k] for k in ('bytes','sha256')},numpy='2.2.6',rows=permutations)),m)
    receipt=dict(schema='neural089-label-free-projection-v1',original_source_lock=s['original_lock_pin'],original_metadata={k:{j:s[k][j] for j in ('bytes','sha256')} for k in loaded if k!='source_lock'},full_run_count=90,full_event_count=total,query_count=len(panel['query_ids']),query_labels_in_output=False,run_bindings=bindings,permutation_binding=private,source_method_qualified=False)
    rp=write_bytes(out/'PROJECTION.json',encoded(receipt),m)
    public=dict(schema='neural089-program-panel-v1',generation=hashlib.sha256(encoded(dict(rows=publicrows,projection=rp))).hexdigest(),original_source_lock=s['original_lock_pin'],runs=publicrows,prior_counts=counts.tolist(),projection_receipt=rp)
    pp=write_bytes(out/'PUBLIC.json',encoded(public),m)
    actual=sum(p.stat().st_size for root in (out,priv) for p in root.rglob('*') if p.is_file());need(actual+100000<=s['limits']['retained'],'actual full output logical extent')
    closure=dict(schema='neural089-projection-closure-v1',public_manifest=pp,projection=rp,private_permutation_binding=private,managed_read_bytes=m.reads,managed_write_bytes=m.writes,retained_logical_bytes=actual,hdf5_internal_physical_IO_measured=False,original_origin=s['origin_monotonic'],elapsed_before_closure=time.monotonic()-s['origin_monotonic'],scientific_qualified=False,runtime_qualified=False,outer_admission_required=True)
    write_bytes(priv/'CLOSURE.json',encoded(closure),m)
    for root in (out,priv):
        for d in sorted([p for p in root.rglob('*') if p.is_dir()],reverse=True)+[root]:
            d.chmod(0o555);fd=os.open(d,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd);m.tick()
    return closure
