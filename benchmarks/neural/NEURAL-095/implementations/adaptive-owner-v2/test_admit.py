"""New admission/CLI controls only; does not repeat complete actor campaign."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


fixtures = load('_owner_fixtures_for_admit', HERE / 'test_owner.py')
admit = load('_owner_admit_test', HERE / 'admit.py')
c = fixtures.c


class AdmissionControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Constructs one new source fixture; no OwnerControls tests are repeated.
        fixtures.OwnerControls.setUpClass()
        cls.f = fixtures.OwnerControls
        cls.deployment_sha = c.pin((cls.f.root / 'DEPLOYMENT.json').read_bytes())['sha256']

    @classmethod
    def tearDownClass(cls):
        fixtures.OwnerControls.tearDownClass()

    def test_attach_existing_request_and_source_command(self):
        target = self.f.root / 'ATTACHED_CONFIG.json'
        request = self.f.root / 'INVENTED_REQUEST.json'
        result = admit.attach(self.f.root, self.deployment_sha,
            self.f.root / 'CONFIGURATION_PAYLOAD.json', c.pin((self.f.root / 'CONFIGURATION_PAYLOAD.json').read_bytes())['sha256'],
            request, c.pin(request.read_bytes())['sha256'], target)
        self.assertFalse(result['execution_authority'])
        self.assertEqual(c.decode(target.read_bytes()), self.f.configuration)
        cmd = admit.command(self.f.root, self.deployment_sha, target, result['configuration']['sha256'])
        self.assertEqual(cmd[1:3], ['-I','-B'])
        self.assertEqual(Path(cmd[3]), self.f.root / c.BASE / 'entrypoint.py')
        self.assertFalse(Path(self.f.payload['output_root']).exists())

    def test_actual_cli_dry_run_never_runs_owner(self):
        completed = subprocess.run([fixtures.CHILD_PYTHON, '-I','-B', str(HERE/'admit.py'),
            '--root', str(self.f.root), '--deployment-sha256', self.deployment_sha, 'run',
            '--configuration', str(self.f.config_path), '--configuration-sha256', self.f.config_sha, '--dry-run'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False,
            env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'})
        self.assertEqual(completed.returncode,0,completed.stderr.decode())
        result = c.decode(completed.stdout)
        self.assertFalse(result['execution_authority']); self.assertFalse(result['runtime_qualified'])
        self.assertEqual(Path(result['argv'][3]), self.f.root/c.BASE/'entrypoint.py')
        self.assertFalse(Path(self.f.payload['output_root']).exists())

    def test_non_dry_run_uses_exact_process_replacement_only(self):
        expected = admit.command(self.f.root,self.deployment_sha,self.f.config_path,self.f.config_sha)
        with patch.object(admit.os,'execv',side_effect=RuntimeError('captured replacement')) as replace:
            with self.assertRaisesRegex(RuntimeError,'captured replacement'):
                admit.main(['--root',str(self.f.root),'--deployment-sha256',self.deployment_sha,'run',
                    '--configuration',str(self.f.config_path),'--configuration-sha256',self.f.config_sha])
        replace.assert_called_once_with(sys.executable,expected)

    def test_deployment_and_configuration_selection_mismatch_refused(self):
        for deployment, config in (('0'*64,self.f.config_sha),(self.deployment_sha,'0'*64)):
            with self.subTest(deployment=deployment), self.assertRaises(ValueError):
                admit.command(self.f.root,deployment,self.f.config_path,config)

    def test_request_mismatch_and_existing_configuration_refused(self):
        wrong = self.f.root/'WRONG_REQUEST.json'
        wrong.write_bytes(c.encode({'configuration_payload_sha256':'0'*64}))
        out = self.f.root/'REFUSED_CONFIG.json'
        with self.assertRaisesRegex(ValueError,'existing request selects'):
            admit.attach(self.f.root,self.deployment_sha,self.f.root/'CONFIGURATION_PAYLOAD.json',
                c.pin((self.f.root/'CONFIGURATION_PAYLOAD.json').read_bytes())['sha256'],wrong,c.pin(wrong.read_bytes())['sha256'],out)
        self.assertFalse(out.exists())
        with self.assertRaisesRegex(ValueError,'fresh configuration'):
            admit.attach(self.f.root,self.deployment_sha,self.f.root/'CONFIGURATION_PAYLOAD.json',
                c.pin((self.f.root/'CONFIGURATION_PAYLOAD.json').read_bytes())['sha256'],wrong,c.pin(wrong.read_bytes())['sha256'],self.f.config_path)

    def test_actor_policy_downgrade_refused_by_actual_loader(self):
        original = self.f.cm.checked
        descriptor = self.f.payload['actor']['arms']['case_adaptive__cue_only']['config']
        def altered(root,pin,cap=262144):
            raw = original(root,pin,cap)
            if pin == descriptor:
                obj = c.decode(raw); obj['schema']='dmfc-offline-reference/v1'; obj['policy']='single_frozen_fit_batch/v1'
                return c.encode(obj)
            return raw
        with patch.object(self.f.cm,'checked',side_effect=altered), self.assertRaisesRegex(ValueError,'mode-specific'):
            self.f.cm.load(self.f.config_path,self.f.config_sha)

    def test_assembled_actor_drift_is_rejected_even_with_rebound_descriptor(self):
        value,freeze,captured=copy.deepcopy(self.f.payload),copy.deepcopy(self.f.freeze),dict(self.f.captured)
        old = value['adaptive_admission']['assembled_actor']; raw=captured[old['path']]+b'\n# drift\n'
        new={'path':old['path'],**c.pin(raw)}
        value['adaptive_admission']['assembled_actor']=new; freeze['adaptive_admission']=value['adaptive_admission']
        freeze['files'][old['path']]=c.pin(raw); captured[old['path']]=raw
        original=self.f.cm.checked
        def mutated(root,pin,cap=262144):
            return raw if pin==new else original(root,pin,cap)
        with patch.object(self.f.cm,'checked',side_effect=mutated),self.assertRaisesRegex(ValueError,'exact original assembled'):
            self.f.cm.validate_adaptive_binding(value,captured,freeze)


if __name__=='__main__':
    unittest.main(verbosity=2)
