"""Focused capacity-artifact and task-specific CI admission controls; no data fits."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = 'benchmarks/neural/NEURAL-092/implementations/public-ci-adapter-v1'
FONT = 'benchmarks/neural/NEURAL-019/implementations/png-transport-dejavu-v1/assets/DejaVuSansMono.ttf'
N021 = 'benchmarks/neural/NEURAL-021/implementations/raster-participant-v1/assets/DejaVuSansMono.ttf'

def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

launcher = load('later_ci_runner', 'scripts/maintenance/run_parallel_source_controls.py')
adapter = load('neural092_ci_adapter', ADAPTER + '/ci_adapter.py')
checker = load('later_ci_repository_checks', 'src/neurobench/repository_checks.py')


class LaterCIControls(unittest.TestCase):
    def aggregate(self, base, fail=False, token='${ARTIFACT_DIR}'):
        root = base/'repo'; root.mkdir()
        program = ('import json,os,pathlib,sys\n'
                   'p=pathlib.Path(sys.argv[1]); assert str(p)==os.environ["OWNED_ARTIFACT"]\n'
                   'p.mkdir(mode=0o700); (p/"raw.json").write_text("real generated artifact")\n'
                   + ('raise SystemExit(4)\n' if fail else 'print(json.dumps({"controls":[{"id":"actual_generated_control","status":"passed"}]}))\n'))
        (root/'control.py').write_text(program)
        inventory=root/'benchmarks/integrity/source-ownership.json';inventory.parent.mkdir(parents=True)
        inventory.write_text(json.dumps({'files':[{'path':'control.py','bytes':len(program.encode()),
                                                   'sha256':hashlib.sha256(program.encode()).hexdigest()}]}))
        expected={'controls':[{'id':'actual_generated_control','status':'passed'}]}
        document={'schema':'parallel-source-controls/v1','groups':{'stdlib':{'python':sys.version.split()[0],'packages':{}}},
                  'commands':[{'id':'artifact-control','task_id':'generated','group':'stdlib','cwd':'.',
                               'argv':['${PYTHON}','-I','-S','-B','control.py',token],
                               'environment':{'OWNED_ARTIFACT':'${ARTIFACT_DIR}'},
                               'runner':'json-controls','expected_output':expected,'expected_tests':1,'expected_skips':0,
                               'timeout_seconds':10,'test_paths':['control.py'],'fixtures':[]}]}
        manifest=base/'manifest.json';manifest.write_text(json.dumps(document))
        return root,manifest,base/'results'

    def test_artifact_substitution_argv_environment_and_success_pointer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,manifest,output=self.aggregate(Path(tmp))
            with contextlib.redirect_stdout(io.StringIO()):result=launcher.run(root,manifest,'stdlib',output)
            self.assertEqual(result[0]['tests'],1)
            self.assertEqual(result[0]['artifact_directory'],'artifact-control.artifacts')
            self.assertEqual((output/'artifact-control.artifacts/raw.json').read_text(),'real generated artifact')
            receipt=json.loads((output/'results.json').read_text())
            self.assertEqual(receipt['completed'][0]['artifact_directory'],result[0]['artifact_directory'])

    def test_artifact_failure_pointer_and_partial_raw_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,manifest,output=self.aggregate(Path(tmp),fail=True)
            with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(ValueError):
                launcher.run(root,manifest,'stdlib',output)
            receipt=json.loads((output/'results.json').read_text())
            self.assertEqual(receipt['failed'][0]['artifact_directory'],'artifact-control.artifacts')
            self.assertTrue((output/'artifact-control.artifacts/raw.json').is_file())
            self.assertIn('process exit 4',receipt['failed'][0]['error'])

    def test_only_whole_artifact_token_and_ordinary_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);root,manifest,output=self.aggregate(base,token='${ARTIFACT_DIR}/nested')
            with self.assertRaisesRegex(ValueError,'unresolved command placeholder'):
                launcher.run(root,manifest,'stdlib',output)
            self.assertFalse(output.exists())
            document=json.loads(manifest.read_text());document['commands'][0]['argv'][-1]='${ARTIFACT_DIR}'
            manifest.write_text(json.dumps(document));(base/'actual').mkdir();(base/'link').symlink_to(base/'actual')
            with self.assertRaisesRegex(ValueError,'symlink in output path'):
                launcher.run(root,manifest,'stdlib',base/'link/results')
            self.assertFalse((base/'actual/results').exists())

    def actual_report(self):
        provenance={'interpreter':sys.executable,'python_version':sys.version,'platform':sys.platform}
        report=json.loads(json.dumps(adapter.FIXED));report.update(provenance)
        return report,provenance

    def test_dynamic_provenance_projection_keeps_actual_six_statuses(self):
        report,provenance=self.actual_report();raw=json.dumps(report).encode()
        projected=adapter.validate_report(raw,raw,b'',0,provenance)
        self.assertEqual(projected['controls'],report['controls'])
        self.assertEqual(len(projected['controls']),6)
        self.assertEqual(json.loads(raw)['python_version'],sys.version)

    def test_failed_missing_reordered_or_extra_statuses_refused(self):
        report,provenance=self.actual_report()
        variations=[[],report['controls'][::-1],report['controls']+[{'id':'invented','status':'passed'}],
                    [*report['controls'][:5],{'id':adapter.CONTROL_IDS[-1],'status':'failed'}]]
        for controls in variations:
            raw=json.dumps({**report,'controls':controls}).encode()
            with self.subTest(controls=controls),self.assertRaises(ValueError):
                adapter.validate_report(raw,raw,b'',0,provenance)

    def test_provenance_types_flags_capture_and_exit_are_not_normalized(self):
        report,provenance=self.actual_report()
        for key,value in [('platform','invented-platform'),('interpreter','different-python'),
                          ('python_version',False),('numerical_calls',False),('authentic_data',0)]:
            raw=json.dumps({**report,key:value}).encode()
            with self.subTest(key=key),self.assertRaises(ValueError):
                adapter.validate_report(raw,raw,b'',0,provenance)
        raw=json.dumps(report).encode()
        for stdout,stderr,code in [(raw+b' ',b'',0),(raw,b'warning',0),(raw,b'',None),(raw,b'',1)]:
            with self.subTest(code=code,stderr=stderr),self.assertRaises(ValueError):
                adapter.validate_report(raw,stdout,stderr,code,provenance)

    def test_duplicate_and_nonfinite_report_json_refused(self):
        for raw in (b'{"status":"passed","status":"failed"}',b'{"number":NaN}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):adapter.decode(raw)

    def test_artifact_allocation_is_fresh_owned_and_outside_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp).resolve();repository=base/'repo';repository.mkdir();artifact=base/'out'
            adapter.allocate(repository,artifact)
            self.assertEqual(artifact.stat().st_mode & 0o777,0o700)
            with self.assertRaises(ValueError):adapter.allocate(repository,artifact)
            with self.assertRaises(ValueError):adapter.allocate(repository,repository/'out')
            (base/'link').symlink_to(artifact)
            with self.assertRaises(ValueError):adapter.allocate(repository,base/'link/new')

    def test_capture_limit_preserves_partial_streams_and_reaps_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact=Path(tmp);receipt={}
            argv=[sys.executable,'-I','-S','-B','-c',
                  'import os; os.write(1,b"x"*10000); os.write(2,b"y"*10000)']
            with self.assertRaisesRegex(ValueError,'combined capture limit'):
                adapter.capture(argv,artifact,artifact,receipt)
            stdout=(artifact/'STDOUT.json').read_bytes();stderr=(artifact/'STDERR.txt').read_bytes()
            self.assertEqual(len(stdout)+len(stderr),16384)
            self.assertTrue(stdout or stderr)
            self.assertEqual(receipt['retained_capture_bytes'],16384)
            self.assertIn('combined capture limit',receipt['capture_error']['message'])
            self.assertIsInstance(receipt['child_exit_code'],int)
            with self.assertRaises(ChildProcessError):os.waitpid(receipt['child_pid'],os.WNOHANG)

    def test_changed_source_pin_descriptor_refused_before_runtime_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);pins=base/'pins.json';pins.write_text('{}')
            with self.assertRaisesRegex(ValueError,'source pin descriptor mismatch'):
                adapter.source_guard(base,pins)

    def test_font_exact_path_identity_and_existing_n021_are_preserved(self):
        pin=checker.PINNED_SOURCE_RESOURCES[FONT]
        self.assertEqual(pin,checker.PINNED_SOURCE_RESOURCES[N021])
        self.assertEqual(pin,{'mode':'100644','bytes':340240,
                             'sha256':'602ec86b8948cfcd956482fe64f94c36c867770149ef2f791d4613f443bcecb3'})
        self.assertNotIn('.ttf',checker.SOURCE_SUFFIXES)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();target=root/FONT;target.parent.mkdir(parents=True)
            body=(ROOT/FONT).read_bytes();self.assertEqual(hashlib.sha256(body).hexdigest(),pin['sha256'])
            target.write_bytes(body)
            artifacts=[{'id':'font-control','path':str(Path(FONT).parent)}]
            # Exercise the actual ownership traversal and source Reader hashes.
            reader=checker.Reader(root)
            self.assertIn(FONT,checker.artifact_members(root,artifacts,reader=reader))
            with target.open('r+b') as stream:stream.write(bytes([body[0]^1]))
            with self.assertRaisesRegex(ValueError,'Pinned source resource mismatch'):
                checker.artifact_members(root,artifacts,reader=checker.Reader(root))
            with target.open('r+b') as stream:stream.write(body[:1])
            target.chmod(0o755)
            with self.assertRaisesRegex(ValueError,'Pinned source resource mismatch'):
                checker.artifact_members(root,artifacts,reader=checker.Reader(root))
            target.chmod(0o644);target.rename(target.with_name('Other.ttf'))
            with self.assertRaisesRegex(ValueError,'Non-source member type'):
                checker.artifact_members(root,artifacts,reader=checker.Reader(root))


    def stage_a_artifact(self):
        return {
            "id": "neural-039-stage-a-metadata-v1",
            "path": "benchmarks/neural/NEURAL-039/acquisition",
            "scope": "task",
            "owner_ids": ["NEURAL-039"],
            "related_task_ids": [],
            "status": "constructed_source",
            "role": "reviewed_source_component",
        }

    def test_stage_a_exact_artifact_route_and_standard_task_roots(self):
        home = "benchmarks/neural/NEURAL-039"
        row = self.stage_a_artifact()
        self.assertTrue(checker.task_artifact_path_allowed(row, home))
        for path in (home + "/implementations/example", home + "/contracts/example"):
            with self.subTest(path=path):
                self.assertTrue(checker.task_artifact_path_allowed({**row, "path": path}, home))
        other_home = "benchmarks/neural/NEURAL-040"
        other = {**row, "id": "ordinary-component", "owner_ids": ["NEURAL-040"]}
        for suffix in ("/implementations/example", "/contracts/example"):
            with self.subTest(home=other_home, suffix=suffix):
                self.assertTrue(checker.task_artifact_path_allowed(
                    {**other, "path": other_home + suffix}, other_home))

    def test_stage_a_route_rejects_neighboring_artifact_identities(self):
        home = "benchmarks/neural/NEURAL-039"
        row = self.stage_a_artifact()
        variants = [
            ("id", "neural-039-stage-a-metadata-v2"),
            ("owner_ids", ["NEURAL-040"]),
            ("owner_ids", []),
            ("owner_ids", ["NEURAL-039", "NEURAL-040"]),
            ("path", "benchmarks/neural/NEURAL-040/acquisition"),
            ("path", home + "/acquisition-extra"),
            ("path", home + "/acquisition/nested"),
            ("scope", "shared"),
            ("scope", "unresolved"),
            ("status", "shared_framework_source"),
            ("status", None),
            ("role", "unreviewed_source_component"),
            ("related_task_ids", ["NEURAL-040"]),
        ]
        for key, value in variants:
            with self.subTest(key=key, value=value):
                self.assertFalse(checker.task_artifact_path_allowed({**row, key: value}, home))
        self.assertFalse(checker.task_artifact_path_allowed(row, "benchmarks/neural/NEURAL-040"))
        for key in ("status", "role"):
            missing = dict(row)
            del missing[key]
            with self.subTest(missing=key):
                self.assertFalse(checker.task_artifact_path_allowed(missing, home))


if __name__=='__main__':
    unittest.main()
