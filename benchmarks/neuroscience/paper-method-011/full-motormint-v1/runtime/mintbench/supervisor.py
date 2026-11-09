"""Concrete outer custody from preparation through child exit and owned cleanup.

No process/kernel/native work on import. Authentic invocation is independently
selected. Inner stage/attempt readings are attribution only; this parent reading
is the inclusive authority and does not add those nested readings again.
"""
import hashlib,os,re,selectors,signal,subprocess,time
from pathlib import Path
from .validation import exact,need,digest,bound_bytes,decode,integer
from .observer import CgroupObserver
from .custody import SharedBudget,DiagnosticCapture
from .schedule import validate_block


def observe_process(argv,*,origin,end,cleanup_end,capture,attach=None,now=time.monotonic,popen=subprocess.Popen):
    """Private argv, bounded original streams, natural exit or explicit kill."""
    state={'started':False,'natural_exit':False,'exit_code':None,'forced_termination':False,
           'group_absent':False,'streams_closed':False,'original_origin':origin,'normal_end':end,'cleanup_end':cleanup_end}
    process=None;selector=selectors.DefaultSelector();count=0
    try:
        need(now()<end,'original deadline before launch')
        process=popen(argv,stdin=subprocess.PIPE if attach else subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,bufsize=0,env={'PATH':'/usr/bin:/bin','HOME':'/var/empty','PYTHONDONTWRITEBYTECODE':'1'})
        state.update(started=True,pid=process.pid)
        if attach:
            attach(process.pid);process.stdin.write(b'START\n');process.stdin.close()
        for stream,name in ((process.stdout,'out'),(process.stderr,'err')):
            os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
        while selector.get_map():
            need(now()<end,'inclusive whole-campaign deadline')
            for key,_ in selector.select(min(.05,max(0,end-now()))):
                block=os.read(key.fileobj.fileno(),65536)
                if not block:capture.eof(key.data);selector.unregister(key.fileobj)
                else:
                    capture.feed(key.data,block);count+=len(block);need(count<=4194304,'outer observed-stream hard cap')
        state['exit_code']=process.wait(timeout=max(.001,end-now()));state['natural_exit']=True
    except BaseException as error:state['reason']=type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            from .transport import absent_group
            if process.poll() is None or not absent_group(process.pid):
                state['forced_termination']=True
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                try:process.wait(timeout=max(.001,cleanup_end-now()))
                except subprocess.TimeoutExpired:pass
            state.update(process_reaped=process.poll() is not None,group_absent=absent_group(process.pid))
            for stream in (process.stdin,process.stdout,process.stderr):
                if stream is not None and not stream.closed:stream.close()
        selector.close();state['streams_closed']=True;state['diagnostics']=capture.close()
    return state


def launch(spec,selected_spec_sha256,*,selected_clock=None):
    origin=time.monotonic() if selected_clock is None else selected_clock['origin']  # Never reset after source/config/input preparation.
    exact(spec,('request_root','request','output_root','output_bytes','final_reserve_bytes','python','child_source',
                'child_source_sha256','cgroup_path','child_cgroup_path','gpu_devices','normal_seconds','cleanup_seconds','docker','ownership_token'),'outer specification')
    need(digest(spec)==selected_spec_sha256,'independent outer launch selection')
    integer(spec['normal_seconds'],1);integer(spec['cleanup_seconds'],1,60)
    end=origin+spec['normal_seconds'];cleanup_end=end+spec['cleanup_seconds']
    if selected_clock is not None:
        exact(selected_clock,('origin','end','cleanup_end'),'central original clock')
        need(selected_clock=={'origin':origin,'end':end,'cleanup_end':cleanup_end}
             and origin<=time.monotonic()<end,'adopt original central clock, never reset')
    parent=Path(spec['cgroup_path']);childgroup=Path(spec['child_cgroup_path'])
    need(childgroup.is_absolute() and '..' not in childgroup.parts and parent in childgroup.parents and childgroup!=parent,'strict private descendant cgroup, never kill outer/host group')
    need(re.fullmatch('[a-f0-9]{32}',spec['ownership_token']),'root-selected unique ownership label')
    output=Path(spec['output_root']);need(output.is_absolute() and output.is_dir() and not any(output.iterdir()),'fresh private outer output')
    budget=SharedBudget(output,spec['output_bytes'],spec['final_reserve_bytes'],create=True)
    observer=CgroupObserver(spec['cgroup_path'],spec['gpu_devices']);begun=False;owned_ready=False;record={'original_origin':origin,'end':end,'cleanup_end':cleanup_end,'stages':[],'selected_spec_sha256':selected_spec_sha256}
    try:
        observer.begin('inclusive_campaign',origin,end);begun=True
        preparation=time.monotonic()
        request=decode(bound_bytes(spec['request_root'],spec['request'],33554432))
        validate_block(request['campaigns'])
        need(len(request['campaigns'])==len(request['campaign_sha256']),'complete selected paired block hashes')
        limits=request['admission_value']['limits'];need(len(request['campaigns'])*3*len(request['plan']['cases'])<=limits['attempts'],'inclusive balanced-block attempt ceiling');role_seconds=request['admission_value']['context_pair']['A']['resources']['role_seconds']
        need(limits['normal_seconds']==spec['normal_seconds'] and len(request['campaigns'])*3*(role_seconds+limits['cleanup_seconds'])<spec['normal_seconds'],'inclusive selected clock includes balanced roles and nonzero preparation/scoring allowance')
        events=dict(line.split() for line in (childgroup/'cgroup.events').read_text().splitlines())
        need(events['populated']=='0' and not (childgroup/'cgroup.procs').read_text().strip(),'empty owned child subtree before launch')
        owned_ready=True
        source=Path(spec['child_source']);need(source.is_absolute() and not source.is_symlink() and hashlib.sha256(source.read_bytes()).hexdigest()==spec['child_source_sha256'],'selected concrete child source')
        for campaign in request['campaigns']:
            need(campaign['cgroup_path']==str(childgroup) and campaign['ownership_token']==spec['ownership_token'],'all descendants under exact owned custody')
            path=Path(campaign['output_root']);need(path.parent==output and not path.exists(),'distinct fresh paired output directories')
        record['stages'].append({'stage':'preparation','start':preparation,'end':time.monotonic()})
        capture=DiagnosticCapture(output,'campaign-child',65536,budget)
        def attach(pid):
            (childgroup/'cgroup.procs').write_text(str(pid))
            need(str(pid) in (childgroup/'cgroup.procs').read_text().split(),'child attached before START handshake')
        argv=[spec['python'],'-I','-B',str(source),str(Path(spec['request_root'])/spec['request']['path']),spec['request']['sha256'],str(origin),str(end),str(cleanup_end),str(output),str(spec['output_bytes']),str(spec['final_reserve_bytes'])]
        record['child']=observe_process(argv,origin=origin,end=end,cleanup_end=cleanup_end,capture=capture,attach=attach)
        record['stages'].append({'stage':'child_preparation_prediction_scoring_report','start':preparation,'end':time.monotonic()})
    except BaseException as error:record['failure']=type(error).__name__+': '+str(error)
    finally:
        cleanup_start=time.monotonic();cleanup=[]
        if not owned_ready:
            record['cleanup_skipped']='ownership not acquired; no pre-existing process or container touched'
        else:
            try:
                # This scope is a fresh private descendant, not an unrelated job.
                def populated():return dict(line.split() for line in (childgroup/'cgroup.events').read_text().splitlines())['populated']=='1'
                if populated():(childgroup/'cgroup.kill').write_text('1')
                while populated() and time.monotonic()<cleanup_end:time.sleep(.01)
                record['child_cgroup_empty']=not populated()
                def cli(args,label):
                    capture=DiagnosticCapture(output,label,65536,budget)
                    result=observe_process([spec['docker'],*args],origin=origin,end=cleanup_end,cleanup_end=cleanup_end,capture=capture)
                    cleanup.append(result)
                    need(result['natural_exit'] and result['exit_code']==0 and result['group_absent'],'owned Docker cleanup observation')
                    stream=result['diagnostics']['streams']['out'];need(stream['complete_original_stream'],'complete cleanup inventory, no truncated selection')
                    return (output/stream['path']).read_text().split()
                ids=cli(['ps','-aq','--filter','label=motormint.owner='+spec['ownership_token']],'cleanup-list')
                need(all(re.fullmatch('[a-f0-9]{12,64}',x) for x in ids),'only observed owned container IDs')
                if ids:cli(['rm','--force',*ids],'cleanup-remove')
                record['owned_containers_absent']=not cli(['ps','-aq','--filter','label=motormint.owner='+spec['ownership_token']],'cleanup-absence')
            except BaseException as error:record['cleanup_failure']=type(error).__name__+': '+str(error)
        record['cleanup_commands']=cleanup;record['stages'].append({'stage':'cleanup','start':cleanup_start,'end':time.monotonic()})
        try:
            need(begun,'inclusive sensor unavailable');record['inclusive_cost']=observer.finish('inclusive_campaign')
        except Exception as error:record['inclusive_cost']=None;record['cost_failure']=str(error)
        record['cost_boundary']='Outer entry after trusted launch-spec call, source/request preparation, child/controller/native descendants, assessments, report writes and owned cleanup. This terminal observer-receipt serialization is custody metadata, not an inner workload stage.'
        record['nested_attribution_must_not_be_added']=True
        record['success']=record.get('child',{}).get('natural_exit') is True and record['child']['exit_code']==0 and record.get('child_cgroup_empty') is True and record.get('owned_containers_absent') is True and record['inclusive_cost'] is not None and 'failure' not in record
        record['scientifically_qualified']=False
        budget.persist(output,'outer-observation.json',record,final=True)
    return record
