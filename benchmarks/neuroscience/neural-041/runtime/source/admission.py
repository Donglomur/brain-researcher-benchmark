"""Source-owned admission; independent qualification producer is not supplied.

The programme remains inactive until a separately appointed evaluator signs the
exact profile/source/protocol/gate evidence, under an out-of-band trusted public
key. The key and attestation have not been created or inspected in BUILD ONLY.
"""
from pathlib import Path
from core import need,encoded,pin,capture,parse,disjoint,descriptor,integer

GATES=('rights_and_source_snapshot','complete44_session36_patient_join','clinical_bundle_and_trial_masks',
    'full_anatomy_and_modality_dispositions','load_and_event_schema','source_clock_units_and_alignment',
    'published_preprocessing_and_interpolation','outcome_blind_eligibility','source_format_and_hdf5_limits',
    'equal_window_and_leakage_audit','fold_and_train_only_processing','reference_competence','independent_numerical_agreement',
    'immutable_source_and_image','daemon_namespace_and_descendant_retirement','read_only_mount_and_target_isolation',
    'hard_memory_pids_cpu_and_wall','whole_output_and_log_quota','whole_study_resource_feasibility',
    'external_physical_io_and_startup_accounting','agent_tools_and_model_cost_accounting','prediction_writer_closure',
    'protected_complete_target_barrier','independent_qualification_issuer')

def verify_signed(profile,signature,public_key):
    need(type(public_key)is bytes and len(public_key)==32 and type(signature)is bytes and len(signature)==64,'independent Ed25519 authority material')
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    Ed25519PublicKey.from_public_bytes(public_key).verify(signature,encoded(profile))
    evidence=profile['qualification_evidence'];need(set(evidence)==set(GATES),'all qualification gates explicitly joined')
    for name,record in evidence.items():
        need(record['status']=='qualified' and record['independent_issuer'] and record['evidence'],'actual independently signed evidence, never source-only status')
        for desc in record['evidence']:descriptor(desc['pin'])
    need(profile['task']=='NEURAL-041' and profile['study'],'task-bound signed selection')
    roots=[profile[k] for k in('source_root','operations_root','journal_root','report_root','views_root')]+[profile['engine']['output_root'],profile['preparation_engine']['output_root']]
    for i,a in enumerate(roots):
        for b in roots[i+1:]:need(disjoint(a,b),'physical alias qualification plus lexical root separation')
    need(profile['engine']['gpu_ids']==profile['preparation_engine']['gpu_ids']==[],'canonical CPU_workstation_bounded resource class')
    need(profile['engine']['whole_cpu_ns']+profile['preparation_engine']['whole_cpu_ns']<=profile['whole_native_cpu_ns'],'prospective aggregate preparation plus all-cell CPU ceiling')
    need(profile['engine']['whole_output_quota_bytes']+profile['preparation_engine']['whole_output_quota_bytes']<=profile['whole_native_output_bytes'],'prospective aggregate native output quota')
    need(profile['engine']['whole_gpu_device_seconds']+profile['preparation_engine']['whole_gpu_device_seconds']<=profile['whole_gpu_device_seconds'],'prospective aggregate GPU device-time reservation')
    need(profile['engine']['clock_domain']==profile['preparation_engine']['clock_domain']=='qualified_shared_host_monotonic','one original shared native/host clock domain')
    need(set(profile['methods'])=={m+'/'+a for m in('frozen_program','case_adaptive_equal_inputs_tools_compute') for a in('numeric','agent_plus_decoder')},'complete participant programme slots')
    for item in list(profile['methods'].values())+[profile['fixed_decoder']]:descriptor(item['pin'])
    return profile

def source_capture(profile,budget):
    files=profile['source'];need(type(files)is dict and files and len(files)<=128,'finite complete source inventory')
    bodies={}
    for name,desc in files.items():
        need(name.endswith('.py') and '/' not in name and '\\' not in name and not name.startswith('.'),'exact source member')
        bodies[name],_=capture(Path(profile['source_root'])/name,desc,1<<20,budget,readonly=True)
    # Root's independently authenticated bootstrap must import these captured
    # bodies. Matching a source file after an earlier unsafe import is not proof.
    return bodies
