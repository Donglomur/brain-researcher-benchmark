"""Generated launcher controls; never import a benchmark implementation."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import signal
from unittest.mock import patch
import urllib.error
import tempfile
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('parallel_controls',ROOT/'scripts/maintenance/run_parallel_source_controls.py')
launcher=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class SummaryControls(unittest.TestCase):
    def test_exact_json_controls_and_boolean_types(self):
        expected={'controls':[{'fixture':0,'equal':True}],'authentic_data_reads':0}
        self.assertEqual(launcher.result_summary(json.dumps(expected),'json-controls',1,expected)['tests'],1)
        for actual in ({**expected,'authentic_data_reads':False},
                       {**expected,'controls':[{'fixture':0,'equal':False}]},
                       {**expected,'controls':[]}, {**expected,'extra':'unreviewed'}):
            with self.subTest(actual=actual),self.assertRaises(ValueError):
                launcher.result_summary(json.dumps(actual),'json-controls',1,expected)

    def test_unittest_exact_count(self):
        self.assertEqual(launcher.result_summary('Ran 2 tests in 0.001s\n\nOK\n','unittest',2)['tests'],2)

    def test_zero_missing_and_changed_counts_refused(self):
        for text in ('OK\n','Ran 0 tests in 0s\nOK\n','Ran 3 tests in 0s\nOK\n'):
            with self.subTest(text=text),self.assertRaises(ValueError):
                launcher.result_summary(text,'unittest',2)

    def test_unittest_skips_and_failures_refused(self):
        for status in ('OK (skipped=1)','FAILED (failures=1)','OK\nOK'):
            with self.subTest(status=status),self.assertRaises(ValueError):
                launcher.result_summary('Ran 2 tests in 0s\n'+status+'\n','unittest',2)

    def test_expected_mutant_failure_does_not_replace_final_suite(self):
        text='Ran 1 test in 0s\nFAILED (failures=1)\nRan 2 tests in 0s\nOK\n'
        self.assertEqual(launcher.result_summary(text,'unittest',2)['tests'],2)

    def test_pytest_exact_summary_and_warnings(self):
        self.assertEqual(launcher.result_summary('=== 3 passed, 1 warning in 0.1s ===\n','pytest',3)['tests'],3)

    def test_pytest_skips_xfails_deselection_refused(self):
        for detail in ('1 skipped','1 xfailed','1 xpassed','1 deselected','1 failed','1 error'):
            with self.subTest(detail=detail),self.assertRaises(ValueError):
                launcher.result_summary('3 passed, '+detail+' in 0.1s\n','pytest',3)

    def test_pytest_later_skip_only_summary_cannot_reuse_prior_pass(self):
        for ending in ('3 skipped in 0.1s','1 error in 0.1s','no tests ran in 0.1s'):
            with self.subTest(ending=ending),self.assertRaises(ValueError):
                launcher.result_summary('3 passed in 0.1s\n'+ending+'\n','pytest',3)
        self.assertEqual(launcher.result_summary('1 failed in 0.1s\n3 passed in 0.1s\n','pytest',3)['tests'],3)


class ProcessControls(unittest.TestCase):
    def test_process_exit_is_required_despite_passing_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'process exit 4'):
                launcher.run_command([sys.executable,'-I','-S','-c',
                    'print("Ran 1 test in 0s\\nOK"); raise SystemExit(4)'],Path(tmp),dict(os.environ),Path(tmp)/'log',5)

    def test_timeout_stops_only_owned_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'wall timeout'):
                launcher.run_command([sys.executable,'-I','-S','-c','import time; time.sleep(10)'],
                    Path(tmp),dict(os.environ),Path(tmp)/'log',1)

    def test_log_limit_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            original=launcher.MAX_LOG_BYTES;launcher.MAX_LOG_BYTES=64
            try:
                with self.assertRaisesRegex(ValueError,'log byte limit'):
                    launcher.run_command([sys.executable,'-I','-S','-c','print("x"*1024)'],
                        Path(tmp),dict(os.environ),Path(tmp)/'log',5)
            finally: launcher.MAX_LOG_BYTES=original


class ManifestControls(unittest.TestCase):
    def test_command_capacity_656_accepts_and_657_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,_,document=self.fixture(root)
            template=document['commands'][0]
            document['commands']=[{**template,'id':'control%d'%index} for index in range(656)]
            _,selected=launcher.validate_document(document,'stdlib')
            self.assertEqual(selected,document['commands'])
            self.assertEqual(len(selected),656)
            document['commands'].append({**template,'id':'control656','group':'other'})
            with self.assertRaisesRegex(ValueError,'bounded command list required'):
                launcher.validate_document(document,'stdlib')

    def test_exact_fixture_directory_membership(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);directory=root/'author';directory.mkdir()
            (directory/'one.py').write_bytes(b'one')
            document={'fixtures':{'one':{'filename':'author/one.py','bytes':3,
                'sha256':hashlib.sha256(b'one').hexdigest()}},
                'fixture_directories':{'author':{'path':'author','members':['one']}}}
            rows=[{'argv':['${PYTHON}','${FIXTURE_DIR:author}'],'fixtures':['one']}]
            self.assertEqual(launcher.bind_fixtures(document,rows,root)['${FIXTURE_DIR:author}'],str(directory.resolve()))
            (directory/'extra.py').write_bytes(b'not authorized')
            with self.assertRaisesRegex(ValueError,'membership mismatch'):
                launcher.bind_fixtures(document,rows,root)

    def test_read_time_change_does_not_imply_content_change(self):
        raw=b'{"key": 1}'
        class GeneratedPath:
            read=False
            def stat(self):
                return SimpleNamespace(st_dev=1,st_ino=2,st_mode=0o100644,st_nlink=1,
                    st_size=len(raw),st_mtime_ns=100,st_ctime_ns=100,st_atime_ns=200 if self.read else 100)
            def open(self,mode):self.read=True;return io.BytesIO(raw)
        self.assertEqual(launcher.bounded_json(GeneratedPath()),{'key':1})
        self.assertEqual(launcher.pinned_read(GeneratedPath(),{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}),raw)

    def test_growth_during_read_is_bounded_before_refusal(self):
        requested=[]
        class BoundedStream(io.BytesIO):
            def read(self,size=-1):requested.append(size);return super().read(size)
        class GeneratedPath:
            def stat(self):
                return SimpleNamespace(st_dev=1,st_ino=2,st_mode=0o100644,st_nlink=1,
                    st_size=10,st_mtime_ns=100,st_ctime_ns=100)
            def open(self,mode):return BoundedStream(b'x'*10000)
        with self.assertRaises(ValueError):launcher.bounded_json(GeneratedPath())
        with self.assertRaises(ValueError):launcher.pinned_read(GeneratedPath(),{'bytes':10,'sha256':'0'*64})
        self.assertEqual(requested,[11,11])

    def fixture(self,root):
        source=root/'benchmarks/neural/TEST/implementations/control/test_control.py'
        source.parent.mkdir(parents=True)
        source.write_text('import unittest\nclass Checks(unittest.TestCase):\n def test_one(self): self.assertEqual(1+1,2)\nif __name__=="__main__": unittest.main()\n')
        path=source.relative_to(root).as_posix();raw=source.read_bytes()
        inventory=root/'benchmarks/integrity/source-ownership.json';inventory.parent.mkdir()
        inventory.write_text(json.dumps({'files':[{'path':path,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}]}))
        document={'schema':'parallel-source-controls/v1','groups':{'stdlib':{'python':sys.version.split()[0],'packages':{}}},
          'fixtures':{},'commands':[{'id':'one','task_id':'TEST','group':'stdlib','runner':'unittest',
          'expected_tests':1,'expected_skips':0,'argv':['${PYTHON}','-I','-B',path],
          'cwd':'.','test_paths':[path],'timeout_seconds':5}]}
        manifest=root/'manifest.json';manifest.write_text(json.dumps(document))
        return source,manifest,document

    def test_complete_owned_source_control(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=base/'repo';root.mkdir()
            _,manifest,_=self.fixture(root)
            result=launcher.run(root,manifest,'stdlib',base/'results')
            self.assertEqual((result[0]['tests'],result[0]['skips']),(1,0))

    def test_python_token_binds_nested_argument_and_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=base/'repo';root.mkdir()
            source,manifest,document=self.fixture(root)
            source.write_text('import argparse, os, sys, unittest\nfrom pathlib import Path\n'
                'parser=argparse.ArgumentParser()\nparser.add_argument("--python",required=True)\n'
                'args=parser.parse_args()\nclass Checks(unittest.TestCase):\n'
                ' def test_selected_interpreter(self):\n'
                '  selected=Path(args.python).resolve(strict=True)\n'
                '  self.assertEqual(selected,Path(sys.executable).resolve(strict=True))\n'
                '  self.assertEqual(os.environ["CONTROL_PYTHON"],args.python)\n'
                'if __name__=="__main__": unittest.main(argv=[sys.argv[0]])\n')
            raw=source.read_bytes();path=source.relative_to(root).as_posix()
            (root/'benchmarks/integrity/source-ownership.json').write_text(json.dumps({'files':[
                {'path':path,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}]}))
            document['commands'][0]['argv'] += ['--python','${PYTHON}']
            document['commands'][0]['environment']={'CONTROL_PYTHON':'${PYTHON}'}
            manifest.write_text(json.dumps(document))
            result=launcher.run(root,manifest,'stdlib',base/'results')
            self.assertEqual((result[0]['tests'],result[0]['skips']),(1,0))
            document['commands'][0]['argv'][-1]='prefix-${PYTHON}'
            manifest.write_text(json.dumps(document))
            with patch.object(launcher,'run_command') as execute,self.assertRaisesRegex(
                    ValueError,'unresolved command placeholder'):
                launcher.run(root,manifest,'stdlib',base/'refused-results')
            execute.assert_not_called()
            self.assertFalse((base/'refused-results').exists())

    def test_meg_whole_artifact_token_materializes_owned_nested_output_and_logs(self):
        # Exercise the actual maintained runtime handler and the actual manifest
        # bootstrap. A tiny generated unittest driver replaces scientific work.
        public=json.loads((ROOT/'benchmarks/integrity/parallel-source-controls.v1.json').read_text())
        production=next(row for row in public['commands']
                        if row['id']=='PAPER-paper-method-add-010.command-09')
        self.assertEqual(production['argv'][-1],'${ARTIFACT_DIR}')
        self.assertEqual(production['argv'][4],'-c')
        driver_path=production['argv'][-2]
        self.assertTrue(driver_path.endswith('/tests_generic_classification/run_controls.py'))
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=base/'repo';root.mkdir()
            _,manifest,document=self.fixture(root)
            source=root/driver_path;source.parent.mkdir(parents=True)
            source.write_text('import argparse,json,stat,sys,unittest\nfrom pathlib import Path\n'
                'p=argparse.ArgumentParser();p.add_argument("--output",required=True)\n'
                'args=p.parse_args();out=Path(args.output).resolve()\n'
                'if out.exists() or not out.parent.is_dir(): raise ValueError("fresh nested output required")\n'
                'with out.with_suffix(".log").open("x") as f: f.write("GENERATED DRIVER LOG\\n")\n'
                'out.mkdir(mode=0o700)\n'
                '(out/"CONTROL_RESULT.json").write_text(json.dumps({"generated_artifact_abi_only":True}))\n'
                'class GeneratedPathCheck(unittest.TestCase):\n'
                ' def test_owned_paths(self):\n'
                '  self.assertEqual(out.name,"meg-generic-classification")\n'
                '  self.assertEqual(out.parent.name,"PAPER-paper-method-add-010.command-09.artifacts")\n'
                '  self.assertEqual(stat.S_IMODE(out.parent.stat().st_mode),0o700)\n'
                'if __name__=="__main__": unittest.main(argv=[sys.argv[0]])\n')
            raw=source.read_bytes()
            (root/'benchmarks/integrity/source-ownership.json').write_text(json.dumps({'files':[
                {'path':driver_path,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}]}))
            selected={**production,'group':'stdlib','expected_tests':1,'timeout_seconds':5,
                      'test_paths':[driver_path]}
            document['commands']=[selected]
            manifest.write_text(json.dumps(document))
            result=launcher.run(root,manifest,'stdlib',base/'results')
            artifact=base/'results'/(selected['id']+'.artifacts')
            nested=artifact/'meg-generic-classification'
            outer_log=base/'results'/(selected['id']+'.log')
            self.assertEqual(result[0]['artifact_directory'],artifact.name)
            self.assertEqual((result[0]['tests'],result[0]['skips']),(1,0))
            self.assertEqual(json.loads((nested/'CONTROL_RESULT.json').read_text()),
                             {'generated_artifact_abi_only':True})
            self.assertEqual((artifact/'meg-generic-classification.log').read_text(),
                             'GENERATED DRIVER LOG\n')
            self.assertIn('Ran 1 test',outer_log.read_text())
            self.assertNotEqual(outer_log,(artifact/'meg-generic-classification.log'))
            with patch.object(launcher,'run_command') as execute,self.assertRaisesRegex(
                    ValueError,'fresh output directory required'):
                launcher.run(root,manifest,'stdlib',base/'results')
            execute.assert_not_called()
            selected['argv']=['${PYTHON}','-I','-S','-B',driver_path,'--output',
                              '${ARTIFACT_DIR}/meg-generic-classification']
            manifest.write_text(json.dumps(document))
            with patch.object(launcher,'run_command') as execute,self.assertRaisesRegex(
                    ValueError,'unresolved command placeholder'):
                launcher.run(root,manifest,'stdlib',base/'legacy-refused')
            execute.assert_not_called()
            self.assertFalse((base/'legacy-refused').exists())

    def test_mixed_stream_mutant_summary_keeps_actual_order_under_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=base/'repo';root.mkdir()
            source,manifest,_=self.fixture(root)
            source.write_text('print("Ran 2 tests in 0s\\nFAILED (failures=1)")\n'+source.read_text())
            raw=source.read_bytes();path=source.relative_to(root).as_posix()
            (root/'benchmarks/integrity/source-ownership.json').write_text(json.dumps({'files':[
                {'path':path,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}]}))
            result=launcher.run(root,manifest,'stdlib',base/'results')
            self.assertEqual(result[0]['tests'],1)

    def test_changed_source_fails_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=base/'repo';root.mkdir()
            source,manifest,_=self.fixture(root);source.write_text('raise AssertionError("must not execute")')
            with self.assertRaisesRegex(ValueError,'source (size|pin) mismatch'):
                launcher.run(root,manifest,'stdlib',base/'results')
            self.assertFalse((base/'results').exists())

    def test_missing_fixture_fails_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=base/'repo';root.mkdir()
            _,manifest,document=self.fixture(root)
            document['commands'][0]['fixtures']=['author-source'];manifest.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError,'required source fixture unavailable'):
                launcher.run(root,manifest,'stdlib',base/'results')

    def test_path_escape_and_link_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'outside').write_text('x');(root/'linked').symlink_to(root/'outside')
            for value in ('../outside','/tmp/file','a/../outside','linked'):
                with self.subTest(value=value),self.assertRaises(ValueError):launcher.local(root,value)

    def test_zero_skips_required_in_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,_,document=self.fixture(root)
            document['commands'][0]['expected_skips']=1
            with self.assertRaisesRegex(ValueError,'may not skip'):launcher.validate_document(document,'stdlib')

    def test_duplicate_ids_and_empty_groups_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,_,document=self.fixture(root)
            document['commands']*=2
            with self.assertRaisesRegex(ValueError,'unique command'):launcher.validate_document(document,'stdlib')
            document['commands']=document['commands'][:1]
            document['commands'][0]['group']='other'
            with self.assertRaisesRegex(ValueError,'empty environment'):launcher.validate_document(document,'stdlib')

    def test_environment_cannot_override_thread_or_import_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,_,document=self.fixture(root)
            for name in ('OPENBLAS_NUM_THREADS','PYTHONPATH','PYTEST_ADDOPTS'):
                document['commands'][0]['environment']={name:'unsafe'}
                with self.subTest(name=name),self.assertRaisesRegex(ValueError,'enforced invariant'):
                    launcher.validate_document(document,'stdlib')


class AggregateControls(unittest.TestCase):
    PASS='import unittest\nclass Checks(unittest.TestCase):\n def test_one(self): self.assertTrue(True)\nif __name__=="__main__": unittest.main()\n'
    SKIP='import unittest\nclass Checks(unittest.TestCase):\n @unittest.skip("generated skipped control")\n def test_one(self): pass\nif __name__=="__main__": unittest.main()\n'

    def fixture(self,root,programs,counts=None):
        source,manifest,document=ManifestControls.fixture(self,root)
        template=document['commands'][0]
        commands=[];pins=[]
        for index,program in enumerate(programs):
            path=source.with_name('control%d.py'%index);path.write_text(program)
            relative=path.relative_to(root).as_posix();raw=path.read_bytes()
            pins.append({'path':relative,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
            commands.append({**template,'id':'control%d'%index,'test_paths':[relative],
                'argv':['${PYTHON}','-I','-S','-B',relative],
                'expected_tests':counts[index] if counts else 1})
        document['commands']=commands
        manifest.write_text(json.dumps(document))
        inventory=root/'benchmarks/integrity/source-ownership.json'
        inventory.write_text(json.dumps({'files':pins}))
        return manifest,document,inventory

    def test_failed_then_passed_then_skipped_are_all_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=base/'repo';root.mkdir()
            manifest,_,_=self.fixture(root,['raise SystemExit(4)\n',self.PASS,self.SKIP])
            output=base/'results'
            with self.assertRaisesRegex(ValueError,'2 of 3 authenticated commands failed'):
                launcher.run(root,manifest,'stdlib',output)
            result=json.loads((output/'results.json').read_text())
            self.assertEqual((result['status'],result['attempted']),('failed',3))
            self.assertEqual([r['id'] for r in result['completed']],['control1'])
            self.assertEqual([r['id'] for r in result['failed']],['control0','control2'])
            self.assertIn('process exit 4',result['failed'][0]['error'])
            self.assertIn('skipped',result['failed'][1]['error'])
            self.assertEqual(len(list(output.glob('*.log'))),3)

    def test_count_mismatch_is_retained_and_later_control_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=base/'repo';root.mkdir()
            manifest,_,_=self.fixture(root,[self.PASS,self.PASS],[2,1])
            output=base/'results'
            with self.assertRaisesRegex(ValueError,'1 of 2 authenticated commands failed'):
                launcher.run(root,manifest,'stdlib',output)
            result=json.loads((output/'results.json').read_text())
            self.assertEqual(result['attempted'],2)
            self.assertIn('test count mismatch',result['failed'][0]['error'])
            self.assertEqual(result['completed'][0]['id'],'control1')

    def test_later_bad_pin_prevents_every_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=base/'repo';root.mkdir()
            manifest,_,inventory=self.fixture(root,[self.PASS,self.PASS])
            pins=json.loads(inventory.read_text());pins['files'][1]['sha256']='0'*64
            inventory.write_text(json.dumps(pins));output=base/'results'
            with patch.object(launcher,'run_command') as execute,self.assertRaisesRegex(ValueError,'source pin mismatch'):
                launcher.run(root,manifest,'stdlib',output)
            execute.assert_not_called();self.assertFalse(output.exists())

    def test_later_missing_cwd_prevents_every_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root=base/'repo';root.mkdir()
            manifest,document,_=self.fixture(root,[self.PASS,self.PASS])
            document['commands'][1]['cwd']='missing';manifest.write_text(json.dumps(document))
            output=base/'results'
            with patch.object(launcher,'run_command') as execute,self.assertRaisesRegex(ValueError,'missing control path'):
                launcher.run(root,manifest,'stdlib',output)
            execute.assert_not_called();self.assertFalse(output.exists())

    def test_unexpected_run_or_cleanup_errors_stay_fatal(self):
        for error in (OSError('generated infrastructure failure'),ValueError('generated cleanup failure')):
            with self.subTest(error=type(error).__name__),tempfile.TemporaryDirectory() as tmp:
                base=Path(tmp);root=base/'repo';root.mkdir()
                manifest,_,_=self.fixture(root,[self.PASS,self.PASS]);output=base/'results'
                with patch.object(launcher,'run_command',side_effect=error) as execute,self.assertRaises(type(error)):
                    launcher.run(root,manifest,'stdlib',output)
                self.assertEqual(execute.call_count,1)
                self.assertFalse((output/'results.json').exists())


class Response:
    def __init__(self,body=b'code',url='https://raw.githubusercontent.com/a/b/abc/source.py',code=200,headers=None):
        self.stream=io.BytesIO(body)
        self.code=code
        self.url=url
        self.headers=headers or {}
        self.read_sizes=[]
        self.closed=False
    def read1(self,amount):
        self.read_sizes.append(amount)
        return self.stream.read(amount)
    def geturl(self):return self.url
    def close(self):self.closed=True


class Opener:
    def __init__(self,responses):self.responses=list(responses);self.requests=[]
    def open(self,request,timeout):
        self.requests.append((request,timeout))
        response=self.responses.pop(0)
        if isinstance(response,BaseException):raise response
        return response


class FixtureControls(unittest.TestCase):
    def test_command_capacity_656_without_fixtures_and_657_refuses(self):
        self.document={'fixtures':{},'commands':[{'group':'stdlib','fixtures':[]} for _ in range(656)]}
        result,opener,_=self.run_fetch([])
        self.assertEqual(result['status'],'succeeded')
        self.assertEqual(result['response_bytes_read'],0)
        self.assertEqual(result['files'],[])
        self.assertEqual(opener.requests,[])
        self.assertEqual(self.receipt(),result)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
        self.dest=self.base/'excess'
        self.document['commands'].append({'group':'other','fixtures':[]})
        with patch.object(launcher.urllib.request,'build_opener') as builder:
            with self.assertRaisesRegex(ValueError,'bounded fixture commands required'):
                launcher.prepare_fixtures(self.root,self.document,'stdlib',self.dest)
        builder.assert_not_called()
        self.assertFalse(self.dest.exists())

    def test_exact_physionet_object_address_only(self):
        address='https://physionet-open.s3.amazonaws.com/chbmit/1.0.0/RECORDS'
        self.document['fixtures']['source']['url']=address
        result,opener,_=self.run_fetch([Response(url=address)])
        self.assertEqual(result['files'][0]['fetched_url'],address)
        self.assertEqual(len(opener.requests),1)
        for refused in (address+'?download=1',address+'#fragment',address+'/',
                        address.replace('RECORDS','OTHER'),address.replace('/1.0.0/','/1.0.1/'),
                        address.replace('https://','http://'),
                        address.replace('https://','https://user:secret@'),
                        address.replace('.com/','.com:443/'),
                        address.replace('physionet-open.','another-bucket.')):
            with self.subTest(url=refused),self.assertRaises(ValueError):
                launcher._url(refused)

    def test_physionet_cross_host_redirect_still_refused(self):
        origin='https://physionet.org/files/chbmit/1.0.0/RECORDS'
        address='https://physionet-open.s3.amazonaws.com/chbmit/1.0.0/RECORDS'
        self.document['fixtures']['source']['url']=origin
        response=Response(b'',url=origin,code=302,headers={'Location':address})
        with self.assertRaisesRegex(ValueError,'cross-host fixture redirect refused'):
            self.run_fetch([response])
        self.assertEqual(self.receipt()['response_bytes_read'],0)
        self.assertFalse((self.dest/'author/source.py').exists())

    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.base=Path(self.temporary.name).resolve()
        self.root=self.base/'checkout';self.root.mkdir()
        self.dest=self.base/'fixtures'
        self.document={'fixtures':{'source':{'url':'https://raw.githubusercontent.com/a/b/abc/source.py',
            'filename':'author/source.py','bytes':4,'sha256':hashlib.sha256(b'code').hexdigest()}},
            'commands':[{'group':'stdlib','fixtures':['source']}]}
    def tearDown(self):self.temporary.cleanup()
    def run_fetch(self,responses):
        opener=Opener(responses)
        with patch.object(launcher.urllib.request,'build_opener',return_value=opener) as builder:
            result=launcher.prepare_fixtures(self.root,self.document,'stdlib',self.dest)
        return result,opener,builder
    def receipt(self):return json.loads((self.dest/'acquisition-receipt.json').read_text())
    def test_exact_public_source_and_no_proxy_credentials(self):
        response=Response()
        result,opener,builder=self.run_fetch([response])
        self.assertEqual((self.dest/'author/source.py').read_bytes(),b'code')
        self.assertEqual(result['response_bytes_read'],4)
        self.assertEqual(result['status'],'succeeded')
        self.assertFalse(result['scientific_qualification'])
        self.assertEqual(builder.call_args.args[0].proxies,{})
        self.assertEqual(len(opener.requests),1)
        self.assertLessEqual(opener.requests[0][1],20)
        self.assertTrue(response.closed)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
    def test_digest_mismatch_preserves_failed_response_accounting(self):
        response=Response(b'evil')
        with self.assertRaisesRegex(ValueError,'digest mismatch'):self.run_fetch([response])
        receipt=self.receipt()
        self.assertEqual(receipt['status'],'failed')
        self.assertEqual(receipt['response_bytes_read'],4)
        self.assertEqual(receipt['responses'][0]['body_sha256'],hashlib.sha256(b'evil').hexdigest())
        self.assertFalse((self.dest/'author/source.py').exists())
    def test_overlength_read_stops_at_one_byte_sentinel(self):
        response=Response(b'codeMORE')
        with self.assertRaisesRegex(ValueError,'digest mismatch'):self.run_fetch([response])
        self.assertEqual(self.receipt()['response_bytes_read'],5)
        self.assertEqual(response.read_sizes,[5])
        self.assertFalse((self.dest/'author/source.py').exists())
    def test_http_error_body_is_counted_and_no_retry(self):
        fp=Response(b'bad')
        error=urllib.error.HTTPError(self.document['fixtures']['source']['url'],404,'missing',{},fp)
        with self.assertRaisesRegex(ValueError,'HTTP response failed'):self.run_fetch([error])
        record=self.receipt()['responses'][0]
        self.assertEqual(record['status'],404)
        self.assertEqual(record['bytes_read'],3)
        self.assertEqual(record['body_sha256'],hashlib.sha256(b'bad').hexdigest())
    def test_same_host_redirect_is_bound_and_charged(self):
        first=Response(b'go',code=302,headers={'Location':'/a/b/def/source.py'})
        final=Response(url='https://raw.githubusercontent.com/a/b/def/source.py')
        result,opener,_=self.run_fetch([first,final])
        self.assertEqual(result['response_bytes_read'],6)
        self.assertEqual(len(opener.requests),2)
        self.assertEqual(result['files'][0]['fetched_url'],final.url)
    def test_cross_host_redirect_fails_without_following(self):
        first=Response(b'go',code=302,headers={'Location':'https://physionet.org/files/other'})
        with self.assertRaisesRegex(ValueError,'cross-host'):self.run_fetch([first])
        self.assertEqual(len(self.receipt()['responses']),1)
        self.assertEqual(self.receipt()['response_bytes_read'],2)
    def test_implicit_redirect_is_refused(self):
        with self.assertRaisesRegex(ValueError,'implicit redirect'):
            self.run_fetch([Response(url='https://raw.githubusercontent.com/a/b/def/source.py')])
        self.assertEqual(self.receipt()['response_bytes_read'],0)
    def test_redirect_loop_is_bounded(self):
        responses=[Response(b'x',code=302,headers={'Location':'/a/b/abc/source.py'}) for _ in range(4)]
        with self.assertRaisesRegex(ValueError,'redirect limit'):self.run_fetch(responses)
        self.assertEqual(len(self.receipt()['responses']),4)
        self.assertEqual(self.receipt()['response_bytes_read'],4)
    def test_bad_urls_are_rejected_before_network(self):
        for url in ('http://raw.githubusercontent.com/a','https://user:secret@raw.githubusercontent.com/a',
                    'https://raw.githubusercontent.com.evil.test/a','https://127.0.0.1/a',
                    'https://raw.githubusercontent.com:443/a','https://raw.githubusercontent.com/a#b'):
            with self.subTest(url=url):
                self.document['fixtures']['source']['url']=url
                with patch.object(launcher.urllib.request,'build_opener') as builder:
                    with self.assertRaises(ValueError):launcher.prepare_fixtures(self.root,self.document,'stdlib',self.dest)
                builder.assert_not_called()
                self.assertFalse(self.dest.exists())
    def test_bad_paths_and_symlink_destination_are_rejected(self):
        for name in ('../escape','/absolute','a//b','a/./b','a\\b','.'):
            self.document['fixtures']['source']['filename']=name
            with self.assertRaises(ValueError):self.run_fetch([])
        self.document['fixtures']['source']['filename']='author/source.py'
        self.dest.symlink_to(self.base/'other')
        with self.assertRaisesRegex(ValueError,'fresh'):self.run_fetch([])
    def test_checkout_or_existing_destination_is_rejected(self):
        self.dest=self.root/'fixtures'
        with self.assertRaisesRegex(ValueError,'outside'):self.run_fetch([])
        self.dest=self.base/'fixtures';self.dest.mkdir()
        with self.assertRaisesRegex(ValueError,'fresh'):self.run_fetch([])
    def test_selected_group_only_fetches_required_files(self):
        self.document['fixtures']['other']={'url':'https://physionet.org/files/a',
            'filename':'other','bytes':3,'sha256':hashlib.sha256(b'xyz').hexdigest()}
        self.document['commands'].append({'group':'other','fixtures':['other']})
        result,opener,_=self.run_fetch([Response()])
        self.assertEqual(len(opener.requests),1)
        self.assertEqual([r['id'] for r in result['files']],['source'])
    def test_count_and_byte_limits_refuse_before_network(self):
        self.document['fixtures']['source']['bytes']=launcher.MAX_FIXTURE_BYTES
        with self.assertRaisesRegex(ValueError,'byte limit'):self.run_fetch([])
        self.document['fixtures']['source']['bytes']=4
        self.document['fixtures'].update({str(i):{} for i in range(64)})
        with self.assertRaisesRegex(ValueError,'file limit'):self.run_fetch([])
    def test_receipt_namespace_cannot_be_used_as_directory(self):
        self.document['fixtures']['source']['filename']='acquisition-receipt.json/source.py'
        with self.assertRaisesRegex(ValueError,'reserved'):self.run_fetch([])
        self.assertFalse(self.dest.exists())
    def test_timeout_restores_alarm_and_records_failure(self):
        with patch.object(launcher,'_read_response',side_effect=TimeoutError('wall deadline')):
            with self.assertRaisesRegex(TimeoutError,'wall deadline'):self.run_fetch([Response()])
        self.assertEqual(self.receipt()['status'],'failed')
        self.assertEqual(self.receipt()['response_bytes_read'],0)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
    def test_partial_read_before_error_is_counted(self):
        response=Response()
        calls=iter([b'co',TimeoutError('read stopped')])
        def read1(amount):
            value=next(calls)
            if isinstance(value,BaseException):raise value
            return value
        response.read1=read1
        with self.assertRaises(TimeoutError):self.run_fetch([response])
        record=self.receipt()['responses'][0]
        self.assertEqual(record['bytes_read'],2)
        self.assertEqual(record['body_sha256'],hashlib.sha256(b'co').hexdigest())
    def test_global_acquisition_cap_includes_redirect_body(self):
        with patch.object(launcher,'MAX_FIXTURE_BYTES',6):
            with self.assertRaisesRegex(ValueError,'sentinel headroom'):
                self.run_fetch([Response(b'go',code=302,headers={'Location':'/a/b/def/source.py'}),
                                Response(url='https://raw.githubusercontent.com/a/b/def/source.py')])
        self.assertEqual(self.receipt()['response_bytes_read'],6)



if __name__=='__main__':unittest.main()
