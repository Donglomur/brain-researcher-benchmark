"""Invented deployment/closure controls; never authentic science or Docker."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


c = module(HERE / 'configure.py', '_portable_dmfc_configuration_tests')


def invented_operator():
    return {'schema': 'dmfc-portable-deployment/v1', 'output_relative': 'artifacts-build/run',
        'runtime_identity': {'transport': {'docker': '/opt/invented/docker', 'environment': {
            'PATH': '/opt/invented/bin:/usr/bin:/bin', 'HOME': '/invented/home', 'TMPDIR': '/invented/tmp',
            'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'DOCKER_HOST': 'unix:///invented/daemon.sock',
            'DOCKER_CONFIG': '/invented/config'}}, 'server': {'ID': 'invented-daemon-ID',
            'Name': 'invented-daemon', 'ServerVersion': 'invented-version', 'OSType': 'linux', 'Architecture': 'aarch64'},
            'image': {'reference': c.IMAGE, 'Id': c.IMAGE, 'Os': 'linux', 'Architecture': 'arm64'}}}


class DeploymentControls(unittest.TestCase):
    def setUp(self):
        # Resolve the platform's /tmp alias before using the unchanged no-symlink
        # guards. A deliberately short private directory meets the Unix ABI.
        self.temp = Path(tempfile.mkdtemp(prefix='dm', dir=Path('/tmp').resolve()))
        self.out = self.temp / 'r'

    def tearDown(self):
        shutil.rmtree(self.temp)

    def deploy(self, operator=None, out=None, package=HERE):
        with patch('subprocess.run', side_effect=AssertionError('no subprocess')), \
             patch('subprocess.Popen', side_effect=AssertionError('no process launch')):
            return c.configure(operator or invented_operator(), out or self.out, package)

    def runtime(self, out=None, identity=None):
        out = out or self.out
        freeze = c.decode((out / c.BASE / 'SOURCE_FREEZE.json').read_bytes())
        captured = {n: (out / n).read_bytes() for n in freeze['files']}
        runtime = module(out / c.BASE / 'runtime_binding.py', '_invented_dmfc_runtime')
        with patch('subprocess.run', side_effect=AssertionError('no Docker probe')), \
             patch('subprocess.Popen', side_effect=AssertionError('no runtime operation')):
            return runtime.load_runtime(out, captured, freeze['files'], identity or invented_operator()['runtime_identity'])

    def test_fresh_deployment_needs_no_data_and_creates_no_request(self):
        observed = []; original = os.open
        def source_only(path, flags, *args, **kwargs):
            p = Path(path)
            self.assertTrue(p.is_relative_to(HERE))
            self.assertIn(p.suffix, ('.py', '.json'))
            observed.append(str(p))
            return original(path, flags, *args, **kwargs)
        with patch('os.open', source_only):
            result = self.deploy()
        self.assertGreater(len(observed), 45)
        self.assertFalse(result['execution_authority'])
        self.assertFalse(result['request_created'])
        self.assertFalse(result['runtime_compatibility_verified'])
        self.assertFalse((self.out / 'data').exists())
        payload = c.decode((self.out / 'CONFIGURATION_PAYLOAD.json').read_bytes())
        self.assertNotIn('request', payload)
        self.assertFalse(Path(payload['output_root']).exists())

    def test_real_closed_runtime_accepts_explicit_relocated_binding_without_probe(self):
        self.deploy()
        runtime = self.runtime()
        self.assertEqual(runtime.transport, invented_operator()['runtime_identity']['transport'])
        self.assertEqual(runtime.contract.IMAGE, c.IMAGE)

    def test_second_root_and_changed_transport_are_explicitly_repinned(self):
        first = self.deploy()
        second = invented_operator()
        second['runtime_identity']['transport']['docker'] = '/different/docker'
        second['runtime_identity']['transport']['environment']['DOCKER_HOST'] = 'unix:///different/socket'
        second['runtime_identity']['transport']['environment']['DOCKER_CONFIG'] = '/different/config'
        out = self.temp / 's'; other = self.deploy(second, out)
        runtime = self.runtime(out, second['runtime_identity'])
        self.assertEqual(runtime.transport, second['runtime_identity']['transport'])
        self.assertNotEqual(first['rendered_sources'][c.ENGINE], other['rendered_sources'][c.ENGINE])
        self.assertNotEqual(first['rendered_sources'][c.BASE + '/SOURCE_FREEZE.json'],
                            other['rendered_sources'][c.BASE + '/SOURCE_FREEZE.json'])

    def test_exact_runtime_transport_guard_is_preserved(self):
        self.deploy()
        wrong = invented_operator()['runtime_identity']
        wrong['transport']['docker'] = '/wrong/docker'
        with self.assertRaisesRegex(ValueError, 'configured transport equals'):
            self.runtime(identity=wrong)

    def test_missing_environment_key_refused_before_output(self):
        value = invented_operator(); del value['runtime_identity']['transport']['environment']['HOME']
        with self.assertRaisesRegex(ValueError, 'all seven'):
            self.deploy(value)
        self.assertFalse(self.out.exists())

    def test_extra_secret_environment_key_refused(self):
        value = invented_operator(); value['runtime_identity']['transport']['environment']['API_TOKEN'] = 'invented'
        with self.assertRaisesRegex(ValueError, 'all seven'):
            self.deploy(value)

    def test_no_image_rebinding_or_fallback(self):
        for key, replacement in [('reference', 'science:latest'), ('Id', 'sha256:' + '0' * 64), ('Architecture', 'amd64')]:
            with self.subTest(key=key):
                value = invented_operator(); value['runtime_identity']['image'][key] = replacement
                with self.assertRaisesRegex(ValueError, 'unchanged exact'):
                    self.deploy(value)

    def test_remote_socket_and_relative_executable_refused(self):
        for key, value in [('DOCKER_HOST', 'tcp://remote:2375'), ('docker', 'docker')]:
            v = invented_operator()
            if key == 'docker': v['runtime_identity']['transport'][key] = value
            else: v['runtime_identity']['transport']['environment'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.deploy(v)

    def test_existing_and_symlink_output_refused(self):
        self.out.mkdir()
        with self.assertRaisesRegex(ValueError, 'fresh destination'):
            self.deploy()
        link = self.temp / 'linked'; link.symlink_to(self.out, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'unlinked'):
            self.deploy(out=link)

    def test_source_tampering_and_source_symlink_refused(self):
        package = self.temp / 'p'; shutil.copytree(HERE / 'source', package / 'source')
        shutil.copyfile(HERE / 'SOURCE_MANIFEST.json', package / 'SOURCE_MANIFEST.json')
        target = package / 'source' / c.BASE / 'operation_owner.py'
        original = target.read_bytes(); target.write_bytes(original + b'\n# tamper\n')
        with self.assertRaisesRegex(ValueError, 'exact source template'):
            self.deploy(package=package)
        target.unlink(); target.symlink_to(HERE / 'source' / c.BASE / 'operation_owner.py')
        with self.assertRaisesRegex(ValueError, 'unlinked'):
            self.deploy(package=package)

    def test_scope_and_reference_changes_refused_even_with_updated_inventory(self):
        for variant in ('cohort', 'references'):
            with self.subTest(variant=variant):
                package = self.temp / variant; shutil.copytree(HERE / 'source', package / 'source')
                inv = c.decode((HERE / 'SOURCE_MANIFEST.json').read_bytes())
                if variant == 'cohort':
                    name = c.BASE + '/SOURCE_FREEZE.json'; value = c.decode((package / 'source' / name).read_bytes())
                    value['scientific_scope']['train'] = 747
                else:
                    name = c.Q + '/dmfc-paired-delivery-20261114-v1/DELIVERY_MANIFEST.json'
                    value = c.decode((package / 'source' / name).read_bytes()); value['scientific_scope']['references'].pop()
                    # Rebind the containing core freeze too, to reach the explicit
                    # science guard rather than merely failing a stale hash.
                    freeze_name = c.BASE + '/SOURCE_FREEZE.json'
                    freeze = c.decode((package / 'source' / freeze_name).read_bytes())
                    freeze['files'][name] = c.pin(c.encode(value))
                    frozen = c.encode(freeze); (package / 'source' / freeze_name).write_bytes(frozen)
                    inv['files'][freeze_name] = c.pin(frozen)
                body = c.encode(value); (package / 'source' / name).write_bytes(body); inv['files'][name] = c.pin(body)
                (package / 'SOURCE_MANIFEST.json').write_bytes(c.encode(inv))
                with self.assertRaisesRegex(ValueError, 'scientific scope|five references'):
                    self.deploy(package=package)

    def test_no_authority_fields_accepted(self):
        value = invented_operator(); value['request'] = {'decision': 'invented-not-authority'}
        with self.assertRaisesRegex(ValueError, 'no authority fields'):
            self.deploy(value)

    def test_long_output_socket_and_parent_escape_refused(self):
        for output in ('artifacts-build/' + 'x' * 90, 'artifacts-build/../escape'):
            value = invented_operator(); value['output_relative'] = output
            with self.subTest(output=output), self.assertRaises(ValueError):
                self.deploy(value)

    def test_json_duplicate_key_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            c.decode(b'{"a":1,"a":2}')

    def test_exact_45_core_and_active_scientific_source_closure(self):
        result = self.deploy()
        freeze = c.decode((self.out / c.BASE / 'SOURCE_FREEZE.json').read_bytes())
        self.assertEqual(len(freeze['files']), 45)
        for name, expected in result['rendered_sources'].items():
            self.assertEqual(c.pin((self.out / name).read_bytes()), expected)
        gate = module(self.out / c.GATE / 'candidate_admission.py', '_invented_gate_closure')
        support = gate.support(self.out)
        self.assertEqual(len(support.fields), 12)
        manifest = c.decode((self.out / c.Q / 'dmfc-paired-delivery-20261114-v1/DELIVERY_MANIFEST.json').read_bytes())
        for expected in [*manifest['evaluator_sources'].values(), *manifest['required_existing_source_and_authority_files']]:
            self.assertEqual(c.pin((self.out / expected['path']).read_bytes()), {k: expected[k] for k in ('bytes', 'sha256')})

    def test_review_template_rebinds_but_remains_unapproved(self):
        self.deploy()
        gate = module(self.out / c.GATE / 'candidate_admission.py', '_invented_template_gate')
        support = gate.support(self.out)
        path = self.out / c.GATE / 'REVIEW_TEMPLATE.json'; body = path.read_bytes(); review = c.decode(body)
        self.assertEqual(review['base_owner_freeze'], gate.BASE_FREEZE)
        self.assertEqual(review['decision'], 'UNREVIEWED_TEMPLATE')
        self.assertFalse(review['execution_authority'])
        self.assertFalse(review['matched_method_proven_by_grader'])
        self.assertEqual(review['reviewer'], '')
        self.assertEqual(review['findings'], '')
        self.assertTrue(all(v is None for v in review['checks'].values()))
        self.assertTrue(all(v == '' for v in review['method_field_findings'].values()))
        with self.assertRaisesRegex(ValueError, 'not execution authority'):
            gate.review_candidate(support, {'path': path.relative_to(self.out).as_posix(), **c.pin(body)})

    def test_original_candidate_gate_builds_exact_52_without_importing_candidate(self):
        self.deploy()
        gate = module(self.out / c.GATE / 'candidate_admission.py', '_invented_candidate_gate')
        support = gate.support(self.out)
        folder = self.out / 'invented-inputs'; folder.mkdir()
        program = folder / 'candidate.py'; program.write_text("raise AssertionError('CANDIDATE_MUST_NOT_EXECUTE_ON_HOST')\n")
        method = folder / 'METHOD.json'; method.write_bytes((self.out / c.BASE / 'numerical-policy/METHOD.json').read_bytes())
        def desc(path): return {'path': path.relative_to(self.out).as_posix(), **c.pin(path.read_bytes())}
        review = {'schema': 'dmfc-external-candidate-review/v1', 'candidate_id': 'NEURAL-095',
            'decision': 'source_and_procedure_reviewed_for_original_contract', 'execution_authority': False,
            'base_owner_freeze': gate.BASE_FREEZE, 'public_contract': gate.CONTRACT,
            'program': desc(program), 'method': desc(method), 'reviewer': 'INVENTED TEST ONLY; not a real review',
            'method_field_findings': {f: 'INVENTED parser-control fixture only.' for f in support.fields},
            'checks': {f: True for f in gate.CHECKS}, 'findings': 'INVENTED metadata parser fixture; execution prohibited.',
            'matched_method_proven_by_grader': False}
        review_path = folder / 'REVIEW.json'; review_path.write_bytes(c.encode(review))
        payload_path = self.out / 'CONFIGURATION_PAYLOAD.json'
        result = gate.prepare(self.out, payload_path, c.pin(payload_path.read_bytes())['sha256'],
                              review_path, c.pin(review_path.read_bytes())['sha256'], self.out / 'candidate',
                              self.out / 'artifacts-build' / 'candidate')
        self.assertFalse(result['candidate_source_imported']); self.assertFalse(result['request_created'])
        frozen = c.decode((self.out / 'candidate' / 'CANDIDATE_FREEZE.json').read_bytes())
        self.assertEqual(len(frozen['files']), 52)
        for name, expected in support.base['files'].items(): self.assertEqual(frozen['files'][name], expected)
        # Merely binding a JSON payload is not an admission grant. The unchanged
        # configuration parser can load such metadata, but the real owner refuses.
        payload_path = self.out / result['payload']['path']; payload = c.decode(payload_path.read_bytes())
        request = folder / 'INVENTED-NOT-A-GRANT.json'
        request.write_bytes(c.encode({'configuration_payload_sha256': c.pin(c.canonical(payload))['sha256']}))
        config = folder / 'CONFIG.json'; config.write_bytes(c.encode({**payload, 'request': desc(request)}))
        loaded, _, _ = support.c.load(config, c.pin(config.read_bytes())['sha256'])
        owner = module(self.out / c.BASE / 'operation_owner.py', '_invented_owner_admission')
        with self.assertRaisesRegex(ValueError, 'current exact root-selected complete operation'):
            owner.admit(loaded, now=0)
        self.assertFalse((self.out / 'artifacts-build' / 'candidate').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
