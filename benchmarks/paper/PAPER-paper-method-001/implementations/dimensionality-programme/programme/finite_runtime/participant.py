"""Arbitrary participant source, tools, learned state and actual product lineage."""
from __future__ import annotations
from pathlib import Path
from .common import require, identity, decode, encode, content_descriptor, relative_path
from .protocol import request, validate_response
from .truth import prediction_input

STAGE_ROLES={
 'describe':{'participant_source','common_specification','admitted_dictionary','paper_view','author_source'},
 'build':{'participant_source','common_specification','dependency_source','R_fit_state'},
 'learn':{'participant_source','build_artifact','training_input','training_truth','fit_state'},
 'calibrate':{'participant_source','build_artifact','calibration_input','calibration_truth','fit_state','calibration_ledger'},
 'author_R':{'participant_source','common_specification','paper_view','author_source','R_input'},
 'estimate':{'participant_source','build_artifact','fit_state','R_fit_state','R_input','I_input','calibration_input','allowed_case_metadata'},
 'report':{'participant_source','build_artifact','sealed_own_product','sealed_record_index','public_case_plan','common_specification','paper_view'} }
OUTPUT_ROLES={
 'describe':{'method_manifest'},'build':{'build_artifact','participant_source'},
 'learn':{'fit_state','fit_ancestry','search_ledger'},
 'calibrate':{'calibration_ledger'},'author_R':{'participant_source','R_fit_state','search_ledger'},
 'estimate':{'participant_product'},'report':{'participant_report'} }

class Participant:
    def __init__(self, source, *, run_id, participant_id, arm, plan_hash, host, inputs,
                 output_store, work_root, journal, meter, tools):
        self.source=source;self.run_id=run_id;self.participant_id=participant_id
        self.arm=arm;self.plan_hash=plan_hash;self.host=host;self.inputs=inputs
        self.outputs=output_store;self.work_root=Path(work_root);self.journal=journal;self.meter=meter
        self.tools=tools;self.counter=0;self.responses=[]
        require(source['participant_identity']==participant_id,'PARTICIPANT_IDENTITY_MISMATCH')
        require(source['entry_command'] and source['files'],'ACTUAL_PARTICIPANT_SOURCE_REQUIRED')
        require(source['source_manifest_sha256']==identity(source['files']), 'METHOD_SOURCE_MANIFEST_MISMATCH')
        for descriptor in source['files']:
            inputs.read(descriptor,{'participant_source'})
        require(tools['network'] is False,'PARTICIPANT_NETWORK_NOT_ALLOWED')
        require(tools['source_environment_sha256'],'QUALIFIED_TOOL_ENVIRONMENT_REQUIRED')
        require(tools['max_threads']<=16,'THREAD_LIMIT_EXCEEDED')

    def invoke(self,stage,payload,*,lane,protocol_id,artifacts=(),state_seals=None,source=None):
        self.meter.checkpoint('participant_stage_admission')
        source=source or self.source;state_seals=state_seals or {}
        roles=set(STAGE_ROLES[stage])
        if self.arm=='A':roles.discard('author_source')
        if lane=='I':roles.discard('R_input');roles.discard('R_fit_state')
        mounts=[]
        source_paths={x['path'] for x in source['files']}
        relative_path(source['root'])
        for index,artifact in enumerate([*source['files'],*artifacts]):
            if stage=='estimate' and artifact['role'] in {'R_input','I_input','calibration_input'}:
                prediction_input(artifact)
                require('prediction_origin' in artifact,'UNBOUND_PREDICTION_ORIGIN')
            self.inputs.admit(artifact,roles|{'participant_source'})
            require(artifact['role'] not in {'protected_truth','reference_product','reference_state'},
                    'REFERENCE_OR_TARGET_EXPOSURE')
            if artifact['path'] in source_paths:
                require(artifact['path'].startswith(source['root']+'/'),'SOURCE_ROOT_MISMATCH')
                destination='/method/'+relative_path(artifact['path'][len(source['root'])+1:])
            else:
                destination=f'/inputs/{index:06d}'
            mounts.append({'source':str(self.inputs.root/artifact['path']),
                           'destination':destination,'readonly':True,'descriptor':artifact})
        # Only sandbox paths enter the participant's message, never host paths or unassigned files.
        visible=[{'path':m['destination'],'logical_path':m['descriptor']['path'],
                  'sha256':m['descriptor']['sha256'],
                  'bytes':m['descriptor']['bytes'],'media_type':m['descriptor']['media_type'],
                  'role':m['descriptor']['role'],
                   **({'prediction_origin':m['descriptor']['prediction_origin']}
                      if 'prediction_origin' in m['descriptor'] else {})} for m in mounts]
        self.counter+=1;rid=f'{lane}-{stage}-{self.counter:08d}'
        req=request(run_id=self.run_id,arm=self.arm,lane=lane,protocol_id=protocol_id,
                    source=source['source_manifest_sha256'],plan=self.plan_hash,request_id=rid,
                    parent=self.journal.head,stage=stage,
                    payload={**payload,'visible_artifacts':visible,'tools':self.tools})
        work=self.work_root/rid
        self.meter.checkpoint('participant_job_directory');work.mkdir(mode=0o700,parents=True,exist_ok=False)
        result=self.host.run(req,request_id=rid,command=source['entry_command'],
                            source_sha256=source['source_manifest_sha256'],mounts=mounts,state_seals=state_seals,
                            workdir=work,output_capacity=self.tools['max_control_stdout'],
                            artifact_write_capacity=self.tools['max_job_artifact_bytes'],
                            environment=self.tools['environment'],context={'network':False,'readonly_state':True,
                            'allowed_roles':sorted(roles),'participant':self.participant_id,'stage':stage,
                            'lane':lane,'arm':self.arm,'isolated_scratch':True,'no_cross_job_state':True,'tool_environment_sha256':self.tools['source_environment_sha256'],
                            'output_directory_host':str(work/'outputs')})
        value=validate_response(decode(result['stdout']),req)
        for artifact in value['artifacts']:
            require(artifact['role'] in OUTPUT_ROLES[stage],'WRONG_STAGE_OUTPUT_ROLE')
            require(artifact['path'].startswith(f'jobs/{rid}/outputs/'),'OUTPUT_OUTSIDE_CURRENT_JOB')
            self.outputs.read(artifact,OUTPUT_ROLES[stage])
        self.meter.checkpoint('participant_product_after_validation')
        record={'request':req,'response':value,'process_receipt':result['receipt'],
                'process_completion':result['completion'],'visible_artifacts':artifacts,
                'product_sha256':identity(value)}
        self.responses.append(record)
        return record

    def derive_R_source(self,record):
        require(record['request']['payload']['stage']=='author_R','R_SOURCE_NEEDS_ACTUAL_AUTHORING')
        require(record['response']['payload']['status']=='ok','R_AUTHORING_FAILED')
        files=[x for x in record['response']['artifacts'] if x['role']=='participant_source']
        require(files,'R_SOURCE_NOT_PRODUCED')
        source={'participant_identity':self.participant_id,'files':files,
                'source_manifest_sha256':identity(files),
                'entry_command':record['response']['payload']['state']['entry_command'],
                'root':record['response']['payload']['state']['source_root'],
                'authoring_receipt':record['process_receipt']}
        return source

def public_case(case):
    allowed={'case_id','input_sha256','selection_sha256','protocol_id','requires_moments',
             'allowed_metadata','units','shape','target_axis','finite_population','metric_protocol'}
    result={k:v for k,v in case.items() if k in allowed}
    require({'case_id','input_sha256','selection_sha256','protocol_id','requires_moments'}<=set(result),
            'INCOMPLETE_CASE_VIEW')
    return result
