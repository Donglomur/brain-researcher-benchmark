"""Independent mathematical reference source. No computation at import time."""
import math
from .errors import require
from .objects import fields


def reconstruction_component(reconstructed,target,masks,profile,reduction):
    require(profile in ('R-paper.patch_L1','R-native.sample_L1','P-sample_mean'),'loss profile')
    require(reduction in ('pooled_mask_v1','equal_example'),'batch reduction')
    require(len(reconstructed)==len(target)==len(masks)>0,'batch support')
    counts=[]
    for pred,gold,indices in zip(reconstructed,target,masks):
        require(len(pred)==len(gold)==len(indices)>0 and len(set(indices))==len(indices),'unique nonempty masked patches')
        error=0.0;samples=0
        for p,t in zip(pred,gold):
            require(len(p)==len(t)==200,'qualified fixed patch width')
            require(all(math.isfinite(v) for v in [*p,*t]),'finite reconstruction')
            error+=math.fsum(abs(a-b) for a,b in zip(p,t));samples+=len(p)
        counts.append({'E':error,'M':len(indices),'N':samples})
    E=math.fsum(x['E'] for x in counts);M=sum(x['M'] for x in counts);N=sum(x['N'] for x in counts)
    if profile=='R-native.sample_L1':require(len({x['M'] for x in counts})==1,'native rectangular masked tensor')
    key='M' if profile=='R-paper.patch_L1' else 'N'
    value=(E/(M if key=='M' else N)) if reduction=='pooled_mask_v1' else math.fsum(x['E']/x[key] for x in counts)/len(counts)
    return {'objective_profile':profile,'batch_reduction':reduction,'width':200,'B':len(counts),'per_example':counts,'E':E,'M':M,'N':N,'value':value,
            'per_example_patch_mean':math.fsum(x['E']/x['M'] for x in counts)/len(counts),'pooled_patch_mean':E/M,'pooled_sample_mean':E/N}


def total_objective(primary,secondary,alpha,lam,phase,secondary_enabled):
    require(math.isfinite(alpha) and alpha>0 and math.isfinite(lam) and lam>=0,'coefficients')
    require(phase in ('train','evaluate'),'phase')
    if not secondary_enabled or phase!='train':
        require(secondary is None,'absent secondary cannot be measured zero')
        return {'alpha':alpha,'lambda':lam,'phase':phase,'secondary_observed':False,'primary':primary,'secondary':None,'value':alpha*primary['value']}
    require(secondary is not None,'secondary missing')
    require(all(primary[x]==secondary[x] for x in ('objective_profile','batch_reduction','B','M','N','width')),'component objective/support mismatch')
    return {'alpha':alpha,'lambda':lam,'phase':phase,'secondary_observed':True,'primary':primary,'secondary':secondary,'value':alpha*(primary['value']+lam*secondary['value'])}


def native_trapezoid(step,n_iter,start,peak,end):
    require(type(step) is int and step>=0 and type(n_iter) is int and n_iter>0,'scheduler indices')
    W=int(.1*n_iter);D=int(.1*n_iter);P=n_iter-W-D;K=W+P+D
    require(W>0 and D>0 and P>0 and all(math.isfinite(x) and x>=0 for x in (start,peak,end)),'scheduler boundaries')
    k=step%K;first=start if step<K else end
    if k<W:return first+(peak-first)*k/W
    if k<W+P:return peak
    return peak-(peak-end)*(k-W-P)/D


def validate_step_trace(trace,profile,expected=None,guard=None):
    fields(profile,('id','source','configuration','environment','W','P','D','K','start_lr','peak_lr','end_lr','native_formula','rank_count','accumulation','resume'))
    require(profile['K']==profile['W']+profile['P']+profile['D'],'cycle sum')
    require(profile['rank_count']>0 and profile['accumulation']>0,'rank/accumulation qualification')
    if profile['native_formula']:
        require(profile['W']==int(.1*profile['K']) and profile['D']==int(.1*profile['K']),'native integer boundary qualification')
    require(expected is not None and len(trace)==len(expected),'independent complete step census required')
    previous={}
    for i,row in enumerate(trace):
        if guard:guard()
        require(all(row[k]==expected[i][k] for k in row if k!='lr_applied'),'complete original trajectory')
        fields(row,('microbatch','optimizer_before','optimizer_after','scheduler_before','scheduler_after','rank','accumulation_index','overflow_skipped','lr_applied','windows','patches','samples','people_support','state_pin','state_before'))
        require(row['optimizer_after']-row['optimizer_before'] in (0,1),'optimizer clock')
        require(not row['overflow_skipped'] or row['optimizer_after']==row['optimizer_before'],'skipped update advanced')
        require(type(row['rank']) is int and 0<=row['rank']<profile['rank_count'] and 0<=row['accumulation_index']<profile['accumulation'],'rank/accumulation index')
        require(row['scheduler_after']-row['scheduler_before'] in (0,1),'scheduler clock')
        if row['rank'] in previous:
            prior=previous[row['rank']]
            require(row['microbatch']>prior['microbatch'] and row['optimizer_before']==prior['optimizer_after'] and row['scheduler_before']==prior['scheduler_after'],'per-rank complete clock continuity')
        if profile['native_formula']:
            expected_lr=native_trapezoid(row['scheduler_before'],profile['K'],profile['start_lr'],profile['peak_lr'],profile['end_lr'])
            require(all(abs(lr-expected_lr)<=1e-12*max(1,abs(expected_lr)) for lr in row['lr_applied']),'LR sequence mismatch')
        require(len(row['lr_applied'])==len(expected[i]['lr_applied'])>0,'full selected parameter-group LR support')
        require(all(abs(a-b)<=1e-12*max(1,abs(b)) for a,b in zip(row['lr_applied'],expected[i]['lr_applied'])),'independent selected LR sequence')
        previous[row['rank']]=row
    require(trace and set(previous)==set(range(profile['rank_count'])),'complete rank census')
    if guard:guard()
    return {'source':profile['source'],'entries':len(trace),'cyclicity_alone_is_not_failure':True,'historical_trace_recovered':False}
