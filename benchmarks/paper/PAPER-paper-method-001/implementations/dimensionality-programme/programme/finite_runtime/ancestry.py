"""Conservative transitive fit ancestry, exact grouping and frozen state reuse."""
from __future__ import annotations
from .common import require, identity

FIT_CLASSES={'TRAIN_FIT','REFERENCE_TRAIN_FIT'}
CASE_CLASSES={'CASE_STAT','MEASUREMENT_CASE','FIXED_CASE_OPERATION'}

class Ancestry:
    def __init__(self, folds, raw_registry):
        self.folds=folds
        self.nodes={}
        for key,row in raw_registry.items():
            self.nodes[key]={'id':key,'parents':[], 'groups':set(row['groups']),
                             'coordinates':row['coordinates'],'class':'RAW'}
        for fold in folds.values():
            sets=[set(fold[k]) for k in ['training','calibration','held']]
            require(not any(sets[i]&sets[j] for i in range(3) for j in range(i+1,3)),
                    'FOLD_GROUP_LEAKAGE')

    def ancestors(self, parents):
        out=set()
        for parent in parents:
            require(parent in self.nodes,'UNKNOWN_TRANSFORM_PARENT',parent)
            out.update(self.nodes[parent]['groups'])
        return out

    def add_state(self, state, *, actual_visible_parents, fold_id, lane, sealed=False):
        require(state['id'] not in self.nodes,'STATE_ID_REUSE')
        require(set(state['parents'])==set(actual_visible_parents),'FALSE_TRANSFORM_PARENT_CLAIM')
        groups=self.ancestors(actual_visible_parents)
        require(set(state['ancestor_groups'])==groups,'TRANSITIVE_ANCESTRY_MISMATCH')
        fold=self.folds[fold_id];cls=state['class']
        if cls in FIT_CLASSES:
            require(lane in {'I','REF'} and groups<=set(fold['training']),
                    'HELD_OR_CALIBRATION_FIT_ANCESTOR')
        elif cls=='R_ONLY_FIT':
            require(lane=='R' and sealed,'R_STATE_BEFORE_ALL_I_SEALS')
        elif cls=='FIXED_EXTERNAL':
            require(not groups and state.get('independent_provenance'), 'EXTERNAL_STATE_PROVENANCE_REQUIRED')
        elif cls in CASE_CLASSES:
            require(not state.get('reusable',False),'CASE_STAT_REUSED_AS_TRANSFORM')
        elif cls=='NO_FIT':
            require(not state.get('learned_parameters',False),'FALSE_NO_FIT_STATE')
        else:require(False,'UNKNOWN_TRANSFORM_CLASS',cls)
        self.nodes[state['id']]={**state,'groups':groups,'fold':fold_id}
        return identity(state)

    def apply(self, state_id, *, fold_id, input_coordinates, case_id, lane):
        require(state_id in self.nodes,'UNKNOWN_STATE')
        state=self.nodes[state_id]
        require(state.get('fold')==fold_id,'CROSS_FOLD_STATE_SUBSTITUTION')
        if lane in {'I','REF'}:
            require(state['class']!='R_ONLY_FIT','R_STATE_LEAKS_INTO_I')
        if state['class'] in CASE_CLASSES:
            require(state.get('case_id')==case_id,'CROSS_CASE_STATE_LEAKAGE')
        require(state['coordinates']==input_coordinates or state.get('coordinate_invariant') is True,
                'INCOMPATIBLE_FEATURE_COORDINATES')
        return state

def validate_grouping(roster):
    group_by_identity={}
    for row in roster:
        key=row['source_identity']
        require(key not in group_by_identity or group_by_identity[key]==row['independent_group'],
                'SAME_SOURCE_SPLIT_ACROSS_GROUPS')
        group_by_identity[key]=row['independent_group']
    mp=[x for x in roster if x.get('animal')=='MP032']
    if mp:require(len({x['independent_group'] for x in mp})==1,'MP032_SPLIT_ACROSS_GROUPS')
    semantic={}
    for row in roster:
        if row.get('semantic_family') is not None:
            key=row['semantic_family']
            semantic.setdefault(key,set()).add(row['independent_group'])
    require(all(len(x)==1 for x in semantic.values()),'TRANSLATION_OR_LAYER_GROUP_LEAKAGE')
    return group_by_identity

def capsule(run_id, participant, arm, plan, source, folds, states, selectors,
            query_plan, exposure, receipt_head, meter):
    require(not exposure['held_R_disclosures'],'I_SEAL_AFTER_HELD_R_EXPOSURE')
    require(set(states)==set(folds),'MISSING_FOLD_STATE_AT_GLOBAL_SEAL')
    return {'schema':'finite_pre_R_I_capsule_v1','run_id':run_id,'participant':participant,
            'arm':arm,'plan_sha256':plan,'source_manifest_sha256':source,'folds':folds,
            'states':states,'selectors':selectors,'query_plan_sha256':query_plan,
            'exposure_history':exposure,'receipt_head':receipt_head,'resources':meter,
            'capsule_kind':'ALL_FOLDS_PRE_R_I'}

def validate_resume(saved, request, r_receipts):
    require(saved['capsule_kind']=='ALL_FOLDS_PRE_R_I','R_ONLY_CAPSULE_CANNOT_RESUME_I')
    for key in ['participant','arm','plan_sha256','source_manifest_sha256','query_plan_sha256']:
        require(saved[key]==request[key],'RESUME_IDENTITY_MISMATCH',key)
    require(not saved['exposure_history']['held_R_disclosures'],'EXPOSED_I_CAPSULE')
    require(r_receipts['capsule_sha256']==identity(saved),'R_RECEIPTS_FROM_OTHER_CAPSULE')
    require(r_receipts['all_obligations']==[f'R{i:02d}' for i in range(37)],'INCOMPLETE_R_PREREQUISITE')
    require(r_receipts['participant']==saved['participant'] and r_receipts['arm']==saved['arm'],
            'BORROWED_R_PREREQUISITE')
    require(r_receipts['I_seal_sequence']<r_receipts['first_held_disclosure_sequence'],
            'R_BEFORE_I_SEAL')
    require(r_receipts['terminal_complete'] and r_receipts['resources_complete'],
            'INCOMPLETE_ORIGINAL_R_CUSTODY')
    require(r_receipts['no_I_mutation'],'MUTATED_RESUME_CAPSULE')
    return saved
