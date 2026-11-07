"""Explicit separate private grading command; never invoked by the program runner.

The authority file is an externally selected trusted-operator input, not a
candidate certificate. Its declarations alone do not establish qualification.
"""
import time
START=time.monotonic()
import argparse,importlib.util,os,resource,signal,sys
from pathlib import Path
HERE=Path(__file__).absolute().parent
sys.path.insert(0,str(HERE))
from common import *
from contract import EPISODES,READ_CAP,WRITE_CAP
from artifact_admission import original,admit_all,native_panel


def outer_closure(v,authority,observed,selected):
    """External root-owned observation after the original observer exits.

    A surviving OBSERVED marker cannot establish this boundary. This receipt
    must come from the future trusted launcher, not from either candidate or
    the original observer being measured. Content checks do not prove provenance.
    """
    keys={'schema','source_manifest','selection','observed','original_origin','original_outer_deadline','finished_monotonic','returncode','natural_exit','child_reaped','owned_group_absence_observed','stdout_bytes','stderr_bytes','cleanup_before_original_deadline','forced'}
    need(type(v)is dict and set(v)==keys and v['schema']=='language_external_whole_command_closure_v1','exact external whole-command closure')
    need(v['source_manifest']==selected['source_manifest']==authority['source_manifest'] and v['selection']==authority['selection'] and v['observed']==authority['observed'],'external source/selection/observation identities')
    start=observed['child']['original_origin']
    need(type(start)in(int,float) and math.isfinite(start) and v['original_origin']==start and v['original_outer_deadline']==start+3000240,'same original outer clock, never renewed')
    need(type(v['finished_monotonic'])in(int,float) and math.isfinite(v['finished_monotonic']) and start<=v['finished_monotonic']<start+3000240,'actual final command completion within original clock')
    need(type(v['returncode'])is int and v['returncode']==0 and all(v[k]is True for k in('natural_exit','child_reaped','owned_group_absence_observed','cleanup_before_original_deadline')) and v['forced']is False,'external original natural-zero/reap/closure after final cleanup')
    need(all(type(v[k])is int and v[k]==0 for k in('stdout_bytes','stderr_bytes')),'original outer silent EOF streams')
    return v


def grade(*,root,here,collection,budget):
    score=original(here);design=collection['design']['sha256'];protocol=collection['protocol_sha256']
    b=parse(capture(root/'OPERATOR_BINDINGS.json',collection['operator_bindings'],33554432,budget),33554432)
    panels={a:parse(capture(root/'panels'/(a+'.json'),collection['prediction_panels'][a],1048576,budget))for a in('A','B')}
    # Re-admit both entire candidates and sealed references before any target callback.
    admit_all(root,collection['native_panels'],panels,b,design,protocol,budget,score)
    op=collection['native_panels']['operator'];_,reference=native_panel(root/op['root'],op['files'],design,protocol,budget,score)
    results={}
    def private(eid):
        r=b['episodes'][eid];budget.reading(r['target']['bytes']+r['baselines']['bytes']+2)
        return score.capture_arrays(root,r['target'],['target'])['target'],score.capture_arrays(root,r['baselines'],score.ARMS[1:])
    for arm in ('A','B'):
        n=collection['native_panels'][arm];_,candidate=native_panel(root/n['root'],n['files'],design,protocol,budget,score)
        d=score.submission(canonical(panels[arm]),'prediction',design,EPISODES)
        budget.reading(sum(r['bytes']+1 for r in d['files']));pred=score.prediction_admit(root,d,b)
        results[arm]={'native':score.native_evaluate(candidate,lambda s:reference[s]),'prediction':score.prediction_evaluate(pred,b,private)}
    return {'schema':'language_separately_authorized_original_grade_v1','source_manifest':collection['source_manifest'],'results':results,'original_metrics_unchanged':True,'scientific_pass':None,'runtime_qualified_by_this_call':False,'whole_paper_reproduction':False}


def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m


def main(argv=None):
    p=argparse.ArgumentParser(allow_abbrev=False);p.add_argument('--authority',required=True);p.add_argument('--authority-sha256',required=True);p.add_argument('--output',required=True);a=p.parse_args(argv)
    need(signal.getitimer(signal.ITIMER_REAL)==(0.,0.),'fresh private grading timer')
    old=signal.getsignal(signal.SIGALRM);primary=None;owned=False
    def expired(*_):raise TimeoutError('original separate grade deadline')
    try:
        owned=True;signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,max(.001,START+3600-time.monotonic()))
        raw,d=observed_capture(a.authority,1048576);need(d['sha256']==a.authority_sha256,'exact external grade authority')
        auth=parse(raw);keys={'schema','task_id','explicit_private_grade_selected','root_verified_receipt_custody','source_manifest','attempt_root','observed','selection','host_environment','other_future_bytes','outer_command_closure'}
        need(type(auth)is dict and set(auth)==keys and auth['schema']=='language_separate_private_grade_authority_v1' and auth['task_id']==TASK and auth['explicit_private_grade_selected']is True and auth['root_verified_receipt_custody']is True,'separate trusted operator grade authority, not candidate data')
        out=ordinary(a.output);need(not out.exists() and out.parent.is_dir(),'fresh separately selected grade output')
        budget=Budget(out.parent,START+3600,read_cap=READ_CAP,write_cap=WRITE_CAP,retained_cap=16777216,other_future=auth['other_future_bytes'])
        manifest=parse(capture(HERE/'SOURCE_MANIFEST.json',auth['source_manifest'],262144,budget))
        for n,d in manifest['files'].items():capture(HERE/relative(n),d,1048576,budget,retain=False,allow_empty=True)
        root=ordinary(auth['attempt_root']);ob=parse(capture(root/'OBSERVED.json',auth['observed'],1048576,budget));selected=parse(capture(root/'SELECTION.json',auth['selection'],1048576,budget))
        need(ob['schema']=='language_building_blocks_original_whole_command_observed_v1' and ob['source']==selected['source_manifest']==auth['source_manifest'] and ob['original_phase_records_checked']==213 and ob['original_trusted_host_records_checked']==71,'same whole original observed attempt')
        external=parse(capture(auth['outer_command_closure']['path'],auth['outer_command_closure'],65536,budget),65536)
        outer_closure(external,auth,ob,selected)
        child=ob['child'];need(child['returncode']==0 and all(child[k]is True for k in('natural_exit','child_reaped','owned_group_absence_observed')) and child['terminal_bytes']=={'stdout':0,'stderr':0},'natural complete original controller boundary')
        controller=load('language_private_controller',HERE/'controller.py');controller.selected(selected)
        engine=load('language_private_engine',HERE/'engine/native.py');observer=load('language_private_observer',HERE/'observe.py')
        # Current grading has its own selected clock. Verification still compares
        # original receipts against their recorded original scientific origin.
        class GradeIO(observer.IO):
            def capture(self,*args,**kwargs):
                budget.deadline();ret=super().capture(*args,**kwargs);budget.deadline();return ret
        io=GradeIO();from verification import verify
        checked=verify(io,root/'run',selected,controller,engine,child['original_origin']);need(checked==ob['collection'],'all original custody reverified before private array access')
        budget.reading(io.read);need(auth['host_environment']==selected['host_environment'],'same externally qualified original numerical environment')
        b=parse(capture(HERE/'BINDINGS.json',manifest['files']['BINDINGS.json'],1048576,budget))
        # Use the source-bound no-.pth environment check, without constructing a run.
        seam=type('QualifiedAdmission',(),{})();seam.v=selected;seam.b=b;seam.budget=budget
        controller.Operations.enable_qualified_numeric_admission(seam)
        resource.setrlimit(resource.RLIMIT_AS,(17179869184,17179869184))
        collection=parse(capture(root/'run/COLLECTION.json',checked,1048576,budget))
        result=grade(root=root/'run',here=HERE,collection=collection,budget=budget)
        result.update(authority=pin(raw),observed=auth['observed'],original_metrics_source=manifest['files']['vendor/operator/score.py'])
        save(out,canonical(result),budget,8*1024**2);budget.deadline();return 0
    except BaseException as e:primary=e;raise
    finally:
        if owned:
            failures=[]
            for action in(lambda:signal.setitimer(signal.ITIMER_REAL,0),lambda:signal.signal(signal.SIGALRM,old)):
                try:action()
                except BaseException as e:failures.append(type(e).__name__)
            if failures:
                if primary is not None:primary.add_note('Grade cleanup uncertainty: '+','.join(failures))
                else:raise RuntimeError('Grade cleanup uncertainty: '+','.join(failures))
if __name__=='__main__':
    rc=main();need(time.monotonic()<START+3600,'private grade natural completion before original separate cutoff');raise SystemExit(rc)
