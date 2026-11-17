"""Future fixed analysis reference. Importing does not fit a model.

This analysis receives experimental labels, but each fitted decoder excludes
the query participant AND every query image identity. It is not task097's
unknown-label agent interface. No original source-space/pseudotrial parity.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from protocol import WINDOWS,MAPPINGS,AVAILABLE,CELL_KEYS,RELEVANCE,DURATIONS,ORIENTATIONS,validate_rows,validate_packet,split,training_weights,contrasts


def validate_features(x,rows):
    import numpy as np
    x=np.asarray(x,dtype=np.float64)
    if x.shape!=(len(rows),5,6):raise ValueError('canonical feature shape')
    for i,r in enumerate(rows):
        for j,w in enumerate(WINDOWS):
            if w in AVAILABLE[r['duration_ms']]:
                if not np.isfinite(x[i,j]).all():raise ValueError('required observed feature missing/nonfinite')
            elif not np.isnan(x[i,j]).all():raise ValueError('unrequested later windows must be structurally absent')
    return x


def predict_all(x,rows,participants,model_factory=None):
    import numpy as np
    validate_rows(rows,participants)
    x=validate_features(x,rows)
    if model_factory is None:
        from sklearn.linear_model import LogisticRegression
        model_factory=lambda:LogisticRegression(C=1.,solver='liblinear',tol=1e-8,max_iter=2000,random_state=98098)
    out=np.full((len(rows),len(MAPPINGS)),np.nan)
    win=list(WINDOWS);y=np.array([r['category'] for r in rows])
    for held in participants:
        for half in (0,1):
            train,test=split(rows,held,half);weight=np.array(training_weights(rows,train))
            for source in WINDOWS:
                tr=x[train,win.index(source),:];mean=tr.mean(axis=0);sd=tr.std(axis=0);sd=np.where(sd==0,1.,sd)
                if not np.isfinite(mean).all() or not np.isfinite(sd).all():raise ValueError('unrepresentable training moments')
                model=model_factory();model.fit((tr-mean)/sd,y[train],sample_weight=weight)
                if not np.array_equal(model.classes_,[0,1]):raise ValueError('reference classes')
                if hasattr(model,'n_iter_') and int(np.max(model.n_iter_))>=2000:raise ValueError('reference convergence not established')
                for j,(a,b) in enumerate(MAPPINGS):
                    if a!=source:continue
                    query=[i for i in test if b in AVAILABLE[rows[i]['duration_ms']]]
                    probabilities=np.asarray(model.predict_proba((x[query,win.index(b),:]-mean)/sd),float)
                    if probabilities.shape!=(len(query),2) or not np.isfinite(probabilities).all() or np.any(probabilities<0) or np.any(probabilities>1) or not np.allclose(probabilities.sum(axis=1),1,atol=1e-10,rtol=0):raise ValueError('reference probability contract')
                    out[query,j]=probabilities[:,1]
    for i,r in enumerate(rows):
        for j,(_,b) in enumerate(MAPPINGS):
            if (b in AVAILABLE[r['duration_ms']])!=bool(np.isfinite(out[i,j])):raise ValueError('prediction availability mismatch')
    return out


def aggregate(probabilities,rows,participants):
    import numpy as np
    validate_rows(rows,participants);p=np.asarray(probabilities,float)
    if p.shape!=(len(rows),len(MAPPINGS)):raise ValueError('prediction shape')
    for i,r in enumerate(rows):
        for j,(_,b) in enumerate(MAPPINGS):
            if b in AVAILABLE[r['duration_ms']]:
                if not np.isfinite(p[i,j]) or not 0<=p[i,j]<=1:raise ValueError('complete probabilities')
            elif not np.isnan(p[i,j]):raise ValueError('unrequested prediction must be absent')
    result={}
    for person in participants:
        cells={}
        for r in RELEVANCE:
            for d in DURATIONS:
                for j,(a,b) in enumerate(MAPPINGS):
                    if b not in AVAILABLE[d]:continue
                    recalls=[]
                    for c in (0,1):
                        for o in ORIENTATIONS:
                            ids=[i for i,row in enumerate(rows) if row['participant']==person and row['relevance']==r and row['duration_ms']==d and row['category']==c and row['orientation']==o]
                            # Each observed trial is queried exactly once across identity halves.
                            recalls.append(float(np.mean((p[ids,j]>=.5)==c)))
                    cells[f'{r}|{d}|{a}>{b}']=sum(recalls)/6
        result[person]={'cells':cells,'contrasts':contrasts(cells)}
    return {'schema':'neural098-analysis-v1','participants':result}


def main():
    import argparse
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'private'))
    from io_utils import read_json,read_features,write_json
    ap=argparse.ArgumentParser();ap.add_argument('--packet',type=Path,required=True);ap.add_argument('--packet-sha256',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    if a.output.exists() or a.output.is_symlink():raise ValueError('fresh output required')
    packet,_=read_json(a.packet,expected=a.packet_sha256)
    participants=read_json(Path(__file__).resolve().parents[1]/'public/COHORT.json')[0]['participants']
    validate_packet(packet,participants)
    x=read_features(a.packet.with_name('features.npy'),packet['features_sha256'],len(packet['rows']))
    write_json(a.output,aggregate(predict_all(x,packet['rows'],participants),packet['rows'],participants))


if __name__=='__main__':main()
