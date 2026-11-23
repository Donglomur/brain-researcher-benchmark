"""Original streaming readers for the three pinned ABR source archives.

Produces a complete *operator preparation bundle*, not admitted candidate input
or a scored reference. No author code, model weights, fitting or inferred labels.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import hmac
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import zipfile

TASK_ID = 'NEURAL-SCOPE-20261114-ABR-TRANSFER'
TONES = (3000,6000,12000,18000,24000,30000,36000,42000)
MAX_MEMBER = 8*1024**2
MAX_EXPANDED = 406584009
MAX_OUTPUT = 512*1024**2
PINS = {
 'manor': {'bytes':14131356,'sha256':'4f9e3bc3f90f7571b0175eca0d089c41838b3a6edd1468feb0fd6012c597f32c','members':222,'expanded':32967252,'tables':110,'traces':6737,'release':'zenodo:17584961','filename':'Manor_Lab_Cleaned.zip'},
 'liberman': {'bytes':12392618,'sha256':'c25fe12ac6594e6d9313a7afddf2896c8114e6126aebcfd555625b73932cda59','members':1740,'expanded':34919265,'tables':748,'traces':7293,'release':'zenodo:17584961','filename':'ABR_Data_Liberman.zip'},
 'marcotti': {'bytes':138620782,'sha256':'3fd7dd1ceed336090fbb517882a15975bd211476d09bde28b9270a7f7b001993','members':211,'expanded':338697492,'tables':209,'traces':16226,'release':'zenodo:15619100','filename':'MouseABRs.zip'},
}
HOLDS = [
 'Marcotti CSV does not encode a physical sample period, voltage unit or acoustic zero; no common 244-point/10-ms view is admitted.',
 'Three target threshold tokens exceed the largest recorded level. Literal 100 must not be silently converted to an exact threshold or a censoring bound.',
 'Liberman stored-row continuity is unresolved: preserve sample indices without a physical waveform axis; the CFTS header period alone does not resolve continuous versus concatenated storage.',
 'Liberman ear headers and filenames may conflict; native voltage/offset and biological repeat mappings need independent source evidence.',
 'Manor wave-cursor fields are not an authenticated threshold-label table; complete support identities, labels and group splits remain unqualified.',
 'No source-only trained comparator, matched four-stack calibration, participant isolation or authentic scoring has been qualified.',
]

class SourceError(ValueError): pass

def need(ok, message):
 if not ok: raise SourceError(message)

def number(value, label):
 try: x=float(value)
 except (TypeError, ValueError, OverflowError) as exc: raise SourceError('invalid '+label) from exc
 need(math.isfinite(x),'nonfinite '+label)
 return x

def canonical(obj):
 return (json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def digest_file(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024**2),b''): h.update(chunk)
 return h.hexdigest()

def stimulus(frequency, target=False):
 value=number(frequency,'frequency')
 if target:
  if value==100: return {'kind':'click'}
  need(value in TONES,'unknown target frequency (100 is click only in Marcotti)')
 need(value>0,'nonpositive tone')
 return {'kind':'tone','frequency_hz':value}

def stimulus_token(value):
 return 'click' if value['kind']=='click' else 'tone:'+format(value['frequency_hz'],'.12g')

def csv_rows(body):
 need(len(body)<=MAX_MEMBER,'member size cap')
 try: text=body.decode('utf-8-sig')
 except UnicodeDecodeError: text=body.decode('latin1')
 reader=csv.reader(io.StringIO(text,newline=''),strict=True)
 header=None
 for n,row in enumerate(reader):
  need(n<200001,'CSV row cap')
  if header is None:
   if len(row)<2:
    need(n<256,'CSV prefix cap');continue
   header=[x.strip() for x in row]
   need(len(header)<32768,'CSV column cap')
   continue
  if not row:continue
  need(len(row)==len(header),'ragged CSV row')
  yield header,row,reader.line_num
 need(header is not None,'missing CSV header')

def column(header,name):
 matches=[i for i,x in enumerate(header) if x==name]
 need(len(matches)==1,'missing/duplicate required column '+name)
 return matches[0]

def parse_wave_csv(body, lab):
 """Preserve every record and signal sample; tolerate duplicated unused metadata."""
 need(lab in ('manor','marcotti'),'wrong CSV source')
 layout=None
 for record_index,(header,row,line) in enumerate(csv_rows(body)):
  if layout is None:
   signal=[i for i,x in enumerate(header) if x.isdecimal()]
   need(signal and [int(header[i]) for i in signal]==list(range(len(signal))),'sample indices must be unique, ordered and complete')
   signal_set=set(signal)
   metadata_indices=[i for i in range(len(header)) if i not in signal_set]
   fi=column(header,'Freq(Hz)'); li=column(header,'Level(dB)')
   layout=True
  samples=[number(row[i],'waveform') for i in signal]
  expected=244 if lab=='manor' else 1953
  need(len(samples)==expected,'unexpected native sample count')
  metadata=[{'column_index':i,'name':header[i],'value':row[i]} for i in metadata_indices]
  if lab=='manor':
   dt=number(row[column(header,'Samp. Per.')],'sample period')/1000
   offset=number(row[column(header,'O.S. Time')],'first sample offset')
   need(number(row[column(header,'No. Samps.')],'declared samples')==len(samples),'declared sample count differs')
   need(dt>0 and 'Data(uv)...' in header,'unsupported Manor calibration header')
   axis={'kind':'uniform','step_ms':dt,'first_sample_ms':offset,'origin':'recording_offset_not_verified_acoustic_zero','unit':'uV','evidence':'TDT BioSigRZ CSV data-analysis manual; native Samp. Per./O.S. Time/Data(uv)...'}
  else:
   axis={'kind':'sample_index','sample_period_ms':None,'first_sample_ms':None,'unit':None,'reason':'release CSV contains no physical axis or voltage calibration'}
  yield {'record_index':record_index,'source_line':line,'stimulus':stimulus(row[fi],target=lab=='marcotti'),'level_db':number(row[li],'level'),'axis':axis,'samples':samples,'private_metadata':metadata}

def parse_cfts(body):
 """Parse every stored value per LEVELS column without assuming row continuity."""
 need(len(body)<=MAX_MEMBER,'member size cap')
 text=body.decode('latin1'); fields={}; raw=[]; matrix=[]; started=False
 for line in text.splitlines():
  need(len(line)<=65536,'CFTS line cap')
  if not started:
   raw.append(line)
   need(len(raw)<=256,'CFTS header cap')
   if line.strip()==':DATA': started=True;continue
   for piece in line.lstrip(':').split('\t'):
    key,sep,value=piece.partition(':')
    if sep:
     key=key.strip().upper();fields.setdefault(key,[]).append(value.strip())
   continue
  if line.strip():
   matrix.append([number(x,'CFTS waveform') for x in line.split()])
   need(len(matrix)<=200000,'CFTS row cap')
 need(started and matrix,'missing CFTS data')
 def field(name):
  values=fields.get(name.upper(),[]);need(len(values)==1,'missing/duplicate CFTS '+name);return values[0]
 levels=[number(x,'CFTS level') for x in field('LEVELS').rstrip(';').split(';')]
 need(levels and all(len(row)==len(levels) for row in matrix),'CFTS LEVELS/data width mismatch')
 freq=number(field('SW FREQ'),'CFTS frequency')*1000
 step=number(field('SAMPLE (µSEC)'),'CFTS sample period')/1000
 need(step>0,'nonpositive CFTS sample period')
 threshold=field('THRESHOLD')
 for i,level in enumerate(levels):
  yield {'record_index':i,'stimulus':stimulus(freq),'level_db':level,'samples':[row[i] for row in matrix],
   'axis':{'kind':'sample_index','sample_period_ms':None,'first_sample_ms':None,'unit':None,
    'header_sample_period_ms':step,'physical_layout':'unresolved_continuous_or_concatenated',
    'reason':'CFTS SAMPLE header period retained as unqualified metadata; stored-row continuity, amplitude and recording/acoustic offset unresolved'},
   'private_metadata':{'header_lines':raw,'fields':fields,'ear_header':field('SW EAR'),'threshold_raw':threshold}}

def target_id(member):
 path=PurePosixPath(member)
 need(path.parent.as_posix()=='Mouse ABRs' and re.fullmatch(r'\d+\.csv',path.name) is not None,'unrecognized target waveform member')
 value=int(path.stem);need(1<=value<=104,'target animal outside release roster');return value

def parse_thresholds(body):
 rows={}
 for header,row,line in csv_rows(body):
  need(len(header)==12 and set(header)=={'Mouse ID','Click','3 kHz','6 kHz','12 kHz','18 kHz','24 kHz','30 kHz','36 kHz','42 kHz','Age','Sex'},'target threshold table schema')
  raw=row[column(header,'Mouse ID')];need(re.fullmatch(r'\d+',raw) is not None,'target threshold animal ID')
  animal=int(raw);need(1<=animal<=104 and animal not in rows,'duplicate/out-of-roster target annotation animal')
  observations=[]
  for name in ['Click']+[f'{f//1000} kHz' for f in TONES]:
   token=row[column(header,name)];value=number(token,'target threshold')
   stim={'kind':'click'} if name=='Click' else stimulus(int(name.split()[0])*1000,target=True)
   observations.append({'stimulus':stim,'raw_token':token,'source_numeric_value':value,'semantics':'unresolved_exact_or_censored','source_line':line,'source_column':name})
  rows[animal]={'annotations':observations,'age_raw':row[column(header,'Age')],'sex_raw':row[column(header,'Sex')]}
 need(set(rows)==set(range(1,105)),'threshold table must include all104 target animals')
 return rows

def safe_members(archive, pin):
 members=archive.infolist();need(len(members)==pin['members'],'archive member denominator differs')
 need(sum(x.file_size for x in members)==pin['expanded'],'archive expanded bytes differ')
 seen=set()
 for member in members:
  name=member.filename;p=PurePosixPath(name)
  need(name and not p.is_absolute() and '..' not in p.parts and '\\' not in name and '\x00' not in name,'unsafe ZIP path')
  need(name not in seen,'duplicate ZIP member');seen.add(name)
  need(member.file_size<=MAX_MEMBER and not member.flag_bits&1,'oversize/encrypted ZIP member')
  mode=member.external_attr>>16
  need(not stat.S_ISLNK(mode),'ZIP symlink refused')
 return sorted(members,key=lambda x:x.filename)

class Bundle:
 """Bounded, deterministic gzip streams; source paths/labels remain private."""
 def __init__(self,destination,key):
  self.root=Path(destination);need(not self.root.exists(),'destination must not exist')
  self.root.mkdir(mode=0o700,parents=True);self.key=key;self.streams={};self.files={};self.bytes=0
 def stream(self,name):
  if name not in self.streams:
   path=self.root/name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
   f=path.open('xb');os.chmod(path,0o600);self.files[name]=f
   self.streams[name]=gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0,compresslevel=1)
  return self.streams[name]
 def write(self,name,payload):
  self.bytes+=len(payload);need(self.bytes<=MAX_OUTPUT,'uncompressed output cap')
  self.stream(name).write(payload)
 def json(self,name,obj):self.write(name,canonical(obj))
 def opaque(self,namespace,value):
  return hmac.new(self.key,(namespace+'\0'+value).encode(),hashlib.sha256).hexdigest()[:32]
 def close(self):
  for s in self.streams.values():s.close()
  for f in self.files.values():f.close()

def prepare(paths,destination,key):
 need(len(key)==32,'opaque ID key must contain32bytes')
 # Verify all archives before creating a bundle. Exact version pins cannot be overridden.
 for lab,pin in PINS.items():
  path=Path(paths[lab]);st=path.lstat();need(stat.S_ISREG(st.st_mode),'source must be regular nonsymlink file')
  need(st.st_size==pin['bytes'] and digest_file(path)==pin['sha256'],'source size/hash mismatch: '+lab)
 bundle=Bundle(destination,key);counts={};target={};thresholds=None;observed_animals={};offsets={};annotation_members=[];annotation_animals=set()
 try:
  for lab,pin in PINS.items():
   totals={'members':0,'tables':0,'traces':0,'waveform_values':0,'annotation_tables':0}
   with zipfile.ZipFile(paths[lab]) as archive:
    for member in safe_members(archive,pin):
     name=member.filename;totals['members']+=1
     body=archive.read(member) # bounded<=8MiB; read-to-end checks ZIP CRC.
     record={'lab':lab,'member':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
     if member.is_dir():record['role']='directory'
     elif name.startswith('__MACOSX/') or PurePosixPath(name).name.startswith('._'):record['role']='AppleDouble_sidecar'
     elif lab=='marcotti' and name=='thresholds.csv':
      need(thresholds is None,'duplicate threshold table');thresholds=parse_thresholds(body)
      record['role']='private_thresholds';totals['tables']+=1;totals['annotation_tables']+=1
     elif lab=='marcotti' and 'wave 1 analysis' in name.lower():
      # Preserve complete annotation tables in the private bundle. Do not interpret peaks as thresholds.
      annotation_name=PurePosixPath(name)
      need(annotation_name.parent.as_posix()=='Wave 1 analysis' and re.fullmatch(r'\d+\.csv',annotation_name.name) is not None,'unrecognized wave1 annotation member')
      annotation_animal=int(annotation_name.stem)
      need(1<=annotation_animal<=104 and annotation_animal not in annotation_animals,'duplicate or out-of-roster wave1 annotation animal')
      annotation_animals.add(annotation_animal)
      annotation_members.append(name);bundle.write('private/wave1/'+hashlib.sha256(name.encode()).hexdigest()+'.csv.gz',body)
      record['role']='private_wave1';totals['tables']+=1;totals['annotation_tables']+=1
     else:
      if lab=='marcotti':
       animal=target_id(name);need(animal not in observed_animals,'multiple waveform files map to one target animal')
       observed_animals[animal]=name;traces=parse_wave_csv(body,lab)
      elif lab=='manor':
       need(name.lower().endswith('.csv'),'unknown Manor scientific member');traces=parse_wave_csv(body,lab)
      else:
       need(name.lower().endswith('.tsv'),'unknown Liberman scientific member');traces=parse_cfts(body)
      record['role']='waveforms';totals['tables']+=1
      for trace in traces:
       totals['traces']+=1;totals['waveform_values']+=len(trace['samples'])
       source_id=f"{lab}/{name}/{trace['record_index']}";trace_id=bundle.opaque('trace',source_id)
       family='target' if lab=='marcotti' else 'support/'+lab
       values=trace.pop('samples');metadata=trace.pop('private_metadata');n=len(values)
       start=offsets.get(family,0);offsets[family]=start+n
       bundle.write('observations/'+family+'/waveforms.f64le.gz',struct.pack('<'+str(n)+'d',*values))
       observation={'trace_id':trace_id,'sample_offset':start,'sample_count':n,'stimulus':trace['stimulus'],'level_db':trace['level_db'],'axis':trace['axis']}
       private={'trace_id':trace_id,'lab':lab,'member':name,'record_index':trace['record_index'],'metadata':metadata}
       if lab=='marcotti':
        k=(animal,stimulus_token(trace['stimulus']));case_id=bundle.opaque('case',str(animal)+'/'+k[1]);observation['case_id']=case_id
        case=target.setdefault(k,{'case_id':case_id,'animal_source_id':animal,'stimulus':trace['stimulus'],'traces':[],'levels':[]})
        case['traces'].append(trace_id);case['levels'].append(trace['level_db'])
       # Record index and source filename do not enter observation index.
       bundle.json('observations/'+family+'/index.jsonl.gz',observation)
       bundle.json('private/trace-provenance.jsonl.gz',private)
     bundle.json('private/member-ledger.jsonl.gz',record)
   need(totals['tables']==pin['tables'] and totals['traces']==pin['traces'],'complete table/trace denominator differs: '+lab)
   counts[lab]=totals
  need(set(observed_animals)==set(range(1,105)) and thresholds is not None,'incomplete target roster')
  need(annotation_animals==set(range(1,105)),'incomplete wave1 annotation roster')
  # Compare the complete observed case set to the source annotation set. Never synthesize missing cases.
  labels={(animal,stimulus_token(a['stimulus'])):a for animal,row in thresholds.items() for a in row['annotations']}
  need(set(target)==set(labels),'target observation/threshold animal-stimulus join differs')
  beyond=0;duplicates=0
  for k,case in sorted(target.items()):
   annotation=labels[k];low=min(case['levels']);high=max(case['levels'])
   outside=annotation['source_numeric_value']<low or annotation['source_numeric_value']>high;beyond+=outside
   duplicate=len(case['levels'])!=len(set(case['levels']));duplicates+=duplicate
   bundle.json('observations/target/cases.jsonl.gz',{'case_id':case['case_id'],'stimulus':case['stimulus'],'trace_ids':case['traces'],'repeated_levels_preserved':duplicate})
   bundle.json('private/annotation-projection.jsonl.gz',{'case_id':case['case_id'],'animal_source_id':k[0],'animal_id':bundle.opaque('animal',str(k[0])),'genetic_background':'C57BL/6NTacCdh23+' if k[0]<=54 else 'C57BL/6N','annotation':annotation,'observed_level_min':low,'observed_level_max':high,'outside_observed_levels':outside,'score_admission':False})
  manifest={'task_id':TASK_ID,'implementation':'native-inputs-v1','status':'complete_native_preparation_not_scientifically_admitted','candidate_delivery_admitted':False,'authentic_scoring_admitted':False,'source_pins':PINS,'counts':counts,'target_animals':len(observed_animals),'target_cases':len(target),'target_trace_count':counts['marcotti']['traces'],'target_annotation_values_outside_recorded_levels':beyond,'target_cases_with_repeated_levels':duplicates,'sample_storage':'gzip contiguous little-endian IEEE754float64; offsets count samples, not bytes','holds':HOLDS,'uncompressed_output_bytes_before_manifest':bundle.bytes}
  bundle.json('private/preparation-manifest.json.gz',manifest)
  bundle.json('private/id-key.json.gz',{'key_hex':key.hex(),'handling':'operator-only; public IDs do not authenticate protected evaluation'})
 finally:bundle.close()
 # Completion seal appears only after all source members, joins, and outputs succeeded.
 files={str(p.relative_to(bundle.root)):{'bytes':p.stat().st_size,'sha256':digest_file(p)} for p in sorted(bundle.root.rglob('*')) if p.is_file()}
 completion={'status':manifest['status'],'candidate_delivery_admitted':False,'target_animals':104,'target_cases':len(target),'files':files,'manifest':manifest}
 out=bundle.root/'COMPLETE.json';out.write_bytes(canonical(completion));os.chmod(out,0o600)
 return completion

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 for lab in PINS:parser.add_argument('--'+lab,required=True,type=Path)
 parser.add_argument('--output',required=True,type=Path)
 parser.add_argument('--key-file',required=True,type=Path,help='operator-owned file containing exactly32binarybytes')
 args=parser.parse_args()
 try:
  need(args.key_file.stat().st_size==32,'key file must contain32bytes')
  result=prepare({lab:getattr(args,lab) for lab in PINS},args.output,args.key_file.read_bytes())
 except (SourceError,ValueError,OSError,csv.Error,zipfile.BadZipFile,UnicodeError) as exc:
  print(json.dumps({'status':'failed_no_completion_seal','error':str(exc)}));return 2
 print(json.dumps({'status':result['status'],'target_animals':result['target_animals'],'target_cases':result['target_cases'],'candidate_delivery_admitted':False}));return 0

if __name__=='__main__':raise SystemExit(main())
