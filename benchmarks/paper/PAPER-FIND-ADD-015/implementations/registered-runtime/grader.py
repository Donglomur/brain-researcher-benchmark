"""Exact pinned worker; candidate validation precedes numeric reference loading."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,'/source')
from numeric_score import read_submission,score_validated,need


def pin(path):
    body=Path(path).read_bytes()
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}


def main():
    plan=json.loads(Path('/source/operator_assets.json').read_text());invocation=json.loads(Path('/source/invocation.json').read_text())
    for name,row in plan['source_files'].items():need(pin('/source/'+name)=={k:row[k]for k in ('bytes','sha256')},'pinned trusted source')
    need(pin('/submission/predictions.npz')==invocation['submission'],'finished submitted file changed')
    spec=json.loads(Path('/source/submission_schema.json').read_text())['fields']
    try:values,digest=read_submission('/submission/predictions.npz',spec)
    except Exception as exc:
        result={'status':'invalid_submission','submission_valid':False,'reason':str(exc),'metrics':None,'private_numeric_reference_loads':0,'scientific_success':None}
    else:
        need(pin('/private/expected.npz')=={k:plan['expected'][k]for k in ('bytes','sha256')},'pinned private reference')
        result=score_validated(values,digest,'/private/expected.npz',spec)
    result['scope']='Fixed processed-trace reconstruction control; open-paper reasoning and improvement not graded.'
    result['candidate_program_executed']=False
    print(json.dumps(result,allow_nan=False),flush=True)
    return 0 if result['status']=='scored'else 2


if __name__=='__main__':raise SystemExit(main())
