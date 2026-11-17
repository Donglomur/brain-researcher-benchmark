"""Numerical investigation artifact checks, not significance or biological truth."""
import hashlib
import math
import re
from delivery_io import canonical,exact,need
from analysis_core import BLOCKS,FIELDS

ATOL=1e-8
RTOL=1e-6


def fingerprint(value):return hashlib.sha256(canonical(value)).hexdigest()


def public_contract(public):
    exact(public,['schema','packet_id','generation','blocks'])
    need(public['schema']=='neural038-panel-v1' and type(public['generation']) is str and
         re.fullmatch('[a-f0-9]{64}',public['generation']),'Source generation')
    need(public['packet_id']==fingerprint({k:v for k,v in public.items() if k!='packet_id'}),'Panel fingerprint')
    need(type(public['blocks']) is list and [r['block_id'] for r in public['blocks']]==list(BLOCKS),'Complete four artifact blocks')
    wanted={}
    for block in public['blocks']:
        exact(block,['block_id','kind','cells'])
        need(block['kind']==('revision' if block['block_id']=='revision_pool' else 'original'),'Distinct revision provenance')
        need(type(block['cells']) is list and 0<len(block['cells'])<=10000,'Complete source memberships')
        rows={}
        for row in block['cells']:
            exact(row,['cell_key','availability'])
            need(type(row['cell_key']) is str and 0<len(row['cell_key'])<=128 and row['cell_key'] not in rows and
                 row['availability'] in ('observed','unobserved'),'Exact unique source row support')
            rows[row['cell_key']]=row['availability']
        wanted[block['block_id']]=rows
    return wanted


def numeric(value,available):
    need((type(value) in (int,float) and math.isfinite(value)) if available else value is None,
         'Finite observed scalar or explicit unavailable null; no booleans')


def admit(public,submission):
    wanted=public_contract(public)
    exact(submission,['schema','packet_id','blocks','original_macro_interaction','revision_mean_interaction'])
    need(submission['schema']=='neural038-investigation-v1' and submission['packet_id']==public['packet_id'] and
         type(submission['blocks']) is list and len(submission['blocks'])==4,'All artifact blocks required')
    admitted={};valid_counts={}
    for block in submission['blocks']:
        exact(block,['block_id','cells','valid_cells','means']);name=block['block_id']
        need(type(name) is str and name in wanted and name not in admitted,'Exact unique block join')
        need(type(block['cells']) is list and len(block['cells'])==len(wanted[name]),'All source rows, no favorable subset')
        rows={}
        for row in block['cells']:
            exact(row,['cell_key','availability',*FIELDS]);key=row['cell_key']
            need(type(key) is str and key in wanted[name] and key not in rows and
                 row['availability']==wanted[name][key],'Exact row join and source-availability mask')
            for field in FIELDS:numeric(row[field],row['availability']=='observed')
            rows[key]=row
        count=sum(value=='observed' for value in wanted[name].values())
        need(type(block['valid_cells']) is int and block['valid_cells']==count,'Exact observed support count')
        exact(block['means'],FIELDS)
        for field in FIELDS:numeric(block['means'][field],count>0)
        admitted[name]={'cells':rows,'means':block['means']};valid_counts[name]=count
    need(set(admitted)==set(wanted),'Every original/revision block retained')
    numeric(submission['original_macro_interaction'],all(valid_counts[n]>0 for n in BLOCKS[:3]))
    numeric(submission['revision_mean_interaction'],valid_counts['revision_pool']>0)
    return admitted,valid_counts


def score(public,submission,load_private):
    admitted,counts=admit(public,submission)
    if not all(counts.values()):
        return {'status':'insufficient_source_support','max_scaled_error':None,'private_target_callbacks':0,
                'reason':'At least one required source block has no complete observed row; no subset-block metric.'}
    expected=load_private()
    exact(expected,['schema','packet_id','blocks','original_macro_interaction','revision_mean_interaction'])
    need(expected['schema']=='neural038-reference-v1','Operator reference schema')
    reference,_=admit(public,{**expected,'schema':'neural038-investigation-v1'})
    errors=[];block_summary={}
    def difference(actual,target):
        error=abs(actual-target)/(ATOL+RTOL*abs(target))
        if not math.isfinite(error):raise OverflowError('Finite input overflowed error arithmetic')
        errors.append(error);return error
    try:
        for name in BLOCKS:
            local=[]
            for key,row in reference[name]['cells'].items():
                if row['availability']=='observed':
                    for field in FIELDS:local.append(difference(admitted[name]['cells'][key][field],row[field]))
            for field in FIELDS:local.append(difference(admitted[name]['means'][field],reference[name]['means'][field]))
            block_summary[name]={'numeric_fields':len(local),'max_scaled_error':max(local),
                                 'within_tolerance':sum(x<=1 for x in local)}
        for key in ('original_macro_interaction','revision_mean_interaction'):
            difference(submission[key],expected[key])
    except (OverflowError,ZeroDivisionError):
        return {'status':'numeric_error','max_scaled_error':None,'private_target_callbacks':1}
    maximum=max(errors)
    return {'status':'scored','max_scaled_error':maximum,'higher_is_better':False,
            'full_numeric_reconstruction':maximum<=1,'numeric_fields':len(errors),
            'numeric_fields_within_tolerance':sum(x<=1 for x in errors),'blocks':block_summary,
            'absolute_tolerance':ATOL,'relative_tolerance':RTOL,'private_target_callbacks':1,
            'biological_success':None,'inference':'Descriptive source-block decomposition; no animal/population or causal p-value.'}
