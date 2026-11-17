#!/usr/bin/env python3
"""Load both pinned selected models, checking every key/shape without inference."""
import argparse
from pathlib import Path
import resource
import time
from author_predict import verify_source, load_author
from prepare import ensure_external, write_json, versions

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
ensure_external(a.output)
if a.output.exists():
    raise ValueError('Refuse evidence overwrite')
verify_source(a.source)
start=time.monotonic()
records=[]
for arm in ['causal','noncausal']:
    config,model,metadata=load_author(a.source,arm)
    records.append(metadata)
    del model
r=resource.getrusage(resource.RUSAGE_SELF)
write_json(a.output,dict(schema='smc_checkpoint_preflight_v1',models=records,versions=versions(),
    wall_seconds=time.monotonic()-start,cpu_seconds=r.ru_utime+r.ru_stime,maxrss_native_units=r.ru_maxrss,
    inference_performed=False,targets_accessed=False,score_linkage_verified=False))
print('Both selected36D checkpoints loaded with exact key/shape compatibility; no inference or score.')
