"""Complete keyed product admission, outside every submitted process."""
from pathlib import Path
from .lifecycle import guard,current,LifecycleError
from .common import require,exact_keys,finite,identity,load,write_new,copy_new,seal_tree,verify_tree,relative
from .contracts import expected_rows

DISPOSITIONS={'value','declared_fit_failure','declared_prediction_failure','declared_undefined','declared_inapplicable'}
def validate_value(family,value,request):
 if family=='I_NEURAL':finite(value)
 elif family=='I_WAIT':require(0<=finite(value)<=100,'wait domain')
 elif family=='I_REWARD':require(type(value)is int and value in(1,2,3,4,5),'five-class prediction')
 elif family in('I_SIM_ATI','I_REAL_ATI'):
  exact_keys(value,('coordinate_map_id','u','v','ratio_disposition','fitted_state_id'));require(isinstance(value['coordinate_map_id'],str)and value['coordinate_map_id'],'ATI coordinate map');require(isinstance(value['fitted_state_id'],str)and value['fitted_state_id'],'ATI fitted state provenance')
  require(value['ratio_disposition']in('defined','zero_denominator'),'ATI disposition')
  require(finite(value['u'])>=0 and finite(value['v'])>=0,'nonnegative norm')
  require((value['u']+value['v']==0)==(value['ratio_disposition']=='zero_denominator'),'ATI denominator disposition')
 elif family=='I_ASSOCIATION':
  exact_keys(value,('latent','coordinate_map_id','null_specification_id'));finite(value['latent']);require(value['coordinate_map_id']and value['null_specification_id'],'association estimator provenance')
 else:
  exact_keys(value,('components','source_policy','methods_conformance','role_dispositions','attempts'))
  require(value['source_policy']=='native_source_reproduction','corrected product cannot replace native')
  require(isinstance(value['methods_conformance'],list)and isinstance(value['attempts'],list),'complete conformance/attempt table')
  require(isinstance(value['role_dispositions'],list)and set(x['role_id']for x in value['role_dispositions'])==set(request['role_ids']),'native complete role support')
  expected={x['component_id']:x for x in request['component_roster']};seen=set()
  for comp in value['components']:
   exact_keys(comp,('component_id','unit','axes','data','disposition','provenance'))
   key=comp['component_id'];require(key in expected and key not in seen,'native component roster');seen.add(key);e=expected[key]
   require(comp['unit']==e['unit']and comp['axes']==e['axes'],'native component geometry/units')
   require(comp['disposition']in('defined','native_nonfinite','scientifically_undefined','provenance_only'),'component disposition')
   require(isinstance(comp['provenance'],dict)and comp['provenance'],'component lineage')
   if comp['disposition']=='defined':
    require(isinstance(comp['data'],list),'native flat data vector');size=1
    for axis in comp['axes']:require(isinstance(axis['labels'],list),'axis labels');size*=len(axis['labels'])
    require(len(comp['data'])==size,'native component length')
    for item in comp['data']:finite(item)
   elif comp['disposition']=='native_nonfinite':
    size=1
    for axis in comp['axes']:size*=len(axis['labels'])
    require(isinstance(comp['data'],list)and len(comp['data'])==size,'complete native mixed nonfinite vector')
    require(any(isinstance(x,str)for x in comp['data']),'nonfinite vector requires a tagged value')
    for item in comp['data']:
     if isinstance(item,str):require(item in('nan','positive_infinity','negative_infinity'),'tagged native nonfinite')
     else:finite(item)
   elif comp['disposition']=='scientifically_undefined':require(comp['data']is None,'undefined cannot carry value')
   else:require(isinstance(comp['data'],dict),'provenance product')
  require(seen==set(expected),'missing native component')
 return value
def collect(plan,outputs,receipt_chain,root):
 """Record complete expected rows even when candidate data is missing or invalid."""
 guard('collector entry');root=Path(root);from .common import make_dir;make_dir(root);expected=expected_rows(plan);require(len(set(expected))==len(expected),'operator duplicate support')
 requests={(f,r['query_id']):r for f,rows in plan['public_universes'].items()for r in rows};requests.update({(r['family_id'],r['obligation_id']):r for r in plan['native_requests']})
 rows={};failures=[];source_id=receipt_chain['source_id'];model_id=receipt_chain['model_id']
 for out,observation in outputs:
  require(observation['status']=='completed_naturally'and observation['original_returncode']==0 and not observation['forced_stop'],'failed process cannot supply valid products')
  verify_tree(out,observation['output_seal'],plan['budget']['file_count'],plan['budget']['output_bytes'])
  response=load(Path(out)/'response.json',plan['budget']['output_bytes'])
  exact_keys(response,('schema','request_id','source_id','model_id','rows'));require(response['schema']=='ofc-response-v1','response schema')
  require(response['request_id']==observation['request_id']and response['source_id']==source_id and response['model_id']==model_id,'response source/model/request binding')
  for row in response['rows']:
   guard('collector row admission')
   try:
    exact_keys(row,('family_id','query_id','disposition','value','reason','watermark'))
    key=(row['family_id'],row['query_id']);require(key in requests and key in expected,'unknown output key');require(key not in rows,'duplicate output key');require(row['disposition']in DISPOSITIONS,'candidate disposition')
    if row['family_id'].startswith('I_'):require(row['watermark']==requests[key]['cutoff'],'host watermark mismatch')
    if row['disposition']=='value':validate_value(row['family_id'],row['value'],requests[key]);require(row['reason']is None,'defined value cannot carry failure')
    else:require(row['value']is None and isinstance(row['reason'],str)and row['reason'],'tagged failure requires null and reason')
    if row['disposition']=='declared_inapplicable':require(row['family_id']in('I_SIM_ATI','I_REAL_ATI'),'inapplicability only ATI')
    rows[key]=row
   except LifecycleError:raise
   except ValueError as e:
    key=(row.get('family_id'),row.get('query_id'))if isinstance(row,dict)else(None,None);failures.append({'key':list(key),'reason':str(e)})
 for key in expected:
  if key not in rows:rows[key]={'family_id':key[0],'query_id':key[1],'disposition':'missing','value':None,'reason':'required output absent or invalid','watermark':None}
 # Unknown/duplicate output invalidates its family; unidentifiable failures invalidate all active families.
 invalid_families=set()
 for f in failures:
  if f['key'][0]in{a for a,b in expected}:invalid_families.add(f['key'][0])
  else:invalid_families.update(a for a,b in expected)
 record={'schema':'ofc-sealed-submission-v1','task_id':plan['task_id'],'condition':plan['condition'],'plan_id':identity(plan),'public_universe_id':identity(plan['public_universes']),'private_commitment':plan['protected_commitment'],'policy_id':plan['policy_id'],'receipt_chain':receipt_chain,'expected_rows':[list(k)for k in expected],'rows':[rows[k]for k in expected],'invalid_families':sorted(invalid_families),'collector_failures':failures,'complete_public_support':all(rows[k]['disposition']!='missing'for k in expected),'private_grade_called':False}
 pin=write_new(root/'submission.json',record);return record,{'path':str(root/'submission.json'),**pin}
