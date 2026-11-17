"""External original controller caller. No child-supplied success alone suffices."""
import argparse,os,selectors,subprocess,time,json,hashlib
from pathlib import Path
from n056.core import need,read_json,capture,save,descriptor,digest,absolute,byte_pin,canonical
from n056.terminal import resource_verdict,TerminalCustody

def main(a):
    started=time.monotonic_ns();source=Path(__file__).resolve().parent
    authority_pin={'bytes':a.authority_bytes,'sha256':a.authority_sha256}
    authority=read_json(a.authority,4*1024**2,authority_pin)
    profile=read_json(a.profile,4*1024**2,authority['profile']);p=profile['outer']
    manifest=read_json(source/'RUNTIME_MANIFEST.json')
    need(authority['source_id']==digest(manifest) and authority['build_only'] is False,'exact externally selected source')
    for row in manifest['files']:capture(source/row['path'],row['bytes'],row)
    capture(p['python']['path'],p['python']['bytes'],p['python'])
    run_end=started+p['wall_ns'];cleanup_end=run_end+p['cleanup_ns']
    root=absolute(str(Path(a.capture).absolute()));root.mkdir(mode=0o700)
    terminal=TerminalCustody(root,{name:p['terminal_file_bytes'] for name in ('ORIGINAL_COMPLETION.json','TERMINAL_JOIN.json')},None,cleanup_end)
    destination=absolute(str(Path(a.destination).absolute()))
    need(not destination.exists() and not root.is_relative_to(source) and not destination.is_relative_to(source),'fresh separate operator destinations')
    cg=absolute(p['cgroup']);need(not cg.exists() and cg.parent.is_dir() and cg.name.startswith('n056-'),'fresh qualified owned hierarchy')
    need(profile['runtime']['cgroup_parent']==str(cg/'jobs'),'all descendant processes in selected hierarchy')
    cg.mkdir();inode=cg.stat().st_ino
    (cg/'cgroup.subtree_control').write_text('+cpu +memory +pids')
    for name,value in [('memory.max',p['memory_bytes']),('memory.swap.max',0),('pids.max',p['pids'])]:(cg/name).write_text(str(value))
    control=cg/'controller';jobs=cg/'jobs';control.mkdir();jobs.mkdir()
    (jobs/'cgroup.subtree_control').write_text('+cpu +memory +pids')
    cmd=[p['python']['path'],'-B',str(source/'run.py'),'run','--authority',str(Path(a.authority).absolute()),
         '--authority-bytes',str(a.authority_bytes),'--authority-sha256',a.authority_sha256,
         '--profile',str(Path(a.profile).absolute()),'--output',str(destination),
         '--outer-run-deadline-ns',str(run_end)]
    launch=save(root/'LAUNCH.json',{'argv':cmd,'started_ns':started,'run_deadline_ns':run_end,'cleanup_deadline_ns':cleanup_end,
       'authority':{'path':str(Path(a.authority).absolute()),**authority_pin},'profile':authority['profile'],
       'source_id':digest(manifest),'ownership':{'path':str(cg),'inode':inode}})
    process=None;forced=False;failure=None;status=None;eof={'stdout':False,'stderr':False};counts={k:0 for k in eof}
    fds={};pipes={};flush={};selector=selectors.DefaultSelector();hashes={n:hashlib.sha256() for n in eof}
    read_counts={n:0 for n in eof}
    def own():return cg.exists() and cg.stat().st_ino==inode
    def kill():
        nonlocal forced
        need(own(),'do not kill reused hierarchy');(cg/'cgroup.kill').write_text('1');forced=True
    def join():(control/'cgroup.procs').write_text(str(os.getpid()))
    try:
        need(time.monotonic_ns()<run_end,'startup used original interval')
        for name in eof:fds[name]=os.open(root/(name+'.txt'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        process=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
           close_fds=True,preexec_fn=join,start_new_session=True,
           env={'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
        for name,stream in [('stdout',process.stdout),('stderr',process.stderr)]:
            pipes[name]=stream;os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
        while process.poll() is None or selector.get_map():
            now=time.monotonic_ns();cpu=int(dict(x.split() for x in (cg/'cpu.stat').read_text().splitlines())['usage_usec'])*1000
            if not forced and (now>=run_end or cpu>p['cpu_ns']):failure='whole hierarchy time/CPU cap';kill()
            if now>=cleanup_end:failure='original cleanup cutoff';break
            for key,_ in selector.select(min(.05,max(0,(cleanup_end-now)/1e9))):
                name=key.data;room=p['stream_bytes']-counts[name]
                data=os.read(key.fileobj.fileno(),min(65536,room+1));read_counts[name]+=len(data)
                if not data:eof[name]=True;selector.unregister(key.fileobj);key.fileobj.close();continue
                accepted=data[:room];off=0
                while off<len(accepted):
                    need(time.monotonic_ns()<cleanup_end,'stream persistence cutoff')
                    n=os.write(fds[name],accepted[off:]);need(n>0,'short original stream write')
                    hashes[name].update(accepted[off:off+n]);off+=n;counts[name]+=n
                if len(data)>room:
                    if not forced:failure='whole stream cap; original prefix retained';kill()
                    selector.unregister(key.fileobj);key.fileobj.close()
        if process.poll() is None:kill()
        remaining=(cleanup_end-time.monotonic_ns())/1e9
        if process.poll() is None and remaining>0:
            try:status=process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:failure='root completion unobserved'
        else:status=process.poll()
    except Exception as exc:
        failure=type(exc).__name__+': '+str(exc)
        if process is not None and own():
            try:kill()
            except Exception:pass
    finally:
        for name,fd in fds.items():
            try:
                need(time.monotonic_ns()<cleanup_end,'late outer flush');os.fsync(fd);flush[name]='complete'
            except Exception as exc:flush[name]='failed:'+type(exc).__name__;failure=failure or 'original stream flush failed'
            finally:os.close(fd)
        selector.close()
        for stream in pipes.values():
            if not stream.closed:stream.close()
    empty=False;resources={};cleanup_error=None
    try:
        need(own(),'hierarchy custody lost')
        if 'populated 1' in (cg/'cgroup.events').read_text():kill()
        while 'populated 1' in (cg/'cgroup.events').read_text() and time.monotonic_ns()<cleanup_end:time.sleep(.01)
        empty='populated 0' in (cg/'cgroup.events').read_text()
        resources={name:(cg/name).read_text() for name in ('cpu.stat','memory.peak','memory.events','pids.events','io.stat')}
        if process is not None and process.poll() is None and empty:
            remaining=(cleanup_end-time.monotonic_ns())/1e9
            if remaining>0:status=process.wait(timeout=remaining)
        if empty:
            for child in sorted((x for x in cg.rglob('*') if x.is_dir()),key=lambda x:len(x.parts),reverse=True):child.rmdir()
            cg.rmdir()
    except Exception as exc:cleanup_error=type(exc).__name__+': '+str(exc)
    verdict=resource_verdict(resources,p)
    if not verdict['complete']:failure=failure or '; '.join(verdict['failures'])
    observation={'launch':launch,'exit_code':status,'launched':process is not None,'forced':forced,'failure':failure,
       'cleanup_error':cleanup_error,'cleanup_empty':empty,'stream_eof':eof,'stream_persistence':flush,
       'stream_counts':counts,'stream_read_counts':read_counts,'resources':resources,
       'leaf_resource_verdict':verdict,'known_stream_prefix_pins':{n:{'bytes':counts[n],'sha256':hashes[n].hexdigest()} for n in eof},'started_ns':started,'observed_ns':time.monotonic_ns(),
       'run_deadline_ns':run_end,'cleanup_deadline_ns':cleanup_end,'complete':False}
    # Original failure evidence is private and bounded. It cannot grant success
    # after the adopted cutoff; all late observation timestamps remain explicit.
    observation['streams']={}
    for name in eof:
        try:observation['streams'][name]=descriptor(root/(name+'.txt'),p['stream_bytes'])
        except Exception as exc:observation['streams'][name]={'capture_failure':type(exc).__name__}
    # Recapture failed child terminal evidence too; never equate missing cost to zero.
    observation['child_terminal_cost']={}
    for filename in ('PROGRAMME_FAILURE.json','WHOLE_COST.json'):
        try:
            need(time.monotonic_ns()<cleanup_end,'failed evidence recapture cutoff')
            raw=capture(destination/filename,p['terminal_file_bytes'])
            from n056.core import json_bytes
            body=json_bytes(raw)
            observation['child_terminal_cost'][filename]={'path':str(destination/filename),**byte_pin(raw),
                'body':body,'captured_bytes':len(raw)}
            if filename=='WHOLE_COST.json':
                observation['child_terminal_cost'][filename]['known_written_including_cost_file']=body['cost']['observed']['written']+len(raw)
                observation['child_terminal_cost'][filename]['basis']='original snapshot plus actually captured terminal bytes; excludes unmeasured OS I/O'
        except Exception as exc:
            observation['child_terminal_cost'][filename]={'unknown_or_missing':True,'error':type(exc).__name__+': '+str(exc)}
    evidence=terminal.emit('ORIGINAL_COMPLETION.json',observation)
    if not (status==0 and not forced and failure is None and cleanup_error is None and empty
            and all(eof.values()) and all(flush.get(n)=='complete' for n in eof)
            and time.monotonic_ns()<cleanup_end):
        terminal.close();return 1
    # Bounded transitive original-file reconciliation, with each identity read
    # once. All paths must remain under the selected source/output roots.
    allowed=(source,destination,root)
    external={str(Path(row['path']).absolute()):{k:row[k] for k in ('bytes','sha256')}
              for bound in (profile['runtime']['rootfs'],profile['provider']['model']) for row in bound['members']}
    seen={};bytes_read=0
    def authenticate(row):
        nonlocal bytes_read
        path=absolute(row['path'])
        key=str(path);pair={k:row[k] for k in ('bytes','sha256')}
        need(any(path.is_relative_to(x) for x in allowed) or external.get(key)==pair,'descriptor outside exact selected roots or model/runtime closure')
        if key in seen:need(seen[key]==pair,'conflicting original identities');return
        need(time.monotonic_ns()<cleanup_end,'external reconciliation cutoff')
        need(len(seen)<p['recapture_members'] and bytes_read+row['bytes']<=p['recapture_bytes'],'complete external recapture budget')
        capture(path,row['bytes'],pair);seen[key]=pair;bytes_read+=row['bytes']
    def walk(value):
        if type(value)is dict:
            if {'path','bytes','sha256'}<=set(value):authenticate(value)
            for x in value.values():walk(x)
        elif type(value)is list:
            for x in value:walk(x)
    selected={}
    for filename in ('REPORT.json','COLLECTOR.json','GRADE.json','WHOLE_COST.json','OPERATION_INDEX.json','PROTOCOL_OPERATOR_ONLY.json'):
        path=destination/filename;row=descriptor(path,p['terminal_file_bytes']);authenticate(row)
        body=read_json(path,p['terminal_file_bytes'],row);selected[filename]=row;walk(body)
        if filename=='REPORT.json':need(body['complete_outputs'] and body['original_final_blocks']==120,'complete original programme report')
        if filename=='OPERATION_INDEX.json':
            need(len(body['operations'])==body['actual_original_operations']==body['budget_process_starts'],'all original lifetimes')
            for operation_terminal in body['operations']:
                outcome=read_json(operation_terminal['path'],p['terminal_file_bytes'],operation_terminal)
                need(outcome['complete'],'every original child complete');walk(outcome)
    need(time.monotonic_ns()<cleanup_end,'no late terminal success')
    terminal.emit('TERMINAL_JOIN.json',{'original':evidence,'complete_original_artifacts':selected,'recaptured_members':len(seen),
       'recaptured_bytes':bytes_read,'source_id':digest(manifest),'observed_ns':time.monotonic_ns(),
       'source_join_verified':True,'original_outer_completion_observed':False,
       'completion_requires_external_original_exit_zero':True,'scientific_qualification':False})
    need(time.monotonic_ns()<cleanup_end,'terminal persistence exceeded original cutoff')
    terminal.close();return 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--authority',required=True);p.add_argument('--authority-bytes',type=int,required=True)
    p.add_argument('--authority-sha256',required=True);p.add_argument('--profile',required=True)
    p.add_argument('--destination',required=True);p.add_argument('--capture',required=True)
    raise SystemExit(main(p.parse_args()))

