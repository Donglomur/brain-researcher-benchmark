"""Portable stdlib source inspection/refusals only; no scientific operator calls."""
import hashlib
import json
import os
from pathlib import Path
import selectors
import stat
import subprocess
import sys
import tempfile
import time
import traceback
import tracemalloc

BUNDLE=(5160,'fd2c8d467b918340ddf2348b300dfe847ac3f2c629908023c0721e59813e0733')
MAX_TRANSFER=4*1048576
MAX_RETAINED=524288
MAX_LIVE=32*1048576
OUTPUT_RESERVE=65536
BASE=Path(__file__).resolve().parent


def need(ok,message):
    if not ok:raise AssertionError(message)


def main():
    costs={'read_bytes':0,'written_source_bytes':0,'source_capture_bytes':0,
           'adapter_initial_load_bytes':0,'subprocess_stream_bytes':0}
    checks=[];calls=[];failure=None;fixture=None;retained=0
    tracemalloc.start()
    def check(ok,name):
        need(ok,name);checks.append(name)
    def read(path,expected=None):
        s=path.lstat()
        need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and
             stat.S_IMODE(s.st_mode) in (0o444,0o644) and s.st_size<=1048576,'ordinary source member')
        b=path.read_bytes();costs['read_bytes']+=len(b)
        need(len(b)==s.st_size,'complete source read')
        if expected is not None:need((len(b),hashlib.sha256(b).hexdigest())==tuple(expected),'exact selected source')
        return b
    def write(path,b):
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as f:f.write(b)
        os.chmod(path,0o644);costs['written_source_bytes']+=len(b)
    def ordinary_inventory(root):
        rows=[]
        for p in root.rglob('*'):
            s=p.lstat()
            if stat.S_ISDIR(s.st_mode):continue
            need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'inventory has only ordinary distinct files')
            rows.append(p.relative_to(root).as_posix())
        return sorted(rows)
    def cli(path,args,cwd):
        argv=[sys.executable,'-I','-S','-B',str(path),*args]
        record={'argv_suffix':args,'exit_code':None,'stdout_bytes':0,'stderr_bytes':0,'timed_out':False}
        calls.append(record);streams={'stdout':bytearray(),'stderr':bytearray()};proc=None;sel=selectors.DefaultSelector()
        primary=None
        try:
            proc=subprocess.Popen(argv,cwd=cwd,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            for label,pipe in [('stdout',proc.stdout),('stderr',proc.stderr)]:
                os.set_blocking(pipe.fileno(),False);sel.register(pipe,selectors.EVENT_READ,label)
            deadline=time.monotonic()+30
            while sel.get_map():
                if time.monotonic()>deadline:record['timed_out']=True;raise TimeoutError('source inspection time limit')
                for key,_ in sel.select(min(.1,max(0,deadline-time.monotonic()))):
                    chunk=os.read(key.fileobj.fileno(),8192)
                    if chunk:
                        costs['subprocess_stream_bytes']+=len(chunk);streams[key.data].extend(chunk)
                        need(len(streams[key.data])<=65536,'bounded source-inspection stream')
                    else:sel.unregister(key.fileobj)
            try:record['exit_code']=proc.wait(timeout=max(.001,deadline-time.monotonic()))
            except subprocess.TimeoutExpired:record['timed_out']=True;raise
        except BaseException as error:primary=error
        finally:
            if proc is not None:
                if proc.poll() is None:
                    try:proc.kill();proc.wait(timeout=5)
                    except BaseException as error:
                        if primary is None:primary=error
                        else:primary.add_note('source child cleanup: '+repr(error))
                for pipe in (proc.stdout,proc.stderr):
                    if pipe is not None:pipe.close()
            sel.close()
            for label,b in streams.items():
                record[label+'_bytes']=len(b);record[label+'_sha256']=hashlib.sha256(b).hexdigest()
            costs['adapter_initial_load_bytes']+=10261
            record['stdout_utf8']=bytes(streams['stdout']).decode('utf8',errors='replace')
            record['stderr_utf8']=bytes(streams['stderr']).decode('utf8',errors='replace')
        if primary is not None:raise primary
        return record
    try:
        manifest_raw=read(BASE/'PACKAGE_FILES.json',BUNDLE);manifest=json.loads(manifest_raw)
        need(manifest['schema']=='nomad_portable_source_bundle_v1','bundle schema')
        check(manifest['preserved_runtime_files']==23 and manifest['preserved_runtime_bytes']==256661,
              'complete unchanged23 runtime extent')
        check(manifest['scientific_manifest_members']==19 and manifest['scientific_manifest_bytes']==238488,
              'complete19 scientific members')
        need(manifest['scientific_execution_or_qualification'] is False,'inactive bundle')
        bodies={}
        for row in manifest['files']:
            name=row['path'];p=Path(name)
            need(name not in bodies and not p.is_absolute() and '..' not in p.parts and str(p)==name,'closed bundle path')
            bodies[name]=read(BASE/name,(row['bytes'],row['sha256']))
        check(len(bodies)==27,'all23 runtime plus four documentation/license bodies')
        component_names=sorted(n.split('/',1)[1] for n in bodies if n.startswith('recovered-operators-v3/'))
        check(len(component_names)==23,'every installed component role supplied')
        check(ordinary_inventory(BASE/'recovered-operators-v3')==component_names,'complete supplied component census')
        # Resolve the ordinary temporary parent; macOS /var aliases are not source paths.
        temporary_parent=Path(tempfile.gettempdir()).resolve()
        with tempfile.TemporaryDirectory(prefix='nomad source checkout ',dir=temporary_parent) as td:
            fixture=Path(td);checkout=fixture/'checkout with spaces';other=fixture/'unrelated cwd';other.mkdir()
            for name,b in bodies.items():write(checkout/name,b)
            write(checkout/'PACKAGE_FILES.json',manifest_raw)
            retained=sum(len(b) for b in bodies.values())+len(manifest_raw)
            check(retained<=MAX_RETAINED,'finite complete source-only checkout')
            child=checkout/'recovered-operators-v3';entry=child/'operator_entry.py'
            observed=cli(entry,['--inspect'],other)
            check(observed['exit_code']==0 and observed['stderr_bytes']==0,'actual isolated cold-checkout CLI inspection')
            result=json.loads(observed['stdout_utf8'])
            costs['source_capture_bytes']+=result['source_capture']['logical_read_reserved']
            check((result['source_members'],result['source_bytes'])==(19,238488),'actual complete capture counts')
            check(result['source_capture']['logical_read_reserved']==241972,'manifest plus complete19 startup bytes')
            check(result['actions']==['plan','consume','grade'] and result['candidate_target_API'] is False
                  and result['default_scientific_execution'] is False and result['qualification'] is False,
                  'real API scope retained without authority or scientific promotion')
            check(len(result['source_capture']['attempts'])==20 and all(x['status']=='captured' for x in result['source_capture']['attempts']),
                  'all20 source captures completed')
            rejected_cli=cli(entry,['--consume'],other)
            check(rejected_cli['exit_code']==2 and rejected_cli['stdout_bytes']==0,'scientific action not exposed by CLI')
            # Load only the stdlib inspection adapter, never bootstrap/source scientific code.
            adapter_raw=read(entry,(10261,'43e180b44a2ed24ef6d268974eba2b6312f2ece1edf1c3e7bc0a961956f6e349'))
            ns={'__name__':'nomad_portable_inspection_only','__file__':str(entry)}
            before_modules=set(sys.modules);exec(compile(adapter_raw,str(entry),'exec'),ns)
            check(not ({'numpy','h5py','scipy','torch','tensorflow'} & (set(sys.modules)-before_modules)),
                  'inspection adapter loads no numerical package')
            def refuse(name,limit=16777216):
                try:ns['inspect_source'](child,source_read_limit=limit)
                except (ValueError,OSError) as error:
                    prefix=getattr(error,'nomad_installed_source_prefix',None)
                    need(prefix is not None,'refusal retains actual source prefix')
                    costs['source_capture_bytes']+=prefix['logical_read_reserved'];checks.append(name)
                    return prefix
                raise AssertionError('accepted '+name)
            prefix=refuse('read ceiling refuses before first source body',3483)
            check(prefix['logical_read_reserved']==0,'refused startup has no charged body read')
            bootstrap=child/'bootstrap.py';original=bodies['recovered-operators-v3/bootstrap.py']
            bootstrap.unlink();refuse('missing required bootstrap refuses');write(bootstrap,original)
            bootstrap.unlink();write(bootstrap,b'!'+original[1:]);refuse('same-length altered bootstrap refuses')
            bootstrap.unlink();write(bootstrap,original)
            alias=fixture/'bootstrap alias.txt';write(alias,original)
            retained=max(retained,sum(len(b) for b in bodies.values())+len(manifest_raw)+len(original))
            bootstrap.unlink();bootstrap.symlink_to(alias);refuse('symlink source refuses');bootstrap.unlink();write(bootstrap,original)
            alias.unlink();os.link(bootstrap,alias);refuse('hardlinked source refuses');alias.unlink()
            extra=child/'unexpected.txt';write(extra,b'invented source census marker\n')
            check(ordinary_inventory(child)!=component_names,'portable full inventory detects an extra file')
            extra.unlink()
            check(ordinary_inventory(child)==component_names,'all23 source roles restored before owned cleanup')
            check(not any(n.startswith('_nomad_recovered_') for n in set(sys.modules)-before_modules),
                  'no captured scientific module loaded')
            need(not any(n in sys.modules for n in ('numpy','h5py','scipy','torch','tensorflow')),'no numeric/native libraries loaded')
        fixture=None
    except BaseException as error:
        failure={'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()}
    current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    transfer=sum(costs.values())+OUTPUT_RESERVE
    result={'schema':'nomad_portable_source_checks_v1','status':'PASS' if failure is None else 'FAIL',
            'checks':checks,'checks_passed':len(checks),'failure':failure,'costs':costs,
            'transfer_with_output_reserve':transfer,'transfer_limit':MAX_TRANSFER,
            'retained_source_peak':retained,'retained_limit':MAX_RETAINED,
            'traced_python_peak':peak,'known_live_with_source_extent':peak+retained,'known_live_limit':MAX_LIVE,
            'bounds_pass':transfer<=MAX_TRANSFER and retained<=MAX_RETAINED and peak+retained<=MAX_LIVE,
            'subprocesses':calls,'fixture_generator':'this exact source; complete source copies only, no arrays',
            'owned_temporary_checkout_removed':fixture is None or not fixture.exists(),'initial_interpreter_stdlib_OS_RSS_or_child_RSS_measured':False,
            'scientific_actions_invoked':[],'actual_native_model_data_Git_network_or_publication':False,
            'source_only_no_qualification':True}
    # All observations precede final outcome assertions; failures remain visible.
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 0 if failure is None and result['bounds_pass'] else 1


if __name__=='__main__':raise SystemExit(main())
