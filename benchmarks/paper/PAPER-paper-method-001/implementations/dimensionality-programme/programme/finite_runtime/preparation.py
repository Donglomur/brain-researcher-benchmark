"""Concrete qualified preparation graph; source gaps remain mandatory failures."""
from __future__ import annotations
from .common import require,identity,Refusal
from .truth import GeneratedTruth,prediction_input,validate_generator_job

PREPARATION_OPERATORS={'Stringer':'O03','Majaj':'O04','TVSD':'O05','THINGS':'O06','LLM':'O07','simulation':'O08'}
FIXED_PRESEAL={'identity_alignment','fixed_window_mean','chronological_trial_means','fixed_encoder','predeclared_generator_world'}
R_ONLY={'spontaneous_fit','spontaneous_apply','legacy_global_center','same_sample_metric'}

def simulation_output_bindings(family, prefix):
    """Exact generator artifact census, including protected truth/certificate."""
    require(family in {f'F{i:02d}' for i in range(1,13)},'UNKNOWN_SIMULATION_FAMILY')
    names=['trials','mask','row_weights','column_weights','private_truth']
    if family=='F10':names.append('private_full_population')
    if family=='F12':names.extend(['private_latent_coordinates','private_truth_certificate'])
    return {'result/outputs/'+name:prefix+'/'+name for name in names}

class Preparation:
    def __init__(self,plan,science,journal,meter,registry):
        self.plan,self.science,self.journal,self.meter=plan,science,journal,meter
        self.registry=registry;self.products={};self.executed=[]
        self.truth=GeneratedTruth(self)

    def run(self,jobs,*,phase,all_I_sealed):
        require(phase in {'P02','P06'},'INVALID_PREPARATION_PHASE')
        for job in jobs:
            self.meter.checkpoint('next_preparation_job')
            require(job['id'] not in self.products,'DUPLICATE_PREPARATION_JOB')
            require(job['operator']==PREPARATION_OPERATORS[job['branch']], 'WRONG_PREPARATION_BRANCH')
            require(job['complete_original_support'] and job['original_source_sha256'],
                    'UNQUALIFIED_PREPARATION_SUPPORT')
            require(job['source_qualification_id'],'MISSING_ORIGINAL_PREPARATION_PRODUCER',job['id'])
            if job['operation']=='generator.world':
                validate_generator_job(job)
                require(job['branch']=='simulation','SIMULATION_PRODUCER_SUBSTITUTION')
                expected=simulation_output_bindings(job['parameters']['family'],job['id'])
                require(set(job['output_bindings'])==set(expected),'SIMULATION_PROTECTED_OUTPUT_CENSUS')
                require(job['protocol'].get('generation_stage') in
                        {'development','calibration','evaluation'},'GENERATOR_STAGE_NOT_BOUND')
            if job['transform_kind'] in R_ONLY:
                require(phase=='P06' and all_I_sealed,'R_ONLY_PREPROCESSING_BEFORE_I_SEAL')
            elif phase=='P02':
                require(job['transform_kind'] in FIXED_PRESEAL,'SHARED_PREFIT_LEAKAGE')
            if job['branch']=='TVSD':
                require(job['measurement']=='LFP' or job['lane']=='SOURCE_DIAGNOSTIC',
                        'MUA_CANNOT_SATISFY_LFP')
            if job['branch']=='LLM':
                require(job['checkpoint_sha256'] and job['tokenizer_sha256'] and job['all_languages']==9,
                        'INCOMPLETE_LLM_SOURCE_BINDING')
                require(job['last_token_policy'] and job['layer_manifest_sha256'],
                        'LLM_LAYER_OR_TOKEN_POLICY_MISSING')
            arrays={}
            for name,parent in job['inputs'].items():
                require(parent in self.registry,'MISSING_PREPARATION_INPUT',parent)
                arrays[name]=self.registry[parent]
            protocol={**job['protocol'],'source_qualification_id':job['source_qualification_id'],
                      'original_source_sha256':job['original_source_sha256']}
            record=self.science.invoke(job['operation'],arrays=arrays,protocol=protocol,
                parameters=job['parameters'],lineage={'preparation_id':job['id'],'phase':phase,
                  'input_identities':{k:v['sha256'] for k,v in arrays.items()},
                  'complete_support_sha256':job['complete_support_sha256'],
                  **({'truth_context':job['truth_context']} if job['operation']=='generator.world' else {})},
                namespace='trusted_preparation')
            result=record['response']['result']
            require(result['status']=='ok','REQUIRED_PREPARATION_UNSCORABLE',
                    {'job':job['id'],'scientific_status':result['status']})
            actual=record['response']['artifacts']
            require(set(job['output_bindings'])=={x['logical_output'] for x in actual},
                    'PREPARATION_OUTPUT_CENSUS_MISMATCH')
            for desc in actual:
                name=job['output_bindings'][desc['logical_output']]
                require(name not in self.registry,'PREPARATION_OUTPUT_OVERWRITE')
                self.registry[name]=desc
            self.products[job['id']]=record;self.executed.append(job['id'])
            self.truth.register(job,record)
            self.journal.append('PREPARATION_COMPLETE',{'id':job['id'],'product':record['product_sha256'],
                                                      'original_receipt':record['process_receipt']})
        return self.registry

    def materialize_case(self,case,*,lane,phase):
        self.meter.checkpoint('before_case_materialization')
        require(phase=='P07' if lane=='I' else phase=='P06','CASE_RELEASE_IN_WRONG_PHASE')
        require(case['input_ids'] and case['selection_sha256'],'CASE_SELECTION_MISSING')
        return self.case_arrays(case)

    def case_arrays(self,case):
        self.meter.checkpoint('before_common_prediction_input_admission')
        require(case['input_ids'] and len(case['input_ids'])<=256,'CASE_INPUT_BOUND')
        arrays={name:prediction_input(self.registry[key]) for name,key in case['input_ids'].items()}
        actual=identity({k:{'bytes':v['bytes'],'sha256':v['sha256'],'shape':v['shape'],
                            'dtype':v['dtype'],'units':v['units']} for k,v in arrays.items()})
        require(actual==case['input_sha256'],'CASE_MATERIALIZATION_SUBSTITUTION')
        return arrays
