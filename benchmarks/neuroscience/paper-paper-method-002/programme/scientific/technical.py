"""Actual technical/solver producers. BUILD reviews parse these definitions only."""
from .technical_support.contracts import admit,require,complete,positive,emit,MORPHOLOGIES,bounded_extents

def architecture(ctx):
 """Project genuine selected source ASTs and caller edges, never cached results."""
 import ast,hashlib
 roster=ctx.read_json('architecture_sources');rows=[]
 required={'module','channel','synapse','integrator','autodiff','vectorization','checkpoint','jit'}
 require(set(roster)==required,'complete architecture mechanism roster')
 for role in sorted(required):
  row=roster[role];raw=ctx.read_source(row['logical'])
  require(hashlib.sha256(raw).hexdigest()==row['sha256'],'architecture source body identity')
  tree=ast.parse(raw.decode());definitions={n.name:n for n in ast.walk(tree)if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}
  require(row['symbols']and set(row['symbols'])<=set(definitions),'actual source symbols')
  for symbol in row['symbols']:
   n=definitions[symbol];calls=sorted(set(ast.unparse(x.func)for x in ast.walk(n)if isinstance(x,ast.Call)))
   rows.append({'role':role,'symbol':symbol,'source_sha256':row['sha256'],'line':n.lineno,'end_line':n.end_lineno,'calls':calls})
 emit(ctx,'architecture_source_map',{'definitions':rows,'historical_environment_verified':False})

def solver(ctx):
 import numpy as np,jax
 from .technical_model import solver_pair
 roster=complete(ctx.read_json('solver_morphologies'),MORPHOLOGIES,'identity')
 vj=[];vn=[];times=[];amps=[];clocks=[]
 # Complete 5 x 10 x 3 family; no cell/batch filtering.
 for identity in MORPHOLOGIES:
  _,jrun,nrun,mapping=solver_pair(ctx.input_path(roster[identity]['logical']),identity)
  jrun=jax.jit(jrun);jrows=[];nrows=[];timerows=[];amprows=[];clockrows=[]
  for index in range(10):
   ctx.checkpoint();amplitude=.2+.1*index
   a=np.asarray(jrun(amplitude));b,clock=nrun(amplitude)
   ctx.record('completed_operation',{'kind':'trajectory_forward','count':2,'coordinate':[identity,index,'independent_Jaxley_and_NEURON']})
   require(a.shape[0]==b.shape[0]==3,'three independent recording sites')
   jclock=np.arange(a.shape[1])*.025
   # Different literal terminal extents remain fully visible; no truncation.
   jrows.append(a);nrows.append(b);clockrows.append({'jaxley_ms':jclock.tolist(),'neuron_ms':clock.tolist()})
   ja=np.argmax(a,axis=1);na=np.argmax(b,axis=1)
   timerows.append(np.stack([jclock[ja],clock[na]]))
   amprows.append(np.stack([a[np.arange(3),ja],b[np.arange(3),na]]))
  vj.append(np.stack(jrows));vn.append(np.stack(nrows));times.append(np.stack(timerows));amps.append(np.stack(amprows))
  clocks.append({'morphology':identity,'mapping':mapping,'amplitudes':clockrows})
 emit(ctx,'Jaxley_voltage',np.stack(vj));emit(ctx,'NEURON_voltage',np.stack(vn))
 emit(ctx,'spike_times',np.stack(times));emit(ctx,'spike_amplitudes',np.stack(amps));emit(ctx,'clock',clocks)
 ctx.record('solver_endpoint','literal full-trace argmax; not threshold spike detection')

def _timing_device(ctx,device):
 import jax,jax.numpy as jnp
 from .technical_model import api,benchmark_cell
 from .technical_support.observations import measure
 jx=api();c=ctx.config;repeats=positive(c['repeats'],'runtime repeats')
 require(c['hardware']in('CPU','A100'),'J03 hardware')
 require(device.platform==('cpu'if c['hardware']=='CPU'else'gpu'),'actual selected device platform')
 if c['hardware']=='A100':require('A100'in device.device_kind,'actual A100 device')
 compile_rows=[];warm_rows=[];gradient_rows=[];memory=[]
 for kind,batches in(('CA1',(1,10,100,1000,10000)),('point',(1,10,100,1000,10000,100000,1000000))):
  cell=benchmark_cell(ctx,kind);params=cell.get_parameters()
  def sim(p,current,radius):
   ps=cell.branch(0).loc(0.).data_set('radius',radius,None)
   ds=cell.branch(0).loc(0.).data_stimulate(jx.step_current(.1 if kind=='point'else 3.,5. if kind=='point'else 2.,current,.025,20.),None)
   return jx.integrate(cell,params=p,param_state=ps,data_stimuli=ds,delta_t=.025,checkpoint_lengths=[10,9,9])
  for batch in batches:
   ctx.checkpoint();radius=1e-5*jnp.arange(batch)
   if c['profile']=='prospective_paper':
    radius=jnp.asarray(ctx.read_array('benchmark_radius:'+kind+':'+str(batch)))
    require(radius.shape==(batch,)and bool(jnp.all(radius>0)),'explicit selected positive prospective radii')
   # Source includes a zero-radius first sample. It is retained, not silently repaired.
   currents=1e-5*jnp.arange(batch)if kind=='point'else jnp.full((batch,),.7)
   batched=jax.jit(jax.vmap(sim,in_axes=(None,0,0)))
   loss=lambda p:jnp.mean(batched(p,currents,radius)[:,0,-1])
   grad=jax.jit(jax.value_and_grad(loss))
   compiled,compile_obs=measure(ctx,lambda:batched.lower(params,currents,radius).compile())
   _,cold=measure(ctx,compiled,params,currents,radius,sync=True)
   gradient_compiled,gradient_compile=measure(ctx,lambda:grad.lower(params).compile())
   ctx.record('completed_operation',{'kind':'trajectory_forward','count':batch,'coordinate':[kind,batch,'cold']})
   compile_rows.append({'kind':kind,'batch':batch,'hardware':c['hardware'],'lower_and_compile':compile_obs,'first_execution':cold,'gradient_lower_and_compile':gradient_compile})
   for repeat in range(repeats):
    _,warm=measure(ctx,compiled,params,currents,radius,sync=c['profile']=='prospective_paper' or kind=='CA1')
    _,g=measure(ctx,gradient_compiled,params,sync=c['profile']=='prospective_paper')
    ctx.record('completed_operation',{'kind':'trajectory_forward','count':batch,'coordinate':[kind,batch,repeat,'warm']})
    ctx.record('completed_operation',{'kind':'trajectory_gradient','count':batch,'coordinate':[kind,batch,repeat,'gradient']})
    key={'kind':kind,'batch':batch,'repeat':repeat,'hardware':c['hardware']}
    warm_rows.append({**key,**warm});gradient_rows.append({**key,**g});memory.append({**key,'warm':warm['after'],'gradient':g['after']})
 emit(ctx,'cold_compile_times',compile_rows);emit(ctx,'warm_times',warm_rows);emit(ctx,'gradient_times',gradient_rows);emit(ctx,'peak_memory',memory)

class _DeviceContext:
 def __init__(self,parent,hardware):
  self.parent=parent;self.config={**parent.config,'hardware':hardware};self.outputs={};self.hardware=hardware
 def __getattr__(self,name):return getattr(self.parent,name)
 def emit_json(self,name,value):
  require(name not in self.outputs,'duplicate device product');self.outputs[name]=value
 def record(self,name,value):
  if name=='completed_operation':value={**value,'coordinate':[self.hardware,*value['coordinate']]}
  return self.parent.record(name,value)

def timing(ctx):
 import jax
 require(ctx.config['hardware']==['CPU','A100'],'full CPU and A100 timing family')
 selected=ctx.config['device_ids'];require(set(selected)=={'CPU','A100'},'explicit actual device identifiers')
 products={k:[]for k in ('cold_compile_times','warm_times','peak_memory','gradient_times')}
 for hardware,platform in (('CPU','cpu'),('A100','gpu')):
  require(type(selected[hardware])is int and selected[hardware]>=0,'explicit device ordinal')
  matches=[d for d in jax.devices(platform)if d.id==selected[hardware]]
  require(len(matches)==1,'selected actual device unavailable');device=matches[0]
  if hardware=='A100':require('A100'in device.device_kind,'actual A100 required')
  child=_DeviceContext(ctx,hardware)
  with jax.default_device(device):_timing_device(child,device)
  require(set(child.outputs)==set(products),'complete actual timing product set per device')
  for name in products:products[name].extend(child.outputs[name])
  ctx.record('actual_timing_device',{'hardware':hardware,'platform':device.platform,'id':device.id,'device_kind':device.device_kind})
 for name,value in products.items():emit(ctx,name,value)

def network(ctx):
 import jax,jax.numpy as jnp
 from .technical_model import build_network,trajectory
 from .technical_support.observations import measure
 spec=ctx.read_json('network_spec');net,params,edges=build_network(ctx,spec)
 count=sum(x.size for x in jax.tree_util.tree_leaves(params))
 require(count==spec['expected_gradient_size'],'full trainable scalar cardinality')
 # Every state and voltage at every exact step, before executing native solver.
 from math import prod
 state_steps=prod(spec['checkpoint_lengths'])if ctx.config['profile']=='source_literal'else spec['steps']
 bounded_extents(ctx,{'full_state':(state_steps+1)*spec['expected_state_size']*8,'parameter_gradient':count*8,'voltage':(spec['steps']+1)*spec['cells']*8,'adjacency':int(edges.nbytes)})
 indices=jnp.asarray(spec['loss_cells'])
 literal=ctx.config['profile']=='source_literal'
 def forward(p):return trajectory(net,p,spec['steps'],spec['dt_ms'],spec['checkpoint_lengths'],literal_padding=literal)[:2]
 def objective(p):
  # Gradient route does not materialize a redundant complete state history.
  voltage=trajectory(net,p,spec['steps'],spec['dt_ms'],spec['checkpoint_lengths'],retain=False,literal_padding=literal)
  return jnp.mean(voltage[-1,indices])
 (state,voltage),fobs=measure(ctx,jax.jit(forward),params)
 require(state.shape[1]==spec['expected_state_size'],'complete state cardinality')
 (loss,gradient),gobs=measure(ctx,jax.jit(jax.value_and_grad(objective)),params)
 ctx.record('completed_operation',{'kind':'network_forward','count':1,'coordinate':[ctx.group,spec['steps']]})
 ctx.record('completed_operation',{'kind':'network_gradient','count':1,'coordinate':[ctx.group,spec['steps']]})
 flat=jnp.concatenate([jnp.ravel(x)for x in jax.tree_util.tree_leaves(gradient)])
 emit(ctx,'full_state',state);emit(ctx,'parameter_gradient',flat);emit(ctx,'connectivity',edges)
 if ctx.group=='J04':emit(ctx,'voltage',voltage)
 else:emit(ctx,'selected_12_loss',jnp.asarray([loss]))
 emit(ctx,'timing_memory',{'full_forward':fobs,'full_gradient':gobs,'state_width':state.shape[1],'state_time_steps_including_padding':state.shape[0]-1,'reported_voltage_steps':voltage.shape[0]-1,'parameter_width':count,'profile':ctx.config['profile'],'historical_generator_available':ctx.group!='J05'})

def transforms(ctx):
 import jax,jax.numpy as jnp,numpy as np
 z=jnp.asarray(ctx.read_array('untransformed'));bounds=np.asarray(ctx.read_array('bounds'))
 require(z.ndim==1,'one complete ordered scalar parameter vector')
 require(bounds.shape==(z.size,2)and np.all(bounds[:,1]>bounds[:,0]),'complete positive bound widths')
 lower=jnp.asarray(bounds[:,0]);width=jnp.asarray(bounds[:,1]-bounds[:,0]);p=lower+width*jax.nn.sigmoid(z)
 derivative=width*jax.nn.sigmoid(z)*jax.nn.sigmoid(-z)
 logjac=jnp.log(width)-jax.nn.softplus(-z)-jax.nn.softplus(z)
 recovered=jnp.log((p-lower)/(lower+width-p))
 require(bool(jnp.all(jnp.isfinite(recovered))),'finite inverse: extreme transform saturation is not clipped')
 emit(ctx,'physical_parameters',p);emit(ctx,'untransformed_parameters',recovered);emit(ctx,'derivative',derivative);emit(ctx,'log_Jacobian',logjac);emit(ctx,'bounds',bounds)
 ctx.record('bounds_units',ctx.read_json('parameter_units'))

def optimize(ctx):
 import jax,jax.numpy as jnp,optax
 from .technical_model import build_network,trajectory
 spec=ctx.read_json('network_spec');net,params,_=build_network(ctx,spec)
 policies=ctx.read_json('optimizer_groups');names=[next(iter(p))for p in params]
 require(set(names)==set(policies),'every original parameter family has a selected optimizer')
 require(ctx.config['zero_gradient_policy']in('refuse','zero_update'),'explicit zero-gradient policy')
 selectors={name:optax.sgd(policies[name]['gamma'],momentum=policies[name]['momentum'])if policies[name]['optimizer']=='sgd'else optax.adam(policies[name]['gamma'])for name in names}
 require(all(p['optimizer']in('sgd','adam')and 0.8<=p['beta']<=.99 for p in policies.values()),'closed source optimizer composition')
 states=[selectors[name].init(p)for name,p in zip(names,params)];history=[];updates_all=[];rates=[]
 indices=jnp.asarray(spec['loss_cells'])
 def objective(p):return jnp.mean(trajectory(net,p,spec['steps'],spec['dt_ms'],spec['checkpoint_lengths'],retain=False)[-1,indices])
 vg=jax.jit(jax.value_and_grad(objective))
 for iteration in range(positive(ctx.config['iterations'],'optimizer iterations')):
  ctx.checkpoint();loss,grad=vg(params);iteration_updates=[];iteration_rates=[]
  for k,(name,p,g)in enumerate(zip(names,params,grad)):
   policy=policies[name];norm=jnp.sqrt(sum(jnp.sum(x*x)for x in jax.tree_util.tree_leaves(g)))
   zero=bool(norm==0)
   require(not zero or ctx.config['zero_gradient_policy']=='zero_update','zero-gradient normalized step undefined')
   scale=0. if zero else (loss if policy['multiply_loss']else 1.)/norm**policy['beta']
   scaled=jax.tree_util.tree_map(lambda x:x*scale,g)
   update,states[k]=selectors[name].update(scaled,states[k],p);params[k]=optax.apply_updates(p,update)
   iteration_updates.append({name:{key:value.tolist()for key,value in update.items()}})
   iteration_rates.append({'name':name,'gamma':policy['gamma'],'beta':policy['beta'],'norm':float(norm),'scale':float(scale),'zero':zero})
  history.append({'iteration':iteration,'loss':float(loss),'gradient':[{k:v.tolist()for k,v in g.items()}for g in grad]});updates_all.append(iteration_updates);rates.append(iteration_rates)
 emit(ctx,'loss_gradient',history);emit(ctx,'per_group_updates',updates_all);emit(ctx,'learning_rate',rates);emit(ctx,'zero_gradient_policy',{'policy':ctx.config['zero_gradient_policy'],'epsilon_added':False})

def checkpoint(ctx):
 import jax,jax.numpy as jnp,numpy as np
 from .technical_model import build_network,trajectory
 from .technical_support.observations import measure
 spec=ctx.read_json('network_spec');net,params,_=build_network(ctx,spec)
 def loss(p,factors):return jnp.mean(trajectory(net,p,spec['steps'],spec['dt_ms'],factors,retain=False)[-1,jnp.asarray(spec['loss_cells'])])
 full,fo=measure(ctx,jax.jit(jax.grad(lambda p:loss(p,None))),params)
 cp,co=measure(ctx,jax.jit(jax.grad(lambda p:loss(p,spec['checkpoint_lengths']))),params)
 f=jnp.concatenate([jnp.ravel(x)for x in jax.tree_util.tree_leaves(full)]);c=jnp.concatenate([jnp.ravel(x)for x in jax.tree_util.tree_leaves(cp)])
 tolerance=ctx.config['gradient_tolerance'];require(bool(jnp.allclose(f,c,rtol=tolerance['rtol'],atol=tolerance['atol'])),'full/checkpoint gradient mismatch')
 # Count actual transformed body callbacks in separate diagnostic invocations.
 # This is not an unperturbed hardware instruction profiler or peak-memory claim.
 full_events=[];checkpoint_events=[]
 def instrumented(p,factors,events):return jnp.mean(trajectory(net,p,spec['steps'],spec['dt_ms'],factors,retain=False,observed_body_events=events)[-1,jnp.asarray(spec['loss_cells'])])
 from .technical_support.observations import synchronize
 synchronize(jax.jit(jax.grad(lambda p:instrumented(p,None,full_events)))(params));jax.effects_barrier()
 synchronize(jax.jit(jax.grad(lambda p:instrumented(p,spec['checkpoint_lengths'],checkpoint_events)))(params));jax.effects_barrier()
 require(len(full_events)>=spec['steps']and len(checkpoint_events)>=len(full_events),'actual callback coverage')
 observations={'job_id':ctx.job['job_id'],'steps':spec['steps'],'instrument':'ordered_jax_debug_callback_in_separate_gradient_run',
               'full_body_events':len(full_events),'checkpoint_body_events':len(checkpoint_events),'additional_observed_body_events':len(checkpoint_events)-len(full_events),
               'native_instruction_or_recompute_parity':False,'observer_perturbs_execution':True}
 emit(ctx,'full_gradient',f);emit(ctx,'checkpoint_gradient',c);emit(ctx,'recompute_counts',observations);emit(ctx,'peak_memory',{'full':fo,'checkpoint':co,'whole_native_parent_peak':'external qualification remains required'})

def ratios(ctx):
 import statistics
 rows=ctx.read_json('hardware_observations');pairs=(('AMD','M3'),('A100','H100'));expected=[]
 for left,right in pairs:
  for operation in('forward','gradient'):
   for batch in(1,10,100,1000,10000):expected.append((left,right,operation,batch))
 require(len(rows)==20,'all twenty hardware comparison slots')
 by={tuple(r[k]for k in('left','right','operation','batch')):r for r in rows};require(set(by)==set(expected),'full hardware-workload inverse')
 result=[];unavailable=[]
 for key in expected:
  row=by[key]
  if row['status']=='unavailable':
   require(key==('AMD','M3','gradient',10000)and row['reason']=='M3_out_of_memory','only named historical unavailable coordinate')
   unavailable.append({'coordinate':list(key),'reason':row['reason']});continue
  require(row['status']=='observed'and row['left_repeats_ns']and row['right_repeats_ns'],'actual repeat vectors')
  require(all(type(v)is int and v>0 for v in row['left_repeats_ns']+row['right_repeats_ns']),'positive observed runtimes')
  require(row['left_source_identity']==row['right_source_identity']and row['left_workload']==row['right_workload'],'same complete workload and source')
  result.append({'coordinate':list(key),'ratio':statistics.mean(row['left_repeats_ns'])/statistics.mean(row['right_repeats_ns'])})
 require(len(result)==19 and len(unavailable)==1,'nineteen observed ratios and explicit missing slot')
 emit(ctx,'runtime_repeats',rows);emit(ctx,'ratio',result);emit(ctx,'hardware_workload',[{'coordinate':list(k),'workload':by[k].get('left_workload'),'source_identity':by[k].get('left_source_identity')}for k in expected]);emit(ctx,'availability_reason',unavailable)

def table(ctx):
 groups=('J03','J10','J11','J12','J14','J19','J22','J24','J27')
 rows=complete(ctx.read_json('whole_family_observations'),groups,'group');table=[];counts=[];resources=[]
 for group in groups:
  row=rows[group]
  require(row['schema']=='jaxley_original_family_capture_v1'and row['condition']==ctx.job['condition'],'actual same-condition parent capture')
  expected=ctx.config['selected_captures'][group]
  require(all(row[k]==expected[k]for k in('job_id','source_tree_sha256','receipt_pin')),'selected original capture identity')
  require(row['artifacts']and row['original_native_observation'],'original complete observation/artifact capture')
  ops=[m['value']for m in row['method_operations']if m['name']=='completed_operation'];actual={};coordinates=set()
  for op in ops:
   positive(op['count'],'observed logical operation count');key=(op['kind'],repr(op['coordinate']))
   require(key not in coordinates,'duplicate actual operation occurrence coordinate');coordinates.add(key)
   actual[op['kind']]=actual.get(op['kind'],0)+op['count']
  planned=ctx.config.get('planned_operation_counts',{}).get(group)
  status='observed_source_logical_counts'if ops else'unavailable_source_operation_profiler'
  if planned is not None:require(actual==planned,'planned versus actual complete operation denominator')
  table.append({'group':group,'observed_counts':actual if ops else None,'status':status,'source_tree_sha256':row['source_tree_sha256'],'job_id':row['job_id'],
                'physical_gradient_or_instruction_count':'not inferred from logical source operation count'})
  counts.append({'group':group,'operations':ops,'status':status});resources.append({'group':group,'original_native_observation':row['original_native_observation'],'receipt_pin':row['receipt_pin']})
 emit(ctx,'nine_table_rows',table);emit(ctx,'observed_operation_counts',counts);emit(ctx,'observed_resources',resources)

def notes(ctx):
 from .technical_notes import notes as consume_actual_products
 return consume_actual_products(ctx)

def run(ctx):
 admit(ctx)
 if ctx.group not in('J01','J32','J35'):
  import jax
  require(jax.config.jax_enable_x64==ctx.config['jax_enable_x64'],'actual selected precision')
 functions={'J01':architecture,'J02':solver,'J03':timing,'J04':network,'J05':network,'J06':transforms,'J07':optimize,'J08':checkpoint,'J32':ratios,'J35':table,'J36':notes}
 require(ctx.group in functions,'Allen has its own closed entrypoint')
 return functions[ctx.group](ctx)
