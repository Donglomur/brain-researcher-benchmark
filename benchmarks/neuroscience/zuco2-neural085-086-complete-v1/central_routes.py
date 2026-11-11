"""Staged exact default/named central source templates; never installs a registry."""
from zuco.constants import ARMS,REPRESENTATIONS,MODES
from zuco.io import need

def proposal(prefix,run_sha256,score_sha256):
    need(type(prefix)is str and not prefix.startswith('/') and '..'not in prefix.split('/'),'portable_package_prefix')
    result={}
    for task in ARMS:
        def execution(rep,mode):
            return {'entrypoint':{'argv':['python3',prefix+'/run_program.py','--task',task,'--program','{program}','--output','{output}','--review','{review}','--other-reserve-bytes','{other_reserve_bytes}','--representation',rep,'--mode',mode],'sha256':run_sha256,'working_directory':'.'},'qualification':None,'deployment_enabled':False,'information_set':'offline_case_local','full_task_scientifically_qualified':False}
        default=execution('released_summary','frozen_program');conditions={rep+'__'+mode:execution(rep,mode) for rep in REPRESENTATIONS for mode in MODES};conditions['released_summary__frozen_program']='default'
        result[task]={'id':task,'program_execution':default,'program_conditions':conditions,'entrypoints':{'score':{'argv':['python3',prefix+'/score_campaign.py','--submission','{submission}','--output','{output}','--review','{review}','--other-reserve-bytes','{other_reserve_bytes}'],'sha256':score_sha256,'working_directory':'.'}},'verification':None,'deployment_enabled':False,'status':'source proposal; separate integration/qualification required','decoder_tool_variant':'unadmitted; separately qualified source/image/checkpoint required','condition_alias_disclosure':'N085 released_summary and band_spatial have identical 840 mean features; no additional benchmark identity'}
    return result
