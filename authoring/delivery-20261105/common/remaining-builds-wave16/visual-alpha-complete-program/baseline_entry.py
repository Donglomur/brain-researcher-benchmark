"""Sealed fixed comparator: no candidate program or previous-context state mounted."""
import time
ORIGIN=time.monotonic()
import importlib.util
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,'/trusted')
from entry_common import guard,need


def main():
    request,view=guard();need(view['mode']=='reference' and view['arm'] is None,'independent operator-only phase')
    import numpy as np
    spec=importlib.util.spec_from_file_location('_visual_alpha_fixed_baseline','/sealed/baseline.py')
    baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
    people=view['participants'];need(len(people)==1 and people[0]['participant']==view['participant'],'exact one participant context')
    person=people[0];signals={}
    for name,row in person['signals'].items():
        signals[name]={k:row[k] for k in ('aperture_identity','band')}
        for key in ('responses','aperture'):
            path=Path('/input')/row[key]
            signals[name][key]=np.load(path,allow_pickle=False)
    with Path('/input/parameter_roster.json').open('rb') as f:raw=f.read(1048577)
    need(len(raw)<=1048576,'complete bounded public roster');rows=json.loads(raw)
    context={'participant':view['participant'],'role':view['fit_role'],'response_indices':person['response_indices'],'signals':signals}
    unique=len({r['aperture_identity'] for r in person['signals'].values()})
    resources=baseline.prospective_resources(view['participant'],view['fit_role'],distinct_apertures=unique)
    limits={'origin':ORIGIN,'deadline':min(ORIGIN+request['producer_seconds'],view['original_work_deadline']),'max_forward_calls':resources['max_forward_calls'],'max_residual_calls':resources['max_residual_calls']}
    raw,audit=baseline.fit_context(context,rows,view['parameter_roster_sha256'],limits=limits)
    audit.update(resources=resources,original_entry_origin=ORIGIN,limits=limits)
    blobs={'submission.json':raw,'baseline_audit.json':(json.dumps(audit,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()}
    for name,body in blobs.items():
        need(0<len(body)<=request['expected_files'][name],'complete bounded operator artifacts')
        fd=os.open('/output/'+name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:
            data=memoryview(body)
            while data:
                n=os.write(fd,data);need(n>0,'complete operator write');data=data[n:]
            os.fsync(fd)
        finally:os.close(fd)
if __name__=='__main__':main()
