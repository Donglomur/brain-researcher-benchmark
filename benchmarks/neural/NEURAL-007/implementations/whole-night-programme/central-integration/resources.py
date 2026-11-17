"""Prospective full-workload observer allocations, not measured feasibility."""
from .core import need, integer, number


def admit(profile, configuration, grant, source_bytes, endpoints):
    keys={'read_bytes','write_bytes','retained_bytes','memory_bytes','cpu_seconds','tree_members','max_member_bytes',
        'json_depth','json_nodes','http','closeout_seconds','read_bytes_per_second','member_seconds',
        'fixed_closeout_seconds','parent_retained_bytes','free_floor_bytes','view_cache_bytes'}
    need(type(profile) is dict and set(profile)==keys,'Complete selected central resource profile')
    for key in keys-{'http','member_seconds'}: integer(profile[key],1)
    need(number(profile['member_seconds']) and profile['member_seconds']>0,'Explicit per-member observation timeout allocation')
    http=profile['http']; need(type(http) is dict and set(http)=={'header_bytes','body_bytes','rows'},'Complete daemon response bounds')
    for value in http.values(): integer(value,1)
    need(http['header_bytes']>=65536 and http['body_bytes']>=1048576,'Whole supported HTTP envelope allocation')
    maximum=9405 if configuration['frozen_profile']=='generic_current_person' else 4749
    limits=configuration['phase_limits']
    phase_members=max(v['max_files']+v['max_directories']+2*v['max_cli_calls']+100 for v in limits.values())
    members=maximum*phase_members+312*(2*256+100)+10000
    need(profile['tree_members']>=members,'Complete all-phase output/event/directory allocation')
    largest=max(16*1024*1024,max(v['manifest_bytes']+v['inventory_bytes']+2048*v['max_files'] for v in limits.values()))
    need(profile['max_member_bytes']>=largest and profile['json_depth']>=64
         and profile['json_nodes']>=max(2000000,16*phase_members),'Complete metadata representation allocation')
    pools=grant['tracked_io_envelopes']; parent_writes=pools['controller_write_bytes']+pools['native_write_bytes']+312*pools['model_context_write_bytes']
    api_wire=len(endpoints)*2*(http['header_bytes']+8*http['body_bytes']+65536)
    read_min=256*1024*1024+3*parent_writes+api_wire
    # All output bodies stay in their original tree. Central retains only the
    # staged source, bounded streams, descriptors and projected inventories.
    central_write_min=source_bytes+4*1024*1024+2048*profile['tree_members']+2*len(endpoints)*(http['body_bytes']+http['rows']*256)+16*1024*1024
    stage_max=3789 if configuration['frozen_profile']=='generic_current_person' else 3189
    # Exact canonical VIEW/BINDING schemas have fixed ASCII fields, UUID32
    # handles, original153-night support and signed64-bit physical extents.
    # auxiliary.stage_pair enforces these complete bounds before retention.
    # Reserve every stage, without relying on accidental deduplication.
    view_cache_min=stage_max*(4096+153*1536)
    need(profile['view_cache_bytes']>=view_cache_min,'Full stage encoded-cache allowance, no reduced cohort')
    # Two stat inventories can coexist, plus full/relative path strings, pin
    # and read-count indices, phase maps, object headers and dictionary slack.
    # Runtime allocator/stdlib qualification is still required: this is a
    # conservative selected address-space provision, not a universal RSS proof.
    memory_min=128*(profile['max_member_bytes']+http['body_bytes'])+32768*profile['tree_members']+512*profile['json_nodes']+profile['view_cache_bytes']+128*1024*1024
    need(profile['read_bytes']>=read_min and profile['write_bytes']>=central_write_min
         and profile['retained_bytes']>=central_write_min and profile['memory_bytes']>=memory_min,
         'Full complete source/metadata/stream memory and retained allocation, no arbitrary small cap')
    need(profile['parent_retained_bytes']>=parent_writes,'Whole original parent retained allocation remains distinct')
    seconds=profile['read_bytes']/profile['read_bytes_per_second']+profile['tree_members']*profile['member_seconds']+profile['fixed_closeout_seconds']
    need(profile['closeout_seconds']>=seconds,'Prospective complete-readback timeout derived from selected ceilings')
    return {'native_phase_maximum':maximum,'model_contexts':312,'candidate_inferences':936,'reference_inferences':1170,
        'maximum_api_requests':2*len(endpoints),'derived_read_minimum':read_min,'derived_central_write_minimum':central_write_min,
        'derived_address_space_minimum':memory_min,'derived_view_cache_minimum':view_cache_min,'derived_closeout_seconds':seconds,'measured_feasible':False,
        'physical_io_and_rss_known':False,'scientific_scope_reduced':False}
