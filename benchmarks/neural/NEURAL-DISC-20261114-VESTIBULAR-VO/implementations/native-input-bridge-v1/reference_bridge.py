"""Attach a separately supplied prior to protected targets for the unchanged v2.

No prior is synthesized, fitted or qualified here. Existing v2 validation does
arithmetic admissibility checks; its evaluate/compare endpoints are never called.
This in-memory bridge is not participant isolation or authentic source admission.
"""
import copy
import hashlib
from pathlib import Path
import types

PROJECTION_SHA256='722afce41d4877a2d151326b88c626a6b6955b8205bf68c67f8b2da1b4dacaa1'


def load_projection():
    path=Path(__file__).resolve().with_name('packet_projection.py')
    body=path.read_bytes()
    if len(body)>65536 or hashlib.sha256(body).hexdigest()!=PROJECTION_SHA256:
        raise ValueError('exact reviewed packet projection source required')
    module=types.ModuleType('vestibular_reference_pinned_projection');module.__file__=str(path)
    exec(compile(body,str(path),'exec'),module.__dict__)
    return module


p=load_projection()

SOURCE_SHA='3db6c47e61f51230ea4a83b5722f1c019337ab09f7ad836b36ce934a0270ca86'


def assemble(prepared,admission,prior,*,accepted_admission_sha256,accepted_prior_sha256,
             id_key,evaluation_id,access_condition):
    e=p.load_evaluator()
    e.identifier(evaluation_id);e.identifier(access_condition);e.digest(accepted_prior_sha256)
    p.need(p.canonical_sha256(prior)==accepted_prior_sha256,'separately selected complete prior identity')
    projection=p.project(prepared,admission,accepted_admission_sha256=accepted_admission_sha256,id_key=id_key)
    public,protected=projection['public'],projection['protected']
    evidence_id=p.canonical_sha256(public)
    e.fields(prior,('schema','task_id','prepared_sha256','public_evidence_id','information_condition','selection','cases'))
    p.need(prior['schema']=='vestibular_supplied_prior_v1' and prior['task_id']==p.TASK
           and prior['prepared_sha256']==admission['prepared_sha256']
           and prior['public_evidence_id']==evidence_id,'prior matches exact prepared data and public observations')
    p.need(prior['information_condition']==public['information_condition']=='full-repeat-v1',
           'this reference bridge binds only the full-repeat information condition')
    selection=prior['selection']
    e.fields(selection,('id','selection_split','selection_protocol_sha256','source_record_ids'))
    e.identifier(selection['id']);e.digest(selection['selection_protocol_sha256'])
    p.need(selection['selection_split']=='training_only','prior selection must exclude held outcomes')
    ids=selection['source_record_ids']
    train={row['id'] for row in protected['source_records'] if row['partition']=='train'}
    p.need(isinstance(ids,list) and ids and all(isinstance(x,str) for x in ids)
           and len(set(ids))==len(ids) and set(ids)<=train,'prior declared source records must be unique permitted training records')
    # v2 declares one target and tick unit globally. Require a single documented
    # unit/axis/scale before assembly; never guess or silently normalize sources.
    units=set()
    for row in protected['source_records']:
        if row['partition']=='excluded':
            continue
        clock=row['clock']
        units.add((clock['target_unit'],clock['axis'],clock['tick_unit'],
                   clock['seconds_numerator'],clock['seconds_denominator']))
    p.need(len(units)==1,'reference requires one documented target axis/unit and exact clock scale; no implicit conversion')
    target_unit,axis,tick_unit,numerator,denominator=next(iter(units))
    qualified_target_unit=f'{target_unit}; axis={axis}'
    qualified_tick_unit=f'{tick_unit}; {numerator}/{denominator} seconds per tick'
    e.identifier(qualified_target_unit);e.identifier(qualified_tick_unit)
    by_id=e.unique_rows(prior['cases'])
    p.need(set(by_id)=={case['id'] for case in protected['cases']},'complete prior required for every held repeat')
    cases=[]
    for target in protected['cases']:
        row=by_id[target['id']]
        e.fields(row,('id','sample_ticks','prediction'))
        p.need(isinstance(row['sample_ticks'],list)
               and all(type(t) is int for t in row['sample_ticks'])
               and row['sample_ticks']==target['sample_ticks'],'prior uses the exact full native sample grid')
        p.need(isinstance(row['prediction'],list) and len(row['prediction'])==len(target['sample_ticks']),
               'complete prior vector required')
        for value in row['prediction']:
            e.finite(value)
        cases.append(copy.deepcopy(target)|{'prior':list(row['prediction'])})
    if admission['kind']=='assessor_admitted_native':
        p.need(prepared['source_sha256']==SOURCE_SHA,'this native task uses the fixed complete original')
    census=protected['census']
    reference={'schema':'vestibular-reference-v1','task_id':p.TASK,'evaluation_id':evaluation_id,
               'evidence_id':evidence_id,'access_condition':access_condition,
               'binding':{'kind':'generated_control' if admission['kind']=='generated_control' else 'assessor_supplied',
                          'source_version':'Borealis 10.5683/SP3/FXFZ2J v2.0' if admission['kind']!='generated_control' else 'generated software control',
                          'source_sha256':prepared['source_sha256'],'roster_sha256':admission['census_sha256'],
                          'protocol_sha256':admission['protocol_sha256'],'target_unit':qualified_target_unit,
                          'tick_unit':qualified_tick_unit,'mask_basis':'input_acquisition_metadata',
                          'prior':{key:selection[key] for key in ('id','selection_split','selection_protocol_sha256')}},
               'animals':copy.deepcopy(census['animals']),'neurons':copy.deepcopy(census['neurons']),
               'pairs':[{key:copy.deepcopy(row[key]) for key in ('id','animal_id','neuron_ids')} for row in census['pairs']],
               'groups':copy.deepcopy(census['groups']),'excluded_pairs':copy.deepcopy(census['excluded_pairs']),
               'excluded_neurons':copy.deepcopy(census['excluded_neurons']),'conditions':list(census['conditions']),
               'additional_conditions':copy.deepcopy(census['additional_conditions']),
               'coverage':copy.deepcopy(census['coverage']),'cases':cases}
    e.validate_reference(reference)
    return {'public':public,'reference':reference,
            'operator_provenance':{'admission_sha256':accepted_admission_sha256,'prior_sha256':accepted_prior_sha256,
                                   'original_target_inventory':protected,
                                   'prior_training_execution_verified':False,
                                   'reference_competence_established':False,
                                   'participant_isolation_established':False,
                                   'candidate_evaluation_performed':False}}
