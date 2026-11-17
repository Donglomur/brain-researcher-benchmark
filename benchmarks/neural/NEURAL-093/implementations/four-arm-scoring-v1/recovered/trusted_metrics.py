"""All156 public outputs first, then exact protected SESSION targets.

This is a trusted operator component, not a candidate metric input API. Source
authentication and lifecycle evidence are required from the coordinator. NumPy
is supplied by the eventual pinned trusted numerical environment; no install,
model evaluation or target access occurs during source construction.
"""
import math
from deps import load
D=load(); c=D['controls']; m=D['comparison']; core=D['score_core']
MAX_PREDICTION=262144

def validate_outputs(panel,commit,raw_outputs,np):
    sessions=m.validate_commit(panel,commit)
    expected={(s['session_token'],arm) for s in sessions for arm in c.ARMS}
    c.need(type(raw_outputs)is dict and set(raw_outputs)==expected,'all156 output bytes before any private reader')
    parsed={}
    for s in sessions:
        for arm in c.ARMS:
            key=(s['session_token'],arm); raw=raw_outputs[key]
            c.need(type(raw)is bytes and 0<len(raw)<=MAX_PREDICTION,'bounded exact prediction bytes before hashing')
            c.need(c.pin(raw)==commit['sessions'][key[0]]['arms'][arm]['prediction'],'sealed prediction identity')
            doc=c.parse(raw,MAX_PREDICTION)
            m.fields(doc,('schema','arm','session_token','candidate_sha256','predictions'),'strict public prediction fields')
            c.need(doc['schema']=='neural093-candidate-predictions-v1' and doc['arm']==arm
                and doc['session_token']==s['session_token'] and doc['candidate_sha256']==commit['program_sha256'],
                'original wire schema extended only by explicit four-arm names')
            rows=doc['predictions']; tokens=s['query_tokens']; by={}
            c.need(type(rows)is list and len(rows)==len(tokens),'complete prediction rows')
            for row in rows:
                m.fields(row,('token','probabilities'),'exact prediction row')
                token=row['token']; values=row['probabilities']
                c.need(type(token)is str and token in tokens and token not in by,'unique source query token')
                c.need(type(values)is list and len(values)==3 and all(type(v)in(int,float)
                    and math.isfinite(v) and 0<=v<=1 for v in values),'finite nonboolean three-class probabilities')
                by[token]=values
            parsed[key]=core.probabilities(np.asarray([by[t] for t in tokens],dtype=np.float64),np)
    return parsed

def score(panel,plan,commit,raw_outputs,private_reader,np,checkpoint=lambda:None):
    """private_reader receives only a plan-bound descriptor, after full validation."""
    parsed=validate_outputs(panel,commit,raw_outputs,np)
    checkpoint(); records=[]
    for s,p in zip(panel['sessions'],plan['sessions']):
        checkpoint()
        descriptor=p['private_mapping']; raw=private_reader(descriptor)
        c.need(type(raw)is bytes and len(raw)<=2097152 and c.pin(raw)=={k:descriptor[k] for k in ('bytes','sha256')},
            'exact private SESSION body before decoding')
        mapping=c.parse(raw,2097152)
        c.need(mapping['schema']=='neural093-candidate-private-session-v1'
            and all(mapping[k]==s[k] for k in ('ordinal','session','mouse','session_token')),'same original session/mouse')
        query=mapping['query']
        c.need(type(query)is list and [x['token'] for x in query]==s['query_tokens']
            and all(type(x['source_row'])is int and x['source_row']>=0 and type(x['target'])is int
                and 0<=x['target']<3 for x in query)
            and len({x['source_row'] for x in query})==len(query),'exact full private ordered support')
        for arm in c.ORIGINAL_ARMS:
            raw_manifest=s['original_manifest_bytes'][arm]['query']
            original=mapping['public_manifests'][arm]['query']
            c.need(all(original[k]==c.pin(raw_manifest)[k] for k in ('bytes','sha256')),'private mapping joins original public query manifests')
        labels=np.asarray([x['target'] for x in query],dtype=np.int64)
        onehot=np.eye(3,dtype=np.float64)[labels]
        for arm in c.ARMS:
            probabilities=parsed[(s['session_token'],arm)]
            values={'natural_log_loss':core.mean_log_loss(probabilities,labels,np),
                'multiclass_Brier_mean_sum3':float(np.mean(np.sum((probabilities-onehot)**2,axis=1))),
                'top1_accuracy':float(np.mean(np.argmax(probabilities,axis=1)==labels))}
            records.append(dict(session_token=s['session_token'],arm=arm,
                **{k:commit[k] for k in ('program_sha256','recipe_sha256','tuning_policy_sha256')},
                prediction=commit['sessions'][s['session_token']]['arms'][arm]['prediction'],
                query_tokens=list(s['query_tokens']),metric_core_sha256=m.METRIC_CORE_SHA256,
                metrics={k:m.extended(v) for k,v in values.items()}))
    checkpoint(); summary=m.summarize(panel,commit,records)
    summary['uncertainty']=bootstrap(summary,np)
    summary['metric_rows_computed_by_trusted_component']=True
    summary['numpy_version']=str(np.__version__)
    joint=summary['equal_mouse_absolute_metrics']['neural_wheel_plus_context']['natural_log_loss']
    summary['unchanged_uniform_formula_for_this_study_joint']=dict(
        formula='ln(3) minus equal-mouse candidate joint natural log loss',
        value=m.extended(math.log(3.)-m.number(joint)),historical_run_replaced=False,
        original_two_arm_benchmark_modified=False)
    checkpoint()
    return summary

def bootstrap(summary,np):
    """Preselected primary only; equal-session effects paired at ten mice."""
    rows=summary['mouse_records']
    c.need(len(rows)==10 and len({r['mouse'] for r in rows})==10
        and [r['mouse'] for r in rows]==sorted(r['mouse'] for r in rows),'complete canonical ten-mouse order')
    effects=[m.number(r['effects']['neural_increment_given_wheel_context']['natural_log_loss']) for r in rows]
    result=dict(schema='neural093_paired_mouse_primary_interval_v1',contrast='neural_increment_given_wheel_context',
        metric='natural_log_loss',mouse_count=10,draws=10000,seed=20261102,generator='PCG64',
        interval_percentiles=[2.5,97.5],quantile_method='linear',conditional_on_fitted_models=True,
        includes_training_randomness=False,causal_interval=False)
    if not all(math.isfinite(x) for x in effects):
        return dict(result,status='undefined_nonfinite_mouse_effect',lower=None,upper=None)
    rng=np.random.Generator(np.random.PCG64(20261102))
    sampled=rng.integers(0,len(rows),size=(10000,len(rows)),dtype=np.int64)
    draws=np.asarray(effects,dtype=np.float64)[sampled].mean(axis=1)
    low,high=np.quantile(draws,[.025,.975],method='linear')
    return dict(result,status='finite',lower=float(low),upper=float(high))
