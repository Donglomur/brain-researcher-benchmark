"""Original complete NEURAL-022 packet projection and submitted-programme route."""
import argparse
import os
from pathlib import Path
import signal
import sys
import time
import types
import uuid

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import (IMAGE,PACKET,PUBLIC,VENDOR,authenticate,capture,contract,decode,
                    encoded,file_mount,need,ordinary,pin,publish,scientific_mounts)
from transport.provider import Provider
from transport.bounds import mount_identity
import grade

BASE_LIMITS={'memory_bytes':3221225472,'cpu_nanos':1500000000,'pids':64,'scratch_bytes':67108864,
             'max_directories':1,'manifest_bytes':16384,'max_cli_calls':128,'max_cli_bytes':4194304,
             'inventory_bytes':65536,'source_read_bytes':16777216,'host_write_bytes':4194304}
PROJECT_LIMITS=BASE_LIMITS|{'setup_seconds':10,'producer_seconds':90,'capture_seconds':10,'cleanup_seconds':30,
                         'max_files':8,'max_file_bytes':524288,'max_output_bytes':2097152}
CANDIDATE_LIMITS=BASE_LIMITS|{'setup_seconds':20,'producer_seconds':20,'capture_seconds':10,'cleanup_seconds':20,
                           'max_files':3,'max_file_bytes':65536,'max_output_bytes':262144}


def configuration(path,stage):
    value=decode(capture(path,32768));need(value['schema']=='neural022_delivery_configuration_v1','Exact operator configuration')
    need(value['image']==IMAGE,'Original immutable numerical image')
    for name in ('docker_binary','docker_socket','control_root','quarantine_root'):
        need(type(value[name]) is str and Path(value[name]).is_absolute(),'Absolute operator '+name);ordinary(value[name])
    source=authenticate(value['source'])
    policy=decode(capture(value['mechanical_policy_path'],32768,value['mechanical_policy_pin']))
    need(policy['schema']=='neural022_delivery_boundary_v1' and policy['source']==source and policy['image']==IMAGE
         and policy['approved_rule']=='exact_original_projection_then_public_candidate_then_private_grade'
         and policy['operator_approved'] is True,'Independent exact source/image/input-boundary policy')
    need(type(policy['image_inventory_sha256']) is str and len(policy['image_inventory_sha256'])==64,'Frozen image inventory')
    allocation=decode(capture(value['allocation_path'],32768,value['allocation_pin']))
    whole=150 if stage=='prepare' else 210
    need(allocation['schema']=='neural022_fresh_delivery_allocation_v1' and allocation['source']==source
         and allocation['stage']==stage and allocation['operator_approved'] is True
         and allocation['historical_failed_projection_seconds']==150 and allocation['new_whole_seconds']==whole,
         'Fresh source-specific stage grant preserves the failed 150 s projection')
    prior=allocation['current_prior_cumulative_seconds'];ceiling=allocation['new_cumulative_ceiling_seconds']
    need(type(prior) in (int,float) and 150<=prior<1e12 and type(ceiling) in (int,float)
         and prior+whole<=ceiling<1e12,'Current history and full-attempt cumulative capacity, never an old reset')
    need(type(allocation['current_history_sha256']) is str and len(allocation['current_history_sha256'])==64,
         'Current external history identity')
    need(allocation['operator_artifact_bytes']>=16777216,'Original 16 MB reserve plus bounded operator metadata')
    return value,policy,allocation,source


def public_validator():
    """Only captured, authenticated, pure-stdlib public-format code runs on host."""
    identity=contract()['local_sources']['candidate.py']
    body=capture(VENDOR/'candidate.py',16384,identity)
    module=types.ModuleType('neural022_public_validator')
    exec(compile(body,'neural022-original-candidate.py','exec'),module.__dict__)
    return module


def admit_public(raw,cases_raw):
    module=public_validator();public=module.strict(cases_raw)
    module.cases(public)  # A malformed operator case roster is never candidate invalidity.
    try:module.validate(raw,public)
    except (ValueError,TypeError,OverflowError,UnicodeError,RecursionError):
        def forbidden(*unused):raise AssertionError('Public invalidity never reaches private grading')
        return module.evaluate(raw,public,forbidden,forbidden,None)
    return None


def packet_metadata(config,source):
    root=ordinary(config['packet_root'])
    value=decode(capture(root/'PACKET.json',32768,config['packet_pin']))
    need(value['schema']=='neural022_delivery_packet_v1' and value['source']==source
         and value['source_contract']==pin(capture(HERE/'original/CONTRACT.json',65536))
         and value['public_training_rows']==141 and value['public_query_rows']==92
         and set(value['files'])==set(PACKET) and value['projection_resources_absent'] is True,
         'Exact complete source-frozen packet and observed projection closure')
    # No private file identity/stat/hash/open here. PACKET is operator metadata only.
    return root,value


class Native:
    def __init__(self,config,policy,output,source,origin,deadline):
        self.config,self.policy,self.output,self.source=config,policy,output,source
        self.origin,self.deadline=origin,deadline

    def phase(self,mode,mounts):
        projection=mode=='project';limits=PROJECT_LIMITS if projection else CANDIDATE_LIMITS
        role='operator' if projection else 'A';action='prepare_originals' if projection else 'held_attempt'
        phase=uuid.uuid4().hex;command=['/usr/local/bin/python','-I','-B','/library/worker.py',mode]
        mounts=mounts|{'/library/worker.py':file_mount(HERE/'worker.py',pin(capture(HERE/'worker.py',32768)),'program')}
        exposure={'schema':'osl_transport_exposure_v1','role':role,'image':IMAGE,'source':self.source,'command':command,
                  'mounts':mount_identity(mounts),'approved_image_inventory_sha256':self.policy['image_inventory_sha256'],
                  'boundary_audit':self.config['mechanical_policy_pin'],'role_boundary_verified':True}
        exposure_path=self.output/(mode+'-EXPOSURE.json');exposure_pin=publish(exposure_path,encoded(exposure))
        provider=Provider(self.config['control_root'],self.config['quarantine_root'],self.config['docker_binary'],
                          self.config['docker_socket'],pin(capture(HERE/'transport/SOURCE_MANIFEST.json',32768)),
                          {exposure_pin['sha256']:str(exposure_path)},limits['source_read_bytes']+1048576,limits['host_write_bytes'])
        phase_deadline=self.deadline if projection else self.deadline-110
        request={'schema':'osl_owned_phase_request_v1','phase_id':phase,'action':action,'role':role,'image':IMAGE,
                 'command':command,'workdir':'/work','source':self.source,'exposure':exposure_pin,
                 'clock':{'origin':self.origin,'phase_deadline':phase_deadline},'resources':limits.copy(),
                 'output':{'kind':'generic','manifest':'OUTPUTS.json'}}
        publish(self.output/(mode+'-REQUEST.json'),encoded(request))
        def journal(name,row):
            if name=='OWNERSHIP':publish(self.output/(mode+'-OWNERSHIP.json'),encoded(row))
        completed=provider.execute_phase(request,mounts,self.deadline,journal)
        observed=provider.observe(phase,pin(encoded(request))['sha256'],completed['receipt_pin'],self.deadline)
        receipt=observed['receipt']
        publish(self.output/(mode+'-TRANSPORT.json'),encoded(completed))
        need(receipt['status']=='captured' and receipt['producer_closed_before_capture'] is True
             and receipt['all_native_resources_closed'] is True and receipt['cli_reaped'] is True
             and receipt['error'] is None and receipt['natural_exit']['ExitCode']==0
             and receipt['natural_exit']['OOMKilled'] is False,'Observed successful stopped producer and full closure')
        need(receipt['source']==self.source and receipt['role']==role and receipt['image']==IMAGE
             and receipt['exposure']==exposure_pin and receipt['input_before']==receipt['input_after'],
             'Exact source, role and complete immutable input join')
        root=ordinary(receipt['quarantine_root'])
        need(root==ordinary(Path(self.config['quarantine_root'])/phase),'Exact owned capture root')
        files=receipt['output_inventory']['files'];wanted=set(PACKET) if projection else {'predictions.json'}
        need(receipt['output_inventory']['complete'] is True and set(files)==wanted|{'RESULT.json','OUTPUTS.json'},
             'Complete original output roster')
        need(decode(capture(root/'RESULT.json',16384,files['RESULT.json']))==
             {'schema':'neural022_worker_exit_v1','mode':mode,'exit_code':0},'Diagnostic wrapper consistency; actual exit separately observed')
        return root,files,{'phase':phase,'receipt':completed['receipt_pin'],'source':self.source,
                           'producer_removed_before_capture':True,'all_native_resources_closed':True}

    def project(self):
        value=contract();root=ordinary(self.config['original_inputs_root'])
        mounts=scientific_mounts('project.py')
        mounts['/input/receipt.json']=file_mount(root/'receipt.json',value['closed_worker_receipt'],'operator_reference')
        for item in value['saved_inputs'].values():
            mounts['/input/'+item['mount_name']]=file_mount(root/item['original_filename'],item['pin'],'operator_reference')
        return self.phase('project',mounts)

    def produce(self,packet_root,packet,program_pin):
        mounts={'/input/'+name:file_mount(packet_root/name,packet['files'][name],'input') for name in PUBLIC}
        mounts['/program/program.py']=file_mount(self.output/'program.py',program_pin,'program')
        return self.phase('candidate',mounts)


def prepare(backend,output,source):
    root,files,closure=backend.project()
    value=contract();receipt=decode(capture(root/'receipt.json',65536,files['receipt.json']))
    need(receipt['status']=='complete_reused_closed_projection' and receipt['source_contract']==pin(capture(HERE/'original/CONTRACT.json',65536))
         and receipt['source_worker_receipt']==value['closed_worker_receipt'] and receipt['models_fitted']==receipt['new_predictions_computed']==0
         and receipt['public_training_rows']==141 and receipt['public_query_rows']==92 and receipt['private_query_targets']==92,
         'Original complete no-refit sanitized projection')
    need(set(receipt['files'])==set(PACKET)-{'receipt.json'}
         and all(receipt['files'][n]==files[n] for n in receipt['files']),'Original receipt joins complete captured packet')
    packet_root=output/'packet';packet_root.mkdir(mode=0o700)
    identities={}
    for name in PACKET:
        identities[name]=publish(packet_root/name,capture(root/name,value['packet_output_caps'][name],files[name]),0o444)
    metadata={'schema':'neural022_delivery_packet_v1','source':source,'source_contract':receipt['source_contract'],
              'files':identities,'public_training_rows':141,'public_query_rows':92,'projection_resources_absent':True,
              'projection_closure':closure,'new_model_fits':0,'new_reference_predictions':0,
              'runtime_qualified':False,'scientific_qualification':False}
    identity=publish(packet_root/'PACKET.json',encoded(metadata))
    publish(output/'COMPLETE.json',encoded({'status':'complete_source_bound_packet_delivery','packet':identity,
                                          'authentic_scientific_success_not_inferred':True}))
    return metadata


def complete(backend,config,output,source,program_pin,grader,deadline):
    packet_root,packet=packet_metadata(config,source)
    authenticate(source);capture(output/'program.py',200000,program_pin)
    root,files,closure=backend.produce(packet_root,packet,program_pin)
    need(closure['source']==source and closure['producer_removed_before_capture'] is True
         and closure['all_native_resources_closed'] is True,'Candidate absent before any private dispatch')
    raw=capture(root/'predictions.json',65536,files['predictions.json'])
    # Re-publish stopped prediction bytes into an immutable participant-readable snapshot.
    submission=output/'predictions.json';submission_pin=publish(submission,raw,0o444)
    capture(output/'program.py',200000,program_pin);authenticate(source)
    publish(output/'PREDICTION_COMMIT.json',encoded({'candidate_closure':closure,'program':program_pin,'prediction':submission_pin}))
    cases=capture(packet_root/'cases.json',16384,packet['files']['cases.json'])
    result=admit_public(raw,cases)
    if result is None:
        need(time.monotonic()+80<=deadline,'Full grader phase remains inside original programme work interval')
        result=grader(config,output/'grade',packet_root,packet,submission,submission_pin,source,deadline)
    else:
        need(result['status']=='invalid_submission' and result['primary_score'] is None and result['private_target_loads']==0,
             'Original invalid/null disposition with no private dispatch')
    publish(output/'SCORE.json',encoded(result))
    publish(output/'COMPLETE.json',encoded({'schema':'neural022_program_completion_v1','status':result['status'],
            'program':program_pin,'prediction':submission_pin,'source':source,'runtime_qualified':False,
            'scientific_qualification':False,'automatic_retry_authorized':False}))
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=('prepare','run'))
    for name in ('configuration','output'):parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--program',type=Path);args=parser.parse_args(argv)
    origin=time.monotonic();config,policy,allocation,source=configuration(args.configuration,args.stage)
    deadline=origin+allocation['new_whole_seconds'];work_end=deadline-30
    need(signal.getitimer(signal.ITIMER_REAL)==(0.,0.),'No inherited process timer')
    def hard(*unused):os._exit(124)
    def interrupted(*unused):
        signal.signal(signal.SIGALRM,hard);signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-time.monotonic()))
        raise TimeoutError('Original work deadline; preserve exact ownership evidence')
    signal.signal(signal.SIGALRM,interrupted)
    # Projection transport has its own 120 s work /30 s cleanup allocation; an outer
    # early signal would interrupt that owned cleanup. Absolute hard cutoff is common.
    signal.signal(signal.SIGALRM,hard if args.stage=='prepare' else interrupted)
    signal.setitimer(signal.ITIMER_REAL,max(.001,(deadline if args.stage=='prepare' else work_end)-time.monotonic()))
    output=ordinary(args.output);created=False
    try:
        need(not output.exists() and output.parent.is_dir(),'Fresh one-shot operator output')
        if args.stage=='run':
            need(args.program is not None,'One programme source');program=capture(args.program,200000)
        output.mkdir(mode=0o700);created=True
        publish(output/'ALLOCATION.json',encoded(allocation))
        backend=Native(config,policy,output,source,origin,deadline)
        if args.stage=='prepare':prepare(backend,output,source);return 0
        identity=publish(output/'program.py',program,0o444)
        publish(output/'COMMIT.json',encoded({'schema':'neural022_program_commit_v1','source':source,'program':identity,
                                             'before_public_input_release':True,'complete_query_rows':92}))
        result=complete(backend,config,output,source,identity,grade.execute,work_end)
        return 0 if result['status']=='scored_exposed_transfer_candidate' else 2
    except BaseException as error:
        if created:publish(output/'FAILED.json',encoded({'error_type':type(error).__name__,'stage':args.stage,'source':source,
            'prior_failed_projection_seconds':150,'new_allocation_seconds':allocation['new_whole_seconds'],
            'preserve_partial_outputs':True,'automatic_retry_authorized':False,
            'closure':'Use exact transport/grade ownership receipts; absence is never inferred.'}))
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)


if __name__=='__main__':raise SystemExit(main())
