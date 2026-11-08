"""Post-exit admission for an independently captured complete controller result.

Called only by a separate trusted launcher after the entry has exited. No source
here launches it, invents measurements, or converts a provisional result into a
scientific/reference-competence qualification.
"""
from ach_util import need,pin,pin_bytes,integer,exact_fields,require_pin,decode

def admit_outer(raw_stdout,raw_stderr,observation,selected,source_pin,selection_pin):
    require_pin(selection_pin)
    exact_fields(observation,('selection_pin','source_pin','origin_ns','producer_finished_ns','observation_finished_ns',
        'exit_code','natural_exit','forced_stop','descendants_closed','stream_eof','stdout_pin','stderr_pin',
        'scope_roster_pin','accounting_evidence_pin','source_custody_evidence_pin','unknown','resources'),
        'exact independent external complete entry/exit observation')
    need(observation['selection_pin']==selection_pin and observation['source_pin']==source_pin and
         observation['origin_ns']==selected['origin_ns'],'same independently selected source and original origin')
    need(type(observation['exit_code']) is int and observation['exit_code']==0 and
         all(observation[k] is True for k in ('natural_exit','descendants_closed','stream_eof')) and
         observation['forced_stop'] is False and observation['unknown']==[],
         'independent final natural-zero EOF descendants and complete physical facts')
    need(selected['origin_ns']<=integer(observation['producer_finished_ns'])<selected['closeout_ns'] and
         observation['producer_finished_ns']<=integer(observation['observation_finished_ns'])<selected['outer_ns'],
         'producer metadata closure and external observation have distinct original cutoffs')
    need(pin_bytes(raw_stdout)==observation['stdout_pin'] and pin_bytes(raw_stderr)==observation['stderr_pin'],
         'complete exact actual entry output streams')
    for k in ('scope_roster_pin','accounting_evidence_pin','source_custody_evidence_pin'):require_pin(observation[k])
    resources=observation['resources'];exact_fields(resources,('read_bytes','write_bytes','retained_bytes','live_bytes'),'whole measured byte dimensions')
    for k,v in resources.items():need(integer(v)<=selected['physical_total_limits'][k],'whole independently measured physical envelope')
    result=decode(raw_stdout.rstrip(b'\n'),selected['entry_output_bytes'])
    need(result.get('source_work_complete') is True and result.get('external_final_natural_zero_required') is True and
         result.get('scientific_qualified') is False,'complete provisional source computation only')
    return {'controller_result':result,'outer_observation_pin':pin(observation),'full_source_run_completed':True,
        'scientific_qualified':False,'reference_competence_qualified':False,'whole_paper_reproduced':False,
        'remaining_scientific_admission':'independent actual input/method/reference-competence review'}
