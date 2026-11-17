"""Future training-only comparator construction; NEVER invoked during package build.

This is a prospective refit protocol, not a replay of published checkpoints.
Every data file is captured/pin checked; held-out behavior never enters a fit.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys
from interface import captured_at,npy_header


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--method',choices=['marble','cebra-time','cebra-behavior'],required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--work',type=Path,required=True,help='Fresh model/checkpoint workspace')
    p.add_argument('--execute-future-training',action='store_true')
    a=p.parse_args()
    if not a.execute_future_training:raise ValueError('future scientific training requires explicit invocation')
    if a.output.exists() or a.work.exists():raise ValueError('fresh output and model workspace required')
    root=a.root.resolve();spec=json.loads((root/'public/protocol.json').read_text())
    assets={row['path']:row for row in json.loads((root/'private/ASSETS.json').read_text())['files']}
    def load(relative,shape):
        path=Path(relative);fd=os.open(root/path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:raw,digest=captured_at(fd,path.name,20_000_000)
        finally:os.close(fd)
        if digest!=assets[relative]['sha256']:raise ValueError('operator input pin mismatch')
        h=npy_header(raw,shape)
        return np.frombuffer(raw,dtype=h['dtype'],offset=h['offset']).reshape(shape).copy()
    # Imports below are intentionally absent from all generated checks.
    import numpy as np
    import torch
    import cebra
    sys.path.insert(0,str(root/'private/author_source'))
    sys.path.insert(0,str(root/'private/author_source/examples/rat_hippocampus'))
    a.output.mkdir(parents=True);a.work.mkdir(parents=True)
    receipt=[]
    for condition in spec['conditions']:
        for rat in spec['rats']:
            name=rat['rat'];cut=rat['split_index'];n=rat['raw_samples']
            channels=rat['neurons'] if condition=='clean' else len(rat['half_columns_zero_based'])
            train=load(f'public/input/{condition}-{name}-train.npy',(cut,channels))
            test=load(f'public/input/{condition}-{name}-test.npy',(n-cut,channels))
            # A separate train-only file is materialized from original labels in memory;
            # full original labels are operator-only. No test behavior enters fit/transform.
            train_labels=None
            if a.method=='cebra-behavior':
                train_labels=load(f'private/labels/{name}.npy',(n,3))[:cut].copy()
            for dim in spec['embedding_dimensions']:
                random.seed(0);np.random.seed(0);torch.manual_seed(0)
                if torch.cuda.is_available():torch.cuda.manual_seed_all(0)
                stem=f'{condition}-{name}-d{dim}';work=a.work/stem
                if a.method=='marble':
                    import MARBLE
                    from rat_utils import convert_spikes_to_rates
                    train_graph,_,pca=convert_spikes_to_rates(train.T,pca_n=20 if dim==32 else 10,kernel_width=10)
                    params={'epochs':100,'order':1,'hidden_channels':[64],'out_channels':dim,
                        'inner_product_features':False,'emb_norm':True,'diffusion':False,'include_positions':True,'seed':0}
                    model=MARBLE.net(train_graph,params=params.copy())
                    model.fit(train_graph,outdir=str(work))
                    train_embedding=model.transform(train_graph).emb.detach().cpu().numpy()
                    # New query graph, training-fitted PCA and frozen learned weights.
                    test_graph,_,_=convert_spikes_to_rates(test.T,pca=pca,kernel_width=10)
                    test_embedding=model.transform(test_graph).emb.detach().cpu().numpy()
                    import pickle
                    with (work/'training_pca.pkl').open('xb') as file:pickle.dump(pca,file)
                else:
                    work.mkdir()
                    behavior=a.method=='cebra-behavior'
                    model=cebra.CEBRA(model_architecture='offset10-model',batch_size=512,
                        learning_rate=3e-4,temperature=1 if behavior else 1.12,
                        output_dimension=dim,max_iterations=10000 if dim==32 else 15000,
                        distance='cosine',conditional='time_delta' if behavior else 'time',
                        device='cuda_if_available',verbose=True,time_offsets=10)
                    if behavior:model.fit(train,train_labels)
                    else:model.fit(train)
                    train_embedding=model.transform(train)[:-1]
                    test_embedding=model.transform(test)[:-1]
                    model.save(str(work/'model.pt'))
                for split,embedding in [('train',train_embedding),('test',test_embedding)]:
                    if embedding.shape!=(rat[f'{split}_rows'],dim) or not np.isfinite(embedding).all():
                        raise ValueError('native output shape/finite contract')
                    destination=a.output/f'{condition}-{name}-{split}-d{dim}.npy'
                    with destination.open('xb') as file:np.save(file,np.asarray(embedding,dtype='<f4'),allow_pickle=False)
                receipt.append({'condition':condition,'rat':name,'dimensions':dim,'seed':0,
                    'behavior_training_labels':a.method=='cebra-behavior','test_behavior_used':False})
    document={'schema':'marble_embedding_submission_v1','protocol_id':spec['protocol_id'],'access_view':'B',
        'method':a.method,'method_name':'training-only refit; not published checkpoint replay'}
    (a.output/'submission.json').write_text(json.dumps(document,indent=2)+'\n')
    (a.work/'PROVENANCE.json').write_text(json.dumps({'protocol_id':spec['protocol_id'],
        'adapter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'paper_numerical_reproduction':False,'fits':receipt},indent=2)+'\n')


if __name__=='__main__':main()
