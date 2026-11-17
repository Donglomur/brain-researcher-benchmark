"""Operator prediction/report grader. NEVER imports or executes candidate code.

Known operator arrays are hash-bound. Candidate NPZ is header/size/axis checked
before loading; actual candidate execution needs the separate offline runner.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,math,stat,zipfile
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
MAX_PREDICTIONS=32*1024**2
FIELDS={'expected_counts','trial_ids','heldout_unit_ids','bin_left_edges_ms','prediction_units','panel_fingerprint'}
SCOPE={'development_only':True,'independent_animals':1,'animal_population_claim':False,'causal_claim':False,
       'neural_information_proven':False,'benchmark_admission_claim':False}
FACT_TOL=1e-8
POINT_TIE_TOL=1e-10


def require(ok,message):
    if not ok:raise ValueError(message)


def regular(path,cap):
    p=Path(path).absolute();s=p.lstat()
    require(all(not q.is_symlink() for q in [p,*p.parents]) and stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<s.st_size<=cap,'Invalid bounded regular file')
    return p


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(1048576),b''):h.update(part)
    return h.hexdigest()


def read_json(path,cap=1000000):
    p=regular(path,cap)
    def pairs(items):
        result={}
        for k,v in items:
            require(k not in result,'Duplicate JSON key');result[k]=v
        return result
    def invalid(x):raise ValueError('Nonfinite JSON value: '+x)
    return json.loads(p.read_text(),object_pairs_hook=pairs,parse_constant=invalid)


def save_json(path,value):
    p=Path(path)
    with p.open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
    p.chmod(0o400)


def metric_module(expected_sha=None):
    p=HERE.parent/'metrics.py'
    expected=expected_sha or read_json(HERE/'evaluation_lock.json')['metric_source_sha256']
    require(sha(p)==expected,'Operator metric dependency changed')
    spec=importlib.util.spec_from_file_location('_fixed_operator_nlb_metric',p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def text(value,name):
    a=np.asarray(value);require(a.shape==() and a.dtype.kind=='U','Invalid scalar '+name)
    return a.item()


def candidate_npz(path,n_trials,n_units):
    """Preflight untrusted ZIP/NPY metadata before NumPy payload allocation."""
    path=regular(path,MAX_PREDICTIONS)
    shapes={'expected_counts.npy':(n_trials,140,n_units),'trial_ids.npy':(n_trials,),
            'heldout_unit_ids.npy':(n_units,),'bin_left_edges_ms.npy':(140,),
            'prediction_units.npy':(),'panel_fingerprint.npy':()}
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist()
        require(len(entries)==len(shapes) and {e.filename for e in entries}==set(shapes),'Wrong/duplicate NPZ inventory')
        require(sum(e.file_size for e in entries)<=MAX_PREDICTIONS,'Expanded prediction cap exceeded')
        for entry in entries:
            kind=stat.S_IFMT(entry.external_attr>>16)
            require(not entry.is_dir() and kind in (0,stat.S_IFREG) and not entry.flag_bits&1
                    and entry.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED),'Nonregular/encrypted/unsupported ZIP member')
            with archive.open(entry) as f:
                version=np.lib.format.read_magic(f)
                require(version in [(1,0),(2,0)],'Unsupported NPY version')
                reader=np.lib.format.read_array_header_1_0 if version==(1,0) else np.lib.format.read_array_header_2_0
                shape,_,dtype=reader(f,max_header_size=10000)
                require(shape==shapes[entry.filename] and not dtype.hasobject,'Wrong NPY shape or object dtype')
                if entry.filename in ['expected_counts.npy','bin_left_edges_ms.npy']:
                    require(dtype.kind in 'fiu' and dtype.itemsize<=8,'Predictions/grid must be real numeric, not bool/complex')
                else:require(dtype.kind=='U' and 0<dtype.itemsize<=256,'IDs and metadata must be bounded Unicode')
                require(f.tell()+math.prod(shape)*dtype.itemsize==entry.file_size,'NPY declared payload size differs')
    with np.load(path,allow_pickle=False) as z:bundle={name:z[name] for name in z.files}
    bundle['prediction_units']=text(bundle['prediction_units'],'prediction units')
    bundle['panel_fingerprint']=text(bundle['panel_fingerprint'],'panel fingerprint')
    return bundle


def evaluate(candidate,gold,comparator,metric=None):
    """Any correctly aligned positive prediction is valid; no model-family gate."""
    metric=metric or metric_module()
    require(set(candidate)==FIELDS,'Candidate must contain exactly one rate array and its axes/units/fingerprint')
    require(set(gold)=={'counts_heldout','trial_ids','unit_ids','valid_mask','panel_fingerprint'},'Wrong operator target schema')
    require(set(comparator)==FIELDS,'Wrong fixed-comparator schema')
    fingerprint=text(gold['panel_fingerprint'],'operator panel') if not isinstance(gold['panel_fingerprint'],str) else gold['panel_fingerprint']
    normalized_gold={'target_counts':gold['counts_heldout'],'trial_ids':gold['trial_ids'],
                     'heldout_unit_ids':gold['unit_ids'],'valid_mask':gold['valid_mask'],
                     'bin_left_edges_ms':np.arange(-250,450,5,dtype=float),'panel_fingerprint':fingerprint}
    score=metric.score_submission(candidate,normalized_gold)
    fixed=metric.score_submission(comparator,normalized_gold)
    scored=score['status']=='scored' and fixed['status']=='scored'
    delta=score['co_bps']-fixed['co_bps'] if scored else None
    point=('above' if delta>POINT_TIE_TOL else 'below' if delta < -POINT_TIE_TOL else 'tied_at_numeric_resolution') if scored else 'undefined'
    return {'schema_version':1,'status':'scored_development_candidate' if scored else 'undefined_zero_target_spikes',
            'prediction_contract_valid':True,'positive_gain_required':False,'candidate':score,'fixed_condition_time':fixed,
            'candidate_minus_condition_co_bps':delta,'point_comparison':point,'point_tie_tolerance':POINT_TIE_TOL,
            'panel_fingerprint':fingerprint,'scope':dict(SCOPE),'candidate_code_executed_by_grader':False,
            'candidate_replay_verified':False,'training_only_selection_verified':False,
            'report_consistency':'pending_separate_post_feedback_report','scientific_admission':False,
            'interpretation':'Signed fixed-method comparison on exposed single-session development trials. Positive delta alone does not establish neural-information necessity or statistical significance.'}


def report_check(report,score,score_sha,prediction_sha):
    """Factual consistency only, independent of whether prediction quality is high."""
    require(isinstance(report,dict),'Report must be a JSON object')
    expected={'score_sha256','predictions_sha256','panel_fingerprint','facts','conclusion','scope','limitations'}
    failures=[]
    if set(report)!=expected:failures.append('Missing/extra report fields')
    for key,value in [('score_sha256',score_sha),('predictions_sha256',prediction_sha),('panel_fingerprint',score['panel_fingerprint'])]:
        if report.get(key)!=value:failures.append('Wrong bound '+key)
    facts={'candidate_co_bps':score['candidate']['co_bps'],'condition_co_bps':score['fixed_condition_time']['co_bps'],
           'candidate_minus_condition_co_bps':score['candidate_minus_condition_co_bps'],
           'target_spikes':score['candidate']['target_spikes'],'valid_cells':score['candidate']['valid_cells']}
    provided=report.get('facts')
    if not isinstance(provided,dict) or set(provided)!=set(facts):failures.append('Wrong fact fields')
    else:
        for key,value in facts.items():
            got=provided[key]
            if key in ['target_spikes','valid_cells']:
                correct=type(got) is int and got==value
            else:
                correct=(got is None) if value is None else (type(got) in (int,float) and math.isfinite(got) and math.isclose(got,value,rel_tol=FACT_TOL,abs_tol=FACT_TOL))
            if not correct:failures.append('Incorrect reported '+key)
    conclusion=report.get('conclusion')
    if not isinstance(conclusion,str) or conclusion not in {'above_fixed_comparator','below_fixed_comparator','numerical_tie','insufficient_evidence'}:failures.append('Unknown conclusion')
    elif conclusion!='insufficient_evidence':
        required={'above_fixed_comparator':'above','below_fixed_comparator':'below','numerical_tie':'tied_at_numeric_resolution'}[conclusion]
        if score['point_comparison']!=required:failures.append('Point-comparison conclusion contradicts computed facts')
    if json.dumps(report.get('scope'),sort_keys=True)!=json.dumps(SCOPE,sort_keys=True):failures.append('Unsupported/incorrect scope claim')
    limits=report.get('limitations')
    if not isinstance(limits,str) or not limits.strip() or len(limits)>8000:failures.append('Nonempty bounded limitations statement required')
    return {'report_factual_scope_consistency_pass':not failures,'failures':failures,'conclusion':conclusion,
            'prediction_score_unchanged':score['candidate']['co_bps'],
            'prediction_delta_unchanged':score['candidate_minus_condition_co_bps'],
            'negative_or_insufficient_conclusion_allowed':True,
            'not_assessed':'Narrative reasoning quality, literature insight, provenance of fitting and actual neural information use require separate evidence/review.'}


def pinned_operator(path,digest,keys,cap):
    p=regular(path,cap);require(sha(p)==digest,'Operator artifact hash mismatch')
    with np.load(p,allow_pickle=False) as z:
        require(set(keys)<=set(z.files),'Operator artifact missing fields')
        return {k:z[k] for k in keys}


def validate_submission_bindings(a,lock):
    freeze=read_json(a.submission_freeze)
    expected={'schema_version','attempt_id','predictions_sha256','program_sha256','method_sha256','public_sha256','panel_fingerprint',
              'protocol_sha256','evaluation_lock_sha256','grader_sha256','information_policy','selection_policy','budget_manifest_sha256'}
    require(set(freeze)==expected and freeze['schema_version']==1 and isinstance(freeze['attempt_id'],str) and freeze['attempt_id'],'Invalid submission freeze')
    for path,cap,key in [(a.predictions,MAX_PREDICTIONS,'predictions_sha256'),(a.program,1000000,'program_sha256'),(a.method,100000,'method_sha256')]:
        regular(path,cap);require(sha(path)==freeze[key],'Changed frozen candidate artifact: '+key)
    require(freeze['protocol_sha256']==sha(HERE/'protocol.json') and freeze['evaluation_lock_sha256']==sha(a.evaluation_lock)
            and freeze['grader_sha256']==sha(__file__),'Changed protocol/scorer/evaluation lock')
    require(freeze['public_sha256']==lock['public_sha256'] and freeze['panel_fingerprint']==lock['panel_fingerprint'],'Submission targets different public packet')
    require(freeze['information_policy']=='offline_reference_withheld' and freeze['selection_policy']=='training_labels_only','Wrong primary arm declaration')
    require(isinstance(freeze['budget_manifest_sha256'],str) and len(freeze['budget_manifest_sha256'])==64 and all(x in '0123456789abcdef' for x in freeze['budget_manifest_sha256']),'Invalid budget-manifest digest')
    review=read_json(a.operator_review)
    require(review.get('decision')=='authorize_one_development_candidate_score'
            and review.get('submission_freeze_sha256')==sha(a.submission_freeze)
            and review.get('evaluation_lock_sha256')==sha(a.evaluation_lock)
            and review.get('grader_sha256')==sha(__file__),'Operator review does not authorize exact score')
    return freeze


def main():
    parser=argparse.ArgumentParser(description=__doc__);subs=parser.add_subparsers(dest='action',required=True)
    score=subs.add_parser('score')
    for name in ['predictions','program','method','submission-freeze','evaluation-lock','operator-review','gold','comparator','output']:score.add_argument('--'+name,required=True)
    report=subs.add_parser('check-report')
    for name in ['score','score-lock','report','output']:report.add_argument('--'+name,required=True)
    a=parser.parse_args()
    if a.action=='check-report':
        lock=read_json(a.score_lock)
        require(set(lock)=={'schema_version','score_sha256','predictions_sha256','submission_freeze_sha256'} and lock['schema_version']==1,'Wrong operator score lock')
        require(sha(regular(a.score,1000000))==lock['score_sha256'],'Feedback score changed')
        result=read_json(a.score)
        require(result['provenance']['predictions_sha256']==lock['predictions_sha256'] and result['provenance']['submission_freeze_sha256']==lock['submission_freeze_sha256'],'Score-lock provenance mismatch')
        checked=report_check(read_json(a.report,20000),result,lock['score_sha256'],lock['predictions_sha256'])
        save_json(a.output,checked);return 0 if checked['report_factual_scope_consistency_pass'] else 2
    lock=read_json(a.evaluation_lock)
    require(lock['expected_eval_trials']==574 and lock['expected_bins']==140 and lock['expected_heldout_units']==45,'Wrong full-panel operator lock')
    frozen=validate_submission_bindings(a,lock)
    candidate=candidate_npz(a.predictions,574,45)
    gold=pinned_operator(a.gold,lock['targets_sha256'],['counts_heldout','trial_ids','unit_ids','valid_mask','panel_fingerprint'],16000000)
    source=pinned_operator(a.comparator,lock['comparator_sha256'],['rates_condition_psth','trial_ids','heldout_unit_ids','bin_left_edges_ms','prediction_units','panel_fingerprint'],128000000)
    comparator={k:source[k] for k in ['trial_ids','heldout_unit_ids','bin_left_edges_ms']}
    comparator.update(expected_counts=source['rates_condition_psth'],prediction_units=text(source['prediction_units'],'comparator units'),panel_fingerprint=text(source['panel_fingerprint'],'comparator panel'))
    result=evaluate(candidate,gold,comparator,metric_module(lock['metric_source_sha256']))
    result['provenance']={'attempt_id':frozen['attempt_id'],'predictions_sha256':frozen['predictions_sha256'],'program_sha256':frozen['program_sha256'],
        'method_sha256':frozen['method_sha256'],'submission_freeze_sha256':sha(a.submission_freeze),'evaluation_lock_sha256':sha(a.evaluation_lock),
        'grader_sha256':sha(__file__),'budget_manifest_sha256':frozen['budget_manifest_sha256'],'information_policy':frozen['information_policy'],
        'target_sha256':lock['targets_sha256'],'comparator_sha256':lock['comparator_sha256']}
    save_json(a.output,result)
    save_json(str(a.output)+'.lock.json',{'schema_version':1,'score_sha256':sha(a.output),'predictions_sha256':frozen['predictions_sha256'],'submission_freeze_sha256':sha(a.submission_freeze)})
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError,KeyError,zipfile.BadZipFile) as exc:
        # Operator-gate failures are not automatically a candidate's fault.
        print(json.dumps({'status':'rejected_no_score','error':type(exc).__name__+': '+str(exc),'candidate_code_executed':False}))
        raise SystemExit(2)
