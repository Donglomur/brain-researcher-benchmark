"""Future complete original-EDF to prepared-H5 correspondence, not an issuer.

This source does no work on import. All original raw observations are required
before the first projection read. No feature, model, interpolation or scoring
operation is performed. Genuine origin/reference/clock adjudication is separate.
"""
import hashlib,os,stat
from io import UnsupportedOperation
from pathlib import Path
import io_contract as io

KEYS=('eeg_digital','scale_to_microvolts','offset_microvolts','channel_labels','source_channel_index')
def identity(value):return tuple(getattr(value,k)for k in('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))

class ProjectionFileOwner:
 """Original reopen retained before effects; each attempted read is budgeted."""
 def __init__(self,source_owner,asset_id):
  self.source_owner=source_owner;self.asset_owner=source_owner.asset_owners[asset_id]
  self.asset=self.asset_owner.asset;self.path=self.asset_owner.path
  self.fd=None;self.stream=None;self.before=None;self.after=None
  self.first_error=None;self.secondary_errors=[];self.close_completed=False;self.started=False
  self.logical_bytes_returned=0;self.read_allowance_charged=0
 def retain(self,error):
  if self.first_error is None:self.first_error=error
  else:self.secondary_errors.append(error)
 def open(self):
  io.need(not self.started,'one original projection reopen');self.started=True
  try:
   self.asset_owner.require_original();self.source_owner.budget.check()
   io.need(not any(p.is_symlink()for p in(self.path,*self.path.parents)),'no projection input symlink ancestry')
   self.fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
   self.before=os.fstat(self.fd)
   io.need(stat.S_ISREG(self.before.st_mode)and self.before.st_nlink==1 and identity(self.before)==self.asset_owner.observation['before_identity'],'same originally observed projection file')
   self.stream=os.fdopen(self.fd,'rb',buffering=0);self.fd=None
  except BaseException as error:self.retain(error);raise
  return self
 def read(self,n=-1):
  try:
   io.need(self.stream is not None and not self.close_completed,'original open projection stream')
   io.need(type(n)is int and n>=0 and n<=self.source_owner.limits['projection_chunk_bytes'],'explicit bounded projection read')
   self.source_owner.budget.charge_projection(n);self.read_allowance_charged+=n
   value=self.stream.read(n);io.need(type(value)is bytes and len(value)<=n,'bounded byte return')
   self.logical_bytes_returned+=len(value);self.source_owner.budget.check();return value
  except BaseException as error:self.retain(error);raise
 def readinto(self,buffer):
  view=memoryview(buffer).cast('B');value=self.read(len(view));view[:len(value)]=value;return len(value)
 def seek(self,offset,whence=0):
  try:
   self.source_owner.budget.check();io.need(type(offset)is int and whence in(0,1,2),'bounded file-position request')
   position=self.stream.seek(offset,whence)
   io.need(0<=position<=self.asset['bytes'],'projection position within original extent');return position
  except BaseException as error:self.retain(error);raise
 def tell(self):return self.stream.tell()
 def readable(self):return True
 def writable(self):return False
 def seekable(self):return True
 def flush(self):self.source_owner.budget.check()
 def write(self,value):raise UnsupportedOperation('original projection inputs are read-only')
 def truncate(self,size=None):raise UnsupportedOperation('original projection inputs are read-only')
 @property
 def closed(self):return self.close_completed
 def verify_digest(self):
  self.seek(0);h=hashlib.sha256();remaining=self.asset['bytes']
  while remaining:
   value=self.read(min(remaining,self.source_owner.limits['chunk_bytes'],self.source_owner.limits['projection_chunk_bytes']))
   io.need(value,'complete projection verification extent');remaining-=len(value);h.update(value)
  io.need(not self.read(1)and h.hexdigest()==self.asset['sha256'],'same complete selected projection bytes')
  self.after=os.fstat(self.stream.fileno())
  io.need(identity(self.before)==identity(self.after)==self.asset_owner.observation['after_identity'],'original projection file identity remains unchanged')
 def close(self):
  if self.close_completed:return
  try:
   if self.stream is not None:
    self.after=os.fstat(self.stream.fileno())
    io.need(identity(self.before)==identity(self.after),'projection file unchanged before close')
  except BaseException as error:self.retain(error)
  try:
   if self.stream is not None:self.stream.close()
   elif self.fd is not None:os.close(self.fd)
   self.close_completed=True
  except BaseException as error:self.retain(error)

class RecordProjectionOwner:
 def __init__(self,source_owner,row):
  self.source_owner=source_owner;self.row=row;self.raw=ProjectionFileOwner(source_owner,row['original_asset'])
  self.prepared=ProjectionFileOwner(source_owner,row['prepared_asset']);self.h5=None
  self.first_error=None;self.secondary_errors=[];self.complete=False;self.checked_samples=0;self.started=False
  self.h5_open_attempted=False;self.h5_open_returned=False;self.h5_close_completed=False;self.prepared_close_deferred=False
 def retain(self,error):
  if self.first_error is None:self.first_error=error
  else:self.secondary_errors.append(error)
 def run(self):
  io.need(not self.started,'one original record projection check');self.started=True
  header=self.source_owner.validation['headers'][self.row['recording_id']]
  declaration=next(r for r in self.source_owner.selection['reference']['records']if r['recording_id']==self.row['recording_id'])
  try:
   self.source_owner.require_raw_observed()
   self.raw.open();self.prepared.open();self.raw.verify_digest();self.prepared.verify_digest()
   # This future physical validation import is never executed by authoring
   # controls. HDF5/native runtime must receive its separate qualification.
   import h5py
   self.prepared.seek(0);self.h5_open_attempted=True
   self.h5=h5py.File(self.prepared,'r',driver='fileobj');self.h5_open_returned=True
   f=self.h5;io.need(set(f.keys())==set(KEYS)and set(f.attrs)=={'sample_rate_hz','duration_seconds','schema_version'},'exact target-free prepared H5 schema')
   for name in KEYS:
    io.need(type(f.get(name,getlink=True))is h5py.HardLink,'no external or soft H5 input links')
    ds=f[name];io.need(type(ds)is h5py.Dataset and not ds.is_virtual and ds.id.get_create_plist().get_external_count()==0 and ds.id.get_create_plist().get_nfilters()==0 and len(ds.attrs)==0,'ordinary internal unfiltered data only')
   rate=header['sample_rate_hz'];duration=header['duration_seconds'];channels=header['selected_channels'];n=len(channels)
   attrs={name:f.attrs[name]for name in('sample_rate_hz','duration_seconds','schema_version')}
   io.need(all(type(value)is int or(getattr(getattr(value,'dtype',None),'kind',None)in('i','u')and getattr(value,'shape',None)==())for value in attrs.values()),'actual scalar integer prepared attributes, not bool/float/array aliases')
   io.need(int(attrs['sample_rate_hz'])==rate and int(attrs['duration_seconds'])==duration and int(attrs['schema_version'])==1,'exact prepared extent/rate/schema')
   data=f['eeg_digital'];io.need(data.shape==(duration*rate,n)and data.dtype.str=='<i2','full little-endian int16 prepared support')
   for name in KEYS[1:]:io.need(f[name].shape==(n,),'complete prepared channel metadata')
   io.need(f['scale_to_microvolts'].dtype.kind=='f'and f['offset_microvolts'].dtype.kind=='f'and f['source_channel_index'].dtype.kind in('i','u')and f['channel_labels'].dtype.kind=='S','original prepared metadata types')
   labels=[x.decode('ascii')for x in f['channel_labels'][:].tolist()]
   indices=f['source_channel_index'][:].tolist();scale=f['scale_to_microvolts'][:].tolist();offset=f['offset_microvolts'][:].tolist()
   io.need(labels==declaration['channel_labels']==[c['label']for c in channels]and indices==declaration['source_channel_indices']==[c['source_index']for c in channels],'prepared labels/indices match actual original header and case declaration')
   io.need(scale==declaration['calibration']['scale_to_microvolts']==[c['scale_to_microvolts']for c in channels]and offset==declaration['calibration']['offset_microvolts']==[c['offset_microvolts']for c in channels],'exact original affine calibration, no declared-only proof')
   counts=header['samples_per_source_record'];offsets=[];total=0
   for count in counts:offsets.append(total);total+=2*count
   per=int(header['record_seconds']*rate);cap=self.source_owner.limits['projection_chunk_bytes']
   io.need(total<=cap and per*n*2<=cap and per*header['records']==duration*rate,'complete original block and projected block fit selected capacity')
   self.raw.seek(header['header_bytes'])
   for i in range(header['records']):
    self.source_owner.budget.check();block=self.raw.read(total);io.need(len(block)==total,'whole original EDF block')
    expected=bytearray(per*n*2)
    for j,c in enumerate(channels):
     index=c['source_index'];io.need(counts[index]==per,'native selected original channel sample extent')
     channel=block[offsets[index]:offsets[index]+2*per]
     expected[2*j::2*n]=channel[0::2];expected[2*j+1::2*n]=channel[1::2]
    actual=data[i*per:(i+1)*per,:]
    io.need(actual.shape==(per,n)and actual.dtype.str=='<i2'and actual.tobytes(order='C')==bytes(expected),'every original selected int16 sample exactly equals prepared projection')
    self.checked_samples+=per*n
   io.need(not self.raw.read(1)and self.checked_samples==duration*rate*n,'full original observed support without trailing data')
  except BaseException as error:
   # HDF5 can wrap a Python file callback error. Retain the original callback
   # failure as primary when it is still owned, then the wrapper observation.
   for owner in(self.raw,self.prepared):
    if owner.first_error is not None and owner.first_error is not self.first_error:self.retain(owner.first_error)
   if error is not self.first_error:self.retain(error)
  finally:
   if self.h5 is not None:
    try:self.h5.close();self.h5_close_completed=True
    except BaseException as error:self.retain(error)
   # Only a successful sample pass earns final same-file digest rereads. Failure
   # closes safely closable streams and preserves cleanup errors/deferred debt.
   if self.first_error is None:
    for owner in(self.raw,self.prepared):
     try:owner.verify_digest()
     except BaseException as error:self.retain(error)
   # A failed HDF5 close leaves the wrapped file unsafe to close underneath it.
   # Retain both handles on this original owner as unresolved cleanup debt.
   self.prepared_close_deferred=self.h5_open_attempted and not self.h5_close_completed
   for owner in((self.raw,)if self.prepared_close_deferred else(self.prepared,self.raw)):
    owner.close()
    if owner.first_error is not None and owner.first_error is not self.first_error:self.retain(owner.first_error)
    self.secondary_errors.extend(owner.secondary_errors)
  if self.first_error is not None:raise self.first_error
  io.need(self.raw.close_completed and self.prepared.close_completed,'both original projection streams closed before completion')
  self.complete=True;return self

class ProjectionValidationOwner:
 def __init__(self,source_owner):
  from source_validation import SourceValidationOwner
  io.need(type(source_owner)is SourceValidationOwner,'same original source owner for direct projection')
  self.source_owner=source_owner;self.records={};self.first_error=None;self.secondary_errors=[];self.complete=False;self.started=False
 def retain(self,error):
  if self.first_error is None:self.first_error=error
  else:self.secondary_errors.append(error)
 def run(self):
  io.need(not self.started,'one original complete projection pass');self.started=True
  try:
   self.source_owner.require_raw_observed()
   for row in self.source_owner.selection['records']:
    self.source_owner.budget.check();rid=row['recording_id'];io.need(rid not in self.records,'one original record projection owner')
    owner=RecordProjectionOwner(self.source_owner,row);self.records[rid]=owner
    io.need(owner.run()is owner and owner.complete,'original completed record projection')
   io.need(len(self.records)==727,'all727 original/prepared correspondences, no subset')
   self.complete=True;self.require_original(self.source_owner)
  except BaseException as error:self.complete=False;self.retain(error);raise
  return self
 def require_original(self,source_owner):
  io.need(source_owner is self.source_owner and source_owner.projection_owner is self,'same acquired original projection owner')
  source_owner.require_raw_observed()
  expected={r['recording_id']:r for r in source_owner.selection['records']}
  io.need(self.complete and self.first_error is None and set(self.records)==set(expected)and len(self.records)==727,'complete same original projection roster')
  for rid,owner in self.records.items():
   io.need(type(owner)is RecordProjectionOwner and owner.source_owner is source_owner and owner.row is expected[rid]and owner.complete and owner.first_error is None and owner.raw.close_completed and owner.prepared.close_completed,'same actual closed record/sample-validation owners')
  return self
