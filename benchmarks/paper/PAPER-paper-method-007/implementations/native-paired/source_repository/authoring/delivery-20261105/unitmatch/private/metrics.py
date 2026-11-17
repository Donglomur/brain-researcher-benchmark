"""Future scientific grading only. Never imported by construction checks.

ISI source: v2.0 ComputeFunctionalScores.m:216-243. The explicit two-day
decoder and finite-value rank AUC are benchmark conventions, not MATLAB parity.
"""


def decode(probabilities, units):
    # Canonical one-to-one matching: descending bidirectional mean, then
    # canonical indices on ties. Only probability strictly greater than 0.5.
    pairs = [(0.5*(probabilities[i][j]+probabilities[j][i]),i,j)
        for i,a in enumerate(units) for j,b in enumerate(units)
        if a['session']==1 and b['session']==2]
    used1,used2,accepted = set(),set(),set()
    for probability,i,j in sorted(pairs,key=lambda x:(-x[0],x[1],x[2])):
        if probability>0.5 and i not in used1 and j not in used2:
            accepted.add((i,j)); used1.add(i); used2.add(j)
    return accepted


def reference(verified_sources, mouse):
    import numpy as np
    import h5py
    # Binary64 definition of source [0 5*10.^(-4:0.1:0)]; no native-bitwise claim.
    edges = np.r_[0., 5.*10.**np.linspace(-4.,0.,41)]
    first,second = [],[]
    for session in mouse['sessions']:
        source=verified_sources[session['source_prepared']]
        source.assert_stable()
        source.file.seek(0)
        with h5py.File(source.file,'r') as file:
            times = np.asarray(file['sp/st']).reshape(-1)
            clusters = np.asarray(file['sp/spikeTemplates']).reshape(-1)
        source.assert_stable()
        if len(times)!=len(clusters) or not np.isfinite(times).all():
            raise ValueError('invalid recorded spike arrays')
        for cid in session['good_cluster_ids']:
            # Preserve original recorded order and source MATLAB overlap at
            # the halfway spike; ceil(N/2) is 1-based in the source.
            selected = times[clusters==cid].astype(np.float64,copy=False)
            n=len(selected)
            if np.any(np.diff(selected)<0):
                raise ValueError('decreasing recorded spike times')
            if n<2:
                first.append(np.full(41,np.nan)); second.append(np.full(41,np.nan)); continue
            first.append(np.histogram(np.diff(selected[:n//2]),edges)[0])
            second.append(np.histogram(np.diff(selected[(n+1)//2-1:]),edges)[0])
    a,b = np.asarray(first,float),np.asarray(second,float)
    a-=a.mean(axis=1,keepdims=True); b-=b.mean(axis=1,keepdims=True)
    denom=np.linalg.norm(a,axis=1)[:,None]*np.linalg.norm(b,axis=1)[None,:]
    with np.errstate(divide='ignore',invalid='ignore'):
        corr=(a@b.T)/denom
    return np.clip(corr,-1.,1.)


def auc(positive, negative):
    import numpy as np
    from scipy.stats import rankdata
    a=np.asarray(positive,float);b=np.asarray(negative,float)
    a=a[np.isfinite(a)];b=b[np.isfinite(b)]
    if not len(a) or not len(b):return None,len(a),len(b)
    ranks=rankdata(np.r_[a,b],method='average')
    value=(ranks[:len(a)].sum()-len(a)*(len(a)+1)/2)/(len(a)*len(b))
    return float(value),len(a),len(b)


def score(matrix, mouse, correlations):
    units=mouse['units'];accepted=decode(matrix,units)
    positive=[];negative=[];within_positive=[];within_negative=[]
    for i,a in enumerate(units):
        for j,b in enumerate(units):
            value=correlations[i,j]
            if a['session']!=b['session']:
                pair=(i,j) if a['session']==1 else (j,i)
                (positive if pair in accepted else negative).append(value)
            else:
                (within_positive if i==j else within_negative).append(value)
    cross,valid_match,valid_nonmatch=auc(positive,negative)
    within,within_same,within_other=auc(within_positive,within_negative)
    count=len(accepted);minimum=min(len(s['good_cluster_ids']) for s in mouse['sessions'])
    # Twenty decoded matches follows the author summary's minimum. Forty finite
    # matched directions is a new coverage guard, not a native-paper criterion.
    eligible=count>=20 and valid_match>=40 and cross is not None
    return {'matches':count,'available_min_day_units':minimum,'stable_unit_yield':count/minimum,
        'isi_auc':cross,'isi_auc_eligible':eligible,'within_session_isi_auc':within,
        'finite_cross_match_directions':valid_match,'finite_cross_nonmatch_directions':valid_nonmatch,
        'finite_within_same':within_same,'finite_within_other':within_other,
        'undefined_cross_directions':len(positive)+len(negative)-valid_match-valid_nonmatch}
