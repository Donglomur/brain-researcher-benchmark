"""Public fixed analytic clock prior. No neural method or private evaluator."""
import ast
import hashlib
import json
from pathlib import Path
import struct


def read(d):
    b=(Path('/input')/d['path']).read_bytes()
    if len(b)!=d['bytes'] or hashlib.sha256(b).hexdigest()!=d['sha256']:raise ValueError('Training input changed')
    if b[:8]!=b'\x93NUMPY\x01\x00':raise ValueError('Primitive NPY1')
    n=struct.unpack('<H',b[8:10])[0];h=ast.literal_eval(b[10:10+n].decode('latin1'))
    if h['descr']!='<i8' or h['shape'][1:]!=(1,) or len(b)!=10+n+8*h['shape'][0]:raise ValueError('Complete binary training vector')
    return list(struct.unpack('<'+'q'*h['shape'][0],b[10+n:]))


def main():
    m=json.loads(Path('/input/TRAINING.json').read_text());labels=read(m['arrays']['labels'])
    if not labels or any(x not in (0,1) for x in labels):raise ValueError('All admitted training labels')
    # Every original training trial supplies all five windows; class counts
    # are equal at each window by construction, so global and window priors coincide.
    margin=(labels.count(1)-labels.count(0))/len(labels)
    if margin==0:margin=-1e-15 # fixed class0 exact tie convention, no probability claim
    out=Path('/output');payload=struct.pack('<d',margin)
    header=repr({'descr':'<f8','fortran_order':False,'shape':()})
    header=(header+' '*((16-(10+len(header)+1)%16)%16)+'\n').encode('latin1')
    b=b'\x93NUMPY\x01\x00'+struct.pack('<H',len(header))+header+payload
    (out/'prior.npy').write_bytes(b)
    model={'schema':'h_model_v1','family':'clock_prior','graph':{'schema':'h_pure_graph_v1','nodes':[{'id':'p','op':'constant','name':'prior'}],'output':'p'},'arrays':{'prior':{'path':'prior.npy','bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'shape':[],'dtype':'<f8'}},'input_shapes':{'clock':{'shape':[5],'dtype':'float64'}},'training_provenance':{'kind':'fixed_clock_prior','global_class_counts':[labels.count(0),labels.count(1)],'all_five_windows_per_training_trial':True,'tie_class':0}}
    (out/'MODEL.json').write_text(json.dumps(model,sort_keys=True,separators=(',',':'),allow_nan=False))


if __name__=='__main__':main()
