"""Protected target-last numerical agreement and status-first reconstruction."""
from pathlib import Path
import math
from core import need,capture,parse,encoded,publish,canonical,descriptor
from contracts import report,DESIGNS,CONTRASTS,METRICS
from authority import grading_selection
from admission import admit,Capture
from outer import natural,command,source_recheck

def close(x,y):return abs(x-y)<=1e-10+1e-6*abs(y)
def reference_agreement(x,y):
    need(x['claim_scope']==y['claim_scope'],'reference same scope')
    for a,b in zip(x['patients'],y['patients']):
        need({k:v for k,v in a.items()if k!='metrics'}=={k:v for k,v in b.items()if k!='metrics'},'independent reference support identity')
        need((a['metrics']is None)==(b['metrics']is None),'independent null support agreement')
        if a['metrics']is not None:need(all(close(a['metrics'][k],b['metrics'][k])for k in METRICS),'independent full11 metric agreement')
    for a,b in zip(x['groups'],y['groups']):
        need(a['design']==b['design']and a['contrast']==b['contrast']and a['n_patients']==b['n_patients'],'independent group support')
        for k in('mean','sign_flip_p'):
            need(a[k]is None and b[k]is None or a[k]is not None and b[k]is not None and abs(a[k]-b[k])<=1e-10,'independent group numeric agreement')
        need(a['ci95']is None and b['ci95']is None or a['ci95']is not None and b['ci95']is not None and all(abs(u-v)<=1e-10 for u,v in zip(a['ci95'],b['ci95'])),'independent group interval agreement')
    return True

def compare(candidate,target):
    endpoints={};status=[]
    for d in DESIGNS:
        for c in CONTRASTS:
            pairs=[(x,y)for x,y in zip(candidate['patients'],target['patients'])if x['design']==d and x['contrast']==c]
            mismatches=[];errors={k:[]for k in METRICS}
            for x,y in pairs:
                if (x['metrics']is None)!=(y['metrics']is None)or(x['n_channels'],x['n_sessions'])!=(y['n_channels'],y['n_sessions']):mismatches.append(x['patient'])
                if x['metrics']is not None and y['metrics']is not None:
                    for k in METRICS:errors[k].append(abs(x['metrics'][k]-y['metrics'][k]))
            supported=sum(y['metrics']is not None for _,y in pairs);ok=not mismatches and supported>0
            endpoints[d+'/'+c]={'status':'matched_support'if ok else'no_target_support'if supported==0 and not mismatches else'support_mismatch','target_supported_people':supported,'mismatched_people':mismatches,'mae':{k:sum(v)/len(v)if ok and len(v)==supported else None for k,v in errors.items()}}
    primary=[endpoints['nuisance_matched/'+c]['mae']['corrected_mi']for c in CONTRASTS]
    return {'endpoints':endpoints,'primary_equal_endpoint_mae':sum(primary)/2 if all(x is not None for x in primary)else None,'neural_gain_scalar':None}

def execute(a,captured,late,b):
    selection,declaration=grading_selection(a,captured,late,b);c=Capture(a,b);root=Path(a['roots']['observation'])
    od=selection['observation'];obs=c.exact(od['path'],root/'OBSERVATION.json',od['pin'],a['resources']['closure_bytes'])
    need(obs['status']=='complete'and obs['source']==captured['pin']and obs['authority']==captured['authority_pin'],'exact complete observed production')
    natural(obs['caller'],command(a,captured),a)
    need(c.exact(obs['caller_artifact']['path'],root/'CALLER.json',obs['caller_artifact']['pin'],65536)==obs['caller'],'persisted original caller record')
    # Independent issuer publishes this only after the outer caller's original
    # tool capture has closed; the provisional OBSERVATION never certifies itself.
    ed=selection['outer_completion'];ep=canonical(ed['path'])
    need(canonical(a['roots']['operator'])in ep.parents,'independent external completion namespace')
    external=parse(capture(ep,ed['pin'],a['resources']['closure_bytes'],b,readonly=True)[0])
    need(external.get('schema')=='neural042_external_outer_completion_v1'and external.get('realm')=='actual_original_tool_capture'
         and external.get('issuer')==a['issuer']and external.get('source')==captured['pin']and external.get('authority')==captured['authority_pin']
         and external.get('observation')==od and type(external.get('exit_code'))is int and external['exit_code']==0
         and external.get('natural_exit')is True and external.get('streams_complete')is True
         and external.get('observed_after_outer_return')is True and external['completed_at']>=obs['observed_end'],
         'original independent outer completion, never provisional self-attestation')
    need(type(external.get('capture_artifacts'))is list and external['capture_artifacts'],'actual original stream/command/tool artifacts')
    for evidence in external['capture_artifacts']:
        path=canonical(evidence['path']);need(canonical(a['roots']['operator'])in path.parents,'protected original capture artifact')
        capture(path,evidence['pin'],a['resources']['closure_bytes'],b,retain=False,readonly=True)
    for name in('stdout','stderr'):
        raw=capture(root/(name+'.bin'),obs['streams'][name],65536,b,readonly=True)[0]
        if name=='stderr':need(not raw,'complete natural empty stderr')
        else:need(parse(raw)['producer']==obs['producer']and parse(raw)['status']=='collected','actual observed worker return')
    admitted=admit(a,captured,obs['producer'],b);need(selection['reference_targets']==admitted['targets'],'late target selection joins actual full reference producers')
    need(obs['schedule']==admitted['producer']['disposition']and all(x.get('empty')is True for x in obs['resource_inventory'].values()),'full observed closure')
    # Every early operand above has an exact source-owned non-target name.
    # Physical alias/firmlink custody remains independently qualified, not lexical proof.
    source_recheck(a,captured,b);targets={}
    for key,d in admitted['targets'].items():
        targets[key]=report(parse(capture(d['path'],d['pin'],a['resources']['reference_report_bytes'],b,readonly=True)[0]),admitted['projection']['people'])
    for world in('O','D'):reference_agreement(targets['R1/'+world],targets['R2/'+world])
    results={}
    for key,value in admitted['reports'].items():
        results[key]={'original_O_reconstruction':compare(value,targets['R1/O']),'D_self_consistency':compare(value,targets['R1/D'])if key.split('-')[1]=='D'else None}
    from diagnostics import sanity_references,paired_reports
    sanity=sanity_references(targets['R1/O']);paired=paired_reports(admitted['reports'],targets['R1/O'],results)
    value={'schema':'neural042_grade_v1','task_id':'NEURAL-042','authority':captured['authority_pin'],'source':captured['pin'],'late_grading':declaration,
           'observation':od,'independent_references_agree':True,'panels':results,'sanity_references':sanity,'paired_comparisons':paired,'scientific_reasoning_score':None,'causal_or_native_understanding_claim':False,
           'qualified_neural_contribution':None,'observed_end':b.tick(),'costs_before_score_publication':b.record()}
    path=canonical(selection['output']);need(path.parent==Path(a['roots']['observation'])and path.name=='SCORE.json','fixed protected score publication')
    raw=encoded(value);need(len(raw)<=a['resources']['closure_bytes'],'complete score/diagnostic publication cap')
    out=publish(path,raw,b,readonly=True);b.tick();return {'status':'graded','score':{'path':str(path),'pin':out}}
