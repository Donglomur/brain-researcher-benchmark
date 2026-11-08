"""Actual qualified collection route; original protected grading stays separate."""
import base64
from pathlib import Path
import sys

TASK='NEURAL-060'
CONDITION='full29_two_modes_three_arms_v3'
REGISTRY='benchmarks/neuroscience/neural-060/manifest.json'
METADATA_RESERVE=268435456
WRITE_RESERVE=2097152
OUTER_RECEIPT_CAP=1048576
CALLER_CAP=65536
CAPTURED_PARENT='''import sys,time,signal,base64,hashlib
path=sys.argv[1];raw=base64.b64decode(sys.argv[2],validate=True)
end=float(sys.argv[3]);expected=sys.argv[4]
if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError("captured parent entry changed")
def expired(*_):raise TimeoutError("original parent closeout deadline")
if not time.monotonic()<end:raise TimeoutError("parent launch after original closeout")
for sig in (signal.SIGALRM,signal.SIGINT,signal.SIGTERM):signal.signal(sig,expired)
signal.setitimer(signal.ITIMER_REAL,end-time.monotonic())
sys.argv=[path,*sys.argv[5:]]
exec(compile(raw,path,"exec"),{"__name__":"__main__","__file__":path})
'''


def descriptor(row):
    u.need(type(row) is dict and set(row)=={'path','bytes','sha256'},'exact operator descriptor')
    u.only_pin(row)
    # Lexical only here; filesystem custody is checked by the eventual capture.
    p=Path(row['path']);u.need(type(row['path']) is str and p.is_absolute() and str(p)==row['path']
        and not row['path'].startswith('//') and '..' not in p.parts,'canonical absolute metadata descriptor')
    return row


def qualify(doc, env, host):
    u.need(type(doc) is dict and doc.get('id')==TASK,'fixed whole-study registry')
    # The common helper deliberately admits generic freezes. This task must bind
    # its entire executed closure, not merely a qualified wrapper file.
    meta=doc.get('program_execution')
    if type(meta) is dict and type(meta.get('verification')) is dict and meta['verification'].get('status')=='passed':
        frozen=meta['source_freeze'];u.need(type(frozen) is dict,'exact task freeze descriptor')
        path=env['here']/'QUALIFICATION_SOURCE_FREEZE.json'
        u.need(frozen.get('path')==str(path.relative_to(env['repo'])),'fixed complete task freeze path')
        fp=u.only_pin(frozen);raw=host.read(path,65536,fp);freeze=u.parse(raw)
        expected={str(Path(n).relative_to(env['repo'])):p for n,p in env['source_rows'].items()}
        u.need(freeze.get('schema')=='neural060_central_qualification_source_v1'
               and freeze.get('task_id')==TASK and freeze.get('files')==expected,
               'qualification must bind every captured central, caller, parent and campaign dependency')
        entry=meta['entrypoint'];index=env['gate'].python_launch(entry['argv'])
        u.need(entry['argv'][index]==str((env['here']/'entry.py').relative_to(env['repo']))
               and entry.get('sha256')==env['manifest']['files']['entry.py']['sha256']
               and entry.get('working_directory')=='.','qualified exact executed central entry')
        # Four bounded JSON captures; wrapper capture; all authenticated freeze
        # members; plus ONE failing growing source read (which aborts the helper).
        # The latter and wrapper each use the helper's16MiB cap. This is a
        # conservative logical reservation, not measured physical I/O.
        bound=4*(2097152+1)+2*(16777216+1)+sum(p['bytes']+1 for p in expected.values())
        host.reserve(bound)
    u.need(env['base'].verified_program_runtime(env['repo']/REGISTRY,doc,env['repo']),
           'not qualified: full NEURAL060 central programme requires independent passing evidence')
    host.tick()


def review_document(raw, env):
    r=u.parse(raw)
    fields={'schema','task_id','operation','execution_selected','central_source','parent_source','registration',
            'producer_authority','campaign_request','work_sha256','condition','original_origin','clock_evidence',
            'issuer','central_resource_qualified','caller_observer_qualified','physical_custody_qualified',
            'protected_grading_authorized','root_final_durability_admission_required','other_reserve_bytes','limits'}
    u.need(type(r) is dict and set(r)==fields and r['schema']=='neural060-central-review-v1'
           and r['task_id']==TASK and r['operation']=='collect' and r['execution_selected'] is True,
           'explicit root-selected collection-only operation')
    u.need(r['central_source']==env['source'] and r['parent_source']==env['parent'].pin,'distinct current central and parent sources')
    u.need(r['condition'] in (None,CONDITION) and type(r['issuer']) is str and r['issuer'], 'selected whole-study route and issuer')
    u.need(all(r[k] is True for k in ('central_resource_qualified','caller_observer_qualified','physical_custody_qualified',
           'root_final_durability_admission_required')) and r['protected_grading_authorized'] is False,
           'caller/resource/physical qualification required; grading not authorized')
    for k in ('registration','producer_authority','campaign_request','clock_evidence'):descriptor(r[k])
    u.only_pin({'bytes':0,'sha256':r['work_sha256']});r['original_origin']=u.finite(r['original_origin']);u.integer(r['other_reserve_bytes'])
    return r


def condition(doc, selected):
    if selected is not None:
        u.need(selected==CONDITION and type(doc.get('program_conditions')) is dict
               and doc['program_conditions'].get(selected)=='default','named alias preserves complete original programme')
    return doc


def campaign(r,doc,env,host):
    gate=env['gate'];repo=env['repo']
    host.reserve(gate.CAPTURE_CAP+gate.VALIDATOR['bytes']+1+gate.PREFERENCE_READ_CAP)
    result=gate.admit(repo,TASK,'run',r['condition'],r['campaign_request']['path'],r['campaign_request']['sha256'],r['work_sha256'])
    u.need(result['request']==u.only_pin(r['campaign_request']),'exact root campaign request')
    route=gate.preferred_route(repo,TASK,'run',r['condition'],r['work_sha256'],(repo/REGISTRY,doc))
    expected={'path':str(env['here'].relative_to(repo)),
              'source':{'path':str((env['here']/'SOURCE_MANIFEST.json').relative_to(repo)),**env['source']}}
    u.need(route['status']=='preferred_source_bound' and route['interface']==expected
           and route['registration']=={'path':REGISTRY,**u.only_pin(r['registration'])},'actual installed central source route')
    result['preferred_program_route']=route;result['metadata_read_charge_bytes']+=route['metadata_read_charge_bytes']
    host.tick();return result


def central_command(cli,doc,env):
    argv=doc['program_execution']['entrypoint']['argv'];index=env['gate'].python_launch(argv)
    values={'{program}':cli['program'],'{output}':cli['output'],'{review}':cli['review'],
            '{other_reserve_bytes}':str(cli['other_reserve_bytes'])}
    command=[sys.executable,*argv[1:index],str(env['repo']/argv[index]),*[values.get(v,v) for v in argv[index+1:]]]
    expected=['--program',cli['program'],'--output',cli['output'],'--review',cli['review'],
              '--other-reserve-bytes',str(cli['other_reserve_bytes']),'--source-bytes',str(env['source']['bytes']),
              '--source-sha256',env['source']['sha256']]
    u.need(command[index]==str(env['here']/'entry.py') and command[index+1:]==expected,
           'exact registered central wrapper and literal source arguments')
    u.need(cli['actual_argv']==command and cli['actual_cwd']==str(env['repo']), 'actual central argv/cwd custody')
    return command


def limits_for(original, selected):
    fields={'host_memory_bytes','free_floor_bytes'}
    u.need(type(selected) is dict and set(selected)==fields, 'root selected host memory and free floor')
    memory=u.integer(selected['host_memory_bytes'],1073741824);floor=u.integer(selected['free_floor_bytes'],1)
    journal=u.integer(original['observer_limits']['journal_bytes'],1)
    producer=u.integer(original['resources']['producer_bytes'],1)
    reads=METADATA_RESERVE+2*(journal+producer+OUTER_RECEIPT_CAP)
    readback=120+(reads+999999)//1000000
    return {'read_bytes':reads,'write_bytes':WRITE_RESERVE,'retained_bytes':WRITE_RESERVE,
            'host_memory_bytes':memory,'free_floor_bytes':floor,'readback_seconds':readback,
            'caller_cleanup_seconds':90,'caller_combined_stream_bytes':CALLER_CAP,'outer_receipt_bytes':OUTER_RECEIPT_CAP}


def clock_binding(r, original, env, host):
    u.need(r['issuer']==original['operator_identity'] and r['original_origin']==original['original_origin'],
           'same protected root issuer and original origin')
    expected=Path(original['operator_root'])/'CENTRAL_ORIGIN.json'
    u.need(r['clock_evidence']['path']==str(expected),'fixed protected root origin receipt')
    raw=host.read(expected,65536,u.only_pin(r['clock_evidence']),readonly=True);v=u.parse(raw)
    fields={'schema','issuer','actual_observation','clock_policy','original_origin','original_deadline',
            'central_source','parent_source','producer_authority','study_id'}
    u.need(type(v) is dict and set(v)==fields and v['schema']=='neural060-central-origin-binding-v1'
           and v['issuer']==r['issuer'] and v['actual_observation'] is True
           and v['clock_policy']=='root_monotonic_before_central_invocation'
           and v['original_origin']==r['original_origin'] and v['original_deadline']==original['whole_deadline']
           and v['central_source']==env['source'] and v['parent_source']==env['parent'].pin
           and v['producer_authority']==u.only_pin(r['producer_authority']) and v['study_id']==original['study_id'],
           'exact independently qualified root clock/authority binding')
    return u.pin(raw)


def observer_command(r, original, env):
    parent=env['parent'];raw=parent.bodies['entry.py'];bootstrap=parent.pins['bootstrap.py']
    close=u.finite(original['whole_deadline'])+u.integer(original['observer_limits']['closeout_seconds'],1)
    args=['observe','--repo',str(env['repo']),'--bootstrap-bytes',str(bootstrap['bytes']),
          '--bootstrap-sha256',bootstrap['sha256'],'--manifest-bytes',str(parent.pin['bytes']),
          '--manifest-sha256',parent.pin['sha256'],'--authority',r['producer_authority']['path'],
          '--authority-bytes',str(r['producer_authority']['bytes']),
          '--authority-sha256',r['producer_authority']['sha256'],'--original-origin',repr(r['original_origin'])]
    return [sys.executable,'-I','-S','-B','-c',CAPTURED_PARENT,str(env['parent_root']/'entry.py'),
            base64.b64encode(raw).decode('ascii'),repr(close),parent.pins['entry.py']['sha256'],*args]


def natural(record, command, repo, origin, normal_end, cleanup_end):
    u.need(type(record) is dict and record.get('natural_exit') is True
           and type(record.get('exit_code')) is int and record['exit_code']==0,'actual caller natural integer-zero exit')
    u.need(record.get('forced_termination_supported') is False and record.get('forced_termination_available') is False
           and record.get('no_mutating_signals') is True and record.get('mutating_signals_disabled') is True
           and type(record.get('mutating_signal_count')) is int and record['mutating_signal_count']==0
           and record.get('cleanup_mode')=='observation_and_bounded_wait_only',
           'root-selected central caller has no child termination capability')
    u.need(all(record.get(k) is True for k in ('successful_observation','process_reaped','process_group_absent',
               'streams_closed','selector_closed','stdout_eof','stderr_eof')),
           'actual caller reaping, group absence and both stream EOFs')
    u.need(all(record.get(k) is False for k in ('timed_out','kill_sent','term_sent','cleanup_attempted','parent_timer_elapsed',
               'cleanup_ownership_unknown','failed_unknown_child_state','requires_separate_child_inspection'))
           and all(record.get(k) is None for k in ('error_type','timer_disable_error','timer_restore_error')),
           'no forced/uncertain caller closure')
    u.need(record['argv']==command and record['cwd']==str(repo)
           and record['normal_end']==normal_end and record['cleanup_end']==cleanup_end
           and origin<=u.finite(record['observed_start'])<=u.finite(record['observed_end'])<normal_end,
           'exact caller invocation and inherited absolute deadlines')


def expected_worker(outer, r, original, env):
    command=outer['command'];parent=env['parent'];bp=parent.pins['bootstrap.py']
    u.need(type(command) is list and len(command)>=2 and command[-2]=='--journal-fd'
           and type(command[-1]) is str and command[-1].isdigit() and int(command[-1])>=3,
           'original independent inherited journal descriptor')
    expected=[sys.executable,'-I','-B',str(env['parent_root']/'entry.py'),'worker','--repo',str(env['repo']),
              '--bootstrap-bytes',str(bp['bytes']),'--bootstrap-sha256',bp['sha256'],
              '--manifest-bytes',str(parent.pin['bytes']),'--manifest-sha256',parent.pin['sha256'],
              '--authority',r['producer_authority']['path'],'--authority-bytes',str(r['producer_authority']['bytes']),
              '--authority-sha256',r['producer_authority']['sha256'],'--original-origin',repr(r['original_origin']),
              '--journal-fd',command[-1]]
    u.need(command==expected,'same actual original worker command and authority')


def readback(bundle, command, original, r, limits, env, host):
    origin=r['original_origin'];whole=original['whole_deadline']
    normal=whole+original['observer_limits']['closeout_seconds'];cleanup=normal+limits['caller_cleanup_seconds']
    natural(bundle['record'],command,env['repo'],origin,normal,cleanup)
    u.need(bundle['stdout']==b'' and bundle['stderr']==b'', 'unchanged parent success emits no caller streams')
    observation=Path(original['observation_root']);attempt=Path(original['attempt_root'])
    raw=host.read(observation/'OUTER.json',OUTER_RECEIPT_CAP,readonly=True);outer=u.parse(raw)
    u.need(outer.get('schema')=='neural060_outer_observation_v1' and outer.get('runtime_source')==env['parent'].pin
           and outer.get('study_id')==original['study_id'] and outer.get('study_admitted') is True
           and outer.get('natural_exit') is True and type(outer.get('exit_code')) is int and outer['exit_code']==0
           and outer.get('timer_fired') is False and outer.get('failure') is None and 'failure' in outer
           and outer.get('owned_containers_after')==[] and outer.get('owned_stop_records')==[]
           and outer.get('failure_prefix') is None, 'original actual natural complete study, no hidden cleanup/failure')
    u.need(outer['original_origin']==origin and outer['original_deadline']==whole and outer['closeout_deadline']==normal
           and origin<=outer['worker_start']<=outer['worker_end']<whole,'original worker and closeout clocks unchanged')
    u.need(outer['actual_outer_argv']==command and outer['qualifications']=={
           name:row['pin'] for name,row in original['qualifications'].items()},'original actual caller argv/qualification lineage')
    expected_worker(outer,r,original,env)
    producer_raw=host.read(attempt/'PRODUCER.json',original['resources']['producer_bytes'],outer['producer'],readonly=True)
    journal=host.read(observation/'EVENTS.jsonl',original['observer_limits']['journal_bytes'],outer['journal'],readonly=True)
    producer=env['parent_core'].parse(producer_raw)
    u.need(producer.get('runtime_source')==env['parent'].pin and producer.get('study_id')==original['study_id']
           and producer.get('original_origin')==origin and producer.get('original_deadline')==whole
           and producer.get('private_targets_opened') is False and producer.get('qualified_neural_contribution') is None,
           'original source-bound whole collection, never grade authority')
    closure=env['parent_outer'].event_closure(journal,env['parent_core'].pin(producer_raw),env['parent'].pin,
                                            origin,whole,producer)
    u.need(env['parent_core'].encoded(closure)==env['parent_core'].encoded(outer['event_closure'])
           and closure['all_required_phases_closed'] is True,'actual independently recomputed complete original event closure')
    return {'outer':u.pin(raw),'producer':u.pin(producer_raw),'journal':u.pin(journal),
            'closure':closure,'private_grading_performed':False,'prediction_panels_require_original_protected_admission':True}


def recheck_sources(env,host):
    # Re-read the exact executed source closure under the current inherited
    # deadline, not the bootstrap's expired local startup clock.
    for path,expected in sorted(env['source_rows'].items()):
        host.read(path,2097152,expected)
    return {'members':len(env['source_rows']),'all_exact':True}


def execute(cli,env,host):
    repo=env['repo'];registry=repo/REGISTRY
    # The fixed registry is known without touching even the --review operand.
    first_raw=host.read(registry,131072);doc=u.parse(first_raw);qualify(doc,env,host)
    review_raw=host.read(cli['review'],32768);r=review_document(review_raw,env)
    host.adopt_origin(r['original_origin'])
    u.need(r['registration']['path']==str(registry) and u.only_pin(r['registration'])==u.pin(first_raw),
           'review binds this exact already-qualified registry')
    condition(doc,r['condition']);qualify(doc,env,host)
    first=campaign(r,doc,env,host)
    authority_raw=host.read(r['producer_authority']['path'],2097152,u.only_pin(r['producer_authority']),readonly=True)
    original=env['parent_core'].parse(authority_raw)
    env['parent_gate'].selected(original,env['parent'].pin,r['original_origin'])
    for name in ('program','output','review'):
        u.path(cli[name])
    u.need(cli['program']==r['producer_authority']['path'] and type(cli['other_reserve_bytes']) is int
           and cli['other_reserve_bytes']==r['other_reserve_bytes'],'same exact root programme and unrelated reservation')
    output=Path(cli['output'])
    u.need(original['attempt_root']==str(output/'attempt') and original['observation_root']==str(output/'observation'),
           'fixed full parent output children')
    limits=limits_for(original,r['limits']);host.configure(limits)
    clock_pin=clock_binding(r,original,env,host)
    command=central_command(cli,doc,env)
    fresh=host.read(registry,131072,u.only_pin(r['registration']));u.need(fresh==first_raw,'same registry before launch')
    qualify(u.parse(fresh),env,host);second=campaign(r,doc,env,host)
    admission=env['gate'].finish(first,second,command,repo)
    u.need(host.read(cli['review'],32768,u.pin(review_raw))==review_raw,'same operation review before launch')
    u.need(host.read(r['producer_authority']['path'],2097152,u.only_pin(r['producer_authority']),readonly=True)==authority_raw,
           'same original authority before launch')
    u.need(clock_binding(r,original,env,host)==clock_pin,'same clock authority before launch')
    recheck_sources(env,host)
    nested=observer_command(r,original,env)
    normal=original['whole_deadline']+original['observer_limits']['closeout_seconds']
    cleanup=normal+limits['caller_cleanup_seconds'];end=cleanup+limits['readback_seconds']
    host.tick();host.prepare(cli['output'],original,cli['other_reserve_bytes'],limits)
    phase='prepared';bundle=None;caller_attempted=False;receipts={}
    try:
        receipts['intent']=host.save('INTENT.json',{'schema':'neural060-central-intent-v1','operation':'collect',
             'central_source':env['source'],'parent_source':env['parent'].pin,'review':u.pin(review_raw),
             'authority':u.only_pin(r['producer_authority']),'root_clock':clock_pin,'original_origin':host.origin,
             'entry_start':host.entry_start,'production_deadline':original['whole_deadline'],
             'caller_normal_end':normal,'caller_cleanup_end':cleanup,'readback_end':end,
             'limits':limits,'caller_not_yet_attempted':True,'protected_grading_authorized':False},65536)
        receipts['campaign']=host.save('CAMPAIGN.json',admission,16384)
        receipts['invocation']=host.save('INVOCATION.json',{'central_argv':command,'observer_argv':nested,'cwd':str(repo)},65536)
        host.arm(normal);phase='caller_entered';caller_attempted=True
        bundle=host.launch(nested,normal,cleanup,repo)
        host.arm(end);phase='caller_returned'
        receipts['stdout']=host.save('caller.stdout',bundle['stdout'],CALLER_CAP)
        receipts['stderr']=host.save('caller.stderr',bundle['stderr'],CALLER_CAP)
        receipts['caller']=host.save('CALLER.json',bundle['record'],65536)
        joined=readback(bundle,nested,original,r,limits,env,host);phase='readback_admitted'
        source_closure=recheck_sources(env,host)
        host.save('RESULT.json',{'schema':'neural060-central-result-v1','status':'complete_collection_unqualified',
            'central_source':env['source'],'parent_source':env['parent'].pin,'review':u.pin(review_raw),
            'authority':u.only_pin(r['producer_authority']),'receipts':receipts,'joined':joined,
            'source_closure':source_closure,
            'source_only_build_is_distinct_from_actual_collection':True,'collection_performed':True,
            'private_grading_performed':False,'runtime_qualified':False,'scientific_qualified':False,
            'qualified_neural_contribution':None,'root_final_durability_admission_required':True,
            'automatic_retry':False,'costs':host.record(),'limits':limits},65536)
        host.tick();return 0
    except BaseException as error:
        if hasattr(error,'bundle'):bundle=error.bundle
        try:
            host.arm(end)
            if bundle is not None:
                for name,key,receipt_key in (('caller.stdout','stdout','stdout'),('caller.stderr','stderr','stderr'),('CALLER.json','record','caller')):
                    if receipt_key not in receipts and not (host.root/name).exists():
                        receipts[receipt_key]=host.save(name,bundle[key],65536)
            host.save('FAILURE.json',{'schema':'neural060-central-failure-v1','last_phase':phase,
                'error_type':type(error).__name__,'caller_attempted':caller_attempted,
                'caller_record':None if bundle is None else bundle['record'],'receipts':receipts,
                'nested_worker_native_state_requires_inspection':caller_attempted,'automatic_retry':False,
                'private_grading_performed':False,'scientific_qualified':False,'qualified_neural_contribution':None,
                'costs':host.record()},65536)
        except BaseException:pass
        raise
