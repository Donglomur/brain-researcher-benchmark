"""Trusted offline scalar timing scorer; no candidate programs or model fits."""
from pathlib import Path
import base64,hashlib,io,json,os,resource,sys,time,unittest
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import numpy as np
from validator import validate
from metrics import score_candidate,METHODS


def require(ok,message):
    if not ok:raise ValueError(message)


def pinned(path,pin,cap):
    p=Path(path);require(p.is_file()and not p.is_symlink()and p.stat().st_nlink==1 and p.stat().st_size==pin['bytes']and 0<pin['bytes']<=cap,'Bounded pinned regular asset')
    require(hashlib.sha256(p.read_bytes()).hexdigest()==pin['sha256'],'Exact asset SHA256');return p


def strict_json(path):
    def unique(pairs):
        d={}
        for k,v in pairs:
            require(k not in d,'Duplicate JSON key');d[k]=v
        return d
    return json.loads(Path(path).read_text(),object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in()).throw(ValueError('Nonfinite JSON token')))


def public_ids(assets):
    p=pinned('/public/identity.json',assets['public']['identity'],10000);obj=strict_json(p)
    require(type(obj)is dict and set(obj)=={'schema_version','case_id'}and type(obj['schema_version'])is int and obj['schema_version']==1,'Exact public identity envelope')
    ids=obj['case_id'];require(type(ids)is list and len(ids)==258 and len(set(ids))==258 and all(type(x)is str and x.startswith('dmfc-')and len(x)==11 and x[5:].isdigit()for x in ids),'258 canonical public trial IDs')
    return ids


def frozen_submission():
    source=Path('/input/submission.npz');expected=os.environ.get('EXPECTED_SUBMISSION_SHA256','')
    require(len(expected)==64,'Exact host candidate hash required')
    require(source.is_file()and not source.is_symlink()and source.stat().st_nlink==1 and source.stat().st_size<=1048576,'Bounded regular candidate')
    dest=Path('/tmp/submission.npz');h=hashlib.sha256();n=0
    with source.open('rb')as f,dest.open('xb')as g:
        while block:=f.read(65536):
            n+=len(block);require(n<=1048576,'Candidate growth beyond cap');h.update(block);g.write(block)
    dest.chmod(0o400);require(h.hexdigest()==expected,'Candidate changed after dispatch hash');return dest


def qualification(assets,ids):
    tests=unittest.TextTestRunner(stream=sys.stderr,verbosity=1).run(unittest.defaultTestLoader.loadTestsFromName('test_adapter'))
    require(tests.wasSuccessful(),'Generated adapter qualification failed')
    p=pinned('/reference/predictions.json',assets['verification_references'],100000);obj=strict_json(p)
    require(type(obj)is dict and set(obj)=={'schema_version','case_id','predictions_ms'}and obj['schema_version']==1 and obj['case_id']==ids and set(obj['predictions_ms'])==set(METHODS),'Exact reference prediction identity/schema')
    allids=np.asarray(ids);fixtures={};pins={}
    def put(name,case_ids,values):
        buffer=io.BytesIO();np.savez(buffer,case_id=case_ids,prediction_ms=values);body=buffer.getvalue();require(len(body)<=1048576,'Fixturecap')
        fixtures[name]=base64.b64encode(body).decode();pins[name]={'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
    for name,arm in [('valid_total_spike','cue_clock_total_spike_ridge'),('valid_temporal','cue_clock_temporal_spike_ridge')]:
        values=np.asarray(obj['predictions_ms'][arm],dtype=np.float64);require(values.shape==(258,)and np.isfinite(values).all(),'Reference finite geometry');put(name,allids,values)
    put('wrong_shape',allids,np.zeros(257,dtype=np.float64))
    badids=allids.copy();badids[0]='dmfc-999999';require('dmfc-999999'not in ids,'Distinct generated incorrect identity');put('wrong_ids',badids,np.zeros(258,dtype=np.float64))
    fixtures['empty']='';pins['empty']={'bytes':0,'sha256':hashlib.sha256(b'').hexdigest()}
    require(sum(x['bytes']for x in pins.values())<=350000,'All fixture bytecap')
    return {'status':'qualification_fixtures_prepared','generated_tests':tests.testsRun,'fixtures_base64':fixtures,'fixture_pins':pins,'private_loader_invocations':0,'private_assets_read':False,'new_fits':0}


def references(assets):
    g=strict_json(pinned('/input/reference_grade.json',assets['private']['reference_grade'],100000))
    c=strict_json(pinned('/input/reference_commit.json',assets['private']['reference_commit'],10000))
    a=strict_json(pinned('/input/reference_audit.json',assets['private']['reference_audit'],10000))
    require(c['status']=='producer_removed_outputs_committed'and c['all_owned_producers_absent']is True,'Stopped reference producer lineage')
    for ck,ap in [('predictions',assets['verification_references']),('public_identity',assets['public']['identity']),('private_targets',assets['private']['targets'])]:
        require(c[ck]=={k:ap[k]for k in('bytes','sha256')},'Committed reference input/output identity')
    require(g['status']=='continuous_fixed_reference_panel_scored'and g['candidate_id']=='NEURAL-095'and g['public_validation_before_private_decode']is True and g['private_loader_invocations']==1,'Reference complete public-before-private qualification')
    require(g['predictions']==c['predictions']and set(g['scores'])==set(METHODS),'Exact frozen reference output lineage')
    require(a['status']=='passed'and a['independent_scalar_checks']==280 and a['score_sha256']==assets['private']['reference_grade']['sha256'],'Independent saved reference arithmetic')
    return g


def main():
    started=time.monotonic();stage='operator_inputs'
    result={'candidate_id':'NEURAL-095','status':'started','private_loader_invocations':0,'scientific_score_computed':False,'candidate_code_executed':False,'new_fits':0,'scientific_success_threshold':None}
    try:
        require(len(sys.argv)==2 and sys.argv[1]in('score','validate','prepare'),'Fixed action')
        action=sys.argv[1];assets=strict_json(HERE/'assets.json');require(assets['candidate_id']=='NEURAL-095'and assets['n']==258,'Exact task asset manifest')
        ids=public_ids(assets)
        if action=='prepare':result.update(qualification(assets,ids));return result,0
        stage='candidate_validation';candidate=frozen_submission();ordered=validate(candidate,ids)
        result.update(prediction_contract_valid=True,submission_sha256=os.environ['EXPECTED_SUBMISSION_SHA256'],trial_count=258)
        if action=='validate':result.update(status='valid_prediction_contract',private_assets_read=False);return result,0
        stage='private_score';reference=references(assets)
        def private_loader():
            p=pinned('/targets/query_targets.npz',assets['private']['targets'],100000);result['private_loader_invocations']+=1
            with np.load(p,allow_pickle=False)as z:values={k:z[k]for k in z.files}
            require(set(values)=={'case_id','tp_ms','condition','context'}and values['case_id'].dtype.kind=='U'and values['case_id'].tolist()==ids,'Exact private target/public ID join')
            return values
        scored=score_candidate(ordered,private_loader,reference);result.update(scored)
        result.update(scientific_score_computed=True,primary_metric=result['candidate']['mae_ms'],metric_name='mae_ms',higher_is_better=False,
            reference_lineage={'source_freeze_sha256':assets['reference_source_freeze']['sha256'],'runtime_freeze_sha256':assets['reference_runtime_freeze']['sha256'],'grade_sha256':assets['private']['reference_grade']['sha256'],'independent_scalar_checks':280,'fits_recomputed':False},
            limits=['One public historical Haydn20161211 session; no biological population CI or p-value.','Prediction AT Set from strictly pre-Set processed spikes; not a 200ms advance forecast or online spike sorting claim.','Released behavioral tp target is not replaced with Go-minus-Set; hand-clock provenance remains unresolved.','Authored fixed comparators, no SOTA, causal mechanism, native LLM or scientific pass-floor claim.'])
        return result,0
    except Exception as exc:
        result.update(status='invalid_submission'if stage=='candidate_validation'else'scoring_error',error=type(exc).__name__+': '+str(exc),scientific_score_computed=False);return result,2
    finally:
        usage=resource.getrusage(resource.RUSAGE_SELF)
        result['resources']={'wall_seconds':time.monotonic()-started,'cpu_including_imports_seconds':usage.ru_utime+usage.ru_stime,'peak_rss_bytes':usage.ru_maxrss*1024,'cgroup_peak_bytes':int(Path('/sys/fs/cgroup/memory.peak').read_text())}


if __name__=='__main__':
    value,code=main();print(json.dumps(value,allow_nan=False,separators=(',',':')));raise SystemExit(code)
