"""Artifact verifier. All six score matrices admitted before private design access."""
import io,sys,math,hashlib,json
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from io_utils import capture,decode,fresh,write_json
from protocol import SUBJECTS,ROIS,expected_rank_metrics
CASES=tuple(f'sub-{p}_{r}' for p in SUBJECTS for r in ROIS)

def load_array(raw,shape):
    if len(raw)>50_000_000:raise ValueError('matrix byte cap')
    f=io.BytesIO(raw)
    try:
        version=np.lib.format.read_magic(f)
        if version==(1,0):actual,fort,dtype=np.lib.format.read_array_header_1_0(f,max_header_size=4096)
        elif version==(2,0):actual,fort,dtype=np.lib.format.read_array_header_2_0(f,max_header_size=4096)
        else:raise ValueError('NPY version')
    except Exception as e:raise ValueError('NPY header') from e
    if actual!=tuple(shape) or fort or dtype.kind!='f' or dtype.itemsize not in (4,8) or dtype.hasobject:raise ValueError('C-order float32/float64 exact shape')
    if len(raw)-f.tell()!=math.prod(shape)*dtype.itemsize:raise ValueError('NPY exact payload')
    arr=np.frombuffer(raw,dtype=dtype,offset=f.tell()).reshape(shape)
    if not np.isfinite(arr).all():raise ValueError('finite score matrix required')
    return arr

def roster_digest(roster):
    return hashlib.sha256(json.dumps(roster,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()).hexdigest()

def validate_roster(roster):
    if not isinstance(roster,dict) or set(roster)!=set(CASES):raise ValueError('operator public roster')
    for r in roster.values():
        if not isinstance(r,dict) or set(r)!={'query_ids','candidate_ids'}:raise ValueError('operator roster fields')
        for name,n,prefix in [('query_ids',1540,'q'),('candidate_ids',3700,'i')]:
            ids=r[name]
            if not isinstance(ids,list) or len(ids)!=n or any(not isinstance(x,str) or len(x)!=25 or x[0]!=prefix or any(c not in '0123456789abcdef' for c in x[1:]) for x in ids) or len(set(ids))!=n:raise ValueError('operator roster support/IDs')
    first=roster[CASES[0]]['candidate_ids']
    if any(r['candidate_ids']!=first for r in roster.values()) or any(roster[f'sub-{p}_V1']['query_ids']!=roster[f'sub-{p}_IT']['query_ids'] for p in SUBJECTS):raise ValueError('operator shared candidate/order consistency')

def admit(root,manifest,roster):
    if set(manifest)!= {'schema','files','roster_sha256'} or manifest['schema']!='neural051-scores-v1' or set(manifest['files'])!=set(CASES):raise ValueError('all six named outputs required')
    if manifest['roster_sha256']!=roster_digest(roster):raise ValueError('stale public roster binding')
    root=Path(root)
    if root.is_symlink() or not root.is_dir() or {p.name for p in root.iterdir()}!={'submission.json',*(c+'.npy' for c in CASES)}:raise ValueError('exact seven-file submission directory')
    if set(roster)!=set(CASES):raise ValueError('operator public roster')
    arrays={};pins={}
    for case in CASES:
        rec=manifest['files'][case]
        if set(rec)!= {'file','sha256'} or rec['file']!=case+'.npy' or not isinstance(rec['sha256'],str) or len(rec['sha256'])!=64 or any(c not in '0123456789abcdef' for c in rec['sha256']):raise ValueError('file binding')
        r=roster[case]
        if set(r)!= {'query_ids','candidate_ids'} or len(r['query_ids'])!=1540 or len(r['candidate_ids'])!=3700 or len(set(r['query_ids']))!=1540 or len(set(r['candidate_ids']))!=3700:raise ValueError('full public identity roster')
        raw,pin=capture(Path(root)/rec['file'],50_000_000,rec['sha256'])
        arrays[case]=load_array(raw,(1540,3700));pins[case]=pin
    return arrays,pins

def grade_arrays(arrays,roster,design):
    if design.get('schema')!='neural051-design-v1' or design.get('full_canonical_split') is not True:raise ValueError('operator design')
    if len(design['candidate_ids'])!=3700 or len(set(design['candidate_ids']))!=3700 or len(design['candidate_concepts'])!=3700 or {c['id'] for c in design['cases']}!=set(CASES) or len(design['cases'])!=6:raise ValueError('operator design support')
    out={}
    for c in design['cases']:
        key=c['id'];r=roster[key]
        if c['person'] not in SUBJECTS or c['roi'] not in ROIS or key!=f"sub-{c['person']}_{c['roi']}" or r['candidate_ids']!=design['candidate_ids'] or r['query_ids']!=[q['id'] for q in c['queries']]:raise ValueError('public/private identity join')
        correct=[q['candidate_index'] for q in c['queries']]
        if len(correct)!=1540 or len(set(correct))!=1540 or any(type(i)!=int or not 0<=i<3700 for i in correct):raise ValueError('operator query support')
        repeats=[len(q['trial_ids']) for q in c['queries']]
        if repeats.count(1)!=1440 or repeats.count(2)!=100:raise ValueError('frozen query repeat groups')
        allm=[];within=[];single=[];repeat=[]
        for scores,index,count in zip(arrays[key],correct,repeats):
            m=expected_rank_metrics(scores,index);allm.append(m);(single if count==1 else repeat).append(m)
            cat=design['candidate_concepts'][index]; inds=[j for j,z in enumerate(design['candidate_concepts']) if z==cat]
            if len(inds) not in (5,6):raise ValueError('same-concept complete support')
            within.append(expected_rank_metrics(scores[inds],inds.index(index)))
        mean=lambda ms:{'top1':math.fsum(m[0] for m in ms)/len(ms),'mrr':math.fsum(m[1] for m in ms)/len(ms),'images':len(ms)}
        out[key]={'all_images':mean(allm),'same_concept':mean(within),'single_presentation':mean(single),'two_repeat_mean':mean(repeat)}
    macro={roi:{k:math.fsum(out[f'sub-{p}_{roi}']['all_images'][k] for p in SUBJECTS)/3 for k in ('top1','mrr')} for roi in ROIS}
    return {'status':'scored','primary_name':'participant_macro_IT_expected_top1','primary':macro['IT']['top1'],'participant_macro':macro,'cases':out,'IT_minus_V1_top1':macro['IT']['top1']-macro['V1']['top1'],'biological_units':3,'population_inference':False,'runtime_or_data_qualification':False}

def evaluate(root,manifest,roster,private_loader):
    entered=False
    try:validate_roster(roster)
    except (ValueError,TypeError,KeyError,OverflowError,RecursionError):return {'status':'operator_error','primary':None,'private_reference_invoked':False,'reason':'invalid_public_roster'}
    try:arrays,pins=admit(root,manifest,roster)
    except (ValueError,TypeError,KeyError,OSError,OverflowError,RecursionError) as e:return {'status':'invalid_submission','primary':None,'private_reference_invoked':False,'reason':type(e).__name__}
    try:
        entered=True;design=private_loader();result=grade_arrays(arrays,roster,design)
        result.update({'private_reference_invoked':True,'captured_submission_sha256':pins});return result
    except (ValueError,TypeError,KeyError,OSError,OverflowError,RecursionError,IndexError) as e:return {'status':'operator_error','primary':None,'private_reference_invoked':entered,'reason':type(e).__name__}
if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser()
    for n in ('submission','roster','roster-sha256','design','design-sha256','output'):a.add_argument('--'+n,required=True)
    v=a.parse_args();fresh(v.output)
    try:roster=decode(capture(v.roster,3_000_000,v.roster_sha256)[0]);validate_roster(roster)
    except Exception as e:write_json(v.output,{'status':'operator_error','primary':None,'private_reference_invoked':False,'reason':type(e).__name__});raise SystemExit(2)
    try:m=decode(capture(Path(v.submission)/'submission.json',10_000)[0])
    except Exception as e:write_json(v.output,{'status':'invalid_submission','primary':None,'private_reference_invoked':False,'reason':type(e).__name__});raise SystemExit(1)
    result=evaluate(v.submission,m,roster,lambda:decode(capture(v.design,10_000_000,v.design_sha256)[0]));write_json(v.output,result)
    raise SystemExit(0 if result['status']=='scored' else 2 if result['status']=='operator_error' else 1)
