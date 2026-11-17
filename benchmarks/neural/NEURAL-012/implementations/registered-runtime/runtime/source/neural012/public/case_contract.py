"""Closed phase-specific exposure and bounded JSON state; not execution authority."""
import hashlib,math,re
import io_contract as io
ARMS=('native','harmonized','normalized','timing')
ROW=('recording_id','patient_id','cohort','duration_seconds')
SHA=re.compile(r'[0-9a-f]{64}\Z')
MAX_STATE_DEPTH=256

def intervals(value,duration):
 io.need(type(value)is list and len(value)<=duration,'bounded training event list')
 end=0
 for pair in value:
  io.need(type(pair)is list and len(pair)==2 and all(type(x)in(int,float)and 0<=x<=duration and x==int(x)for x in pair),'finite integral event pair')
  a,b=pair;io.need(0<=a<b<=duration and a>=end,'ordered nonoverlapping events');end=b
 return value

def project_row(row,arm,events=None):
 io.need(arm in ARMS,'known arm')
 out={k:row[k]for k in ROW}
 if arm!='timing':
  out['montage_sha256']=row['montage_sha256'];out['signal']=dict(row['signal'])
 if events is not None:out['events']=[list(p)for p in events]
 return out

def phase_rows(case):
 return case['train']if case['phase']=='fit'else case['query']

def validate_case(case,phase=None):
 io.need(type(case)is dict and case.get('phase')in('fit','predict'),'known phase')
 actual=case['phase'];partition='train'if actual=='fit'else'query'
 fields=['schema_version','task_id','arm','phase','training_people',partition,'scientific_profile_sha256','supervisor_verified']
 if actual=='predict':fields.append('fit_case_sha256')
 io.fields(case,fields)
 io.need(type(case['schema_version'])is int and case['schema_version']==3 and case['task_id']==io.TASK,'versioned N012 phase case')
 io.need(phase is None or actual==phase,'required phase')
 arm=case['arm'];n=case['training_people']
 io.need(arm in ARMS and type(n)is int and n in(22,23)and case['supervisor_verified']is False,'case is not execution authority')
 io.need(type(case['scientific_profile_sha256'])is str and SHA.fullmatch(case['scientific_profile_sha256']),'selected scientific profile identity')
 if actual=='predict':io.need(type(case['fit_case_sha256'])is str and SHA.fullmatch(case['fit_case_sha256']),'exact matching fit-case digest')
 rows=case[partition];io.need(type(rows)is list and 0<len(rows)<=686,'bounded whole phase support')
 ids=set();people=set();duration=0
 for row in rows:
  keys=list(ROW)+([]if arm=='timing'else['montage_sha256','signal'])+(['events']if actual=='fit'else[])
  io.fields(row,keys);rid,pid,d=row['recording_id'],row['patient_id'],row['duration_seconds']
  io.need(type(rid)is str and io.ID.fullmatch(rid)and rid not in ids and type(pid)is str and io.ID.fullmatch(pid),'opaque unique record/person identities')
  expected='CHB'if actual=='fit'or n==22 else'Siena'
  io.need(row['cohort']==expected and type(d)is int and 0<d<=86400,'complete source cohort/duration')
  ids.add(rid);people.add(pid);duration+=d
  if actual=='fit':intervals(row['events'],d)
  if arm!='timing':
   io.need(type(row['montage_sha256'])is str and SHA.fullmatch(row['montage_sha256']),'physical montage binding')
   s=row['signal'];io.fields(s,['file','bytes','sha256'])
   io.need(s['file']=='signals/'+rid+'.h5'and type(s['bytes'])is int and 0<s['bytes']<10000000000 and type(s['sha256'])is str and SHA.fullmatch(s['sha256']),'exact signal descriptor')
 io.need(duration<=10000000,'bounded whole observed phase duration')
 if actual=='fit':
  io.need(len(people)==n and (len(rows)==686 if n==23 else len(rows)<686),'all declared training biological people')
 else:io.need((len(people)==1 if n==22 else len(people)==14 and len(rows)==41),'whole source-person or target-cohort query view')
 return case

def validate_phase_pair(fit,predict):
 """Host-only complete inverse; never expose this combined object to a program."""
 validate_case(fit,'fit');validate_case(predict,'predict')
 io.need(fit['arm']==predict['arm']and fit['training_people']==predict['training_people']and fit['scientific_profile_sha256']==predict['scientific_profile_sha256'],'same arm, training rule and scientific profile')
 io.need(hashlib.sha256(io.encoded(fit)).hexdigest()==predict['fit_case_sha256'],'exact fit-to-query binding')
 train,query=fit['train'],predict['query']
 io.need({r['recording_id']for r in train}.isdisjoint(r['recording_id']for r in query),'disjoint phase recording IDs')
 io.need({r['patient_id']for r in train}.isdisjoint(r['patient_id']for r in query),'disjoint biological people')
 io.need(len(train)+len(query)==(686 if fit['training_people']==22 else 727),'whole logical-job support')
 io.need(sum(r['duration_seconds']for r in train+query)<=10000000,'complete combined duration bound')
 return fit,predict

def validate_fit_limits(limits):
 """Runtime-selected state resources; authoring limits are not model limits."""
 io.fields(limits,['bytes','nodes','depth','string_bytes','key_bytes'])
 io.need(all(type(v)is int for v in limits.values()),'integer fitted-state resource limits')
 io.need(0<limits['bytes']<=io.MAX_JSON and 0<limits['nodes']<=io.MAX_JSON and 0<=limits['depth']<=MAX_STATE_DEPTH,'selected bounded JSON bytes/nodes/depth')
 io.need(0<=limits['string_bytes']<=limits['bytes']and 0<=limits['key_bytes']<=limits['bytes'],'selected JSON string/key byte bounds')
 return limits

def validate_fit_state(value,fit_case_sha256=None,arm=None,limits=None):
 """JSON data only: no harness pickle/import/eval. A candidate may ignore it."""
 limits=validate_fit_limits(limits)
 io.fields(value,['schema_version','task_id','arm','fit_case_sha256','training_use_declaration','state'])
 io.need(type(value['schema_version'])is int and value['schema_version']==1 and value['task_id']==io.TASK,'fitted artifact schema')
 io.need(value['arm']in ARMS and type(value['fit_case_sha256'])is str and SHA.fullmatch(value['fit_case_sha256']),'artifact arm/case binding')
 io.need(arm is None or value['arm']==arm,'artifact arm matches original fit')
 io.need(fit_case_sha256 is None or value['fit_case_sha256']==fit_case_sha256,'artifact belongs to original fit case')
 io.need(value['training_use_declaration']in('fit_attempted','no_fit'),'training declaration, not semantic proof')
 stack=[(value['state'],0)];seen=0
 while stack:
  item,depth=stack.pop();seen+=1
  io.need(seen<=limits['nodes']and depth<=limits['depth'],'bounded fitted-state JSON tree')
  if item is None or type(item)is bool:continue
  if type(item)is int:io.need(item.bit_length()<=limits['bytes']*4,'state integer fits selected byte bound');continue
  if type(item)is float:io.need(math.isfinite(item),'finite state number');continue
  if type(item)is str:io.need(len(item.encode('utf8'))<=limits['string_bytes'],'bounded state string');continue
  if type(item)is list:
   io.need(seen+len(stack)+len(item)<=limits['nodes'],'bounded state list');stack.extend((x,depth+1)for x in item);continue
  if type(item)is dict:
   io.need(seen+len(stack)+len(item)<=limits['nodes']and all(type(k)is str and len(k.encode('utf8'))<=limits['key_bytes']for k in item),'bounded JSON object keys');stack.extend((x,depth+1)for x in item.values());continue
  raise ValueError('state must contain only JSON data')
 io.need(len(io.encoded(value))<=limits['bytes'],'bounded immutable fit artifact bytes')
 return value
