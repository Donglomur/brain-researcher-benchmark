"""Frozen prospective reference builder. Never invoked during construction.

No candidate program is executed. Requires the independently prepared packet;
the resulting gold is operator-private and must be independently qualified.
"""
import argparse
from collections import defaultdict
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'public'))
from pac import wire_effects, summarize, DESIGNS, CONTRASTS, METRICS, need
from io_utils import read_json, ordinary_bytes


def packet_valid(p):
    import re
    need(type(p) is dict and set(p) == {'schema','patients','source_sessions','channels'}
         and p['schema'] == 'neural042_packet_v1' and type(p['source_sessions']) is int
         and p['source_sessions'] == 44, 'Exact full-source packet schema')
    ids=p['patients']; need(type(ids) is list and len(ids)==36 and ids==sorted(set(ids))
        and all(type(v) is str and re.fullmatch('[a-f0-9]{24}',v) for v in ids), '36 opaque patient IDs')
    rows=p['channels']; need(type(rows) is list and len(rows)<=4096, 'Bounded channel roster')
    seen=set(); sessions={}
    for r in rows:
        need(type(r) is dict and set(r)=={'id','patient','session','path','bytes','sha256','n_trials'},'Exact channel fields')
        need(all(type(r[k]) is str and re.fullmatch('[a-f0-9]{24}',r[k]) for k in ('id','patient','session'))
             and r['id'] not in seen and r['patient'] in ids,'Channel identity join')
        need(r['path']=='channels/'+r['id']+'.npz' and type(r['bytes']) is int and 0<r['bytes']<=2_000_000
             and type(r['n_trials']) is int and 0<r['n_trials']<=140
             and type(r['sha256']) is str and re.fullmatch('[a-f0-9]{64}',r['sha256']), 'Channel path/extent/pin')
        need(r['session'] not in sessions or sessions[r['session']]==r['patient'],'Session belongs to exactly one patient')
        sessions[r['session']]=r['patient']; seen.add(r['id'])
    need(len(sessions)<=44 and [r['id'] for r in rows]==sorted(seen),'Sorted channel roster')
    return p


def load_channel(root, r):
    b=ordinary_bytes(Path(root)/r['path'],2_000_000)
    need(len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'],'Prepared channel pin mismatch')
    names={'lfp','rates','loads','correct','probe','order','ids'}
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        need(set(z.namelist())=={k+'.npy' for k in names} and len(z.namelist())==7
             and sum(v.file_size for v in z.infolist())<=2_000_000,'Bounded exact NPZ entries')
    with np.load(io.BytesIO(b),allow_pickle=False) as z: x={k:z[k] for k in names}
    n=r['n_trials']; need(x['lfp'].shape==(n,1000) and x['lfp'].dtype.kind=='f'
        and all(x[k].shape==(n,) for k in names-{'lfp'}) and x['ids'].dtype.kind=='U','Prepared channel shape')
    need(all(x[k].dtype.kind in 'fiu' and np.isfinite(x[k]).all() for k in names-{'ids'}),'Finite ordinary prepared numeric data')
    need(len(set(x['ids'].tolist()))==n and all(len(v)==24 for v in x['ids']),'Unique trial IDs')
    return x


def aggregate(packet, effects):
    """Equal wires within session, then sessions within patient, then patients."""
    rows=[]
    for patient in packet['patients']:
        owned=[r for r in packet['channels'] if r['patient']==patient]
        for design in DESIGNS:
            for contrast in CONTRASTS:
                grouped=defaultdict(list)
                for r in owned:
                    v=effects[r['id']][design][contrast]
                    if v is not None: grouped[r['session']].append(v['metrics'])
                sessions=[{k:float(np.mean([v[k] for v in vs])) for k in METRICS} for vs in grouped.values()]
                rows.append({'patient':patient,'design':design,'contrast':contrast,
                    'n_sessions':len(sessions),'n_channels':sum(len(v) for v in grouped.values()),
                    'metrics':None if not sessions else {k:float(np.mean([v[k] for v in sessions])) for k in METRICS}})
    groups=[]
    for d in DESIGNS:
        for c in CONTRASTS:
            v=[r['metrics']['corrected_mi'] for r in rows if r['design']==d and r['contrast']==c and r['metrics'] is not None]
            groups.append({'design':d,'contrast':c,**summarize(v,d+':'+c)})
    return {'schema':'neural042_report_v1','patients':rows,'groups':groups,
            'claim_scope':'descriptive_patient_associations_not_causal_or_crossoscillator_proof'}


def build(packet_path, out):
    p=packet_valid(read_json(packet_path)); effects={}
    for r in p['channels']:
        x=load_channel(Path(packet_path).parent,r)
        effects[r['id']]=wire_effects(x['lfp'],x['rates'],x['loads'].tolist(),x['correct'].tolist(),
            x['probe'].tolist(),x['ids'].tolist(),x['order'].tolist(),r['id'])
    output=Path(out); need(not output.exists(),'Fresh private gold output')
    output.write_text(json.dumps(aggregate(p,effects),indent=2,allow_nan=False)+'\n')
    output.chmod(0o600)


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--packet',required=True);p.add_argument('--out',required=True);a=p.parse_args();build(a.packet,a.out)
