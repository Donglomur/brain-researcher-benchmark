"""NEURAL-001 independent reference algebra; no I/O, providers or qualification.

Only the owner's separately qualified full-study controller may call training on
scientific inputs. Generic algebra helpers also support invented small operands;
those helpers are not benchmark admission routes or evidence of native parity.
"""
from dataclasses import dataclass
from types import MappingProxyType
import hashlib
import json
import math
import numpy as np

LAGS = tuple(range(-16, 1))
LAMBDAS = (1e-6, 1e-4, 1e-2, 1., 1e2, 1e4, 1e6)
RANKS = (32, 64)
SCALES = (.5, 1., 2.)
ALPHAS = (.001, .1, 10., 1000.)
BLOCK_ROWS = 4096

class ReferenceError(ValueError):
    pass

def require(ok, reason):
    if not ok:
        raise ReferenceError(reason)

def _finite(x):
    require(np.isfinite(x).all(), 'Finite algebra operand/result required')
    return x

def _readonly(x):
    # Immutable bytes backing prevents setflags(write=True), unlike merely
    # disabling the flag on an owning NumPy allocation.
    x = np.asarray(x, dtype='<f8', order='C')
    return np.frombuffer(x.tobytes(order='C'), dtype='<f8').reshape(x.shape)

@dataclass(frozen=True)
class Epoch:
    run_id: str
    epoch_id: str
    meg: object
    envelope: object

@dataclass(frozen=True)
class FrozenReference:
    family: str
    person_id: str
    run_ids: tuple
    epoch_ids: tuple
    lengths: tuple
    channel_kinds: tuple
    config: tuple
    array_items: tuple
    report_json: bytes

    @property
    def arrays(self):
        return MappingProxyType(dict(self.array_items))

    @property
    def array_payload_bytes(self):
        return sum(x.nbytes for _, x in self.array_items)

class Events:
    def __init__(self, callback, person_id, family):
        require(callable(callback), 'A controller progress/deadline callback is required')
        self.callback = callback
        self.person_id = person_id
        self.family = family
        self.fold = 'all_training'
        self.config = None
        self.ridge_attempts = 0
        self.pca_attempts = 0
        self.blocks = 0
        self.logical_operand_bytes = 0

    def emit(self, phase, **details):
        if phase == 'ridge_attempt': self.ridge_attempts += 1
        if phase == 'pca_attempt': self.pca_attempts += 1
        if phase.endswith('_block'): self.blocks += 1
        self.logical_operand_bytes += int(details.get('operand_bytes', 0))
        event = dict(id=self.person_id, family=self.family, fold=self.fold,
                     config=self.config, phase=phase, **details)
        self.callback(event)  # may refuse before the corresponding operation


def training_plan(expected_run_ids):
    runs = tuple(expected_run_ids)
    require(len(runs) in (2, 4) and len(set(runs)) == len(runs), 'All two/four source-admitted runs required')
    return dict(run_ids=runs, folds=tuple(dict(held_run=r, train_runs=tuple(x for x in runs if x != r)) for r in runs),
                R1_ridge_attempts=7*len(runs)+1, R2_ridge_attempts=24*len(runs)+1,
                R2_pca_attempts=2*len(runs)+1, R2_design_pca_upper=2*(len(runs)+1), R0_means=1,
                reference_panels=('R1/neural','R1/within_query_half_shift','R2/neural','R2/within_query_half_shift','R0/no_neural'))


def validate_training(epochs, expected_run_ids, expected_epoch_ids, expected_epoch_runs, expected_lengths, channel_kinds, *, family):
    require(family in ('R0', 'R1', 'R2'), 'Known independent reference family')
    epochs = tuple(epochs); runs = tuple(expected_run_ids); ids = tuple(expected_epoch_ids); lengths = tuple(expected_lengths)
    training_plan(runs)
    require(all(type(x) is str and x for x in runs+ids), 'Opaque string run and epoch identifiers')
    require(len(ids) > 0 and len(ids) == len(lengths) and len(set(ids)) == len(ids), 'Complete unique expected epoch roster')
    require(all(type(x) is int and x >= 4 for x in lengths), 'Exact source-admitted epoch lengths')
    require(all(type(e) is Epoch for e in epochs), 'Exact Epoch records required')
    require(tuple(e.epoch_id for e in epochs) == ids, 'Every admitted epoch in the declared order; no omission/replacement')
    require(tuple(e.run_id for e in epochs) == tuple(expected_epoch_runs), 'Exact independently admitted epoch-to-run mapping')
    require(set(e.run_id for e in epochs) == set(runs), 'Every admitted source run must contribute its admitted epochs')
    kinds = tuple(channel_kinds)
    require(len(kinds) == 306 and kinds.count('mag') == 102 and kinds.count('grad') == 204, 'All306 sensors with original kinds')
    for e, n in zip(epochs, lengths):
        y = e.envelope
        require(type(y) is np.ndarray and y.dtype == np.dtype('<f8') and y.shape == (n,), 'Complete float64 envelope epoch')
        _finite(y)
        if family != 'R0':
            x = e.meg
            require(type(x) is np.ndarray and x.dtype == np.dtype('<f8') and x.shape == (n,306), 'Complete float64 306-channel epoch')
            _finite(x)
        # R0 deliberately never accesses e.meg, not even for a shape check.
    require(sum(lengths) <= 250000, 'Provisional complete-view cap; overflow requires successor, never crop')
    return epochs, runs, ids, lengths, kinds


def iter_lag_blocks(x, *, lags=LAGS, block_rows=BLOCK_ROWS, bias=True):
    """Generic algebra: lag l at output row t uses input row t-l.

    Each invocation is ONE epoch/query. Padding fills missing features only;
    no observation or target is appended/removed.
    """
    x = np.asarray(x, dtype=np.float64)
    require(x.ndim == 2 and x.shape[0] > 0 and x.shape[1] > 0, 'Nonempty matrix')
    require(type(block_rows) is int and 0 < block_rows <= BLOCK_ROWS, 'Bounded lag block')
    require(lags and all(type(v) is int for v in lags), 'Integer lag sequence')
    n,c = x.shape
    for start in range(0,n,block_rows):
        stop = min(n,start+block_rows)
        out = np.zeros((stop-start,len(lags)*c+int(bias)), dtype=np.float64)
        if bias: out[:,0] = 1.
        for j,lag in enumerate(lags):
            lo=max(start,lag); hi=min(stop,n+lag)
            if hi>lo:
                col=int(bias)+j*c
                out[lo-start:hi-start,col:col+c] = x[lo-lag:hi-lag]
        yield start,stop,out


def ridge_from_gram(gram, cross, penalty):
    """Summed-loss ridge; column0 is the unpenalized intercept."""
    gram=np.asarray(gram,dtype=np.float64);cross=np.asarray(cross,dtype=np.float64)
    require(gram.ndim==2 and gram.shape[0]==gram.shape[1] and cross.shape==(gram.shape[0],), 'Compatible sufficient statistics')
    require(math.isfinite(penalty) and penalty>0, 'Positive finite declared ridge penalty')
    _finite(gram);_finite(cross)
    system=gram.copy();idx=np.arange(1,len(cross));system[idx,idx]+=penalty
    return _finite(np.linalg.solve(system,cross))


def _blocks(epochs, attr, events, phase):
    for e in epochs:
        a=getattr(e,attr)
        for start in range(0,len(a),BLOCK_ROWS):
            b=a[start:start+BLOCK_ROWS]
            events.emit(phase,epoch=e.epoch_id,rows=len(b),operand_bytes=b.nbytes)
            yield b


def _moments(epochs, attr, events, selector=None):
    """Population moments, two passes. Selector can pool sensor kinds."""
    count=0;total=None
    for b in _blocks(epochs,attr,events,'moments_mean_block'):
        a=b if selector is None else b[:,selector].reshape(-1)
        value=np.sum(a,axis=0,dtype=np.float64)
        total=value.copy() if total is None else total+value
        count += len(a)
    require(count>0, 'Nonempty training-only moment support')
    mean=total/count;ss=np.zeros_like(mean,dtype=np.float64)
    for b in _blocks(epochs,attr,events,'moments_variance_block'):
        a=b if selector is None else b[:,selector].reshape(-1)
        ss += np.sum((a-mean)**2,axis=0,dtype=np.float64)
    scale=np.sqrt(ss/count)
    _finite(np.asarray(mean));_finite(np.asarray(scale))
    require(np.all(scale>0), 'Zero training scale invalidates reference; never drop support')
    return np.asarray(mean),np.asarray(scale)


def _target_moments(epochs,events):
    mean,scale=_moments(epochs,'envelope',events)
    return float(mean),float(scale)


def _kind_transform(epochs,kinds,events):
    means=[];scales=[]
    for kind in ('mag','grad'):
        mask=np.asarray([k==kind for k in kinds])
        m,s=_moments(epochs,'meg',events,mask);means.append(float(m));scales.append(float(s))
    return dict(kind_mean=np.asarray(means),kind_scale=np.asarray(scales))


def apply_kind(x,arrays,kinds):
    ind=np.asarray([0 if k=='mag' else 1 for k in kinds])
    return _finite((x-arrays['kind_mean'][ind])/arrays['kind_scale'][ind])


def spatial_parameters(epochs,rank,events):
    """Streaming 306-square Gram eigensystem gives PCA right singular vectors.

    Mathematically equivalent to the specified centered-matrix right SVD;
    numerical/tied-eigenspace behavior still needs exact environment qualification.
    """
    events.emit('pca_attempt',rank=rank)
    mean,scale=_moments(epochs,'meg',events)
    n=sum(len(e.envelope) for e in epochs);p=len(mean)
    require(type(rank) is int and 0<rank<=min(n,p),'Full requested PCA rank, no rank reduction')
    zbar=np.zeros(p)
    for b in _blocks(epochs,'meg',events,'pca_center_block'):zbar+=np.sum((b-mean)/scale,axis=0)
    zbar/=n;cov=np.zeros((p,p))
    for b in _blocks(epochs,'meg',events,'pca_covariance_block'):
        z=(b-mean)/scale-zbar;cov+=z.T@z
    events.emit('pca_eigensolve',rank=rank,matrix_bytes=cov.nbytes)
    values,vectors=np.linalg.eigh(_finite(cov/n));order=np.argsort(-values,kind='stable')[:rank]
    require(np.all(values[order]>0),'Nonpositive retained PCA eigenvalue invalidates reference')
    v=vectors[:,order].copy()
    for j in range(rank):
        i=int(np.argmax(np.abs(v[:,j])))
        if v[i,j]<0:v[:,j]*=-1
    q2=np.zeros(rank)
    for b in _blocks(epochs,'meg',events,'pca_component_scale_block'):
        scores=((b-mean)/scale-zbar)@v;q2+=np.sum(scores*scores,axis=0)
    q=np.sqrt(q2/n);_finite(q);require(np.all(q>0),'Zero component variance invalidates reference')
    return dict(channel_mean=mean,channel_scale=scale,pca_center=zbar,pca_vectors=v,pca_scale=q)


def apply_spatial(x,arrays):
    return _finite((((x-arrays['channel_mean'])/arrays['channel_scale'])-arrays['pca_center'])@arrays['pca_vectors']/arrays['pca_scale'])


def rff_base(rank, *, width=512, lag_count=17):
    """Generic algebra helper; production calls use width512, lag_count17."""
    require(type(rank) is int and rank>0 and type(width) is int and width>0 and type(lag_count) is int and lag_count>0,'Positive random-map dimensions')
    rng=np.random.Generator(np.random.PCG64(20261107+rank))
    g=rng.standard_normal(size=(lag_count*rank,width),dtype=np.float64)
    b=2*np.pi*rng.random(size=width,dtype=np.float64)
    return g,b


def _admitted_map(rank,events,identities):
    events.emit('random_map_generation',rank=rank,seed=20261107+rank,allocated_array_bytes=(17*rank*512+512)*8)
    g,b=rff_base(rank)
    events.emit('random_map_identity',rank=rank,operand_bytes=g.nbytes+b.nbytes)
    identity=dict(seed=20261107+rank,shape=list(g.shape),dtype='<f8',numpy_version=np.__version__,
                  g_sha256=hashlib.sha256(memoryview(g).cast('B')).hexdigest(),
                  phase_sha256=hashlib.sha256(memoryview(b).cast('B')).hexdigest())
    key=str(rank)
    require(key not in identities or identities[key]==identity,'Identical rank map across held-run folds and final refit')
    identities[key]=identity
    return g,b


def rff_features(lagged,g,phase,scale):
    require(math.isfinite(scale) and scale>0,'Positive RFF scale')
    require(lagged.shape[1]==g.shape[0] and phase.shape==(g.shape[1],),'Exact RFF dimensions')
    # Deterministic scaling consumes no additional RNG draws.
    return _finite(math.sqrt(2/g.shape[1])*np.cos((lagged@g)/(scale*math.sqrt(g.shape[0]))+phase))


def _features(x,family,arrays,kinds,config,events,epoch_id):
    transformed=apply_kind(x,arrays,kinds) if family=='R1' else apply_spatial(x,arrays)
    for start,stop,a in iter_lag_blocks(transformed,bias=(family=='R1')):
        events.emit('feature_block',epoch=epoch_id,rows=stop-start,operand_bytes=a.nbytes)
        if family=='R2':
            phi=rff_features(a,arrays['rff_g'],arrays['rff_phase'],config[1])
            with_bias=np.empty((len(phi),len(phi[0])+1));with_bias[:,0]=1.;with_bias[:,1:]=phi;a=with_bias
        yield start,stop,a


def _statistics(epochs,family,arrays,kinds,config,target_mean,target_scale,events):
    d=5203 if family=='R1' else 513
    gram=np.zeros((d,d));cross=np.zeros(d);n=0
    for e in epochs:
        for start,stop,a in _features(e.meg,family,arrays,kinds,config,events,e.epoch_id):
            y=(e.envelope[start:stop]-target_mean)/target_scale
            events.emit('covariance_block',epoch=e.epoch_id,rows=len(y),operand_bytes=a.nbytes+y.nbytes)
            gram+=a.T@a;cross+=a.T@y;n+=len(y)
    _finite(gram);_finite(cross)
    return gram,cross,n


def _predict_epoch(x,family,arrays,kinds,config,target_mean,target_scale,events,epoch_id):
    out=np.empty(len(x),dtype=np.float64)
    for a,b,features in _features(x,family,arrays,kinds,config,events,epoch_id):
        events.emit('prediction_block',epoch=epoch_id,rows=b-a,operand_bytes=features.nbytes)
        out[a:b]=(features@arrays['beta'])*target_scale+target_mean
    return _finite(out)


def _rank(x):
    order=np.argsort(x,kind='stable');a=x[order];out=np.empty(len(x));i=0
    while i<len(x):
        j=i+1
        while j<len(x) and a[j]==a[i]:j+=1
        out[order[i:j]]=(i+j+1)/2.;i=j
    return out


def validation_z(pred,target):
    """Training validation only; final query scorer belongs to protected grader."""
    pred=np.asarray(pred,dtype=np.float64);target=np.asarray(target,dtype=np.float64)
    require(pred.shape==target.shape and pred.ndim==1 and len(pred)>=4,'Complete validation epoch')
    _finite(pred);_finite(target);require(not np.all(target==target[0]),'Constant validation target invalidates reference')
    if np.all(pred==pred[0]):return 0.
    a=_rank(pred);b=_rank(target);a-=math.fsum(a)/len(a);b-=math.fsum(b)/len(b)
    rho=math.fsum(float(x)*float(y) for x,y in zip(a,b))/math.sqrt(math.fsum(a*a)*math.fsum(b*b))
    bound=float(np.nextafter(1.,0.));return math.atanh(max(-bound,min(bound,rho)))


def _validation(epochs,family,arrays,kinds,config,ym,ys,events):
    scores=[]
    for e in epochs:
        pred=_predict_epoch(e.meg,family,arrays,kinds,config,ym,ys,events,e.epoch_id)
        scores.append(validation_z(pred,e.envelope))
    require(scores,'Every held run has its complete epochs')
    return math.fsum(scores)/len(scores)


def _solve(gram,cross,penalty,events):
    events.emit('ridge_attempt',penalty=float(penalty),matrix_bytes=gram.nbytes)
    return ridge_from_gram(gram,cross,penalty)


def _freeze(family,person_id,runs,ids,lengths,kinds,config,arrays,report):
    items=tuple((name,_readonly(value)) for name,value in sorted(arrays.items()))
    report=dict(report,array_payload_bytes=sum(x.nbytes for _,x in items),
                numpy_version=np.__version__,numpy_required_for_scientific_run='2.2.6',
                immutable_backing='bytes-backed little-endian float64 arrays',
                native_parity=False,scientific_qualification=False)
    body=json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return FrozenReference(family,person_id,runs,ids,lengths,kinds,tuple(config),items,body),report


def train_reference(person_id,epochs,expected_run_ids,expected_epoch_ids,expected_epoch_runs,expected_lengths,channel_kinds,family,*,stage,progress):
    """Full person reference source, with all held-run folds then final refit.

    `stage` is only a protocol assertion, NOT permission or qualification.
    External controller must enforce original clock, authority and complete study.
    """
    require(stage=='person_training','No query-phase fitting')
    require(type(person_id) is str and person_id,'Opaque participant id')
    events=Events(progress,person_id,family);events.emit('training_admission')
    require(np.__version__=='2.2.6','Production reference requires qualified NumPy2.2.6; generic algebra controls are separate')
    epochs,runs,ids,lengths,kinds=validate_training(epochs,expected_run_ids,expected_epoch_ids,expected_epoch_runs,expected_lengths,channel_kinds,family=family)
    plan=training_plan(runs)
    if family=='R0':
        total=0.;n=0
        for b in _blocks(epochs,'envelope',events,'prior_mean_block'):total+=float(np.sum(b));n+=len(b)
        mean=total/n;require(math.isfinite(mean),'Finite unconditional mean')
        return _freeze(family,person_id,runs,ids,lengths,kinds,(),{'target_mean':np.array(mean)},dict(plan=plan,training_epoch_runs=list(expected_epoch_runs),cv=[],ridge_attempts=0,pca_attempts=0,logical_operand_bytes=events.logical_operand_bytes))
    configs=tuple((v,) for v in LAMBDAS) if family=='R1' else tuple((k,h,a) for k in RANKS for h in SCALES for a in ALPHAS)
    scores={c:[] for c in configs};records=[];map_identities={}
    for held in runs:
        events.fold=held;events.config=None;train=tuple(e for e in epochs if e.run_id!=held);valid=tuple(e for e in epochs if e.run_id==held)
        ym,ys=_target_moments(train,events)
        if family=='R1':
            arrays=_kind_transform(train,kinds,events)
            gram,cross,n=_statistics(train,family,arrays,kinds,(),ym,ys,events)
            for config in configs:
                events.config=config;arrays['beta']=_solve(gram,cross,64*config[0],events)
                score=_validation(valid,family,arrays,kinds,config,ym,ys,events)
                scores[config].append(score);records.append(dict(fold=held,config=config,score=score,training_runs=tuple(r for r in runs if r!=held),validation_epochs=tuple(e.epoch_id for e in valid)))
        else:
            for rank in RANKS:
                events.config=(rank,);arrays=spatial_parameters(train,rank,events)
                arrays['rff_g'],arrays['rff_phase']=_admitted_map(rank,events,map_identities)
                for scale in SCALES:
                    events.config=(rank,scale);gram,cross,n=_statistics(train,family,arrays,kinds,(rank,scale),ym,ys,events)
                    for alpha in ALPHAS:
                        config=(rank,scale,alpha);events.config=config;arrays['beta']=_solve(gram,cross,n*alpha,events)
                        score=_validation(valid,family,arrays,kinds,config,ym,ys,events)
                        scores[config].append(score);records.append(dict(fold=held,config=config,score=score,training_runs=tuple(r for r in runs if r!=held),validation_epochs=tuple(e.epoch_id for e in valid)))
    means={c:math.fsum(v)/len(runs) for c,v in scores.items()}
    require(all(len(v)==len(runs) for v in scores.values()),'Every configuration evaluated on every original run')
    if family=='R1':selected=max(configs,key=lambda c:(means[c],c[0]))
    else:selected=max(configs,key=lambda c:(means[c],c[2],c[1],-c[0]))
    events.fold='all_training';events.config=selected;events.emit('selected_configuration',selection_score=means[selected])
    ym,ys=_target_moments(epochs,events)
    arrays=_kind_transform(epochs,kinds,events) if family=='R1' else spatial_parameters(epochs,selected[0],events)
    if family=='R2':
        arrays['rff_g'],arrays['rff_phase']=_admitted_map(selected[0],events,map_identities)
    gram,cross,n=_statistics(epochs,family,arrays,kinds,selected,ym,ys,events)
    arrays['beta']=_solve(gram,cross,64*selected[0] if family=='R1' else n*selected[2],events)
    arrays['target_mean']=np.array(ym);arrays['target_scale']=np.array(ys)
    require(events.ridge_attempts==plan[family+'_ridge_attempts'],'Complete ridge attempt count')
    if family=='R2':require(events.pca_attempts==plan['R2_pca_attempts'],'Complete PCA attempt count')
    events.emit('training_complete',ridge_attempts=events.ridge_attempts,pca_attempts=events.pca_attempts)
    return _freeze(family,person_id,runs,ids,lengths,kinds,selected,arrays,dict(plan=plan,training_epoch_runs=list(expected_epoch_runs),cv=records,selection=[dict(config=c,mean_run_z=means[c]) for c in configs],selected=selected,ridge_attempts=events.ridge_attempts,pca_attempts=events.pca_attempts,blocks=events.blocks,logical_operand_bytes=events.logical_operand_bytes,random_map_reuse='fresh rank-keyed map; identical values for every fold/person/refit/scale/alpha',random_map_identities=map_identities,inputs_are_training_only=True))


def predict_reference(state,query_view,*,progress):
    require(type(state) is FrozenReference,'Reviewed frozen reference state')
    events=Events(progress,state.person_id,state.family);events.fold='query';events.config=state.config;events.emit('query_admission')
    require(type(query_view) is dict,'Exact current query view')
    n=query_view.get('length');ident=query_view.get('id');arm=query_view.get('arm')
    require(type(n) is int and 4<=n<=61440 and type(ident) is str and ident,'Complete current interval')
    require(query_view.get('fs_hz')==64,'Original64Hz view')
    require(tuple(query_view.get('channel_kinds',()))==state.channel_kinds,'Exact original channel kinds/order')
    if state.family=='R0':
        require(arm=='no_neural','Prior reference only in no-neural arm')
        # Do not read/query_view.get('meg') on the no-neural path.
        events.emit('prior_prediction_block',epoch=ident,rows=n)
        return np.full(n,float(state.arrays['target_mean']),dtype='<f8')
    require(arm in ('neural','within_query_half_shift'),'Neural reference only in its paired arms')
    x=query_view.get('meg');require(type(x) is np.ndarray and x.dtype==np.dtype('<f8') and x.shape==(n,306),'Exact current full sensor matrix');_finite(x)
    arrays=state.arrays
    # Support.make_query_view already transformed the arm; never roll again.
    return _predict_epoch(x,state.family,arrays,state.channel_kinds,state.config,float(arrays['target_mean']),float(arrays['target_scale']),events,ident)


def state_payload(state):
    require(type(state) is FrozenReference,'Frozen reference state')
    arrays=dict(state.array_items)
    metadata=dict(schema='neural001_reference_state_v1',family=state.family,person_id=state.person_id,run_ids=list(state.run_ids),epoch_ids=list(state.epoch_ids),lengths=list(state.lengths),channel_kinds=list(state.channel_kinds),config=list(state.config),report=json.loads(state.report_json),arrays={k:dict(shape=list(v.shape),dtype='<f8',bytes=v.nbytes,sha256=hashlib.sha256(v.tobytes()).hexdigest()) for k,v in arrays.items()})
    return metadata,MappingProxyType(arrays)


def restore_state(metadata,arrays):
    """Plain named arrays only; no pickle, callable or file/path deserialization."""
    require(type(metadata) is dict and set(metadata)=={'schema','family','person_id','run_ids','epoch_ids','lengths','channel_kinds','config','report','arrays'} and metadata.get('schema')=='neural001_reference_state_v1','Exact state schema')
    family=metadata.get('family');config=tuple(metadata.get('config',()))
    base={'target_mean':()}
    if family=='R1':
        require(config in tuple((v,) for v in LAMBDAS),'Exact R1 configuration');shapes=dict(base,target_scale=(),kind_mean=(2,),kind_scale=(2,),beta=(5203,))
    elif family=='R2':
        require(config in tuple((k,h,a) for k in RANKS for h in SCALES for a in ALPHAS),'Exact R2 configuration');k=config[0];shapes=dict(base,target_scale=(),channel_mean=(306,),channel_scale=(306,),pca_center=(306,),pca_vectors=(306,k),pca_scale=(k,),rff_g=(17*k,512),rff_phase=(512,),beta=(513,))
    elif family=='R0':require(config==(),'Exact R0 configuration');shapes=base
    else:raise ReferenceError('Unknown state family')
    require(set(arrays)==set(shapes)==set(metadata.get('arrays',{})),'Exact state array names')
    checked={}
    for name,shape in shapes.items():
        x=arrays[name];row=metadata['arrays'][name]
        require(type(x) is np.ndarray and x.dtype==np.dtype('<f8') and x.shape==shape,'Exact state array dtype/shape');_finite(x)
        require(row==dict(shape=list(shape),dtype='<f8',bytes=x.nbytes,sha256=hashlib.sha256(x.tobytes()).hexdigest()),'Exact state payload identity')
        if name.endswith('scale'):require(np.all(x>0),'Positive frozen training scales')
        checked[name]=x
    runs=tuple(metadata['run_ids']);training_plan(runs);ids=tuple(metadata['epoch_ids']);lengths=tuple(metadata['lengths']);kinds=tuple(metadata['channel_kinds'])
    require(len(ids)==len(lengths)>0 and len(set(ids))==len(ids) and all(type(n) is int and n>=4 for n in lengths),'Complete frozen training support metadata')
    require(len(kinds)==306 and kinds.count('mag')==102 and kinds.count('grad')==204,'Frozen full sensor kinds')
    report=metadata['report'];require(type(report) is dict,'Plain provenance report')
    epoch_runs=report.get('training_epoch_runs');require(type(epoch_runs) is list and len(epoch_runs)==len(ids) and set(epoch_runs)==set(runs),'Complete frozen epoch-to-run provenance')
    plan=training_plan(runs)
    require(report.get('ridge_attempts')==(0 if family=='R0' else plan[family+'_ridge_attempts']),'Complete frozen ridge attempt provenance')
    require(report.get('pca_attempts')==(plan['R2_pca_attempts'] if family=='R2' else 0),'Complete frozen PCA attempt provenance')
    require(type(metadata['person_id']) is str and metadata['person_id'],'Opaque participant id')
    state=FrozenReference(family,metadata['person_id'],runs,ids,lengths,kinds,config,tuple((name,_readonly(x)) for name,x in sorted(checked.items())),json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    # External owner binds this payload to its source/admission and actual training
    # receipt; a self-declared hash or this importer does NOT establish custody.
    return state
