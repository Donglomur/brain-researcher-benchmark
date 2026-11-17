"""Native all-unit TS1 adapter derived from pinned NEURAL060 preparation source.

No scientific dependency is imported until explicitly selected preparation.
"""
import hashlib
import hmac
import math

SPLITS = ('train', 'val', 'test')
CONTRASTS = (-1., -.25, -.125, -.0625, 0., .0625, .125, .25, 1.)
np = h5py = None
TICK = None


def libraries(tick):
    global np, h5py, TICK
    import numpy as numpy_module
    import h5py as h5py_module
    np, h5py, TICK = numpy_module, h5py_module, tick


def need(ok, msg):
    if TICK is not None: TICK()
    if not ok: raise ValueError(msg)

def text(x): return x.decode() if isinstance(x, bytes) else str(x)

def source_identity(stream, spec):
    """Authenticate exact S3 multipart content and compute a local SHA256."""
    h = hashlib.sha256(); parts=[]; n=0
    while True:
        block=stream.read(8*1024**2)
        if not block: break
        n+=len(block);h.update(block);parts.append(hashlib.md5(block).digest())
    etag=hashlib.md5(b''.join(parts)).hexdigest()+'-'+str(len(parts))
    need(n==spec['bytes'] and etag==spec['etag'].strip('"'),'Exact selected S3 size/multipart ETag mismatch')
    sha=h.hexdigest()
    if spec.get('inherited_sha256') is not None:
        need(sha==spec['inherited_sha256'],'Inherited original SHA256 mismatch')
    stream.seek(0)
    return sha

def dataset(f,path):
    for i in range(1,len(path.split('/'))+1):
        need(isinstance(f.get('/'.join(path.split('/')[:i]),getlink=True),h5py.HardLink),'Hard-linked native source fields only')
    d=f[path];need(isinstance(d,h5py.Dataset),'Expected dataset:'+path)
    need(not d.is_virtual and not d.external,'No virtual/external native storage')
    return d

def intervals(f,path):
    a=np.asarray(dataset(f,path+'/start')[()],float);b=np.asarray(dataset(f,path+'/end')[()],float)
    need(a.ndim==1 and a.shape==b.shape and len(a)>0 and np.isfinite(a).all() and np.isfinite(b).all() and (b>a).all(),'Valid domains')
    need(all(b[i]<=a[i+1] for i in range(len(a)-1)),'Sorted disjoint domains')
    return list(zip(a.tolist(),b.tolist()))

def contains(domains,start,end):
    return [i for i,(a,b) in enumerate(domains) if a<=start and end<=b]

def lower_bound(ds,value):
    lo,hi=0,len(ds)
    while lo<hi:
        mid=(lo+hi)//2
        if float(ds[mid])<value:lo=mid+1
        else:hi=mid
    return lo

def stimulus(row):
    left,right=row['contrast_left'],row['contrast_right']
    need(math.isnan(left)!=math.isnan(right),'Exactly one absent stimulus side')
    shown=right if math.isnan(left) else left
    side=0 if math.isnan(left) else 1
    need(math.isfinite(shown) and shown in (0.,.0625,.125,.25,1.),'Source contrast magnitude')
    need(row['stimulus_side']==side and row['stimulus_contrast']==(0.,.0625,.125,.25,1.).index(shown),'Source stimulus code join')
    signed=0. if shown==0 else shown if side==1 else -shown
    probability=row['probability_left'];need(probability in (.2,.5,.8),'Source block probability')
    index=(.2,.5,.8).index(probability);need(row['block_prior']==(0,-1,1)[index],'Source block code join')
    return [float(x==signed) for x in CONTRASTS]+[float(i==index) for i in range(3)]

def metadata_rows(f,spec):
    need(text(group(f,'session').attrs['id'])==spec['eid'] and text(group(f,'subject').attrs['id'])==spec['subject'],'Native session/animal identity')
    need(text(group(f,'brainset').attrs['id'])=='ibl_brain_wide_bench_2026' and text(group(f,'brainset').attrs['unit_filtering'])=='all_units','Exact all-unit build')
    units=len(dataset(f,'units/id'));need(units>0,'Nonempty declared unit axis')
    domain={s:intervals(f,'ts1_'+s+'_domain') for s in SPLITS}
    all_domains=[(s,i,a,b) for s,rows in domain.items() for i,(a,b) in enumerate(rows)]
    need(all(min(a[3],b[3])<=max(a[2],b[2]) for j,a in enumerate(all_domains) for b in all_domains[j+1:]),'Official domains overlap')
    wheel_domain=intervals(f,'wheel/domain');spike_domain=intervals(f,'spikes/domain')
    need(len(wheel_domain)==1 and float(group(f,'wheel').attrs['sampling_rate'])==50.,'Native50Hz regular wheel clock')
    speed=dataset(f,'wheel/wheel_speed');position=dataset(f,'wheel/wheel_pos')
    need(speed.ndim==position.ndim==1 and len(speed)==len(position),'Native wheel geometry')
    origin=wheel_domain[0][0]
    clock=origin+np.arange(len(speed),dtype=float)/50
    starts=dataset(f,'task_aligned_intervals/movement_window/start')[()]
    ends=dataset(f,'task_aligned_intervals/movement_window/end')[()]
    trial_index=dataset(f,'task_aligned_intervals/movement_window/trial_index')[()]
    need(starts.ndim==ends.ndim==trial_index.ndim==1 and starts.shape==ends.shape==trial_index.shape
         and trial_index.dtype.kind in 'iu','Movement interval arrays')
    need(np.isfinite(starts).all() and np.isfinite(ends).all() and (np.diff(starts)>0).all(),'Movement chronology')
    original=dataset(f,'trials/trial_index')[()]
    need(original.dtype.kind in 'iu' and len(set(original.tolist()))==len(original),'Unique original trials')
    by_trial={int(v):i for i,v in enumerate(original)}
    fields=('is_valid','movement_onset_time','stim_on_time','contrast_left','contrast_right','stimulus_side','stimulus_contrast','probability_left','block_prior')
    trial={k:dataset(f,'trials/'+k) for k in fields}
    need(all(len(x)==len(original) for x in trial.values()),'Complete original trial fields')
    rows=[];dispositions=[]
    for i,(start,end,ti) in enumerate(zip(starts,ends,trial_index)):
        start,end=float(start),float(end);ti=int(ti)
        need(abs(end-start-1.)<=1e-9 and ti in by_trial,'Native1second movement interval join')
        j=by_trial[ti];m={k:trial[k][j].item() for k in fields}
        need(bool(m['is_valid']) and abs(float(m['movement_onset_time'])-start)<=1e-9,'Source-valid movement trial join')
        need(math.isfinite(m['stim_on_time']) and m['stim_on_time']<start,'Current stimulus observed before movement')
        sb=stimulus(m)
        matches=[(s,d) for s,ds in domain.items() for d in contains(ds,start-1,end)]
        reason=None
        if len(matches)!=1:reason='whole2s_context_not_inside_exactly_one_official_split'
        elif not contains(wheel_domain,start-1,end) or not contains(spike_domain,start-1,end):reason='outside_declared_wheel_or_spike_support'
        lo,mid,hi=np.searchsorted(clock,[start-1,start,end],side='left')
        if reason is None and (mid-lo!=50 or hi-mid!=50 or hi>len(clock)):reason='not50actual_samples_each_side'
        disposition={'movement_row':i,'trial_index':ti,'context_start':start-1,'context_end':end,
                     'included':reason is None,'reason':reason,
                     'split':matches[0][0] if len(matches)==1 else None,
                     'domain_index':matches[0][1] if len(matches)==1 else None,
                     'boundary_distance_s':min(start-1-domain[matches[0][0]][matches[0][1]][0],
                                               domain[matches[0][0]][matches[0][1]][1]-end) if len(matches)==1 else None}
        dispositions.append(disposition)
        if reason is not None:continue
        hs=np.asarray(speed[lo:mid],float);hp=np.asarray(position[lo:mid],float);y=np.asarray(speed[mid:hi],float)
        need(np.isfinite(np.r_[hs,hp,y]).all() and (hs>=0).all() and (y>=0).all(),'Finite absolute wheel values')
        ho=clock[lo:mid]-start;to=clock[mid:hi]-start
        need((ho>=-1-1e-10).all() and (ho<0).all() and (to>=0).all() and (to<1).all(),'Native half-open wheel sampling')
        hp=hp-hp[-1]
        rows.append({'trial_index':ti,'movement_row':i,'start':start,'end':end,'split':matches[0][0],'domain_index':matches[0][1],
                     'context':{'history_speed':hs.tolist(),'history_position':hp.tolist(),'history_offsets':ho.tolist(),
                                'target_offsets':to.tolist(),'stimulus_block':sb,'stimulus_latency_s':start-m['stim_on_time']},'wheel_speed':y.tolist()})
    need(all(any(r['split']==s for r in rows) for s in SPLITS),'Required session lacks an eligible split; do not drop session')
    return rows,dispositions,units

def validate_spikes(f,units):
    times=dataset(f,'spikes/timestamps');indices=dataset(f,'spikes/unit_index')
    need(times.ndim==indices.ndim==1 and len(times)==len(indices) and indices.dtype.kind in 'iu','Native spike vectors')
    last=-math.inf
    for a in range(0,len(times),1000000):
        t=np.asarray(times[a:a+1000000],float);u=indices[a:a+1000000]
        need(np.isfinite(t).all() and (np.diff(t)>=0).all() and (not len(t) or t[0]>=last),'Sorted finite spike clock')
        need((u>=0).all() and (u<units).all(),'Source unit-index range')
        if len(t):last=t[-1]

def counts_for(f,row,units):
    ds=dataset(f,'spikes/timestamps');a=lower_bound(ds,row['start']);b=lower_bound(ds,row['end'])
    times=np.asarray(ds[a:b],float);u=dataset(f,'spikes/unit_index')[a:b].astype(np.int64)
    edges=row['start']+np.arange(51,dtype=float)/50
    bins=np.searchsorted(edges,times,side='right')-1
    need((bins>=0).all() and (bins<50).all(),'Half-open native neural bins')
    counts=np.bincount(bins*units+u,minlength=50*units).reshape(50,units)
    need(counts.max(initial=0)<=np.iinfo(np.uint32).max,'Lossless uint32 neural counts')
    return counts.astype(np.uint32)

def token(key,name,value):return hmac.new(key,(name+'\0'+value).encode(),hashlib.sha256).hexdigest()[:32]


def group(f, path):
    for i in range(1, len(path.split('/')) + 1):
        need(isinstance(f.get('/'.join(path.split('/')[:i]), getlink=True), h5py.HardLink),
             'Hard-linked native group only')
    value = f[path]
    need(isinstance(value, h5py.Group), 'Native group required')
    return value


def unit_axis(f):
    """Hash exact dtype, ordered native identifiers; never filter or sort units."""
    import json
    ds = dataset(f, 'units/id')
    need(ds.ndim == 1 and len(ds) > 0, 'Native one-dimensional all-unit axis')
    digest = hashlib.sha256()
    digest.update(json.dumps({'dtype': ds.dtype.str, 'count': len(ds)}, sort_keys=True,
                             separators=(',', ':')).encode())
    seen = set()
    for start in range(0, len(ds), 4096):
        for value in ds[start:start + 4096]:
            if hasattr(value, 'item'):
                value = value.item()
            if type(value) is bytes:
                item = ['bytes', value.hex()]
            elif type(value) is str:
                item = ['str', value]
            elif type(value) is int:
                item = ['int', value]
            else:
                raise ValueError('Unsupported native unit-ID scalar type; no coercion')
            raw = json.dumps(item, ensure_ascii=True, separators=(',', ':')).encode()
            need(raw not in seen, 'Unique declared native units')
            seen.add(raw)
            digest.update(len(raw).to_bytes(8, 'big'))
            digest.update(raw)
    return digest.hexdigest()


def overlap_counts(rows):
    """Count all overlapping included2s contexts within each split, not just neighbors."""
    import heapq
    counts = {}
    for split in SPLITS:
        end_heap, count = [], 0
        for row in sorted((r for r in rows if r['split'] == split), key=lambda r: r['start']):
            start = row['start'] - 1
            while end_heap and end_heap[0] <= start:
                heapq.heappop(end_heap)
            count += len(end_heap)
            heapq.heappush(end_heap, row['end'])
        counts[split] = count
    return counts
