"""Fixed public roster and artifact contract, with no scientific execution."""
from pathlib import Path
from delivery_io import decode, read, pin, need
ROOT=Path(__file__).resolve().parent
PROTOCOL_RAW=read(ROOT/'PROTOCOL.json',100000)
P=decode(PROTOCOL_RAW)
PROTOCOL_SHA=pin(PROTOCOL_RAW)['sha256']
SESSIONS={r['id']:r for r in P['sessions']}
FAMILIES=['context','random_token','ngram1','ngram3','ngram5','ngram7','ngram10','sem_syn','word2vec','syn']
ARMS=P['prospective']['arms']
FOLD_IDS=[f'{s}_f{f}' for s in SESSIONS for f in range(5)]
CAP=32*1024**2

def native_shapes(session):
    u=SESSIONS[session]['units']
    d={'population':(40,33),'unit':(u,40,33),'time_shuffle':(40,33),
       'random_token':(1,33),'sentence_swap':(1,33)}
    d.update({f'ngram{n}':(1,33) for n in (1,3,5,7,10)})
    for f in ('sem_syn','word2vec','syn'):
        d[f]=(3,1);d[f+'_shuffle']=(3,1)
    return d

def feature_member(s,f):
    if f in ('sem_syn','word2vec','syn'): return f'DNN/{s}/sem_syn/{f}_R_embeddings_pca.npy'
    name='vicuna7b' if f=='context' else ('vicuna7b_random_token_randtok' if f=='random_token' else 'vicuna7b_'+f[5:]+'gram')
    return f'DNN/{s}/llama/{name}_R_embeddings_pca.npy'

def design_check(d):
    need(d.get('schema')=='language_design_v1' and d.get('protocol_sha256')==PROTOCOL_SHA,'Design protocol')
    need(list(d.get('sessions',{}))==list(SESSIONS),'Complete ordered fourteen sessions')
    for s,r in d['sessions'].items():
        need(r['geometry']==SESSIONS[s] and set(r['files'])=={'fr','speaker','timing','qid',*FAMILIES},'Exact source geometry/files')
    return d
