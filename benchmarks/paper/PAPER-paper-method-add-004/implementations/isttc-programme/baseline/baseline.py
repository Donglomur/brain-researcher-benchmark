"""Unrun source-derived baseline. Execution performs scientific estimation.

This file is a future candidate program, never used by the artifact grader.
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    a.output.mkdir(exist_ok=False,parents=True)
    here=Path(__file__).resolve().parent
    sys.path.insert(0,str(here/'source/src'))
    sys.path.insert(0,str(here))
    import numpy as np
    from statsmodels.tsa.stattools import acf
    from isttc.acfunc import acf_pearsonr_trial_avg,acf_sttc_trial_concat,acf_sttc
    from isttc.tau import fit_single_exp,func_single_exp
    from isttc.spike_utils import bin_spike_train_fixed_len,bin_trials
    from read_inputs import load_panel,records
    metadata={'schema':'isttc_submission_v1','condition':'reproduction','source_commit':'e78cfd2b2ea79b7a7e707db7b79e218212497e43','notes':'Pinned current-source baseline; 50ms bins/lags,25ms STTC dt,20 lags,start_idx=1,3000ms trial padding. No R-squared filtering. Source-version reconstruction, not publication-exact claim.'}
    (a.output/'methods.json').write_text(json.dumps(metadata,indent=2)+'\n')
    with (a.output/'estimates.csv').open('x',newline='') as f:
        writer=csv.writer(f);writer.writerow(['unit_id','method','status','tau_ms'])
        for panel,methods in [('continuous',('acf','isttc')),('trials',('pearsonr','isttc_trials'))]:
            times,offsets=load_panel(a.input,panel)
            for i in range(100000):
                rows=records(times,offsets,i if panel=='continuous' else i*40,1 if panel=='continuous' else 40)
                for method in methods:
                    # Original notebooks cast continuous spike timestamps to integers.
                    try:
                        if method=='acf':
                            binned=bin_spike_train_fixed_len([int(t) for t in rows[0]],50,1000,600000,False)
                            y=acf(binned,nlags=20)
                        elif method=='isttc':
                            y=acf_sttc(np.asarray([int(t) for t in rows[0]]),20,50,25,600000,False)
                        elif method=='pearsonr':
                            _,y=acf_pearsonr_trial_avg(bin_trials(rows,1000,50),20,False)
                        else:
                            y=acf_sttc_trial_concat(rows,n_lags_=20,lag_shift_=50,sttc_dt_=25,trial_len_=1000,zero_padding_len_=3000,verbose_=False)
                        tau=float(fit_single_exp(y,start_idx_=1,exp_fun_=func_single_exp)[2])*50
                        if not math.isfinite(tau) or tau<=0:raise ValueError('No valid positive fit')
                        writer.writerow([i,method,'ok',repr(tau)])
                    except (ValueError,RuntimeError,FloatingPointError,ZeroDivisionError):
                        writer.writerow([i,method,'failed',''])
            del times,offsets


if __name__=='__main__':main()
