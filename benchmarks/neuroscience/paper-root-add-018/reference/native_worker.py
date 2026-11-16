"""Real native reference producer, authored only; no native execution here.

An independently qualified recipe binds original input/cohort roles, every
producer job, every full numerical component and missing external producers.
Absence of any binding is a hard reference failure, never an answer-file replay.
"""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ofc.common import load,write_new,require,identity,bounded_read,relative
from reference.capture import instrument_figure,resolve_product

def matlab_literal(path):return "'"+str(path).replace("'","''")+"'"
def native_fit(recipe,inputs,output):
 require(recipe['qualified_native_bindings']is True,'native input/producer/extraction bindings not qualified')
 jobs=recipe['jobs'];require(jobs and len({x['id']for x in jobs})==len(jobs),'native producer DAG')
 complete=set();records=[];source=Path(__file__).resolve().parent/'author_source'
 for job in jobs:
  require(set(job['dependencies'])<=complete,'native dependency not complete');folder=output/job['id'];folder.mkdir();request={**job['request'],'author_source':str(source),'output_root':str(folder)}
  if job['kind']=='original_native_dispatch':
   requestpath=folder/'request.json';write_new(requestpath,request)
   command=[recipe['matlab_executable'],'-batch',f"addpath({matlab_literal(Path(__file__).resolve().parent)});native_dispatch(jsondecode(fileread({matlab_literal(requestpath)})));"]
  elif job['kind']=='captured_original_figure':
   original,pin=bounded_read(source/relative(job['source_path']),pin=job['source_pin']);capture=instrument_figure(original,pin['sha256']);wrapper=folder/(capture['name']+'.m');wrapper.write_bytes(capture['body']);requestpath=folder/'request.json';write_new(requestpath,{'arguments':job['arguments']})
   command=[recipe['matlab_executable'],'-batch',f"addpath(genpath({matlab_literal(source)}));addpath({matlab_literal(folder)});r=jsondecode(fileread({matlab_literal(requestpath)}));products=feval('{capture['name']}',r.arguments{{:}});save({matlab_literal(folder/'native_products.mat')},'products','-v7.3');"]
   write_new(folder/'CAPTURE_PROVENANCE.json',{k:v for k,v in capture.items()if k!='body'})
  elif job['kind']=='qualified_missing_original_producer':
   # Missing original hLDS/block/simulation sources must arrive as a pinned,
   # independently qualified source executable, never a precomputed result.
   require(job['source_pin']and job['independent_qualification_id'],'missing native source closure')
   executable=inputs/relative(job['source_path']);bounded_read(executable,pin=job['source_pin'])
   command=[recipe['python_executable'],str(executable),'--input',str(inputs),'--output',str(folder),'--request',str(inputs/relative(job['request_path']))]
  else:raise ValueError('unknown native producer kind')
  write_new(folder/'COMMAND.json',{'argv':command,'job_id':job['id'],'dependencies':job['dependencies']})
  with (folder/'stdout.log').open('xb')as so,(folder/'stderr.log').open('xb')as se:
   completed=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=so,stderr=se,check=False)
  write_new(folder/'COMPLETION.json',{'original_returncode':completed.returncode,'job_id':job['id'],'substituted_precomputed_reference':False})
  require(completed.returncode==0,'native producer failed');bounded_read(folder/'native_products.mat',recipe['max_native_product_bytes'])
  records.append({'id':job['id'],'products':str((folder/'native_products.mat').relative_to(output))});complete.add(job['id'])
 write_new(output/'MODEL.json',{'recipe':recipe,'completed_jobs':records,'source':str(source),'all_native_jobs_executed':True})

def native_analyze(request,model_root,output):
 import numpy as np
 import hdf5storage
 state=load(model_root/'MODEL.json');recipe=state['recipe'];lookup={x['id']:x for x in state['completed_jobs']};cache={};rows=[]
 obligations=request['payload']['native_requests'];require(set(recipe['obligation_bindings'])=={x['obligation_id']for x in obligations},'complete74 native extraction mapping')
 for obligation in obligations:
  binding=recipe['obligation_bindings'][obligation['obligation_id']];components=[]
  require(set(binding['components'])=={x['component_id']for x in obligation['component_roster']},'full component map')
  for component in obligation['component_roster']:
   selected=binding['components'][component['component_id']];stage=selected['job_id'];require(stage in lookup,'component lacks actual producer')
   if stage not in cache:cache[stage]=hdf5storage.loadmat(model_root/lookup[stage]['products'])
   value=resolve_product(cache[stage],selected['field_path'])
   if selected['kind']=='provenance':data=selected['qualified_provenance_mapping'];disposition='provenance_only'
   else:
    arr=np.asarray(value,dtype=float);shape=tuple(len(a['labels'])for a in component['axes']);require(arr.shape==shape,'native product dimensional binding')
    if np.any(~np.isfinite(arr)):
     data=[float(x)if np.isfinite(x)else'nan'if np.isnan(x)else'positive_infinity'if x>0 else'negative_infinity'for x in arr.reshape(-1)];disposition='native_nonfinite'
    else:data=arr.reshape(-1).tolist();disposition='defined'
   components.append({'component_id':component['component_id'],'unit':component['unit'],'axes':component['axes'],'data':data,'disposition':disposition,'provenance':{'producer_job_id':stage,'full_native_product':lookup[stage]['products'],'source_binding':selected['source_binding'],'field_path':selected['field_path'],'native_policy':selected['native_policy']}})
  rows.append({'family_id':obligation['family_id'],'query_id':obligation['obligation_id'],'disposition':'value','reason':None,'watermark':None,'value':{'components':components,'source_policy':'native_source_reproduction','methods_conformance':binding['methods_conformance'],'role_dispositions':binding['role_dispositions'],'attempts':state['completed_jobs']}})
 write_new(output/'response.json',{'schema':'ofc-response-v1','request_id':request['request_id'],'source_id':request['source_id'],'model_id':request['model_id'],'rows':rows})

def main():
 p=argparse.ArgumentParser();p.add_argument('--request',required=True);p.add_argument('--output',required=True);p.add_argument('--inputs',required=True);p.add_argument('--model');args=p.parse_args();req=load(args.request);out=Path(args.output);inputs=Path(args.inputs)
 if req['phase']=='build':write_new(out/'build.json',{'producer':'original_source_full_paper','source_files':59,'native_closure_unqualified_until_recipe_bound':True})
 elif req['phase']=='investigate':write_new(out/'investigation.json',{'required_obligations':req['public_contract']['scope']['obligation_ids'],'missing_bindings_must_fail':True})
 elif req['phase']=='fit':native_fit(load(inputs/'native_recipe.json'),inputs,out)
 elif req['phase']=='analyze':native_analyze(req,Path(args.model),out)
 else:raise ValueError('Native reference worker is reproduction-only; prospective references use their own actual learner source.')
if __name__=='__main__':main()
