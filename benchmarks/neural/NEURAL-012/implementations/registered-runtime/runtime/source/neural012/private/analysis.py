"""Full CHB→Siena descriptive reconstruction, frozen prediction evidence only."""
import hashlib,math,re
import io_contract as io
import event_protocol as event
from vendor.analysis_core import paired,numeric_error,false_alarms
from scientific_contract import validate_profile,profile_sha256
from protocol_policy import validate_comparison
from phase_provenance import validate_evidence
ARMS=('native','harmonized','normalized','timing')
METRICS=('event_f1','event_sensitivity','false_alarms_per_24_observed_hours')
SHA=re.compile(r'[0-9a-f]{64}\Z')

def interval_list(value,duration):
 io.need(type(value)is list and len(value)<=duration,'bounded event array');last=0
 for p in value:
  io.need(type(p)is list and len(p)==2 and all(type(x)in(int,float) and 0<=x<=duration for x in p),'finite bounded endpoints')
  a,b=p;io.need(a<b and a>=last and all(x==int(x) for x in p),'integral nonoverlapping source intervals');last=b
 return value

def panel(value):
 io.fields(value,['schema_version','task_id','records','scientific_profile','source_qualification_sha256']);io.need(type(value['schema_version'])is int and value['schema_version']==2 and value['task_id']==io.TASK,'exact V4 panel/task')
 validate_profile(value['scientific_profile'])
 io.need(type(value['source_qualification_sha256'])is str and SHA.fullmatch(value['source_qualification_sha256']),'source qualification identity is a declaration, not an issuer')
 rows=value['records'];io.need(type(rows)is list and len(rows)==727,'all727 recordings');out={};people={'CHB':set(),'Siena':set()};counts={'CHB':0,'Siena':0}
 for row in rows:
  io.fields(row,['recording_id','patient_id','cohort','duration_seconds','montage_sha256','signal'])
  rid,pid,c,d=row['recording_id'],row['patient_id'],row['cohort'],row['duration_seconds']
  io.need(type(rid)is str and io.ID.fullmatch(rid) and rid not in out and type(pid)is str and io.ID.fullmatch(pid) and c in people,'unique identity/cohort')
  io.need(type(d)is int and 0<d<=86400 and type(row['montage_sha256'])is str and SHA.fullmatch(row['montage_sha256']),'duration/montage')
  pin=row['signal'];io.fields(pin,['file','bytes','sha256']);io.need(pin['file']=='signals/'+rid+'.h5' and type(pin['bytes'])is int and 0<pin['bytes']<10000000000 and type(pin['sha256'])is str and SHA.fullmatch(pin['sha256']),'target-free signal binding')
  out[rid]=row;people[c].add(pid);counts[c]+=1
 io.need(counts=={'CHB':686,'Siena':41} and len(people['CHB'])==23 and len(people['Siena'])==14 and people['CHB'].isdisjoint(people['Siena']),'full independent cohorts, no patientpairing')
 io.need(list(out)==sorted(out),'canonical prepared-panel record order for exact packet lineage')
 io.need(sum(x['duration_seconds'] for x in rows)<=10000000,'bounded observed support');return out

def admit_stream(value,records):
 io.fields(value,['schema_version','task_id','arm','records']);io.need(value['schema_version']==1 and type(value['schema_version'])is int and value['task_id']==io.TASK and value['arm'] in ARMS,'stream identity')
 rows=value['records'];io.need(type(rows)is list and len(rows)==727,'whole727prediction stream');out={}
 for r in rows:
  io.fields(r,['recording_id','scores','events']);rid=r['recording_id'];io.need(type(rid)is str and rid in records and rid not in out and type(r['scores'])is list,'unique score stream')
  d=records[rid]['duration_seconds'];derived=event.from_scores(r['scores'],d);io.need(r['events']==derived,'fixed probability-to-event transformation');out[rid]=derived
 return out

def validate_packet(packet):
 io.fields(packet,['schema_version','task_id','seal_sha256','scientific_profile','source_qualification_sha256','execution_evidence','records']);io.need(type(packet['seal_sha256'])is str and SHA.fullmatch(packet['seal_sha256']),'frozen seal binding')
 base={'schema_version':packet['schema_version'],'task_id':packet['task_id'],'scientific_profile':packet['scientific_profile'],'source_qualification_sha256':packet['source_qualification_sha256'],'records':[{k:v for k,v in r.items() if k not in ('annotations','arms')} for r in packet['records']]};records=panel(base)
 evidence=packet['execution_evidence'];validate_evidence(evidence,hashlib.sha256(io.encoded(base)).hexdigest(),profile_sha256(packet['scientific_profile']))
 validate_comparison(evidence['comparison'])
 source_people={r['patient_id']for r in records.values()if r['cohort']=='CHB'}
 for arm in ARMS:
  io.need({r['held_source_patient']for r in evidence['lineages']if r['arm']==arm and r['held_source_patient']is not None}==source_people,'observed fold people match this exact full source panel')
 for row in packet['records']:
  io.fields(row,list(records[row['recording_id']])+['annotations','arms']);d=row['duration_seconds'];interval_list(row['annotations'],d);io.fields(row['arms'],ARMS)
  for arm in ARMS:
   interval_list(row['arms'][arm],d);io.need(row['arms'][arm]==event.canonical(row['arms'][arm],d),'canonical frozen arm events')
 return packet['records']

def mean_se(values):
 n=len(values);io.need(n>0,'supported metric');mean=math.fsum(values)/n;se=math.sqrt(math.fsum((x-mean)**2 for x in values)/(n*(n-1))) if n>1 else None
 return {'n':n,'mean':mean,'standard_error':se}

def reconstruct(packet):
 rows=validate_packet(packet);groups={'CHB':{},'Siena':{}};false=[]
 for row in rows:
  c,pid,d=row['cohort'],row['patient_id'],row['duration_seconds'];p=groups[c].setdefault(pid,{a:[] for a in ARMS})
  for arm in ARMS:
   p[arm].append(event.count_events(row['annotations'],row['arms'][arm],d))
   if c=='Siena':false.append({'recording_id':row['recording_id'],'arm':arm,'intervals':false_alarms(row['annotations'],row['arms'][arm],d)})
 people={c:{pid:{a:event.summarize(counts) for a,counts in arms.items()} for pid,arms in sorted(p.items())} for c,p in groups.items()}
 io.need(all(arms['native']['reference_events']>0 for people0 in people.values() for arms in people0.values()),'every source patient has source seizures')
 macros={c:{a:{m:mean_se([p[a][m] for p in people[c].values()]) for m in METRICS} for a in ARMS} for c in groups}
 contrasts={}
 for a,b in [('harmonized','native'),('normalized','harmonized'),('harmonized','timing')]:
  contrasts[a+'_minus_'+b]={m:paired([p[a][m]-p[b][m] for p in people['Siena'].values()]) for m in METRICS}
 shifts={}
 for a in ARMS:
  shifts[a]={}
  for m in METRICS:
   source,target=macros['CHB'][a][m],macros['Siena'][a][m]
   shifts[a][m]={'source_n':23,'target_n':14,'target_minus_source_mean':target['mean']-source['mean'],'descriptive_standard_error':math.hypot(target['standard_error'],source['standard_error']),'paired_people':False}
 return {'patients':people,'cohort_macros':macros,'target_paired_contrasts':contrasts,'unpaired_cohort_shifts':shifts,'target_false_alarm_localization':sorted(false,key=lambda x:(x['recording_id'],ARMS.index(x['arm']))),'recordings':727,'biological_patients':37,'observed_seconds':sum(r['duration_seconds'] for r in rows),'causal_or_clinical_utility_established':False,'interpretation':{'temporal_mode':'offline_transductive','label_profile':packet['scientific_profile']['label_profile'],'comparison_mode':packet['execution_evidence']['comparison']['mode'],'uncertainty':'descriptive_conditional_on_shared_fitted_models','semantic_training_use_verified':False,'scientifically_qualified':False}}

def detector_outcomes(packet):
 """Prespecified performance endpoints of frozen streams, separate from report accuracy."""
 report=reconstruct(packet)
 return {'task_id':io.TASK,'outcome_kind':'frozen_detector_performance','primary_endpoint':'Siena_equal_person_event_f1','primary_by_arm':{a:report['cohort_macros']['Siena'][a]['event_f1']for a in ARMS},'secondary_by_arm':{a:{m:report['cohort_macros']['Siena'][a][m]for m in METRICS[1:]}for a in ARMS},'target_paired_contrasts':report['target_paired_contrasts'],'unpaired_cohort_shifts':report['unpaired_cohort_shifts'],'recordings':727,'biological_patients':37,'scientific_profile_sha256':profile_sha256(packet['scientific_profile']),'interpretation':report['interpretation'],'frontier_improvement_established':False}

def grade(packet,input_sha,submission):
 io.fields(submission,['schema_version','task_id','input_sha256','report']);io.need(type(submission['schema_version'])is int and submission['schema_version']==1 and submission['task_id']==io.TASK and submission['input_sha256']==input_sha,'exact analysis input binding')
 expected=reconstruct(packet)
 def support(a,e,key=''):
  if key in ('source_n','target_n','recordings','biological_patients','n','observed_seconds'):io.need(type(a)is int and a==e,'exact integer support')
  if type(e)is dict:
   io.fields(a,e)
   for k in e:support(a[k],e[k],k)
  elif type(e)is list:
   io.need(type(a)is list and len(a)==len(e),'complete support list')
   for x,y in zip(a,e):support(x,y)
 support(submission['report'],expected)
 error=numeric_error(submission['report'],expected)
 return {'task_id':io.TASK,'outcome_kind':'analysis_reconstruction','primary_metric':'maximum_scaled_reconstruction_error','error':error,'lower_is_better':True,'within_numerical_tolerance':error<=1e-8,'scientific_improvement_proven':False,'detector_competence_measured_by_this_grade':False}
