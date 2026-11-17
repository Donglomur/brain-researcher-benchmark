"""Classify actual selected source identities, never native/scientific qualification."""
import hashlib,re
from pathlib import Path
import io_contract as io

ARMS=('native','harmonized','normalized','timing')
SHA=re.compile(r'[0-9a-f]{64}\Z')
REFERENCE_FILES=frozenset(('reference.py','control_recipe.py','physical_io.py','case_contract.py','event_protocol.py','scientific_contract.py','io_contract.py'))

def protocol_sources():
 root=Path(__file__).resolve().parents[1]/'public'
 raw=io.read(root/'PROTOCOL.json',100000)
 value=io.strict(raw)
 io.need(value['schema']=='neural012_frozen_protocol_v5' and value['task_id']==io.TASK,'selected trusted-host/local-reader protocol')
 pins=value['source_sha256'];io.fields(pins,REFERENCE_FILES);rows=[]
 for name in sorted(REFERENCE_FILES):
  pin=pins[name];io.need(type(pin)is str and SHA.fullmatch(pin),'source pin')
  body=io.read(root/name,100000,pin)
  rows.append({'path':name,'bytes':len(body),'sha256':pin})
 return value,hashlib.sha256(raw).hexdigest(),rows

def controlled_programme():
 _,_,rows=protocol_sources()
 return {'schema':'neural012_selected_programme_v3','entrypoint':'reference.py','files':rows}

def is_reference(value,rows):
 io.fields(value,['schema','entrypoint','files'])
 io.need(value['schema']=='neural012_selected_programme_v3' and type(value['files'])is list and value['files'],'explicit V3 programme')
 names=set()
 for row in value['files']:
  io.fields(row,['path','bytes','sha256'])
  io.need(type(row['path'])is str and row['path']not in names and type(row['bytes'])is int and 0<row['bytes']<=1048576 and type(row['sha256'])is str and SHA.fullmatch(row['sha256']),'unique bounded programme source rows')
  names.add(row['path'])
 return value['entrypoint']=='reference.py' and sorted(value['files'],key=lambda r:r['path'])==rows

def validate_comparison(value):
 io.fields(value,['schema','mode','arm_modes','timing','named_method_source_identity_verified','runtime_qualified','protocol_sha256'])
 io.need(value['schema']=='neural012_comparison_source_identity_v1' and type(value['protocol_sha256'])is str and SHA.fullmatch(value['protocol_sha256']),'comparison source identity')
 io.fields(value['arm_modes'],ARMS)
 io.need(all(x in ('audited_fixed_reference','arbitrary_program')for x in value['arm_modes'].values()),'comparison arm modes')
 io.need(value['arm_modes']['timing']=='audited_fixed_reference' and value['timing']=='fixed_elapsed_minute_reference','exact source-audited timing comparator')
 fixed=all(x=='audited_fixed_reference'for x in value['arm_modes'].values())
 io.need(value['mode']==('controlled_reference_preprocessing'if fixed else'bundled_candidate_method') and type(value['named_method_source_identity_verified'])is bool and value['named_method_source_identity_verified']==fixed,'method claim follows all selected sources')
 io.need(value['runtime_qualified']is False,'source equality never qualifies native execution')
 return value

def classify_programmes(programmes):
 io.fields(programmes,ARMS)
 _,protocol_pin,rows=protocol_sources();modes={}
 for arm,value in programmes.items():
  io.fields(value,['manifest_raw','root'])
  modes[arm]='audited_fixed_reference'if is_reference(io.strict(value['manifest_raw']),rows)else'arbitrary_program'
 io.need(modes['timing']=='audited_fixed_reference','O1 timing must use exact audited reference source; arbitrary metadata-only code is a different control')
 fixed=all(v=='audited_fixed_reference'for v in modes.values())
 return validate_comparison({'schema':'neural012_comparison_source_identity_v1','mode':'controlled_reference_preprocessing'if fixed else'bundled_candidate_method','arm_modes':modes,'timing':'fixed_elapsed_minute_reference','named_method_source_identity_verified':fixed,'runtime_qualified':False,'protocol_sha256':protocol_pin})
