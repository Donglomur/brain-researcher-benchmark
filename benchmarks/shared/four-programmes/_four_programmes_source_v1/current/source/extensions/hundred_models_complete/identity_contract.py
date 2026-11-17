"""Exact twelve-field v3 subject and later v4 attestation/authority joins.

Pure typed identity checks do not mint independent root/worker authority.
The actual channel consumer and source-owned issuer must use these checks.
"""
import hashlib,json
from four_programmes.common import need,integer,pin,closed,same,bounded_size
from four_programmes.schema import check
from .fixed_tables import SUBJECT_SCHEMA,ISSUANCE_SCHEMA
from .reservations import ReservationPlan

FIELDS=('campaign_id','stage','sequence','reservation_plan','reservation_row','original_authority',
        'source_manifest','scope','inputs','plan','submission','root_issuer_source')
DOMAIN=b'hundred-models-invocation-subject-v3\n'

def scalars(value,depth=0):
 need(depth<=64,'bounded fixed original schema depth')
 if value is None or type(value)is bool:return
 if type(value)is int:need(0<=value<=9007199254740991,'bounded exact integer');return
 if type(value)is str:
  need(all(not 0xd800<=ord(c)<=0xdfff for c in value),'Unicode scalar codepoints only');return
 if type(value)is dict:
  need(all(type(k)is str for k in value),'literal string keys')
  for k,v in value.items():scalars(k,depth+1);scalars(v,depth+1)
  return
 if type(value)is list:
  for v in value:scalars(v,depth+1)
  return
 need(False,'no floats, custom values or implicit conversions in identity records')

def canonical(value):
 scalars(value)
 return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('utf8')

def typed(value,name,*,family='subject'):
 table=SUBJECT_SCHEMA if family=='subject'else ISSUANCE_SCHEMA
 scalars(value);check(value,{'$ref':'#/$defs/'+name,'$defs':table['$defs']})
 def paths(x):
  if type(x)is dict:
   if set(x)=={'path','bytes','sha256'}:
    p=x['path'];need(0<len(p)<=2048 and not p.startswith('/') and '\\'not in p and
     all(ord(c)>=32 and ord(c)!=127 for c in p) and all(t not in ('','.','..')for t in p.split('/')),'exact original relative descriptor namespace')
   for v in x.values():paths(v)
  elif type(x)is list:
   for v in x:paths(v)
 paths(value)
 if 'campaign_id'in value:need(all(ord(c)>=32 and ord(c)!=127 for c in value['campaign_id']),'bounded plain campaign spelling')
 return value

def decode(raw,name,*,cap,meter,family='subject'):
 need(type(raw)is bytes and len(raw)<=cap,'prebounded complete original metadata bytes')
 meter.charge('work',len(raw)*64+4096)
 def pairs(items):
  obj={}
  for k,v in items:need(k not in obj,'duplicate key');obj[k]=v
  return obj
 def no_float(x):need(False,'no floating wire encoding')
 value=json.loads(raw,object_pairs_hook=pairs,parse_float=no_float,parse_constant=no_float)
 typed(value,name,family=family);need(raw==canonical(value),'one canonical UTF8 LF record, no alternate whitespace/BOM')
 return value

def material(invocation,plan):
 need(type(plan)is ReservationPlan,'actual complete original plan')
 closed(invocation,FIELDS);body={'schema':'hundred_models_invocation_subject_material_v3',**invocation}
 typed(body,'SubjectMaterial');t=plan.stage(body['sequence'])
 need(body['campaign_id']==plan.body['campaign_id'] and body['reservation_plan']==plan.pin and
      body['reservation_row']==t['row'] and body['stage']==t['stage'] and
      body['source_manifest']==plan.body['source_manifest'] and body['root_issuer_source']==plan.body['root_issuer_source'],
      'same exact full root/source/plan/stage identity')
 need((body['submission'] is None)==(body['stage']=='reference'),'reference null and actual A/B original submission identity')
 return body

def subject(invocation,plan):
 m=material(invocation,plan)
 return {'schema':'hundred_models_invocation_subject_v3','material':m,'material_hash':hashlib.sha256(DOMAIN+canonical(m)).hexdigest()}

def validate_subject(body,*,invocation,plan):
 typed(body,'Subject');expected=subject(invocation,plan)
 need(canonical(body)==canonical(expected),'all twelve original fields and exact domain-separated material hash')
 return body

def validate_chain_records(*,invocation,plan,subject_body,subject_pin,selection,selection_pin,authority,authority_pin):
 validate_subject(subject_body,invocation=invocation,plan=plan)
 for body,d,name in [(subject_body,subject_pin,'Subject'),(selection,selection_pin,'RootSelection'),(authority,authority_pin,'InvocationAuthority')]:
  typed(body,name);typed(d,'Descriptor');need(pin(canonical(body))=={k:d[k]for k in ('bytes','sha256')},'captured exact original identity '+name)
 need({k:authority[k]for k in FIELDS}==invocation and authority['pre_run_subject']==subject_pin and
      authority['root_selection']==selection_pin,'authority exact twelve original fields and earlier ancestors')
 t=plan.stage(invocation['sequence']);h=plan.rows[t['issuer_host_row']];a=h['issuance'];win=a['window']
 need(selection['subject']==subject_pin and selection['root_issuer_source']==plan.body['root_issuer_source'] and
      selection['issuer_qualification']==a['issuer_qualification'] and selection['source_admission']==a['source_admission'] and
      selection['clock_binding']==plan.body['clock_binding'] and selection['reservation_plan']==plan.pin and
      selection['issuance_slot']==a['slot'] and selection['host_row']==h['id'] and
      selection['adapter_reservation_id']==h['adapter_reservation_id'] and selection['issuer_window']==win,
      'earlier exact issuer row/slot/source/qualification/window')
 need(win['start_ns']<=selection['issued_monotonic_ns']<win['stop_ns'],'original RootSelection publication inside selected issuer interval')
 # These are semantic comparisons of exact already captured records, not claims
 # that descriptors alone establish source acceptance or physical observation.
 return authority

def validate_chain(*,received_ns,**records):
 """C consumer additionally requires its actual receive clock, before I.stop."""
 authority=validate_chain_records(**records);plan=records['plan'];inv=records['invocation']
 t=plan.stage(inv['sequence']);win=plan.rows[t['issuer_host_row']]['issuance']['window']
 integer(received_ns,1)
 need(records['selection']['issued_monotonic_ns']<=received_ns<win['stop_ns'],'actual complete C receipt inside original issuer interval')
 return authority
