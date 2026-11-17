"""Whole-programme plans and deterministic required reference membership.

Authentic rosters, unknown final-paper grids and original producer provenance must
be separately qualified. A plan cannot shrink those obligations to the available data.
"""
from __future__ import annotations
from itertools import product
from .common import require, identity, ROUTES
from .ancestry import validate_grouping

EXPECTED_R={f'R{i:02d}' for i in range(37)}
EXPECTED_I={f'I{i:02d}' for i in range(1,6)}
EXPECTED_OP={f'O{i:02d}' for i in range(1,33)}
EXPECTED_GATE={f'G{i:02d}' for i in range(1,25)}
NORMATIVE_JSON=('OBLIGATIONS','OPERATORS','INPUTS','COHORTS','PROSPECTIVE_SIMULATION_GRID',
    'REFERENCE_SELECTION','PHASE_AND_EXPOSURE_CONTRACT','TRANSFORM_ANCESTRY_CONTRACT',
    'SPLIT_AND_GROUP_POLICY','PRODUCER_CONSUMER_BINDINGS','PRODUCT_EXPOSURE_BINDINGS',
    'SOURCE_API_MAP','FUTURE_QUALIFICATION')

class Contracts:
    def __init__(self, documents):
        require(set(documents)==set(NORMATIVE_JSON),'INCOMPLETE_NORMATIVE_SCIENTIFIC_CONTRACT')
        self.documents=documents
        require(len(documents['INPUTS']['roles'])==26 and len(documents['COHORTS']['records'])==13,
                'FULL_INPUT_OR_COHORT_SCOPE_REDUCED')
        require({x['id'] for x in documents['FUTURE_QUALIFICATION']['gates']}==EXPECTED_GATE,
                'SCIENTIFIC_GATE_SCOPE_REDUCED')
        self.obligations={x['id']:x for x in documents['OBLIGATIONS']['obligations']}
        self.operators={x['id']:x for x in documents['OPERATORS']['operators']}
        self.reference=documents['REFERENCE_SELECTION']
        self.keys={x['id']:x for x in self.reference['primary_selection_keys']}
        self.bank={x['id']:x for x in self.reference['reference_bank']}
        require(set(self.obligations)==EXPECTED_R|EXPECTED_I,'INCOMPLETE_42_OBLIGATIONS')
        require(set(self.operators)==EXPECTED_OP,'INCOMPLETE_32_OPERATORS')
        require(len(self.keys)==24 and len(self.bank)==17,'INCOMPLETE_REFERENCE_CONTRACT')
        self.hash=identity({k:identity(v) for k,v in documents.items()})

    def variants(self, key_id):
        key=self.keys[key_id]
        for ref in key['eligible_reference_ids_before_qualification']:
            for variant in self.bank[ref]['variants']:
                yield {'key':key_id,'reference_id':ref,'variant':variant,
                       'id':f'{key_id}/{ref}/{variant}'}

    def uncertainty_variants(self, key_id):
        key=self.keys[key_id]
        for point in self.variants(key_id):
            for rule,spec in self.reference['uncertainty_selector']['structural_rule_matrix'].items():
                if key['family'] not in spec['families'] or key['trial_view'] not in spec['views']:
                    continue
                for scale in ([1] if rule=='U03_TWO_AXIS_PERCENTILE' else [1,1.25,1.5,2]):
                    yield {**point,'rule':rule,'scale':scale,
                           'id':f"{point['id']}/{rule}/{scale}"}

    def world_requirements(self, split):
        counts={'development':40,'calibration':40,'evaluation':200}
        require(split in counts,'UNKNOWN_WORLD_SPLIT')
        for family in self.documents['PROSPECTIVE_SIMULATION_GRID']['families']:
            for cell in family['cells']:
                for world in range(counts[split]):
                    # Opaque evaluation identifiers are subsequently assigned by the trusted
                    # generator. This ordinal remains in trusted planning, never CaseView.
                    yield {'family':family['id'],'cell':cell['id'],'ordinal':world,
                           'P':cell['P'],'Q':cell['Q'],'split':split,'views':[2,4]}

    def preflight_census(self):
        points=sum(len(list(self.variants(k))) for k in self.keys)
        intervals=sum(len(list(self.uncertainty_variants(k))) for k in self.keys)
        require(points==187 and intervals==1963,'REFERENCE_EXPANSION_CHANGED')
        return {'point_variants':points,'uncertainty_variants':intervals,
                'point_calibration_outputs':points*240,'point_evaluation_outputs':points*1200,
                'interval_calibration_outputs':intervals*240,
                'interval_evaluation_outputs':intervals*1200,
                'required_R_obligations':37,'required_I_obligations':5}

class Plan:
    def __init__(self, value, contracts):
        self.value,self.contracts=value,contracts
        require(value['route'] in ROUTES,'UNKNOWN_ROUTE')
        require(value['contracts_sha256']==contracts.hash,'WRONG_ACCEPTED_DESIGN')
        require(set(value['obligation_manifest'])==EXPECTED_R|EXPECTED_I,'SCOPE_REDUCTION')
        require(set(value['operator_manifest'])==EXPECTED_OP,'OPERATOR_SCOPE_REDUCTION')
        require(set(value['gate_manifest'])==EXPECTED_GATE,'GATE_SCOPE_REDUCTION')
        require(set(value['cohort_manifest'])=={x['id'] for x in contracts.documents['COHORTS']['records']},
                'COHORT_SCOPE_REDUCTION')
        require(set(value['Stringer_sessions'])=={f'STR{i:02d}' for i in range(1,8)},'STRINGER_SESSION_OMITTED')
        require(set(value['language_manifest'])==set(next(x['languages'] for x in
            contracts.documents['COHORTS']['records'] if x['id']=='LLAMA3')),'LANGUAGE_OMITTED')
        require(set(value['biological_sources'])=={'Stringer','Majaj','TVSD','THINGS'},'BIOLOGY_SOURCE_OMITTED')
        validate_grouping(value['group_roster'])
        require(value['resource_preflight']['complete_expansion'] is True,'FULL_RESOURCE_PREFLIGHT_REQUIRED')
        require(value['resource_preflight']['census']==contracts.preflight_census(),'RESOURCE_CENSUS_MISMATCH')
        require(value['resource_preflight']['uncertainty_draws']==999,'RESAMPLING_PLAN_REDUCED')
        require(value['resource_preflight']['all_cost_categories_included'], 'OMITTED_COMPUTE_OR_STORAGE_COST')
        require(value['original_exposure_history'] is not None,'EXPOSURE_HISTORY_REQUIRED')
        require(value['same_inputs_A_B_sha256'] and value['source_authority_sha256'], 'PAIRED_SOURCE_AUTHORITY_REQUIRED')
        # Invocation route and an exact resume pointer do not redefine the sealed
        # scientific plan. Their authorization is checked separately on every effect.
        self.hash=identity({k:v for k,v in value.items() if k not in {'route','resume_capsule'}})
        self.route=value['route'];self.arm=self.route[-1]
        self.r_only=self.route.startswith(('reproduce','source-diagnostic'))
        self.resume=bool(value.get('resume_capsule'))
        require(not self.resume or self.route.startswith('improve'),'RESUME_ONLY_FOR_IMPROVE')

    def validate_case_rows(self, rows, lane):
        ids=set(); covered=set()
        for row in rows:
            require(row['case_id'] not in ids,'DUPLICATE_CASE')
            ids.add(row['case_id']);covered.update(row['obligations'])
            require(set(row['obligations'])<=EXPECTED_R|EXPECTED_I,'UNKNOWN_CASE_OBLIGATION')
            require(row['lane']==lane and row['input_sha256'] and row['selection_sha256'], 'CASE_IDENTITY_INCOMPLETE')
            require(row['original_support_sha256'],'ORIGINAL_SUPPORT_REQUIRED')
            require(row['source_provenance_sha256'],'CASE_SOURCE_PROVENANCE_REQUIRED')
            require(row['complete_support'] is True,'PARTIAL_CASE_SUPPORT')
        needed=EXPECTED_R if lane=='R' else EXPECTED_I
        require(covered>=needed,'MISSING_SCHEDULED_OBLIGATIONS',sorted(needed-covered))
        return ids

    def validate_evaluation_worlds(self, rows):
        keys={(x['family'],x['cell'],x['world_ordinal'],x['view']) for x in rows}
        expected={(x['family'],x['cell'],x['ordinal'],view)
                  for x in self.contracts.world_requirements('evaluation') for view in x['views']}
        require(keys==expected and len(rows)==len(expected),'INCOMPLETE_SIMULATION_EVALUATION_BANK')
        require(len({x['world_id'] for x in rows})==14400,'WORLD_PAIRING_CENSUS_CHANGED')
        return True

    def case_contract(self, case):
        return identity({k:case[k] for k in ['case_id','input_sha256','selection_sha256',
            'protocol_id','original_support_sha256','source_provenance_sha256','obligations']})


def scientific_case_contracts(data):
    fields=('case_id','lane','input_sha256','selection_sha256','protocol_id',
            'original_support_sha256','source_provenance_sha256','obligations','target_identity','truth_binding')
    rows=[{k:case.get(k) for k in fields} for case in data['R_cases']+data['I_cases']]
    require(len({x['case_id'] for x in rows})==len(rows),'DUPLICATE_PAIRED_CASE_ID')
    return sorted(rows,key=lambda x:x['case_id'])


def shared_scientific_identity(plan,data):
    """Acyclic: this identity precedes target wrapper creation and excludes its SHA."""
    return identity({'contracts_sha256':plan.contracts.hash,'case_contracts':scientific_case_contracts(data),
        'cohort_manifest':plan.value['cohort_manifest'],'Stringer_sessions':plan.value['Stringer_sessions'],
        'language_manifest':plan.value['language_manifest'],'biological_sources':plan.value['biological_sources'],
        'group_roster':plan.value['group_roster'],
        'generated_truth_plan':[{k:j.get(k) for k in ('id','operation','parameters','protocol','truth_context',
             'original_source_sha256','complete_support_sha256','output_bindings')}
             for j in data['preparation_P02']+data['preparation_P06'] if j['operation']=='generator.world']})


def paired_input_target_identity(plan,data):
    desc=data['protected_target_index']
    # Physical staging roots can differ. Actual scientific target bytes/provenance
    # and every case input/support remain identical, not merely equal case labels.
    return identity({'scientific_plan_sha256':shared_scientific_identity(plan,data),
        'protected_target_index':{k:desc[k] for k in ('bytes','sha256','role','media_type','producer')},
        'case_contracts':scientific_case_contracts(data)})
