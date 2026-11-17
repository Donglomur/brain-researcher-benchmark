"""Future data-only derivative/image projection. No model fitting; never run on real payloads."""
import argparse,csv,hashlib,io as mem,math,os
from pathlib import Path
import numpy as np
import delivery_io as io
import protocol as p
import array_io
EYE=('UADC009-2104','UADC010-2104','UADC013-2104')

def rows(root):
 r=csv.DictReader(mem.StringIO(io.read(root/'assets/bound/TRIALS.csv',10000000).decode()));out=list(r)
 for x in out:
  for k in ('epoch_index','session','run','run_row','image','concept','corrected_sample'):x[k]=int(x[k])
 io.need(len(out)==88992,'Exact full experimental panel');return out

def neural_summary(data,times,names,expected):
 a=np.asarray(data,dtype=float);t=np.asarray(times,dtype=float)
 io.need(a.ndim==3 and a.shape[1:]==(271,281) and len(names)==len(set(names))==271 and set(names)==set(expected),'Actual complete271 sensor geometry')
 io.need(np.allclose(t,np.arange(-20,261)/200,rtol=0,atol=1e-9),'Exact200Hz epoch grid')
 io.need(np.isfinite(a).all() and np.all(abs(a)<=1e12),'Complete finite bounded source epochs; no trial deletion')
 order=[names.index(n) for n in expected];a=a[:,order]
 return np.asarray([np.concatenate([np.mean(a[:,:,b],axis=2) for b in p.bins(win,200)],axis=1) for win in p.WINDOWS],dtype='<f4').transpose(1,0,2).copy()

def meg(root,person,roster,expected):
 import mne
 path=root/f'derivatives/preprocessed/preprocessed_P{person[-1]}-epo.fif'
 epochs=mne.read_epochs(path,preload=False,verbose='ERROR')
 try:
  io.need(len(epochs)==27048 and epochs.metadata is not None and float(epochs.info['sfreq'])==200,'Actual full derivative identity')
  io.need(len(epochs.ch_names)==271 and all(mne.channel_type(epochs.info,i)=='mag' for i in range(271)),'Actual MEG kinds, not BIDS OTHER/analog')
  for r in roster:
   x=epochs.metadata.iloc[r['epoch_index']]
   io.need(x['trial_type']=='exp' and int(x['things_image_nr'])==r['image'] and int(x['things_category_nr'])==r['concept'] and int(x['session_nr'])==r['session'] and int(x['run_nr'])==r['run'],'Exact metadata/FIF epoch join')
  parts=[]
  for k in range(0,len(roster),16):
   batch=roster[k:k+16];parts.append(neural_summary(epochs[[r['epoch_index'] for r in batch]].get_data(),epochs.times,epochs.ch_names,expected))
  return np.concatenate(parts)
 finally:
  if hasattr(epochs,'close'):epochs.close()

def eye_file(stream,session,roster):
 """One pinned open CSV; native ordinal selection, rounded-ms values only validate clock."""
 import pandas as pd
 index={r['image']:i for i,r in enumerate(roster)};n=len(roster);full=np.zeros(n,np.int32);sums=np.zeros((n,5,4,3));count=np.zeros((n,5,4,3),np.int32);expected={(w,b):set(ids) for w,win in enumerate(p.WINDOWS) for b,ids in enumerate(p.bins(win,1200))}
 cols=['time',*EYE,'trial_type','things_image_nr','things_category_nr','session_nr','run_nr']
 for chunk in pd.read_csv(stream,usecols=cols,chunksize=50000):
  for image,g in chunk[chunk.trial_type=='exp'].groupby('things_image_nr',sort=False):
   io.need(float(image).is_integer() and int(image) in index,'Exact eye image ID');i=index[int(image)];r=roster[i]
   io.need((g.things_category_nr==r['concept']).all() and (g.session_nr==session).all() and (g.run_nr==r['run']).all() and r['session']==session,'Eye/FIF metadata join')
   start=int(full[i]);ticks=np.arange(start,start+len(g));display=g['time'].to_numpy(float);io.need(np.isfinite(display).all() and np.all(abs(display-(-100+ticks*1000/1200))<=.51) and int(ticks[-1])<1681,'Full ordered1200Hz rounded-ms clock')
   full[i]+=len(g);values=g[list(EYE)].to_numpy(float);finite=np.isfinite(values);io.need(np.all(abs(values[finite])<=1e12),'Bounded raw ocular values')
   for w in range(5):
    for b in range(4):
     mask=np.array([int(t) in expected[(w,b)] for t in ticks]);v=values[mask];valid=np.isfinite(v)
     # Every bin has24source samples. Divide before summing to bound arithmetic.
     sums[i,w,b]+=np.where(valid,v,0).sum(0)/24;count[i,w,b]+=valid.sum(0)
 io.need(np.all(full==1681),'All experimental eye epochs complete; no omitted or repeated trials')
 fraction=count/24.;mean=np.divide(sums,fraction,out=np.zeros_like(sums),where=fraction>0)
 io.need(np.isfinite(mean).all(),'Finite aggregate')
 return np.concatenate((mean.reshape(n,5,12),fraction.reshape(n,5,12)),axis=2).astype('<f4')

def visual_features(body):
 from PIL import Image
 with Image.open(mem.BytesIO(body)) as im:
  io.need(im.format in ('JPEG','PNG') and 1<=im.width<=4096 and 1<=im.height<=4096,'Bounded authentic image')
  rgb=np.asarray(im.convert('RGB').resize((64,64),Image.Resampling.BILINEAR),dtype=float)/255
 return visual_array(rgb)

def visual_array(rgb):
 rgb=np.asarray(rgb,dtype=float);io.need(rgb.shape==(64,64,3) and np.isfinite(rgb).all() and np.all((rgb>=0)&(rgb<=1)),'Finite64pxRGB image')
 gray=rgb@np.array([.2126,.7152,.0722]);features=list(rgb.mean((0,1)))+list(rgb.std((0,1)))
 features+=list(gray.reshape(8,8,8,8).mean((1,3)).ravel());features+=list(gray.reshape(4,16,4,16).std((1,3)).ravel())
 gy,gx=np.gradient(gray);mag=np.hypot(gx,gy);angles=(np.arctan2(gy,gx)+np.pi)%(2*np.pi);hist=np.histogram(angles,bins=np.linspace(0,2*np.pi,9),weights=mag)[0];features+=list(hist/max(float(hist.sum()),1e-12))+[float(mag.mean())]
 power=abs(np.fft.fft2(gray-gray.mean()))**2;freq=np.fft.fftfreq(64);radius=np.hypot(freq[:,None],freq[None,:]);total=float(power.sum());features += [float(power[(radius>j*.09)&(radius<=(j+1)*.09)].sum()/max(total,1e-12)) for j in range(8)]
 out=np.asarray(features,dtype='<f4');io.need(out.shape==(103,) and np.isfinite(out).all(),'Exactly103 fixed unlearned visual features');return out

def verify_bundle(root,assets):
 """Decoder opens split FIF by filename; caller MUST mount source bundle immutable.

 Checks full pins before opening and requires the same filesystem object/stats
 afterward. This cannot certify mount/isolation itself; no mutable-bundle claim.
 """
 states={}
 for a in assets:
  path=io.resolve(root,a['path']);io.read(path,a['bytes'],{k:a[k] for k in ('bytes','sha256')},retain=False);states[a['path']]=path.stat()
 return states

def recheck(root,states):
 for name,old in states.items():
  new=io.regular(io.resolve(root,name)).stat();io.need(all(getattr(old,k)==getattr(new,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_nlink')),'Source bundle changed during decoding')

def main():
 a=argparse.ArgumentParser();a.add_argument('--source-root',type=Path,required=True);a.add_argument('--image-root',type=Path,required=True);a.add_argument('--images',type=Path,required=True);a.add_argument('--immutable-bundle-binding',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--max-source-bytes',type=int,required=True);a.add_argument('--max-output-bytes',type=int,required=True);q=a.parse_args();io.need(not io.regular(q.output).exists(),'Fresh features root');here=Path(__file__).parent;assets=io.json_file(here/'source/PAYLOADS.json',100000)['files'];io.need(sum(x['bytes'] for x in assets)<=q.max_source_bytes and q.max_output_bytes>=2100000000,'Full source66.18GB plus future2.1GB output reservation')
 binding=io.json_file(q.immutable_bundle_binding,10000);io.exact(binding,['read_only_mount','outside_mutation_excluded','method','evidence_sha256']);io.need(binding['read_only_mount'] is True and binding['outside_mutation_excluded'] is True and type(binding['method'])is str and binding['method'],'External immutable-source guarantee required, currently unavailable');io.check_pin({'bytes':1,'sha256':binding['evidence_sha256']},1)
 roster=rows(here);images=io.json_file(q.images,8000000);io.need(images['schema']=='neural054_images_v1' and images['content_verified'] is True,'Actual image pins required');expected_images={r['image']:r['image_path'] for r in roster};io.need(len(images['images'])==22248 and {r['image'] for r in images['images']}==set(expected_images),'All22248 authentic images');out=io.fresh(q.output);manifest={'schema':'neural054_features_v1','people':{},'images':[],'source_identity':io.pin(io.canonical(assets)),'image_manifest_identity':io.pin(io.canonical(images)),'immutable_binding':io.pin(io.canonical(binding))}
 states=verify_bundle(q.source_root,assets)
 try:
  sensors=io.json_file(here/'source/SENSOR_ORDER.json',100000)['names']
  for person in p.PERSONS:
   rs=[r for r in roster if r['person']==person];n=meg(q.source_root,person,rs,sensors);eyes=np.zeros((22248,5,24),dtype='<f4');lookup={r['image']:i for i,r in enumerate(rs)}
   for session in range(1,13):
    subset=[r for r in rs if r['session']==session];name=f'derivatives/preprocessed/eyes_epoched_cleaned_P{person[-1]}_S{session}.csv';asset=next(x for x in assets if x['path']==name)
    with io.verified_stream(io.resolve(q.source_root,name),{k:asset[k] for k in ('bytes','sha256')}) as stream:e=eye_file(stream,session,subset)
    for i,r in enumerate(subset):eyes[lookup[r['image']]]=e[i]
   manifest['people'][person]={}
   for family,arr in (('neural',n),('ocular',eyes)):
    name=person+'_'+family+'.npy';pin=array_io.write(out/name,arr,600000000);manifest['people'][person][family]={'path':name,**pin,'shape':list(arr.shape)}
  vs=[]
  for r in sorted(images['images'],key=lambda r:r['image']):
   io.exact(r,['image','image_path','local_path','bytes','sha256']);io.need(r['image_path']==expected_images[r['image']],'Exact source image identity');body=io.read(io.resolve(q.image_root,r['local_path']),30000000,{k:r[k] for k in ('bytes','sha256')});vs.append(visual_features(body));manifest['images'].append(r['image'])
  arr=np.stack(vs);manifest['visual']={'path':'visual.npy',**array_io.write(out/'visual.npy',arr,10000000),'shape':list(arr.shape)}
 finally:recheck(q.source_root,states)
 io.need(sum(x.stat().st_size for x in out.iterdir())<=q.max_output_bytes,'Reserved output ceiling');io.put(out/'FEATURES.json',manifest,500000)
if __name__=='__main__':main()
