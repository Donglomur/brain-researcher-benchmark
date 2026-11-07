"""Fixed offline scorer or generated qualification; never executes candidate code."""
from pathlib import Path
import base64,hashlib,io,json,os,resource,sys,time,unittest
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import numpy as np
from validator import validate,InvalidSubmission
from metrics import score_candidate

REFERENCE_FREEZE='d26188086287b1a672b17ed33415f30748942b83718cca4093f462e0b40ec782'
CASES=('development-001','development-002')


def require(ok,message):
    if not ok:raise ValueError(message)


def pinned(path,pin,cap):
    p=Path(path);require(p.is_file()and not p.is_symlink()and p.stat().st_nlink==1 and p.stat().st_size==pin['bytes']and 0<pin['bytes']<=cap,'Bounded pinned regular asset')
    require(hashlib.sha256(p.read_bytes()).hexdigest()==pin['sha256'],'Exact asset SHA256');return p


def public_ids(assets):
    result={}
    for case in CASES:
        p=pinned('/public/'+case+'.npz',assets['public']['cases'][case]['features'],2000000)
        with np.load(p,allow_pickle=False)as z:
            require('labels'not in z.files,'No private target in public feature packet')
            ids=z['trial_ids'];name=z['case_id']
        require(str(name)==case and ids.shape==(200,)and ids.dtype.kind=='U'and len(np.unique(ids))==200 and all(v.startswith(case+'-')for v in ids.tolist()),'Qualified complete public person identity')
        result[case]=ids
    require(len(set(np.concatenate(list(result.values())).tolist()))==400,'400 globally unique public IDs')
    return result


def frozen_submission():
    source=Path('/input/submission.npz');expected=os.environ.get('EXPECTED_SUBMISSION_SHA256','')
    require(len(expected)==64,'Exact host candidate hash required')
    require(source.is_file()and not source.is_symlink()and source.stat().st_nlink==1 and source.stat().st_size<=1048576,'Bounded regular candidate')
    dest=Path('/tmp/submission.npz');h=hashlib.sha256();n=0
    with source.open('rb')as f,dest.open('xb')as g:
        while block:=f.read(65536):
            n+=len(block);require(n<=1048576,'Candidate growth beyond cap');h.update(block);g.write(block)
    dest.chmod(0o400);require(h.hexdigest()==expected,'Candidate changed after dispatch hash')
    return dest


def qualification(assets,ids):
    tests=unittest.TextTestRunner(stream=sys.stderr,verbosity=1).run(unittest.defaultTestLoader.loadTestsFromName('test_adapter'))
    require(tests.wasSuccessful(),'Generated adapter qualification failed')
    predictions={}
    for case in CASES:
        p=pinned('/reference/'+case+'.npz',assets['verification_references'][case],100000)
        with np.load(p,allow_pickle=False)as z:
            require(np.array_equal(z['trial_ids'],ids[case])and str(z['case_id'])==case,'Reference prediction/public ID parity')
            predictions[case]={arm:z[arm]for arm in('eeg','prior')}
    allids=np.concatenate([ids[c]for c in CASES]);fixtures={};counts={}
    def put(name,trial_ids,p):
        buffer=io.BytesIO();np.savez(buffer,trial_ids=trial_ids,target_probability=p);value=buffer.getvalue();require(len(value)<=1048576,'Fixturecap')
        fixtures[name]=base64.b64encode(value).decode();counts[name]={'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest()}
    for arm in('eeg','prior'):put('valid_'+arm,allids,np.concatenate([predictions[c][arm]for c in CASES]))
    put('wrong_shape',allids,np.zeros(399,dtype=np.float64))
    put('missing_case',ids[CASES[0]],predictions[CASES[0]]['eeg'])
    fixtures['empty']='';counts['empty']={'bytes':0,'sha256':hashlib.sha256(b'').hexdigest()}
    require(sum(v['bytes']for v in counts.values())<=350000,'All generated fixture artifactcap')
    return {'status':'qualification_fixtures_prepared','generated_tests':tests.testsRun,'fixtures_base64':fixtures,'fixture_pins':counts,'target_loader_invocations':0,'private_assets_read':False,'new_fits':0}


def references(assets):
    grade=json.loads(pinned('/input/reference_grade.json',assets['private']['reference_grade'],100000).read_text())
    commit=json.loads(pinned('/input/reference_commit.json',assets['private']['reference_commit'],10000).read_text())
    require(commit['status']=='predictions_frozen_before_private_grade'and commit['producer_removed_and_absent']is True and commit['source_freeze_sha256']==REFERENCE_FREEZE==assets['reference_freeze'],'Stopped fixed reference lineage')
    require(set(commit['files'])=={'development-001.npz','development-002.npz','diagnostics.json'},'Complete reference output inventory')
    for case in CASES:require(commit['files'][case+'.npz']['sha256']==assets['verification_references'][case]['sha256'],'Exact reference artifact identity')
    audit=grade['independent_arithmetic']
    require(grade['status']=='erp_reference_scored_and_audited'and grade['all_public_validated_before_targets']is True and grade['target_loader_invocations']==2 and audit['status']=='passed'and audit['checks']==391 and audit['comparison_defined']is True,'Qualified complete reference arithmetic')
    return grade['scores']


def main():
    started=time.monotonic();stage='operator_inputs'
    result={'candidate_id':'NEURAL-077','status':'started','target_loader_invocations':0,'scientific_score_computed':False,'candidate_code_executed':False,'new_fits':0,'scientific_success_threshold':None}
    try:
        require(len(sys.argv)==2 and sys.argv[1]in('score','validate','prepare'),'Fixed action')
        action=sys.argv[1];assets=json.loads((HERE/'assets.json').read_text());require(assets['candidate_id']=='NEURAL-077'and tuple(assets['case_ids'])==CASES,'Exact task asset manifest')
        ids=public_ids(assets)
        if action=='prepare':result.update(qualification(assets,ids));return result,0
        stage='candidate_validation';candidate=frozen_submission();ordered=validate(candidate,ids)
        result.update(prediction_contract_valid=True,submission_sha256=os.environ['EXPECTED_SUBMISSION_SHA256'],trial_count=400,people=2)
        if action=='validate':result.update(status='valid_prediction_contract',private_assets_read=False);return result,0
        stage='private_score';reference=references(assets)
        def private_loader(case):
            p=pinned('/targets/'+case+'.npz',assets['private']['targets'][case],100000)
            result['target_loader_invocations']+=1
            with np.load(p,allow_pickle=False)as z:values={k:z[k]for k in z.files}
            require(set(values)=={'trial_ids','labels','case_id'}and str(values['case_id'])==case and np.array_equal(values['trial_ids'],ids[case]),'Exact private target/public ID join')
            return values['labels']
        scored=score_candidate(ordered,private_loader,reference);result.update(scored)
        result.update(scientific_score_computed=True,primary_metric=result['candidate']['participant_macro_balanced_accuracy'],metric_name='participant_macro_balanced_accuracy',higher_is_better=True,
                      reference_lineage={'source_freeze_sha256':REFERENCE_FREEZE,'grade_sha256':assets['private']['reference_grade']['sha256'],'prior_arithmetic_checks':391,'fits_recomputed':False},
                      limits=['Two historical development people; no population confidence interval.','Released marker clock, zero added shift; no physical P3 latency or pre-response claim.','Poststimulus activity may contain motor/ocular effects; score is not native LLM understanding.','Authored fixed references, not published SOTA or acceptance thresholds.'])
        return result,0
    except Exception as exc:
        result.update(status='invalid_submission'if stage=='candidate_validation'else'scoring_error',error=type(exc).__name__+': '+str(exc),scientific_score_computed=False);return result,2
    finally:
        usage=resource.getrusage(resource.RUSAGE_SELF)
        result['resources']={'wall_seconds':time.monotonic()-started,'cpu_including_imports_seconds':usage.ru_utime+usage.ru_stime,'peak_rss_bytes':usage.ru_maxrss*1024,'cgroup_peak_bytes':int(Path('/sys/fs/cgroup/memory.peak').read_text())}


if __name__=='__main__':
    value,code=main();print(json.dumps(value,allow_nan=False,separators=(',',':')));raise SystemExit(code)
