"""Future externally isolated candidate execution, identical A/B quotas and inputs."""
from pathlib import Path
from .guard import need,encoded,bare,Publisher,capture,capture_created,strict,ordinary
from .array_io import verify_file
from .controller import run_owned

def execute(root,submission,authority,budget,output):
    need(authority['candidate_execution_selected'] is True,'separate explicit candidate selection')
    need(authority['submission']==bare(encoded(submission)),'exact frozen candidate invocation')
    lease=strict(capture(root,authority['external_isolation'],budget))
    need(lease['qualified'] is True and lease['network']=='disabled' and lease['deadline_ns']==budget.deadline_ns,'independent candidate isolation required')
    need(lease['private_reference_mounted'] is False and lease['other_arm_mounted'] is False,'private answers and alternative arm inaccessible')
    need(submission['arm'] in ('A','B') and submission['budget_identity']==authority['matched_arm_budget_identity'],'same declared A/B compute')
    for file in submission['source_files']:verify_file(root,file,budget)
    binary=verify_file(root,submission['executable'],budget);publisher=Publisher(output,budget)
    cwd=ordinary(root,submission['working_directory']);need(cwd.is_dir(),'isolated candidate workspace')
    need(not ordinary(root,submission['result_path']).exists(),'fresh candidate output path')
    argv=[str(binary),*submission['arguments']]
    try:
        observation=run_owned(argv,str(cwd),submission['environment'],budget,stream_limit=submission['stream_limit_bytes'],limits=submission['process_limits'])
        # Actual candidate output is captured by an externally admitted descriptor, not inferred from exit0.
        body,result_input=capture_created(root,submission['result_path'],budget,cap=submission['maximum_result_bytes']);document=strict(body)
        need(document['schema']=='hundred_models_submission_v2' and 'custody' not in document,'candidate supplies scientific output; operator attaches actual own-run custody')
        document['custody']={'schema':'hundred_models_own_run_custody_v1','inputs':authority['inputs'],'plan':authority['plan'],'runtime_source':bare(encoded(submission['source_files'])),'environment':bare(encoded(submission['environment'])),'source_workspace':str(cwd),'raw_endpoint_records':bare(body)}
        result=publisher.write('candidate_result.json',encoded(document))
        return publisher.write('CANDIDATE_RECEIPT.json',encoded({'submission':bare(encoded(submission)),'result':result,'completion':observation['completion'],'stdout_hex':observation['stdout'].hex(),'stderr_hex':observation['stderr'].hex(),'scientific_qualification':False}))
    except BaseException as error:error.known_output_prefix=publisher.state();raise
