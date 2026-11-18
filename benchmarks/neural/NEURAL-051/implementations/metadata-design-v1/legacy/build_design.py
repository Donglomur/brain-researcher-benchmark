"""Build private source-identity mapping; never load neural values."""
import csv,io,json,sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from io_utils import capture,decode,write_json
from protocol import SUBJECTS,ROIS,split,image_id

def build(root, pins, seed):
    if not isinstance(seed,str) or len(seed)<32:raise ValueError('private operator seed >=32 characters')
    data={}
    for p in SUBJECTS:
        raw,_=capture(Path(root)/f'sub-{p}_StimulusMetadata.csv',500000,pins[p])
        rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
        for r in rows:
            for k in ('session','run','subject_id','trial_id'):r[k]=int(r[k])
        data[p]=rows
    splits,candidates,concepts=split(data)
    cids=[image_id(n) for n in candidates]
    if len(set(cids))!=len(cids):raise ValueError('candidate hash collision')
    cases=[]
    for p in SUBJECTS:
        groups={}
        for r in splits[p]['query']:groups.setdefault(r['stimulus'],[]).append(r['trial_id'])
        # HMAC-like private keyed ordering; source row/session/image never exposed with query rows.
        order=sorted(groups,key=lambda n:hashlib.sha256((seed+'|'+p+'|'+n).encode()).digest())
        queries=[{'id':'q'+hashlib.sha256((seed+'query|'+p+'|'+n).encode()).hexdigest()[:24], 'trial_ids':sorted(groups[n]),'candidate_index':candidates.index(n)} for n in order]
        for roi in ROIS:
            cases.append({'id':f'sub-{p}_{roi}','person':p,'roi':roi,'train_trial_ids':[r['trial_id'] for r in splits[p]['train']], 'train_images':[r['stimulus'] for r in splits[p]['train']], 'validation_trial_ids':[r['trial_id'] for r in splits[p]['validation']], 'validation_images':[r['stimulus'] for r in splits[p]['validation']], 'queries':queries})
    return {'schema':'neural051-design-v1','candidates':candidates,'candidate_ids':cids,'candidate_concepts':[concepts[n] for n in candidates],'cases':cases,'source_pins':pins,'full_canonical_split':True}
if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--metadata',required=True);a.add_argument('--pins',required=True);a.add_argument('--seed-file',required=True);a.add_argument('--output',required=True);v=a.parse_args()
    pins=decode(capture(v.pins,2000)[0]);seed=capture(v.seed_file,4096)[0].decode().strip();write_json(v.output,build(v.metadata,pins,seed))
