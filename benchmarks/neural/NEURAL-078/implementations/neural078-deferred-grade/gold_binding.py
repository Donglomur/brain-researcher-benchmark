"""Selected admitted-reference metadata joins; never opens a gold body."""
from bound_io import need,parse,capture,identity
from admission import same,only

NAMES=('TARGET_BINDING.json','WORKER_COMPLETION.json','RECOVERY_ATTEMPT.json','RECOVERY_COMPLETION.json')

def validate(raw,rows,people,scorer_pins):
    b,w,a,r=(parse(raw[n]) for n in NAMES)
    gold=only(rows['private/reference/GOLD.json']);binding_pin=only(rows['private/reference/TARGET_BINDING.json'])
    need(b['schema']=='neural078_private_target_binding_v1' and same(b['gold'],dict(name='GOLD.json',**gold)),'Original selected gold identity')
    packets=[dict(person=p,name=p+'.npz',**only(rows['public/data/'+p+'.npz'])) for p in people]
    need(same(b['packets'],packets),'All eight gold/public packet identities')
    need(b['protocol_sha256']==rows['public/PROTOCOL.json']['sha256'],'Original protocol identity')
    for name,p in scorer_pins.items():need(same(b['frozen_sources'][name],p),'Unchanged frozen scorer in target binding')
    need(b['empirical_EEG_contrasts_computed'] is True and b['new_scientific_choices'] is False and b['unsupported_nulls_preserved'] is True and b['host_admission_required'] is True,'Original fixed descriptive answer semantics')
    need(type(b['model_fits'])is int and b['model_fits']==0 and type(b['candidate_or_method_evaluations'])is int and b['candidate_or_method_evaluations']==0,'No original model/candidate evaluation')
    need(w['schema']=='neural078_answer_worker_completion_v1' and w['source_sha256']==b['answer_source_sha256'] and w['host_admission_required'] is True and w['not_a_candidate_evaluation'] is True,'Original answer worker provenance')
    need(same(w['files'],[dict(name='GOLD.json',**gold),dict(name='TARGET_BINDING.json',**binding_pin)]),'Original answer worker complete outputs')
    need(a['schema']=='neural078_answer_recovery_attempt_v2' and a['success'] is True and a['status']=='private_answer_recovered_from_existing_bytes','Subsequent admitted recovery required')
    for doc in (a,r):
        need(doc['original_host_admission_success'] is False and doc['original_cleanup_within180seconds_proven'] is False and doc['new_answer_computation'] is False and doc['new_empirical_calculation'] is False,'Preserve original failed admission and recovery limits')
    need(a['original_failure_preserved'] is True and a['model_or_candidate_evaluation'] is False,'Recovery preserves original failed history')
    need(r['schema']=='neural078_answer_recovery_completion_v2' and r['subsequent_metadata_recovery'] is True and r['recovery_source_sha256']==a['source_sha256'] and same(r['recovery_record'],identity(raw['RECOVERY_ATTEMPT.json'])),'Admitted recovery record/source join')
    need(same(r['gold'],dict(name='GOLD.json',**gold)) and same(a['outputs']['gold'],r['gold']) and same(a['outputs']['binding'],dict(name='TARGET_BINDING.json',**binding_pin)) and same(a['outputs']['worker_completion'],identity(raw['WORKER_COMPLETION.json'])),'Complete recovered output pins')
    return gold

def read(package,rows,people,scorer_pins):
    raw={n:capture(package/'private/reference'/n,32768,rows['private/reference/'+n]) for n in NAMES}
    return raw,validate(raw,rows,people,scorer_pins)
