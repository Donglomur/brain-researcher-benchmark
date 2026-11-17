"""Real prospective R1/R2/R3 numerical methods. SOURCE ONLY until separately qualified.

No NumPy import or operation occurs at module import. The orchestration never uses
these functions for invented engineering controls. Whole-source review and native
agreement remain required before authentic reference execution.
"""
import hashlib
import math
import time
from .common import require,diagnostic_type
from .assignment import assign
from .schedule import Counter

TEMPERATURES=(.01,.02,.05,.1,.2,.5,1.,2.,5.,10.)
ALPHAS=(.01,.1,1.,10.,100.,1000.)

def configurations(reference):
    import itertools
    require(reference in ('R1','R2','R3'),'learned reference role')
    return [(1.,)] if reference=='R1' else ([(a,) for a in ALPHAS] if reference=='R2' else list(itertools.product((256,512),(1e-4,1e-3),(0.,1e-4))))

def expected_jobs(reference,outer,mask,seed,people):
    jobs=[{'reference':reference,'outer':outer,'inner':person,'config':config,'seed':seed,'mask':mask,'fit_rows':13240,'fit_people':8}
          for config in configurations(reference) for person in sorted(people)]
    jobs.append({'reference':reference,'outer':outer,'inner':'FINAL','seed':seed,'mask':mask,'fit_rows':16540,'fit_people':9})
    return jobs

def arrays():
    import numpy
    return numpy

def original_r1():
    # This module is a byte-for-byte copy of the retained original core. It is
    # imported only at a separately authorized numerical reference operation.
    from . import original_r1 as core
    return core

def r1_fit(image_features,people,outer,held_inner,rows,guard):
    eligible=[p for p in sorted(people) if p!=held_inner]
    forbidden=[outer]+([] if held_inner is None else [held_inner])
    require(len(eligible)==(9 if held_inner is None else 8),'complete original R1 person support')
    guard('before exact original R1 fit')
    model=original_r1().fit_ridge_encoder(image_features,people,eligible,rows,forbidden_people=forbidden)
    guard('after exact original R1 fit')
    return dict(model,kind='original_r1')

def r1_correlation(query,predicted):
    return original_r1().correlation_scores(query,predicted)

def r1_probabilities(scores,temperature):
    return original_r1().probabilities(scores,temperature)

def r1_loss(scores,temperature):
    # Diagnostic record only; selection/calibration itself calls original core.
    np=arrays();p=r1_probabilities(scores,temperature);selected=p[np.arange(200),np.arange(200)]
    return math.inf if np.any(selected==0) else float(-np.log(selected).mean())

def r1_calibrate(score_panels,people):
    np=arrays();expected=sorted(people)
    require(len(expected)==9 and len(score_panels)==90,'complete original R1 calibration caller')
    by_person={person:[(scores,np.arange(200)) for scores in score_panels[i*10:(i+1)*10]] for i,person in enumerate(expected)}
    result=original_r1().fit_temperature(by_person,expected_people=expected)
    values=result['development_equal_person_log_losses'];temperature=result['temperature']
    return temperature,{'grid':result['grid'],'objectives':[None if math.isinf(v) else v for v in values],
                        'positive_infinity':[math.isinf(v) for v in values],'selected_index':result['grid'].index(temperature),
                        'status':'calibration_uninformative_infinite' if all(math.isinf(v) for v in values) else 'calibrated_on_four_repeat_inner_data',
                        'numerical_source':'exact_retained_original_R1_core','original_source_scope':result['source_scope']}

def checked(value):
    np=arrays();require(np.isfinite(value).all(),'nonfinite numerical result')
    return value

def standardize(x):
    np=arrays();mean=x.mean(axis=0,dtype=np.float64);std=x.std(axis=0,ddof=0,dtype=np.float64)
    std=np.where(std==0,1.,std)
    return mean,std

def ridge(x,y,alpha,guard):
    np=arrays();guard('ridge begin')
    x=np.asarray(x,dtype=np.float64);y=np.asarray(y,dtype=np.float64)
    mean,std=standardize(x);z=(x-mean)/std;offset=y.mean(axis=0,dtype=np.float64)
    gram=z.T@z;gram.flat[::gram.shape[0]+1]+=float(alpha)
    guard('ridge sufficient statistics')
    w=np.linalg.solve(gram,z.T@(y-offset));guard('ridge solve returned')
    return dict(kind='ridge',mean=checked(mean),std=checked(std),offset=checked(offset),w=checked(w))

def synthetic(model,x,guard):
    np=arrays();guard('prediction begin')
    if model['kind']=='original_r1':
        out=original_r1().predict_eeg(model,x);guard('original R1 prediction returned');return out
    z=(np.asarray(x,dtype=np.float64)-model['mean'])/model['std']
    if model['kind']=='mlp':z=z.astype(np.float32)
    if model['kind']=='ridge':out=z@model['w']+model['offset']
    else:out=np.maximum(z@model['w1'].T+model['b1'],np.float32(0))@model['w2'].T+model['b2']+model['offset'].astype(np.float32)
    guard('prediction returned');return checked(out)

def pearson(query,predicted):
    np=arrays();q=np.asarray(query,dtype=np.float64).reshape(len(query),-1);p=np.asarray(predicted,dtype=np.float64).reshape(len(predicted),-1)
    q=q-q.mean(axis=1,keepdims=True);p=p-p.mean(axis=1,keepdims=True)
    numerator=q@p.T;den=np.sqrt((q*q).sum(axis=1))[:,None]*np.sqrt((p*p).sum(axis=1))[None,:]
    out=np.zeros_like(numerator);np.divide(numerator,den,out=out,where=den!=0)
    return checked(np.clip(out,-1,1))

def probabilities(scores,temperature):
    np=arrays();require(math.isfinite(temperature) and temperature>0,'positive frozen temperature')
    scores=np.asarray(scores,dtype=np.float64);z=(scores-scores.max(axis=1,keepdims=True))/temperature
    e=np.exp(z);p=e/e.sum(axis=1,keepdims=True)
    return checked(p)

def loss(scores,temperature):
    np=arrays();p=probabilities(scores,temperature);truth=p[np.arange(len(p)),np.arange(len(p))]
    if np.any(truth==0):return math.inf
    return float(-np.log(truth).mean(dtype=np.float64))

def calibrate(score_panels):
    require(len(score_panels)==90 and all(len(s)==200 for s in score_panels),'nine people times ten original calibration panels')
    values=[math.fsum(loss(s,t) for s in score_panels)/90 for t in TEMPERATURES]
    i=min(range(len(values)),key=lambda j:(values[j],j))
    return TEMPERATURES[i],{'grid':list(TEMPERATURES),'objectives':[None if math.isinf(v) else v for v in values],
                            'positive_infinity':[math.isinf(v) for v in values],
                            'selected_index':i,'status':'calibration_uninformative_infinite' if all(math.isinf(v) for v in values) else 'calibrated_on_four_repeat_inner_data'}

def model_identity(model):
    h=hashlib.sha256()
    for k in sorted(model):
        h.update(k.encode()+b'\x00');v=model[k]
        if hasattr(v,'tobytes'):
            h.update(str(v.dtype).encode());h.update(str(v.shape).encode());h.update(v.tobytes(order='C'))
        else:h.update(str(v).encode())
    return h.hexdigest()

def mlp(x,y,config,domain,epochs,guard):
    np=arrays();guard('MLP initialization')
    mean,std=standardize(np.asarray(x,dtype=np.float64));offset=np.asarray(y,dtype=np.float64).mean(axis=0)
    z=((x-mean)/std).astype(np.float32);target=(y-offset).astype(np.float32)
    hidden,rate,decay=config;dims=(z.shape[1],hidden,target.shape[1]);weights=[]
    for layer,(fan_in,fan_out) in enumerate(zip(dims,dims[1:])):
        rng=Counter(dict(domain,purpose='weight',layer=layer));bound=math.sqrt(6/(fan_in+fan_out))
        w=np.fromiter(((2*rng.unit53()-1)*bound for _ in range(fan_in*fan_out)),dtype=np.float32,count=fan_in*fan_out).reshape(fan_out,fan_in)
        weights.extend([w,np.zeros(fan_out,dtype=np.float32)])
    w1,b1,w2,b2=weights;mom=[np.zeros_like(w) for w in weights];var=[np.zeros_like(w) for w in weights]
    checkpoints={};step=0
    for epoch in range(1,epochs+1):
        order=Counter(dict(domain,purpose='row-shuffle',epoch=epoch)).permutation(len(z))
        for start in range(0,len(order),128):
            guard('MLP batch');idx=order[start:start+128];xb=z[idx];yb=target[idx]
            pre=xb@w1.T+b1;hidden_values=np.maximum(pre,np.float32(0));output=hidden_values@w2.T+b2
            delta=np.float32(2/(len(idx)*target.shape[1]))*(output-yb)
            dw2=delta.T@hidden_values;db2=delta.sum(axis=0);dh=(delta@w2)*(pre>0)
            gradients=[dh.T@xb,dh.sum(axis=0),dw2,db2]
            step+=1
            for k,(weight,gradient) in enumerate(zip(weights,gradients)):
                gradient=checked(gradient+np.float32(decay)*weight)
                mom[k]*=np.float32(.9);mom[k]+=np.float32(.1)*gradient
                var[k]*=np.float32(.999);var[k]+=np.float32(.001)*(gradient*gradient)
                mhat=mom[k]/np.float32(1-.9**step);vhat=var[k]/np.float32(1-.999**step)
                weight-=np.float32(rate)*mhat/(np.sqrt(vhat)+np.float32(1e-8))
                checked(weight)
            guard('MLP batch returned')
        if epoch in (10,25,50) or epoch==epochs:
            checkpoints[epoch]=dict(kind='mlp',mean=mean.copy(),std=std.copy(),offset=offset.copy(),
                                     w1=w1.copy(),b1=b1.copy(),w2=w2.copy(),b2=b2.copy())
    return checkpoints

class TrainingRecorder:
    """Original function observations are a breakdown of the enclosing process cost."""
    def __init__(self,guard):self.guard=guard;self.records=[];self.first_exception=None
    def declare(self,identities):
        require(not self.records,'reference jobs predeclared once before any fit')
        self.records=[{'expected_identity':i,'status':'unattempted','first_error':None,'original_identity':None,
                       'start':None,'end':None,'cpu_start':None,'cpu_end':None,'seconds':None,'cpu_seconds':None} for i in identities]
    def fail_pending(self,exc):
        if self.first_exception is None:self.first_exception=exc
        cause=next((r['original_identity'] for r in self.records if r['status']=='failed'),{'stage':'reference_preparation_or_selection_before_next_fit'})
        for r in self.records:
            if r['status']=='unattempted':r.update(status='unattempted_after_failure',causal_original=cause,first_error={'type':diagnostic_type(self.first_exception)})
    def run(self,identity,fn):
        matches=[r for r in self.records if r['status']=='unattempted' and all(identity[k]==v for k,v in r['expected_identity'].items())]
        require(len(matches)==1,'one original predeclared fitting job')
        r=matches[0];r.update(original_identity=identity,status='started',start=time.monotonic(),cpu_start=time.process_time())
        try:
            self.guard('before fitting job')
            value=fn();self.guard('after fitting job');r['status']='complete';return value
        except BaseException as exc:
            if self.first_exception is None:self.first_exception=exc
            r['status']='failed';r['first_error']={'type':diagnostic_type(exc)};self.fail_pending(exc);raise
        finally:
            r['end']=time.monotonic();r['cpu_end']=time.process_time();r['seconds']=r['end']-r['start'];r['cpu_seconds']=r['cpu_end']-r['cpu_start']

class Learner:
    def __init__(self,x,people,outer,fit_rows,selection,calibration,guard,mask,recorder=None):
        np=arrays();require(x.shape==(16540,4096),'full fixed feature matrix')
        require(len(people)==9 and outer not in people,'all nine nonouter people')
        require(all(v.shape==(16540,1700) for v in people.values()),'all complete mean EEG arrays')
        require(len(fit_rows)==13240 and len(selection)==10 and all(len(v)==330 for v in selection),'full selection support')
        require(len(calibration)==10 and all(len(v)==200 for v in calibration),'full original calibration support')
        self.x=x;self.people=people;self.outer=outer;self.fit_rows=fit_rows;self.selection=selection;self.calibration=calibration
        require(mask in ('FULL','PRE_ONLY','POST_ONLY'),'unique training mask')
        self.mask=mask;self.guard=guard;self.recorder=recorder if recorder is not None else TrainingRecorder(guard);self.selection_records=[]
    def mean(self,excluded,rows):
        np=arrays();ids=[k for k in sorted(self.people) if k!=excluded]
        require(len(ids)==(8 if excluded else 9),'equal-person target support')
        out=np.zeros((len(rows),1700),dtype=np.float64)
        for person in ids:
            self.guard('mean EEG person');out+=self.people[person][rows]
        return out/len(ids)
    def assess(self,model,person):
        np=arrays();validation=self.people[person];a=[];u=[];cal=[];mse=[]
        for rows in self.selection:
            self.guard('full330 selection panel');pred=synthetic(model,self.x[rows],self.guard);target=validation[rows]
            scores=pearson(target,pred);assignment=assign(scores)
            a.append(sum(i==j for i,j in enumerate(assignment))/330)
            u.append(float((scores.argmax(axis=1)==np.arange(330)).mean()))
            mse.append(float(np.square(pred.astype(np.float64)-target).mean(dtype=np.float64)))
        for rows in self.calibration:
            pred=synthetic(model,self.x[rows],self.guard);cal.append(pearson(validation[rows],pred))
        return {'assignment':math.fsum(a)/10,'independent':math.fsum(u)/10,'MSE':math.fsum(mse)/10,'calibration':cal,
                'selection_panels':[{'rank':i,'assignment':a[i],'independent':u[i],'MSE':mse[i]} for i in range(10)]}
    def fit(self,reference,seed):
        require(reference in ('R1','R2','R3'),'learned reference')
        configs=configurations(reference);planned=expected_jobs(reference,self.outer,self.mask,seed,self.people)
        if self.recorder.records:require([r['expected_identity'] for r in self.recorder.records]==planned,'same original pre-load fitting registry')
        else:self.recorder.declare(planned)
        self.selection_records=[{'outer':self.outer,'inner':person,'config':list(config),'epoch':epoch,'status':'unattempted','first_error':None}
                                for config in configs for person in sorted(self.people) for epoch in ((10,25,50) if reference=='R3' else (None,))]
        best=None;best_cal=None;best_config=None
        for config in configs:
            by_epoch={e:[] for e in ((10,25,50) if reference=='R3' else (None,))}
            for person in sorted(self.people):
                ident={'reference':reference,'outer':self.outer,'inner':person,'config':config,'seed':seed,'mask':self.mask,'fit_rows':13240,'fit_people':8}
                if reference=='R1':
                    models={None:self.recorder.run(ident,lambda:r1_fit(self.x,self.people,self.outer,person,self.fit_rows,self.guard))}
                else:
                    y=self.mean(person,self.fit_rows);x=self.x[self.fit_rows]
                    if reference=='R3':models=self.recorder.run(ident,lambda:mlp(x,y,config,dict(ident),50,self.guard))
                    else:models={None:self.recorder.run(ident,lambda:ridge(x,y,config[0],self.guard))}
                for epoch,model in models.items():
                    sr=next(r for r in self.selection_records if r['inner']==person and r['config']==list(config) and r['epoch']==epoch)
                    sr.update(status='started',start=time.monotonic())
                    try:
                        if reference=='R1':
                            cal=[r1_correlation(self.people[person][rows],synthetic(model,self.x[rows],self.guard)) for rows in self.calibration]
                            result={'assignment':None,'independent':None,'MSE':None,'calibration':cal,'selection_panels':[]}
                        else:result=self.assess(model,person)
                        objectives=[[(r1_loss if reference=='R1' else loss)(s,t) for t in TEMPERATURES] for s in result['calibration']]
                        sr.update(status='complete',end=time.monotonic(),model_sha256=model_identity(model),assignment=result['assignment'],
                                  independent=result['independent'],MSE=result['MSE'],selection_panels=result['selection_panels'],
                                  calibration_objectives=[[{'value':None if math.isinf(v) else v,'positive_infinity':math.isinf(v)} for v in row] for row in objectives])
                    except BaseException as exc:
                        sr.update(status='failed',end=time.monotonic(),first_error={'type':diagnostic_type(exc)});self.recorder.fail_pending(exc);raise
                    by_epoch[epoch].append(result)
            for epoch,rows in by_epoch.items():
                require(len(rows)==9,'all inner people selected jointly')
                if reference=='R1':key=(0,)
                else:key=(-math.fsum(r['assignment'] for r in rows)/9,-math.fsum(r['independent'] for r in rows)/9,math.fsum(r['MSE'] for r in rows)/9,*config,*(() if epoch is None else (epoch,)))
                if best is None or key<best:
                    best=key;best_config=(config,epoch);best_cal=[s for r in rows for s in r['calibration']]
        temperature,calibration_report=r1_calibrate(best_cal,self.people) if reference=='R1' else calibrate(best_cal);config,epoch=best_config
        final_id={'reference':reference,'outer':self.outer,'inner':'FINAL','config':config,'seed':seed,'mask':self.mask,'fit_rows':16540,'fit_people':9}
        if reference=='R1':model=self.recorder.run(final_id,lambda:r1_fit(self.x,self.people,self.outer,None,list(range(16540)),self.guard))
        else:
            y=self.mean(None,list(range(16540)))
            if reference=='R3':model=self.recorder.run(final_id,lambda:mlp(self.x,y,config,dict(final_id),epoch,self.guard))[epoch]
            else:model=self.recorder.run(final_id,lambda:ridge(self.x,y,config[0],self.guard))
        return model,{'reference':reference,'seed':seed,'outer':self.outer,'selected_config':list(config),'selected_epoch':epoch,
                      'temperature':temperature,'calibration':calibration_report,'selection_records':self.selection_records,
                      'original_training_records':self.recorder.records,'final_model_sha256':model_identity(model),
                      'outer_query_exposed':False,'calibration_repeat_transfer':'four-repeat inner to eighty-repeat query; no calibration guarantee'}
