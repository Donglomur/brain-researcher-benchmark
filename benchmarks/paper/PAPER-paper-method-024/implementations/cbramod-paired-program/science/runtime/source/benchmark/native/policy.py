"""Metadata-only admission for real CBraMod source dispatch; no scientific imports."""
import hashlib,json,math,re
from pathlib import Path

COMMIT='b9e961003214326972c567eff390e75b0287e32a'
DATASETS={
 'FACED':('faced','multiclass',9,32,10),
 'SEED-V':('seedv','multiclass',5,62,1),
 'PhysioNet-MI':('physio','multiclass',4,64,4),
 'SHU-MI':('shu','binary',2,32,4),
 'ISRUC':('isruc','multiclass',5,6,30),
 'CHB-MIT':('chb','binary',2,16,10),
 'BCIC2020-3':('speech','multiclass',5,64,3),
 'Mumtaz2016':('mumtaz','binary',2,19,5),
 'SEED-VIG':('seedvig','regression',1,17,8),
 'MentalArithmetic':('stress','binary',2,20,5),
 'TUEV':('tuev','multiclass',6,16,5),
 'TUAB':('tuab','binary',2,16,10),
 'BCIC-IV-2a':('bciciv2a','multiclass',4,22,4),
}
PRIMARY=tuple(DATASETS)[:12]
RECIPE={'epochs':50,'batch_size':64,'lr':0.0001,'weight_decay':0.05,
 'optimizer':'AdamW','clip_value':1,'dropout':0.1,'classifier':'all_patch_reps',
 'num_workers':16,'label_smoothing':0.1,'multi_lr':True,'frozen':False}
# These values are actual finetune_main defaults, not a claim about the five paper runs.
CENTRAL=('FACED','SEED-V','PhysioNet-MI','SHU-MI')

class MissingSource(ValueError):pass

def need(ok,msg):
 if not ok:raise ValueError(msg)
def exact(x,ks):need(type(x)is dict and set(x)==set(ks),'exact metadata fields: '+str(ks))
def sha(x):need(type(x)is str and re.fullmatch('[0-9a-f]{64}',x),'sha256')
def integer(x,lo,hi,name):need(type(x)is int and lo<=x<=hi,name)
def ident(x):need(type(x)is str and re.fullmatch('[A-Za-z0-9_.-]{1,200}',x),'opaque identity')
def encode(x):return(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def digest(x):return hashlib.sha256(encode(x)).hexdigest()
def relative(x):
 need(type(x)is str and re.fullmatch('[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*',x),'ordinary relative path')
 need('..'not in Path(x).parts and '.'not in Path(x).parts,'no relative escape')
 return x

def method_route(dataset,method):
 need(dataset in DATASETS,'declared full-scope dataset')
 if method=='CBraMod':return {'source':'official','pretrained':True,'dataset':dataset}
 if method=='CBraMod_pretraining_none' and dataset in CENTRAL:return {'source':'official','pretrained':False,'dataset':dataset}
 raise MissingSource('Exact selected executable source/recipe is missing for '+dataset+'/'+method+'; full panel remains required')

def split_descriptor(x,dataset,split):
 exact(x,('schema','dataset_id','split','prepared_root','source_keys','group_by_key','lineage_sha256','source_commit','official_manifest_sha256'))
 need(x['schema']=='cbramod_training_split_v1' and x['dataset_id']==dataset and x['split']==split,'TRAIN/validation descriptor identity')
 relative(x['prepared_root']);sha(x['lineage_sha256']);sha(x['official_manifest_sha256']);need(x['source_commit']==COMMIT,'training descriptor source commit')
 ks=x['source_keys'];need(type(ks)is list and 1<=len(ks)<=1000000,'complete nonempty ordered source roster')
 canonical=[]
 for k in ks:
  if dataset=='ISRUC':
   need(type(k)is list and len(k)==2,'explicit ordered ISRUC sequence/label pairs')
   for name in k:relative(name)
   canonical.append(k[0])
  else:relative(k);canonical.append(k)
 need(len(set(canonical))==len(canonical),'unique source rows')
 groups=x['group_by_key'];need(type(groups)is dict and set(groups)==set(canonical),'all source rows have biological group identity')
 for v in groups.values():ident(v)
 return x

def validate_plan(p):
 exact(p,('schema','dataset_id','method','seed_slot','seed_values','params','train','val','query','foundation','qualification','caps','official_source_sha256','recipe_policy'))
 need(p['schema']=='cbramod_native_fit_v1','native plan schema');route=method_route(p['dataset_id'],p['method'])
 sha(p['official_source_sha256']);d=DATASETS[p['dataset_id']]
 seeds=p['seed_values'];need(type(seeds)is list and len(seeds)==5 and len(set(seeds))==5,'five explicit distinct seeds, no invented defaults')
 for s in seeds:integer(s,0,2**32-1,'seed')
 integer(p['seed_slot'],0,4,'seed slot')
 exact(p['params'],tuple(RECIPE)+('cuda',))
 for k,v in RECIPE.items():need(type(p['params'][k])is type(v) and p['params'][k]==v,'exact source-default recipe operand '+k)
 integer(p['params']['cuda'],0,1024,'explicit CUDA ordinal')
 need(p['recipe_policy']=='source_defaults_validation_only_strict_positive_monitor_v1','explicit derived source-default recipe; not five-run historical parity')
 train=split_descriptor(p['train'],p['dataset_id'],'train');val=split_descriptor(p['val'],p['dataset_id'],'val')
 need(train['official_manifest_sha256']==val['official_manifest_sha256']==p['official_source_sha256'],'split/operative source join')
 q=p['query'];exact(q,('path','bytes','sha256','shape','dtype','row_ids','groups','lineage_sha256','query_sha256'))
 relative(q['path']);sha(q['sha256']);sha(q['lineage_sha256']);sha(q['query_sha256']);integer(q['bytes'],1,2**63-1,'input byte extent')
 need(q['dtype']=='<f4','source-normalized float32 inference tensors')
 ids=q['row_ids'];need(type(ids)is list and 1<=len(ids)<=1000000 and len(set(ids))==len(ids),'complete unique query row order')
 for x in ids:ident(x)
 need(type(q['groups'])is list and len(q['groups'])==len(ids),'complete query biological groups')
 for g in q['groups']:ident(g)
 if p['dataset_id']=='ISRUC':
  need(len(ids)%20==0,'complete twenty-epoch sequences')
  expected=[len(ids)//20,20,6,6000]
 else:expected=[len(ids),d[3],d[4],200]
 need(type(q['shape'])is list and all(type(n)is int for n in q['shape']) and q['shape']==expected,'exact official model input geometry')
 need(q['bytes']>=math.prod(expected)*4+10,'declared complete NPY extent')
 if p['dataset_id'] not in ('SEED-V','BCIC2020-3','CHB-MIT','TUEV','TUAB'):
  tr=set(train['group_by_key'].values());va=set(val['group_by_key'].values());te=set(q['groups'])
  need(not tr&va and not tr&te and not va&te,'paper whole-person split has no group overlap')
 f=p['foundation']
 if route['pretrained']:
  exact(f,('path','bytes','sha256','pretraining_condition_sha256'));relative(f['path']);sha(f['sha256']);sha(f['pretraining_condition_sha256']);integer(f['bytes'],1,2**63-1,'weights extent')
 else:need(f is None,'no pretrained weights for selected no-pretraining route')
 qual=p['qualification'];exact(qual,('unresolved','inventory_sha256','source_to_paper_review_sha256','seed_identity_sha256','split_qualification_sha256','preprocessing_sha256','sequence_metric_policy'))
 need(qual['unresolved']==[],'unresolved authentic source/cohort/run qualifications remain a setup hold')
 for k,v in qual.items():
  if k not in ('unresolved','sequence_metric_policy'):sha(v)
 need(qual['sequence_metric_policy']=='canonical_epoch_flatten_v1','explicit benchmark adaptation: per-epoch ISRUC validation, not exact evaluator parity')
 cap=p['caps'];exact(cap,('maximum_input_bytes','maximum_checkpoint_bytes','maximum_predictions_bytes','maximum_receipt_bytes','maximum_runtime_seconds'))
 for k,v in cap.items():integer(v,1,2**63-1,'positive explicit cap '+k)
 need(q['bytes']<=cap['maximum_input_bytes'],'input cap before decoder')
 need(math.prod([len(ids),d[2]])*4+4096<=cap['maximum_predictions_bytes'],'complete probability rectangle cap before native work')
 if f:need(f['bytes']<=cap['maximum_checkpoint_bytes'],'foundation cap before native work')
 # Hash operands bind evidence; they do not certify its scientific contents.
 return {'route':route,'plan_sha256':digest(p),'seed':seeds[p['seed_slot']],'source_complete':False}
