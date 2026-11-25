"""Focused EXP003 bootstrap controls; no Docker, R, network or payload install."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'run_exp003_generated_r.py'
if not SOURCE.exists(): SOURCE=HERE.parents[1]/'scripts/maintenance/run_exp003_generated_r.py'
verified=globals().get('__EXP003_VERIFIED_BOOTSTRAP__')
if verified is None:
    spec=importlib.util.spec_from_file_location('exp003_bootstrap',SOURCE)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
else:
    m=types.ModuleType('exp003_bootstrap');m.__file__=str(SOURCE)
    exec(compile(verified,str(SOURCE),'exec'),m.__dict__)
TRANSIENT_LOGICAL_BYTES=0


class Controls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.path=self.root/'source.py';self.path.write_bytes(b'code')
        self.digest=hashlib.sha256(b'code').hexdigest()
    def tearDown(self):
        global TRANSIENT_LOGICAL_BYTES
        TRANSIENT_LOGICAL_BYTES+=sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file() and not p.is_symlink())
        self.tmp.cleanup()
    def test_exact_source_bytes(self):self.assertEqual(m.pinned(self.path,4,self.digest),b'code')
    def test_tamper_and_extent_refusal(self):
        for size,digest in ((4,'0'*64),(3,self.digest),(65537,self.digest)):
            with self.subTest(size=size,digest=digest),self.assertRaises(ValueError):m.pinned(self.path,size,digest)
    def test_single_hardlink_required(self):
        os.link(self.path,self.root/'alias')
        with self.assertRaisesRegex(ValueError,'single-link'):m.pinned(self.path,4,self.digest)
    def test_leaf_and_parent_symlinks_refused(self):
        link=self.root/'link';link.symlink_to(self.path)
        with self.assertRaises(OSError):m.pinned(link,4,self.digest)
        directory=self.root/'directory';directory.mkdir();(directory/'x').write_bytes(b'code')
        alias=self.root/'alias';alias.symlink_to(directory,target_is_directory=True)
        with self.assertRaises(OSError):m.pinned(alias/'x',4,self.digest)
    def test_fifo_is_refused_without_blocking(self):
        fifo=self.root/'fifo';os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError,'single-link'):m.pinned(fifo,4,self.digest)
    def test_content_mutation_during_read_is_refused(self):
        original=m.os.fdopen
        path=self.path
        class Wrapper:
            def __init__(self,stream):self.stream=stream
            def __enter__(self):return self
            def __exit__(self,*args):self.stream.close()
            def read(self,size):
                result=self.stream.read(size);path.write_bytes(b'evil');return result
        with patch.object(m.os,'fdopen',side_effect=lambda *a,**kw:Wrapper(original(*a,**kw))):
            with self.assertRaisesRegex(ValueError,'pin mismatch'):m.pinned(self.path,4,self.digest)
    def test_access_time_is_not_identity(self):
        a=self.path.stat();os.utime(self.path,ns=(a.st_atime_ns+100000,a.st_mtime_ns))
        self.assertEqual(m.pinned(self.path,4,self.digest),b'code')
    def namespace(self):
        root=self.root/'namespace';root.mkdir();(root/'tests').mkdir()
        expected={f'f{i}' for i in range(8)}|{'tests/control.R'}
        for name in expected:(root/name).write_bytes(b'x')
        return root,expected
    def test_exact_nine_file_namespace(self):
        root,expected=self.namespace();m.exact_namespace(root,expected)
    def test_extra_namespace_file_and_directory_refused(self):
        root,expected=self.namespace();extra=root/'unreviewed';extra.write_bytes(b'x')
        with self.assertRaisesRegex(ValueError,'unexpected'):m.exact_namespace(root,expected)
        extra.unlink();extra.mkdir()
        with self.assertRaisesRegex(ValueError,'unexpected'):m.exact_namespace(root,expected)
    def test_missing_namespace_member_refused(self):
        root,expected=self.namespace();(root/'f0').unlink()
        with self.assertRaisesRegex(ValueError,'membership mismatch'):m.exact_namespace(root,expected)
    def test_namespace_link_refused(self):
        root,expected=self.namespace();(root/'f0').unlink();(root/'f0').symlink_to(self.path)
        with self.assertRaisesRegex(ValueError,'linked'):m.exact_namespace(root,expected)
    def composite_source(self):
        root=self.root/'checkout';root.mkdir()
        document={'namespace':'producer','companion_namespace':'companions','field_schema':'schema.json','source_files':{}}
        for key,count in (('namespace',9),('companion_namespace',8)):
            base=root/document[key];base.mkdir()
            for index in range(count):
                path=base/f'f{index}';path.write_bytes(b'x')
                document['source_files'][str(path.relative_to(root))]={'bytes':1,'sha256':hashlib.sha256(b'x').hexdigest()}
        for name in ('COMPARISON.md', 'compare_exports.py', 'tests/comparison_controls.py', 'tests/artifact_custody_controls.py'):
            path=root/'companions'/name;path.parent.mkdir(exist_ok=True)
            path.write_bytes(b'x')
            document['source_files'][str(path.relative_to(root))]={'bytes':1,'sha256':hashlib.sha256(b'x').hexdigest()}
        (root/'schema.json').write_bytes(b'{}')
        document['source_files']['schema.json']={'bytes':2,'sha256':hashlib.sha256(b'{}').hexdigest()}
        return root,document
    def test_composite_exact_nine_plus_twelve_and_schema(self):
        root,document=self.composite_source();m.authenticate_sources(document,root)
        self.assertEqual(len(document['source_files']),22)
        # The previous twenty-one-file closure cannot omit the custody controls.
        previous=json.loads(json.dumps(document))
        del previous['source_files']['companions/tests/artifact_custody_controls.py']
        with self.assertRaisesRegex(ValueError,'cardinality'):m.authenticate_sources(previous,root)
        # Retain the earlier eighteen-file closure rejection as well.
        legacy=json.loads(json.dumps(previous))
        for name in ('COMPARISON.md', 'compare_exports.py', 'tests/comparison_controls.py'):
            del legacy['source_files']['companions/'+name]
        with self.assertRaisesRegex(ValueError,'cardinality'):m.authenticate_sources(legacy,root)
    def test_composite_companion_extra_and_missing_refused(self):
        root,document=self.composite_source();extra=root/'companions'/'extra';extra.write_bytes(b'x')
        with self.assertRaisesRegex(ValueError,'unexpected'):m.authenticate_sources(document,root)
        extra.unlink()
        for name in ('f0', 'COMPARISON.md', 'compare_exports.py', 'tests/comparison_controls.py', 'tests/artifact_custody_controls.py'):
            path=root/'companions'/name;path.unlink()
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'membership mismatch'):
                m.authenticate_sources(document,root)
            path.write_bytes(b'x')
    def test_composite_unlisted_source_and_pin_tamper_refused(self):
        root,document=self.composite_source();document['source_files']['foreign.json']={'bytes':2,'sha256':'0'*64}
        with self.assertRaisesRegex(ValueError,'only twenty-one'):m.authenticate_sources(document,root)
        del document['source_files']['foreign.json']
        for name in ('f0', 'COMPARISON.md', 'compare_exports.py', 'tests/comparison_controls.py', 'tests/artifact_custody_controls.py'):
            path=root/'companions'/name;path.write_bytes(b'y')
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'pin mismatch'):
                m.authenticate_sources(document,root)
            path.write_bytes(b'x')
    def test_composite_commands_mounts_and_distinct_results(self):
        root,document=self.composite_source()
        document.update({'schema':'exp003-generated-r-environment/v3','source_commit':'frozen','namespace_revision':{'source_commit':'generated-extension'},'current_namespace_revision':{'scope':'current source identity only','predecessor_descriptor':{'path':'previous-environment.json','bytes':2,'sha256':hashlib.sha256(b'{}').hexdigest()},'changed_source_files':[],'added_source_files':['companions/tests/artifact_custody_controls.py'],'namespace_member_counts':{'namespace':9,'companion_namespace':12,'field_schema':1},'source_file_count':22},'image':{'identity':'rocker/r-ver@sha256:'+'a'*64,'config_digest':'sha256:'+'b'*64},'jsonlite':{},'parse_expression':'parse-seven-only'})
        descriptor=self.root/'environment.json';raw=json.dumps(document).encode();descriptor.write_bytes(raw)
        archive=self.root/'package.tar.gz';archive.write_bytes(b'not installed')
        output=self.root/'output';captured=[]
        def fake_command(argv,*args,**kwargs):
            if argv[:3]==['docker','image','inspect']:
                return json.dumps([{'Id':'sha256:'+'b'*64,'Os':'linux','Architecture':'arm64'}])
            self.assertEqual(argv[:2],['docker','pull']);return ''
        def fake_container(argv,name,log):
            captured.append(argv)
            if log.name=='parse.log':return '7 R source files parsed; no expressions evaluated.\n'
            if log.name=='generated-controls.log':return 'Generated R collector/parse checks: 219 passed; no estimator called.\n'
            if log.name=='generated-artifact-controls.log':return 'Generated native artifact checks: 237 passed; no estimator called.\n'
            return ''
        with patch.object(m.sys,'argv',['bootstrap',str(descriptor),str(len(raw)),hashlib.sha256(raw).hexdigest(),str(root),str(output)]),patch.object(m.signal,'signal'),patch.object(m,'command',side_effect=fake_command),patch.object(m,'acquire_jsonlite',return_value=archive),patch.object(m,'owned_container',side_effect=fake_container):
            m.main()
        self.assertEqual(len(captured),5)
        for argv in captured[1:]:
            for key,inside in (('namespace','/inputs/nider-primary-producer-v2'),('companion_namespace','/inputs/nider-primary-companions-v1')):
                self.assertIn('type=bind,src='+str(root/document[key])+',dst='+inside+',readonly',argv)
            self.assertEqual(argv[argv.index('--network')+1],'none')
        self.assertEqual(captured[-2][-4:],['Rscript','--vanilla','tests/collector_controls.R','/inputs/nider-primary-producer-v2'])
        self.assertEqual(captured[-1][-4:],['Rscript','--vanilla','tests/artifact_controls.R','/inputs/nider-primary-companions-v1'])
        self.assertEqual(captured[-1][captured[-1].index('--workdir')+1],'/inputs/nider-primary-companions-v1')
        result=json.loads((output/'result.json').read_text())
        self.assertEqual(result['suites'],{'collector':{'checks':219,'skips':0},'native_artifacts':{'checks':237,'skips':0}})
        self.assertEqual(result['parsed_files'],7);self.assertFalse(result['scientific_qualification'])
        self.assertEqual(result['namespace_revision'],document['namespace_revision'])
        self.assertEqual(result['current_namespace_revision'],document['current_namespace_revision'])
        self.assertEqual(result['source_commit'],document['source_commit'])

    def test_response_read_is_extent_plus_one(self):
        response=io.BytesIO(b'abcdef');raw=bytearray();receipt={}
        m.read_dependency_response(response,3,raw,receipt)
        self.assertEqual(raw,b'abcd');self.assertEqual(receipt['body_bytes_read'],4)
    def test_failed_dependency_body_preserved_and_not_installed(self):
        class Response(io.BytesIO):
            code=403
            def geturl(self):return 'https://cran.r-project.org/src/contrib/Archive/jsonlite/jsonlite_1.8.8.tar.gz'
        response=Response(b'failure')
        class Opener:
            def open(self,*a,**kw):return response
        spec={'url':response.geturl(),'bytes':1053028,'sha256':'0'*64}
        with patch.object(m.urllib.request,'build_opener',return_value=Opener()):
            with self.assertRaisesRegex(ValueError,'digest/status'):m.acquire_jsonlite(spec,self.root)
        receipt=json.loads((self.root/'dependency-acquisition.json').read_text())
        self.assertEqual(receipt['body_bytes_read'],7)
        self.assertEqual((self.root/'dependency-response.bin').read_bytes(),b'failure')
        self.assertFalse((self.root/'jsonlite_1.8.8.tar.gz').exists())
    def test_wrong_dependency_url_refused_before_network(self):
        with patch.object(m.urllib.request,'build_opener') as opener:
            with self.assertRaises(ValueError):m.acquire_jsonlite({'url':'https://example.com/a','bytes':1053028},self.root)
        opener.assert_not_called()
    def test_exact_results_and_changed_counts(self):
        parse='7 R source files parsed; no expressions evaluated.\n'
        text='Generated R collector/parse checks: 219 passed; no estimator called.\n'
        artifacts='Generated native artifact checks: 237 passed; no estimator called.\n'
        m.strict_result(parse,text,artifacts)
        for value in (text.replace('219','218'),text+text,text.replace('passed','skipped'),''):
            with self.assertRaisesRegex(ValueError,'count/outcome'):m.strict_result(parse,value,artifacts)
        for value in (artifacts.replace('237','236'),artifacts+artifacts,artifacts.replace('passed','skipped'),'',text):
            with self.assertRaisesRegex(ValueError,'count/outcome'):m.strict_result(parse,text,value)
        with self.assertRaisesRegex(ValueError,'parse'):m.strict_result('4 R source files parsed',text,artifacts)
    def test_subprocess_exit_cannot_be_replaced_by_success_text(self):
        with self.assertRaisesRegex(ValueError,'command failed'):
            m.command([sys.executable,'-I','-S','-B','-c','print("success");raise SystemExit(1)'],self.root/'exit.log')
    def test_burst_output_retention_is_hard_capped(self):
        with self.assertRaisesRegex(ValueError,'log limit'):
            m.command([sys.executable,'-I','-S','-B','-c','import os,time;os.write(1,b"x"*500000);time.sleep(5)'],self.root/'burst.log')
        self.assertEqual((self.root/'burst.log').stat().st_size,m.MAX_LOG)
    def test_owned_command_timeout(self):
        with self.assertRaisesRegex(ValueError,'deadline'):
            m.command([sys.executable,'-I','-S','-B','-c','import time;time.sleep(5)'],self.root/'timeout.log',0.1)
    def test_container_cleanup_runs_after_cancellation(self):
        with patch.object(m,'command',side_effect=InterruptedError('cancelled')),patch.object(m,'cleanup_container') as cleanup:
            with self.assertRaises(InterruptedError):m.owned_container(['never-Docker'],'owned',self.root/'container.log')
        cleanup.assert_called_once_with('owned',self.root/'container.log.cleanup')
    def test_cleanup_refuses_unconfirmed_removal(self):
        with patch.object(m,'command',return_value='daemon unavailable'):
            with self.assertRaisesRegex(ValueError,'not confirmed'):m.cleanup_container('owned',self.root/'cleanup')
    def test_actual_sigterm_reaches_owned_cleanup(self):
        ready=self.root/'ready';marker=self.root/'cleaned';log=self.root/'signal.log'
        code='import importlib.util,pathlib,signal,sys; s=importlib.util.spec_from_file_location("m",sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);signal.signal(signal.SIGTERM,m.cancel);m.cleanup_container=lambda name,log:pathlib.Path(sys.argv[3]).write_text(name);pathlib.Path(sys.argv[2]).write_text("ready");m.owned_container([sys.executable,"-I","-S","-B","-c","import time;time.sleep(10)"],"owned",pathlib.Path(sys.argv[4]))'
        process=subprocess.Popen([sys.executable,'-I','-S','-B','-c',code,str(SOURCE),str(ready),str(marker),str(log)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+3
            while not ready.exists() and process.poll() is None and time.monotonic()<deadline:time.sleep(0.02)
            self.assertTrue(ready.exists());time.sleep(0.05);process.send_signal(signal.SIGTERM)
            process.communicate(timeout=5)
            self.assertNotEqual(process.returncode,0);self.assertEqual(marker.read_text(),'owned')
        finally:
            if process.poll() is None:process.kill();process.communicate()
    def test_first_sigterm_during_normal_cleanup_is_deferred(self):
        ready=self.root/'cleanup-ready';marker=self.root/'cleanup-done'
        code='''import importlib.util,pathlib,signal,sys,time
s=importlib.util.spec_from_file_location("m",sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
signal.signal(signal.SIGTERM,m.cancel)
def fake_command(*args,**kwargs):
 pathlib.Path(sys.argv[2]).write_text("ready")
 time.sleep(.2)
 pathlib.Path(sys.argv[3]).write_text("removed")
 return "owned"
m.command=fake_command
m.cleanup_container("owned",pathlib.Path(sys.argv[4]))
'''
        process=subprocess.Popen([sys.executable,'-I','-S','-B','-c',code,str(SOURCE),str(ready),str(marker),str(self.root/'cleanup.log')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+3
            while not ready.exists() and process.poll() is None and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue(ready.exists());process.send_signal(signal.SIGTERM)
            process.communicate(timeout=5)
            self.assertEqual(marker.read_text(),'removed');self.assertNotEqual(process.returncode,0)
        finally:
            if process.poll() is None:process.kill();process.communicate()
    def test_exited_leader_does_not_leave_stdout_holding_descendant(self):
        ready=self.root/'descendant-ready';marker=self.root/'descendant-stopped'
        child='import pathlib,signal,sys,time;signal.signal(signal.SIGTERM,lambda *a:(pathlib.Path(sys.argv[2]).write_text("stopped"),sys.exit(0)));pathlib.Path(sys.argv[1]).write_text("ready");time.sleep(10)'
        leader='import pathlib,subprocess,sys,time;p=subprocess.Popen([sys.executable,"-I","-S","-B","-c",sys.argv[1],sys.argv[2],sys.argv[3]]);deadline=time.monotonic()+2\nwhile not pathlib.Path(sys.argv[2]).exists() and time.monotonic()<deadline:time.sleep(.01)\nprint("leader finished",flush=True)'
        created=[];original=subprocess.Popen
        def recorded(*args,**kwargs):
            process=original(*args,**kwargs);created.append(process);return process
        try:
            with patch.object(m.subprocess,'Popen',side_effect=recorded):
                with self.assertRaisesRegex(ValueError,'deadline'):
                    m.command([sys.executable,'-I','-S','-B','-c',leader,child,str(ready),str(marker)],self.root/'descendant.log',1)
            deadline=time.monotonic()+2
            while not marker.exists() and time.monotonic()<deadline:time.sleep(.02)
            self.assertEqual(marker.read_text(),'stopped')
        finally:
            for process in created:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
    def test_first_sigterm_during_group_cleanup_defers_escalation_and_close(self):
        ready=self.root/'group-ready';marker=self.root/'group-closed';trace=self.root/'group-signals'
        code='''import importlib.util,pathlib,signal,sys,time
s=importlib.util.spec_from_file_location("m",sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
signal.signal(signal.SIGTERM,m.cancel)
def fake_killpg(pid,sig):
 with pathlib.Path(sys.argv[4]).open("a") as f:f.write(str(sig)+"\\n")
m.os.killpg=fake_killpg
class Stream:
 def close(self):pathlib.Path(sys.argv[3]).write_text("closed")
class Process:
 pid=12345
 stdout=Stream()
 waits=0
 def wait(self,timeout):
  self.waits+=1
  if self.waits==1:
   pathlib.Path(sys.argv[2]).write_text("ready")
   time.sleep(.2)
  return 0
m.cleanup_group(Process(),False)
'''
        process=subprocess.Popen([sys.executable,'-I','-S','-B','-c',code,str(SOURCE),str(ready),str(marker),str(trace)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+3
            while not ready.exists() and process.poll() is None and time.monotonic()<deadline:time.sleep(.02)
            self.assertTrue(ready.exists());process.send_signal(signal.SIGTERM)
            process.communicate(timeout=5)
            self.assertEqual(marker.read_text(),'closed')
            self.assertEqual(trace.read_text().splitlines(),[str(signal.SIGTERM),str(signal.SIGKILL)])
            self.assertNotEqual(process.returncode,0)
        finally:
            if process.poll() is None:process.kill();process.communicate()


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Controls)
    if suite.countTestCases()!=28:
        raise SystemExit('Expected exactly 28 EXP003 bootstrap controls')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print('Temporary logical artifact bytes before cleanup:',TRANSIENT_LOGICAL_BYTES)
    raise SystemExit(0 if result.testsRun==28 and result.wasSuccessful()
                     and not result.skipped and not result.expectedFailures else 1)
