"""Generated resource/identity controls; no Docker, host probes or authentic assets."""
import ast
import copy
import json
import inspect
import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import memory_profile as M
import telemetry as T
BASE = HERE.parent/'neural034-portable'
RAW = BASE/M.LOCAL/'grader/grader_runtime.py'
SCORE = BASE/'benchmarks/neuroscience/neural-034/score.py'

def source_runtime():
    body=RAW.read_bytes()
    M.need(M.pin(body)=={'bytes':12696,'sha256':'83413b3058da6a95cc6d9a41ffc8cb0cd7dd1dd4d9839d619bbbb197bf2e7636'}, 'Pinned original source')
    return M.replace(body.decode(), 'stream.write(body); stream.flush(); os.fsync(fd)',
                     'stream.write(body); stream.flush(); os.fchmod(fd, 0o644); os.fsync(fd)').encode()

def held_source():
    body=SCORE.read_bytes()
    M.need(M.pin(body)=={'bytes':17590,'sha256':'82787ea36072a24e21c65ff1088a4238f6126ea43a46ba1949a2635bdeed81bc'}, 'Exact original scorer')
    held=types.ModuleType('_generated_memory_held'); held.__file__=str(SCORE)
    with mock.patch.dict(os.environ, {'NEURAL034_DOCKER':'/generated/never-dispatched-docker'}):
        exec(compile(body,str(SCORE),'exec'),held.__dict__)
    return held, body

def function(body,name):
    tree=ast.parse(body)
    return ast.dump(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)

def info(held):
    mounts={'/source/grader.py':'/generated/grader.py','/source/telemetry.py':'/generated/telemetry.py'}
    env={key:'2' for key in held.THREADS}; env['PYTHONDONTWRITEBYTECODE']='1'
    row={'Name':'/generated','Id':'a'*64,'Image':held.IMAGE,'State':{'Status':'created','Running':False,'Pid':0,'OOMKilled':False},
         'Config':{'Image':held.IMAGE,'User':'65534:65534','Entrypoint':['python'],
          'Cmd':['-I','-B','/source/telemetry.py'],'WorkingDir':'/tmp','Volumes':None,'Tty':False,'OpenStdin':False,
          'Env':[k+'='+v for k,v in env.items()]},
         'HostConfig':{'NetworkMode':'none','ReadonlyRootfs':True,'Privileged':False,'CapDrop':['ALL'],
          'SecurityOpt':['no-new-privileges:true'],'PidMode':'','IpcMode':'private','RestartPolicy':{'Name':'no'},
          'Memory':536870912,'MemorySwap':536870912,'NanoCpus':2000000000,'CgroupnsMode':'private','OomKillDisable':False,
          'PidsLimit':32,'ShmSize':1048576,'Tmpfs':held.TMPFS,'LogConfig':{'Type':'none','Config':{}},
          'Ulimits':[{'Name':k,'Soft':v[0],'Hard':v[1]} for k,v in held.ULIMITS.items()],
          'Mounts':[{'Type':'bind','Source':v,'Target':k,'ReadOnly':True} for k,v in mounts.items()]},
         'Mounts':[{'Type':'bind','Source':v,'Destination':k,'RW':False} for k,v in mounts.items()]}
    return row,mounts,env

class Controls(unittest.TestCase):

    def test_exact_resource_verifier_and_denials(self):
        held,body=held_source(); verify=M.derive_verify(held,body); row,mounts,env=info(held)
        verify(row,'generated',mounts,env)
        for key,value in [('Memory',4294967296),('MemorySwap',1073741824),('CgroupnsMode','host'),
                          ('NanoCpus',1000000000),('NetworkMode','host'),('ReadonlyRootfs',False)]:
            bad=copy.deepcopy(row); bad['HostConfig'][key]=value
            with self.assertRaises(ValueError): verify(bad,'generated',mounts,env)
        for edit in ('cmd','mount','env'):
            bad=copy.deepcopy(row)
            if edit=='cmd': bad['Config']['Cmd'][-1]='/source/grader.py'
            if edit=='mount': bad['Mounts'][1]['RW']=True
            if edit=='env': bad['Config']['Env'][0]=bad['Config']['Env'][0].replace('=2','=1')
            with self.assertRaises(ValueError): verify(bad,'generated',mounts,env)

    def test_counted_dispatch_overlay_preserves_permission_and_terminal_failure_evidence(self):
        derived=M.derive_runtime(source_runtime()); namespace={'__file__':str(RAW)}
        exec(compile(derived,str(RAW)+'::generated','exec'),namespace)
        self.assertIn('os.fchmod(fd, 0o644)',derived.decode())
        held,body=held_source(); tree=ast.parse(body)
        text=ast.get_source_segment(body.decode(),next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_child'))
        for before,after,count in namespace['RUN_CHILD_SUBSTITUTIONS']+M.substitutions(): text=M.replace(text,before,after,count)
        compile(text,'generated-run-child','exec')
        self.assertIn("'--cgroupns', 'private'",text)
        self.assertEqual(text.count('str(536870912)'),2)
        self.assertIn("args += [IMAGE, '-I', '-B', '/source/telemetry.py']",text)
        self.assertLess(text.index('Exact readonly telemetry source before dispatch'),text.index("created = docker(args, work)"))
        self.assertLess(text.index("write(run/'terminal_inspection.json'"),text.index('terminal(stopped_rows[0]'))
        self.assertIn('work = start+7',text); self.assertIn('cleanup(run, name, start+8.5)',text)
        # Execute the exact newly reordered terminal seam with a genuine OOM
        # guard failure: raw state must survive before validation rejects it.
        lines=text[text.index("        stopped = docker("):text.index("        report = json.loads")]
        lines='\n'.join(line[8:] for line in lines.splitlines())
        saved=[]; state={'Id':'a'*64,'State':{'OOMKilled':True,'ExitCode':137}}
        scope={'docker':lambda *a:{'returncode':0,'stdout':json.dumps([state])},'json':json,
          'need':M.need,'created_id':'a'*64,'name':'generated','work':1.,'outcome':{'returncode':137},
          'run':Path('/generated'), 'write':lambda path,value:saved.append((path,value)),
          'terminal':lambda *a:M.need(False,'actual OOM rejects successful grade')}
        with self.assertRaises(ValueError): exec(compile(lines,'generated-terminal','exec'),scope)
        self.assertEqual(saved,[(Path('/generated/terminal_inspection.json'),state)])

    def test_raw_frame_join_failures_and_unknown_not_sampled_peak(self):
        before={'schema':T.SCHEMA,'phase':'before','measurement':{'peak_status':'unsupported','peak_bytes':None}}
        after={'schema':T.SCHEMA,'phase':'after','measurement':{'peak_status':'unsupported','peak_bytes':None}}
        result={'returncode':0,'stdout':'original','stderr':T.frame_bytes(before).decode()+T.frame_bytes(after).decode()}
        parsed,normalized=M.parse_streams(result)
        self.assertEqual(normalized,{'returncode':0,'stdout':'original','stderr':''})
        self.assertEqual(parsed['coverage'],'both_ordered_frames')
        self.assertIsNone(parsed['frames'][1]['measurement']['peak_bytes'])
        self.assertFalse(parsed['full_container_lifetime_peak_claim'])
        for stderr in (result['stderr']+T.frame_bytes(after).decode(),T.frame_bytes(after).decode(),
                       T.PREFIX+'{"schema":"wrong","phase":"before"}\n',T.frame_bytes(before).decode().rstrip()):
            with self.assertRaises(ValueError): M.parse_streams(dict(result,stderr=stderr))
        _,mixed=M.parse_streams(dict(result,stderr=result['stderr']+'unexpected original stderr\n'))
        self.assertEqual(mixed['stderr'],'unexpected original stderr\n')

    def test_old_qualification_refused_before_runtime_loading(self):
        fake=types.ModuleType('run'); fake.checked=lambda *a,**k:json.dumps({'allowed_use':'separately_admitted_closed_viewer_protected_grading','resource_profile':M.PROFILE}).encode()
        fake.decode=json.loads
        review={'resource_profile':M.PROFILE,'portable_runtime':{'qualification':{}}}
        with mock.patch.dict(sys.modules,{'run':fake}):
            with self.assertRaisesRegex(ValueError,'no old4GiB'): M.install(types.SimpleNamespace(),Path('/generated'),review,{})
        with mock.patch.dict(sys.modules,{'run':fake}):
            with self.assertRaisesRegex(ValueError,'Root selected'): M.install(types.SimpleNamespace(),Path('/generated'),dict(review,resource_profile={}),{})

    def test_selected_overlay_is_shared_by_grade_recovery_and_full_provenance_checker(self):
        runtime=source_runtime(); bridge=(RAW.parent/'grade_bridge.py').read_bytes()
        original_pin={'bytes':12696,'sha256':'83413b3058da6a95cc6d9a41ffc8cb0cd7dd1dd4d9839d619bbbb197bf2e7636'}
        bridge=M.replace(bridge.decode(),repr(original_pin),repr(M.pin(runtime))).encode()
        source={'members':{name:M.pin((HERE/name).read_bytes()) for name in
                           ('memory_profile.py','telemetry.py','host_observation.py')}}
        roster={M.LOCAL+'grader/grader_runtime.py':runtime,M.LOCAL+'grader/grade_bridge.py':bridge}
        fake=types.ModuleType('run'); fake.FREEZE={'path':'source-freeze'}; fake.decode=json.loads
        def checked(value,root=None):
            name=value['path']
            if name=='qualification': return json.dumps({'allowed_use':M.ALLOWED_USE,'resource_profile':M.PROFILE}).encode()
            if name=='source-freeze': return json.dumps({'files':{k:M.pin(v) for k,v in roster.items()}}).encode()
            body=roster[name] if name in roster else (HERE/name).read_bytes()
            self.assertEqual(M.pin(body),{k:value[k] for k in ('bytes','sha256')}); return body
        def module(name,path,body):
            result=types.ModuleType(name); result.__file__=str(path)
            exec(compile(body,str(path),'exec'),result.__dict__); return result
        fake.checked=checked; fake.module=module
        review={'resource_profile':M.PROFILE,'portable_runtime':{'qualification':{'path':'qualification'}}}
        old=types.SimpleNamespace(grader=object(),owner=object())
        with mock.patch.dict(sys.modules,{'run':fake}): updated=M.install(old,BASE,review,source)
        self.assertIs(updated.owner,old.owner); self.assertIsNot(updated.grader,old.grader)
        runtime_object=updated.grader.runtime()
        original_grade=inspect.getclosurevars(updated.grader.grade).nonlocals['original_grade']
        self.assertIs(original_grade.__globals__['_RUNTIME'],runtime_object)
        self.assertIs(updated.grader.recover_grade.__globals__['_RUNTIME'],runtime_object)
        self.assertEqual(runtime_object.TOTAL_BYTES,M.GRADER_CAP)
        # The saved checker rejects even a single forged original-worker pin
        # before asking for any worker inspection, file or private asset.
        closure=inspect.getclosurevars(updated.grader.memory_check).nonlocals
        expected=closure['profile_record']; altered=copy.deepcopy(expected)
        altered['original_worker']['sha256']='0'*64
        fake.capture=lambda *a,**k:json.dumps(altered).encode()
        with self.assertRaisesRegex(ValueError,'whole executed'):
            updated.grader.memory_check('/generated',{}, {},{})
        held,unused=held_source(); initial,mounts,env=info(held)
        mounts['/source/telemetry.py']=str(HERE/'telemetry.py')
        initial['HostConfig']['Mounts'][1]['Source']=mounts['/source/telemetry.py']
        initial['Mounts'][1]['Source']=mounts['/source/telemetry.py']
        terminal=copy.deepcopy(initial); terminal['State'].update(Status='exited',ExitCode=0)
        measurement={'memory_limit_match':True,'swap_limit_match':True,'peak_status':'available',
          'peak_bytes':19000000,'peak_observed_monotonic_ns':100,'peak_kind':'kernel_cgroup_high_water',
          'entire_container_lifetime_measured':False,'oom_status':'available','oom_counters':{'oom':0,'oom_kill':0}}
        before={'schema':T.SCHEMA,'phase':'before','measurement':measurement}
        after={'schema':T.SCHEMA,'phase':'after','measurement':measurement,'worker_returncode':0,
               'before_frame_emitted':True,'same_cgroup_as_before':True}
        raw={'schema':'neural034-memory-worker-capture/v1','immutable_id':'a'*64,'container':'generated',
             'resource_profile':M.PROFILE,'result':{'returncode':0,'stdout':'same unchanged score',
              'stderr':T.frame_bytes(before).decode()+T.frame_bytes(after).decode()}}
        parsed,normalized=M.parse_streams(raw['result'])
        docs={'memory_profile.json':expected,'ownership.json':{'mounts':mounts},'worker_streams.json':raw,
              'memory.json':dict(parsed,immutable_id='a'*64,container='generated',resource_profile=M.PROFILE)}
        fake.capture=lambda path,*a,**k:json.dumps(docs[Path(path).name]).encode()
        child={'resource_profile':M.PROFILE,'worker':normalized}
        with mock.patch.dict(os.environ,{'NEURAL034_DOCKER':'/generated/never-dispatched-docker'}):
            observed=updated.grader.memory_check('/generated',initial,terminal,child)
            self.assertEqual(observed['after']['measurement']['peak_bytes'],19000000)
            self.assertFalse(observed['measured_sufficiency'])
            unknown=copy.deepcopy(after); unknown['measurement'].update(peak_status='unsupported',peak_bytes=None)
            raw['result']['stderr']=T.frame_bytes(before).decode()+T.frame_bytes(unknown).decode()
            parsed,normalized=M.parse_streams(raw['result']); child['worker']=normalized
            docs['memory.json']=dict(parsed,immutable_id='a'*64,container='generated',resource_profile=M.PROFILE)
            with self.assertRaisesRegex(ValueError,'Supported kernel peak'):
                updated.grader.memory_check('/generated',initial,terminal,child)
        sys.modules.pop('_neural034_memory512_frozen_grader',None)

    def test_host_probe_capture_is_same_owned_bounded_primitive(self):
        held,body=held_source(); call=M.host_capture(held,body)
        with self.assertRaisesRegex(ValueError,'fixed read-only'): call(['/usr/bin/true'],1.)
        self.assertIn('Popen',call.__code__.co_names)
        self.assertIn('DefaultSelector',call.__code__.co_names)
        self.assertIn('kill',call.__code__.co_names)



    def test_public_lineage_and_exact_package_dependency_closure(self):
        archive=HERE.parents[1]/'docs/memory512-control-20261118'
        original_body=(archive/'EXECUTED_SOURCE.json').read_bytes()
        self.assertEqual(M.pin(original_body),{'bytes':4356,'sha256':'7e778c1ff660c5828c9df9b3ad73c60c2087a5907857671a05ed794327e1ee2f'})
        original=json.loads(original_body)
        self.assertEqual(M.pin((archive/'EXECUTED_README.md').read_bytes()),original['members']['README.md'])
        current_body=(HERE/'SOURCE.json').read_bytes(); current=json.loads(current_body)
        runtime=types.ModuleType('_public_memory_run'); runtime.__file__=str(HERE/'run.py')
        exec(compile((HERE/'run.py').read_bytes(),runtime.__file__,'exec'),runtime.__dict__)
        checked,dependencies=runtime.package({'path':str(HERE/'SOURCE.json'),**M.pin(current_body)},HERE.parents[4],staged=HERE)
        self.assertEqual(checked,current); self.assertEqual(len(dependencies),5)
        self.assertEqual(len(current['members']),7)
        for name,expected in original['members'].items():
            if name.endswith('.py'):
                self.assertEqual(current['members'][name],expected)
                self.assertEqual(M.pin((HERE/name).read_bytes()),expected)
        self.assertNotEqual(current['members']['README.md'],original['members']['README.md'])
        self.assertEqual(current['resource_profile'],M.PROFILE)
        self.assertFalse(current['execution_authority']); self.assertFalse(current['native_qualification'])
        self.assertFalse(current['public_portability_lineage']['public_descriptor_executed'])
        self.assertFalse(current['public_portability_lineage']['qualification_inherited'])
        self.assertEqual(current['predecessor']['path'],'benchmarks/neural/NEURAL-034/docs/memory512-control-20261118/PREDECESSOR_SOURCE.json')
        self.assertEqual(M.pin((HERE.parents[4]/current['predecessor']['path']).read_bytes()),
                         {key:current['predecessor'][key] for key in ('bytes','sha256')})
        for key in ('bytes','sha256'):self.assertEqual(current['predecessor'][key],original['predecessor'][key])
        self.assertNotIn('/Users/',current_body.decode())
        remainder=copy.deepcopy(current); remainder.pop('public_portability_lineage')
        remainder['predecessor']['path']=original['predecessor']['path']
        remainder['members']['README.md']=original['members']['README.md']
        remainder['limitations']=remainder['limitations'][:-1]
        self.assertEqual(remainder,original)

if __name__=='__main__': unittest.main()
