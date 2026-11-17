"""Future artifact scoring. Never run during construction.

Decoder follows MARBLE rat_utils.py and CEBRA0.4.0 float-target KNNDecoder.
Alignment below is a NumPy-only adaptation of CEBRA0.4.0 helpers.py/metrics.py
(Copyright Mackenzie W. Mathis & Steffen Schneider, Apache-2.0; retained
originals/license under comparator_source). Numeric source
operations are retained; explicit degenerate/nonfinite guards are added.
"""


def arrays(captured):
    import numpy as np
    return {name:np.frombuffer(raw,dtype=h['dtype'],offset=h['offset']).reshape(h['shape'])
        for name,(raw,h) in captured.items()}


def alignment(embeddings,labels):
    import numpy as np
    minimum=min(float(np.min(y)) for y in labels);maximum=max(float(np.max(y)) for y in labels)
    if not minimum<maximum:raise ValueError('undefined consistency: constant pooled behavior')
    result=[]
    for embedding,label in zip(embeddings,labels):
        # Check before averaging: bin-size-dependent rounding must not make a
        # constant input look variable after normalization.
        if np.max(np.ptp(embedding,axis=0))==0:
            raise ValueError('undefined consistency: collapsed input embedding')
        digits=np.digitize(label,np.linspace(minimum,maximum,100))
        rows=[]
        for bin_index in range(100)[1:]:
            value=None
            for difference in (0,1,2):
                mask=abs(digits-bin_index)<=difference
                if mask.sum():value=embedding[mask].mean(axis=0);break
            if value is None:raise ValueError('undefined consistency: empty source position bin')
            norm=np.linalg.norm(value,axis=0)
            if not np.isfinite(norm) or norm==0:raise ValueError('undefined consistency: zero/nonfinite bin mean')
            rows.append(value/norm)
        rows=np.asarray(rows)
        # Prevent constant embeddings receiving a perfect force-finite R2.
        if np.max(np.ptp(rows,axis=0))==0:
            raise ValueError('undefined consistency: collapsed embedding')
        result.append(rows)
    return result


def score(embeddings,labels,spec):
    import numpy as np
    from sklearn.neighbors import KNeighborsRegressor
    from sklearn.linear_model import LinearRegression
    output={}
    for condition in spec['conditions']:
        rows=[];test_embeddings=[];test_positions=[]
        for rat in spec['rats']:
            name=rat['rat'];cut=rat['split_index'];target=labels[name]
            train_y=target[:cut-1,0];test_y=target[cut:-1,0]
            train_x=embeddings[f'{condition}-{name}-train-d32.npy']
            test_x=embeddings[f'{condition}-{name}-test-d32.npy']
            decoder=KNeighborsRegressor(n_neighbors=36,metric='cosine')
            prediction=decoder.fit(train_x,train_y).predict(test_x)
            errors=np.abs(prediction-test_y)
            if not np.isfinite(errors).all():raise ValueError('nonfinite decoded errors')
            rows.append({'rat':name,'samples':len(test_y),'mae_m':float(errors.mean()),'median_absolute_error_m':float(np.median(errors))})
            test_embeddings.append(embeddings[f'{condition}-{name}-test-d3.npy']);test_positions.append(test_y)
        consistent=[];reason=None
        try:
            aligned=alignment(test_embeddings,test_positions)
            for i,a in enumerate(aligned):
                for j,b in enumerate(aligned):
                    if i==j:continue
                    value=float(LinearRegression().fit(a,b).score(a,b))
                    if not np.isfinite(value):raise ValueError('undefined consistency: nonfinite R2')
                    consistent.append({'source':spec['rats'][i]['rat'],'target':spec['rats'][j]['rat'],'r2':value})
        except ValueError as error:
            consistent=[];reason=str(error)
        output[condition]={'decoding_per_rat':rows,'equal_rat_mae_m':sum(x['mae_m'] for x in rows)/len(rows),
            'consistency_12_directions':consistent,'mean_consistency_r2':sum(x['r2'] for x in consistent)/12 if len(consistent)==12 else None,
            'undefined_consistency_reason':reason}
    return output


def improvement(candidate,baseline):
    clean_ok=all(c['mae_m']<=b['mae_m'] for c,b in zip(candidate['clean']['decoding_per_rat'],baseline['clean']['decoding_per_rat']))
    half_ok=all(c['mae_m']<=b['mae_m'] for c,b in zip(candidate['half']['decoding_per_rat'],baseline['half']['decoding_per_rat']))
    strictly_better=candidate['half']['equal_rat_mae_m']<baseline['half']['equal_rat_mae_m']
    consistency_ok=all(candidate[k]['mean_consistency_r2'] is not None and baseline[k]['mean_consistency_r2'] is not None
        and candidate[k]['mean_consistency_r2']>=baseline[k]['mean_consistency_r2'] for k in ('clean','half'))
    return {'clean_error_nondegrading_every_rat':clean_ok,'half_error_nondegrading_every_rat':half_ok,
        'half_equal_rat_error_strictly_better':strictly_better,'consistency_nondegrading_both_conditions':consistency_ok,
        'improvement_condition':bool(clean_ok and half_ok and strictly_better and consistency_ok)}
