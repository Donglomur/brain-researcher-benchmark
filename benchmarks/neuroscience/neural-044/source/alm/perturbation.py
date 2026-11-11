"""Full-schedule finite-lag response reference; never isolate overlapping pulses.

This is a benchmark-defined associational estimator, not a reproduced missing
DataJoint method or proof of monosynaptic connection. No fitting occurs on import.
"""
from .contracts import require

def lag_design(start, stop, stimuli, targets, edges, lead=False):
    import numpy as np
    require(len(edges)>=2 and all(a<b for a,b in zip(edges,edges[1:])), 'lag bin order')
    require(np.all(stop>start),'exposure interval for design')
    x = np.zeros((len(start),len(targets)*(len(edges)-1)), dtype=float)
    lookup = {t:i for i,t in enumerate(targets)}
    for event in stimuli:
        event_key=(event['target_id'],event['power_mw'],event['condition'])
        require(event_key in lookup, 'event missing from complete target/power/condition design')
        j = lookup[event_key]*(len(edges)-1)
        for k,(a,b) in enumerate(zip(edges,edges[1:])):
            left,right=(event['on']-b,event['on']-a) if lead else (event['on']+a,event['on']+b)
            # Integrate the prespecified onset-lag basis across each exposure,
            # rather than assigning a possibly straddling frame to its midpoint.
            x[:,j+k] += np.maximum(0,np.minimum(stop,right)-np.maximum(start,left))/(stop-start)
    return x

def fit_responses(recording, protocol):
    import numpy as np
    from sklearn.linear_model import Ridge
    stimuli = recording['stimuli']
    require(stimuli, 'no stimulation recording')
    target_rows = {r['target_id']:r for r in recording['targets']}
    rows, audit = [], []
    edges = protocol['lag_edges']
    require(edges == [i/10 for i in range(11)], 'fixed ten 100-ms lag bins through one second')
    baseline={}
    for link in recording['cell_links']:
        epoch,plane,roi_id=link['baseline_roi']
        bp=next(p for p in recording['planes'] if p['epoch']==epoch and p['id']==plane)
        require(not any(s['epoch']==epoch for s in stimuli), 'baseline must precede all stimulation in separate epoch')
        require(bp['exposure_end'][-1] < min(s['on'] for s in stimuli), 'baseline is not prestimulation')
        j=next(i for i,r in enumerate(bp['roi']) if r['roi_id']==roi_id)
        valid=(bp['artifact']==0)&(bp['support_start']>=recording['epoch_bounds'][epoch][0])&(
               bp['support_end']<=recording['epoch_bounds'][epoch][1])
        require(int(valid.sum())>=protocol['baseline_min_frames'], 'insufficient independent baseline')
        baseline[tuple(link['rest_roi'])]=float(bp['values'][valid,j].mean())
    for p in recording['planes']:
        events = [s for s in stimuli if s['epoch']==p['epoch']]
        if not events:
            continue
        targets = sorted({(s['target_id'],s['power_mw'],s['condition']) for s in events})
        k = len(edges)-1
        expected_design = len(p['values'])*(len(targets)*k+4)*8
        require(expected_design <= protocol['max_design_bytes'], 'complete design exceeds budget; no subsampling')
        mid = (p['exposure_start']+p['exposure_end'])/2
        keep = ((p['artifact']==0)&(p['support_end']<=p['exposure_end']) &
                (mid>=min(s['on'] for s in events)+edges[-1]) &
                (mid<max(s['off'] for s in events)-edges[-1]))
        require(int(keep.sum()) > len(targets)*k+4, 'insufficient independent design rows')
        t=mid[keep]
        motion=p['movement'][keep]
        trend=(t-t.mean())/max(float(t.std()),1e-12)
        nuisance=np.column_stack((trend,trend**2,motion,motion**2))
        y=p['values'][keep]
        for control in ('lagged','lead_null'):
            x=lag_design(p['exposure_start'][keep],p['exposure_end'][keep],
                         events,targets,edges,lead=control=='lead_null')
            x=np.column_stack((x,nuisance))
            # Fixed regularization, never optimized against the reported effect.
            model=Ridge(alpha=protocol['ridge_alpha'],solver='svd')
            model.fit(x,y)
            singular=np.linalg.svd(np.column_stack((np.ones(len(x)),x)),compute_uv=False)
            rank=int(np.linalg.matrix_rank(np.column_stack((np.ones(len(x)),x))))
            condition_number=float(singular[0]/singular[-1]) if singular[-1]>0 else None
            beta=model.coef_[:,:len(targets)*k].reshape(y.shape[1],len(targets),k)
            widths=np.diff(edges)
            response=(beta*widths).sum(axis=2)/widths.sum()
            for j,(target,power,site_condition) in enumerate(targets):
                ev=[s for s in events if (s['target_id'],s['power_mw'],s['condition'])==(target,power,site_condition)]
                # Power/condition strata retain separate columns, including a
                # zero-power true sham if and only if the source actually has it.
                for i,roi in enumerate(p['roi']):
                    rows.append({'mouse':recording['mouse'],'session':recording['session'],
                        'epoch':p['epoch'],'target_id':target,'follower_roi':[p['epoch'],p['id'],roi['roi_id']],
                        'follower_xyz':[roi['x'],roi['y'],roi['z']],
                        'target_xyz':[target_rows[target][a] for a in ('x','y','z')],
                        'target_cell_id':target_rows[target]['cell_id'],
                        'condition':site_condition,
                        'classification_basis':target_rows[target]['classification_basis'],
                        'response':float(response[i,j]),
                        'baseline':baseline.get((p['epoch'],p['id'],roi['roi_id'])),
                        'movement':float(motion.mean()),'power':power,
                        'power_levels':[power],'control':control,'pulses':len(ev),
                        'direct_target':target_rows[target]['cell_id'] is not None and
                          any(l['cell_id']==target_rows[target]['cell_id'] and
                              l['rest_roi']==[p['epoch'],p['id'],roi['roi_id']] for l in recording['cell_links'])})
            audit.append({'plane':p['id'],'epoch':p['epoch'],'control':control,
                          'targets':len(targets),'lag_bins':k,'frames':len(t),
                          'rank_with_intercept':rank,'columns_with_intercept':x.shape[1]+1,
                          'condition_number':condition_number,
                          'identified_unregularized':rank==x.shape[1]+1,
                          'design_bytes':int(x.nbytes),'responses':int(response.size),
                          'residual_df_not_claimed':True})
    return rows,audit

def join_tuning(recording,responses,tuning,minimum_distance):
    import numpy as np
    links={tuple(l['rest_roi']):l['cell_id'] for l in recording['cell_links']}
    rows,dispositions=[],[]
    for row in responses:
        follower=links.get(tuple(row['follower_roi']))
        target=row['target_cell_id']
        distance=float(np.linalg.norm(np.asarray(row['target_xyz'])-row['follower_xyz']))
        reason=None
        if row['direct_target'] or distance<minimum_distance:
            reason='direct_or_optically_proximal_target'
        elif follower not in tuning or target not in tuning:
            reason='tuning_missing_for_target_or_follower'
        elif row['baseline'] is None:
            reason='independent_baseline_cell_identity_missing'
        if reason:
            dispositions.append({'target':row['target_id'],'follower':row['follower_roi'],
                                  'control':row['control'],'reason':reason})
            continue
        rows.append({**row,'distance':distance,'follower_cell_id':follower,
                     'similarity':float(tuning[target]@tuning[follower])})
    require(len(rows)+len(dispositions)==len(responses),'pair disposition inverse')
    return rows,dispositions
