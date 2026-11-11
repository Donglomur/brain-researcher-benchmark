"""Local consistency reader for host-staged signal; never a provenance issuer.

The trusted host admits and snapshots inputs before launching this candidate.
Standalone use only checks the supplied bytes/geometry/calibration declarations;
it cannot establish publisher origin, genuine common reference or qualification.
No host source owner, target selector or issuer authority enters this process.
"""
import hashlib,os,stat
from pathlib import Path
from io_contract import need
from scientific_contract import reference_record

def local_schema(f,h5py,row,declaration):
 keys=('eeg_digital','scale_to_microvolts','offset_microvolts','channel_labels','source_channel_index')
 need(set(f.keys())==set(keys)and set(f.attrs)=={'sample_rate_hz','duration_seconds','schema_version'},'exact staged target-free H5 schema')
 for name in keys:
  need(type(f.get(name,getlink=True))is h5py.HardLink,'internal hard staged links only')
  ds=f[name];need(type(ds)is h5py.Dataset and not ds.is_virtual and ds.id.get_create_plist().get_external_count()==0 and ds.id.get_create_plist().get_nfilters()==0 and len(ds.attrs)==0,'ordinary internal unfiltered staged data')
 attrs={name:f.attrs[name]for name in('sample_rate_hz','duration_seconds','schema_version')}
 need(all(type(v)is int or(getattr(getattr(v,'dtype',None),'kind',None)in('i','u')and getattr(v,'shape',None)==())for v in attrs.values()),'actual scalar integer staged attributes')
 rate=int(attrs['sample_rate_hz']);n=len(declaration['channel_labels'])
 need(rate==declaration['sample_rate_hz']and int(attrs['duration_seconds'])==row['duration_seconds']and int(attrs['schema_version'])==1,'selected staged rate/duration/schema')
 need(f['eeg_digital'].shape==(row['duration_seconds']*rate,n)and f['eeg_digital'].dtype.str=='<i2','full staged int16 sample geometry')
 for name in keys[1:]:need(f[name].shape==(n,),'complete staged channel metadata')
 need(f['scale_to_microvolts'].dtype.kind=='f'and f['offset_microvolts'].dtype.kind=='f'and f['source_channel_index'].dtype.kind in('i','u')and f['channel_labels'].dtype.kind=='S','staged metadata types')
 return rate

def load(row,root,reference_binding):
 declaration=reference_record(reference_binding,row)
 if row['cohort']=='Siena':need(declaration['common_reference']['claim']=='common_reference','unresolved common-reference declaration is ineligible')
 # Host admission is enforced by execution_boundary.stage. A declaration here
 # selects the computation and binds local bytes; it does not prove provenance.
 import numpy as np
 import h5py
 pin=row['signal'];path=Path(root)/pin['file'];need(path.resolve().is_relative_to(Path(root).resolve()),'contained signal path')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 with os.fdopen(fd,'rb') as stream:
  before=os.fstat(stream.fileno());need(stat.S_ISREG(before.st_mode) and before.st_size==pin['bytes'],'ordinary bound HDF5')
  def digest():
   stream.seek(0);h=hashlib.sha256()
   for b in iter(lambda:stream.read(1048576),b''):h.update(b)
   stream.seek(0);return h.hexdigest()
  need(digest()==pin['sha256'],'exact signal bytes')
  with h5py.File(stream,'r') as f:
   rate=local_schema(f,h5py,row,declaration);scale=np.asarray(f['scale_to_microvolts'],dtype=np.float64);offset=np.asarray(f['offset_microvolts'],dtype=np.float64);labels=[x.decode('ascii') for x in f['channel_labels'][:]];indices=[int(x) for x in f['source_channel_index'][:]];data=f['eeg_digital']
   need(rate==declaration['sample_rate_hz'] and labels==declaration['channel_labels'] and indices==declaration['source_channel_indices'] and scale.tolist()==declaration['calibration']['scale_to_microvolts'] and offset.tolist()==declaration['calibration']['offset_microvolts'],'actual HDF5 channel/calibration/montage matches admitted declaration')
   need(rate in (256,512) and data.shape==(row['duration_seconds']*rate,len(labels)) and scale.shape==offset.shape==(len(labels),) and np.isfinite(scale).all() and (scale>0).all() and np.isfinite(offset).all(),'exact calibrated support')
   values=np.asarray(data,dtype=np.float64)*scale+offset
  after=os.fstat(stream.fileno());need(all(getattr(before,k)==getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')) and digest()==pin['sha256'],'same verified signal snapshot')
 need(np.isfinite(values).all(),'finite physical EEG')
 # The fourth value selects the declared Siena common-reference subtraction.
 # It is not evidence that the physical reference or source origin is genuine.
 return values,rate,labels,row['cohort']=='Siena'
