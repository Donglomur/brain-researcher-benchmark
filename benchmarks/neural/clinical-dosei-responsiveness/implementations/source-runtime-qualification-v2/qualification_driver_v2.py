"""Finite generated qualification orchestrator; admission belongs to the host.

No source module here launches Docker on import. The injected context must be
authenticated by the separately reviewed entry/guard before this function.
"""
import hashlib
import os
from pathlib import Path
import re
import time

COMMAND_CAP=80
PER_PHASE_COMMAND_CAP=40
STREAM_GRANT_CAP=12*1024*1024
OBSERVED_STREAM_CAP=3*1024*1024
CLEANUP_OBSERVED_RESERVE=256*1024
STAGING_CAP=65536


class QualificationFailure(RuntimeError):
    pass


def require(ok,reason):
    if not ok:raise QualificationFailure(reason)


class StagingMeter:
    def __init__(self):self.charged=self.confirmed=0;self.events=[]
    def write(self,delegate,path,raw):
        require(type(raw) is bytes and self.charged+len(raw)<=STAGING_CAP,'generated staging capacity')
        self.charged+=len(raw)
        item={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'confirmed':False}
        self.events.append(item)
        delegate(path,raw)
        item['confirmed']=True;self.confirmed+=len(raw)
    def summary(self):
        return {'cap_bytes':STAGING_CAP,'charged_cumulative_write_bytes':self.charged,
                'confirmed_cumulative_write_bytes':self.confirmed,
                'unknown_write_grant_bytes':self.charged-self.confirmed,'writes':list(self.events),
                'deleted_files_refunded':False}


class CommandMeter:
    def __init__(self,ctx,store):
        self.ctx,self.store=ctx,store
        self.policy=ctx.modules['policy'];self.raw=ctx.modules['raw']
        self.commands=[];self.names=set();self.specs={};self.identities=set();self.all_created=[]
        self.granted=self.observed=self.ordinary_observed=self.cleanup_observed=0
        self.ordinary_phase_grant=self.cleanup_phase_grant=0
        self.ordinary_count=self.cleanup_count=0
        self.cancelled=False;self.validation_errors=[];self.active_case=None

    def _scope(self,command):
        p=self.ctx.protocol
        require(type(command) is list and len(command)>=7 and
                command[0]==p['docker_executable'] and command[1]=='--config' and
                type(command[2]) is str and Path(command[2]).parent.parent==Path(self.ctx.output_root)/'staging' and
                command[3:5]==['--host','unix://'+p['docker_socket']], 'fixed daemon command scope')
        args=command[5:]
        cleanup=(len(args)==3 and args[:2]==['container','inspect'] and args[2] in self.identities|self.names or
                 len(args)==4 and args[:3]==['container','rm','--force'] and args[3] in self.identities or
                 len(args)==7 and args[:6]==['container','ls','--all','--no-trunc','--quiet','--filter'] and
                 args[6].startswith('id=') and args[6][3:] in self.identities)
        require(cleanup or args[:2]==['image','inspect'] or args[0]=='create' or
                (len(args)==4 and args[:3]==['container','start','--attach'] and args[3] in self.identities),
                'unadmitted daemon operation')
        return args,cleanup

    def _validate(self,receipt,command,kwargs,output):
        raw=self.raw;store=self.store
        require(type(receipt) is dict and receipt.get('schema')=='dosei_raw_command_receipt_v1',
                'original raw receipt required')
        original=store.lookup(receipt.get('retained_receipt'),'command_receipt')[1]
        require(original is not None,'bounded raw receipt body')
        value=self.policy.decode(original)
        require(value=={k:v for k,v in receipt.items() if k!='retained_receipt'},'raw receipt differs from original')
        intentraw=store.lookup(receipt.get('intent'),'command_intent')[1]
        intent=self.policy.decode(intentraw)
        wanted={'schema':'dosei_raw_command_intent_v1','command':list(self.ctx.command_prefix)+command,
                'cwd':kwargs['cwd'],'timeout_seconds':kwargs['timeout_seconds'],
                'output_limit':kwargs['output_limit'],'stderr':'merged_raw_stdout','stdin':'closed_without_input'}
        require(intent==wanted,'original command intent binding differs')
        _,_,prefix=store.lookup(receipt.get('retained_original'),'command_output_prefix')
        observed=receipt.get('observed_prefix')
        require(observed==receipt['retained_original'] and type(observed['bytes']) is int and
                0<=observed['bytes']<=kwargs['output_limit']+1,'bounded original output prefix')
        require(type(receipt.get('charged_output_bytes')) is int and
                type(receipt.get('success')) is bool and type(receipt.get('eof_observed')) is bool,
                'strict receipt counters')
        closure=receipt.get('closure')
        require(type(closure) is dict and closure.get('complete') is True and
                closure.get('post_wait_group_absence_observed') is True and
                type(closure.get('leader_returncode')) is int and
                closure['leader_returncode']==receipt.get('returncode'),'owned CLI cleanup unconfirmed')
        if receipt['success']:
            require(receipt.get('failure_category') is None and receipt['eof_observed'] is True and
                    type(receipt.get('unread_output_bytes')) is int and receipt['unread_output_bytes']==0 and
                    receipt['charged_output_bytes']==observed['bytes'] and not receipt.get('errors') and
                    type(output) is bytes and raw.binding(output)==observed,'successful output chain differs')
        else:
            require(receipt['charged_output_bytes']==kwargs['output_limit']+1 and
                    receipt.get('failure_category') in ('command_output_capacity','command_wall_timeout') and
                    receipt['eof_observed'] is False and receipt.get('unread_output_bytes') is None and
                    not receipt.get('errors'),'unadmitted or incomplete expected command failure')
        return observed['bytes'],prefix

    def __call__(self,command,**kwargs):
        args,cleanup=self._scope(command)
        if cleanup:
            self.ctx.checkpoint(cleanup=True)
        else:
            require(not self.cancelled,'ordinary commands cancelled')
            try:self.ctx.checkpoint()
            except BaseException:
                self.cancelled=True;raise
        require(len(self.commands)<COMMAND_CAP and
                (self.cleanup_count if cleanup else self.ordinary_count)<PER_PHASE_COMMAND_CAP,
                'finite command allowance exhausted')
        requested_cap=kwargs.get('output_limit')
        require(type(requested_cap) is int and requested_cap in (131072,2097152),
                'frozen backend requested output cap')
        remaining=(CLEANUP_OBSERVED_RESERVE-self.cleanup_phase_grant if cleanup else
                   OBSERVED_STREAM_CAP-CLEANUP_OBSERVED_RESERVE-self.ordinary_phase_grant)
        case_cap=(524288 if self.active_case=='runtime' and args[:3]==['container','start','--attach']
                  else requested_cap)
        cap=min(case_cap,remaining-1)
        if self.active_case=='runtime' and args[:3]==['container','start','--attach']:
            require(cap==524288,'complete fresh runtime capture grant required')
        require(cap>0 and
                self.granted+cap+1<=STREAM_GRANT_CAP,'finite stream grant capacity')
        kwargs=dict(kwargs,output_limit=cap)
        requested_timeout=kwargs.get('timeout_seconds')
        limit=self.ctx.protocol['limits']['cleanup_deadline_seconds' if cleanup else 'operation_deadline_seconds']
        remaining_seconds=limit-(time.monotonic()-self.ctx.started)-2
        require(type(requested_timeout) in (int,float) and 0<requested_timeout<=60 and
                remaining_seconds>0,'command cleanup-margin deadline')
        kwargs['timeout_seconds']=min(requested_timeout,remaining_seconds)
        require(kwargs.get('process_api') is self.ctx.modules['owned'] and
                kwargs.get('recorder') is self.store,'fixed process and custody adapters')
        if args[0]=='create':
            name=args[args.index('--name')+1]
            require(name not in self.names and len(self.names)<6,'six distinct create attempts maximum')
            labels=[args[i+1] for i,v in enumerate(args) if v=='--label']
            mounts=[args[i+1] for i,v in enumerate(args) if v=='--mount']
            require(len(labels)==2 and len(mounts)==2,'fixed generated create scope')
            context=labels[0].split('=',1)[1];ordinal=int(labels[1].split('=',1)[1])
            paths=[item.split(',')[1][4:] for item in mounts]
            spec=self.policy.specification(self.policy.profile(self.ctx.profile_bytes),context,ordinal,*paths)
            require(name==spec['name'] and args==self.policy.create_arguments(
                self.policy.profile(self.ctx.profile_bytes),spec),'exact generated create arguments')
            self.specs[name]=spec
            self.names.add(name)
        entry={'ordinal':len(self.commands),'cleanup':cleanup,'operation':args[:3],
               'grant_bytes':cap+1,'requested_output_limit':requested_cap,'effective_output_limit':cap,
               'requested_timeout_seconds':requested_timeout,'effective_timeout_seconds':kwargs['timeout_seconds'],
               'observed_bytes':None,'verified':False}
        self.commands.append(entry);self.granted+=cap+1
        if cleanup:self.cleanup_count+=1;self.cleanup_phase_grant+=cap+1
        else:self.ordinary_count+=1;self.ordinary_phase_grant+=cap+1
        old=self.store.cleanup;self.store.cleanup=cleanup
        try:
            try:result=self.ctx.command_runner(command,**kwargs)
            except self.raw.CommandFailure as error:
                receipt=error.receipt;result=None
                entry['exception_category']=error.category
                self._finish(entry,receipt,command,kwargs,None,cleanup)
                raise
            receipt=result['receipt']
            self._finish(entry,receipt,command,kwargs,result['output'],cleanup)
            require(type(result.get('returncode')) is int and result['returncode']==receipt['returncode'],
                    'returned exit disagrees with original receipt')
            if args[0]=='create' and result['returncode']==0:
                identity=result['output'].strip().decode('ascii')
                require(re.fullmatch('[0-9a-f]{64}',identity) and identity not in self.all_created,
                        'unique full created container ID required')
                self.identities.add(identity);self.all_created.append(identity)
            elif args[:2]==['container','inspect'] and args[2] in self.names and result['returncode']==0:
                value=self.policy.decode(result['output']);identity=value[0]['Id']
                self.policy.admit_ownership(self.specs[args[2]],value,required_id=identity)
                if identity not in self.identities:
                    require(identity not in self.all_created,'recovered container ID reused')
                    self.identities.add(identity);self.all_created.append(identity)
            return result
        except BaseException as error:
            if not entry['verified']:
                entry['error_type']=type(error).__name__;self.validation_errors.append(entry['ordinal'])
                self.cancelled=True
            raise
        finally:self.store.cleanup=old

    def _finish(self,entry,receipt,command,kwargs,output,cleanup):
        count,prefix=self._validate(receipt,command,kwargs,output)
        require(self.observed+count<=OBSERVED_STREAM_CAP and
                (self.cleanup_observed+count<=CLEANUP_OBSERVED_RESERVE if cleanup else
                 self.ordinary_observed+count<=OBSERVED_STREAM_CAP-CLEANUP_OBSERVED_RESERVE),
                'observed stream allowance exceeded')
        self.observed+=count
        if cleanup:self.cleanup_observed+=count
        else:self.ordinary_observed+=count
        if receipt['success']:
            unused=entry['grant_bytes']-count;self.granted-=unused
            if cleanup:self.cleanup_phase_grant-=unused
            else:self.ordinary_phase_grant-=unused
            entry['grant_bytes']=count
        entry.update(observed_bytes=count,verified=True,receipt=receipt['retained_receipt'],
                     success=receipt['success'],failure_category=receipt['failure_category'],
                     prefix_initial=prefix,unread_output_bytes=receipt['unread_output_bytes'])

    def summary(self):
        return {'command_attempts':len(self.commands),'ordinary_attempts':self.ordinary_count,
                'cleanup_attempts':self.cleanup_count,'command_cap':COMMAND_CAP,
                'logical_stream_grant_cap_bytes':STREAM_GRANT_CAP,
                'charged_logical_stream_grant_bytes':self.granted,
                'known_observed_prefix_bytes':self.observed,
                'ordinary_phase_charged_bytes':self.ordinary_phase_grant,
                'cleanup_phase_charged_bytes':self.cleanup_phase_grant,
                'phase_grants_retained_on_failed_or_unknown_commands':True,
                'unknown_or_unverified_commands':list(self.validation_errors),
                'all_created_container_ids':list(self.all_created),
                'commands':[{k:v for k,v in item.items() if k!='prefix_initial'} for item in self.commands],
                'physical_kernel_daemon_io_measured':False}


def run_qualification(ctx):
    """Return bounded final accounting; caller must require status==succeeded."""
    ctx.checkpoint()
    modules=ctx.modules
    backend,policy,cases,storage=(modules[k] for k in ('backend','policy','cases','store'))
    p=ctx.protocol
    require(type(ctx.protocol_sha256) is str and re.fullmatch('[0-9a-f]{64}',ctx.protocol_sha256),
            'authenticated external protocol digest required')
    require(type(p.get('context_ids')) is list and len(p['context_ids'])==3 and
            len(set(p['context_ids']))==3 and all(type(v) is str and re.fullmatch('[0-9a-f]{64}',v)
                for v in p['context_ids']),'three exact context IDs required')
    require(type(p.get('limits')) is dict and type(p['limits'].get('cleanup_deadline_seconds')) is int and
            0<p['limits']['cleanup_deadline_seconds']<=590,'bounded cleanup deadline required')
    profile=policy.profile(ctx.profile_bytes)
    root=Path(ctx.output_root);storage.directory_signature(root)
    report_writer=storage.ReportWriter(root)
    class RuntimeOriginalStore(storage.EvidenceStore):
        """Keep only the first-call originals already accepted by the recorder."""
        def __init__(self,path):
            super().__init__(path);self.runtime_originals={};self.runtime_bytes=0
        def __call__(self,kind,raw):
            ordinal=len(self.entries)
            if ordinal<27:
                require(len(raw)<=524288 and self.runtime_bytes+len(raw)<=1048576,
                        'bounded first-call original capture')
            bound=super().__call__(kind,raw)
            if ordinal<27:
                entry=self.entries[ordinal]
                require(entry['status']=='confirmed','confirmed first-call original required')
                self.runtime_originals['evidence/'+entry['path']]=raw
                self.runtime_bytes+=len(raw)
            return bound
    store=RuntimeOriginalStore(root/'evidence')
    stage_root=root/'staging';os.mkdir(stage_root,0o700)
    staging=StagingMeter();command=CommandMeter(ctx,store)
    class BoundedBackend(backend.DockerCodeBackend):
        def _write(self,path,raw):return staging.write(super()._write,path,raw)
    reports=[];closures=[];cleanup_failures=[];failure=None;interruption=None
    canary_path=str(stage_root/'GENERATED_HOST_CANARY.txt')
    try:
        generated=cases.programs(canary_path,p['docker_socket'],probe_source=ctx.probe_source)
        require({k:storage.binding(v.encode('utf-8')) for k,v in generated.items()}==p['generated_programs'],
                'all six fixed program bodies differ from protocol')
        # The canary deliberately remains outside both admitted file mounts.
        staging.write(lambda path,raw:backend.DockerCodeBackend._write(None,path,raw),canary_path,cases.CANARY)
        expected_staging=len(cases.CANARY)+3*len(cases.OBSERVATION)+sum(len(v.encode('utf-8')) for v in generated.values())
        require(expected_staging<=STAGING_CAP,'fixed source extent admission')
        for context_index,names in enumerate((cases.NAMES[:4],('flood',),('deadline',))):
            ctx.checkpoint();instance=None;context_start=len(command.commands);primary=None
            checked_call_bindings=[];runtime_provisional=None;runtime_report=None
            try:
                instance=BoundedBackend(profile_bytes=ctx.profile_bytes,
                    public_binding={'case_id':cases.CASE_ID,'observation_sha256':cases.OBSERVATION_SHA256},
                    observation_bytes=cases.OBSERVATION,
                    viewer=lambda _:(_ for _ in ()).throw(QualificationFailure('viewer outside qualification')),
                    context_id=p['context_ids'][context_index],staging_parent=str(stage_root),
                    docker_executable=p['docker_executable'],docker_socket=p['docker_socket'],
                    recorder=store,policy_api=policy,command_api=modules['raw'],process_api=modules['owned'],
                    call_wall_seconds=2 if context_index==2 else 30,max_calls=len(names),command_runner=command)
                for name in names:
                    before=len(command.commands);evidence_before=len(store.entries);command.active_case=name
                    if context_index==0:
                        result=instance.run_tool('python',generated[name])
                        call_entries=[v for v in store.entries[evidence_before:] if v['kind']=='code_call']
                        require(len(call_entries)==1 and call_entries[0]['status']=='confirmed',
                                'one original call per completed control')
                        checked_call_bindings.append(dict(call_entries[0]['binding']))
                        if name=='runtime':
                            fresh=modules['fresh_state']
                            authority=fresh.Authority(
                                protocol_sha256=ctx.protocol_sha256,context_id=p['context_ids'][0],
                                worker_pid=os.getpid(),output_directory=str(root),
                                python_executable=p['python_executable'],cli_shim_path=p['cli_shim']['path'],
                                docker_executable=p['docker_executable'],docker_socket=p['docker_socket'],
                                canary_path=canary_path,program_sha256=p['generated_programs']['runtime']['sha256'],
                                original_bindings=tuple(('evidence/'+v['path'],v['binding']['bytes'],v['binding']['sha256'])
                                    for v in store.entries[:27]),
                                module_source_sha256=tuple((alias,p['modules'][key]['sha256']) for alias,key in
                                    (('docker_policy','policy'),('network_policy','network_policy'),
                                     ('owned','owned'),('probe','probe'),('cases','cases'))))
                            runtime_provisional=fresh.derive_runtime_state(
                                store.runtime_originals,profile_bytes=ctx.profile_bytes,probe_source=ctx.probe_source,
                                authority=authority,modules={'docker_policy':policy,
                                    'network_policy':modules['network_policy'],'owned':modules['owned'],
                                    'probe':modules['probe'],'cases':cases})
                            runtime_report={'case':name,'status':'context_closure_pending',
                                            'fresh_state':runtime_provisional}
                            reports.append(runtime_report)
                            store.runtime_originals.clear()
                        else:
                            value=cases.validate_normal(name,result,policy=policy,profile=profile,
                                                        canary_path=canary_path,socket_path=p['docker_socket'])
                            reports.append({'case':name,'status':'confirmed','output':value})
                    else:
                        expected='command_output_capacity' if name=='flood' else 'command_wall_timeout'
                        try:instance.run_tool('python',generated[name])
                        except backend.CodeBackendFailure as error:require(error.category==expected,'unexpected refusal category')
                        else:raise QualificationFailure('expected bounded refusal absent')
                        failed=[c for c in command.commands[before:] if c.get('failure_category')==expected]
                        require(len(failed)==1 and failed[0]['operation']==['container','start','--attach'],
                                'expected attach refusal evidence required')
                        if name=='flood':require(failed[0]['effective_output_limit']==2097152,
                            'full frozen backend output limit required for flood qualification')
                        observed_marker=failed[0]['prefix_initial'].startswith(cases.marker(name))
                        reports.append({'case':name,'status':'confirmed' if observed_marker else 'startup_phase_unresolved',
                            'failure_category':expected,'candidate_marker_observed':observed_marker,
                            'requested_output_limit':failed[0]['requested_output_limit'],
                            'effective_output_limit':failed[0]['effective_output_limit'],
                            'original_command_receipt':failed[0]['receipt'],
                            'unknown_unread_output_bytes':failed[0]['unread_output_bytes']})
                        prior=len(command.commands)
                        try:instance.run_tool('python',generated[name])
                        except backend.CodeBackendFailure as error:require(error.category=='code_context_unavailable','failed context did not poison')
                        else:raise QualificationFailure('failed context reusable')
                        require(len(command.commands)==prior,'poison check started another command')
                        require(observed_marker,'deadline/flood candidate phase not observed; no retry')
            except BaseException as error:
                primary=error
                raise
            finally:
                if instance is not None:
                    store.cleanup=True
                    try:
                        closed=instance.close()
                        close_raw=store.lookup(closed,'code_close')[1]
                        value=policy.decode(close_raw)
                        require(value.get('complete') is True and not value.get('errors') and
                                not value.get('owned_container_ids_unresolved') and
                                not value.get('container_names_with_unresolved_create'), 'owned context closure incomplete')
                        require(len(value.get('calls',[]))==len(names),'all fixed call receipts required')
                        for bound in value['calls']:
                            call=policy.decode(store.lookup(bound,'code_call')[1])
                            require(type(call.get('closure')) is dict and set(call['closure'])=={'remove','absence'},
                                    'individual container closure missing')
                            for receipt_binding in call['closure'].values():store.lookup(receipt_binding,'command_receipt')
                        if context_index==0 and runtime_provisional is not None:
                            final_runtime=modules['fresh_state'].bind_context_close(
                                runtime_provisional,close_raw,expected_call_bindings=checked_call_bindings)
                            runtime_report['fresh_state']=final_runtime
                            runtime_report['status']='context_closed_receipt_pending'
                        closures.append({'context_index':context_index,'original':closed,
                                         'commands':len(command.commands)-context_start,'complete':True})
                    except BaseException as cleanup:
                        cleanup_failures.append({'context_index':context_index,'type':type(cleanup).__name__,
                            'category':getattr(cleanup,'category',str(cleanup))[:200]})
                        if primary is not None and (not isinstance(primary,Exception) or isinstance(cleanup,Exception)):
                            raise primary
                        raise
                    finally:store.cleanup=False
            if context_index==0:
                require(runtime_report is not None and runtime_report['status']=='context_closed_receipt_pending',
                        'fresh context receipt unavailable')
                final_runtime=runtime_report['fresh_state']
                receipt_binding=store('fresh_runtime_state',storage.canonical(final_runtime))
                runtime_report.pop('fresh_state')
                runtime_report.update(fresh_state_receipt=receipt_binding,
                    runtime_control_confirmed=final_runtime['runtime_control_confirmed'],
                    necessary_condition_matches=final_runtime['necessary_condition_matches'],
                    network_qualified=False,
                    status=('confirmed' if final_runtime['runtime_control_confirmed']
                            else 'necessary_condition_failed'))
                require(runtime_report['status']=='confirmed',
                        'fresh necessary network state condition not satisfied')
        require(len(reports)==6 and all(v['status']=='confirmed' for v in reports) and
                len(command.all_created)==6 and len(set(command.all_created))==6,
                'complete six-container scope required')
        require(not command.validation_errors and staging.confirmed==expected_staging,'complete known source accounting')
        require(sorted(path.name for path in stage_root.iterdir())==['GENERATED_HOST_CANARY.txt'],
                'backend staging cleanup incomplete')
        ctx.checkpoint()
    except BaseException as error:
        failure={'type':type(error).__name__,'category':getattr(error,'category',str(error))[:200]}
        if not isinstance(error,Exception):interruption=error
    report={'schema':'dosei_generated_docker_qualification_v2',
            'status':'succeeded' if failure is None else 'failed','failure':failure,
            'generated_only':True,'cases':reports,'context_closures':closures,'cleanup_failures':cleanup_failures,
            'profile_sha256':policy.PROFILE_SHA256,'observation_sha256':cases.OBSERVATION_SHA256,
            'protocol_sha256':ctx.protocol_sha256,
            'evidence':store.summary(),'staging':staging.summary(),'commands':command.summary(),
            'report_write_scope':'Counters above precede separate final report write; returned accounting includes it',
            'qualification_limits':{'no_authentic_neural_data':True,'no_model_api':True,'no_scoring':True,
                'no_arbitrary_code_cpu_policy_claim':True,'inspected_network_none_and_no_host_socket_mounts':True,
                'fresh_runtime_state_is_one_necessary_condition':True,'no_atomic_network_snapshot':True,
                'no_firewall_or_routing_rule_claim':True,'prior_qualification_failures_preserved':True,
                'own_namespace_socket_creation_not_prohibited':True,'no_general_sandbox_security_proof':True,
                'no_benchmark_readiness_increment':True}}
    try:report_binding=report_writer.write(report)
    except BaseException as error:
        failure=failure or {'type':type(error).__name__,'category':'final_report_custody_failure'}
        report_binding=None
        if not isinstance(error,Exception) and interruption is None:interruption=error
    summary={'status':'succeeded' if failure is None else 'failed','failure':failure,
             'report':report_binding,'evidence_writes':{k:v for k,v in store.summary().items() if k!='files'},
             'staging_writes':staging.summary(),'report_writes':report_writer.summary(),
             'logical_stream_grant_bytes':command.granted,'known_observed_prefix_bytes':command.observed,
             'unknown_or_unverified_commands':command.validation_errors,
             'elapsed_seconds':time.monotonic()-ctx.started}
    if interruption is not None:
        interruption.qualification_summary=summary
        raise interruption
    return summary
