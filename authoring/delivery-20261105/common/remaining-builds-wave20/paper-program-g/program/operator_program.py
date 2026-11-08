"""Independent complete native/control and nested improvement producer."""
import argparse,json,os,sys
from pathlib import Path
sys.path.insert(0,'/runtime')
import numpy as np
from reference_math import native_fold,fit_references,predict_references
import operator_state

def array(path,shape,dtype):
    a=np.load(path,allow_pickle=False,mmap_mode='r')
    if a.shape!=tuple(shape)or a.dtype!=np.dtype(dtype):raise ValueError('exact full input shape/dtype')
    return np.asarray(a)

def run(mode,root,case,model):
    h,d=case['rows'],case['features']
    if mode=='native':
        import scipy
        if scipy.__version__!='1.15.3':raise ValueError('qualified source MAT runtime')
        from scipy.io import loadmat
        from prepare import mat_census,validate_arrays
        raw=(root/'original.mat').read_bytes()
        if len(raw)!=case['original_mat_bytes']:raise ValueError('full admitted original MAT')
        mat_census(raw,case['mat_decoded_bytes'],case['numeric_array_bytes'])
        import io
        a=loadmat(io.BytesIO(raw),variable_names=['X','y'],verify_compressed_data_integrity=True)
        x,y,_=validate_arrays(a['X'],a['y'],case['numeric_array_bytes'])
        if x.shape!=(h,d):raise ValueError('original selected HW support')
        output=np.empty((h,101),dtype=np.float64);covered=np.zeros(h,dtype=np.int64)
        for fold in case['source_folds']:
            tr=np.array(fold['train_positions0'],dtype=np.int64);te=np.array(fold['test_positions0'],dtype=np.int64)
            output[te]=native_fold(np.asarray(x[tr]),np.asarray(y[tr]),np.asarray(x[te]),case['source_session_token'],fold['fold']);covered[te]+=1
        if not np.all(covered==1):raise ValueError('every source HW row predicted once')
        return output.astype('<f8').tobytes()
    x=array(root/('Xtrain.npy'if mode=='fit'else 'Xquery.npy'),(h,d),'float64')
    if mode=='fit':
        y=array(root/'ytrain.npy',(h,),'int64');return operator_state.encode(fit_references(x,y))
    if mode=='predict':
        # State is the captured independent operator artifact, never candidate bytes.
        with open(model,'rb')as f:raw=f.read(case['model_cap_bytes']+1)
        if len(raw)>case['model_cap_bytes']:raise ValueError('sealed operator state cap')
        return predict_references(operator_state.decode(raw,d),x).astype('<f8').tobytes()
    raise ValueError('native/fit/predict mode')

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('native','fit','predict'));p.add_argument('--input',required=True);p.add_argument('--case',required=True);p.add_argument('--output',required=True);p.add_argument('--model');a=p.parse_args();case=json.loads(Path(a.case).read_text());body=run(a.mode,Path(a.input),case,a.model)
    with open(a.output,'xb')as f:f.write(body);f.flush();os.fsync(f.fileno())
if __name__=='__main__':main()
