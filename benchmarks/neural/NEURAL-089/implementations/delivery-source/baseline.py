"""Prospective streaming temporal-bin logistic baseline SOURCE, not author CNN.

Five fixed SGD epochs, alpha1e-4, no tuning or validation/query fitting.
Training-only feature scaling is fitted in a separate pass before classifier
updates. No model was fit during package construction.
"""
import argparse
import hashlib
from pathlib import Path
from io_contract import TASK, need, strict, read, write


def features(windows):
    import numpy as np
    x = np.asarray(windows)
    need(x.ndim == 3 and x.shape[1:] == (306,125) and np.isfinite(x).all(), "complete fixed MEG windows")
    return x.astype(np.float64).reshape(len(x),306,5,25).mean(axis=3).reshape(len(x),1530)


def iter_partition(root, manifest, partition, batch_size=128):
    import h5py
    import numpy as np
    for row in manifest["runs"]:
        if row["partition"] != partition: continue
        path = root/row["path"]
        need(path.resolve().parent == root.resolve() and not path.is_symlink()
             and path.stat().st_size == row["bytes"], "local pinned prepared run")
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
        need(digest.hexdigest()==row['sha256'],'prepared input SHA256')
        with h5py.File(path,'r') as source:
            labeled=partition!='query'
            need(set(source)==({'windows','ids','labels'} if labeled else {'windows','ids'}), 'target-free query members')
            need(source['windows'].shape==(row['windows'],306,125) and source['windows'].dtype==np.dtype('<f4')
                 and source['ids'].shape==(row['windows'],) and source['ids'].dtype==np.dtype('S24'), 'fixed prepared schema')
            if labeled:need(source['labels'].shape==(row['windows'],),'training label alignment')
            for start in range(0,row['windows'],batch_size):
                ids=[x.decode('ascii') for x in source['ids'][start:start+batch_size]]
                x=features(source['windows'][start:start+batch_size])
                y=source['labels'][start:start+batch_size] if labeled else None
                if labeled:need(np.issubdtype(y.dtype,np.integer) and ((y>=0)&(y<39)).all(),'39-class training labels')
                yield ids,x,y


def factories():
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import SGDClassifier
    return StandardScaler(), SGDClassifier(loss='log_loss',penalty='l2',alpha=1e-4,fit_intercept=True,
        learning_rate='optimal',random_state=89,shuffle=False,average=False,tol=None,max_iter=1)


def fit_training(training_batches, make=factories):
    import numpy as np
    scaler,model=make();seen=0
    for _,x,y in training_batches():
        need(y is not None and len(x)==len(y),'labeled training batch');scaler.partial_fit(x);seen+=len(x)
    need(seen>0,'nonempty complete training partition')
    for epoch in range(5):
        count=0
        for _,x,y in training_batches():
            model.partial_fit(scaler.transform(x),y,classes=np.arange(39));count+=len(x)
        need(count==seen,'same complete training set every fixed epoch')
    need(list(model.classes_)==list(range(39)),'fixed39-class model order')
    return scaler,model


def predict_queries(query_batches, scaler, model):
    import numpy as np
    rows=[];seen=set()
    for ids,x,y in query_batches:
        need(y is None,'query labels prohibited')
        probabilities=np.asarray(model.predict_proba(scaler.transform(x)),dtype=np.float64)
        need(probabilities.shape==(len(ids),39) and np.isfinite(probabilities).all()
             and ((probabilities>=0)&(probabilities<=1)).all()
             and np.allclose(probabilities.sum(axis=1),1.,rtol=0,atol=1e-6),'39-probability simplex')
        for q,p in zip(ids,probabilities):
            need(q not in seen,'unique query IDs');seen.add(q);rows.append({'query_id':q,'probabilities':p.tolist()})
    return {'schema_version':1,'task_id':TASK,'predictions':rows}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    manifest=strict(read(a.input/'inputs.json',1000000))
    need(manifest['task_id']==TASK,'task identity')
    scaler,model=fit_training(lambda:iter_partition(a.input,manifest,'train'))
    result=predict_queries(iter_partition(a.input,manifest,'query'),scaler,model)
    panel=strict(read(a.input/'panel.json'));need({r['query_id'] for r in result['predictions']}==set(panel['query_ids']),'complete query panel')
    write(a.output,result)


if __name__=='__main__':main()
