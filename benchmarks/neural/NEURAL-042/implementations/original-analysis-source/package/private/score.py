"""Portable artifact grader: candidate validation precedes private gold access."""
import argparse
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from pac import DESIGNS, CONTRASTS, METRICS
from reference import packet_valid
from io_utils import read_json, pinned_json


def need(ok,message):
    if not ok: raise ValueError(message)


def finite(x):
    return type(x) in (int,float) and math.isfinite(x)


def report_valid(v,packet):
    need(type(v) is dict and set(v)=={'schema','patients','groups','claim_scope'} and v['schema']=='neural042_report_v1'
        and v['claim_scope']=='descriptive_patient_associations_not_causal_or_crossoscillator_proof','Exact report fields/scope')
    expected=[(p,d,c) for p in packet['patients'] for d in DESIGNS for c in CONTRASTS]
    need(type(v['patients']) is list and len(v['patients'])==len(expected),'Complete144 patient/contrast/design rows')
    for r,key in zip(v['patients'],expected):
        need(type(r) is dict and set(r)=={'patient','design','contrast','n_sessions','n_channels','metrics'}
             and (r['patient'],r['design'],r['contrast'])==key,'Exact ordered unique row identity')
        channels=[x for x in packet['channels'] if x['patient']==r['patient']]
        need(type(r['n_sessions']) is int and type(r['n_channels']) is int
             and 0<=r['n_sessions']<=len({x['session'] for x in channels})
             and r['n_sessions']<=r['n_channels']<=len(channels),'Feasible source coverage')
        if r['metrics'] is None:
            need(r['n_sessions']==r['n_channels']==0,'Null estimate has zero support')
        else:
            need(r['n_sessions']>0 and type(r['metrics']) is dict and set(r['metrics'])==set(METRICS)
                 and all(finite(x) for x in r['metrics'].values()),'All finite metric values required')
            # These are contrasts, so negative values are valid. Bound only
            # quantities with exact analytic ranges; power/rate have no cap.
            need(all(-1<=r['metrics'][k]<=1 for k in ('mi','trial_null','shift_null','early_mi','late_mi','harmonic_plv'))
                 and -2<=r['metrics']['corrected_mi']<=2 and -2<=r['metrics']['waveform_asymmetry']<=2,'Analytic contrast ranges')
    need(type(v['groups']) is list and len(v['groups'])==4,'Four group summaries')
    for r,(d,c) in zip(v['groups'],[(d,c) for d in DESIGNS for c in CONTRASTS]):
        need(type(r) is dict and set(r)=={'design','contrast','n_patients','mean','ci95','sign_flip_p'}
             and (r['design'],r['contrast'])==(d,c),'Group identity')
        rows=[x for x in v['patients'] if x['design']==d and x['contrast']==c and x['metrics'] is not None]
        need(type(r['n_patients']) is int and r['n_patients']==len(rows),'Summary support matches patient rows')
        if len(rows)<2:
            need(r['mean'] is None and r['ci95'] is None and r['sign_flip_p'] is None,'Insufficient population support')
        else:
            need(finite(r['mean']) and abs(r['mean']-math.fsum(x['metrics']['corrected_mi']/len(rows) for x in rows))<=1e-10
                 and type(r['ci95']) is list and len(r['ci95'])==2 and all(finite(x) and -2<=x<=2 for x in r['ci95'])
                 and r['ci95'][0]<=r['ci95'][1] and finite(r['sign_flip_p']) and 0<r['sign_flip_p']<=1,'Finite consistent group summary')
    return v


def assess(candidate,packet,gold_loader):
    try: report_valid(candidate,packet)
    except (ValueError,TypeError,KeyError,OverflowError) as e:
        return {'status':'invalid_submission','score':None,'detail':str(e),'target_loader_calls':0}
    calls=0
    try:
        calls+=1; gold=report_valid(gold_loader(),packet)
    except (ValueError,TypeError,KeyError,OverflowError,OSError) as e:
        return {'status':'operator_error','score':None,'detail':str(e),'target_loader_calls':calls}
    if not all((a['metrics'] is None)==(b['metrics'] is None) and a['n_sessions']==b['n_sessions']
               and a['n_channels']==b['n_channels'] for a,b in zip(candidate['patients'],gold['patients'])):
        return {'status':'incorrect_support','score':None,'target_loader_calls':calls}
    try:
        errors={k:[] for k in METRICS}; primary={c:[] for c in CONTRASTS}
        for a,b in zip(candidate['patients'],gold['patients']):
            if b['metrics'] is None: continue
            for k in METRICS: errors[k].append(abs(a['metrics'][k]-b['metrics'][k]))
            if a['design']=='nuisance_matched':
                primary[a['contrast']].append(abs(a['metrics']['corrected_mi']-b['metrics']['corrected_mi']))
        per={c:(math.fsum(x/len(v) for x in v) if v else None) for c,v in primary.items()}
        available=[x for x in per.values() if x is not None]
        diagnostics={k:(math.fsum(x/len(v) for x in v) if v else None) for k,v in errors.items()}
        group_errors=[]
        for a,b in zip(candidate['groups'],gold['groups']):
            if b['mean'] is not None:
                group_errors.append({'design':b['design'],'contrast':b['contrast'],
                   'mean_absolute_error':abs(a['mean']-b['mean']),
                   'ci_endpoint_max_error':max(abs(x-y) for x,y in zip(a['ci95'],b['ci95'])),
                   'sign_flip_p_absolute_error':abs(a['sign_flip_p']-b['sign_flip_p'])})
        if not all(x is None or math.isfinite(x) for x in diagnostics.values()):
            raise ArithmeticError('Arithmetic exhaustion')
        numeric_match=all(math.isclose(a['metrics'][k],b['metrics'][k],rel_tol=1e-6,abs_tol=1e-10)
            for a,b in zip(candidate['patients'],gold['patients']) if b['metrics'] is not None for k in METRICS)
        group_match=all(r['mean_absolute_error']<=1e-10 and r['ci_endpoint_max_error']<=1e-10
                        and r['sign_flip_p_absolute_error']<=1e-10 for r in group_errors)
        constant={}; count_only={}
        for c in CONTRASTS:
            target=[r for r in gold['patients'] if r['contrast']==c and r['design']=='nuisance_matched' and r['metrics'] is not None]
            baseline={r['patient']:r for r in gold['patients'] if r['contrast']==c and r['design']=='count_only'}
            constant[c]=math.fsum(abs(r['metrics']['corrected_mi'])/len(target) for r in target) if target else None
            available_count=[(r,baseline[r['patient']]) for r in target if baseline[r['patient']]['metrics'] is not None]
            count_only[c]=math.fsum(abs(a['metrics']['corrected_mi']-b['metrics']['corrected_mi'])/len(target)
                                   for a,b in available_count) if target and len(available_count)==len(target) else None
        return {'status':'scored' if len(available)==2 else 'incomplete_primary_support',
                'score':math.fsum(x/2 for x in available) if len(available)==2 else None,
                'score_name':'equal_endpoint_patient_MAE_of_nuisance_matched_surrogate_corrected_MI',
                'lower_is_better':True,'endpoint_mae':per,'diagnostic_mae_by_unit':diagnostics,
                'group_errors':group_errors,'all_numeric_claims_match':numeric_match and group_match,
                'fixed_zero_coupling_mae':constant,'fixed_count_only_mae':count_only,
                'target_loader_calls':calls,
                'scope':'numerical artifact fidelity; no biological sign, SOTA or narrative-quality reward'}
    except (ArithmeticError,OverflowError) as e:
        return {'status':'valid_unscorable_arithmetic','score':None,'detail':str(e),'target_loader_calls':calls}


def main():
    p=argparse.ArgumentParser();p.add_argument('--submission',required=True);p.add_argument('--operator',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    try:
        op=read_json(a.operator)
        if op.get('packet') is None:
            result={'status':'data_unavailable','score':None,'target_loader_calls':0}
        else:
            packet=packet_valid(pinned_json(Path(a.operator).parent,op['packet']))
            try: candidate=read_json(a.submission,2_000_000)
            except (ValueError,OSError,UnicodeError) as e:
                result={'status':'invalid_submission','score':None,'target_loader_calls':0,'detail':type(e).__name__}
            else:
                if op.get('gold') is None:
                    try: report_valid(candidate,packet)
                    except (ValueError,TypeError,KeyError,OverflowError) as e:
                        result={'status':'invalid_submission','score':None,'target_loader_calls':0,'detail':str(e)}
                    else: result={'status':'reference_unavailable','score':None,'target_loader_calls':0}
                else: result=assess(candidate,packet,lambda:pinned_json(Path(a.operator).parent,op['gold']))
    except (ValueError,OSError,KeyError,TypeError,OverflowError) as e:
        result={'status':'operator_error','score':None,'target_loader_calls':0,'detail':str(e)}
    Path(a.out).write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return 0 if result['status']=='scored' else 2


if __name__=='__main__': raise SystemExit(main())
