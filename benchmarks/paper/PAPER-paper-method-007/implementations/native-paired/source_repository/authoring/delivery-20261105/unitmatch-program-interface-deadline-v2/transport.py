"""Local binding around exact retained UnitMatch transport sources, not a new task engine."""
import json, os, selectors, signal, subprocess, sys, time, types
from pathlib import Path
from bound_io import need,capture,parse,encoded,identity

def loaded(name,body,path):
    mod=types.ModuleType(name);mod.__file__=str(path);sys.modules[name]=mod
    exec(compile(body,str(path),'exec'),mod.__dict__);return mod

def bounded_call(binary,env,args,deadline,cap):
    """Adapted NEURAL068 bounded CLI capture; nonzero exits remain explicit operands."""
    need(deadline-time.monotonic()>0,'Docker client deadline')
    p=sel=None;completed=None;buffers={'stdout':bytearray(),'stderr':bytearray()}
    try:
        p=subprocess.Popen([binary,*args],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,start_new_session=True,bufsize=0)
        sel=selectors.DefaultSelector()
        for key,f in [('stdout',p.stdout),('stderr',p.stderr)]:os.set_blocking(f.fileno(),False);sel.register(f,selectors.EVENT_READ,key)
        while sel.get_map():
            left=deadline-time.monotonic();need(left>0,'Bounded Docker client time')
            for key,_ in sel.select(min(.05,left)):
                try:b=os.read(key.fileobj.fileno(),min(32768,cap-len(buffers[key.data])+1))
                except BlockingIOError:continue
                if not b:sel.unregister(key.fileobj);continue
                need(len(buffers[key.data])+len(b)<=cap,'Preventive Docker stream cap');buffers[key.data].extend(b)
        rc=p.wait(timeout=max(.001,deadline-time.monotonic()))
        need(time.monotonic()<deadline,'Client wait deadline')
        completed=subprocess.CompletedProcess(args,rc,bytes(buffers['stdout']),bytes(buffers['stderr']))
    except BaseException as error:
        error.stdout_bytes=len(buffers['stdout']);error.stderr_bytes=len(buffers['stderr'])
        error.returncode=p.poll() if p is not None else None
        raise
    finally:
        try:
            if p is not None and p.poll() is None:
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                p.wait(timeout=max(.001,min(1,deadline-time.monotonic())))
        finally:
            try:
                if sel is not None:sel.close()
            finally:
                if p is not None:
                    try:p.stdout.close()
                    finally:p.stderr.close()
    if time.monotonic()>=deadline:
        error=TimeoutError('Client close deadline');error.stdout_bytes=len(buffers['stdout'])
        error.stderr_bytes=len(buffers['stderr']);error.returncode=p.returncode if p is not None else None
        raise error
    return completed

def bind(source,snapshot,public_root,unit,binary,env,budget,verified_mounts,validate_fold,call=bounded_call):
    """Compile authenticated bytes. Only filesystem locator globals are rebound."""
    mods={}
    loaded('io_utils',source['vendor/io_utils.py'],snapshot/'io_utils.py')
    for name in ('absence','runtime_contract','engine','contract_profile','profile','interface'):
        mods[name]=loaded(name,source['vendor/'+name+'.py'],snapshot/(name+'.py'))
    old_command=mods['contract_profile'].command
    def task_command(role,profile):
        if role=='holder':return old_command(role,profile)
        return ['-I','-B','/program/program.py','--input','/input','--out','/output','--held-out',unit['unit_id'],'--access-view',unit['view'],'--method-name',unit['method_name'],'--program-sha256',unit['program_sha256']]
    mods['contract_profile'].command=task_command
    original=mods['engine'];engines=[]
    class BoundEngine(original.Engine):
        def __init__(self,end,out,budget):
            super().__init__(end,out,budget);self.identities={};self.successful=[];engines.append(self)
        def run(self,args,timeout=5,cap=200000):
            need(0<cap<=22000000 and len(self.commands)<160,'Bounded task command inventory')
            self.budget.charge_read(2*(cap+1))
            try:p=call(binary,env,args,min(self.end,time.monotonic()+timeout),cap)
            except BaseException as error:
                self.sequence+=1;self.commands.append({'sequence':self.sequence,'argv':args,
                    'returncode':getattr(error,'returncode',None),'stdout_bytes':getattr(error,'stdout_bytes',0),
                    'stderr_bytes':getattr(error,'stderr_bytes',0),'error_type':type(error).__name__})
                raise
            self.sequence+=1;self.commands.append({'sequence':self.sequence,'argv':args,'returncode':p.returncode,'stdout_bytes':len(p.stdout),'stderr_bytes':len(p.stderr)})
            return p
        def journal(self):self.budget.save(self.out/'resource_ownership.json',{'owned':self.owned},65536,replace=True)
        def inspect(self,kind,name):
            v=super().inspect(kind,name);key=(kind,name)
            prior=self.identities.get(key)
            ident=v['Id'] if kind=='container' else (v['Name'],v['CreatedAt'],v['Mountpoint'],v['Driver'],v.get('Options'))
            need(prior is None or prior==ident,'Stable owned resource identity');self.identities[key]=ident
            return v
        def cleanup(self,kind,name):
            row={'kind':kind,'name':name,'absence_verified':False};key=(kind,name)
            try:
                owned=[r for r in self.owned if (r['kind'],r['name'])==key]
                need(len(owned)==1 and owned[0]['attempted_before_dispatch'] is True,'Only journaled exact resource')
                def inspect(target):return ['volume','inspect',target] if kind=='volume' else ['inspect','--type','container',target]
                def absent(target,p):return mods['absence'].absence(p.returncode,p.stdout.decode(),p.stderr.decode(),kind,target)
                q=self.run(inspect(name),timeout=2);prior=self.identities.get(key)
                if not absent(name,q):
                    need(q.returncode==0,'Live inspect or exact absence')
                    rows=json.loads(q.stdout);need(type(rows)is list and len(rows)==1,'Single resource')
                    v=rows[0];need(v['Name']==(name if kind=='volume' else '/'+name),'Exact current name')
                    now=v['Id'] if kind=='container' else (v['Name'],v['CreatedAt'],v['Mountpoint'],v['Driver'],v.get('Options'))
                    # A create without an authenticated inspection remains unresolved; never remove by guessed name.
                    need(prior is not None and now==prior,'Saved immutable identity before removal')
                    target=prior if kind=='container' else name
                    r=self.run(['volume','rm',target] if kind=='volume' else ['rm','--force',target],timeout=2)
                    row['remove_returncode']=r.returncode
                need(prior is not None,'Known created identity for successful cleanup')
                targets=[name,prior] if kind=='container' else [name];observed={}
                for target in targets:observed[target]=absent(target,self.run(inspect(target),timeout=2))
                row.update(required_absence_targets=targets,absence_observations=observed,absence_verified=all(observed.values()))
            except BaseException as e:row['error_type']=type(e).__name__
            self.successful.append(row);return row
    facade=types.ModuleType('qualified_core');facade.BaseEngine=BoundEngine;facade.regular=original.regular;facade.digest=original.digest;sys.modules['qualified_core']=facade
    support=types.ModuleType('ordinary_support')
    support.admit_unit=lambda got,sha:need(got==unit and type(sha)is str and len(sha)==64,'Exact ordinary unit')
    support.verified_input_mounts=verified_mounts;sys.modules['ordinary_support']=support
    ep=loaded('engine_profile',source['vendor/engine_profile.py'],snapshot/'engine_profile.py')
    task=loaded('_portable_neural099_unit',source['vendor/task_unit.py'],snapshot/'task_unit.py')
    task.HERE=snapshot;task.ROOT=public_root
    def validate_public(raw):
        validate_fold(raw,unit)
        return True
    return {'task':task,'engine_class':BoundEngine,'engines':engines,'contract':mods['contract_profile'],'validate_public':validate_public,
        'interface':mods['interface'],'absence':mods['absence'],'profile_engine':ep.ProfileEngine}


def barrier(lib,deadline):
    rows=[]
    for engine in lib['engines']:
        engine.end=deadline
        for item in reversed(engine.owned):rows.append(engine.cleanup(item['kind'],item['name']))
    need(len(rows)==3 and all(r['absence_verified'] for r in rows),'All three unit resources absent before private release')
    need(sum(r['kind']=='container' for r in rows)==2 and sum(r['kind']=='volume' for r in rows)==1,'Producer,holder,volume only')
    return rows
