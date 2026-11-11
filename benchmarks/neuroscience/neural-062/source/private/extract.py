"""Future bounded native-clock projection. No actual neural or behavior values decoded yet."""
from pathlib import Path
import math
import delivery_io as io
import cohort_binding
import protocol as p
import nwb_source as src

def clock(values):
 import numpy as np
 io.need(values.ndim==1 and np.isfinite(values).all() and np.all(np.diff(values)>0),'Strict common-seconds clock')
def summaries(data,ts,cols,onset,edges):
 import numpy as np
 out=[]
 for low,high in zip(edges[:-1],edges[1:]):
  a=onset+low;b=onset+high;i=int(np.searchsorted(ts,a,side='left'));j=int(np.searchsorted(ts,b,side='left'))
  if j-i<2 or j-i>100 or np.max(np.diff(np.r_[a,ts[i:j],b]))>.15:return [None]*14
  # ROI selection is fixed by published QC; no response-based cell selection.
  block=np.asarray(data[i:j,:],dtype=float)[:,cols]
  if not np.isfinite(block).all() or np.max(np.abs(block))>1e20:return [None]*14
  v=block.mean(axis=0);out += [float(v.mean()),float(v.std()),*map(float,np.quantile(v,[.1,.25,.5,.75,.9],method='linear'))]
 return out

def behavior_mean(values,ts,onset,lo,hi):
 import numpy as np
 a=onset+lo;b=onset+hi;i=int(np.searchsorted(ts,a));j=int(np.searchsorted(ts,b));v=values[i:j]
 if not len(v):return None,0.0
 finite=np.isfinite(v);coverage=float(finite.mean());continuous=len(v)>=2 and np.max(np.diff(np.r_[a,ts[i:j],b]))<=.1
 return (float(v[finite].mean()) if continuous and coverage>=.8 else None),coverage

def behavior(f):
 import numpy as np
 io.need(src.internal(f,'processing/running/speed/data').attrs.get('unit') in('cm/s',b'cm/s','cm/second',b'cm/second'),'Native running cm/s');run=src.vector(f,'processing/running/speed/data',kind='f',cap=2000000);rt=src.vector(f,'processing/running/speed/timestamps',len(run),'f',2000000);clock(rt)
 for name in('processing/running/speed/timestamps','acquisition/EyeTracking/eye_tracking/timestamps'):
  ds=src.internal(f,name);io.need(ds.attrs.get('unit') in('seconds',b'seconds'),'Native behavior seconds')
 pupil=src.vector(f,'acquisition/EyeTracking/pupil_tracking/area',kind='f',cap=2000000);et=src.vector(f,'acquisition/EyeTracking/eye_tracking/timestamps',len(pupil),'f',2000000);blink=src.vector(f,'acquisition/EyeTracking/likely_blink/data',len(pupil),'b',2000000);clock(et)
 # Use stored cleaned area/blink arrays; do not rerun a whole-held-session SDK z-score.
 pupil=np.asarray(pupil,dtype=float).copy();pupil[blink|(~np.isfinite(pupil))|(pupil<0)]=np.nan
 return run,rt,pupil,et

def project(path,record,byte_binding):
 import numpy as np
 io.need(type(byte_binding)is int and 0<byte_binding<=4_000_000_000,'Exact bounded future byte binding; larger source needs explicit resource revision')
 binding={'bytes':byte_binding,'blake2b_512':record['asset']['file_hash']};roi={'rois':[{'cell_roi_id':a,'cell_specimen_id':b} for a,b in record['published_rois']]};output=[];counts={'all_source_image_rows':0,'omitted':0,'unknown_context':0,'not_change_detection':0,'near_next_presentation':0,'invalid_current_clock':0};p.static(record)
 with src.opened_source(io.regular(path),binding) as f:
  # Source identity is additionally checked before any future row projection.
  subject=src.internal(f,'general/subject/subject_id')[()];subject=subject.decode() if isinstance(subject,bytes) else str(subject);io.need(subject==record['mouse_id'],'Exact NWB mouse')
  ds,ts,cols=src.neural(f,roi);run,rt,pupil,et=behavior(f)
  for table in src.presentations(f):
   n=len(table['ids']);base='intervals/'+table['group']+'/'
   blocks=src.internal(f,base+'stimulus_block_name').asstr()[:].tolist();changes=src.vector(f,base+'is_change',n,'bif',200000);ends=src.vector(f,base+'stop_time',n,'f',200000);active=src.vector(f,base+'active',n,'b',200000)
   io.need(len(blocks)==n and len(set(map(int,table['ids'])))==n,'Unique native presentation IDs');starts=table['starts'];clock(starts);io.need(np.all(np.isin(table['omitted'],[0,1])),'Omitted0/1')
   for i,(sid,t,end,name,omitted,block,change) in enumerate(zip(table['ids'],starts,ends,table['image_names'],table['omitted'],blocks,changes)):
    counts['all_source_image_rows']+=1
    if 'change_detection' not in block:counts['not_change_detection']+=1;continue
    io.need(bool(active[i])==(record['passive']=='False'),'Source active/passive agrees with cohort')
    if omitted:counts['omitted']+=1;continue
    io.need(name!='omitted' and 1<=len(name)<=512,'Named shown image')
    if not np.isfinite(change) or change not in(0,1):counts['unknown_context']+=1;continue
    if not np.isfinite(end) or not .15<=end-t<=.35:counts['invalid_current_clock']+=1;continue
    if i+1<n and starts[i+1]<t+.55:counts['near_next_presentation']+=1;continue
    pre=summaries(ds,ts,cols,float(t),p.WINDOWS['PRE']);post=summaries(ds,ts,cols,float(t),p.WINDOWS['POST'])
    r=[behavior_mean(run,rt,float(t),a,b) for a,b in ((-.5,-.25),(-.25,0))];e=[behavior_mean(pupil,et,float(t),a,b) for a,b in ((-.5,-.25),(-.25,0))]
    cov=[r[0][0],r[1][0],e[0][0],e[1][0],r[0][1],r[1][1],e[0][1],e[1][1]];speed=(r[0][0]+r[1][0])/2 if all(x[0] is not None for x in r) else None
    output.append({'presentation_id':int(sid),'group':table['group'],'image_name':name,'context':'CHANGE' if change else 'REPEAT','running_bin':p.running_bin(speed),'covariates':cov,'PRE':pre,'POST':post})
 return {'format':'neural062_projection_v1','experiment':record['ophys_experiment_id'],'mouse':record['mouse_id'],'source':binding,'record_sha256':io.pin(io.canonical(record))['sha256'],'rows':output,'census':counts}
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--source',required=True);a.add_argument('--experiment',required=True);a.add_argument('--bytes',required=True,type=int);a.add_argument('--output',required=True);q=a.parse_args();root=Path(__file__).resolve().parent;record=next(r for r in cohort_binding.load(root)['rows'] if r['ophys_experiment_id']==q.experiment)
 out=project(q.source,record,q.bytes);out['method']={n:io.read(root/n,200000,retain=False) for n in('extract.py','nwb_source.py','protocol.py','delivery_io.py','cohort_binding.py')};io.put(q.output,out,16000000)
