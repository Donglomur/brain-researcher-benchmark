"""Owner-pinned relocatable bridge to the unchanged full248 task."""
from pathlib import Path
from common import need,read,decode,pin,admit_pin,write,encode
from packet import just_pin
from docker_owner import IMAGE
from rounding import from_score
from portable_config import current,state

def selection(value):
    need(type(value) is dict and set(value)=={'schema','config_sha256','private_local_delivery_selected',
         'transient_reference_use_selected','model_calls','programs','comparator_calibration'},
         'closed portable owner selection')
    need(value['schema']=='tms_portable_selected_reconstruction_v1'
         and value['config_sha256']==state()['sha256']
         and value['private_local_delivery_selected'] is True
         and value['transient_reference_use_selected'] is True
         and type(value['model_calls']) is int and value['model_calls']==0
         and type(value['comparator_calibration']) is bool,'explicit portable private selection')
    need(type(value['programs']) is dict and set(value['programs'])=={'A','B'},'both immutable programs')
    for entry in value['programs'].values():admit_pin(just_pin(entry),262144)
    return value

def prepare(value,*,root,source_bodies,source_root,budget):
    selection(value);cfg=current();a=cfg['assets'];ref=cfg['reference']
    # This review is an owner-selected authority artifact, not a self-issued
    # proof or candidate-visible capability. The immutable image remains fixed.
    read(a['runtime_review']['path'],just_pin(a['runtime_review']),budget,1048576)
    need(cfg['runtime']['image']==IMAGE,'unchanged admitted candidate image')
    program={'path':str(source_root/'candidate/comparator.py'),**pin(source_bodies['candidate/comparator.py'])}
    if value['comparator_calibration']:
        need(value['programs']=={'A':program,'B':program},'fixed competent calibration programs')
    delivery={'schema':'tms_p16_private_delivery_selection_v1',
              'private_delivery_selected':True,'image_content_selected':True,'image':IMAGE,
              'projection_receipt':a['projection_receipt'],
              'projection_original_outcome':a['projection_outcome'],
              'projection_independent_review':a['projection_review']}
    return {'schema':'tms_method_specified_two_arm_owner_plan_v1','root':str(root),
            'input_manifest':a['input_manifest'],'input_values':a['input_values'],'delivery':delivery,
            'reference_selection':{'schema':'tms_p16_authentic_assessment_selection_v1',
              'descriptor':ref['descriptor'],'source_lock_sha256':ref['source_lock_sha256'],
              'transient_use_selected':True,'input_projection_selected':True,
              'image_content_selected':True,'private_delivery_selected':True},
            'programs':value['programs'],'execution_selected':True,'model_calls':0,
            'source_profile':'original_scientific_operands'}

def diagnostics(root,*,budget,calibration=False):
    """After both candidates close. Calibration is transport/schema admission.

    Equal valid outputs need not be numerically accurate. Full continuous errors
    and rounding outcomes remain private and unchanged, without a new threshold.
    """
    need(type(calibration) is bool,'typed_calibration_mode')
    result=[];closed_bodies=[]
    for ordinal,arm in enumerate(('A','B'),1):
        # Output pins come from the exact current private file bytes; these are
        # post-closure diagnostics, not independent authority for a reference.
        def current(path,cap):
            import os,stat,hashlib
            from common import plain,signature
            p=plain(path);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            try:
                a=os.fstat(fd);need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and
                    stat.S_IMODE(a.st_mode)==0o400 and 0<=a.st_size<=cap,'closed_owner_result')
                budget.charge_read(a.st_size);parts=[];left=a.st_size
                while left:
                    budget.check();b=os.read(fd,min(left,65536));need(bool(b),'complete_owner_result');parts.append(b);left-=len(b)
                need(signature(a)==signature(os.fstat(fd))==signature(p.lstat()),'stable_owner_result')
                return b''.join(parts)
            finally:os.close(fd)
        body=current(root/('candidate-'+arm)/'SUBMISSION.private.bin',2232)
        outcome=decode(current(root/'assessment'/f'submission-{ordinal:02d}.outcome.private.json',1048576))
        if calibration:
            need(outcome['status']=='scored' and
                 outcome['score']['all248_categories_match'] is True,
                 'fixed_comparator_complete_scoring_required')
            closed_bodies.append(body)
        if outcome['status']=='scored':
            diagnostic=from_score(body,outcome['score'])
        else:
            need(outcome['status']=='refused','closed_interface_outcome')
            diagnostic={'schema':'tms_numerical_diagnostic_unavailable_v1',
                        'reason':'protected_score_refused','all_results_private':True}
        result.append(write(root/'assessment'/f'submission-{ordinal:02d}.rounding.private.json',encode(diagnostic),budget))
    if calibration:
        need(len(closed_bodies)==2 and len(closed_bodies[0])==2232 and
             closed_bodies[0]==closed_bodies[1],'fixed_comparator_arm_transport_equality')
        entry=write(root/'assessment'/'CALIBRATION.private.json',encode({
            'schema':'tms_p23_fixed_comparator_interface_calibration_v1',
            'both_closed_and_scored':True,'all248_categories_admitted':True,
            'complete_A_B_output_bytes_equal_including_NaN_payloads':True,
            'numerical_accuracy_threshold':None,'numerical_reproduction_success_claimed':False,
            'code_assistance_effect':False,'continuous_errors_and_rounding_must_be_reported':True,
            'results_private':True}),budget)
        return {'rounding':result,'interface_calibration':entry}
    return {'rounding':result,'interface_calibration':None}
