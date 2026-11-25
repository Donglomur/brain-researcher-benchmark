"""Strict artifact grading. Never imports or executes submitted code."""
import argparse
import math
from fractions import Fraction
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import package_io as io
from analysis_core import GROUPS, CONTRASTS

ROOT=Path(__file__).resolve().parents[1]

def exact(obj,keys):
    if type(obj) is not dict or set(obj)!=set(keys):raise ValueError('Exact object keys required')

def number(value,nullable=False):
    if nullable and value is None:return
    if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Finite ordinary number required')

def ids(value,allowed):
    if type(value) is not list or any(type(x) is not str or x not in allowed for x in value) or len(set(value))!=len(value):
        raise ValueError('Unique known identity list required')

def validate(candidate,identity,contract_sha,input_sha):
    exact(candidate,('schema_version','task_id','contract_sha256','input_sha256','analysis'))
    if type(candidate['schema_version']) is not int or candidate['schema_version']!=1 or candidate['task_id']!='NEURAL-033':raise ValueError('Task/version')
    if candidate['contract_sha256']!=contract_sha or candidate['input_sha256']!=input_sha:raise ValueError('Input/contract identity')
    value=candidate['analysis'];exact(value,('excluded','eligible_row_ids','panels'))
    allowed=set(identity['row_ids']);known_mice=set(identity['mouse_ids'])
    ids(value['eligible_row_ids'],allowed)
    if type(value['excluded']) is not list or len(value['excluded'])>len(allowed):raise ValueError('Excluded roster')
    reasons={'baseline_not_stable','followup_not_stable','baseline_shaft','followup_shaft',
             *(kind+field for kind in ('nonfinite_','invalid_') for field in ('baseline_volume','followup_volume','event_rate'))}
    excluded=[]
    for row in value['excluded']:
        exact(row,('row_id','reason'))
        if row['reason'] not in reasons:raise ValueError('Exclusion reason')
        excluded.append(row['row_id'])
    ids(excluded,allowed)
    if set(excluded)&set(value['eligible_row_ids']) or set(excluded)|set(value['eligible_row_ids'])!=allowed:raise ValueError('Full source-row partition')
    exact(value['panels'],('all','balanced'))
    for name,panel in value['panels'].items():
        exact(panel,('groups','matched_bin_mass','contrasts','delete_one_mouse'))
        exact(panel['groups'],GROUPS)
        for group in panel['groups'].values():
            exact(group,('row_ids','mice','n_rows','n_mice','effective_mice','rank','coefficients','status','reason'))
            ids(group['row_ids'],allowed);ids(group['mice'],known_mice)
            for key,bound in [('n_rows',len(allowed)),('n_mice',len(known_mice)),('rank',3)]:
                if type(group[key]) is not int or not 0<=group[key]<=bound:raise ValueError('Bounded count')
            if group['n_rows']!=len(group['row_ids']) or group['n_mice']!=len(group['mice']):raise ValueError('Declared support counts')
            if group['n_mice']>group['n_rows'] or group['rank']>group['n_rows']:raise ValueError('Impossible support/rank')
            number(group['effective_mice'],True)
            if group['effective_mice'] is not None and not 1-1e-10<=group['effective_mice']<=group['n_mice']+1e-10:
                raise ValueError('Effective mouse count outside represented support')
            if group['status']=='defined':
                if group['reason'] is not None or group['rank']!=3 or group['n_rows']<3 or group['n_mice']<2 or group['effective_mice'] is None:raise ValueError('Defined fit status')
                exact(group['coefficients'],('intercept','activity_rank','baseline_rank'))
                for item in group['coefficients'].values():number(item)
            elif group['status']=='unavailable':
                if group['coefficients'] is not None or group['reason'] not in ('insufficient_support','rank_deficient'):raise ValueError('Undefined fit')
                if group['reason']=='insufficient_support' and not (group['rank']==0 and group['effective_mice'] is None and (group['n_rows']<3 or group['n_mice']<2)):
                    raise ValueError('Insufficient-support fit invariants')
                if group['reason']=='rank_deficient' and not (group['rank']<3 and group['n_rows']>=3 and group['n_mice']>=2 and group['effective_mice'] is not None):
                    raise ValueError('Rank-deficient fit invariants')
            else:raise ValueError('Fit status')
        exact(panel['matched_bin_mass'],() if name=='all' else ('apical','basal'))
        for values in panel['matched_bin_mass'].values():
            if type(values) is not list or len(values)!=9:raise ValueError('Nine matching bins')
            for item in values:
                number(item)
                if not 0<=item<=1:raise ValueError('Bin mass')
        exact(panel['contrasts'],CONTRASTS)
        for item in panel['contrasts'].values():
            exact(item,('estimate','jackknife_se','deletion_min','deletion_max','uncertainty_status'))
            for key in ('estimate','jackknife_se','deletion_min','deletion_max'):number(item[key],True)
            if item['jackknife_se'] is not None and item['jackknife_se']<0:raise ValueError('Nonnegative uncertainty')
            status=item['uncertainty_status']
            if status not in ('defined','point_unavailable','deletion_unavailable'):raise ValueError('Uncertainty status')
            if status=='defined' and any(item[k] is None for k in ('estimate','jackknife_se','deletion_min','deletion_max')):raise ValueError('Defined uncertainty values')
            if status=='point_unavailable' and item['estimate'] is not None:raise ValueError('Undefined point')
            if status=='deletion_unavailable' and item['estimate'] is None:raise ValueError('Available point required')
            if status!='defined' and any(item[k] is not None for k in ('jackknife_se','deletion_min','deletion_max')):raise ValueError('Unavailable uncertainty')
        if type(panel['delete_one_mouse']) is not dict or not set(panel['delete_one_mouse'])<=known_mice:raise ValueError('Known deletion IDs')
        for item in panel['delete_one_mouse'].values():
            exact(item,CONTRASTS)
            for value in item.values():number(value,True)
    return candidate['analysis']

def relative_error(a,b):
    scale=1+abs(b)
    # Same-sign subtraction cannot overflow and preserves adjacent float errors.
    return abs(a-b)/scale if (a>=0)==(b>=0) else abs(a)/scale+abs(b)/scale

def finite_mean(values):
    # Accumulate exact binary inputs before division; per-item division can
    # erase a positive subnormal error even when the final mean is representable.
    return float(sum((Fraction(value) for value in values), Fraction()) / len(values)) if values else None

def discrepancy(candidate,expected,path='',numbers=None,mismatches=None):
    numbers=[] if numbers is None else numbers;mismatches=[] if mismatches is None else mismatches
    if type(expected) in (float,int) and type(expected) is not bool and type(candidate) in (float,int) and type(candidate) is not bool:
        if isinstance(expected,int):
            if candidate!=expected:mismatches.append(path)
        else:numbers.append(relative_error(candidate,expected))
    elif type(candidate)!=type(expected):mismatches.append(path)
    elif isinstance(expected,dict):
        if set(candidate)!=set(expected):mismatches.append(path+' keys')
        for k in expected.keys()&candidate.keys():discrepancy(candidate[k],expected[k],path+'/'+k,numbers,mismatches)
    elif isinstance(expected,list):
        if len(candidate)!=len(expected):mismatches.append(path+' length')
        for i,(a,b) in enumerate(zip(candidate,expected)):discrepancy(a,b,path+'/'+str(i),numbers,mismatches)
    elif candidate!=expected:mismatches.append(path)
    return numbers,mismatches

def evaluate(candidate,identity,contract_sha,input_sha,reference):
    analysis=validate(candidate,identity,contract_sha,input_sha)  # Entire artifact before recomputation.
    expected=reference()
    errors=[];availability=[];panel_errors={}
    for panel in ('all','balanced'):
        current=[]
        for name in CONTRASTS:
            a=analysis['panels'][panel]['contrasts'][name]['estimate'];b=expected['panels'][panel]['contrasts'][name]['estimate']
            if (a is None)!=(b is None):availability.append(panel+'/'+name)
            elif b is not None:current.append(relative_error(a,b))
        errors.extend(current);panel_errors[panel]=finite_mean(current)
    numeric,mismatch=discrepancy(analysis,expected)
    primary=None if availability or mismatch or any(x is None for x in panel_errors.values()) else finite_mean(list(panel_errors.values()))
    return {'task_id':'NEURAL-033','status':'graded','primary_normalized_contrast_mae':primary,'panel_normalized_contrast_mae':panel_errors,
            'defined_contrasts':len(errors),'availability_mismatches':availability,
            'structural_mismatch_count':len(mismatch),'structural_mismatches':mismatch[:100],
            'secondary_normalized_numeric_mae':finite_mean(numeric),
            'candidate_code_executed':False,'scientific_success_threshold':None,'higher_is_better':False}

ERRORS=(ValueError,TypeError,KeyError,OSError,OverflowError,UnicodeError,RecursionError,ArithmeticError,ImportError,RuntimeError)

def grade_bytes(body,identity,contract_sha,input_sha,reference):
    """Separate rejected submissions from operator failures, with no reference access before admission."""
    try:
        candidate=io.strict_json(body)
        validate(candidate,identity,contract_sha,input_sha)
    except ERRORS as exc:
        return failure('invalid_submission',exc,False),2
    try:
        result=evaluate(candidate,identity,contract_sha,input_sha,reference)
        result['reference_invoked']=True
        return result,0
    except ERRORS as exc:
        return failure('operator_error',exc,True),3

def failure(status,exc,invoked):
    return {'task_id':'NEURAL-033','status':status,'error':type(exc).__name__+': '+str(exc)[:240],
            'primary_normalized_contrast_mae':None,'candidate_code_executed':False,'reference_invoked':invoked}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--submission',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or args.output.is_symlink() or any(p.is_symlink() for p in args.output.absolute().parents):raise FileExistsError('Fresh non-symlink report path required')
    try:
        contract=io.asset('public/CONTRACT.json');identity=io.strict_json(io.asset('public/identity.json'))
        input_pin=identity['input_sha256'];contract_pin=io.pin(contract)['sha256']
    except ERRORS as exc:
        result,code=failure('operator_error',exc,False),3
    else:
        def reference():
            # Operator-owned implementation and pinned public data; no candidate source import.
            from analysis_core import analyze
            body=io.asset('public/observations.json')
            if io.pin(body)['sha256']!=input_pin:raise ValueError('Input generation mismatch')
            return analyze(io.strict_json(body)['rows'])
        try:body=io.read_bytes(args.submission,2097152)
        except ERRORS as exc:result,code=failure('invalid_submission',exc,False),2
        else:result,code=grade_bytes(body,identity,contract_pin,input_pin,reference)
    io.write_new(args.output,io.encode(result));return code

if __name__=='__main__':raise SystemExit(main())
