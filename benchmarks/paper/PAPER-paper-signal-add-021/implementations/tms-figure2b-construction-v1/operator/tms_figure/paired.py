"""Trusted target-last A/B grade caller. No authority creator or candidate runner."""
from __future__ import annotations
import hashlib,json,os
from pathlib import Path
from .contract import *
from .outputs import admit,specs,encode
from .compare import numbers,tolerance
from .reference import reference_to_directory


def closed_pair(plan,observations):
    """Trusted observations must come from an independently qualified runtime observer."""
    keys(plan,['schema','identity','arms','absolute_tolerance','relative_tolerance','tolerance_justification','matched_policy','source_lock'])
    require(plan['schema']=='tms_figure2b_paired_plan_v1','plan schema');metadata(plan['identity'])
    tolerance(plan['absolute_tolerance'],plan['relative_tolerance'])
    pin(plan['tolerance_justification']);pin(plan['matched_policy']);pin(plan['source_lock'])
    require(type(plan['arms']) is dict and set(plan['arms'])=={'A','B'},'both arms')
    require(type(observations) is dict and set(observations)=={'A','B'},'both trusted closure observations')
    names=set()
    for arm in ['A','B']:
        row=plan['arms'][arm];keys(row,['trial_id','view','program','output'])
        require(type(row['trial_id']) is str and row['trial_id'] and row['trial_id'] not in names,'distinct frozen trials');names.add(row['trial_id'])
        for name in ['view','program','output']:pin(row[name])
        obs=observations[arm]
        keys(obs,['schema','arm','trial_id','view','program','output','natural_exit','returncode','producer_closed','capture_complete','exclusive_custody','isolation_qualified'])
        require(obs['schema']=='tms_figure2b_trusted_closure_v1' and obs['arm']==arm and all(obs[k]==row[k] for k in ['trial_id','view','program','output']),'closure identity')
        require(type(obs['returncode']) is int and obs['returncode']==0 and all(obs[k] is True for k in ['natural_exit','producer_closed','capture_complete','exclusive_custody','isolation_qualified']),'complete natural closed producer')
    return plan


def source_lock(lock_path,expected,budget):
    """Explicit frozen implementation members, verified without candidate imports."""
    lock=json_body(read_pinned(lock_path,expected,budget))
    keys(lock,['schema','files']);require(lock['schema']=='tms_figure2b_source_lock_v1' and type(lock['files']) is dict,'source lock')
    expected_names={'__init__.py','contract.py','derivative.py','outputs.py','reference.py','reduction.py','compare.py','paired.py','fieldtrip.py','views.py','slab.py'}
    require(set(lock['files'])==expected_names,'complete operative source lock')
    for name,bodypin in lock['files'].items():
        fd=open_pinned(Path(__file__).parent/name,bodypin,budget);os.close(fd)


def grade_pair(*, plan, observations, authority_path, authority_pin, source_lock_path,
               captures, derivative_path, private_output, budget, metadata_read_reservation):
    """Caller-owned grants/observations are trusted inputs, never candidate artifacts.

    Candidate isolation and observer authenticity are external admission gates. This
    module validates their joins; a forged host grant is not made authentic by JSON.
    No routine creates an authorization, launches a candidate, or accepts a score callback.
    """
    require(type(budget) is Budget,'exact cumulative budget')
    closed_pair(plan,observations)
    authority=json_body(read_pinned(authority_path,authority_pin,budget))
    keys(authority,['schema','plan_sha256','observations_sha256','operation','authorized_by_operator'])
    require(authority['schema']=='tms_figure2b_operator_grant_v1' and authority['operation']=='compute-protected-reference-and-grade-pair' and authority['authorized_by_operator'] is True,'explicit separate grading grant')
    require(authority['plan_sha256']==digest(plan) and authority['observations_sha256']==digest(observations),'authority bound to exact plan and observations')
    source_lock(source_lock_path,plan['source_lock'],budget)
    require(type(captures) is dict and set(captures)=={'A','B'},'both output locations')
    paths=[Path(captures[x]).absolute() for x in ['A','B']]
    output=Path(private_output).absolute()
    require(paths[0]!=paths[1] and all(not output.is_relative_to(x) and not x.is_relative_to(output) for x in paths),'private output distinct from candidates')
    # Authenticate and admit ALL A and B bodies before resolving the derivative.
    accepted={arm:admit(captures[arm],plan['arms'][arm]['output'],plan['identity'],budget) for arm in ['A','B']}
    require(not output.exists(),'fresh private output');output.mkdir(mode=0o700)
    reference_pin=reference_to_directory(derivative_path,plan['identity'],output/'reference',budget,metadata_read_reservation=metadata_read_reservation)
    reference=admit(output/'reference',reference_pin,plan['identity'],budget)
    report={'schema':'tms_figure2b_paired_agreement_v1','plan_sha256':digest(plan),'reference':reference_pin,'numerical_tolerance':{'absolute':plan['absolute_tolerance'],'relative':plan['relative_tolerance'],'justification':plan['tolerance_justification']},'arms':{},'holds':HOLDS,'scientifically_qualified':False}
    layout=specs(plan['identity'])
    for arm in ['A','B']:
        rows={}
        for name,spec in layout.items():
            a,b=accepted[arm][name],reference[name]
            if spec['dtype']=='f8':
                row,residual=numbers(a,b,absolute_tolerance=plan['absolute_tolerance'],relative_tolerance=plan['relative_tolerance'])
                body=encode(residual,'f8',budget);budget.charge(write=len(body))
                filename=arm+'.'+name+'.signed-residual.f8'
                with (output/filename).open('xb') as stream:stream.write(body)
                row['signed_residuals']={'path':filename,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'dtype':'little-endian-f8','shape':spec['shape'],'nonfinite_pair_residual':'NaN; exact category/sign agreement counted separately'}
            else:
                count=sum(x==y for x,y in zip(a,b));row={'elements':len(a),'pass_count':count,'fail_count':len(a)-count,'comparison':'exact discrete support or undefined mask'}
            rows[name]=row
        report['arms'][arm]={'fields':rows,'all_elements_pass':all(x['fail_count']==0 for x in rows.values())}
    body=json.dumps(report,sort_keys=True,allow_nan=False,indent=2).encode();budget.charge(write=len(body))
    with (output/'REPORT.json').open('xb') as stream:stream.write(body)
    return report
