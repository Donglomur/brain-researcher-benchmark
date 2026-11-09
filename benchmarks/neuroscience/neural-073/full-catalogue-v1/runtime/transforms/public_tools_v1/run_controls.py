"""Single bounded invented public DTO equivalence/redaction control invocation."""
from pathlib import Path
from types import MappingProxyType
import hashlib,importlib.util,json,sys,traceback
HERE=Path(__file__).resolve().parent;T=HERE.parent
source_pins=[]
for path in [T/'__init__.py',T/'numeric.py',T/'dependency.py',T/'NUMPY_API_CONTRACT.json',HERE/'__init__.py',HERE/'projection.py']:
 b=path.read_bytes();source_pins.append({'relative':str(path.relative_to(T)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
spec=importlib.util.spec_from_file_location('n073_public_control_package',T/'__init__.py',submodule_search_locations=[str(T)])
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
from n073_public_control_package.dependency import numpy_api
from n073_public_control_package.public_tools_v1 import project_transform,apply_transform,from_dict,from_json,parameter_digest
from n073_public_control_package.public_tools_v1.projection import _decode_array
np=numpy_api();L=m.NumericLimits(300000,16777216);results=[]
def check(name,value):
 if not bool(value):raise AssertionError(name)
 results.append({'name':name,'passed':True})
def reject(name,fn):
 try:fn()
 except m.NumericalError as e:results.append({'name':name,'passed':True,'refusal':str(e)})
 else:raise AssertionError(name+' failed to refuse')
def freeze(x):return np.frombuffer(x.tobytes(order='C'),dtype=np.float64).reshape(x.shape)
private_meta=MappingProxyType({'fit_record_ids':('PRIVATE_FIT_ID_MARKER',),'dependency_key':'PRIVATE_LINEAGE_MARKER','source_path':'PRIVATE_SOURCE_PATH_MARKER'})
try:
 # Invented fitted parameters, not the output of any authentic or256-PCA fit.
 # The sole dense temporary and immutable parameter body each total524288B.
 raw=np.eye(256,dtype=np.float64);raw[-1,-1]=0
 components=freeze(raw);del raw
 nmean=freeze(np.arange(256,dtype=np.float64)/1024)
 nscale=freeze(np.ones(256,dtype=np.float64)*2)
 pcamean=freeze(np.ones(256,dtype=np.float64)/8)
 cmean=freeze(np.zeros(105,dtype=np.float64));cscale=freeze(np.ones(105,dtype=np.float64)*3)
 ns=m.Scaler(nmean,nscale,private_meta);cs=m.Scaler(cmean,cscale,private_meta)
 evraw=np.ones(256,dtype=np.float64);evraw[-1]=0;ev=freeze(evraw);del evraw
 pc=m.PCA(pcamean,components,ev,private_meta)
 sm64=freeze(np.zeros(64,dtype=np.float64));ss64=freeze(np.ones(64,dtype=np.float64)*2)
 sm256=freeze(np.zeros(256,dtype=np.float64));ss256=freeze(np.ones(256,dtype=np.float64)*2)
 s64=m.Scaler(sm64,ss64,private_meta);s256=m.Scaler(sm256,ss256,private_meta)
 bank=m.ViewBank('NC','raw',(4,4,16),ns,cs,pc,s64,s256,private_meta)
 x=(np.arange(256,dtype=np.float64)/64).reshape(1,256);c=np.arange(105,dtype=np.float64).reshape(1,105)/50
 p64=project_transform(bank,'rbf_ovr_svm',pca_rank=64,limits=L)
 check('PCA64_exact_selected_parameters',p64.parameters['pca_components'].shape==(256,64) and set(p64.parameters)=={'n_mean','n_scale','pca_mean','pca_components','score_mean','score_scale','c_mean','c_scale'})
 check('PCA64_public_private_equivalence',np.allclose(apply_transform(p64,x,c,limits=L),m.transform_view(bank,x,c,pca_rank=64,limits=L),rtol=0,atol=1e-14))
 check('PCA64_no_unused_backing_columns',p64.parameters['pca_components'].nbytes==131072 and len(p64.parameters['pca_components'].base.base)==131072)
 p256=project_transform(bank,'extra_trees',pca_rank=256,limits=L)
 check('PCA256_public_private_equivalence',np.allclose(apply_transform(p256,x,c,limits=L),m.transform_view(bank,x,c,pca_rank=256,limits=L),rtol=0,atol=1e-14))
 check('PCA256_zero_component_convention',p256.algorithm['pca_zero_columns']==(255,) and apply_transform(p256,x,c,limits=L)[0,255]==0)
 check('full_used_immutable_backing_may_be_shared',np.shares_memory(p256.parameters['pca_components'],components))
 # Full-coordinate projection must not traverse any unused PCA child.
 class Trap:
  def __getattribute__(self,name):raise AssertionError('unused PCA was read')
 fullbank=m.ViewBank('NC','raw',(4,4,16),ns,cs,Trap(),Trap(),Trap(),private_meta)
 pf=project_transform(fullbank,'ridge',limits=L)
 check('full_family_exports_only_scalers',set(pf.parameters)=={'n_mean','n_scale','c_mean','c_scale'} and 'pca_rank' not in pf.algorithm)
 check('full_family_public_private_equivalence',np.allclose(apply_transform(pf,x,c,limits=L),m.transform_view(bank,x,c,limits=L),rtol=0,atol=1e-14))
 linear=project_transform(fullbank,'linear_ovr_svm',limits=L)
 check('linear_full_family_equivalence',np.allclose(apply_transform(linear,x,c,limits=L),apply_transform(pf,x,c,limits=L),rtol=0,atol=1e-14))
 rmsbank=m.ViewBank('N','rms',(4,4,16),ns,None,Trap(),Trap(),Trap(),private_meta)
 centroid=project_transform(rmsbank,'centroid',limits=L)
 check('centroid_RMS_public_private_equivalence',np.allclose(apply_transform(centroid,x,None,limits=L),m.transform_view(rmsbank,x,None,limits=L),rtol=0,atol=1e-14))
 conly=m.ViewBank('C',None,None,None,cs,None,None,None,private_meta)
 cp=project_transform(conly,'extra_trees',limits=L)
 check('C_only_no_neural_fields',set(cp.algorithm)=={'view','reference_family'} and set(cp.parameters)=={'c_mean','c_scale'})
 check('C_only_public_private_equivalence',np.allclose(apply_transform(cp,None,c,limits=L),m.transform_view(conly,None,c,limits=L),rtol=0,atol=1e-14))
 for dto in [pf,cp,centroid]:
  plain=dto.to_dict(limits=L);text=json.dumps(plain,sort_keys=True,allow_nan=False)
  check('no_private_metadata_'+dto.algorithm['reference_family'],all(marker not in text for marker in ['PRIVATE_FIT_ID_MARKER','PRIVATE_LINEAGE_MARKER','PRIVATE_SOURCE_PATH_MARKER','fit_record_ids','dependency_key','source_path']))
  digest=parameter_digest(dto,limits=L)
  again=from_json(text,limits=L,expected_digest=digest,max_bytes=65536)
  check('bounded_roundtrip_'+dto.algorithm['reference_family'],parameter_digest(again,limits=L)==digest)
 digest=parameter_digest(cp,limits=L);plain=cp.to_dict(limits=L)
 bad=json.loads(json.dumps(plain));bad['algorithm']['fit_record_ids']=['PRIVATE_FIT_ID_MARKER']
 reject('hidden_metadata_tamper_rejected',lambda:from_dict(bad,limits=L,expected_digest=digest))
 bad=json.loads(json.dumps(plain));bad['parameters']['c_mean']['data'][0]+=1
 reject('numeric_parameter_tamper_rejected_by_external_pin',lambda:from_dict(bad,limits=L,expected_digest=digest))
 reject('duplicate_JSON_keys_rejected',lambda:from_json('{"schema":1,"schema":2}',limits=L,expected_digest=digest,max_bytes=100))
 reject('C_only_neural_call_rejected',lambda:apply_transform(cp,x,c,limits=L))
 reject('C_only_selected_PCA_rejected',lambda:project_transform(conly,'rbf_ovr_svm',pca_rank=64,limits=L))
 reject('unused_PCA_request_for_ridge_rejected',lambda:project_transform(fullbank,'ridge',pca_rank=64,limits=L))
 reject('small_serialization_budget_refuses_before_list_copy',lambda:p64.to_dict(limits=m.NumericLimits(10,128)))
 small=_decode_array({'shape':[2,2],'dtype':'float64','data':[1.,-2.,3.,4.]},(2,2),limits=L)
 check('generic_2D_codec_exact',np.array_equal(small,np.array([[1.,-2.],[3.,4.]],dtype=np.float64)))
 reject('generic_2D_codec_bad_extent',lambda:_decode_array({'shape':[2,2],'dtype':'float64','data':[1.]},(2,2),limits=L))
 status='PASS'
except Exception as e:
 status='FAIL';results.append({'name':'original_failure','type':type(e).__name__,'error':str(e),'traceback':traceback.format_exc()})
receipt={'schema':'n073_public_transform_invented_controls_v1','status':status,'source_pins_before_import':source_pins,'checks':results,'fixture_cumulative_charge':1400000,'prior_fixture_cumulative':1703936,'fixture_live_bound':4194304,'retained_numeric_array_files':0,'scope':'Invented fitted-parameter inference/DTO controls only. No authentic data, no full PCA fit or scientific model execution. Full256 serialization intentionally not materialized in this bounded control; generic2D codec and complete small-state roundtrips checked.','private_fixtures_are_not_training_admission':True}
(HERE/'CONTROL_RECEIPT_V1.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
print(json.dumps({'status':status,'checks':len(results)}))
if status!='PASS':print(json.dumps(results[-1]));raise SystemExit(1)
