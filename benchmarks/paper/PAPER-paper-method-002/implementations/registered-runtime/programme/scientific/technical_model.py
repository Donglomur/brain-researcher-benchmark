"""Concrete Jaxley/NEURON constructors and exact-length full-state evolution.

Source based on the frozen experiments revision; v0.8.2 is prospective API
compatibility, not a recovered historical environment. Nothing runs on import.
"""
from .technical_support.contracts import require,network_spec
SITES={'n144':([0,34,54],[.8,.8,.8],0),'485574832':([0,60,68],[.2,.6,.6],160),
 '480351780':([0,66,71],[.2,.6,.6],220),'484559000':([0,35,37],[.2,.8,.8],155),
 '488683425':([0,61,63],[.2,.8,.8],198)}
def api():
 from importlib.metadata import version
 require(version('jaxley')=='0.8.2','unreviewed Jaxley API')
 import jaxley as jx
 return jx
def hh(cell,initial=-62.0):
 from jaxley.channels import HH
 cell.insert(HH());cell.set('axial_resistivity',1000.0);cell.set('v',initial)
 cell.set('HH_m',.074901);cell.set('HH_h',.4889);cell.set('HH_n',.3644787)
 return cell
def solver_pair(path,identity):
 """Original five-morphology radius/path-length join, independent simulators."""
 import numpy as np
 from neuron import h
 jx=api();branches,locs,rotation=SITES[identity]
 h.load_file('stdlib.hoc');h.load_file('import3d.hoc')
 for sec in list(h.allsec()):h.delete_section(sec=sec)
 reader=h.Import3d_SWC_read();reader.input(path);importer=h.Import3d_GUI(reader,False);importer.instantiate(None)
 sections=list(h.allsec())
 for sec in sections:sec.nseg=4
 radii=np.asarray([seg.diam/2 for sec in sections for seg in sec])
 from jaxley.io.swc import swc_to_jaxley
 _,lengths,_,_,_=swc_to_jaxley(path,max_branch_len=2000.0)
 section_lengths=np.asarray([sec.L for sec in sections]);mapping=[]
 for length in lengths:
  distances=np.abs(section_lengths-length);index=int(np.argmin(distances))
  require(float(distances[index])<2e-4,'original branch-length matching tolerance');mapping.append(index)
 cell=jx.read_swc(path,4,max_branch_len=2000.0,assign_groups=True)
 for branch in range(1,len(cell.comb_parents)):
  for comp in range(4):cell.branch(branch).comp(comp).set('radius',radii[4*mapping[branch]+comp])
 cell.rotate(rotation);hh(cell)
 for branch,loc in zip(branches,locs):cell.branch(branch).loc(loc).record()
 for sec in sections:
  sec.insert('hh');sec.Ra=1000.;sec.gnabar_hh=.120;sec.gkbar_hh=.036;sec.gl_hh=.0003;sec.ena=50.;sec.ek=-77.;sec.el_hh=-54.3
 def jaxley_run(amplitude):
  current=jx.step_current(3.,2.,amplitude,.025,20.)
  ds=cell.branch(0).loc(.2).data_stimulate(current,None)
  return jx.integrate(cell,delta_t=.025,data_stimuli=ds,voltage_solver='jaxley.stone')
 def neuron_run(amplitude):
  stim=h.IClamp(sections[0](.2));stim.delay=3.;stim.dur=2.;stim.amp=amplitude
  recs=[]
  for branch,loc in zip(branches,locs):
   v=h.Vector();v.record(sections[mapping[branch]](loc)._ref_v);recs.append(v)
  clock=h.Vector();clock.record(h._ref_t);h.dt=.025;h.finitialize(-62.);h.fcurrent()
  while h.t<20.:h.fadvance()
  return np.asarray(recs),np.asarray(clock)
 return cell,jaxley_run,neuron_run,{'branches':branches,'locations':locs,'neuron_section_map':mapping,'uniqueness':len(set(mapping))==len(mapping),'mapping_policy':'literal nearest section length; nonunique mappings disclosed'}
def benchmark_cell(ctx,kind):
 jx=api()
 if kind=='point':cell=hh(jx.Compartment())
 elif kind=='CA1':
  cell=hh(jx.read_swc(ctx.input_path('morphology:n144'),4,max_branch_len=2000.,assign_groups=True));cell.init_states()
 else:raise ValueError('benchmark cell kind')
 if kind=='CA1':
  for branch in(0,34,54):cell.branch(branch).loc(.85).record()
 else:cell.branch(0).loc(0.).record()
 for name in('HH_gNa','HH_gLeak','radius'):cell.make_trainable(name)
 return cell
def build_network(ctx,spec):
 """Explicit full adjacency; no inferred missing historical topology or seeds."""
 import numpy as np
 jx=api();from jaxley.connect import connect
 from jaxley.synapses import IonotropicSynapse,TanhRateSynapse
 network_spec(spec,ctx.group,ctx.config['profile']);cells=[]
 from .technical_support.contracts import bounded_extents
 bounded_extents(ctx,{'selected_construction_peak_estimate':spec['construction_memory_bytes'],'full_adjacency_bytes':spec['expected_edges']*6*8,'full_weight_bytes':spec['expected_edges']*8})
 if spec.get('recipe')=='released_large_notebook':return literal_large_network(ctx,spec)
 for row in spec['morphologies']:
  ctx.checkpoint()
  if row['kind']=='swc':cell=jx.read_swc(ctx.input_path(row['logical']),int(row['nseg']),max_branch_len=float(row['max_branch_len']),assign_groups=True)
  elif row['kind']=='three_branch':
   require(row['parents']==[-1,0,0]and len(row['nseg'])==3,'explicit three-branch morphology')
   branches=[jx.Branch(jx.Compartment(),ncomp=int(n))for n in row['nseg']]
   cell=jx.Cell(branches,parents=row['parents'])
  else:raise ValueError('closed morphology kind')
  hh(cell,-65.);cell.init_states()
  for name,value in row['parameters'].items():
   require(name in('length','radius','axial_resistivity','capacitance','HH_gNa','HH_gK','HH_gLeak'),'closed morphology parameter')
   cell.set(name,value)
  cells.append(cell)
 net=jx.Network(cells)
 adjacency=ctx.read_array(spec['adjacency_logical'])
 require(adjacency.shape==(spec['expected_edges'],6),'complete edge (precell,branch,comp,postcell,branch,comp) matrix')
 require(adjacency.dtype.kind in'iu','integer edge identities')
 synapse=IonotropicSynapse()if spec['synapse']=='IonotropicSynapse'else TanhRateSynapse()
 # Literal connect is used for every supplied edge; no Bernoulli replacement.
 for row in adjacency:
  ctx.checkpoint();a,b,c,d,e,f=map(int,row)
  require(0<=a<len(cells)and 0<=d<len(cells),'edge cell identity')
  connect(net.cell(a).branch(b).comp(c),net.cell(d).branch(e).comp(f),synapse)
 require(len(net.edges)==spec['expected_edges'],'complete constructed connectivity')
 weights=ctx.read_array(spec['weights_logical'])
 require(weights.shape==(len(net.edges),),'one actual weight per edge')
 net.set(spec['synapse']+'_gS',weights)
 for cell_index,(branch,comp)in enumerate(spec['record_compartments']):net.cell(cell_index).branch(branch).comp(comp).record()
 currents=ctx.read_array(spec['currents_logical'])
 require(currents.shape==(len(spec['stimulus_compartments']),spec['steps']),'full stimulus clock')
 for row,current in zip(spec['stimulus_compartments'],currents):net.cell(row[0]).branch(row[1]).comp(row[2]).stimulate(current)
 for name in spec['trainable_families']:
  if name.endswith('_gS'):getattr(net,spec['synapse']).edge('all').make_trainable(name)
  else:net.cell('all').branch('all').comp('all').make_trainable(name)
 params=net.get_parameters();net.to_jax()
 return net,params,adjacency
def literal_large_network(ctx,spec):
 """Released size_factor=1, seed0, extra cell, explicit morphology-order intake.

 The original os.walk ordering is not recovered by sorting filenames. Its exact
 selected order is an input prerequisite and remains a historical-source gap.
 """
 import numpy as np
 jx=api();from jaxley.connect import fully_connect,sparse_connect
 from jaxley.synapses import IonotropicSynapse
 require(ctx.group=='J04'and ctx.config['profile']=='source_literal','released recipe is not paper2000 parity')
 require(spec['size_factor']==1 and spec['dt_ms']==.025,'literal size_factor and timestep')
 ordered=ctx.read_json('original_morphology_walk_order');cells=[];selection=[]
 require(ordered and all(r['selected_walk_path_length']>32 and r['selected_walk_path_length']<40 for r in ordered),'actual original walk-order descriptors')
 for row in ordered:
  cell=jx.read_swc(ctx.input_path(row['logical']),2,max_branch_len=500.)
  accepted=cell.total_nbranches<280
  selection.append({'logical':row['logical'],'branches':cell.total_nbranches,'accepted':accepted})
  if accepted:cells.append(cell)
 require(cells,'no selected original CA1 cells');cells=cells+[cells[0]]
 require(len(cells)==spec['cells'],'actual extra-cell count conflicts with selected extent')
 net=jx.Network(cells);np.random.seed(0)
 for layer in range(4):
  pre=net.cell(list(range(10*layer,10*(layer+1))));post=net.cell(list(range(10*(layer+1),10*(layer+2))))
  fully_connect(pre,post,IonotropicSynapse());sparse_connect(pre,post,IonotropicSynapse(),.58)
 fully_connect(net.cell(list(range(40,50))),net.cell(50),IonotropicSynapse())
 from jaxley.channels import HH
 net.insert(HH());net.set('v',-65.);net.init_states();net.set('IonotropicSynapse_s',0.)
 net.set('IonotropicSynapse_gS',.00003*20);net.IonotropicSynapse.edge(list(range(len(net.edges)-10,len(net.edges)))).set('IonotropicSynapse_gS',.0001*20)
 for cell_index in range(len(cells)):net.cell(cell_index).branch(1).comp(0).record()
 # Source current amplitudes/locations are supplied with the full original
 # caller coordinates, never inferred from an unavailable morphology tree.
 currents=ctx.read_array(spec['currents_logical'])
 require(currents.shape==(len(spec['stimulus_compartments']),spec['steps']),'full literal stimulus extent')
 for row,current in zip(spec['stimulus_compartments'],currents):net.cell(row[0]).branch(row[1]).comp(row[2]).stimulate(current)
 for name in spec['trainable_families']:
  if name.endswith('_gS'):net.IonotropicSynapse.edge('all').make_trainable(name)
  else:net.cell('all').branch('all').comp('all').make_trainable(name)
 require(len(net.edges)==spec['expected_edges'],'actual literal synapse count, not quoted1M')
 node_columns=['global_cell_index','local_branch_index','local_comp_index']
 require(set(node_columns)<=set(net.nodes.columns),'complete node identity columns')
 pre=net.nodes.loc[net.edges['pre_global_comp_index'],node_columns].to_numpy()
 post=net.nodes.loc[net.edges['post_global_comp_index'],node_columns].to_numpy()
 adjacency=np.concatenate([pre,post],axis=1);ctx.record('literal_morphology_selection',selection)
 return net,net.get_parameters(),adjacency
def trajectory(net,params,steps,dt,checkpoints=None,retain=True,observed_body_events=None,literal_padding=False):
 """Exact step count; unlike integrate's padded tail, no unobserved evolution."""
 import jax,jax.numpy as jnp
 from jaxley.integrate import build_init_and_step_fn
 from jaxley.utils.jax_utils import nested_checkpoint_scan
 from math import prod
 net.to_jax();init,step=build_init_and_step_fn(net,voltage_solver='jaxley.stone',solver='bwd_euler')
 state,all_params=init(params,delta_t=dt)
 external={k:v.T for k,v in net.externals.items()}
 require(all(v.shape[0]==steps for v in external.values()),'exact unpadded external clock')
 executed_steps=steps
 if checkpoints is not None and literal_padding:
  executed_steps=prod(checkpoints);require(executed_steps>=steps,'source checkpoint coverage')
  external={k:jnp.concatenate([v,jnp.zeros((executed_steps-steps,)+v.shape[1:],dtype=v.dtype)],axis=0)for k,v in external.items()}
 rec_indices=net.recordings.rec_index.to_numpy();rec_states=net.recordings.state.to_numpy()
 # Report physical dynamical states, not redundant cached channel currents.
 names=sorted(set(['v']+[k for channel in net.channels for k in channel.channel_states]+list(net.synapse_state_names)))
 def flatten(s):return jnp.concatenate([jnp.ravel(s[name])for name in names])
 def readout(s):return jnp.asarray([s[k][i]for k,i in zip(rec_states,rec_indices)])
 def body(s,x):
  if observed_body_events is not None:
   # Local diagnostic, intentionally separate from performance timing runs.
   jax.debug.callback(lambda:observed_body_events.append(1),ordered=True)
  s=step(s,all_params,x,delta_t=dt)
  return s,(flatten(s),readout(s))if retain else readout(s)
 if checkpoints is None:final,output=jax.lax.scan(body,state,external,length=steps)
 else:
  require(prod(checkpoints)==executed_steps,'checkpoint factors must cover exact full steps')
  final,output=nested_checkpoint_scan(body,state,external,length=executed_steps,nested_lengths=checkpoints)
 if retain:
  states,voltage=output
  return jnp.concatenate([flatten(state)[None,:],states]),jnp.concatenate([readout(state)[None,:],voltage[:steps]]),names
 return output[:steps]
