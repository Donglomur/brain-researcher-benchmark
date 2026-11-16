"""Strict arbitrary-report scorer; private gold is currently unprepared.

Only generated gold has been used in software checks. This is not a sandbox.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from analysis_core import PEOPLE,NUMBERS,read_bounded_file,strict_json,strict_json_bytes,validate_report,need


def leaves(value,prefix=''):
    if type(value) is dict:
        for key in sorted(value):yield from leaves(value[key],prefix+'/'+key)
    else:yield prefix,value


def compare(candidate,gold):
    # Validate the entire candidate before opening a private target in main().
    validate_report(candidate);validate_report(gold)
    predicted={r['participant_id']:r for r in candidate['participants']}
    expected={r['participant_id']:r for r in gold['participants']}
    checks=[]
    for group in PEOPLE+('aggregate',):
        a=candidate['aggregate'] if group=='aggregate' else {k:v for k,v in predicted[group].items() if k!='participant_id'}
        b=gold['aggregate'] if group=='aggregate' else {k:v for k,v in expected[group].items() if k!='participant_id'}
        av=dict(leaves(a));bv=dict(leaves(b))
        need(set(av)==set(bv),'Exact reference field set')
        for key,value in bv.items():
            actual=av[key]
            numeric_field=key.rsplit('/',1)[-1] in NUMBERS+('matched_FCz_equal_person_mean','matched_FCz_between_person_descriptive_SE')
            if numeric_field and value is not None:
                match=type(actual) in (int,float) and abs(actual-value)<=1e-9+1e-7*abs(value)
            else:match=type(actual)==type(value) and actual==value
            checks.append({'field':group+key,'matches':bool(match)})
    matched=sum(c['matches'] for c in checks)
    return {'schema':'neural078_numeric_grade_v1','score':matched/len(checks),
            'matching_fields':matched,'required_fields':len(checks),
            'full_reconstruction':matched==len(checks),'field_checks':checks,
            'effect_sign_is_not_a_pass_criterion':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--submission',type=Path,required=True);p.add_argument('--gold',type=Path,required=True)
    p.add_argument('--gold-sha256',required=True,help='Expected private reference pin from the selected target binding')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();need(not a.output.exists(),'Fresh score output')
    candidate=validate_report(strict_json(a.submission))
    need(re.fullmatch(r'[0-9a-f]{64}',a.gold_sha256) is not None,'Explicit expected private gold identity')
    gold_bytes=read_bounded_file(a.gold,65536)
    need(hashlib.sha256(gold_bytes).hexdigest()==a.gold_sha256,'Private gold matches expected selected reference pin')
    gold=validate_report(strict_json_bytes(gold_bytes))
    result=compare(candidate,gold)
    with a.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')


if __name__=='__main__':main()
