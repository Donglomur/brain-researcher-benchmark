"""Strict summary worker; no candidate program execution or scientific pass floor."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,'/source')
from summary_score import read_json,validate,score,need


def pin(path):
    body=Path(path).read_bytes()
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}


def main():
    plan=json.loads(Path('/source/operator_assets.json').read_text())
    invocation=json.loads(Path('/source/invocation.json').read_text())
    for name,row in plan['source_files'].items():
        need(pin('/source/'+name)=={k:row[k]for k in ('bytes','sha256')},'trusted helper pin')
    try:
        candidate,candidate_pin=read_json('/submission/summary.json')
        need(candidate_pin==invocation['submission'],'submitted bytes changed since host snapshot')
        validate(candidate)
        need(candidate['input_sha256']==plan['source_input_sha256'],'original CSV target fingerprint required')
    except Exception as exc:
        result={'status':'invalid_submission','submission_valid':False,'reason':str(exc),'metrics':None,
                'private_numeric_reference_loads':0,'scientific_success':None}
    else:
        reference,reference_pin=read_json('/private/reference.json')
        need(reference_pin=={k:plan['expected'][k]for k in ('bytes','sha256')},'private reference pin')
        metrics=score(candidate,reference)
        result={'status':'scored'if metrics['status']=='valid_summary_continuously_scored'else metrics['status'],
                'submission_valid':True,'metrics':metrics,'private_numeric_reference_loads':1,
                'submission_pin':candidate_pin,'private_reference_pin':reference_pin,'scientific_success':None}
    result.update(scope='Original Salzburg processed CSV; six shared-spec posterior-summary targets only. Primary open-paper reconstruction, model fidelity, candidate provenance and improvement are not adjudicated.',
                  candidate_program_executed=False,model_fits=0,
                  claimed_diagnostics_and_mcse_verified=False)
    print(json.dumps(result,allow_nan=False),flush=True)
    return 0 if result['status']=='scored'else 2


if __name__=='__main__':raise SystemExit(main())
