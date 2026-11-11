"""Future source metadata projection with explicit C1/C2 and whitelist evidence.

The genuine source issuer is absent. No source operand is opened before its
barrier. C2 candidates are hypotheses, never silently installed target labels.
"""
import argparse,hashlib,json,re
from pathlib import Path
from edf_header import inspect_header
from official_clock import _loadSeizures,_correctEdfFileNameTypos
from io_contract import need
import io_contract as io
import scientific_contract as scientific

PARSER_SHA='e5f23800937640cce32eabfd4e43ecd184f09ad941a65ae55c3f76d69126b3fb'

def seconds(clock):
 return scientific.clock_seconds(clock)

def validate_whitelists(value):
 io.fields(value,['schema','subjects']);need(value['schema']=='siena_release_EEG_whitelists_v1' and type(value['subjects'])is list and len(value['subjects'])==14,'complete explicit release whitelist declaration')
 out={}
 for row in value['subjects']:
  io.fields(row,['patient','summary_sha256','eeg_labels','evidence_sha256','authority_status'])
  p=row['patient'];need(type(p)is str and re.fullmatch(r'PN\d{2}',p) and p not in out,'unique release subject')
  scientific.pin(row['summary_sha256']);scientific.pin(row['evidence_sha256']);need(row['authority_status']=='unissued','whitelist declaration is not authentic admission')
  labels=row['eeg_labels'];need(type(labels)is list and labels and all(type(x)is str and scientific.EEG.fullmatch(x) for x in labels) and len(labels)==len(set(labels)),'explicit release-listed EEG names')
  scientific.edge_mapping(labels,'Siena');out[p]=row
 return out

def build(source,release_whitelists,selected_profile):
 scientific.validate_profile(selected_profile);whitelists=validate_whitelists(release_whitelists)
 scientific.require_source_authority('Siena_source_preparation',scientific.digest({'scientific_profile':selected_profile,'release_whitelists':release_whitelists}))
 need(hashlib.sha256(io.read(Path(__file__).with_name('official_clock.py'),100000)).hexdigest()==PARSER_SHA,'exact retained original annotation parser')
 headers=io.strict(io.read(source/'HEADERS.json',1000000))['records'];rows=[];events={};issues=[]
 for row in headers:
  path=row['path'];need(type(path)is str and re.fullmatch(r'PN\d{2}/[^/]+\.edf',path),'confined original EDF name');patient=Path(path).parent.name;need(patient in whitelists,'source subject has release whitelist')
  whitelist=whitelists[patient];header_path=source/row['header_file'];need(header_path.resolve().is_relative_to(source.resolve()),'confined captured header')
  body=io.read(header_path,1000000,row['sha256']);h=inspect_header(body,row['source_bytes'],whitelist['eeg_labels'])
  summary=source/Path(path).parent/('Seizures-list-'+patient+'.txt');summary_raw=io.read(summary,1000000,whitelist['summary_sha256']);text=summary_raw.decode('utf8')
  name=_correctEdfFileNameTypos(path)
  starts=[];start_strings=[];matches=0
  for block in re.split(r'(?=File name:)',text):
   first=block.splitlines()[0] if block else ''
   if first.strip()!='File name: '+name:continue
   matches+=1
   m=re.search(r'Registration start time:\s*(\d[\d .:]+)',block)
   if m:
    clock=m[1].strip().replace('1 6.','16.')
    starts.append(seconds(clock));start_strings.append(clock)
  need(matches>0,'every file explicitly annotated; absence never background')
  need(starts and len(set(starts))==1,'unique registration start')
  # Do not silently reconcile original clocks if they disagree.
  discrepancy=starts[0]!=seconds(h['registration_clock'])
  if discrepancy:issues.append({'path':path,'issue':'EDF registration clock differs from annotation registration clock','summary_clock':start_strings[0],'header_clock':h['registration_clock'],'resolution_status':'unresolved'})
  pairs=sorted([list(x) for x in _loadSeizures(str(source/path))]);last=0
  for a,b in pairs:need(a==int(a) and b==int(b) and 0<=a<b<=h['duration_seconds'] and a>=last,'valid integral nonoverlapping in-record source events');last=b
  clock_record={'schema':'siena_clock_record_v2','path':path,'source_version':'1.0.0','source_sha256':row['source_sha256'],'header_sha256':row['sha256'],'annotation_sha256':whitelist['summary_sha256'],'parser_sha256':PARSER_SHA,'summary_clock':start_strings[0],'header_clock':h['registration_clock'],'duration_seconds':h['duration_seconds'],'source_events':pairs,'C2_candidate':scientific.shifted_clock_candidate(pairs,start_strings[0],h['registration_clock'],h['duration_seconds']),'discrepancy':discrepancy,'resolution':{'status':'unresolved','selected_origin':None,'evidence_sha256':None,'authority_status':'unissued'}}
  scientific.validate_clock_record(clock_record)
  events[path]={'events':pairs,'summary_sha256':whitelist['summary_sha256'],'clock_record':clock_record,'label_profile':'C1_source_parser','target_definition':'T1_pinned_parser_intervals'}
  rows.append({'path':path,'patient':patient,'url':'https://physionet.org/files/siena-scalp-eeg/1.0.0/'+path,'bytes':row['source_bytes'],'sha256':row['source_sha256'],'header':h,'header_sha256':row['sha256'],'annotation_evidence':'pinned_author_clock_functions','release_whitelist':whitelist})
 need(len(rows)==41 and len({r['path'] for r in rows})==41 and {r['patient'] for r in rows}==set(whitelists) and len(events)==41 and sum(len(r['events']) for r in events.values())==47,'complete14/41/47 source metadata')
 whitelist_identity=scientific.digest({'schema':release_whitelists['schema'],'subjects':[whitelists[p] for p in sorted(whitelists)]})
 return {'schema':'siena_source_map_v2','version':'1.0.0','records':rows,'scientific_profile':selected_profile,'release_whitelists_sha256':whitelist_identity,'clock_issues':issues,'all_EEG_samples_locally_present':False,'source_qualification_issued':False}, {'schema':'siena_annotation_map_v2','records':events,'clock_qualification_issued':False}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('source','release-whitelists','scientific-profile','output'):p.add_argument('--'+n,type=Path,required=True)
 for n in ('release-whitelists-sha256','scientific-profile-sha256'):p.add_argument('--'+n,required=True)
 a=p.parse_args();need(not a.output.exists(),'fresh metadata output')
 maps,annotations=build(a.source,io.strict(io.read(a.release_whitelists,1000000,a.release_whitelists_sha256)),io.strict(io.read(a.scientific_profile,100000,a.scientific_profile_sha256)))
 a.output.mkdir(mode=0o700);io.write(a.output/'SOURCE_MAP.json',maps);io.write(a.output/'SOURCE_ANNOTATIONS.json',annotations)
 print(json.dumps({'files':41,'people':14,'annotations':47,'source_bytes':sum(x['bytes'] for x in maps['records']),'observed_seconds':sum(x['header']['duration_seconds'] for x in maps['records']),'clock_issue_count':len(maps['clock_issues'])}))
