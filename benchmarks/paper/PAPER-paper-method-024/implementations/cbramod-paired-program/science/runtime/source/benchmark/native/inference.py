"""Target-free complete ordered prediction export through the real official head."""
import ast,hashlib,math,os,time
from pathlib import Path
from .policy import DATASETS,need

def inspect_input(path,spec):
 # Header admission is before NumPy; never pickle or an object dtype.
 with open(path,'rb')as f:
  prefix=f.read(8);need(prefix[:6]==b'\x93NUMPY'and tuple(prefix[6:])in((1,0),(2,0),(3,0)),'numeric NPY format')
  width=2 if prefix[6]==1 else 4;raw=f.read(width);need(len(raw)==width,'complete NPY header length')
  n=int.from_bytes(raw,'little');need(1<=n<=4096,'bounded NPY header');raw=f.read(n)
  need(len(raw)==n and raw.endswith(b'\n'),'complete header')
  tree=ast.parse(raw.decode('ascii').strip(),mode='eval').body
  need(isinstance(tree,ast.Dict)and len(tree.keys)==3 and all(isinstance(k,ast.Constant)and type(k.value)is str for k in tree.keys),'literal header')
  need({k.value for k in tree.keys}=={'descr','fortran_order','shape'},'exact nonduplicate NPY keys')
  h=ast.literal_eval(tree)
  need(type(h['shape'])is tuple and all(type(x)is int for x in h['shape'])and list(h['shape'])==spec['shape'],'input shape')
  need(h['descr']==spec['dtype']and h['fortran_order']is False,'numeric float32 C-order source-normalized input')
  need(f.tell()+math.prod(spec['shape'])*4==spec['bytes']==Path(path).stat().st_size,'complete physical NPY extent')

def export(components,model,plan,input_path,output_path,deadline):
 import numpy as np
 torch=components['torch'];q=plan['query'];d=DATASETS[plan['dataset_id']];inspect_input(input_path,q)
 x=np.load(input_path,mmap_mode='r',allow_pickle=False,max_header_size=4096)
 y=None
 try:
  y=np.lib.format.open_memmap(output_path,mode='w+',dtype='<f4',shape=(len(q['row_ids']),d[2]),fortran_order=False)
  row=0;batch=plan['params']['batch_size'];model.eval()
  with torch.no_grad():
   for begin in range(0,len(x),batch):
    need(time.monotonic()<deadline,'whole execution deadline')
    a=np.array(x[begin:begin+batch],dtype=np.float32,copy=True,order='C')
    need(np.isfinite(a).all(),'nonfinite input rejects entire run')
    out=model(torch.from_numpy(a).cuda())
    if d[1]=='multiclass':v=torch.softmax(out,dim=-1).reshape(-1,d[2])
    elif d[1]=='binary':
     prob=torch.sigmoid(out).reshape(-1);v=torch.stack((1-prob,prob),dim=1)
    else:v=out.reshape(-1,1)
    values=v.detach().cpu().numpy();need(np.isfinite(values).all(),'complete finite native outputs')
    n=len(values);need(row+n<=len(y),'no extra prediction rows');y[row:row+n]=values;row+=n
  need(row==len(y),'complete prediction support');y.flush()
 finally:
  x._mmap.close()
  if y is not None:y._mmap.close()
 size=Path(output_path).stat().st_size;need(size<=plan['caps']['maximum_predictions_bytes'],'full prediction output cap')
 h=hashlib.sha256()
 with open(output_path,'rb')as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return {'path':Path(output_path).name,'bytes':size,'sha256':h.hexdigest(),
  'shape':[len(q['row_ids']),d[2]],'dtype':'<f4','query_sha256':q['query_sha256'],
  'row_identity_sha256':__import__('hashlib').sha256(__import__('json').dumps(q['row_ids'],separators=(',',':')).encode()).hexdigest()}
