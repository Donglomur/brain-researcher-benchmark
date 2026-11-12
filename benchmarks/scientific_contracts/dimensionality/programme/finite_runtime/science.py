"""Source-bound independent scientific jobs, with protected inputs opened last."""
from __future__ import annotations
from pathlib import Path
from .common import require,identity,decode,relative_path
from .transport import ParameterTransport

def prepared_output_role(logical_output, protocol):
    """Protected issuer outputs cannot inherit an ordinary reference-input role."""
    name=logical_output.removeprefix('result/outputs/')
    if name=='private_truth':
        stage=protocol.get('generation_stage')
        require(stage in {'development','calibration','evaluation'},'GENERATOR_STAGE_NOT_BOUND')
        return {'development':'training_truth','calibration':'calibration_truth',
                'evaluation':'protected_truth'}[stage]
    if name=='private_truth_certificate':
        stage=protocol.get('generation_stage')
        require(stage in {'development','calibration','evaluation'},'GENERATOR_STAGE_NOT_BOUND')
        return {'development':'training_truth_certificate','calibration':'calibration_truth_certificate',
                'evaluation':'protected_truth'}[stage]
    if name.startswith('private_'):return 'protected_truth'
    return 'reference_input'

class Science:
    def __init__(self, host, authority, store, journal, meter, source, work_root, environment):
        self.host,self.authority,self.store=host,authority,store
        self.journal,self.meter,self.source=journal,meter,source
        self.work_root=Path(work_root);self.environment=environment;self.counter=0;self.output_registry={}
        require(environment['environment'].get('PYTHONPATH')=='/science:/science/scientific-runtime',
                'SCIENTIFIC_MODULE_LAYOUT_NOT_QUALIFIED')
        authority.producer('finite_science',source['source_manifest_sha256'])
        require(identity(source['files'])==source['source_manifest_sha256'],'SCIENTIFIC_SOURCE_MANIFEST_MISMATCH')
        for item in source['files']:store.read(item,{'qualified_scientific_source'})

    def invoke(self, operation, *, arrays, protocol, parameters, lineage, namespace,
               access=None):
        self.meter.checkpoint('scientific_job_admission')
        require(namespace in {'independent_reference','trusted_preparation','trusted_collection','protected_grade'},
                'INVALID_INDEPENDENT_ISSUER')
        allowed_operations={
            'trusted_preparation':{'generator.world','preparation.transform','preparation.stringer_source'},
            'trusted_collection':{'score.select_participant','score.legacy76_validate','aggregate.curves','aggregate.majaj_curves'},
            'independent_reference':{'moments.direct','moments.optimized','finite.population','local.select',
                'reference.point','reference.literal','reference.fit','reference.bundle','uncertainty.residual_fit',
                'uncertainty.sets','uncertainty.resample','score.select_point','score.select_uncertainty',
                'aggregate.curves','aggregate.majaj_curves'},
            'protected_grade':{'score.point','score.interval','score.paired','score.access_effect',
                'score.uncertainty_quality','score.support','score.mandatory_pairwise',
                'score.reproduction','score.legacy76','aggregate.transfer'}}
        require(operation in allowed_operations[namespace],'OPERATION_IN_WRONG_EXPOSURE_NAMESPACE')
        if namespace=='protected_grade':
            require(access is not None,'TARGET_ACCESS_ISSUER_REQUIRED')
            access.check('protected_scientific_invocation')
        mounts=[];decoded={}
        for item in self.source['files']:
            require(item['path'].startswith(self.source['root']+'/'),'SCIENCE_SOURCE_ROOT_MISMATCH')
            relative=relative_path(item['path'][len(self.source['root'])+1:])
            mounts.append({'source':str(self.store.root/item['path']),'destination':'/science/'+relative,
                           'readonly':True,'descriptor':item})
        for index,(name,descriptor) in enumerate(arrays.items()):
            if descriptor['role']=='reference_product':
                registry=self.output_registry.get((descriptor['path'],descriptor['sha256']))
                require(namespace=='independent_reference' and registry is not None and
                        registry['descriptor']==descriptor,'UNISSUED_REFERENCE_INTERMEDIATE')
                original=registry['lineage']
                require(registry['namespace']=='independent_reference' and
                    original.get('input_identity')==lineage.get('input_identity') and
                    original.get('point_id')==lineage.get('reference_variant',lineage.get('point_id')) and
                    original.get('state_id')==lineage.get('point_state_id',lineage.get('state_id')),
                    'INTERMEDIATE_PRODUCER_INPUT_STATE_SUBSTITUTION')
                allowed_output={'covariance':'result/outputs/moment_covariance',
                                'bootstrap_gamma':'result/outputs/bootstrap_gamma'}
                field_name=name.split('.',1)[-1]
                require(name==field_name or name.split('.',1)[0] in
                    {'U01_FIELLER','U02_LOG_DELTA','U03_TWO_AXIS_PERCENTILE'},
                    'UNQUALIFIED_INTERMEDIATE_RULE_NAMESPACE')
                require(allowed_output.get(field_name)==descriptor['logical_output'],
                        'UNQUALIFIED_REFERENCE_INTERMEDIATE_FIELD')
            if descriptor['role']=='protected_truth':
                require(namespace=='protected_grade' and access is not None,'EARLY_TARGET_READ')
                access.check('before_each_protected_target_body')
            allowed={'reference_input','training_input','calibration_input','training_truth',
                     'calibration_truth','raw_preparation_input','fit_state','R_input','I_input'}
            if descriptor['role']=='reference_product':allowed.add('reference_product')
            if namespace=='trusted_collection':allowed|={'sealed_own_product'}
            if namespace=='protected_grade':allowed|={'protected_truth','sealed_own_product','reference_product'}
            self.store.admit(descriptor,allowed)
            sandbox=f'/inputs/{index:06d}'
            mounts.append({'source':str(self.store.root/descriptor['path']),
                           'destination':sandbox,'readonly':True,'descriptor':descriptor})
            decoded[name]={'sandbox_path':sandbox,'bytes':descriptor['bytes'],'sha256':descriptor['sha256'],
                           'shape':descriptor['shape'],'dtype':descriptor['dtype'],
                           'format':'npy_numeric_v1','readonly':True}
        self.counter+=1;rid=f'science-{self.counter:08d}'
        transport=ParameterTransport(self.store,f'jobs/{rid}/parameter-tables',rid,
                   'protected_parameter' if namespace=='protected_grade' else 'scientific_parameter')
        transported=transport.externalize(parameters)
        tables={}
        for table,spec in transport.tables.items():
            parts=[]
            for desc in spec['parts']:
                sandbox=f'/tables/{len(mounts):08d}'
                mounts.append({'source':str(self.store.root/desc['path']),'destination':sandbox,
                               'readonly':True,'descriptor':desc})
                parts.append({'sandbox_path':sandbox,'bytes':desc['bytes'],'sha256':desc['sha256']})
            tables[table]={**spec,'parts':parts}
        req={'schema':'finite_scientific_request_v1','request_id':rid,'operation':operation,
             'arrays':decoded,'protocol':protocol,'parameters':transported,'tables':tables,
             'max_parameter_rows':self.environment['max_parameter_rows'],
             'original_deadline':self.meter.deadline,'lineage':lineage,
             'source_manifest_sha256':self.source['source_manifest_sha256'],
             'issuer_namespace':namespace,'scientific_execution_qualified':True}
        work=self.work_root/rid;self.meter.checkpoint('scientific_work_directory')
        work.mkdir(parents=True,mode=0o700,exist_ok=False)
        result=self.host.run(req,request_id=rid,command=self.source['entry_command'],
             source_sha256=self.source['source_manifest_sha256'],mounts=mounts,
             state_seals=lineage.get('state_seals',{}),workdir=work,
             output_capacity=self.environment['max_control_stdout'],
             artifact_write_capacity=self.environment['max_job_artifact_bytes'],
             environment=self.environment['environment'],context={'network':False,'readonly_state':True,
             'allowed_roles':sorted({x['descriptor']['role'] for x in mounts}|{'qualified_scientific_source'}),
             'namespace':namespace,'no_participant_output_as_reference':True,
             'tool_environment_sha256':self.environment['source_environment_sha256'],
             'output_directory_host':str(work/'outputs')})
        record=decode(result['stdout'])
        require(record['request_id']==rid and record['request_sha256']==identity(req),
                'SCIENCE_REQUEST_SUBSTITUTION')
        require(record['source_manifest_sha256']==self.source['source_manifest_sha256']
                and record['lineage']==lineage,'SCIENCE_SOURCE_OR_PARENT_SUBSTITUTION')
        original_response=self.store.write(f'jobs/{rid}/original-scientific-response.json',result['stdout'],
            role='original_scientific_response',producer=result['receipt']['sha256'])
        canonical={}
        for artifact in record['artifacts']:
            relative=relative_path(artifact['path'])
            artifact.update({'path':f'jobs/{rid}/outputs/'+relative,'role':
                (prepared_output_role(relative.removesuffix('.npy'),protocol) if namespace=='trusted_preparation' else 'reference_product'),
                'media_type':'application/x-npy','logical_output':relative.removesuffix('.npy'),
                'units':protocol.get('output_units',{}).get(relative.removesuffix('.npy'),'unspecified')})
            if namespace=='trusted_preparation' and artifact['role']=='protected_truth':
                # Issuer/monitor owns the original produced bytes and receipt. The
                # controller reads scalar/certificate bodies only at target-last.
                self.store.admit(artifact,{'protected_truth'})
            else:self.store.read(artifact,{artifact['role']})
            canonical[relative]=dict(artifact)
            self.output_registry[(artifact['path'],artifact['sha256'])]={'descriptor':dict(artifact),'lineage':lineage,
                'namespace':namespace,'receipt':result['receipt'],'source':self.source['source_manifest_sha256']}
        def bind(value):
            if isinstance(value,dict):
                if set(value)=={'artifact'}:
                    old=value['artifact'];new=canonical.get(old['path'])
                    require(new is not None and new['sha256']==old['sha256'] and new['bytes']==old['bytes'],
                            'NESTED_SCIENTIFIC_ARTIFACT_SUBSTITUTION')
                    return {'artifact':new}
                return {k:bind(v) for k,v in value.items()}
            if isinstance(value,list):return [bind(v) for v in value]
            return value
        record['result']=bind(record['result'])
        record['array_outputs']={a['logical_output'][len('result/outputs/'):]:a for a in record['artifacts']
            if a['logical_output'].startswith('result/outputs/') and '/' not in a['logical_output'][len('result/outputs/'):]}
        record['original_response']=original_response
        self.meter.checkpoint('after_scientific_output_before_next_effect')
        return {'request':req,'response':record,'process_receipt':result['receipt'],
                'completion':result['completion'],'product_sha256':identity(record)}
