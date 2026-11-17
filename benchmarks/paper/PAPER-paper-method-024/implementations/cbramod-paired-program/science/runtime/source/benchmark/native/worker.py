"""Real CBraMod construction/fit/inference route; source-only until provisioned."""
import argparse,hashlib,json,os,stat,time
from pathlib import Path
from types import SimpleNamespace
from .policy import DATASETS,validate_plan,need,encode
from .source import verify_official,pinned_file,native_components
from .loaders import loaders
from .fit import fit
from .inference import inspect_input,export

class CappedWriter:
 def __init__(self,path,cap):self.file=open(path,'xb');self.cap=cap
 def write(self,data):
  need(self.file.tell()+len(data)<=self.cap,'checkpoint physical byte cap')
  return self.file.write(data)
 def flush(self):return self.file.flush()
 def tell(self):return self.file.tell()
 def seek(self,*args):return self.file.seek(*args)
 def close(self):return self.file.close()

def owner_paths(official,inputs,output):
 from .owners import admit_owners
 roots=admit_owners({'official':official,'inputs':inputs},{'output':output})
 return [roots['official'],roots['inputs'],roots['output']]

def admit_inputs(plan,inputs):
 q=plan['query'];pinned_file(inputs/q['path'],q,plan['caps']['maximum_input_bytes']);inspect_input(inputs/q['path'],q)
 if plan['foundation']:pinned_file(inputs/plan['foundation']['path'],plan['foundation'],plan['caps']['maximum_checkpoint_bytes'])
 # Authentic processed databases/recordings and label-bearing TRAIN/val assets
 # still require independent complete inventory qualification. No assertion here
 # upgrades source-key/group strings to such evidence.

def execute(plan,official_root,inputs_root,output_root):
 started=time.monotonic();binding=validate_plan(plan)
 official,inputs,output=owner_paths(official_root,inputs_root,output_root)
 verify_official(official,plan['official_source_sha256'])
 need(plan['caps']['maximum_receipt_bytes']>=len(encode(plan))+32768,'complete declared receipt allocation before native work')
 deadline=started+plan['caps']['maximum_runtime_seconds'];admit_inputs(plan,inputs)
 need(time.monotonic()<deadline,'deadline before native boundary')
 c=native_components(official,plan['dataset_id'],plan['official_source_sha256']);torch=c['torch'];torch.cuda.set_device(plan['params']['cuda'])
 c['entry'].setup_seed(binding['seed']) # before loader construction and model initialization
 params=SimpleNamespace(**plan['params'],downstream_dataset=plan['dataset_id'],
  num_of_classes=DATASETS[plan['dataset_id']][2],seed=binding['seed'],
  datasets_dir=str(inputs/plan['train']['prepared_root']),model_dir=str(output),
  use_pretrained_weights=binding['route']['pretrained'],
  foundation_dir=str(inputs/plan['foundation']['path'])if plan['foundation']else '')
 dl=loaders(c,plan,inputs);model=c['head'].Model(params);trainer=c['trainer'].Trainer(params,dl,model)
 result=fit(c,trainer,plan,deadline)
 output.mkdir(parents=True,exist_ok=False)
 writer=CappedWriter(output/'checkpoint.pth',plan['caps']['maximum_checkpoint_bytes'])
 try:torch.save(trainer.model.state_dict(),writer);writer.flush();os.fsync(writer.file.fileno())
 finally:writer.close()
 artifact=export(c,trainer.model,plan,inputs/plan['query']['path'],output/'predictions.npy',deadline)
 need(time.monotonic()<deadline,'completed prediction deadline')
 receipt={'schema':'cbramod_native_result_v1','binding':binding,'method':plan['method'],
  'dataset_id':plan['dataset_id'],'seed_slot':plan['seed_slot'],'seed':binding['seed'],
  'fit':result,'predictions':artifact,'elapsed_seconds':time.monotonic()-started,
  'official_source_sha256':plan['official_source_sha256'],'recipe_policy':plan['recipe_policy'],
  'source_default_run_not_historical_paper_parity':True,'scientifically_qualified':False}
 b=encode(receipt);need(len(b)<=plan['caps']['maximum_receipt_bytes'],'complete receipt cap')
 with(output/'RESULT.json').open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
 return receipt

def main():
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--plan-sha256',required=True)
 p.add_argument('--official-root',required=True);p.add_argument('--inputs-root',required=True);p.add_argument('--output-root',required=True);a=p.parse_args()
 path=Path(a.plan);need(path.stat().st_size<=16*1024*1024,'bounded plan');raw=path.read_bytes()
 need(hashlib.sha256(raw).hexdigest()==a.plan_sha256,'exact plan pin')
 plan=json.loads(raw);print(encode(execute(plan,a.official_root,a.inputs_root,a.output_root)).decode(),end='')
if __name__=='__main__':main()
