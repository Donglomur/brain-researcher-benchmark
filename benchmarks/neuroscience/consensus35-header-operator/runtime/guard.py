"""Exact nested capacity primitives; unrelated donor dispatch omitted."""
import base64,decimal,errno,hashlib,json,os,plistlib,re,selectors,signal,stat,subprocess,sys,time
from pathlib import Path

def main():
 def need(ok,msg):
  if not ok: raise ValueError(msg)

 def alarm(*_): result['deadline_alarm_observed']=True

 def check_active():
  if result['deadline_alarm_observed'] or time.monotonic()>=deadline:raise TimeoutError('guard_admission_deadline')

 def encoded(v):return (json.dumps(v,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()

 def put(path,v):
  raw=encoded(v);need(len(raw)<=262144,'guard_member_extent')
  with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  path.chmod(0o600)
  return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

 def close_group(p):
  notes=[];until=time.monotonic()+2;absent_now=False
  for i in range(66):
   try:os.killpg(p.pid,0)
   except OSError as e:
    notes.append({'probe':i,'errno':e.errno})
    if e.errno==errno.ESRCH:absent_now=True;break
    break
   else:
    notes.append({'probe':i,'present':True})
    if i==0:
     try:os.killpg(p.pid,signal.SIGKILL);notes.append({'signal':'SIGKILL','delivered':True})
     except OSError as e:notes.append({'signal':'SIGKILL','errno':e.errno})
   if time.monotonic()>=until:break
   time.sleep(min(.01,max(0,until-time.monotonic())))
  return {'complete':absent_now,'explicit_ESRCH':absent_now,'observations':notes}

 def probe(name,argv):
  check_active()
  start_ns=time.monotonic_ns(); wall_ns=time.time_ns();t=start_ns/1e9;until=min(t+3,deadline)
  row={'name':name,'argv':argv,'started_monotonic_ns':str(start_ns),'started_wall_ns':str(wall_ns),'active_timeout_seconds':3,'stream_cap_bytes':65536,'invocations':1,'stdout_EOF':False,'stderr_EOF':False,'failure':None}
  proc=None;sel=selectors.DefaultSelector();buffers={'stdout':bytearray(),'stderr':bytearray()}
  admission={'name':name,'spawn_attempted':False,'spawn_returned':False,'pid':None,'reaped':False,'group_absent':False,'receipt_recorded':False}
  result['probe_admissions'].append(admission)
  owned[name]={'proc':None,'selector':sel,'admission':admission}
  try:
   check_active();admission['spawn_attempted']=True
   proc=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,env={'PATH':'/usr/bin:/bin:/usr/sbin','LANG':'C','LC_ALL':'C'})
   owned[name]['proc']=proc;admission['spawn_returned']=True;admission['pid']=proc.pid
   row['pid']=proc.pid;row['new_session']=True;check_active()
   for label,f in [('stdout',proc.stdout),('stderr',proc.stderr)]:
    os.set_blocking(f.fileno(),False);sel.register(f,selectors.EVENT_READ,label)
   while sel.get_map() or proc.poll() is None:
    check_active();need(time.monotonic()<until,'probe_active_deadline')
    for key,_ in sel.select(min(.05,max(0,until-time.monotonic()))):
     label=key.data;left=65536-len(buffers[label]);need(left>0,'probe_stream_limit_reached')
     data=os.read(key.fileobj.fileno(),min(8192,left))
     if not data:row[label+'_EOF']=True;sel.unregister(key.fileobj)
     else:
      buffers[label].extend(data)
      need(len(buffers[label])<65536,'probe_stream_limit_reached')
   proc.wait(timeout=max(.001,until-time.monotonic()));row['returncode']=proc.returncode;row['active_ended_monotonic_ns']=str(time.monotonic_ns())
  except BaseException as e:
   row['failure']={'type':type(e).__name__,'message':str(e)[:512]}
  finally:
   if proc is not None:
    if proc.poll() is None:
     try:os.killpg(proc.pid,signal.SIGKILL)
     except OSError as e:row['kill_errno']=e.errno
     try:proc.wait(timeout=2)
     except subprocess.TimeoutExpired:row['reaping_unresolved']=True
    row['returncode']=proc.poll();row['reaped']=type(proc.returncode) is int
    # Preserve all still-available observed bytes after a failed probe, within the same stream ceilings.
    for key in list(sel.get_map().values()):
     label=key.data
     while len(buffers[label])<65536:
      try:data=os.read(key.fileobj.fileno(),min(8192,65536-len(buffers[label])))
      except BlockingIOError:break
      if not data:row[label+'_EOF']=True;break
      buffers[label].extend(data)
    row['group_cleanup']=close_group(proc)
    admission['reaped']=row['reaped'];admission['group_absent']=row['group_cleanup']['complete']
    for f in (proc.stdout,proc.stderr):
     if f is not None:f.close()
   sel.close()
   for label in ('stdout','stderr'):
    raw=bytes(buffers[label]);row[label+'_bytes']=len(raw);row[label+'_sha256']=hashlib.sha256(raw).hexdigest();row[label+'_base64']=base64.b64encode(raw).decode('ascii');result['probe_body_bytes']+=len(raw)
   end_ns=time.monotonic_ns();row['ended_monotonic_ns']=str(end_ns);row['ended_wall_ns']=str(time.time_ns());row['elapsed_seconds']=(end_ns-start_ns)/1e9
   row['complete']=row['failure'] is None and row.get('returncode')==0 and row.get('reaped') is True and row['stdout_EOF'] and row['stderr_EOF'] and row.get('group_cleanup',{}).get('complete') is True
   receipt=put(guard/'PROBES'/(name+'.json'),row);result['probes'].append({'name':name,'pid':row.get('pid'),'receipt':receipt,'complete':row['complete'],'returncode':row.get('returncode'),'reaped':row.get('reaped'),'group_absent':row.get('group_cleanup',{}).get('complete',False)})
  admission['receipt_recorded']=True
  owned.pop(name,None)
  return row
