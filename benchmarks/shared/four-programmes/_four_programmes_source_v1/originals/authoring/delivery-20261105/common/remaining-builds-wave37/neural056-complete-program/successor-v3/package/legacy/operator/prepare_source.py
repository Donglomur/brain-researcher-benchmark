"""Future isolated operator conversion of all original EEG repeats; no fits/scores.
Pinned NumPy object dictionaries require the explicit trusted-source reader.
The reader is not a hostile-pickle sandbox; external offline memory isolation
and a separately approved large-data allowance remain required.
"""
import argparse,sys,json,io,zipfile
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'public'))
from common import PEOPLE,canonical,need
from array_io import capture,identity,fresh_output
from source_io import read_source_dictionary
from source_bindings import check_source_asset

def summarize(v,partition):
 need(type(v)is dict and set(v)=={'preprocessed_eeg_data','ch_names','times'},'Exact source fields')
 n,repeats=(16540,4) if partition=='train' else (200,80);x=v['preprocessed_eeg_data'];need(type(x)is np.ndarray and x.shape==(n,repeats,17,100) and x.dtype.str=='<f8','Full original17channel float64 schema')
 names=v['ch_names'].tolist() if isinstance(v['ch_names'],np.ndarray) else v['ch_names'];t=np.asarray(v['times']);need(type(names)is list and len(names)==len(set(names))==17 and all(type(s)is str and s for s in names),'17channel labels');need(t.shape==(100,) and t.dtype.kind=='f' and np.isfinite(t).all() and np.all(np.diff(t)>0),'Full observed times')
 mean=np.empty((n,17,100));odd=np.empty_like(mean) if partition=='test' else None;even=np.empty_like(mean) if partition=='test' else None
 for start in range(0,n,32):
  block=x[start:start+32];need(np.isfinite(block).all(),'All source repeats finite')
  with np.errstate(over='raise',invalid='raise'):mean[start:start+32]=block.mean(axis=1,dtype=np.float64)
  if partition=='test':
   odd[start:start+32]=block[:,0::2].mean(axis=1,dtype=np.float64);even[start:start+32]=block[:,1::2].mean(axis=1,dtype=np.float64)
 arrays={'mean':mean} if partition=='train' else {'mean':mean,'half_odd':odd,'half_even':even}
 need(all(np.isfinite(a).all() for a in arrays.values()),'Representable means')
 return arrays,{'channel_names':names,'times_seconds':t.tolist(),'units':'released_noise_normalized_EEG_not_microvolts'}

def stage(archive,person,output,acquisition):
 need(person in PEOPLE,'All-source personID');fresh_output(output);m=json.loads(Path(acquisition).read_text());row=next(r for r in m['assets'] if r['asset_id']==person);check_source_asset(row,person);b=capture(archive,row['bytes']);need(identity(b)=={'bytes':row['bytes'],'sha256':row['sha256']},'Full original provider pin before decode');out=Path(output);out.mkdir();records={};coords=None
 with zipfile.ZipFile(io.BytesIO(b)) as z:
  names=z.namelist();need(len(names)==len(set(names)),'No duplicateZIPmembers')
  for part,basename,cap in [('train','preprocessed_eeg_training.npy',900_000_000),('test','preprocessed_eeg_test.npy',218_000_000)]:
   matches=[x for x in z.infolist() if Path(x.filename).name==basename and not x.is_dir()];need(len(matches)==1,'Exact one original field');f=matches[0];need(0<f.file_size<=cap and not f.flag_bits&1,'Bounded source extent')
   with z.open(f) as s:v=read_source_dictionary(s,maximum_bytes=cap)
   a,c=summarize(v,part);del v
   if coords is not None:need(c==coords,'Equaltrain/testcoordinates')
   coords=c;p=out/(part+'.npz');np.savez_compressed(p,**a);records[part]=identity(p.read_bytes());del a
 (out/'STAGED.json').write_bytes(canonical({'schema':'neural056_staged_person_v1','person':person,'archive':{'bytes':row['bytes'],'sha256':row['sha256']},'coordinates':coords,'arrays':records,'repeats':{'train':4,'test':80},'scientific_fit_or_score':False}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--archive',required=True);p.add_argument('--person',required=True);p.add_argument('--output',required=True);p.add_argument('--acquisition',required=True);a=p.parse_args();stage(a.archive,a.person,a.output,a.acquisition)
