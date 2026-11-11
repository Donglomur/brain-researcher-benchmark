"""Mouse-unit effects and held-mouse prediction, with explicit nuisance controls."""
from .contracts import require

def pair_design(rows,with_tuning):
    import numpy as np
    x=[]
    for r in rows:
        d=r['distance']/100
        z=[d,d*d,r['baseline'],r['movement'],r['power'],int(r['condition']=='nonresponding_site')]
        if with_tuning:
            z += [r['similarity'], r['similarity']*int(r['condition']=='nonresponding_site')]
        x.append(z)
    return np.asarray(x,dtype=float)

def held_mouse_improvement(rows,alpha):
    import numpy as np
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    all_mice=sorted({r['mouse'] for r in rows})
    before={m:sum(r['mouse']==m for r in rows) for m in all_mice}
    # A held-mouse response-derived site label would leak the held target.
    rows=[r for r in rows if r['classification_basis']=='independent_pretest']
    mice=sorted({r['mouse'] for r in rows})
    if len(mice)<3:
        return [{'mouse':m,'improvement':None,'status':'not_estimable',
                 'reason':'fewer than three mice with independent pretest site classification',
                 'response_selected_pairs_excluded':before[m]-sum(r['mouse']==m for r in rows)} for m in all_mice]
    result=[]
    for mouse in mice:
        train=[r for r in rows if r['mouse']!=mouse]
        test=[r for r in rows if r['mouse']==mouse]
        errors=[]
        for tune in (False,True):
            model=make_pipeline(StandardScaler(),Ridge(alpha=alpha,solver='svd'))
            # Each mouse contributes total weight one, irrespective of cell count.
            counts={m:sum(r['mouse']==m for r in train) for m in mice if m!=mouse}
            weights=np.asarray([1/counts[r['mouse']] for r in train])
            model.fit(pair_design(train,tune),np.asarray([r['response'] for r in train]),
                      ridge__sample_weight=weights)
            pred=model.predict(pair_design(test,tune))
            errors.append(float(np.mean((pred-[r['response'] for r in test])**2)))
        result.append({'mouse':mouse,'nuisance_mse':errors[0],'tuning_mse':errors[1],
                       'improvement':errors[0]-errors[1],'pairs':len(test),
                       'response_selected_pairs_excluded':before[mouse]-len(test)})
    result.extend({'mouse':m,'improvement':None,'status':'not_estimable',
                   'reason':'no independent pretest site classification',
                   'response_selected_pairs_excluded':before[m]} for m in all_mice if m not in mice)
    return result

def partial_effect(rows):
    import numpy as np
    effects=[]
    for mouse in sorted({r['mouse'] for r in rows}):
        r=[x for x in rows if x['mouse']==mouse]
        x=pair_design(r,False)
        x=np.column_stack((np.ones(len(r)),x))
        y=np.asarray([a['response'] for a in r])
        z=np.asarray([a['similarity'] for a in r])
        yr=y-x@np.linalg.lstsq(x,y,rcond=None)[0]
        zr=z-x@np.linalg.lstsq(x,z,rcond=None)[0]
        denom=float(zr@zr)
        zc=z-z.mean();yc=y-y.mean()
        rawdenom=float(zc@zc)
        unadjusted=float(zc@yc/rawdenom) if rawdenom>1e-12 else None
        if denom<=1e-12:
            effects.append({'mouse':mouse,'status':'not_estimable','effect':None,'unadjusted':unadjusted})
        else:
            effects.append({'mouse':mouse,'status':'estimated','effect':float(zr@yr/denom),'unadjusted':unadjusted})
    return effects

def matched_contrasts(rows,distance_edges,caliper):
    """Match high/low tuning within session/target/site/distance stratum.

    Fixed similarity cutoffs are protocol constants, not test-outcome selection.
    Greedy nearest matching is deterministic and reports every unmatched pair.
    """
    import numpy as np
    groups={}
    for i,r in enumerate(rows):
        b=next((j for j,(a,c) in enumerate(zip(distance_edges,distance_edges[1:]))
                if a<=r['distance']<c or (j==len(distance_edges)-2 and r['distance']==c)),None)
        if b is None:
            continue
        key=(r['mouse'],r['session'],r['target_id'],r['condition'],b)
        groups.setdefault(key,[]).append((i,r))
    pairs=[]
    for key,values in sorted(groups.items()):
        high=[(i,r) for i,r in values if r['similarity']>=caliper['high_similarity']]
        low={i:r for i,r in values if r['similarity']<=caliper['low_similarity']}
        for i,a in sorted(high):
            options=[]
            for j,b in low.items():
                d=[abs(a[k]-b[k])/caliper[k] if caliper[k]>0 else
                   (0 if a[k]==b[k] else float('inf')) for k in ('baseline','movement','power')]
                if max(d)<=1:
                    options.append((sum(d),j,b))
            if not options:
                continue
            _,j,b=min(options,key=lambda x:(x[0],x[1]))
            del low[j]
            pairs.append({'mouse':key[0],'high_row':i,'low_row':j,
                          'contrast':a['response']-b['response']})
    effect=[]
    for mouse in sorted({r['mouse'] for r in rows}):
        values=[p['contrast'] for p in pairs if p['mouse']==mouse]
        effect.append({'mouse':mouse,'contrast':float(np.mean(values)) if values else None,
                       'matched':len(values),'total_rows':sum(r['mouse']==mouse for r in rows)})
    unmatched=sorted(set(range(len(rows)))-{p[k] for p in pairs for k in ('high_row','low_row')})
    dispositions=[]
    for i in unmatched:
        r=rows[i]
        reason=('outside_matching_distance' if not distance_edges[0]<=r['distance']<=distance_edges[-1]
                else 'middle_tuning_stratum' if caliper['low_similarity']<r['similarity']<caliper['high_similarity']
                else 'no_available_opposite_stratum_within_calipers')
        dispositions.append({'row':i,'reason':reason})
    return {'pairs':pairs,'mouse_effects':effect,'unmatched_rows':unmatched,
            'unmatched_dispositions':dispositions}

def response_class_contrast(rows):
    """Observed site-class association, never a randomized class treatment effect."""
    import numpy as np
    result=[]
    for mouse in sorted({r['mouse'] for r in rows}):
        r=[x for x in rows if x['mouse']==mouse and x['condition'] in ('neuron_target','nonresponding_site')]
        z=np.asarray([int(x['condition']=='neuron_target') for x in r])
        if len(set(z.tolist()))!=2:
            result.append({'mouse':mouse,'status':'not_estimable','reason':'both site classes unavailable'})
            continue
        x=pair_design(r,False)[:,:-1];x=np.column_stack((np.ones(len(r)),x))
        y=np.asarray([a['response'] for a in r]);yr=y-x@np.linalg.lstsq(x,y,rcond=None)[0]
        zr=z-x@np.linalg.lstsq(x,z,rcond=None)[0];denom=float(zr@zr)
        result.append({'mouse':mouse,'unadjusted':float(y[z==1].mean()-y[z==0].mean()),
                       'adjusted':float(zr@yr/denom) if denom>1e-12 else None,
                       'status':'observational','pairs':len(r)})
    return result

def crossfit_matched(rows,distance_edges,caliper_scale):
    """Every held mouse uses only other-mouse cutoffs and covariate scales."""
    import numpy as np
    result=[]
    for mouse in sorted({r['mouse'] for r in rows}):
        training=[r for r in rows if r['mouse']!=mouse]
        testing=[r for r in rows if r['mouse']==mouse]
        require(training,'matching requires independent training mice')
        counts={m:sum(r['mouse']==m for r in training) for m in {r['mouse'] for r in training}}
        weights=np.asarray([1/counts[r['mouse']] for r in training]);weights/=weights.sum()
        caliper={}
        for key in ('baseline','movement','power'):
            v=np.asarray([r[key] for r in training]);mean=float(weights@v)
            caliper[key]=float(np.sqrt(weights@((v-mean)**2)))*caliper_scale
        order=np.argsort([r['similarity'] for r in training],kind='stable')
        values=np.asarray([r['similarity'] for r in training])[order]
        cdf=np.cumsum(weights[order])
        low,high=[values[min(int(np.searchsorted(cdf,q,side='left')),len(values)-1)] for q in (.25,.75)]
        if not low<high:
            result.append({'held_mouse':mouse,'status':'not_estimable',
                           'reason':'training tuning quartiles tied','unmatched_rows':list(range(len(testing)))})
            continue
        caliper.update(low_similarity=float(low),high_similarity=float(high))
        result.append({'held_mouse':mouse,'caliper':caliper,
                       'training_mice':sorted({r['mouse'] for r in training}),
                       'result':matched_contrasts(testing,distance_edges,caliper)})
    return result

def distance_sensitivity(rows):
    """Operational boundaries: [25,50), [50,100), [100,250], and >250 µm."""
    groups={'25_to_50':[],'50_to_100':[],'100_to_250':[],'over_250':[]}
    for r in rows:
        d=r['distance'];require(d>=25,'proximal rows must be dispositioned first')
        key='25_to_50' if d<50 else '50_to_100' if d<100 else '100_to_250' if d<=250 else 'over_250'
        groups[key].append(r)
    return {k:{'n_pairs':len(v),'effect':partial_effect(v) if v else [],
               'n_mice':len({r['mouse'] for r in v})} for k,v in groups.items()}

def uncertainty(mouse_values):
    import numpy as np
    from scipy.stats import t
    v=np.asarray(mouse_values,dtype=float)
    require(np.isfinite(v).all() and len(v)>=2,'mouse uncertainty requires at least two units')
    mean=float(v.mean()); se=float(v.std(ddof=1)/np.sqrt(len(v)))
    radius=float(t.ppf(.975,len(v)-1))*se
    return {'n_mice':len(v),'mean':mean,'ci95':[mean-radius,mean+radius],
            'method':'mouse t interval; approximate independent-mouse sampling, not causal proof'}
