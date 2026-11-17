"""Pure metadata contracts. A declaration never issues authentic-source authority.

The authentic issuer is intentionally absent. Actual consumers call the explicit
barrier before physical input use or C2 target admission. These validators can be
reviewed/tested on invented metadata without pretending the barrier was met.
"""
import hashlib,json,math,re

SHA=re.compile(r'[0-9a-f]{64}\Z')
ID=re.compile(r'[0-9a-f]{24}\Z')
EEG=re.compile(r'^(?:FP|AF|F|FC|FT|C|CP|T|P|PO|O)(?:[0-9]{1,2}|Z)$')
EDGES=('FP1-F7','F7-T7','T7-P7','P7-O1','FP1-F3','F3-C3','C3-P3','P3-O1','FP2-F4','F4-C4','C4-P4','P4-O2','FP2-F8','F8-T8','T8-P8','P8-O2','FZ-CZ','CZ-PZ')
ALIASES={'T3':'T7','T4':'T8','T5':'P7','T6':'P8'}
LABEL_PROFILES=('C1_source_parser','C2_edf_aligned')
SOURCE_PARSER_SHA256='e5f23800937640cce32eabfd4e43ecd184f09ad941a65ae55c3f76d69126b3fb'
FIXED_PROFILE={'schema':'neural012_scientific_profile_v1','target':'T1_pinned_parser_intervals','montage':'M1_fixed18_release_whitelist','temporal':'E1_offline_whole_record','fit':'F2_two_phase','query':'Q1_whole_job','comparison':'O1_reference_controlled','qualification_status':'unissued'}

def need(ok,message):
 if not ok:raise ValueError(message)
def fields(value,keys):need(type(value)is dict and set(value)==set(keys),'exact scientific metadata fields')
def encoded(value):return (json.dumps(value,sort_keys=True,allow_nan=False,separators=(',',':'))+'\n').encode()
def digest(value):return hashlib.sha256(encoded(value)).hexdigest()
def pin(value):need(type(value)is str and SHA.fullmatch(value),'exact SHA256 declaration');return value
def profile(label_profile):
 need(label_profile in LABEL_PROFILES,'selected clock profile');return dict(FIXED_PROFILE,label_profile=label_profile)
def validate_profile(value):
 fields(value,list(FIXED_PROFILE)+['label_profile'])
 need(all(value[k]==v for k,v in FIXED_PROFILE.items()) and value['label_profile'] in LABEL_PROFILES,'root-selected scientific profile; qualification remains unissued')
 return value
def profile_sha256(value):return digest(validate_profile(value))

class SourceQualificationUnavailable(RuntimeError):pass
def require_source_authority(purpose,binding_sha256):
 """No issuer installed: syntax, hashes, declarations and callbacks are not proof."""
 need(purpose in ('physical_signal_inputs','Siena_source_preparation','full_panel_source_join','C2_target_alignment','protected_target_admission','phase_input_admission','campaign_input_admission'),'named scientific source requirement')
 pin(binding_sha256)
 raise SourceQualificationUnavailable('Authentic source authority is unavailable for '+purpose+'; no declaration can qualify '+binding_sha256)

def normalized_label(label):
 need(type(label)is str and 0<len(label)<=32 and label.isascii(),'bounded exact channel label')
 return '-'.join(ALIASES.get(x,x) for x in label.upper().removeprefix('EEG ').split('-'))

def edge_mapping(labels,cohort):
 """M1 structural mapping only; common-reference truth is a separate authority."""
 need(type(labels)is list and 0<len(labels)<=512 and cohort in ('CHB','Siena'),'bounded measured channel roster')
 canonical=[normalized_label(x) for x in labels];out=[]
 for edge in EDGES:
  a,b=edge.split('-')
  if cohort=='CHB':
   match=[(i,1) for i,x in enumerate(canonical) if x==edge]+[(i,-1) for i,x in enumerate(canonical) if x==b+'-'+a]
   need(len(match)==1,'M1 exact unique measured edge; no duplicate/path/zero-fill substitution')
   i,sign=match[0];out.append([i,None,sign])
  else:
   need(canonical.count(a)==1 and canonical.count(b)==1,'M1 unique complete Siena endpoints')
   out.append([canonical.index(a),canonical.index(b),1])
 return out

MONTAGE_FIELDS=('cohort','sample_rate_hz','channel_labels','source_channel_indices','calibration','release_eeg_labels','release_whitelist_sha256','common_reference','input_evidence_sha256')
def montage_sha256(record):return digest({k:record[k] for k in MONTAGE_FIELDS})
def validate_reference_record(record):
 fields(record,['recording_id','duration_seconds','signal_sha256','montage_sha256',*MONTAGE_FIELDS])
 need(type(record['recording_id'])is str and ID.fullmatch(record['recording_id']),'opaque reference record ID')
 need(type(record['duration_seconds'])is int and 0<record['duration_seconds']<=86400,'complete recording duration')
 pin(record['signal_sha256']);pin(record['input_evidence_sha256']);pin(record['montage_sha256'])
 cohort=record['cohort'];labels=record['channel_labels'];mapping=edge_mapping(labels,cohort)
 for label in labels:
  parts=normalized_label(label).split('-')
  need((len(parts)==1 and EEG.fullmatch(parts[0])) or (len(parts)==2 and EEG.fullmatch(parts[0]) and (EEG.fullmatch(parts[1]) or parts[1] in ('REF','CS2'))),'EEG-only measured derivations; no auxiliary channel admission')
 need(type(record['sample_rate_hz'])is int and record['sample_rate_hz']==(256 if cohort=='CHB' else 512),'native cohort sample rate')
 indices=record['source_channel_indices'];need(type(indices)is list and len(indices)==len(labels) and all(type(i)is int and 0<=i<512 for i in indices) and indices==sorted(set(indices)),'exact unique ordered source-channel indices')
 cal=record['calibration'];fields(cal,['scale_to_microvolts','offset_microvolts'])
 for key in cal:
  values=cal[key];need(type(values)is list and len(values)==len(labels) and all(type(x)in(int,float) and math.isfinite(x) for x in values),'complete finite affine calibration')
 need(all(x>0 for x in cal['scale_to_microvolts']),'positive physical scaling')
 ref=record['common_reference'];fields(ref,['claim','system','evidence_sha256','qualification_status'])
 need(ref['qualification_status']=='unissued','declaration is not common-reference qualification')
 if cohort=='CHB':
  need(record['release_eeg_labels']==[] and record['release_whitelist_sha256'] is None and ref=={'claim':'not_required','system':None,'evidence_sha256':None,'qualification_status':'unissued'},'CHB measured bipolar policy')
 else:
  listed=record['release_eeg_labels'];need(type(listed)is list and listed and len(listed)==len(set(listed)) and all(type(x)is str and EEG.fullmatch(x) for x in listed),'explicit unique release-listed EEG electrodes')
  need(len(labels)==len(set(labels)) and set(labels)==set(listed),'Siena native channel support exactly release EEG whitelist')
  pin(record['release_whitelist_sha256'])
  need(ref['claim'] in ('unresolved','common_reference'),'explicit unresolved or documentary reference claim')
  if ref['claim']=='unresolved':need(ref['system'] is None and ref['evidence_sha256'] is None,'no inferred reference evidence')
  else:
   need(type(ref['system'])is str and 0<len(ref['system'])<=256,'named documentary reference system');pin(ref['evidence_sha256'])
 need(record['montage_sha256']==montage_sha256(record),'exact declared montage identity')
 return mapping

def validate_reference(value,expected_rows=None):
 fields(value,['schema','scientific_profile','records']);need(value['schema']=='neural012_reference_declaration_v3','versioned physical declaration')
 validate_profile(value['scientific_profile']);rows=value['records'];need(type(rows)is list and 0<len(rows)<=727,'bounded full or projected reference roster')
 by_id={}
 for record in rows:
  validate_reference_record(record);rid=record['recording_id'];need(rid not in by_id,'unique declared reference ID');by_id[rid]=record
 if expected_rows is not None:
  need(type(expected_rows)is list and len(expected_rows)==len(by_id) and len({r['recording_id'] for r in expected_rows})==len(expected_rows),'exact expected reference roster')
  need(set(by_id)=={r['recording_id'] for r in expected_rows},'no other-phase physical reference rows')
  for row in expected_rows:join_reference(by_id[row['recording_id']],row)
 return value
def join_reference(record,row):
 need(record['recording_id']==row['recording_id'] and record['cohort']==row['cohort'] and record['duration_seconds']==row['duration_seconds'] and record['signal_sha256']==row['signal']['sha256'] and record['montage_sha256']==row['montage_sha256'],'reference binds actual case signal, duration and montage')
 return record
def project_reference(value,phase_rows):
 validate_reference(value);need(type(phase_rows)is list and phase_rows,'nonempty phase support')
 by_id={r['recording_id']:r for r in value['records']}
 need(all(r['recording_id'] in by_id for r in phase_rows),'all phase records have reference declarations')
 projected={'schema':value['schema'],'scientific_profile':dict(value['scientific_profile']),'records':[json.loads(encoded(by_id[r['recording_id']])) for r in phase_rows]}
 return validate_reference(projected,phase_rows)
def reference_record(value,row):
 validate_reference(value);matches=[r for r in value['records'] if r['recording_id']==row['recording_id']]
 need(len(matches)==1,'exact physical reference record');return join_reference(matches[0],row)

def clock_seconds(value):
 need(type(value)is str and re.fullmatch(r'\d{1,2}[.:]\d{2}[.:]\d{2}',value),'explicit clock string')
 h,m,s=map(int,re.split('[.:]',value));need(0<=h<24 and 0<=m<60 and 0<=s<60,'clock range');return h*3600+m*60+s
def event_intervals(value,duration):
 need(type(duration)is int and 0<duration<=86400 and type(value)is list,'bounded clock support');last=0
 for pair in value:
  need(type(pair)is list and len(pair)==2 and all(type(x)in(int,float) and math.isfinite(x) and x==int(x) for x in pair),'integral event endpoints')
  a,b=pair;need(0<=a<b<=duration and a>=last,'complete ordered in-record events');last=b
 return value
def shifted_clock_candidate(source_events,summary_clock,header_clock,duration):
 """C2 hypothesis only; preserves T1 event durations/corrections, never clips."""
 event_intervals(source_events,duration);delta=clock_seconds(summary_clock)-clock_seconds(header_clock);out=[]
 for a,b in source_events:
  start=(int(a)+delta)%86400;end=start+int(b-a)
  if not(0<=start<end<=duration):return {'status':'invalid_outside_record','events':None,'origin_delta_seconds':delta}
  out.append([start,end])
 if any(out[i][0]<out[i-1][1] for i in range(1,len(out))):return {'status':'invalid_order','events':None,'origin_delta_seconds':delta}
 return {'status':'candidate_only','events':out,'origin_delta_seconds':delta}
def validate_clock_record(value):
 fields(value,['schema','path','source_version','source_sha256','header_sha256','annotation_sha256','parser_sha256','summary_clock','header_clock','duration_seconds','source_events','C2_candidate','discrepancy','resolution'])
 need(value['schema']=='siena_clock_record_v2' and value['source_version']=='1.0.0','source clock identity')
 need(type(value['path'])is str and re.fullmatch(r'PN\d{2}/[^/]+\.edf',value['path']),'bounded original source path')
 for k in ('source_sha256','header_sha256','annotation_sha256','parser_sha256'):pin(value[k])
 need(value['parser_sha256']==SOURCE_PARSER_SHA256,'root-selected original T1 parser identity')
 event_intervals(value['source_events'],value['duration_seconds'])
 need(encoded(value['C2_candidate'])==encoded(shifted_clock_candidate(value['source_events'],value['summary_clock'],value['header_clock'],value['duration_seconds'])),'exact typed recomputed clock hypothesis')
 need(type(value['discrepancy'])is bool and value['discrepancy']==(clock_seconds(value['summary_clock'])!=clock_seconds(value['header_clock'])),'original clock discrepancy preserved')
 r=value['resolution'];fields(r,['status','selected_origin','evidence_sha256','authority_status'])
 need(r['authority_status']=='unissued' and r['status'] in ('unresolved','documented_selection'),'clock decision never self-qualifies')
 if r['status']=='unresolved':need(r['selected_origin'] is None and r['evidence_sha256'] is None,'no invented clock adjudication')
 else:need(r['selected_origin'] in ('summary','EDF'),'explicit origin decision');pin(r['evidence_sha256'])
 return value
def events_for_profile(clock_record,scientific_profile):
 c=validate_clock_record(clock_record);p=validate_profile(scientific_profile)
 if p['label_profile']=='C1_source_parser':return [list(x) for x in c['source_events']]
 r=c['resolution'];need(r['status']=='documented_selection' and r['selected_origin']=='EDF','C2 needs explicit original-record EDF-clock resolution')
 need(c['C2_candidate']['status']=='candidate_only','C2 complete in-record events without clipping')
 require_source_authority('C2_target_alignment',digest({'clock_record':c,'scientific_profile':p}))
 return [list(x) for x in c['C2_candidate']['events']]
