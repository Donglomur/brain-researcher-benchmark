"""Complete original-source receipts; no accuracy bands or narrative scoring."""
import csv
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path
import numpy as np

WINDOWS=[('headline_pre',-200,-50),('control_post',0,400)]+[(f'curve_{(-500+50*i)/1000:.3f}',-500+50*i,-300+50*i) for i in range(19)]
NAMES=tuple(w[0] for w in WINDOWS)
SOURCE_FIELDS='source_trial_row trial_id stimulus_time_s feedback_time_s choice_registration_time_s wheel_movement_onset_time_s choice rewarded eligible selected selection_reason fold'.split()
PRED_FIELDS='analysis source_trial_row trial_id fold label prediction decision_score window_start_s window_end_s'.split()
FOLD_FIELDS='analysis fold n_train_trials n_test_trials n_train_class0 n_train_class1 n_test_class0 n_test_class1 n_correct accuracy'.split()
CURVE_FIELDS='analysis window_start_s window_end_s accuracy pooled_oof_accuracy accuracy_sd'.split()
COUNT_FIELDS='analysis window_start_s window_end_s source_trial_row trial_id source_unit_row unit_id spike_count'.split()
SUPPORT_FIELDS='n_starts_before_trial_start n_ends_after_trial_stop n_starts_before_stimulus n_ends_after_choice_registration n_starts_before_task_epoch n_ends_after_task_epoch n_overlapping_selected_window_pairs'.split()

def require(ok,message):
    if not ok: raise AssertionError(message)

def integer(x):
    require(not isinstance(x,(bool,np.bool_)),'Boolean is not an integer')
    try: value=Decimal(str(x))
    except (InvalidOperation,ValueError,TypeError): raise AssertionError('Invalid integer')
    require(value.is_finite() and value==value.to_integral_value(),'Nonfinite/fractional integer')
    return int(value)

def number(x):
    require(not isinstance(x,(bool,np.bool_)),'Boolean is not a measurement')
    try: value=float(x)
    except (ValueError,TypeError,OverflowError): raise AssertionError('Invalid measurement')
    require(math.isfinite(value),'Nonfinite measurement')
    return value

def close(a,b,atol=1e-6,rtol=0,label='measurement'):
    a,b=number(a),number(b)
    require(abs(a-b)<=atol+rtol*abs(b),f'{label} differs from original source/declared arithmetic')

def json_load(path):
    def pairs(rows):
        result={}
        for k,v in rows:
            require(k not in result,'Duplicate JSON key'); result[k]=v
        return result
    return json.loads(Path(path).read_text(),object_pairs_hook=pairs,parse_constant=lambda x: (_ for _ in ()).throw(AssertionError('Nonfinite JSON')))

def csv_load(path,fields):
    with Path(path).open(newline='') as f:
        reader=csv.DictReader(f)
        require(reader.fieldnames and len(set(reader.fieldnames))==len(reader.fieldnames),'Missing/duplicate CSV headers')
        require(set(fields)<=set(reader.fieldnames),'Missing required columns')
        rows=list(reader)
    require(rows and all(None not in r and all(v is not None for v in r.values()) for r in rows),'Empty/malformed CSV')
    return rows

def match(a,b,label='metadata',atol=0,closed=False):
    if isinstance(b,dict):
        require(isinstance(a,dict) and set(b)<=set(a),f'Missing {label} fields')
        if closed: require(set(a)==set(b),f'Unexpected {label} scientific fields')
        for k,v in b.items(): match(a[k],v,label+'.'+k,atol,closed)
    elif isinstance(b,list):
        require(isinstance(a,list) and len(a)==len(b),f'Wrong {label} list')
        for x,y in zip(a,b): match(x,y,label,atol,closed)
    elif b is None: require(a is None,f'Undefined {label} must be null')
    elif isinstance(b,bool): require(isinstance(a,bool) and a==b,f'Wrong {label} Boolean')
    elif isinstance(b,int): require(isinstance(a,(int,float)) and not isinstance(a,bool) and integer(a)==b,f'Wrong {label} integer')
    elif isinstance(b,float):
        require(isinstance(a,(int,float)) and not isinstance(a,bool),f'Wrong {label} type'); close(a,b,atol,0,label)
    else: require(isinstance(a,str) and a==b,f'Wrong {label} text')

def keyed(rows,fields):
    result={}
    for r in rows:
        key=tuple(r[k] if k=='analysis' else integer(r[k]) for k in fields)
        require(key not in result,'Duplicate keyed row'); result[key]=r
    return result

def validate_source(rows,ref):
    actual=keyed(rows,['source_trial_row']); expected=keyed(ref['source_rows'],['source_trial_row'])
    require(set(actual)==set(expected),'Complete original trial ledger required')
    for key,wanted in expected.items():
        for field,value in wanted.items():
            x=actual[key][field]
            if value is None: require(x=='','Undefined source value must be empty')
            elif field.endswith('_time_s'): close(x,value,1e-9,0,'original source time')
            elif field in ('choice','selection_reason'): require(x==value,'Wrong source choice/reason')
            else: require(integer(x)==value,'Wrong source identity/selection/fold')

def int_array(value,label):
    x=np.asarray(value)
    require(x.dtype.kind in 'iu',f'{label} must be integer, not bool/float/object')
    require(not x.size or (int(x.min())>=-(2**63) and int(x.max())<2**63),f'{label} integer overflow')
    return x.astype(np.int64,copy=False)

def axis_order(actual,wanted,label):
    require(actual.ndim==1 and len(actual)==len(wanted),f'Incomplete {label} axis')
    ids=actual.tolist(); require(len(set(ids))==len(ids) and set(ids)==set(wanted.tolist()),f'Wrong/duplicate {label} axis')
    index={v:i for i,v in enumerate(ids)}
    return np.array([index[v] for v in wanted.tolist()])

def validate_counts(path,ref):
    with np.load(path,allow_pickle=False) as z:
        require(set(COUNT_FIELDS)<=set(z.files),'Missing count tensor axes')
        values={k:np.array(z[k]) for k in z.files}
    require(all(x.dtype.kind in 'biufUS' for x in values.values()),'Nonprimitive receipt')
    require(values['analysis'].dtype.kind=='U','Unicode analysis IDs required')
    a=axis_order(values['analysis'],ref['analysis'],'analysis')
    t=axis_order(int_array(values['source_trial_row'],'trial row'),ref['source_trial_row'],'trial')
    u=axis_order(int_array(values['source_unit_row'],'unit row'),ref['source_unit_row'],'unit')
    for k,order in [('trial_id',t),('unit_id',u)]:
        x=int_array(values[k],k); require(x.shape==ref[k].shape and np.array_equal(x[order],ref[k]),'Wrong original NWB ID')
    for k in ('window_start_s','window_end_s'):
        x=values[k]; require(x.dtype.kind=='f' and x.shape==(21,) and np.isfinite(x).all(),'Invalid window axis')
        require(np.all(np.abs(x[a]-ref[k])<=1e-9),'Wrong count window')
    counts=int_array(values['spike_count'],'spike counts')
    require(counts.shape==ref['spike_count'].shape and np.all(counts>=0),'Incomplete/negative counts')
    require(np.array_equal(counts[np.ix_(a,t,u)],ref['spike_count']),'Spike counts differ from original occurrences')

def validate_predictions(rows,ref):
    require(len(rows)==21*len(ref['labels']),'Complete OOF table required')
    index={int(v):i for i,v in enumerate(ref['source_trial_row'])}; seen=set(); pred=np.empty(ref['scores'].shape,dtype=np.int8)
    for row in rows:
        name,source=row['analysis'],integer(row['source_trial_row'])
        require(name in NAMES and source in index,'Unknown source trial/analysis')
        ai,ti=NAMES.index(name),index[source]
        require((ai,ti) not in seen,'Duplicate OOF trial'); seen.add((ai,ti))
        for k,rk in [('trial_id','trial_id'),('fold','folds'),('label','labels')]: require(integer(row[k])==int(ref[rk][ti]),'Wrong source ID/label/shared fold')
        for k in ('window_start_s','window_end_s'): close(row[k],ref[k][ai],1e-9,0,'prediction window')
        score=number(row['decision_score']); close(score,ref['scores'][ai,ti],1e-5,1e-6,'source model decision score')
        p=integer(row['prediction']); require(p in (0,1) and p==int(score>0),'Prediction must follow submitted score')
        pred[ai,ti]=p
    return pred

def summarize(ref,pred):
    y,f=ref['labels'],ref['folds']; folds=[]; analyses=[]; curve=[]
    for ai,name in enumerate(NAMES):
        accuracies=[]
        for fold in range(5):
            te,tr=f==fold,f!=fold; nc=int(np.sum(pred[ai,te]==y[te])); acc=nc/int(te.sum()); accuracies.append(acc)
            folds.append(dict(analysis=name,fold=fold,n_train_trials=int(tr.sum()),n_test_trials=int(te.sum()),
                n_train_class0=int(np.sum(y[tr]==0)),n_train_class1=int(np.sum(y[tr]==1)),n_test_class0=int(np.sum(y[te]==0)),n_test_class1=int(np.sum(y[te]==1)),n_correct=nc,accuracy=acc))
        s=dict(analysis=name,mean_accuracy=float(np.mean(accuracies)),pooled_oof_accuracy=float(np.mean(pred[ai]==y)),accuracy_sd=float(np.std(accuracies)))
        analyses.append(s)
        if ai>=2: curve.append(dict(analysis=name,window_start_s=float(ref['window_start_s'][ai]),window_end_s=float(ref['window_end_s'][ai]),accuracy=s['mean_accuracy'],pooled_oof_accuracy=s['pooled_oof_accuracy'],accuracy_sd=s['accuracy_sd']))
    eligible=[r for r in ref['source_rows'] if r['eligible']]
    result=dict(status='complete',n_source_trials=len(ref['source_rows']),n_eligible_trials=len(eligible),n_selected_trials=len(y),n_units=len(ref['unit_id']),
        eligible_class_counts={str(c):sum(r['rewarded']==c for r in eligible) for c in (0,1)},selected_class_counts={str(c):int(np.sum(y==c)) for c in (0,1)},chance=.5,
        headline=analyses[0],post_feedback=analyses[1],post_minus_pre=analyses[1]['mean_accuracy']-analyses[0]['mean_accuracy'],analyses=analyses)
    return folds,curve,result

def validate_table(rows,expected,fields,keys):
    a,b=keyed(rows,keys),keyed(expected,keys); require(set(a)==set(b),'Incomplete aggregate table')
    for key,r in b.items():
        for field,v in r.items():
            x=a[key][field]
            if isinstance(v,str): require(x==v,'Wrong analysis')
            elif isinstance(v,int): require(integer(x)==v,'Wrong aggregate count')
            else:
                if field in ('accuracy','pooled_oof_accuracy','accuracy_sd'): require(0<=number(x)<=1,'Invalid accuracy domain')
                close(x,v,1e-9 if field.endswith('_s') else 1e-6,0,'recomputed aggregate')

def validate_results(actual,expected):
    match(actual,{k:v for k,v in expected.items() if k!='analyses'},'results',1e-6)
    for k in ('eligible_class_counts','selected_class_counts'): match(actual[k],expected[k],k,closed=True)
    a,b=keyed(actual['analyses'],['analysis']),keyed(expected['analyses'],['analysis']); require(set(a)==set(b),'Complete analysis summaries required')
    for k in b: match(a[k],b[k],'analysis result',1e-6)
    for row in actual['analyses']+[actual['headline'],actual['post_feedback']]:
        for k in ('mean_accuracy','pooled_oof_accuracy','accuracy_sd'): require(0<=number(row[k])<=1,'Invalid result domain')

def validate_metadata(actual,ref):
    expected=ref['metadata']
    if 'status' in actual: require(actual['status'] in ('complete','ok'),'Contradictory incomplete/failure metadata status')
    for k in ('source','method'): match(actual.get(k),expected[k],k,closed=True)
    for k in ('source_manifest_sha256','method_contract_sha256'): require(actual.get(k)==expected[k],'Wrong frozen fingerprint')
    match(actual.get('source_summary'),expected['source_summary'],'source_summary',1e-9)
    for k in ('kilosort_label_counts','ibl_quality_score_counts','probe_counts'): match(actual['source_summary'][k],expected['source_summary'][k],k,closed=True)
    a,b=keyed(actual.get('support_by_analysis',[]),['analysis']),keyed(expected['support_by_analysis'],['analysis']); require(set(a)==set(b),'Complete source support metadata required')
    for k in b: match(a[k],b[k],'window support')
    software=actual.get('software'); require(isinstance(software,dict) and software and all(isinstance(k,str) and k.strip() and isinstance(v,str) and v.strip() for k,v in software.items()),'Actual software/version mapping required')
    fits=actual.get('fits'); require(isinstance(fits,list) and len(fits)==105,'Complete105 fit diagnostics required'); seen=set()
    for r in fits:
        require(isinstance(r,dict) and {'analysis','fold','mean_gradient_inf','finite_parameters','optimizer_status','warnings'}<=set(r),'Missing fit diagnostics')
        key=r['analysis'],integer(r['fold']); require(key not in seen and key[0] in NAMES and 0<=key[1]<5,'Wrong/duplicate fit key'); seen.add(key)
        require(r['finite_parameters'] is True and 0<=number(r['mean_gradient_inf'])<=1e-9,'Fit violates public convergence criterion')
        s=r['optimizer_status']; require((isinstance(s,str) and bool(s.strip())) or (isinstance(s,(int,float)) and not isinstance(s,bool) and math.isfinite(s)),'Raw optimizer status required')
        require(isinstance(r['warnings'],list) and all(isinstance(w,str) for w in r['warnings']),'Warning strings required')

def validate_output_directory(output,ref):
    output=Path(output)
    validate_source(csv_load(output/'source_trials.csv',SOURCE_FIELDS),ref)
    validate_counts(output/'spike_counts.npz',ref)
    pred=validate_predictions(csv_load(output/'trial_predictions.csv',PRED_FIELDS),ref)
    folds,curve,result=summarize(ref,pred)
    validate_table(csv_load(output/'folds.csv',FOLD_FIELDS),folds,FOLD_FIELDS,['analysis','fold'])
    validate_table(csv_load(output/'decoding_vs_window.csv',CURVE_FIELDS),curve,CURVE_FIELDS,['analysis'])
    validate_results(json_load(output/'results.json'),result)
    validate_metadata(json_load(output/'run_metadata.json'),ref)
    require((output/'findings.md').read_text().strip(),'Nonempty findings required')
    return result
