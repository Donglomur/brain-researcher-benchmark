"""Exercise launcher argv and status using a stub; never invoke Harbor."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'examples/original-three/scripts/run_task.sh'


class ExampleLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.task = self.root / "task with 'quotes' and spaces"
        self.task.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.log = self.root / 'calls.jsonl'
        stub = self.bin / 'harbor'
        stub.write_text('''#!/usr/bin/env python3
import json, os, sys
with open(os.environ['LAUNCH_TEST_LOG'], 'a') as out:
    out.write(json.dumps(sys.argv[1:]) + '\\n')
sys.exit(int(os.environ.get('LAUNCH_TEST_EXIT', '0')))
''')
        stub.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        LAUNCH_TEST_LOG=str(self.log), NILEARN_CACHE=str(self.root / 'no-cache'))

    def launch(self, agent='oracle', run=True, task=None):
        args = ['bash', str(SCRIPT), str(task or self.task), agent]
        if run:
            args.append('--run')
        return subprocess.run(args, env=self.env, cwd=self.root,
                              text=True, capture_output=True, timeout=10)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_success_preserves_literal_task_and_output_arguments(self):
        marker = self.root / 'must-not-exist'
        self.env['OUT'] = "out with spaces; touch " + str(marker) + " $(touch " + str(marker) + ")"
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        args, = self.calls()
        self.assertEqual(args[args.index('-p') + 1], str(self.task))
        self.assertEqual(args[args.index('-o') + 1], self.env['OUT'])
        self.assertNotIn('--mounts', args)
        self.assertFalse(marker.exists())

    def test_print_only_does_not_invoke_harbor(self):
        result = self.launch(agent='all', run=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [])
        self.assertEqual(sum(line.startswith('harbor ') for line in result.stdout.splitlines()), 3)
        self.assertIn('# add --run to execute', result.stdout)

    def test_all_modes_and_failure_exit_status(self):
        result = self.launch(agent='all')
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertEqual([args[args.index('-a') + 1] for args in calls], ['oracle', 'codex', 'claude-code'])
        self.assertIn('CODEX_FORCE_AUTH_JSON=1', calls[1])
        self.log.unlink()
        self.env['LAUNCH_TEST_EXIT'] = '7'
        result = self.launch(agent='all')
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(len(self.calls()), 1)

    def test_cache_path_is_a_single_valid_json_operand(self):
        cache = self.root / 'cache "quoted" \\ and\nnewline'
        cache.mkdir()
        self.env['NILEARN_CACHE'] = str(cache)
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        args, = self.calls()
        mounts = json.loads(args[args.index('--mounts') + 1])
        self.assertEqual(mounts, [{'type': 'bind', 'source': str(cache),
                                   'target': '/nilearn_data', 'read_only': True}])
        self.assertIn('NILEARN_DATA=/nilearn_data', args)

    def test_builtin_task_and_unknown_agent(self):
        result = self.launch(task='DEVCONN-001')
        self.assertEqual(result.returncode, 0, result.stderr)
        args, = self.calls()
        self.assertEqual(args[args.index('-p') + 1], str(ROOT / 'examples/original-three/DEVCONN-001'))
        self.log.unlink()
        result = self.launch(agent='unknown')
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.calls(), [])


if __name__ == '__main__':
    unittest.main()
