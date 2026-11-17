"""Complete Siena deterministic projection. No feature extraction or model calls.

The selected source/clock profile and publisher whitelist are explicit. Genuine
source authority is unavailable; declared metadata cannot admit physical inputs.
"""
import argparse,hashlib,hmac,json,os,stat
from pathlib import Path
import io_contract as io
from edf_header import inspect_header
import scientific_contract as scientific

def identity(st):return tuple(getattr(st,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))

def project(source,dest,row):
 scientific.require_source_authority('Siena_source_preparation',scientific.digest(row))
 import numpy as np
 import h5py
 fd=os.open(source,os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW)
 with os.fdopen(fd,'rb') as stream:
  before=os.fstat(stream.fileno());io.need(stat.S_ISREG(before.st_mode) and before.st_size==row['bytes'],'exact ordinary EDF')
  digest=hashlib.sha256()
  for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
  io.need(digest.hexdigest()==row['sha256'],'publisher source SHA');stream.seek(0)
  header_bytes=stream.read(row['header']['header_bytes']);io.need(hashlib.sha256(header_bytes).hexdigest()==row['header_sha256'],'captured source header')
  header=inspect_header(header_bytes,row['bytes'],row['release_whitelist']['eeg_labels']);io.need(header==row['header'],'exact source header and release-whitelist mapping');counts=header['samples_per_source_record'];channels=header['selected_channels'];offsets=np.cumsum([0]+counts);per=int(header['record_seconds']*512)
  check=hashlib.sha256(header_bytes)
  with h5py.File(dest,'x') as out:
   data=out.create_dataset('eeg_digital',(header['duration_seconds']*512,len(channels)),dtype='<i2',chunks=(512,len(channels)))
   out.create_dataset('scale_to_microvolts',data=[c['scale_to_microvolts'] for c in channels]);out.create_dataset('offset_microvolts',data=[c['offset_microvolts'] for c in channels]);out.create_dataset('channel_labels',data=np.array([c['label'].encode() for c in channels],dtype='S16'));out.create_dataset('source_channel_index',data=[c['source_index'] for c in channels])
   out.attrs['sample_rate_hz']=512;out.attrs['duration_seconds']=header['duration_seconds'];out.attrs['schema_version']=1
   for i in range(header['records']):
    raw=stream.read(2*sum(counts));io.need(len(raw)==2*sum(counts),'full continuous source record');check.update(raw);values=np.frombuffer(raw,dtype='<i2')
    data[i*per:(i+1)*per,:]=np.column_stack([values[offsets[c['source_index']]:offsets[c['source_index']+1]] for c in channels])
   io.need(not stream.read(1) and check.hexdigest()==row['sha256'] and identity(before)==identity(os.fstat(stream.fileno())),'unchanged complete source bytes')
 dest.chmod(0o444)
 digest=hashlib.sha256()
 with dest.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):digest.update(b)
 return {'bytes':dest.stat().st_size,'sha256':digest.hexdigest()}

def validate_preparation(source_map,annotations):
 io.fields(source_map,['schema','version','records','scientific_profile','release_whitelists_sha256','clock_issues','all_EEG_samples_locally_present','source_qualification_issued'])
 io.fields(annotations,['schema','records','clock_qualification_issued'])
 rows=source_map['records'];io.need(source_map['schema']=='siena_source_map_v2' and source_map['version']=='1.0.0' and type(rows)is list and len(rows)==41 and len({r['path'] for r in rows})==41 and len({r['patient'] for r in rows})==14,'whole Siena cohort')
 profile=scientific.validate_profile(source_map['scientific_profile']);scientific.pin(source_map['release_whitelists_sha256'])
 io.need(source_map['all_EEG_samples_locally_present'] is False and source_map['source_qualification_issued'] is False and annotations['clock_qualification_issued'] is False,'metadata source does not declare authentic qualification')
 io.need(annotations['schema']=='siena_annotation_map_v2' and set(annotations['records'])=={r['path'] for r in rows},'complete source annotation join')
 events={};issues=[];clock_records=[];whitelists={}
 for row in rows:
  a=annotations['records'][row['path']];io.fields(a,['events','summary_sha256','clock_record','label_profile','target_definition']);clock=scientific.validate_clock_record(a['clock_record'])
  io.need(a['label_profile']=='C1_source_parser' and a['target_definition']=='T1_pinned_parser_intervals' and a['events']==clock['source_events'],'retained pinned-parser compatibility intervals')
  io.need(clock['path']==row['path'] and clock['source_sha256']==row['sha256'] and clock['header_sha256']==row['header_sha256'] and clock['annotation_sha256']==a['summary_sha256']==row['release_whitelist']['summary_sha256'] and clock['header_clock']==row['header']['registration_clock'] and clock['duration_seconds']==row['header']['duration_seconds'],'clock decisions join exact original record/header/annotation')
  w=row['release_whitelist'];io.fields(w,['patient','summary_sha256','eeg_labels','evidence_sha256','authority_status'])
  io.need(w['patient']==row['patient']==row['path'].split('/')[0] and w['authority_status']=='unissued','whitelist exact subject and unissued authority')
  scientific.pin(w['summary_sha256']);scientific.pin(w['evidence_sha256'])
  listed=w['eeg_labels'];io.need(type(listed)is list and listed and all(type(x)is str and scientific.EEG.fullmatch(x) for x in listed) and len(listed)==len(set(listed)),'explicit release EEG list')
  io.need(row['header']['release_eeg_labels']==listed and len(row['header']['selected_channels'])==len(listed) and {x['label'] for x in row['header']['selected_channels']}==set(listed),'exact publisher-listed channel selection without extras')
  if row['patient'] in whitelists:io.need(whitelists[row['patient']]==w,'one exact release whitelist per source subject')
  whitelists[row['patient']]=w
  scientific.edge_mapping([x['label'] for x in row['header']['selected_channels']],'Siena')
  if clock['discrepancy']:issues.append({'path':row['path'],'issue':'EDF registration clock differs from annotation registration clock','summary_clock':clock['summary_clock'],'header_clock':clock['header_clock'],'resolution_status':'unresolved'})
  clock_records.append(clock)
 io.need(source_map['clock_issues']==issues,'original discrepancies cannot be erased or narrowed')
 io.need(source_map['release_whitelists_sha256']==scientific.digest({'schema':'siena_release_EEG_whitelists_v1','subjects':[whitelists[p] for p in sorted(whitelists)]}),'recomputed whole-cohort whitelist identity')
 io.need(sum(len(a['events']) for a in annotations['records'].values())==47,'all47 original event entries remain')
 for row in rows:events[row['path']]=scientific.events_for_profile(annotations['records'][row['path']]['clock_record'],profile)
 return rows,profile,events,scientific.digest(clock_records)

def build(source_map,annotations,staged,output,key,max_bytes):
 rows,profile,events,clock_pin=validate_preparation(source_map,annotations)
 source_binding=scientific.digest({'source_map':source_map,'annotations':annotations})
 scientific.require_source_authority('Siena_source_preparation',source_binding)
 io.need(not output.exists() and not output.is_symlink() and not output.parent.is_symlink(),'fresh ordinary output parent')
 io.need(type(key)is bytes and len(key)==32,'private opaque-ID key')
 logical=sum(r['header']['duration_seconds']*512*2*len(r['header']['selected_channels']) for r in rows)
 io.need(type(max_bytes)is int and max_bytes>=logical+100000000,'entire source projection plus100MB overhead; no truncation')
 for row in rows:
  p=staged/row['path'];io.need(p.resolve().is_relative_to(staged.resolve()) and p.is_file() and not p.is_symlink(),'all original EDF paths present')
 output.mkdir(mode=0o700);(output/'signals').mkdir();(output/'private').mkdir(mode=0o700);panel=[];targets=[]
 for row in rows:
  rid=hmac.new(key,('record:'+row['path']).encode(),hashlib.sha256).hexdigest()[:24];pid=hmac.new(key,('patient:'+row['patient']).encode(),hashlib.sha256).hexdigest()[:24]
  pin=project(staged/row['path'],output/'signals'/(rid+'.h5'),row);d=row['header']['duration_seconds']
  panel.append(dict(recording_id=rid,patient_id=pid,duration_seconds=d,observed_intervals=[[0,d]],path='signals/'+rid+'.h5',**pin));targets.append({'recording_id':rid,'events':events[row['path']]})
  io.need(sum(p.stat().st_size for p in (output/'signals').iterdir())+10000000<=max_bytes,'actual output cap')
 from score import panel as validate,targets as validate_targets
 value={'schema_version':1,'task_id':io.TASK,'records':panel};raw=io.encoded(value);records=validate(value)
 gold={'schema_version':1,'task_id':io.TASK,'panel_sha256':hashlib.sha256(raw).hexdigest(),'records':targets};validate_targets(gold,records,gold['panel_sha256'])
 source_profile={'schema':'siena_preparation_profile_v1','scientific_profile':profile,'panel_sha256':hashlib.sha256(raw).hexdigest(),'targets_sha256':scientific.digest(gold),'clock_records_sha256':clock_pin,'release_whitelists_sha256':source_map['release_whitelists_sha256'],'source_qualification_sha256':source_binding,'authority_status':'unissued'}
 io.write(output/'private/SOURCE_PROFILE.json',source_profile)
 io.write(output/'private/targets.json',gold);io.write(output/'panel.json',value) # completion marker last
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for k in ['source-map','annotations','staged','output','key']:p.add_argument('--'+k,type=Path,required=True)
 for k in ['source-map-sha256','annotations-sha256']:p.add_argument('--'+k,required=True)
 p.add_argument('--max-output-bytes',type=int,required=True);a=p.parse_args()
 source_map=io.strict(io.read(a.source_map,2000000,a.source_map_sha256));annotations=io.strict(io.read(a.annotations,1000000,a.annotations_sha256))
 validate_preparation(source_map,annotations)
 scientific.require_source_authority('Siena_source_preparation',scientific.digest({'source_map':source_map,'annotations':annotations}))
 build(source_map,annotations,a.staged,a.output,io.read(a.key,32),a.max_output_bytes)
