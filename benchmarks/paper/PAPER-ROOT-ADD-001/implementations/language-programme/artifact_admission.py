"""Complete original artifact admission; scientific evaluation is separately deferred.

All imports of the unchanged numerical admission source occur only in the future
qualified runtime, after source authority. No source-construction scorer execution.
"""
import importlib.util,sys
from pathlib import Path
from common import need,descriptor,capture,parse,pin,canonical,save
from contract import SESSIONS,EPISODES
CAP=33554432
PANEL_CAP=536870912


def original(here):
    public=here/'vendor/public';operator=here/'vendor/operator'
    sys.path[:0]=[str(public),str(operator)]
    spec=importlib.util.spec_from_file_location('language_original_score',operator/'score.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def native_panel(root,files,design_sha,protocol_sha,budget,score):
    need(set(files)=={s+'.npz'for s in SESSIONS}|{'submission.json'},'exact full native outputs')
    raw=capture(root/'submission.json',files['submission.json'],500000,budget)
    d=score.submission(raw,'native',design_sha,SESSIONS)
    need(d['protocol_sha256']==protocol_sha,'same native protocol')
    for r in d['files']:
        name=r['id']+'.npz';need(r['path']==name and descriptor(r,CAP)==files[name],'exact deterministic native capture identity')
    budget.reading(sum(r['bytes']+1 for r in d['files']))
    return d,score.native_admit(root,d)


def prediction_panel(rows,design_sha,protocol_sha):
    need(list(rows)==list(EPISODES),'all70 exact ordered episode outputs')
    files=[]
    for eid,r in rows.items():
        descriptor(r,CAP);files.append({'id':eid,'path':r['path'],'bytes':r['bytes'],'sha256':r['sha256'],'case_sha256':r['case_sha256']})
    need(sum(r['bytes']for r in files)<=PANEL_CAP,'original complete512MiB candidate panel cap')
    return {'schema':'language_submission_v1','mode':'prediction','protocol_sha256':protocol_sha,'design_sha256':design_sha,'files':files}


def admit_all(root,native,panels,bindings,design_sha,protocol_sha,budget,score):
    """The precise all-candidate barrier precedes every operator numerical decode."""
    need(set(native)=={'A','B','operator'} and set(panels)=={'A','B'},'complete independent candidate/reference panels')
    b=score.binding_admit(bindings,design_sha)
    candidates={}
    for arm in ('A','B'):
        n=native[arm];nd,nv=native_panel(root/n['root'],n['files'],design_sha,protocol_sha,budget,score)
        pd=score.submission(canonical(panels[arm]),'prediction',design_sha,EPISODES)
        budget.reading(sum(r['bytes']+1 for r in pd['files']))
        candidates[arm]={'native':nv,'prediction':score.prediction_admit(root,pd,b)}
    # No target array is opened here. This boundary follows both complete arms.
    op=native['operator'];_,reference=native_panel(root/op['root'],op['files'],design_sha,protocol_sha,budget,score)
    for eid in EPISODES:
        r=b['episodes'][eid];c=r['case'];budget.reading(r['baselines']['bytes']+1);a=score.capture_arrays(root,r['baselines'],score.ARMS[1:])
        need(set(a)==set(score.ARMS[1:]),'four independent source-produced baselines')
        for x in a.values():need(x.shape==(c['rows'],c['units']) and x.dtype.kind=='f' and x.dtype.itemsize in(4,8) and score.np.isfinite(x).all(),'complete finite full-unit operator predictions')
    return {'native_candidate_panels':2,'candidate_prediction_files':140,'operator_native_panels':1,'operator_baseline_episodes':70,'operator_arrays':280,'target_arrays_opened':False,'scientific_grading_called':False}
