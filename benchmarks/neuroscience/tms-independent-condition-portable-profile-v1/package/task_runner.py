"""Concrete authentic two-arm owner API; no invocation is selected now.

A future root-selected launcher must authenticate this complete source and its
owner plan before calling. Candidates never choose plans, reference pins or
data-provenance records. The versioned run_once entry separately gates image preparation and private reconstruction.
"""
from pathlib import Path
from common import need,read,write,encode,plain
from runtime import load_numeric
from portable_config import current
from packet import input_packet,require_authentic_delivery,stage_materials,paired_materials,just_pin
from docker_owner import run_candidate
from assessment import score_authentic

def execute_authentic(plan, *, document_bodies,budget,active_deadline):
    keys={'schema','root','input_manifest','input_values','delivery','reference_selection','programs',
          'execution_selected','model_calls','source_profile'}
    need(type(plan) is dict and set(plan)==keys and
         plan['schema']=='tms_method_specified_two_arm_owner_plan_v1' and
         plan['execution_selected'] is True and type(plan['model_calls']) is int and plan['model_calls']==0 and
         plan['source_profile']=='original_scientific_operands','explicit_authentic_owner_plan')
    need(type(plan['programs']) is dict and set(plan['programs'])=={'A','B'},'both_frozen_programs')
    root=plain(plan['root']);root.mkdir(mode=0o700)
    modules,evidence=load_numeric(budget)
    identity_pin={'bytes':5214,'sha256':'4491f48145c8b9cddc7fcf7f7193a671117038583b234552cfa3bf85a23e262c'}
    identity_body=read(current()['assets']['identity']['path'],identity_pin,budget)
    identity=modules['authentic'].identity(identity_body)
    projection=input_packet(plan['input_manifest'],plan['input_values'],budget=budget,
                             mode='authentic',identity=identity)
    require_authentic_delivery(plan['delivery'],projection,budget=budget)
    materials={};programs={}
    for arm in ('A','B'):
        materials[arm]=stage_materials(root/('task-'+arm),arm=arm,mode='authentic',
            document_bodies=document_bodies,budget=budget,delivery=plan['delivery'],projection=projection)
        entry=plan['programs'][arm]
        body=read(entry['path'],just_pin(entry),budget,262144)
        need(0<len(body)<=262144 and b'\0' not in body,'bounded_frozen_python_source')
        body.decode('utf-8')
        programs[arm]=write(root/('solution-'+arm+'.py'),body,budget)
    paired_materials(materials['A'],materials['B'])
    closed=[]
    for arm in ('A','B'):
        input_packet(plan['input_manifest'],plan['input_values'],budget=budget,
                     mode='authentic',identity=identity)
        result=run_candidate(root=root/('candidate-'+arm),input_dir=Path(projection['folder']),
            task_dir=Path(materials[arm]['folder']),program=Path(programs[arm]['path']),
            budget=budget,active_deadline=active_deadline)
        input_packet(plan['input_manifest'],plan['input_values'],budget=budget,
                     mode='authentic',identity=identity)
        closed.append(result)
    # No original interval/category/reference body has been captured until both
    # isolated candidate processes and typed CIDs have completed and been removed.
    receipts=score_authentic(closed,modules=modules,selection=plan['reference_selection'],
                            root=root/'assessment',budget=budget)
    record={'schema':'tms_method_specified_two_arm_owner_result_v1','programs':programs,
            'closed_submissions':2,'all_candidates_closed_before_reference':True,
            'receipts':receipts,'shared_materials':materials['A']['shared'],
            'B_only_code':materials['B']['code'],'accepted_base':evidence,
            'method_specified_reconstruction':True,'paper_only_understanding':False,
            'native_parity_claimed':False,'scientific_qualification':False,
            'model_calls':0,'results_owner_private':True}
    return write(root/'RESULT.private.json',encode(record),budget)

