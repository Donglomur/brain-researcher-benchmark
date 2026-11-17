"""Complete90-run metadata, streaming views and fixed full pointwise schedule."""
import ast, hashlib, math, os, re, stat, struct

JSON_CAP=64_000_000
OUTPUT_CAP=1_100_000_000
ARRAY_CAP=306_000_001_024
NEURAL_CAP=306_000_100_000
MODEL_CAP=268_435_456
PRED_CAP=32768
NATIVE_CAP=262144
PANELS=('candidate','independent_reference')
ARMS=('MEG','ZERO_MEG','PERMUTED_LABELS','PRIOR')
PLAN_FIELDS={'cases','query_count','training_count','development_count','total_feature_bytes','fit_feature_bytes','query_feature_bytes','label_bytes','fit_files','query_files'}
WINDOW_BYTES=306*125*4

def admit(public):
    c.need(type(public)is dict and set(public)=={'schema','generation','original_source_lock','runs','prior_counts','projection_receipt'} and public['schema']=='neural089-program-panel-v1','exact label-free complete panel')
    c.need(type(public['generation'])is str and re.fullmatch('[0-9a-f]{64}',public['generation']),'generation')
    c.need(public['original_source_lock']==science.ORIGINAL_LOCK_PIN,'exact original90 source identity');c.exact_pin(public['projection_receipt'])
    c.need(public['generation']==hashlib.sha256(c.encoded(dict(rows=public['runs'],projection=public['projection_receipt']))).hexdigest(),'exact full projection generation')
    rows=public['runs'];c.need(type(rows)is list and len(rows)==90,'all90 runs')
    aliases=set();seen=set();totals={'train':0,'validation':0,'query':0};counts=dict(totals);full=0;fitbytes=0;querybytes=0;labelbytes=0;queries=[];fit=[]
    for row in rows:
        role=row.get('partition');c.need(role in counts,'original partition')
        fields={'partition','group_id','ids','features','windows'}|({'labels','permuted_labels'} if role!='query' else set())
        c.need(type(row)is dict and set(row)==fields,'no original run identity/timing/target in query metadata')
        alias=row['group_id'];c.need(type(alias)is str and re.fullmatch('[0-9a-f]{24}',alias) and alias not in aliases,'unique opaque run')
        aliases.add(alias);n=row['windows'];c.need(type(n)is int and 1<=n<=2_000_000,'full nonempty run')
        ids=row['ids'];c.need(type(ids)is list and len(ids)==n and ids==sorted(ids) and len(set(ids))==n and all(type(q)is str and re.fullmatch('[0-9a-f]{24}',q) and q not in seen for q in ids),'original sorted unique opaque IDs')
        seen.update(ids);counts[role]+=1;totals[role]+=n
        pin=row['features'];c.need(type(pin)is dict and set(pin)=={'path','bytes','sha256','offset'} and pin['path']=='arrays/'+alias+'.npy' and type(pin['offset'])is int and 10<=pin['offset']<=4096 and pin['bytes']==pin['offset']+n*WINDOW_BYTES,'complete little-float32 array extent')
        c.only_pin(pin);full+=pin['bytes']
        if role=='query':
            querybytes+=pin['bytes'];queries=[dict(id=q,row=i,run=row) for i,q in enumerate(ids)]
        else:
            fit.append(row);fitbytes+=pin['bytes']
            for kind in ('labels','permuted_labels'):
                p=row[kind];c.need(type(p)is dict and set(p)=={'path','bytes','sha256'} and p['path']=='labels/'+alias+('-permuted.bin' if kind=='permuted_labels' else '.bin') and p['bytes']==2*n,'complete fixedint16 labels')
                c.only_pin(p);labelbytes+=p['bytes']
    c.need(counts=={'train':88,'validation':1,'query':1} and len(seen)<=2_000_000 and 0<totals['query']<=200_000,'complete original88/1/1 and full retained bounds')
    c.need(full<=NEURAL_CAP,'full projection byte ceiling; never truncate')
    prior=public['prior_counts'];c.need(type(prior)is list and len(prior)==39 and all(type(v)is int and v>=0 for v in prior) and sum(prior)==totals['train'],'alltraining counts only')
    # Preserve manifest run order: the reference uses exactly this original order.
    return dict(cases=len(seen),query_count=totals['query'],training_count=totals['train'],development_count=totals['validation'],total_feature_bytes=full,fit_feature_bytes=fitbytes,query_feature_bytes=querybytes,label_bytes=labelbytes,fit_files=89,query_files=1,fit=fit,queries=queries,query_by_id={r['id']:r for r in queries})

def phases(public,plan=None):
    p=admit(public) if plan is None else plan;i=0
    for panel in PANELS:
        for arm in ('MEG','PERMUTED_LABELS','PRIOR'):
            yield dict(panel=panel,kind='fit',arm=arm,case_id=None,model_key=None,result_key=panel+'/'+arm,ordinal=i,phase_id=f'phase-{i:07d}');i+=1
        for arm in ARMS:
            model=panel+('/MEG' if arm=='ZERO_MEG' else '/'+arm)
            ids=[None] if arm=='PRIOR' else [r['id'] for r in p['queries']]
            for q in ids:
                yield dict(panel=panel,kind='infer',arm=arm,case_id=q,model_key=model,result_key=None,ordinal=i,phase_id=f'phase-{i:07d}');i+=1
    c.need(i==6*p['query_count']+8,'full two-panel phase count')

def limits(p,times):
    c.need(set(times)=={'fit','infer'} and all(type(v)is int and 0<v<=31_536_000 for v in times.values()),'explicit prospective phase times')
    c.need(set(p)==PLAN_FIELDS and all(type(v)is int and v>0 for v in p.values()),'exact complete scalar plan')
    q=p['query_count'];n=6*q+8;models=6
    view=p['fit_feature_bytes']+p['label_bytes']//2+JSON_CAP
    metadata=6*OUTPUT_CAP+12*JSON_CAP+n*(NATIVE_CAP+PRED_CAP+65536+3*8192)
    retained=view+models*MODEL_CAP+metadata+4096*(12*n+1000)
    work=4*p['fit_feature_bytes']+2*p['label_bytes']+6*q*(WINDOW_BYTES+128)
    reads=3*work+2*p['total_feature_bytes']+12*MODEL_CAP+6*500_000_000+(6*q+2)*16_000_000+4*metadata+64_000_000
    writes=2*work+12*MODEL_CAP+2*metadata+64_000_000
    observer_reads=4*metadata+12*MODEL_CAP+64_000_000
    observer_seconds=600+(observer_reads+999999)//1_000_000
    whole=600+6*times['fit']+(6*q+2)*times['infer']+150*n+observer_seconds
    return dict(retained=retained,reads=reads,writes=writes,observer_reads=observer_reads,observer_seconds=observer_seconds,whole_seconds=whole,max_entries=12*n+1000,phase_count=n,query_count=q,total_managed_reads=reads+observer_reads+4_000_000,native_model_mount_bytes_upper=(6*q+2)*MODEL_CAP,native_input_mount_bytes_upper=work)

def header(raw,shape):
    c.need(raw[:8]==b'\x93NUMPY\x01\x00' and len(raw)>=10,'fixed simple NPYv1')
    size=int.from_bytes(raw[8:10],'little');c.need(0<size<=4086 and len(raw)==size+10,'bounded complete header')
    value=ast.literal_eval(raw[10:].decode('latin1'))
    c.need(type(value)is dict and value=={'descr':'<f4','fortran_order':False,'shape':shape} and value['fortran_order']is False and type(value['shape'])is tuple and all(type(x)is int for x in value['shape']),'exact C-order littlefloat32 shape')

def source_files(public):
    out={}
    for row in public['runs']:
        for k in ('features','labels','permuted_labels'):
            if k in row:out[row[k]['path']]=c.only_pin(row[k])
    return out

def stream_copy(source,target,pin,budget,header_shape=None,offset=None):
    """Whole-file authentication and bounded copy, no giant source read."""
    source=c.path(source);target=c.path(target);budget.tick()
    fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);out=None
    try:
        initial=os.fstat(fd);c.need(stat.S_ISREG(initial.st_mode) and initial.st_nlink==1 and initial.st_size==pin['bytes'],'exact full source extent')
        budget.read(initial.st_size+1);budget.write(initial.st_size)
        out=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400);h=hashlib.sha256();total=0
        while True:
            budget.tick();block=os.read(fd, min(1048576,initial.st_size+1-total))
            if not block:break
            c.need(total+len(block)<=initial.st_size,'no growing source')
            if total==0 and header_shape is not None:header(block[:offset],header_shape)
            h.update(block);total+=len(block);view=memoryview(block)
            while view:budget.tick();n=os.write(out,view);c.need(n>0,'whole stream copy');view=view[n:]
        c.need(total==initial.st_size and h.hexdigest()==pin['sha256'] and c.stamp(initial)==c.stamp(os.fstat(fd))==c.stamp(source.lstat()),'unchanged authenticated source')
        budget.tick();os.fsync(out);os.fchmod(out,0o444);os.fsync(out);budget.tick()
    finally:
        os.close(fd)
        if out is not None:os.close(out)
    c.sync_dir(target.parent,budget.tick);return c.only_pin(pin)

def query_bytes(source,row,index,zero,budget):
    p=row['features'];source=c.path(source);fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);c.need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_size==p['bytes'],'whole source query extent')
        budget.read(p['offset']+WINDOW_BYTES);raw=os.pread(fd,p['offset'],0);header(raw,(row['windows'],306,125))
        values=os.pread(fd,WINDOW_BYTES,p['offset']+index*WINDOW_BYTES)
        c.need(len(values)==WINDOW_BYTES and all(math.isfinite(x[0]) and -10<=x[0]<=10 for x in struct.iter_unpack('<f',values)),'complete finite original query')
        c.need(c.stamp(a)==c.stamp(os.fstat(fd))==c.stamp(source.lstat()),'source unchanged through extent read')
    finally:os.close(fd)
    h=npy_header((306,125));return h+(bytes(WINDOW_BYTES) if zero else values)

def npy_header(shape):
    text=repr({'descr':'<f4','fortran_order':False,'shape':shape}).encode('ascii');pad=(-10-len(text)-1)%64;body=text+b' '*pad+b'\n'
    return b'\x93NUMPY\x01\x00'+len(body).to_bytes(2,'little')+body

def view(root,source_root,public,phase,budget,plan=None):
    p=admit(public) if plan is None else plan;c.need(not root.exists(),'fresh single view');budget.capacity(32768)
    root.mkdir(mode=0o700);(root/'arrays').mkdir(mode=0o700);(root/'labels').mkdir(mode=0o700)
    expected={};req={'schema':'neural089-program-input-v1'}
    if phase['kind']=='fit' and phase['arm']=='PRIOR':req.update(mode='fit_prior',counts=public['prior_counts'])
    elif phase['kind']=='fit':
        req.update(mode='fit_neural',runs=[])
        for row in p['fit']:
            f=row['features'];expected[f['path']]=stream_copy(source_root/f['path'],root/f['path'],f,budget,(row['windows'],306,125),f['offset'])
            lp=row['permuted_labels' if phase['arm']=='PERMUTED_LABELS' else 'labels'];name='labels/'+row['group_id']+'.bin'
            expected[name]=stream_copy(source_root/lp['path'],root/name,lp,budget)
            req['runs'].append(dict(partition=row['partition'],group_id=row['group_id'],windows=row['windows'],ids=row['ids'],features=dict(path=f['path'],**expected[f['path']]),labels=dict(path=name,**expected[name])))
    elif phase['arm']=='PRIOR':req.update(mode='infer_prior')
    else:
        row=p['query_by_id'][phase['case_id']];body=query_bytes(source_root/row['run']['features']['path'],row['run'],row['row'],phase['arm']=='ZERO_MEG',budget)
        expected['arrays/query.npy']=c.save(root/'arrays/query.npy',body,WINDOW_BYTES+4096,budget.tick,budget.write);c.readable(root/'arrays/query.npy',budget.tick)
        req.update(mode='infer_neural',query_id=row['id'],features=dict(path='arrays/query.npy',**expected['arrays/query.npy']))
    expected['INPUT.json']=c.save(root/'INPUT.json',c.encoded(req),JSON_CAP,budget.tick,budget.write);c.readable(root/'INPUT.json',budget.tick)
    for d in (root/'arrays',root/'labels',root):os.chmod(d,0o555);c.sync_dir(d,budget.tick)
    return expected

def verify_view(root,expected,budget):
    files,dirs,_=c.inventory(root,budget.limits['retained'],1000)
    c.need(set(files)==set(expected) and {d.relative_to(root).as_posix() for d in dirs}=={'.','arrays','labels'},'exact restricted view')
    for name,(_,s) in files.items():c.need(s[4]==expected[name]['bytes'] and stat.S_IMODE(s[2])==0o444,'read-only regular view')
    c.need(all(stat.S_IMODE(d.lstat().st_mode)==0o555 for d in dirs),'read-only dirs');budget.tick()
    return {name:s for name,(_,s) in files.items()}

def retire(root,expected,stamps,budget):
    c.need(verify_view(root,expected,budget)==stamps,'view unchanged')
    for d in (root,root/'arrays',root/'labels'):os.chmod(d,0o700)
    for name in expected:budget.tick();(root/name).unlink()
    (root/'arrays').rmdir();(root/'labels').rmdir();root.rmdir();c.sync_dir(root.parent,budget.tick)
    c.need(not os.path.lexists(root),'retired before following exposure')
