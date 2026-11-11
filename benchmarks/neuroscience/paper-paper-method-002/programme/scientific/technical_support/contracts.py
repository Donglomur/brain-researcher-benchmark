"""Closed technical job admission, no numerical imports or execution."""
GROUPS=('J01','J02','J03','J04','J05','J06','J07','J08','J11','J32','J35','J36')
MORPHOLOGIES=('n144','485574832','480351780','484559000','488683425')
ALLEN=('485574832','488683425','480353286','473601979')
PRODUCTS={
'J01':('architecture_source_map',),
'J02':('Jaxley_voltage','NEURON_voltage','spike_times','spike_amplitudes','clock'),
'J03':('cold_compile_times','warm_times','peak_memory','gradient_times'),
'J04':('full_state','voltage','parameter_gradient','connectivity','timing_memory'),
'J05':('full_state','parameter_gradient','selected_12_loss','connectivity','timing_memory'),
'J06':('physical_parameters','untransformed_parameters','derivative','log_Jacobian','bounds'),
'J07':('loss_gradient','per_group_updates','learning_rate','zero_gradient_policy'),
'J08':('full_gradient','checkpoint_gradient','recompute_counts','peak_memory'),
'J11':('full_voltage','soft_DTW','spike_count','spike_times','spike_amplitudes','best_final_hof_lineage','resource_trajectory'),
'J32':('runtime_repeats','ratio','hardware_workload','availability_reason'),
'J35':('nine_table_rows','observed_operation_counts','observed_resources'),
'J36':('eight_notes_source_map','native_method_tests')}
NUMERIC={
 'J02':('Jaxley_voltage','NEURON_voltage','spike_times','spike_amplitudes'),
 'J04':('full_state','voltage','parameter_gradient','connectivity'),
 'J05':('full_state','parameter_gradient','selected_12_loss','connectivity'),
 'J06':('physical_parameters','untransformed_parameters','derivative','log_Jacobian','bounds'),
 'J08':('full_gradient','checkpoint_gradient')}
def require(condition,message):
 if not condition:raise ValueError(message)
def positive(value,name):
 require(type(value)is int and value>0,name);return value
def complete(rows,expected,key):
 require(type(rows)is list and len(rows)==len(expected),'complete '+key+' cardinality')
 observed=[r[key]for r in rows]
 require(len(set(observed))==len(observed)and set(observed)==set(expected),'complete unique '+key)
 return {r[key]:r for r in rows}
def admit(ctx):
 require(ctx.group in GROUPS and ctx.action=='run','closed technical action')
 require(set(ctx.products)==set(PRODUCTS[ctx.group]),'complete scientific products')
 require(all(p['format']==('jaxley-flat-numeric-v1'if name in NUMERIC.get(ctx.group,())else'json')for name,p in ctx.products.items()),'exact technical output formats')
 c=ctx.config
 require(c.get('profile')in('source_literal','prospective_paper'),'explicit source/paper profile')
 require(c.get('jaxley_api')=='0.8.2','selected prospective API version')
 require(c.get('historical_parity')is False,'original environment remains unverified')
 require(type(c.get('jax_enable_x64'))is bool,'explicit numerical precision')
 return c
def network_spec(spec,group,profile):
 require(type(spec)is dict and group in('J04','J05','J07','J08'),'network schema')
 n=positive(spec['cells'],'cell count');positive(spec['steps'],'step count')
 for field in('expected_edges','expected_state_size','expected_gradient_size','construction_memory_bytes'):positive(spec[field],field)
 require(type(spec['checkpoint_lengths'])is list and spec['checkpoint_lengths']and all(type(x)is int and x>0 for x in spec['checkpoint_lengths']),'complete checkpoint factors')
 require(spec['dt_ms']==0.025,'selected timestep')
 require(type(spec['morphologies'])is list and len(spec['morphologies'])==n,'full morphology identity sequence')
 require(len(spec['record_compartments'])==n,'one explicit voltage compartment per cell')
 require(len(set(spec['loss_cells']))==len(spec['loss_cells'])and all(type(x)is int and 0<=x<n for x in spec['loss_cells']),'loss cell identities')
 require(spec['trainable_families']==['HH_gNa','HH_gK','HH_gLeak',spec['synapse']+'_gS'],'full parameter family roster')
 if group=='J04'and profile=='prospective_paper':
  require((n,spec['steps'],spec['expected_edges'],spec['expected_state_size'],spec['expected_gradient_size'])==(2000,8000,1000000,3920000,3200000),'full J04 paper demand')
 if group=='J05':
  require(profile=='prospective_paper','J05 exact historical generator is unavailable')
  require(n==12000 and spec['expected_edges']==25400000 and len(spec['loss_cells'])==12,'full J05 demand')
  require(spec['synapse']=='TanhRateSynapse','J05 tanh-rate mechanism')
  require(all(x['kind']=='three_branch'for x in spec['morphologies']),'J05 all three-branch cells')
 if group=='J04':require(spec['synapse']=='IonotropicSynapse','original detailed-network synapse mechanism')
 return spec
def bounded_extents(ctx,counts):
 total=sum(positive(v,k)for k,v in counts.items())
 require(total<=ctx.limits['array_memory_bytes'],'whole source allocations not admitted')
 ctx.record('allocation_demand_bytes',counts)
def emit(ctx,name,value):
 if ctx.products[name]['format']=='json':ctx.emit_json(name,value)
 else:ctx.emit_numeric(name,value)
