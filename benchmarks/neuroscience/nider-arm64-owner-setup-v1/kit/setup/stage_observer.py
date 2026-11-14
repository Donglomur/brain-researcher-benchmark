"""Bounded stage observer. CPU/RAM/network enforced by reviewed Docker create.

Disk is a conservative sampled budget, NOT a filesystem quota. Only this stage's
exact owned container can be killed. All failures retain original output/receipt.
"""
import argparse, datetime, hashlib, json, os, pathlib, selectors, signal, subprocess, time, traceback

def size_tree(root):
    return sum(p.stat().st_size for p in pathlib.Path(root).rglob('*') if p.is_file() and not p.is_symlink())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--external',required=True);ap.add_argument('--name',required=True)
    ap.add_argument('--seconds',type=float,required=True);ap.add_argument('--selection',required=True)
    ap.add_argument('--container');ap.add_argument('--retention-root');ap.add_argument('--retention-limit',type=int)
    ap.add_argument('--disk-root',required=True);ap.add_argument('argv',nargs=argparse.REMAINDER)
    a=ap.parse_args();root=pathlib.Path(a.external);logs=root/'logs';logs.mkdir(exist_ok=True)
    assert a.name.replace('-','').replace('_','').isalnum() and 0<a.seconds<=5400
    assert not a.container or a.container.startswith('nider-clean-')
    argv=a.argv[1:] if a.argv[:1]==['--'] else a.argv;assert argv
    selection=json.loads(pathlib.Path(a.selection).read_text())
    end_global=datetime.datetime.fromisoformat(selection['start_utc']).timestamp()+5400
    assert time.time()<end_global
    paths={k:logs/(a.name+'.'+k) for k in ['stdout','stderr','json']}
    assert not any(p.exists() for p in paths.values())
    log_allowance=16*1024**2-size_tree(logs)-4*1024**2
    assert log_allowance>0
    if a.retention_root:
        assert a.retention_limit and size_tree(a.retention_root)<a.retention_limit-65536
    start=time.monotonic();deadline=min(start+a.seconds,start+end_global-time.time())
    data={'schema':'nider_portable_provision_stage_original_v1','argv':argv,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'requested_seconds':a.seconds,'effective_seconds':deadline-start,'container':a.container,'observations':[],'termination_reason':None,'cleanup':[],'pipe_EOF':[],'child_reaped':False}
    child=None;streams=selectors.DefaultSelector();written=0;next_disk=0;stopping=None;kill_sent=False
    interrupted=None;saved_handlers={}
    def note_cleanup_signal(signum,_frame):data['cleanup'].append({'event':'secondary_signal_during_unwind','signal':signum})
    def reason(value):
        if data['termination_reason'] is None:data['termination_reason']=value
    def docker_small(command,seconds=5):
        try:
            result=subprocess.run(command,capture_output=True,timeout=seconds)
            return {'argv':command,'exit_code':result.returncode,'stdout':result.stdout.decode(errors='replace'),'stderr':result.stderr.decode(errors='replace')}
        except subprocess.TimeoutExpired as exc:
            return {'argv':command,'timeout':seconds,'stdout':(exc.stdout or b'').decode(errors='replace'),'stderr':(exc.stderr or b'').decode(errors='replace')}
        except Exception as exc:return {'argv':command,'exception':type(exc).__name__+':'+str(exc)}
    try:
      with paths['stdout'].open('xb') as out,paths['stderr'].open('xb') as err:
        handles={'stdout':out,'stderr':err}
        child=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True);data['pid']=child.pid
        streams.register(child.stdout,selectors.EVENT_READ,'stdout');streams.register(child.stderr,selectors.EVENT_READ,'stderr')
        while streams.get_map() or child.poll() is None:
          now=time.monotonic()
          if now>=deadline:reason('wall_or_global_deadline')
          if a.retention_root and size_tree(a.retention_root)>a.retention_limit-65536:reason('retention_budget_margin')
          if now>=next_disk:
            private=size_tree(a.disk_root);obs={'elapsed_seconds':now-start,'private_files_bytes':private}
            if a.container:
              check=docker_small(['docker','inspect','--size','--format','{{json .}}',a.container])
              if check.get('exit_code')==0:
                info=json.loads(check['stdout']);rw=info.get('SizeRw',0);obs['owned_SizeRw']=rw;obs['container_id']=info['Id'];obs['state']=info['State'];obs['limits']={k:info['HostConfig'].get(k) for k in ['Memory','MemorySwap','NanoCpus','NetworkMode','PidsLimit']}
                obs['conservative_disk_bytes']=selection['base_size_bytes']+2*rw+private
                if obs['conservative_disk_bytes']>7*1024**3:reason('sampled_disk_budget_margin')
              else:obs['container_observation_error']=check;reason('container_size_observation_failed')
            data['observations'].append(obs);next_disk=time.monotonic()+20
          if data['termination_reason'] and stopping is None:
            stopping=time.monotonic()
            if a.container:data['cleanup'].append(docker_small(['docker','kill',a.container]))
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
          if stopping and not kill_sent and time.monotonic()-stopping>2:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            kill_sent=True
          if stopping and time.monotonic()-stopping>8:
            data['cleanup'].append({'event':'bounded_pipe_close_without_EOF'});break
          for key,_ in streams.select(.2):
            chunk=os.read(key.fileobj.fileno(),65536)
            if not chunk:
              data['pipe_EOF'].append(key.data);streams.unregister(key.fileobj);key.fileobj.close();continue
            permitted=log_allowance-written
            if a.retention_root:permitted=min(permitted,a.retention_limit-65536-size_tree(a.retention_root))
            if len(chunk)>max(0,permitted):reason('transcript_budget_margin');chunk=chunk[:max(0,permitted)]
            handles[key.data].write(chunk);handles[key.data].flush();written+=len(chunk)
        if child.poll() is None:
            if a.container:data['cleanup'].append(docker_small(['docker','kill',a.container]))
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        try:data['exit_code']=child.wait(timeout=3);data['child_reaped']=True
        except subprocess.TimeoutExpired:reason('unreaped_child')
    except BaseException as exc:
      interrupted=exc
      for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGALRM):
        saved_handlers[sig]=signal.getsignal(sig);signal.signal(sig,note_cleanup_signal)
      reason('observer_exception');data['observer_exception']={'class':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
      if a.container:data['cleanup'].append(docker_small(['docker','kill',a.container]))
      if child and child.poll() is None:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
      if child:
        try:data['exit_code']=child.wait(timeout=3);data['child_reaped']=True
        except subprocess.TimeoutExpired:pass
    finally:
      for key in list(streams.get_map().values()):streams.unregister(key.fileobj);key.fileobj.close()
      streams.close();data['elapsed_seconds']=time.monotonic()-start;data['logs']=[]
      if a.container:data['final_container_observation']=docker_small(['docker','inspect','--size','--format','{{json .}}',a.container])
      for k in ['stdout','stderr']:
        if paths[k].exists():
          raw=paths[k].read_bytes();data['logs'].append({'path':str(paths[k]),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
      if a.retention_root:data['retention_bytes_before_receipt']=size_tree(a.retention_root)
      paths['json'].write_text(json.dumps(data,indent=2)+'\n')
      print(json.dumps({'receipt':str(paths['json']),'bytes':paths['json'].stat().st_size,'sha256':hashlib.sha256(paths['json'].read_bytes()).hexdigest(),'exit_code':data.get('exit_code'),'termination_reason':data['termination_reason'],'elapsed_seconds':data['elapsed_seconds'],'child_reaped':data['child_reaped'],'pipe_EOF':data['pipe_EOF']}))
      for sig,old in saved_handlers.items():signal.signal(sig,old)
    if interrupted is not None and not isinstance(interrupted,Exception):raise interrupted
    return 0 if data.get('exit_code')==0 and data['termination_reason'] is None and data['child_reaped'] and set(data['pipe_EOF'])=={'stdout','stderr'} else 1

if __name__=='__main__':raise SystemExit(main())
