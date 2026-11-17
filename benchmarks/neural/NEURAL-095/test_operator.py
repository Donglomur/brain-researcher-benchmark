"""Generated current-route controls. Never launch a selected backend or data job.

Run after integrating adjacent operator.py/current-operator-routes.v1.json.
This proposal supplies tests; it does not claim their execution or passage.
"""
import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch

PACKAGE=Path(__file__).resolve().parent
SOURCE_ROOT=PACKAGE.parents[2]
HOME=Path('benchmarks/neural/NEURAL-095')


class SelectedRouteControls(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='dmfc-route-',dir=Path('/tmp').resolve()))
        self.task=self.root/HOME;self.task.mkdir(parents=True)
        self.route=json.loads((PACKAGE/'current-operator-routes.v1.json').read_bytes())
        for selected in self.route['conditions'].values():
            for name in selected['source_closure']:
                relative=Path(selected['source_directory'])/name
                destination=self.root/relative;destination.parent.mkdir(parents=True,exist_ok=True)
                destination.write_bytes((SOURCE_ROOT/relative).read_bytes())
        for name in ('operator.py','current-operator-routes.v1.json'):
            (self.task/name).write_bytes((PACKAGE/name).read_bytes())
        self.module=types.ModuleType('_generated_dmfc_current_route')
        self.module.__file__=str(self.task/'operator.py')
        exec(compile((self.task/'operator.py').read_bytes(),self.module.__file__,'exec'),self.module.__dict__)
        self.assertEqual(self.module.ROOT,self.root)

    def tearDown(self):
        shutil.rmtree(self.root)

    def selected(self,condition,stage,args):
        with patch.object(self.module.os,'execv',side_effect=RuntimeError('captured-dispatch')) as execute:
            with self.assertRaisesRegex(RuntimeError,'captured-dispatch'):
                self.module.main(['--condition',condition,'--stage',stage,'--',*args])
        self.assertEqual(execute.call_count,1)
        executable,argv=execute.call_args.args
        self.assertEqual(executable,self.module.sys.executable)
        self.assertEqual(argv[:3],[executable,'-I','-B'])
        return argv

    def test_owner_configure_uses_exact_accepted_entrypoint(self):
        args=['--operator','operator.json','--destination','/srv/dmfc-v2']
        argv=self.selected('stateful_case_investigator/v2','configure',args)
        self.assertEqual(argv[3:], [str(self.task/'implementations/adaptive-owner-v2/configure.py'),*args])

    def test_owner_admit_preserves_existing_request_and_dry_run_arguments(self):
        args=['--root','/srv/dmfc-v2','--deployment-sha256','a'*64,'run',
              '--configuration','/srv/dmfc-v2/config.json','--configuration-sha256','b'*64,'--dry-run']
        argv=self.selected('stateful_case_investigator/v2','admit',args)
        self.assertEqual(argv[3:],[str(self.task/'implementations/adaptive-owner-v2/admit.py'),*args])

    def test_all_viewer_stages_select_fixed_command_prefix(self):
        sessions=[]
        for view in ('cue_only','neural'):
            path=self.root/('session-'+view);path.mkdir()
            (path/'BOUNDARY.json').write_text(json.dumps({'schema':'neural095-participant-view/v1',
                'mode':'restricted_count_viewer/v1','view':view,'sandbox':'macos'}))
            sessions.append(str(path))
        for stage in ('view','collect','grade'):
            args=['--inputs','generated.json']+(['--sandbox','macos'] if stage=='view' else
                ['--cue-session',sessions[0],'--neural-session',sessions[1]])
            with self.subTest(stage=stage):
                argv=self.selected('restricted_count_viewer/v1',stage,args)
                self.assertEqual(argv[3:],[str(self.task/'implementations/participant-transport-v1/transport.py'),stage,*args])

    def test_show_command_does_not_launch(self):
        with patch.object(self.module.os,'execv',side_effect=AssertionError('no launch')):
            out=io.StringIO()
            with contextlib.redirect_stdout(out):
                code=self.module.main(['--condition','stateful_case_investigator/v2','--stage','configure','--show-command','--','--help'])
        value=json.loads(out.getvalue())
        self.assertEqual(code,0);self.assertFalse(value['execution_authority']);self.assertFalse(value['runtime_qualified'])

    def test_unknown_or_cross_condition_stage_refused_before_launch(self):
        with patch.object(self.module.os,'execv',side_effect=AssertionError('no launch')):
            with self.assertRaises(ValueError):
                self.module.main(['--condition','stateful_case_investigator/v2','--stage','grade','--','--help'])
            with self.assertRaises(SystemExit):
                self.module.main(['--condition','historical-offline','--stage','configure','--','--help'])

    def test_source_or_route_tampering_refused(self):
        source=self.task/'implementations/adaptive-owner-v2/configure.py'
        original=source.read_bytes();source.write_bytes(original+b'\n')
        with patch.object(self.module.os,'execv',side_effect=AssertionError('no launch')):
            with self.assertRaises(ValueError):
                self.module.main(['--condition','stateful_case_investigator/v2','--stage','configure','--','--help'])
        source.write_bytes(original)
        (self.task/'current-operator-routes.v1.json').write_bytes(b'{}')
        with patch.object(self.module.os,'execv',side_effect=AssertionError('no launch')),self.assertRaises(ValueError):
            self.module.main(['--condition','stateful_case_investigator/v2','--stage','configure','--','--help'])

    def test_linked_selected_source_refused(self):
        source=self.task/'implementations/adaptive-owner-v2/configure.py'
        target=self.root/'linked.py';source.rename(target);source.symlink_to(target)
        with patch.object(self.module.os,'execv',side_effect=AssertionError('no launch')),self.assertRaises(ValueError):
            self.module.main(['--condition','stateful_case_investigator/v2','--stage','configure','--','--help'])

    def test_forwarded_selector_switch_and_protocol_only_refused(self):
        for args in (['--condition','stateful_case_investigator/v2'],['--stage','grade'],['--sandbox','protocol_only']):
            with self.subTest(args=args),patch.object(self.module.os,'execv',side_effect=AssertionError('no launch')),self.assertRaises(ValueError):
                self.module.main(['--condition','restricted_count_viewer/v1','--stage','view','--',*args])




class HardeningControls(unittest.TestCase):
    setUp=SelectedRouteControls.setUp
    tearDown=SelectedRouteControls.tearDown
    selected=SelectedRouteControls.selected

    def refused(self,arguments,condition='restricted_count_viewer/v1',stage='view'):
        with patch.object(self.module.os,'execv',side_effect=AssertionError('No backend launch')),self.assertRaises(ValueError):
            self.module.main(['--condition',condition,'--stage',stage,'--',*arguments])

    def test_normal_macos_forwarding_after_hardening(self):
        args=['--inputs','cue.json','--view','cue_only','--output','session','--client','participant.py',
              '--python','/framework/python','--sandbox','macos','--max-actions','2000','--max-images','1500',
              '--max-output-bytes','134217728','--wall-seconds','300']
        command=self.selected('restricted_count_viewer/v1','view',args)
        self.assertEqual(command[4:],['view',*args])

    def test_equal_form_sandbox_override_is_refused(self):
        for args in (['--sandbox','macos','--sandbox=protocol_only'],
                     ['--sandbox=protocol_only','--sandbox','macos'],
                     ['--sandbox=macos']):
            with self.subTest(arguments=args):self.refused(args)

    def test_abbreviated_sandbox_overrides_are_refused(self):
        for flag in ('--sand','--sandb','--s'):
            with self.subTest(flag=flag):self.refused(['--sandbox','macos',flag,'protocol_only'])

    def test_duplicate_sandbox_and_other_viewer_options_are_refused(self):
        for args in (['--sandbox','macos','--sandbox','protocol_only'],
                     ['--sandbox','macos','--sandbox','macos'],
                     ['--sandbox','macos','--view','cue_only','--view','neural']):
            with self.subTest(arguments=args):self.refused(args)
        self.refused(['--inputs','pair.json','--sandbox','macos'],stage='collect')

    def test_equal_form_selector_overrides_refused_in_both_routes(self):
        for word in ('--condition=restricted_count_viewer/v1','--stage=grade','--show-command=true'):
            for condition,stage in (('restricted_count_viewer/v1','view'),('stateful_case_investigator/v2','configure')):
                with self.subTest(word=word,condition=condition):self.refused([word],condition,stage)

    def test_same_bytes_path_replacement_after_read_is_refused(self):
        source=self.task/'implementations/adaptive-owner-v2/configure.py'
        raw=source.read_bytes();original=self.module.hashlib.sha256;replaced=[]
        def after_read(body):
            result=original(body)
            if body==raw and not replaced:
                backup=self.root/'old-source.py';source.rename(backup);source.write_bytes(raw);replaced.append(True)
            return result
        with patch.object(self.module.hashlib,'sha256',side_effect=after_read):
            self.refused(['--help'],'stateful_case_investigator/v2','configure')
        self.assertEqual(replaced,[True])


class SessionControls(unittest.TestCase):
    setUp=SelectedRouteControls.setUp
    tearDown=SelectedRouteControls.tearDown

    def sessions(self,invalid=None):
        result=[]
        for view in ('cue_only','neural'):
            path=self.root/('closed-'+view);path.mkdir(exist_ok=True)
            (path/'BOUNDARY.json').write_text(json.dumps({'schema':'neural095-participant-view/v1',
                'mode':'restricted_count_viewer/v1','view':view,'sandbox':'protocol_only' if view==invalid else 'macos'}))
            result.append(path)
        return result

    def refused(self,stage,args):
        with patch.object(self.module.os,'execv',side_effect=AssertionError('No backend launch')), \
             self.assertRaises((ValueError,OSError)):
            self.module.main(['--condition','restricted_count_viewer/v1','--stage',stage,'--',*args])

    def test_protocol_only_either_view_refused_for_collect_and_grade(self):
        for view in ('cue_only','neural'):
            cue,neural=self.sessions(view)
            for stage in ('collect','grade'):
                with self.subTest(view=view,stage=stage):
                    self.refused(stage,['--cue-session',str(cue),'--neural-session',str(neural)])

    def test_session_option_alias_equal_and_duplicate_overrides_refused(self):
        cue,neural=self.sessions()
        base=['--cue-session',str(cue),'--neural-session',str(neural)]
        for tail in (['--cue',str(neural)],['--cue-session='+str(neural)],['--neural-session',str(cue)],['--neural',str(cue)]):
            for stage in ('collect','grade'):
                with self.subTest(tail=tail,stage=stage):self.refused(stage,base+tail)

    def test_wrong_mode_view_or_duplicate_boundary_keys_refused(self):
        cue,neural=self.sessions()
        path=cue/'BOUNDARY.json'
        for raw in (b'{"schema":"neural095-participant-view/v1","view":"neural","mode":"restricted_count_viewer/v1","sandbox":"macos"}',
                    b'{"schema":"neural095-participant-view/v1","view":"cue_only","mode":"other","sandbox":"macos"}',
                    b'{"schema":"neural095-participant-view/v1","view":"cue_only","mode":"restricted_count_viewer/v1","sandbox":"protocol_only","sandbox":"macos"}'):
            path.write_bytes(raw)
            self.refused('collect',['--cue-session',str(cue),'--neural-session',str(neural)])

    def test_linked_oversized_missing_boundary_refused_before_backend(self):
        cue,neural=self.sessions();path=cue/'BOUNDARY.json';original=path.read_bytes()
        target=self.root/'boundary-copy.json';target.write_bytes(original);path.unlink();path.symlink_to(target)
        self.refused('grade',['--cue-session',str(cue),'--neural-session',str(neural)])
        path.unlink();path.write_bytes(b' ' * 65537)
        self.refused('grade',['--cue-session',str(cue),'--neural-session',str(neural)])
        path.unlink()
        self.refused('grade',['--cue-session',str(cue),'--neural-session',str(neural)])


if __name__=='__main__':
    unittest.main(verbosity=2)
