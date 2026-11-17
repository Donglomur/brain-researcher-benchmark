"""Trusted arbitrary forecasting-submission validator/scorer; no candidate code."""
from pathlib import Path
import hashlib,json,os,resource,sys,time
import numpy as np
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import scoring_core as core


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def pinned(path,pin):
    p=core.regular(path,max(pin['bytes'],1));core.require(p.stat().st_size==pin['bytes']and sha(p)==pin['sha256'],'Pinned operator/public asset changed');return p


def main():
    start=time.monotonic();action=sys.argv[1];assets=json.loads((HERE/'assets.json').read_text())
    result={'candidate_id':'NEURAL-018','status':'started','candidate_code_executed':False,'target_loader_invocations':0,'new_fits':0,'scientific_success_threshold':None}
    try:
        past=pinned('/input/public.npz',assets['public']['past']);manifest=json.loads(pinned('/input/manifest.json',assets['public']['manifest']).read_text())
        with np.load(past,allow_pickle=False)as z:trial_ids=z['eval_trial_ids']
        public={'trial_ids':trial_ids,'forecast_unit_ids':np.asarray(manifest['identity_recipe']['forecast_unit_ids']),
                'bin_left_edges_ms':np.asarray(manifest['identity_recipe']['forecast_left_edges_ms']),
                'prediction_units':'expected_spikes_per_bin','panel_fingerprint':manifest['panel_fingerprint']}
        frozen=Path('/tmp/submission.npz');consumed=0;h=hashlib.sha256()
        with Path('/input/submission.npz').open('rb')as src,frozen.open('xb')as dst:
            while b:=src.read(1048576):
                consumed+=len(b);core.require(consumed<=core.MAX_PREDICTIONS,'Candidate grew beyond cap');h.update(b);dst.write(b)
        frozen.chmod(0o400);core.require(h.hexdigest()==os.environ['EXPECTED_SUBMISSION_SHA256'],'Candidate changed after host binding')
        candidate=core.load_validated_submission(frozen,public);result['submission_sha256']=h.hexdigest()
        if action=='validate':
            result.update(status='valid_prediction_contract',prediction_contract_valid=True,scientific_score_computed=False,scientific_success=None);return result,0
        fixed=core.load_validated_submission(pinned('/input/reference.npz',assets['private']['comparator']),public)
        path=pinned('/input/gold.npz',assets['private']['targets']);result['target_loader_invocations']+=1
        with np.load(path,allow_pickle=False)as z:gold={k:z[k]for k in z.files}
        core.require(gold['target_counts'].shape==(574,40,182)and np.array_equal(gold['trial_ids'],public['trial_ids'])and np.array_equal(gold['unit_ids'],public['forecast_unit_ids'])and np.array_equal(gold['bin_left_edges_ms'],public['bin_left_edges_ms'])and gold['panel_fingerprint'].item()==public['panel_fingerprint'],'Exact private/public identity join')
        score=core.evaluate(candidate,gold,fixed);point=score['candidate']['fp_bps']
        panel=assets['reference_panel']
        result.update(status='scored',prediction_contract_valid=True,scientific_score_computed=True,scientific_success=None,score=score,
                      primary_metric=point,metric_name='fp_bps',higher_is_better=True,fixed_reference_panel=panel,
                      signed_differences={k:None if point is None else point-v['fp_bps']for k,v in panel.items()},
                      scope='Condition-assisted local single-session exposed development forecasting with past-only preprocessed query bins. No biological causal, online-spike-sorting, population or native-understanding claim.')
        return result,0
    except Exception as exc:result.update(status='rejected_no_score',error=type(exc).__name__+': '+str(exc),scientific_score_computed=False);return result,2
    finally:
        u=resource.getrusage(resource.RUSAGE_SELF)
        result['resources']={'elapsed_seconds':time.monotonic()-start,'cpu_seconds_including_imports':u.ru_utime+u.ru_stime,'peak_rss_bytes':u.ru_maxrss*1024,'cgroup_peak_bytes':int(Path('/sys/fs/cgroup/memory.peak').read_text())}


if __name__=='__main__':
    value,code=main();print(json.dumps(value,allow_nan=False,separators=(',',':')));raise SystemExit(code)
