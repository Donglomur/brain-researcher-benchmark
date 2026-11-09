"""Exact independent activation/method/grading evidence, never computed answers."""
from pathlib import Path
import time
from core import need,integer,finite,descriptor,canonical,disjoint,relative,capture,parse,encoded,pin,capture_new_protected
from contracts import TASK,exact
GATES=('source_assets','signal_schema','upstream_preprocessing','clinical_review','eligibility','accuracy_support','control_views','f_semantic_boundary','i_scope','tools','references','native_anchor','resources','transport','target_last','reasoning_review','rights','source_family')
ROOTS=('source','raw','packet','private','output','operator','observation','secrets')
METHOD_FINDINGS=('full_canonical_estimand','complete_case_support','no_protected_reference_access','declared_world_and_tools','no_cross_case_or_world_state','typed_f_provider_boundary','declared_numerical_adaptation','no_hidden_generated_execution','source_dependency_closure')


def selection_pin(value):
    return pin(encoded({k:v for k,v in value.items()if k!='qualifications'}))


def selected(value,source_pin,origin,role):
    need(type(value)is dict and value.get('active')is True,'not qualified: N042 source construction only')
    need(value.get('schema')=='neural042_root_authority_v1'and value.get('task_id')==TASK,'exact task authority')
    need(value.get('source_manifest')==source_pin,'complete source closure identity')
    need(role in ('prepare','observe','worker','grade') and value.get('roles',{}).get(role)is True,'independently selected actual role')
    exact(value['roots'],ROOTS,'all physical-policy roots')
    roots=[canonical(value['roots'][k])for k in ROOTS]
    need(all(disjoint(a,b)for i,a in enumerate(roots)for b in roots[i+1:]),'canonical disjoint physical-policy roots')
    clock=value['clock'];exact(clock,('origin','production_end','observation_end','readback_end'),'original complete clocks')
    times=[finite(clock[k])for k in ('origin','production_end','observation_end','readback_end')]
    need(times[0]==finite(origin)and times==sorted(set(times)),'one inherited strict clock chain')
    need(value['replicate']=='author-01','only declared single-policy realization')
    need(value['grading']=={'selected':False},'production authority cannot embed future scores')
    need(type(value['qualifications'])is dict and set(value['qualifications'])==set(GATES),'all18 gate dispositions')
    for name,row in value['qualifications'].items():
        exact(row,('path','pin','selection'),'independent qualification descriptor')
        relative(row['path']);descriptor(row['pin']);need(row['selection']==selection_pin(value),'actual full selection pin')
    from configuration import validate
    validate(value)
    return value


def qualify(value,source_pin,origin,role,budget):
    selected(value,source_pin,origin,role);records={}
    for name in GATES:
        row=value['qualifications'][name]
        raw,_=capture(Path(value['roots']['operator'])/relative(row['path']),row['pin'],value['resources']['qualification_bytes'],budget,readonly=True)
        doc=parse(raw)
        need(doc.get('schema')=='neural042_actual_gate_v1'and doc.get('realm')=='actual_external_evidence'
             and doc.get('task_id')==TASK and doc.get('kind')==name and doc.get('issuer')==value['issuer']
             and doc.get('source_manifest')==source_pin and doc.get('selection')==selection_pin(value),'exact external gate lineage')
        # These two optional outputs cannot be prerequisites for prospective P collection.
        optional=name in ('native_anchor','reasoning_review')
        need(doc.get('qualified')is True or(optional and doc.get('qualified')is False and doc.get('operation_selected')is False),
             'required actual gate unavailable')
        if name=='accuracy_support':
            need(doc.get('criterion')=='complete_support_disposition_with_unchanged_floor_and_nullable_primary',
                 'support admission does not require a positive/nonempty scientific result')
        if name=='signal_schema':
            # Actual source-qualified DynamicTableRegion reference resolution is
            # external evidence, not inferred from equal integer row indices.
            from preparation.prepare import LOCK
            raw_lock,_=capture(Path(value['roots']['source'])/'preparation/SOURCE_ASSETS.json',LOCK,LOCK['bytes'],budget)
            assets=parse(raw_lock)['assets'];links=doc.get('electrode_table_identity_by_asset')
            need(type(links)is dict and set(links)=={x['asset_id']for x in assets},'all44 original DynamicTableRegion identities independently resolved')
            for asset in assets:
                link=links[asset['asset_id']]
                need(link=={'source_sha256':asset['sha256'],'lfp_region':'/acquisition/LFPs/electrodes','unit_region':'/units/electrodes',
                    'target_table':'/general/extracellular_ephys/electrodes','independent_reference_resolution':True}and link.get('independent_reference_resolution')is True,
                    'exact qualified common electrode table, not integer coincidence')
        evidence=doc.get('evidence');need(type(evidence)is list and evidence,'external evidence, not actor assent')
        for item in evidence:
            exact(item,('path','pin'),'gate evidence descriptor');relative(item['path'])
            capture(Path(value['roots']['operator'])/item['path'],item['pin'],value['resources']['qualification_bytes'],budget,retain=False,readonly=True)
        records[name]={'pin':row['pin'],'qualified':doc['qualified'],'operation_selected':doc.get('operation_selected',True)}
    budget.tick();return records


def method(value,identity,source,recipe,claim,mode,budget,cutoff):
    path=Path(value['roots']['operator'])/relative(value['method_admissions'][identity])
    while not path.exists():
        now=budget.tick(cutoff);time.sleep(min(.05,max(0,cutoff-now)))
    raw,desc=capture_new_protected(path,value['resources']['qualification_bytes'],budget);doc=parse(raw)
    need(doc.get('schema')=='neural042_method_admission_v1'and doc.get('accepted')is True
         and doc.get('issuer')==value['issuer']and doc.get('study')==value['study_id']and doc.get('identity')==identity
         and doc.get('source')==source and doc.get('recipe')==recipe and doc.get('claim')==claim
         and doc.get('mode')==mode and doc.get('selection')==selection_pin(value),'independent exact authored method admission')
    need(type(doc.get('findings'))is dict and set(doc['findings'])==set(METHOD_FINDINGS)
         and all(doc['findings'][k]is True for k in METHOD_FINDINGS),'complete semantic findings')
    need(type(doc.get('evidence'))is list and doc['evidence'],'actual semantic review evidence')
    for row in doc['evidence']:
        capture(Path(value['roots']['operator'])/relative(row['path']),row['pin'],value['resources']['qualification_bytes'],budget,retain=False,readonly=True)
    budget.tick(cutoff);return {'path':str(path),'pin':desc}


def grading_selection(value,captured,declaration,budget):
    exact(declaration,('path','pin'),'late grading declaration')
    path=canonical(declaration['path']);need(canonical(value['roots']['operator'])in path.parents,'protected grading selection namespace')
    raw,_=capture(path,declaration['pin'],value['resources']['qualification_bytes'],budget,readonly=True);doc=parse(raw)
    need(doc.get('schema')=='neural042_actual_grading_v1'and doc.get('realm')=='actual_external_evidence'
         and doc.get('qualified')is True and doc.get('issuer')==value['issuer']and doc.get('task_id')==TASK
         and doc.get('source_manifest')==captured['pin']and doc.get('production_authority')==captured['authority_pin']
         and doc.get('selection')==selection_pin(value),'independently selected observed production/source')
    need(type(doc.get('evidence'))is list and doc['evidence'],'actual target custody/metric/resource evidence')
    for row in doc['evidence']:
        capture(Path(value['roots']['operator'])/relative(row['path']),row['pin'],value['resources']['qualification_bytes'],budget,retain=False,readonly=True)
    exact(doc['grading'],('observation','reference_targets','output','outer_completion'),'bounded separate grading operands')
    budget.tick();return doc['grading'],declaration
