"""Independent operator native and forecast program; never candidate mounted."""
import argparse,json,struct,sys
from pathlib import Path
sys.path.insert(0,'/runtime')

def read_exact(f,n):
    b=bytearray()
    while len(b)<n:
        q=f.read(n-len(b))
        if not q:raise ValueError('partial binary frame')
        b.extend(q)
    return bytes(b)

def main():
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['native','fit','stream']);p.add_argument('--input',required=True);p.add_argument('--case',required=True);p.add_argument('--output');p.add_argument('--model');a=p.parse_args();case=json.loads(Path(a.case).read_text())
    if a.kind=='native':
        import native_entry
        sys.argv=[sys.argv[0],'--input',str(Path(a.input)/case['session']['file']),'--case',a.case,'--output',a.output];return native_entry.main()
    import numpy as np
    from reference_math import fit_all,predict_all,state_to_npz_members,state_from_npz_members
    if a.kind=='fit':
        z=np.load(Path(a.input)/'development.npy',allow_pickle=False);need=z.dtype==np.dtype('float64') and list(z.shape)==[case['partition']['neurons'],case['partition']['development_end']]
        if not need:raise ValueError('complete exact prefix')
        state=fit_all(z,case['session']['modality']);members=state_to_npz_members(state)
        with open(a.output,'xb') as f:np.savez(f,**members)
        return
    with np.load(a.model,allow_pickle=False) as f:state=state_from_npz_members({k:f[k] for k in f.files})
    from stream_io import HEADER,MAGIC
    n=case['partition']['neurons'];source=sys.stdin.buffer;out=sys.stdout.buffer
    for index in range(case['partition']['query_start'],case['partition']['query_stop']):
        header=read_exact(source,HEADER.size);magic,j,width,token=HEADER.unpack(header)
        if magic!=MAGIC or j!=index or width!=n:raise ValueError('exact current chronological request')
        z=np.frombuffer(read_exact(source,8*n),dtype='<f8');pred=predict_all(state,z);out.write(header)
        for key in ('dmd','persistence','diagonal_ar'):out.write(np.asarray(pred[key],dtype='<f8').tobytes())
        out.flush()
    if source.read(1):raise ValueError('no extra query after complete panel')
if __name__=='__main__':main()
