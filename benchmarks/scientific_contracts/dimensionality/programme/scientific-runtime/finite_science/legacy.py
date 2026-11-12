"""Unchanged legacy76 score arithmetic, with I/O and original custody external."""
import math
from .common import require,result
from .legacy_projection import validate,need,rms


def candidate(payload):
    req=payload['request'];design=req['design'];p=payload['protocol']
    require(p.get('legacy_design_identity_admitted') is True,'exact qualified legacy public design required','qualification_required')
    require(len(design['cases'])==19 and len({x['point'] for x in design['cases']})==19 and len(design['estimators'])==4 and len(set(design['estimators']))==4,'full19panel4estimator legacy roster')
    try:parsed=validate(req['candidate'],design)
    except (ValueError,TypeError,OverflowError,RecursionError) as error:
        return result({'legacy_status':'invalid_submission','score':None,'reason':str(error)},dict(record_count=0,private_numeric_loads=0),status='invalid_artifact')
    return result({'legacy_status':'valid_candidate','record_count':len(parsed)},dict(record_count=len(parsed),nested_panels=19,private_numeric_loads=0,source_version='legacy_core_2a487739f419'))


def score(payload):
    req=payload['request'];p=payload['protocol']
    require(p.get('score_stage')=='target_last' and p.get('legacy_candidate_validation_receipt_id') and p.get('legacy_target_decode_receipt_id'),'original candidate-validation-before-target-decode custody required','qualification_required')
    admitted=candidate(payload)
    if admitted['status']!='ok':return admitted
    # Pure core validation repeated on exact already-admitted candidate; the
    # controller must bind both requests to identical candidate/design bodies.
    candidate_values=validate(req['candidate'],req['design']);raw=req['legacy_target']
    points={'full':raw['full_reference']}
    for point in raw['points']:
        if not point['reuses_full_reference']:
            points[point['axis']+str(point['grid_index'])]=point['moments']
    need(set(points)=={p['point'] for p in req['design']['cases']},'private/public panel identity')
    errors={group:{field:[] for field in ('A','B','ratio')} for group in ('full','nonfull')};details=[]
    for (point,estimator),values in sorted(candidate_values.items()):
        target=points[point][estimator];group='full' if point=='full' else 'nonfull';delta={}
        for field in ('A','B','ratio'):
            expected=target[field]
            need(type(expected) in (int,float) and math.isfinite(expected) and expected!=0,'qualified nonzero reference required')
            relative=(values[field]-expected)/abs(expected)
            need(math.isfinite(relative),'finite score arithmetic')
            errors[group][field].append(relative);delta[field]=relative
        details.append({'point':point,'estimator':estimator,'signed_relative_errors':delta})
    scores={group+'_'+field+'_relative_RMSE':rms(values) for group,fields in errors.items() for field,values in fields.items()}
    report={'status':'scored','score':scores['full_ratio_relative_RMSE'],'direction':'lower','primary_metric':'full_ratio_relative_RMSE','metrics':scores,'record_count':len(candidate_values),'nested_panels':len(points),'independent_animals':1,'signed_record_errors':details,'success_threshold':None,'scientific_reconstruction_only':True,'candidate_program_or_chronology_verified':False,'whole_paper_or_improvement_qualified':False}
    return result({'legacy_report':report},dict(source_version='legacy_core_2a487739f419a4c1e5a9359d4a4507e5fecdb0c424562d43e83f71e62dddb0f6',candidate_validation_receipt=p['legacy_candidate_validation_receipt_id'],target_decode_receipt=p['legacy_target_decode_receipt_id'],kernel_private_file_loads=0,historical_standalone_private_numeric_loads=1,actual_external_numeric_decode_count=p['legacy_actual_target_decode_count']),['All six arithmetic summaries and literal metric definitions preserved.','External original target decode and candidate validation are separate actual custody; this in-memory kernel claims no file read.'])
