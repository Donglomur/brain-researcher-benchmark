"""Concrete external whole-controller observation and independent final admission."""
import os
from pathlib import Path
import common as c
import authority,closure,grading,protocol as p
from host_observation import Bridge,admit as admit_host
from transport.process import ProcessObserver

def launch_request(source,controller,outer_output,controller_entry,bootstrap_read_cap,run):
    """Construct the complete prior request; no later authority/envelope pin.

    An operator first publishes this immutable metadata, then obtains independent
    request-bound authority, then joins both descriptors in the final envelope.
    This pure constructor reads no operand and grants no execution authority.
    """
    c.descriptor(source);c.descriptor(controller_entry)
    c.exact(controller,('schema','source','run','channel','output_root','protected_roots','native_config','preparation','preparation_manifest','reference_manifest','issuer_manifest','issuer_worker_limits','issuer_sandbox','host_python','host_environment','provider_config','replication_seeds','public_protocol','tool_source','candidate_runner','numeric_source','grade_manifest','grade_worker_io','host_metadata_capacity_bytes'))
    c.need(controller['schema']=='neural081_complete_controller_v1'and c.typed_equal(controller['source'],source),'complete original controller request payload')
    c.descriptor(controller['run']);c.absolute(outer_output);c.absolute(controller['output_root'])
    c.integer(bootstrap_read_cap,1,64*2**20)
    c.need(type(run)is dict and type(run.get('origin'))is float and type(run.get('normal_endpoint'))is float,'original typed launch clock')
    origin=c.finite(run['origin'],0);endpoint=c.finite(run['normal_endpoint'],0)
    c.need(origin<endpoint,'original positive launch interval')
    return c.parse(c.encoded({'schema':'neural081_outer_launch_request_v1','source_manifest':source,
        'controller':controller,'outer_output':outer_output,'controller_entry':controller_entry,
        'bootstrap_read_cap':bootstrap_read_cap,'run':controller['run'],
        'original_origin':origin,'normal_endpoint':endpoint}))

def admit_launch(envelope,envelope_desc,source,source_files,run,budget):
    """Authenticate the earlier complete request before real role admission."""
    c.exact(envelope,('schema','source_manifest','controller','launch_request','outer_authority','outer_output','controller_entry','bootstrap_read_cap'))
    c.need(envelope['schema']=='neural081_selected_execution_envelope_v2'and c.typed_equal(envelope['source_manifest'],source),'exact acyclic outer envelope')
    c.descriptor(envelope_desc)
    expected=launch_request(source,envelope['controller'],envelope['outer_output'],envelope['controller_entry'],envelope['bootstrap_read_cap'],run)
    protected=[c.absolute(v)for v in envelope['controller']['protected_roots']]
    for name in ('launch_request','outer_authority'):
        c.descriptor(envelope[name]);path=c.absolute(envelope[name]['path'])
        c.need(not any(path.is_relative_to(root)for root in protected),'outer launch metadata outside protected bodies')
    request=c.capture_json(envelope['launch_request'],budget,[Path(envelope['launch_request']['path']).parent])
    c.need(c.typed_equal(request,expected),'exact entire prior launch request equals final selected payload')
    selected=c.capture_json(envelope['outer_authority'],budget,[Path(envelope['outer_authority']['path']).parent])
    c.need(c.typed_equal(selected['run'],envelope['controller']['run']),'outer authority binds the original controller run descriptor')
    admitted,conditions=authority.admit(selected,source,envelope['launch_request'],'G0','outer',budget,source_files,protected_roots=envelope['controller']['protected_roots'])
    c.need(c.typed_equal(admitted,run),'actual admitted original run body equals captured entry run')
    return selected,conditions

def execute(envelope,envelope_desc,source,source_files,run,budget):
    selected,conditions=admit_launch(envelope,envelope_desc,source,source_files,run,budget)
    config=envelope['controller'];c.need(c.typed_equal(conditions['observer'].get('entry'),envelope['controller_entry'])and envelope['controller_entry']in source_files,'exact independently selected controller entry')
    c.need(c.typed_equal(conditions['provider'].get('configuration'),config['provider_config']),'exact original provider metadata before selected credential forwarding')
    provider=c.capture_json(config['provider_config'],budget,[Path(config['provider_config']['path']).parent]);name=provider['api_key_env']
    c.need(type(name)is str and conditions['provider'].get('launch_credential_name')==name,'one exact permitted environment name')
    env=dict(config['host_environment']);c.need(name not in env and c.typed_equal(conditions['observer'].get('host_environment'),env),'clean independently selected source environment')
    value=os.environ.get(name);c.need(type(value)is str and value,'single selected credential available');env[name]=value
    python=c.absolute(config['host_python']);c.need(conditions['observer'].get('host_python')==str(python),'qualified original host interpreter')
    entry=envelope['controller_entry'];argv=[str(python),'-I','-B',entry['path'],'--operation','controller','--config',envelope_desc['path'],'--config-bytes',str(envelope_desc['bytes']),'--config-sha256',envelope_desc['sha256'],'--source',source['path'],'--source-bytes',str(source['bytes']),'--source-sha256',source['sha256'],'--origin',str(budget.origin),'--deadline',str(budget.end),'--bootstrap-read-cap',str(envelope['bootstrap_read_cap'])]
    root=c.new_directory(envelope['outer_output'],budget)
    intent=c.publish_json(root/'INTENT.json',{'schema':'neural081_outer_controller_intent_v1','source':source,'envelope':envelope_desc,'launch_request':envelope['launch_request'],'argv':argv,'origin':budget.origin,'normal_endpoint':budget.end,'credential_names':[name],'credential_values_recorded':False},budget)
    try:
        original=ProcessObserver().run(argv,cwd='/',env=env,budget=Bridge(budget),seconds=max(0,budget.end-budget.clock()),cleanup_seconds=120,stream_cap=262144)
    except BaseException as error:
        evidence=getattr(error,'evidence',None)
        # This best-effort failure record is never a successful outer admission.
        try:c.publish_json(root/'FAILURE.json',{'schema':'neural081_original_outer_failure_v1','intent':intent,'type':type(error).__name__,'original_evidence':evidence,'partial_or_unknown':True,'automatic_retry':False},budget)
        except BaseException:pass
        raise
    finally:
        del value;env.pop(name,None)
    streams={k:c.publish(root/(k.upper()+'.txt'),original[k],budget)for k in('stdout','stderr')}
    observation=c.publish_json(root/'ORIGINAL_OBSERVATION.json',original['observation'],budget)
    admit_host(original['observation'],argv,budget.origin,budget.end,streams['stdout'],streams['stderr'])
    # The selected output filename is source-owned. Its actual extent/pin is
    # captured only after the original controller has naturally stopped.
    path=c.absolute(config['output_root'])/'RESULT.json';size=path.lstat().st_size;c.integer(size,1,16*2**20)
    budget.charge('read_bytes',size+1)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        with os.fdopen(fd,'rb',closefd=False)as stream:raw=stream.read(size+1)
        after=os.fstat(fd);named=path.lstat();fields=('st_dev','st_ino','st_size','st_mode','st_nlink','st_mtime_ns','st_ctime_ns')
        c.need(len(raw)==size and before.st_nlink==1 and all(getattr(before,k)==getattr(after,k)==getattr(named,k)for k in fields),'actual complete stable original controller result')
    finally:os.close(fd)
    result_desc={'path':str(path),**c.pin(raw)};result=c.parse(raw)
    c.need(result['schema']=='neural081_provisional_complete_controller_v1'and c.typed_equal(result['source'],source)and result['status']=='provisional_until_independent_whole_controller_natural_exit','same actual complete controller provisional result')
    # Index is label-free; both protected operands are discovered as identities,
    # never opened by this external observer even though grading already ended.
    index=p.validate_index(c.capture_json(result['index'],budget,[Path(result['index']['path']).parent]));protected=[index[k]for k in('protected_support_descriptor','protected_assessment_descriptor')]
    audit=closure.AuditAccess([c.absolute(config['output_root']),config['channel']['request_root'],config['channel']['response_root'],*[r['authority']['channel_root']for r in result['channel_records']],*[Path(d['path']).parent for d in source_files]],protected,[],budget)
    graph=closure.admit(result['study'],index,audit,source);grading.admit_panels(index,graph['panels'],audit,source)
    closure.qualifications(result['channel_records'],source,source_files,audit,phases=('G0','G1','G2','G3','G5'))
    actual_grade=closure.native(result['grade']['closure'],audit,source_files,expected_job='G5/complete',expected_kind='grader')
    c.need(result['grade']['result']in actual_grade['artifacts'],'actual source-owned protected scorer output')
    score=audit.json(result['grade']['result']);c.need(c.typed_equal(score['study'],result['study'])and score['protected_reads_after_full_barrier']is True and score['provider_or_candidate_resume_allowed']is False,'same closed protected source grader')
    for d in source_files:audit.read(d)
    report={'schema':'neural081_independent_outer_admission_v1','source':source,'intent':intent,'launch_request':envelope['launch_request'],'original_observation':observation,'streams':streams,'controller_result':result_desc,'study':result['study'],'grade':result['grade'],'all_original_counts':p.counts(index),'original_origin':budget.origin,'normal_endpoint':budget.end,'completed_monotonic':budget.clock(),'status':'admitted_after_actual_natural_controller_and_complete_source_graph','budget':budget.snapshot(),'scientific_performance_not_established_by_source_build':True}
    budget.check_clock();return c.publish_json(root/'ADMISSION.json',report,budget)
