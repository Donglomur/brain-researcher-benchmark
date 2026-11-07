"""Trusted continuous intermediate-reconstruction scorer. Never executes a submission."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile
import numpy as np

CAP=2000000


def need(ok,message):
    if not ok:raise ValueError(message)


def read_submission(path,spec):
    b=Path(path).read_bytes();need(0<len(b)<=CAP,'bounded submission bytes')
    with zipfile.ZipFile(io.BytesIO(b))as z:
        entries=z.infolist();expected={k+'.npy'for k in spec}
        need(len(entries)==len(expected)and {e.filename for e in entries}==expected,'exact unique declared keys')
        total=0
        for e in entries:
            need(e.compress_type==zipfile.ZIP_STORED and not e.flag_bits&1 and e.file_size<=CAP and e.compress_size==e.file_size,'stored bounded plain member')
            total+=e.file_size;need(total<=CAP,'bounded total members')
            with z.open(e)as f:
                h=f.read(8);need(h[:6]==b'\x93NUMPY'and h[6:]in(b'\x01\x00',b'\x02\x00'),'NPY magic/version')
                n=2 if h[6:]==b'\x01\x00'else 4;raw=f.read(n);need(len(raw)==n,'header size prefix');size=int.from_bytes(raw,'little');need(0<size<=4096,'bounded header')
                hdr=f.read(size);need(len(hdr)==size,'complete header');d=ast.literal_eval(hdr.decode('latin1'))
                need(type(d)is dict and set(d)=={'descr','shape','fortran_order'}and d['fortran_order']is False,'plain C-order header')
                key=e.filename[:-4];target=spec[key];need(type(d['shape'])is tuple and list(d['shape'])==target['shape'],'exact shape')
                dtype=np.dtype(d['descr']);need(not dtype.hasobject and dtype.fields is None,'nonobject primitive')
                if target['kind']=='identity':need(dtype.kind in 'Ui'and dtype.str==target['dtype'],'exact identity dtype')
                else:need(dtype.kind=='f'and dtype.itemsize in (4,8),'real float32/64 numeric values')
                count=1
                for x in d['shape']:need(type(x)is int and x>=0,'integer dimensions');count*=x
                need(8+n+size+count*dtype.itemsize==e.file_size,'exact declared payload length')
        with np.load(io.BytesIO(b),allow_pickle=False,max_header_size=4096)as f:
            values={k:f[k]for k in spec}
    for key,a in values.items():
        if spec[key]['kind']=='numeric':need(np.isfinite(a).all()and np.all(np.abs(a)<1e100),'finite numerically bounded values')
        else:need(a.tolist()==spec[key]['values'],'exact ordered case/unit identity')
    return values,hashlib.sha256(b).hexdigest()


def score_validated(candidate,digest,expected_path,spec):
    # Gold opens only after all candidate fields and identities validate.
    with np.load(expected_path,allow_pickle=False)as f:gold={k:f[k]for k in spec}
    metrics={};field_errors={}
    for k in spec:
        if spec[k]['kind']=='numeric':
            error=candidate[k].astype(np.float64)-gold[k].astype(np.float64)
            field_errors[k]={'rmse':float(np.sqrt(np.mean(error*error))),'mae':float(np.mean(np.abs(error))),'max_abs_error':float(np.max(np.abs(error))),'n_values':int(error.size)}
    # Equal experiment weighting measures reconstruction, not population inference.
    for panel,key,groupkey in [('fig2','fig2__delta','fig2__experiment_id'),('multiopto_high_power','multiopto_hi__delta','multiopto__experiment_id'),('multiopto_low_power','multiopto_lo__delta','multiopto__experiment_id')]:
        rows=[]
        for gid in np.unique(gold[groupkey]):
            mask=gold[groupkey]==gid;e=candidate[key][mask].astype(float)-gold[key][mask].astype(float)
            rows.append({'experiment_id':str(gid),'rmse':float(np.sqrt(np.mean(e*e))),'n_cells':int(mask.sum())})
        metrics[panel+'_equal_experiment_delta_rmse']={'value':float(np.mean([r['rmse']for r in rows])),'direction':'lower','per_experiment':rows}
    # Fig3I's direct high-minus-low comparison is distinct from either power alone.
    e=(candidate['multiopto_hi__delta']-candidate['multiopto_lo__delta'])-(gold['multiopto_hi__delta']-gold['multiopto_lo__delta'])
    grouped=[float(np.sqrt(np.mean(e[gold['multiopto__experiment_id']==g]**2)))for g in np.unique(gold['multiopto__experiment_id'])]
    metrics['multiopto_high_minus_low_delta_equal_experiment_rmse']={'value':float(np.mean(grouped)),'direction':'lower','unit':'Fig3I paired-minus-alone power contrast reconstruction'}
    metrics['multivis_cell_condition_delta_rmse']={'value':field_errors['multivis__delta']['rmse'],'direction':'lower','unit':'cell×condition reconstruction; animal mapping unresolved'}
    metrics['fig4_normalized_integral_rmse']={'value':field_errors['fig4__normalized_integral']['rmse'],'direction':'lower','unit':'deterministic curve reconstruction under selected LOESS2.1.2'}
    return {'status':'scored','submission_valid':True,'submission_sha256':digest,'primary_metric':'fig2_equal_experiment_delta_rmse','metrics':metrics,'all_numeric_field_errors':field_errors,'private_numeric_reference_loads':1,'scientific_success':None,'reward_floor':None,'interpretation':'Continuous numerical reconstruction diagnostics; no binary scientific pass, no overall capability average, no full-paper or improvement qualification.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--submission',required=True);p.add_argument('--expected',required=True);p.add_argument('--spec',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    spec=json.loads(Path(a.spec).read_text())['fields']
    try:candidate,digest=read_submission(a.submission,spec)
    except Exception as e:r={'status':'invalid_submission','submission_valid':False,'reason':str(e),'metrics':None,'private_numeric_reference_loads':0,'scientific_success':None}
    else:r=score_validated(candidate,digest,a.expected,spec)
    Path(a.output).write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':r['status'],'submission_valid':r['submission_valid']}),flush=True)
    return 0 if r['submission_valid']else 2


if __name__=='__main__':raise SystemExit(main())
