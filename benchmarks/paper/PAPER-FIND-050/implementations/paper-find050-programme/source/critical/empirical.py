"""Full Fig3 source preprocessing; authentic loads are separately native-qualified."""
from .core import *
from .programme import contract
class Record:
 def __init__(self,row,ctx):
  self.row=row;self.context=ctx;self.session_id=row['session_id'];self.modality=row['modality'];self.device=ctx.device;self.handle=None
 def open_full_fig3(self):
  import numpy as np
  from scipy.sparse import csr_matrix
  ctx=self.context;ctx.authority.require('authentic_full_fig3:'+self.session_id,ctx.authority.source_sha256)
  # Exact input naming is retained. No face/face2 or session-label aliases.
  path=ordinary(ctx.input_root/self.row['file']);r=ctx.plans['empirical_dynamics']['input_files'][self.session_id]
  # Live operator admission owns native decompression/allocation and input-byte
  # authentication. An ordinary-file hash alone cannot grant np.load/pickle use.
  need(r['filename']==self.row['file'],'same admitted source member')
  ctx.authority.require('native_decode_exact_member:'+r['sha256'],ctx.authority.source_sha256)
  self.handle=np.load(path,allow_pickle=True);d=self.handle
  if self.modality=='calcium':
   x=d['sp'];xpos=d['xpos'];ypos=d['ypos']
  else:
   st=d['st'];cl=d['clu'];st-=st.min();tbin=1./22
   # Literal source uint8 CSR accumulation (including overflow), rounded
   # uint32 time bins, float32 conversion and zero horizontal probe offsets.
   it=np.round(st/tbin).astype('uint32');nn=cl.max()+1;nt=int(np.round(st.max()/tbin))+1
   x=csr_matrix((np.ones(cl.size,dtype='uint8'),(cl,it)),shape=(nn,nt)).toarray().astype('float32')
   keep=x.mean(axis=1)>.01*tbin;x=x[keep];xpos=d['iprobe'][keep].astype('float32')*0;ypos=d['ypos'][keep]
  need(list(x.shape)==r['full_shape'],'complete admitted neuron/time support')
  return x,xpos,ypos
 def close(self):
  if self.handle is not None:
   handle=self.handle;self.handle=None
   # A failed close may already have acted; do not retry this native handle.
   handle.close()
def records(ctx):
 c=contract('COHORT.json');m={r['session_id']:r for r in c['sessions']}
 return [Record(m[k],ctx) for k in c['fig3_order']]
