"""Complete job-census qualification; unresolved original grids are never guessed."""
from .custody import need,pin,encode
from .guard import distinct,integer,real,RequiredUnscorable
from .kernels import KERNELS

def validate(scope,census):
    need(census['schema']=='critical_init_qualified_full_census_v1','full externally qualified census')
    need(census['scope_digest']==scope.digest,'same immutable scope')
    need(census['canonical_id']=='PAPER-FIND-050','same benchmark')
    need(census['original_grid_evidence'] and census['original_seed_evidence']and census['supplement_evidence'],'original complete grids, RNG hierarchy and supplements')
    scope.whole_plan(census)
    need(set(census['gate_ids'])=={g['id']for g in scope.gates},'all17 gates retained')
    jobs=census['jobs'];ids=distinct([j['id']for j in jobs]);seen=set()
    by_panel={p:[]for p in scope.panel_ids}
    roles=set()
    for j in jobs:
        need(j['kind']in ('numeric','native','artifact'),'actual fixed role type')
        need(j['panels']and set(j['panels'])<=set(by_panel),'producer panel support')
        need(set(j['dependencies'])<=seen,'topologically ordered actual dependencies')
        seen.add(j['id']);roles.add(j['scientific_role'])
        for p in j['panels']:by_panel[p].append(j['id'])
        need(j['variant']in ('paper_independent','held_author_source','corrected_scientific','prospective'),'separate variants')
        need(j['full_original_support']is True and j['support_identity']and j['expected_outputs'],'complete declared scientific outputs')
        integer(j['logical_array_bytes'],1)
        real(j['limits']['seconds'],0);real(j['limits']['cpu_seconds'],0);integer(j['limits']['memory_bytes'],1)
        need(j['limits']['seconds']>0 and j['limits']['memory_bytes']>0 and j['limits']['cpu_seconds']>0,'selected finite whole-job resources')
        if j['kind']=='numeric':need(j['kernel']in KERNELS,'actual implemented numeric kernel')
        if j['kind']=='native':
            need(j['native_entry_pin']and j['native_import_closure']and j['native_command'],'complete original native entry, not a callback stub')
            need(j['native_abi']['version']=='critical-init-nested-native-abi-v1','qualified explicit nested native arguments')
    for panel,entry in census['panels'].items():
        if entry['status']=='bound':need(entry['jobs']==by_panel[panel],'exact full producer-to-panel incidence')
    obligations=census['support_obligations']
    # These are lower-bound identities, never a claim to reconstruct unknown full job counts.
    need(obligations['core29']==[s['session_id']for s in scope.sessions],'all29 source recordings')
    need(len(set(obligations['facemap_session_ids']))==16 and len(set(obligations['facemap_mouse_ids']))==12,'full16/12 exact roster')
    need(len(set(obligations['external_session_ids']))==6,'all6 source task recordings')
    need(len(set(obligations['reduced_rate_calcium_ids']))==26,'all26 original reduction producer rows')
    need(set(obligations['reduced_rate_calcium_ids'])=={s['session_id']for s in scope.sessions if s['modality']=='calcium'},'exact26 identity join')
    need(obligations['time_keep']==[50+200*i for i in range(19)]+[4000],'exact full20 source temporal grid')
    fractions=[.01+.05*i for i in range(20)]+[1.0]
    need(len(obligations['neuron_fraction'])==21 and all(abs(a-b)<1e-12 for a,b in zip(obligations['neuron_fraction'],fractions)),'exact full21 source neuron grid')
    need(set(obligations['state_session_ids'])=={s['session_id']for s in scope.sessions if s.get('hasrunning_flag_as_source')},'all8 source state flags and eligibility dispositions')
    expected_memory={(task,dynamics,readout,i)for task in ('binary','zero_shot','subspace')for dynamics in ('symmetric','nonsymmetric','relu')for readout in ('fixed','random_time')for i in range(20)}
    actual_memory={(x['task'],x['dynamics'],x['readout'],x['replicate'])for x in obligations['memory_curves']}
    need(len(obligations['memory_curves'])==360 and actual_memory==expected_memory,'all360 original memory curves, not only one method')
    grid=obligations['memory_delay_grid']
    import numpy as np
    need(set(grid)=={'regular','aligned'},'both recovered source delay grids')
    need(grid['regular']==np.linspace(60,1500,51)[:-1].astype('int32').tolist()and grid['aligned']==np.linspace(60,4500,51)[:-1].astype('int32').tolist(),'all50 exact delays in both original source regimes')
    need(obligations['memory_paper_aligned_examples']==2000 and obligations['memory_literal_aligned_examples']==600,'both conflicting original supports retained')
    need(obligations['memory_paper_echo_gain']==1.4 and obligations['memory_literal_echo_gain']==1.35,'paper and notebook gain variants separate')
    need(obligations['full_legacy_janelia']and obligations['full_legacy_london'],'complete original legacy supports')
    need(set(census['required_scientific_roles'])<=roles,'all original scientific source roles have concrete producers')
    return {'census':pin(encode(census)),'jobs':len(jobs),'panels':76,'scientifically_qualified':False}

def require_executable(census):
    held={p:r for p,r in census['panels'].items()if r['status']!='bound'}
    if held:raise RequiredUnscorable('G08','Whole original programme cannot execute while mandatory producer roles are missing',held)

