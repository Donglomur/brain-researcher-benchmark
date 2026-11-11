"""Concrete complete view construction and target-last comparison callers.

These are trusted-operator source functions, not candidate-isolation issuers.
All endpoints remain inactive pending the separately listed qualification gates.
"""
import hashlib
from pathlib import Path
from input_owner import need,integer,capture,Writer
from source_pipeline import decode_json

SUBJECTS=tuple('sub-%02d'%i for i in range(1,7))
ARMS=('nuisance','nuisance_eye','nuisance_dynamic','full','full_shift500ms')

def stage_all(pool_root,pool_descriptor,out,per_view_cap,owner):
    rec=owner.begin('stage_complete_30_views');answer=None
    try:
        need(pool_descriptor['path']=='POOL.json' and integer(per_view_cap,1,2**63-1),'Selected original pool and per-view cap')
        raw=capture(pool_root,pool_descriptor,owner);pool=decode_json(raw)
        need(pool['schema']=='neural080_pool_v1' and [r['subject'] for r in pool['subjects']]==list(SUBJECTS),'Full pool before view preparation')
        import stage
        parent=Writer(out,owner);rows=[]
        for person in SUBJECTS:
            for arm in ARMS:
                # Conservative bound of the actual inherited capture limits:
                # pool20M+nuisance32M+ocular12M+dynamic60M+targets160M+20M.
                owner.reserve('read_bytes',304_000_000)
                owner.reserve('write_bytes',per_view_cap)
                view=parent.root/(person+'_'+arm)
                prepared=stage.stage(Path(pool_root),pool_descriptor['sha256'],person,arm,view,per_view_cap,owner=owner)
                scope_descriptor=prepared['scope_descriptor']
                need(scope_descriptor['path']=='SCOPE.json','Actual stager scope output')
                body=capture(view,scope_descriptor,owner)
                rows.append({'subject':person,'arm':arm,'root':str(view),'scope':{'path':'SCOPE.json','bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}})
        parent.document('VIEW_SELECTION.json',rows)
        answer=rows
    except BaseException as exc:owner.failure(rec,exc)
    owner.complete(rec);return answer

def compare_complete(candidate,reference,query,binding,out,owner):
    """Both complete thirty-array panels admitted before any private targets.

    Reuses the exact existing primary/contrasts/bootstrap; paired reference
    differences are descriptive and do not establish comparator competence.
    """
    rec=owner.begin('compare_complete_panels');answer=None
    try:
        import score
        import arrays
        from scorer_core import evaluate,mse,mean,serialize
        from io_contract import capture as legacy_capture,decode
        # All unchanged reader bounds are charged before their calls. These are
        # conservative logical bytes, not native allocator/CPU accounting.
        owner.reserve('read_bytes',2*(512*1024**2+100_000)+6*20_000_000+300_000)
        owner.reserve('retained_bytes',2*512*1024**2+6*20_000_000)
        qraw=legacy_capture(Path(query),200_000,owner=owner)
        candidate_values=score.admit(Path(candidate),qraw,owner=owner)
        reference_values=score.admit(Path(reference),qraw,owner=owner)
        # No private target binding is opened until both admissions succeed.
        obj=decode(legacy_capture(Path(binding),100_000,owner=owner))
        need(type(obj) is dict and set(obj)=={'schema','query_sha256','targets'} and obj['schema']=='neural080_private_v1' and obj['query_sha256']==hashlib.sha256(qraw).hexdigest(),'Exact common private binding')
        rows=obj['targets'];need(type(rows) is list and len(rows)==6,'All six targets')
        seen=set()
        for row in rows:
            score.descriptor(row,('subject','file','bytes','sha256'))
            need(row['subject'] in SUBJECTS and row['subject'] not in seen and row['file']==row['subject']+'.npy','Unique full target role')
            seen.add(row['subject'])
        gold={r['subject']:arrays.load(Path(binding).parent/r['file'],r,score.SHAPE,owner=owner) for r in rows}
        c=evaluate(candidate_values,gold);r=evaluate(reference_values,gold)
        differences={p:mse(reference_values[p]['full'],gold[p])-mse(candidate_values[p]['full'],gold[p]) for p in SUBJECTS}
        answer={'schema':'neural080_complete_comparison_v2','candidate':c,'reference':r,
                'reference_minus_candidate_full_mse_by_person':serialize(differences),
                'mean_reference_minus_candidate_full_mse':serialize(mean(list(differences.values()))),
                'statistical_unit':'six persons; same fixed102 exposed videos',
                'qualified_dynamic_information':None,'competence_qualified':False,
                'confirmatory_winner':None,'scientific_qualification':False}
        Writer(out,owner).document('COMPARISON.json',answer)
    except BaseException as exc:owner.failure(rec,exc)
    owner.complete(rec);return answer
