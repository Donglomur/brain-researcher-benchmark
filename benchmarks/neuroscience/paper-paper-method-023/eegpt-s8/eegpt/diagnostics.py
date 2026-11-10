"""Complete numerical scientific companions, only in authorized workers.

These functions never turn a paper image or favorable claim into a target.
Full original indices, null supports and independently fixed recipes survive.
"""
from .protocol import need,fields,finite,identity,digest


def channel_similarity(embedding,channel_ids,layout,equality_policy):
    import numpy as np
    a=np.asarray(embedding,dtype=np.float64);need(a.ndim==2 and a.shape[0]==58 and len(channel_ids)==58 and len(set(channel_ids))==58 and np.isfinite(a).all(),'complete ordered58-channel learned embedding')
    need(equality_policy in ('prose_strict','caption_inclusive'),'explicit independently qualified original threshold semantics')
    norm=np.linalg.norm(a,axis=1);valid=norm>0;den=norm[:,None]*norm[None,:];cosine=np.full((58,58),np.nan);np.divide(a@a.T,den,out=cosine,where=den>0);need(np.isfinite(cosine[valid[:,None]&valid[None,:]]).all(),'finite defined cosine support')
    compare=(lambda value,threshold:value>threshold) if equality_policy=='prose_strict' else (lambda value,threshold:value>=threshold)
    edges={key:[] for key in ('high_0.5','high_0.4','high_0.3','band_0.1_0.3')}
    for i in range(58):
        for j in range(i+1,58):
            if not valid[i] or not valid[j]:continue
            value=float(cosine[i,j])
            for key,threshold in (('high_0.5',.5),('high_0.4',.4),('high_0.3',.3)):
                if compare(value,threshold):edges[key].append([channel_ids[i],channel_ids[j]])
            if .1<value<=.3:edges['band_0.1_0.3'].append([channel_ids[i],channel_ids[j]])
    # Undefined cells are accompanied by an explicit mask; the portable finite
    # array stores0 only where mask=false, never a claimed zero correlation.
    mask=valid[:,None]&valid[None,:];stored=np.where(mask,cosine,0.)
    return {'channel_ids':channel_ids,'cosines':stored,'defined':mask,'zero_norm':[channel_ids[i] for i in range(58) if not valid[i]],'edges':edges,'physical_layout':layout,'equality_policy':equality_policy,'functional_connectivity_or_causal_interpretation':False}


def pearson_sufficient(x,y):
    import numpy as np
    a=np.asarray(x,dtype=np.float64);b=np.asarray(y,dtype=np.float64);need(a.shape==b.shape and a.ndim==1 and len(a)>0 and np.isfinite(a).all() and np.isfinite(b).all(),'all planned noise/delta pairs')
    # Centered sufficient sums avoid large-offset cancellation; keep anchors,
    # original counts, means and sums so the result is independently auditable.
    ac=a-a[0];bc=b-b[0];ma=ac.mean();mb=bc.mean();da=ac-ma;db=bc-mb;sxx=float(da@da);syy=float(db@db);sxy=float(da@db)
    return {'n':len(a),'anchor_x':float(a[0]),'anchor_y':float(b[0]),'mean_centered_x':float(ma),'mean_centered_y':float(mb),'sum_xx':sxx,'sum_yy':syy,'sum_xy':sxy,'pearson':None if sxx==0 or syy==0 else sxy/(sxx*syy)**.5,'undefined_reason':'zero variance' if sxx==0 or syy==0 else None}


def perturbation(model,epochs,plan,*,device):
    import numpy as np
    import torch
    fields(plan,('row_ids','channel_ids','draw_ids','distribution','seed','state_identity','qualification'),'complete prospective perturbation plan');digest(plan['qualification'])
    x=np.asarray(epochs);need(x.ndim==3 and len(x)==len(plan['row_ids']) and x.shape[1]==len(plan['channel_ids']),'whole selected query population and original channel axis')
    fields(plan['distribution'],('kind','mean','standard_deviation'),'fixed multiplicative noise law');need(plan['distribution']['kind']=='normal' and plan['distribution']['standard_deviation']>0,'predeclared Gaussian multiplicative noise, no guessed historical parameters')
    rng=np.random.default_rng(plan['seed']);model.eval()
    def logits(value):
        output=model(value);output=output[-1] if isinstance(output,tuple) else output;need(isinstance(output,torch.Tensor) and output.ndim==2,'qualified actual full-class logits ABI');return output
    with torch.no_grad():baseline=logits(torch.as_tensor(x,dtype=torch.float32,device=device)).detach().double().cpu().numpy()
    need(baseline.ndim==2 and len(baseline)==len(x),'full original class logits');records=[]
    for channel in range(x.shape[1]):
        all_noise=[];all_delta=[]
        for draw in plan['draw_ids']:
            noise=rng.normal(plan['distribution']['mean'],plan['distribution']['standard_deviation'],size=len(x));changed=x.copy();changed[:,channel,:]*=(1+noise[:,None])
            with torch.no_grad():changed_logits=logits(torch.as_tensor(changed,dtype=torch.float32,device=device)).detach().double().cpu().numpy()
            observed_logits=changed_logits
            need(observed_logits.shape==baseline.shape and np.isfinite(observed_logits).all(),'full perturbed logits');delta=observed_logits-baseline;all_noise.append(noise);all_delta.append(delta)
            records.append({'channel':plan['channel_ids'][channel],'draw':draw,'noise':noise,'baseline_logits':baseline,'perturbed_logits':observed_logits,'delta':delta})
        noise=np.concatenate(all_noise);deltas=np.concatenate(all_delta,axis=0)
        records.append({'channel':plan['channel_ids'][channel],'summary':[pearson_sufficient(noise,deltas[:,k]) for k in range(baseline.shape[1])]})
    return {'plan':plan,'baseline':baseline,'all_records':records,'causal_interpretation':False}


def representation(features,plan):
    import numpy as np
    from sklearn.manifold import TSNE
    fields(plan,('row_ids','layer','pooling','metric','perplexity','initialization','learning_rate','iterations','seed','implementation_identity','qualification'),'complete fixed tSNE recipe');digest(plan['qualification']);digest(plan['implementation_identity'])
    a=np.asarray(features,dtype=np.float64);need(a.ndim==2 and len(a)==len(plan['row_ids']) and np.isfinite(a).all(),'complete label-free feature matrix');need(0<plan['perplexity']<len(a),'fullpopulation valid selected perplexity')
    coordinates=TSNE(n_components=2,metric=plan['metric'],perplexity=plan['perplexity'],init=plan['initialization'],learning_rate=plan['learning_rate'],max_iter=plan['iterations'],random_state=plan['seed'],method='exact').fit_transform(a)
    return {'row_ids':plan['row_ids'],'features':a,'coordinates':coordinates,'recipe':plan,'labels_used':False,'linear_separability_proof':False}


def attention_summary(weights,valid_mask,plan):
    import numpy as np
    fields(plan,('axes','aggregation','layer_ids','head_ids','query_rows','key_tokens','time_origin','channels','qualification'),'complete attention query recipe');digest(plan['qualification'])
    a=np.asarray(weights,dtype=np.float64);mask=np.asarray(valid_mask,dtype=bool);shape=[len(plan['axes'][k]) for k in plan['aggregation']['axis_order']]
    need(list(a.shape)==shape and mask.shape==a.shape and np.isfinite(a).all() and (a>=0).all(),'every original layer/head/query/key/time/channel cell and valid token mask')
    need(np.all(a[~mask]==0),'masked attention cannot carry unreported weight');key_axis=plan['aggregation']['axis_order'].index('key');sums=a.sum(axis=key_axis);defined=mask.any(axis=key_axis)
    need(np.allclose(sums[defined],1.,atol=1e-6,rtol=0),'full valid attention row normalization')
    axes=tuple(plan['aggregation']['axis_order'].index(k) for k in plan['aggregation']['mean_axes']);count=mask.sum(axis=axes);total=np.where(mask,a,0).sum(axis=axes);mean=np.zeros_like(total);np.divide(total,count,out=mean,where=count>0)
    return {'full_weights':a,'valid_mask':mask,'summary':mean,'summary_defined':count>0,'counts':count,'recipe':plan,'causal_or_ERP_mechanism_proof':False}


def scaling(points,recipe):
    import numpy as np
    fields(recipe,('point_ids','x_field','y_field','x_transform','y_transform','formula','parameter_convention','qualification'),'complete predeclared scaling regression');digest(recipe['qualification'])
    need([p['id'] for p in points]==recipe['point_ids'] and len(points) in (4,8),'all original size or data-fraction points')
    need(recipe['formula']=='ordinary_least_squares_intercept_slope' and recipe['x_transform'] in ('identity','log') and recipe['y_transform'] in ('identity','log'),'explicit prospective curve, no guessed historical fit')
    x=np.asarray([p[recipe['x_field']] for p in points],dtype=np.float64);y=np.asarray([p[recipe['y_field']] for p in points],dtype=np.float64);need(np.isfinite(x).all() and np.isfinite(y).all(),'complete finite source values')
    if recipe['x_transform']=='log':need((x>0).all(),'positive log-domain size/fraction');x=np.log(x)
    if recipe['y_transform']=='log':need((y>0).all(),'positive log-domain response');y=np.log(y)
    design=np.column_stack((np.ones(len(x)),x));parameters,_,rank,_=np.linalg.lstsq(design,y,rcond=None);need(rank==2,'identified intercept/slope');residual=y-design@parameters
    return {'points':points,'recipe':recipe,'parameters':parameters,'residuals':residual,'n_model_points':len(points),'independent_biological_sample_count':None,'extrapolated_frontier_claim':False}


def loss_reduction(rows,variant):
    need(variant in ('A','B','C','D'),'full selected loss ablation');groups={}
    for row in rows:
        key=(row['partition'],row['epoch']);g=groups.setdefault(key,{'LA_numerator':0.,'LA_denominator':0,'LR_numerator':0.,'LR_denominator':0,'steps':[]})
        need(row['id'] not in g['steps'],'every original loss observation once');g['steps'].append(row['id'])
        for k in ('LA_numerator','LR_numerator'):g[k]+=finite(row[k],k)
        for k in ('LA_denominator','LR_denominator'):need(type(row[k]) is int and row[k]>0,'positive original loss denominator');g[k]+=row[k]
    out=[]
    for (partition,epoch),g in sorted(groups.items()):
        la=g['LA_numerator']/g['LA_denominator'];lr=g['LR_numerator']/g['LR_denominator'];out.append({'partition':partition,'epoch':epoch,**g,'LA':la,'LR':lr,'total':lr if variant=='A' else la+lr})
    return out
