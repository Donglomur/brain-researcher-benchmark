"""Source-owned equal-person group aggregation, no private references imported."""
import hashlib
from pathlib import Path
from core import need,parse,capture
from contracts import DESIGNS,CONTRASTS,CLAIM,report,person_rows,identities
from worker_common import start,out,finish

def aggregate(rows,roster,b):
    import numpy as np
    need(np.__version__=='2.2.6','normative group RNG/numerical version')
    identities(roster,36);need(len(rows)==144,'complete144 rows')
    for i,p in enumerate(roster):person_rows(rows[4*i:4*i+4],p)
    groups=[]
    for j,(d,c)in enumerate((d,c)for d in DESIGNS for c in CONTRASTS):
        v=np.asarray([rows[i*4+j]['metrics']['corrected_mi']for i in range(36)if rows[i*4+j]['metrics']is not None],dtype=np.float64);n=len(v)
        result={'design':d,'contrast':c,'n_patients':n,'mean':None,'ci95':None,'sign_flip_p':None}
        if n>=2:
            seed=int.from_bytes(hashlib.sha256(('neural042-v1:'+d+':'+c).encode()).digest()[:8],'big')
            g=np.random.default_rng(seed);b.tick()
            ix=g.integers(0,n,size=(10000,n));boot=v[ix].mean(axis=1);sign=g.choice([-1,1],size=(10000,n));null=(sign*v).mean(axis=1)
            result.update(mean=float(v.mean()),ci95=[float(x)for x in np.quantile(boot,[.025,.975],method='linear')],sign_flip_p=float((1+(np.abs(null)>=abs(v.mean())).sum())/10001));b.tick()
        groups.append(result)
    return report({'schema':'neural042_report_v1','patients':rows,'groups':groups,'claim_scope':CLAIM},roster)

def run(request,context):
    b=start(request,context);need(request['planned_group_live_bytes']>=20<<20,'full10000x36 RNG/metadata working reservation')
    rows=[]
    for i,p in enumerate(request['people']):
        d=request['person_results'][i];need(d['person']==p,'ordered exact complete person outputs')
        raw,_=capture(Path('/inputs/people')/(p+'.json'),d['pin'],request['output_caps']['REPORT.json'],b,readonly=True)
        obj=parse(raw);person_rows(obj['rows'],p);rows.extend(obj['rows'])
    result=aggregate(rows,request['people'],b)
    return finish(request,context,b,{'REPORT.json':out('REPORT.json',result,request,b)}, {'person_results':request['person_results']})
