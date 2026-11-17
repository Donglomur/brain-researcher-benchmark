"""Concrete process effects and separately observed custody/closure completion."""
from pathlib import Path
import os,resource,signal,subprocess,time,stat
from banc_runtime.codec import need
from .io import exact_fields,integer,absolute_directory,read
from .custody import open_file,identity
from .clock import guard
from .failures import observation

def sandbox_argv(config,*,role,input_root,output_root,source_root,command,meter):
    guard(meter,'before_enclosure_construction')
    exact_fields(config,('profile','launcher_root','launcher','rootfs','python','Rscript','environment'),'sandbox')
    need(config['profile']=='linux_bwrap_v1','explicit separately qualified Linux bubblewrap enclosure')
    raw=read(config['launcher_root'],config['launcher'],meter,16777216)
    launcher=absolute_directory(config['launcher_root'])/config['launcher']['path']
    need(os.access(launcher,os.X_OK),'qualified executable namespace launcher')
    rootfs=absolute_directory(config['rootfs']);input_root=absolute_directory(input_root);output_root=absolute_directory(output_root)
    need(type(config['environment']) is dict and all(type(k) is str and type(v) is str and k not in ('LD_PRELOAD','PYTHONPATH') for k,v in config['environment'].items()),'explicit qualified environment')
    argv=[str(launcher),'--die-with-parent','--new-session','--unshare-all','--clearenv','--ro-bind',str(rootfs),'/',
      '--proc','/proc','--dev','/dev','--tmpfs','/tmp','--ro-bind',str(input_root),'/input','--bind',str(output_root),'/output','--chdir','/output']
    need(role in ('reference','actor_cluster','actor_downstream'),'closed enclosure role')
    if role=='reference':argv+=['--ro-bind',str(absolute_directory(source_root)),'/programme']
    for name,value in sorted(config['environment'].items()):
        need(name and '\0' not in name+value and '=' not in name,'plain environment pair');argv+=['--setenv',name,value]
    need(type(command) is list and command and all(type(x) is str and '\0' not in x for x in command),'closed argv without shell')
    guard(meter,'after_enclosure_construction');return argv+['--']+command

def bounded_process(argv,*,cwd,log_root,name,limits,meter):
    """Natural child status never certifies observer/log/resource closure.

    No ambiguous close is retried; independent closes are all attempted. A
    successful child with incomplete custody returns effective failure125 and
    retains the natural child0 separately. Rlimits are not physical enclosure.
    """
    guard(meter,'before_process_setup');cwd=absolute_directory(cwd);log_root=absolute_directory(log_root)
    need(type(name) is str and name and all(c.isascii() and (c.isalnum() or c in '._-') for c in name),'ordinary process identity')
    for k in ('wall_seconds','cpu_seconds','address_space_bytes','file_bytes'):integer(limits[k],k,1)
    meter.start_job();meter.reserve_output(2*limits['file_bytes'])
    names=[name+'.stdout',name+'.stderr'];fds=[];created=[];events=[];cleanup=[];primary=None
    def restrict():
        resource.setrlimit(resource.RLIMIT_CPU,(limits['cpu_seconds'],limits['cpu_seconds']))
        resource.setrlimit(resource.RLIMIT_AS,(limits['address_space_bytes'],limits['address_space_bytes']))
        resource.setrlimit(resource.RLIMIT_FSIZE,(limits['file_bytes'],limits['file_bytes']))
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    proc=None;ru=None;natural=None;started=time.monotonic();reason=None
    try:
        for leaf in names:
            directory,leaf,fd=open_file(log_root,leaf,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
            fds.append(fd);created.append((directory,leaf,identity(os.fstat(fd))))
        guard(meter,'before_process_spawn');cwd.verify();log_root.verify()
        proc=subprocess.Popen(argv,cwd=cwd,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},stdin=subprocess.DEVNULL,
          stdout=fds[0],stderr=fds[1],start_new_session=True,preexec_fn=restrict,close_fds=True)
        while True:
            pid,status,usage=os.wait4(proc.pid,os.WNOHANG)
            if pid:ru=usage;natural=os.waitstatus_to_exitcode(status);proc.returncode=natural;break
            guard(meter,'during_process')
            if time.monotonic()-started>limits['wall_seconds']:
                reason='child_wall_deadline_exceeded';os.killpg(proc.pid,signal.SIGKILL)
                _,status,ru=os.wait4(proc.pid,0);natural=os.waitstatus_to_exitcode(status);proc.returncode=natural;break
            time.sleep(.01)
        guard(meter,'after_process_wait')
    except BaseException as exc:
        primary=observation(exc,'process_observation');events.append(primary)
        if proc is not None and proc.returncode is None:
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            except BaseException as cleanup_error:events.append(observation(cleanup_error,'process_kill_cleanup'))
            try:
                _,status,ru=os.wait4(proc.pid,0);natural=os.waitstatus_to_exitcode(status);proc.returncode=natural
            except BaseException as cleanup_error:events.append(observation(cleanup_error,'process_wait_cleanup'))
    finally:
        for index,fd in enumerate(fds):
            try:os.close(fd)
            except BaseException as exc:
                event=observation(exc,'log_'+str(index)+'_close_ambiguous_no_retry');cleanup.append(event);events.append(event)
    extents=[];extent_known=True
    for directory,leaf,original in created:
        try:
            directory.verify();st=os.stat(leaf,dir_fd=directory.fd,follow_symlinks=False)
            need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and identity(st)==original and st.st_size<=limits['file_bytes'],'original bounded process log current identity')
            extents.append(st.st_size)
        except BaseException as exc:extent_known=False;events.append(observation(exc,'log_extent_or_identity'))
    if extent_known:meter.complete_output(sum(extents))
    try:cwd.verify();log_root.verify();guard(meter,'after_process_log_closure')
    except BaseException as exc:events.append(observation(exc,'process_terminal_custody_or_deadline'))
    complete=not events and natural is not None and ru is not None and extent_known and len(created)==2
    effective=natural if complete else 125
    failure=reason or (None if effective==0 else ('process_exit_'+str(natural) if complete else 'observer_or_custody_incomplete'))
    rss=None if ru is None else int(ru.ru_maxrss*(1 if os.uname().sysname=='Darwin' else 1024))
    return {'id':name,'argv':argv,'natural_exit_code':natural,'exit_code':effective,'observer_complete':complete,
      'wall_seconds':time.monotonic()-started,'peak_rss_bytes':rss,'output_bytes':sum(extents) if extent_known else None,
      'failure':failure,'observations':events,'cleanup_errors':cleanup,'selected_limits':limits,
      'cpu_user_seconds':None if ru is None else ru.ru_utime,'cpu_system_seconds':None if ru is None else ru.ru_stime,
      'stdout_path':str(log_root/names[0]),'stderr_path':str(log_root/names[1]),'native_or_scientific_qualification_inferred':False}
