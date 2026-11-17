"""Scientific negative-control source, authored but never executed in construction."""
from .contracts import require

def block_label_rotation(rows,train_indices):
    """Deterministic whole-block label null; diagnostic, not a permutation p-value."""
    copied=[dict(r) for r in rows]
    sessions=sorted({(rows[i]['mouse'],rows[i]['session']) for i in train_indices})
    changed=[]
    for session in sessions:
        ids=[i for i in train_indices if (rows[i]['mouse'],rows[i]['session'])==session]
        blocks=sorted({rows[i]['block'] for i in ids},key=lambda b:min(rows[i]['time'] for i in ids if rows[i]['block']==b))
        require(len(blocks)>1,'insufficient blocks for null')
        labels=[]
        for block in blocks:
            values={rows[i]['y'] for i in ids if rows[i]['block']==block}
            require(len(values)==1,'mixed-direction source block; explicit regrouping needed')
            labels.append(next(iter(values)))
        for j,block in enumerate(blocks):
            for i in ids:
                if rows[i]['block']==block:
                    copied[i]['y']=labels[(j+1)%len(labels)];changed.append(i)
    require(set(changed)==set(train_indices),'null touched wrong rows')
    return copied

def tuning_rotation(rows):
    """Within mouse/session/site/distance-stratum tuning negative control."""
    groups={}
    for i,r in enumerate(rows):
        d=r['distance'];b=0 if d<50 else 1 if d<100 else 2 if d<=250 else 3
        groups.setdefault((r['mouse'],r['session'],r['condition'],b),[]).append(i)
    out=[dict(r) for r in rows];coverage=[]
    for key,ids in sorted(groups.items()):
        if len(ids)<2:
            coverage.append({'stratum':list(key),'status':'unavailable','rows':len(ids)})
            continue
        for j,i in enumerate(ids):
            out[i]['similarity']=rows[ids[(j+1)%len(ids)]]['similarity']
        coverage.append({'stratum':list(key),'status':'rotated','rows':len(ids)})
    return out,coverage
