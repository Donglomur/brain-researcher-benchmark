"""Prospective class-blind 30% label selection from prequalified TRAIN IDs only.

This is a declared successor policy, not an assertion about historical sampling.
No label, EEG, model, validation or test observation is read by this function.
"""
import hashlib
from contract import exact,need,ident,encode


def select(rows,training_groups,dataset,seed):
    ident(dataset);need(type(seed) is int and 0<=seed<2**63,'precommitted integer seed')
    need(type(rows) is list and len(rows)>=4,'complete training identity roster')
    need(type(training_groups) is list and training_groups==sorted(set(training_groups)) and training_groups,'qualified train groups')
    for group in training_groups:ident(group)
    ids=[]
    for row in rows:
        exact(row,('id','group'));ident(row['id']);ident(row['group']);need(row['group'] in training_groups,'training-only row');ids.append(row['id'])
    need(len(ids)==len(set(ids)),'unique train sample identities')
    k=3*len(ids)//10
    ranked=sorted(ids,key=lambda v:(hashlib.sha256(encode(['cbramod-low-label30-v1',dataset,seed,v])).digest(),v))
    chosen=set(ranked[:k])
    return {'schema':'cbramod_training_label_selection_v1','dataset':dataset,'seed':seed,'total_training_rows':len(ids),
        'selected_count':k,'rule':'floor(3*N/10), class-blind SHA256 rank, original row order retained',
        'selected_ids':[v for v in ids if v in chosen],'training_groups':training_groups.copy(),
        'historical_sampler_parity':False}
