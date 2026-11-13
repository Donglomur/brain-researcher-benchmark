"""Real source-owned scientific worker entry; never executed during source build."""
import sys,time,os,runpy
from .contracts import need,closed,parse,canonical,digest,Budget,Custody,Store,Authority

def execute(request,inputs,outputs,trace):
 role=request['role'];b=request['body'];products={}
 from .arrays import load_arrays,dump_arrays,state_encode,state_decode
 def arrays(pin,cap=512*2**20):return load_arrays(inputs.read(pin,cap),cap=cap)
 def write(name,raw,cap=512*2**20):return outputs.write(name,raw,cap)
 def save_state(name,state,config):
  meta,raw=state_encode(state,config['bindings'],config['limits']);return {'metadata':write(name+'.json',meta),'arrays':write(name+'.npz',raw)}
 def load_state(pair,config):return state_decode(inputs.read(pair['metadata'],config['limits']['max_state_bytes']),inputs.read(pair['arrays'],config['limits']['max_state_bytes']),config['bindings'],config['limits'])
 if role=='raw_prepare':
  from .raw_prepare import prepare
  raw=inputs.read(b['raw'],1024*2**20);planned=inputs.json(b['planned_support']);inputs.read(b['organizer_source'],4*2**20)
  public,target,proof=prepare(raw,planned,inputs.path(b['organizer_source']['path']),b['source_manifest']['sha256'],trace)
  products={'public':write('public.npz',dump_arrays(public)),'target':write('target.npz',dump_arrays(target)),'conversion':write('conversion.json',canonical(proof))}
 elif role=='project_views':
  from .views import project,shuffle_map
  from .programme import CONDITIONS,planned_support
  import numpy as np
  public=arrays(b['public']);public['panel_fingerprint']=str(public['panel_fingerprint'].item());planned=planned_support(inputs.json(b['planned_support']));commitment=inputs.json(b['shuffle_commitment']);seed=inputs.read(b['protected_shuffle_seed'],32)
  for k in('train_trial_ids','eval_trial_ids','heldin_unit_ids','heldout_unit_ids','train_condition_ids','eval_condition_ids','bin_left_edges_ms'):need(np.array_equal(public[k],planned[k])and canonical(public[k].tolist())==canonical(planned[k]),'exact canonical prepared support must match pre-activity commitment')
  mapping=shuffle_map(seed,planned,commitment)
  for condition in CONDITIONS:
   training,query,refs=project(public,condition,shuffle=mapping);products[condition+'_training']=write(condition+'_training.npz',dump_arrays(training));products[condition+'_query']=write(condition+'_query.npz',dump_arrays(query))
  support={**planned,'panel_fingerprint':public['panel_fingerprint']};products['support']=write('support.json',canonical(support));products['protected_map']=write('protected_map.npz',dump_arrays({'donor_index':mapping}));trace({'event':'all_five_physical_information_views','planned_support_sha256':digest(canonical(planned)),'same_fixed_map_for_all_arms':True})
 elif role in('reference_train','reference_development','reference_predict','tool_only'):
  from . import scientific
  import numpy as np
  config=dict(b['config']);training=arrays(b['training']);split=inputs.json(b['split'])if b.get('split')else None
  if 'train_bin_opportunities'in training:training['train_bin_opportunities']=int(training['train_bin_opportunities'].item())
  rid=b['reference'];need(config['bindings']['training']==b['training']['sha256'],'actual training content binding')
  if role=='reference_train':
   if rid in('R0','R1','R2'):need(set(training)=={'train_counts_heldout','train_trial_ids','heldout_unit_ids','train_condition_ids','bin_left_edges_ms'},'context-reference state has no empirical observed-neuron payload or metadata')
   if rid=='R0':need(b.get('rate_training')is not None,'complete rate-only diagnostic state producer')
   state=scientific.train(rid,training,split,config,trace);pair=save_state('trained',state,config);products.update({'state_metadata':pair['metadata'],'state_arrays':pair['arrays']})
   # Original searched-development certificate is a state product; no new grid.
   if rid not in('R0','R1','R3'):
    cert=scientific.development(rid,training,split,{**config,'training_state':state},trace);cp=save_state('development',cert,config);products.update({'development_metadata':cp['metadata'],'development_arrays':cp['arrays']})
   if rid=='R0'and b.get('rate_training'):
    rt=arrays(b['rate_training']);rt['train_bin_opportunities']=int(rt['train_bin_opportunities'].item());rc={**config,'bindings':{**config['bindings'],'training':b['rate_training']['sha256']}};rs=scientific.train('R0',rt,None,rc,trace);rp=save_state('rate_trained',rs,rc);products.update({'rate_state_metadata':rp['metadata'],'rate_state_arrays':rp['arrays']})
  elif role=='reference_development':
   cert=scientific.development(rid,training,split,config,trace)
   if rid=='R0':scientific.development('R1',training,split,{**config,'joint_development':cert},trace)
   pair=save_state('development',cert,config);products={'development_metadata':pair['metadata'],'development_arrays':pair['arrays']}
  else:
   query=arrays(b['query']);need(config['bindings']['query']==b['query']['sha256'],'full query pool binding')
   base_config={**config,'bindings':{k:v for k,v in config['bindings'].items()if k!='query'}}
   if role=='reference_predict':state=load_state(b['state'],base_config);state=scientific.adapt(state,training,query,config,trace);pair=save_state('adapted',state,config);products.update({'state_metadata':pair['metadata'],'state_arrays':pair['arrays']})
   else:state=load_state(b['state'],config)
   if b.get('case_route'):
    from .views import case_query
    rates=np.concatenate([scientific.predict(state,case_query(query,i),config,trace)for i in range(574)],axis=0)
   else:rates=scientific.predict(state,query,config,trace)
   support=inputs.json(b['support']);pred={'expected_counts':rates,'trial_ids':query['eval_trial_ids'],'heldout_unit_ids':query['heldout_unit_ids'],'bin_left_edges_ms':query['bin_left_edges_ms'],'prediction_units':np.asarray('expected_spikes_per_bin'),'panel_fingerprint':np.asarray(support['panel_fingerprint'])};products['prediction']=write('prediction.npz',dump_arrays(pred,32*2**20),32*2**20)
 elif role=='participant_tool'and b['tool']=='reference_predict':
  from . import scientific
  from .views import case_query
  import numpy as np
  config=b['config'];state=load_state(b['state'],config);query=arrays(b['query']);need(config['bindings']['query']==b['query']['sha256'],'same adapted full query pool')
  if b['case_index']is not None:query=case_query(query,b['case_index'])
  rates=scientific.predict(state,query,config,trace);support=inputs.json(b['support']);pred={'expected_counts':rates,'trial_ids':query['eval_trial_ids'],'heldout_unit_ids':query['heldout_unit_ids'],'bin_left_edges_ms':query['bin_left_edges_ms'],'prediction_units':np.asarray('expected_spikes_per_bin'),'panel_fingerprint':np.asarray(support['panel_fingerprint'])};products['prediction']=write('prediction.npz',dump_arrays(pred,32*2**20),32*2**20)
 elif role in('participant_F','participant_tool'):
  # Arbitrary captured source executes solely in this already-contained worker.
  # It owns numerical choices and writes the six-field prediction itself.
  if role=='participant_F':
   source=b['submitted_source'];inputs.read(source,128*2**10);source_path=inputs.path(source['path'])
   if 'input_request_template'in b:
    need('input_request'not in b,'one original F request transport')
    from .contracts import descriptor
    template=b['input_request_template'];closed(template,{'schema','training','query','state','case_index','context','output_contract'})
    need(template['schema']=='NLB017_arbitrary_method_inputs_v1'and template['state']is None and template['case_index']is None and template['output_contract']=='six_array_expected_spikes_per_bin','fixed full F request template')
    for key in('training','query'):
     descriptor(template[key]);need(template[key]in request['declared_inputs'],'F request uses admitted actual view')
    context=template['context'];closed(context,{'programme','group','condition','code_view','mode'})
    need(context['programme']==request['bindings']['programme']and context['mode']=='F'and request['job']==context['group']+'/programme'and context['condition']==context['group'].split('/')[0]and context['code_view']==context['group'].split('/')[1][-1],'exact original F request context')
    inp=write('actual_request.json',canonical(template),2**20);products['actual_request']=inp;request_path=outputs.path(inp['path'])
   else:
    need(b['input_request']in request['declared_inputs'],'explicit learner request');request_path=inputs.path(b['input_request']['path'])
  else:
   source_raw=b['source_utf8'].encode();need(len(source_raw)<=128*2**10 and digest(source_raw)==b['source_sha256'],'actual model-emitted source identity');source=write('actual_programme.py',source_raw,128*2**10);products['actual_source']=source;source_path=outputs.path(source['path'])
   inp=write('actual_request.json',canonical(b['input_request']),2**20);products['actual_request']=inp;request_path=outputs.path(inp['path'])
  if role=='participant_F':
   from .reference_service import bind,unbind
   bind(b['reference_service'],inputs,outputs,trace)
  old=list(sys.argv);sys.argv=[str(source_path),'--request',str(request_path),'--output',str(outputs.path('candidate.npz'))]
  try:runpy.run_path(str(source_path),run_name='__main__')
  finally:
   sys.argv=old
   if role=='participant_F':unbind()
  kind=b.get('output_kind','prediction')if role=='participant_tool'else'prediction';need(kind in('state','prediction'),'declared arbitrary-source output kind');cap=512*2**20 if kind=='state'else 32*2**20;pin,raw=outputs.capture('candidate.npz',cap)
  if kind=='state':load_arrays(raw,cap=cap)
  products[kind]=pin
 elif role=='protected_score':
  from .scoring import grade
  collection=inputs.json(b['collection'],64*2**20);support=collection['support'];target=arrays(b['target']);preds={k:inputs.read(pin,32*2**20)for k,pin in collection['prediction_groups'].items()};contrasts=inputs.json(b['contrasts']);result,private=grade(preds,target,support,contrasts,inputs.custody.resources)
  products={'grade':write('grade.json',canonical(result)),'private_ledger':write('private_ledger.npz',dump_arrays(private))}
 elif role=='protected_uncertainty':
   from .scoring import uncertainty,UncertaintyDrawFailure,publish_draw_failure
   try:result,draws=uncertainty(inputs.json(b['grade']),arrays(b['private_ledger']),inputs.json(b['contrasts']),inputs.json(b['support']))
   except UncertaintyDrawFailure as original:publish_draw_failure(original,trace)
   products={'uncertainty':write('uncertainty.json',canonical(result)),'private_draws':write('private_draws.npz',dump_arrays(draws))}
 elif role=='aggregate_report':
  from .reporting import aggregate
  result=aggregate(inputs.json(b['grade']),inputs.json(b['uncertainty']),inputs.json(b['costs']),inputs.json(b['exposure']),b['disposition']);products={'aggregate':write('aggregate.json',canonical(result))}
 else:raise ValueError('unsupported selected worker role')
 return products

def main():
 from .worker_runtime import main as worker_main
 return worker_main(execute)

def entry():
 # main retains and raises the original worker error after publication. Even
 # an ordinary participant SystemExit(0) is a failed invocation, not success.
 try:return main()
 except BaseException as original:raise SystemExit(1) from original

if __name__=='__main__':raise SystemExit(entry())
