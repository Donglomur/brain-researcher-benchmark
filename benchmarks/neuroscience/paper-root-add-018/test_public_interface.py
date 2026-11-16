"""Relocation and real-operator engineering checks; all products are invented."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parent
TASK = 'PAPER-ROOT-ADD-018'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode()


def identity(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write_json(path, value):
    body = canonical(value) + b'\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return {'path': str(path), 'bytes': len(body),
            'sha256': hashlib.sha256(body).hexdigest()}


WORKER = r'''import json,sys
from pathlib import Path
request=json.loads(Path(sys.argv[1]).read_text())
output=Path(sys.argv[2]);phase=request['phase']
if phase!='analyze':
 (output/'invented-state.json').write_text(json.dumps({'phase':phase,'invented':True}))
else:
 rows=[]
 for item in request['payload']['native_requests']:
  component=item['component_roster'][0]
  value={'components':[{'component_id':component['component_id'],'unit':component['unit'],'axes':component['axes'],'data':{'invented_obligation':item['obligation_id']},'disposition':'provenance_only','provenance':{'invented':True}}],'source_policy':'native_source_reproduction','methods_conformance':['invented engineering only'],'role_dispositions':[{'role_id':x} for x in item['role_ids']],'attempts':[]}
  rows.append({'family_id':item['family_id'],'query_id':item['obligation_id'],'disposition':'value','value':value,'reason':None,'watermark':None})
 (output/'response.json').write_text(json.dumps({'schema':'ofc-response-v1','request_id':request['request_id'],'source_id':request['source_id'],'model_id':request['model_id'],'rows':rows}))
'''


TARGET_AUDIT_BOOTSTRAP = r'''import json,runpy,sys
from pathlib import Path
package,output,target,event_file=sys.argv[1:5]
args=sys.argv[5:];events=[]
def audit(event,values):
 if event!='open' or not isinstance(values[0],str) or values[0]!=target:return
 root=Path(output);closure=json.loads((root/'PREDICTIONS_CLOSED.json').read_text())
 assert closure['all_selected_predictions_closed'] is True
 records=closure['candidate_collections']+closure['reference_collections']
 assert len(records)==2
 stages=[]
 for descriptor in records:
  record=json.loads(Path(descriptor['path']).read_text())
  assert record['receipt_chain']['natural_complete'] is True
  assert len(record['rows'])==74 and not record['invalid_families']
  stages+=record['receipt_chain']['stages']
 assert len(stages)==8
 assert all(s['original_reaped'] and s['containment_resolved'] and s['terminal_custody_saved'] and s['original_returncode']==0 and not s['forced_stop'] for s in stages)
 events.append({'target_open_after_complete_candidate_reference_closure':True,'closed_stages':8,'pids':[s['pid'] for s in stages]})
sys.addaudithook(audit)
sys.argv=[str(Path(package)/'operator_api.py'),*args]
try:runpy.run_path(sys.argv[0],run_name='__main__')
finally:Path(event_file).write_text(json.dumps(events))
'''


class PublicInterface(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ofc invented relocated ')
        self.root = Path(self.temp.name).resolve()
        self.package = self.root / 'source with spaces'
        shutil.copytree(PACKAGE, self.package,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        self.output = self.root / 'operation'

    def tearDown(self):
        self.temp.cleanup()

    def run_python(self, *args):
        return subprocess.run([sys.executable, '-I', '-S', '-B', *map(str, args)],
                              capture_output=True, text=True, timeout=60,
                              cwd=self.root, check=False)

    def review(self):
        pins = json.loads((self.package / 'RUNTIME_SOURCE_PINS.json').read_text())
        return {'schema': 'ofc-operator-review-v1', 'task_id': TASK,
                'implementation_source_id': identity(pins), 'mode': 'engineering',
                'scientific_authorized': False,
                'execution': {'mode': 'trusted_inert_engineering'},
                'plans': {}, 'private_targets': {}, 'reference_programs': [],
                'allowed_conditions': ['R_A'], 'history_id': 'invented-history',
                'wall_seconds': 30, 'output_reservation_bytes': 16 * 1024**2,
                'qualification': None}

    def args(self, review, program=None):
        path = self.root / 'review.json'
        write_json(path, review)
        return ['--program', str(program or self.root / 'missing-program.json'),
                '--review', str(path), '--output', str(self.output),
                '--other-reserve-bytes', '0', '--condition', 'R_A']

    def invented_runtime(self):
        pins = json.loads((self.package / 'RUNTIME_SOURCE_PINS.json').read_text())
        missing = [r for r in pins['files'] if r.startswith('reference/author_source/')]
        self.assertEqual(len(missing), 59)
        # Only this temporary generated copy receives obvious stand-ins and a
        # different declared runtime identity. Never substitute them in release.
        for rel in missing:
            path = self.package / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            body = ('% INVENTED ENGINEERING PLACEHOLDER: ' + rel + '\n').encode()
            path.write_bytes(body)
            pins['files'][rel] = {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
        write_json(self.package / 'RUNTIME_SOURCE_PINS.json', pins)

    def test_relocated_help_and_reference_configuration(self):
        result = self.run_python(self.package / 'operator_api.py', '--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--other-reserve-bytes', result.stdout)
        destination = self.root / 'unqualified declarations'
        result = self.run_python(self.package / 'configure_references.py', '--output', destination)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)['qualified'])
        files = list(destination.glob('*.json'))
        self.assertEqual(len(files), 2)
        for path in files:
            value = json.loads(path.read_text())
            self.assertEqual(value['source_root'], str(self.package))
            self.assertEqual(len(value['files']), 97)
            self.assertEqual(len(value['declared_obligations']), 74)
            self.assertEqual(value['dependency_lock']['status'], 'not_independently_qualified')
        repeated = self.run_python(self.package / 'configure_references.py', '--output', destination)
        self.assertNotEqual(repeated.returncode, 0)

    def test_missing_author_dependency_refuses_before_program_or_output(self):
        result = self.run_python(self.package / 'operator_api.py', *self.args(self.review()))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('reference/author_source/', result.stderr)
        self.assertFalse(self.output.exists())

    def test_stale_runtime_review_refuses_before_missing_author(self):
        review = self.review()
        review['implementation_source_id'] = '0' * 64
        result = self.run_python(self.package / 'operator_api.py', *self.args(review))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('review stale implementation', result.stderr)
        self.assertFalse(self.output.exists())

    def test_changed_owned_member_refuses(self):
        path = self.package / 'ofc/common.py'
        body = path.read_bytes()
        self.assertIn(b'Strict records', body)
        path.write_bytes(body.replace(b'Strict records', b'strict records', 1))
        result = self.run_python(self.package / 'operator_api.py', *self.args(self.review()))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('content pin mismatch', result.stderr)
        self.assertFalse(self.output.exists())

    def test_engineering_cannot_authorize_science(self):
        self.invented_runtime()
        review = self.review()
        review['scientific_authorized'] = True
        result = self.run_python(self.package / 'operator_api.py', *self.args(review))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('engineering/scientific boundary', result.stderr)
        self.assertFalse(self.output.exists())

    def test_real_operator_full_roster_reference_closure_before_targets(self):
        self.invented_runtime()
        scope = json.loads((self.package / 'design/SCOPE_POLICY_BINDINGS.json').read_text())
        obligations = scope['obligations']
        self.assertEqual(len(obligations), 74)
        native = [{'obligation_id': x['obligation_id'], 'family_id': 'R_' + x['family'],
                   'role_ids': x['cohort_roles'], 'input_ids': [],
                   'component_roster': [{'component_id': 'invented', 'unit': 'dimensionless', 'axes': []}]}
                  for x in obligations]
        public = {}
        for family in scope['prospective_family_ids']:
            count = 200 if family == 'I_SIM_ATI' else 1
            public[family] = [{'query_id': family + '-' + str(i), 'family_id': family,
                              'stream_id': 'invented-' + str(i),
                              'public': {'target_unit': 'invented-unit'}, 'public_input_ids': [],
                              'cutoff': {'trial_ordinal': 0, 'bin_ordinal': 0},
                              'group_keys': {'rat': 'invented-rat', 'session': 'invented-session',
                                             'unit': 'invented-unit', 'case': 'invented-' + str(i)}}
                             for i in range(count)]
        worker = self.root / 'invented-worker'
        worker.mkdir()
        (worker / 'worker.py').write_text(WORKER)
        source_row = {'path': 'worker.py', 'bytes': len(WORKER.encode()),
                      'sha256': hashlib.sha256(WORKER.encode()).hexdigest()}
        source_id = identity([source_row])
        submission = {'schema': 'ofc-submission-v1', 'task_id': TASK,
                      'method_id': 'invented-engineering', 'source_root': str(worker),
                      'files': [source_row], 'entrypoints': {phase: ['python3', '/source/worker.py', '{request}', '{output}']
                          for phase in ('build', 'investigate', 'fit', 'predict', 'analyze')},
                      'dependency_lock': {'invented': True}, 'seed_policy': {'invented': True},
                      'declared_obligations': [x['obligation_id'] for x in obligations]}
        program = self.root / 'program.json'
        program_pin = write_json(program, submission)
        policies = {family: {'required_strata': [[]], 'stratum_keys': [], 'qualified': False,
                             'mandatory_comparators': ['invented-reference'],
                             'comparator_sources': {'invented-reference': source_id}}
                    for family in scope['native_family_ids']}
        private = {'policy_id': 'invented-policy', 'family_policies': policies, 'rows': []}
        for item in native:
            private['rows'].append({'family_id': item['family_id'], 'query_id': item['obligation_id'],
                'disposition': 'observed', 'group_keys': {},
                'value': {'components': [{'component_id': 'invented', 'unit': 'dimensionless', 'axes': [],
                    'data': {'invented_obligation': item['obligation_id']}, 'disposition': 'provenance_only'}]}})
        target = self.root / 'invented-protected-targets.json'
        target_pin = write_json(target, private)
        plan = {'schema': 'ofc-plan-v1', 'task_id': TASK, 'experiment_id': 'invented-experiment',
                'condition': 'R_A', 'scope': {'obligation_ids': submission['declared_obligations'],
                    'role_ids': scope['cohort_role_ids'],
                    'family_ids': scope['native_family_ids'] + scope['prospective_family_ids'],
                    'simulation_cases': 200, 'open_gate_ids': scope['open_gates']},
                'budget': {'wall_seconds': 25, 'phase_seconds': 5, 'output_bytes': 262144,
                    'scratch_bytes': 65536, 'file_count': 256, 'log_bytes': 16384,
                    'source_bytes': 65536, 'input_bytes': 262144, 'request_limit': 10,
                    'cpus': 1, 'memory_bytes': 33554432, 'pids': 4, 'tmp_bytes': 65536},
                'public_inputs': [], 'public_universes': public, 'native_requests': native,
                'protected_commitment': identity({'public': public, 'native': native,
                    'protected': private, 'policy': 'invented-policy'}),
                'dependency_environment': {'invented': True}, 'seed_manifest': {'invented': True},
                'qualification_id': 'invented-unqualified', 'reference_definitions': [],
                'policy_id': 'invented-policy'}
        plan_pin = write_json(self.root / 'plan.json', plan)
        review = self.review()
        review.update(plans={'R_A': plan_pin}, private_targets={'R_A': target_pin},
            reference_programs=[{'id': 'invented-reference', 'conditions': ['R_A'],
                                 'program': program_pin, 'qualified_source_id': source_id}],
            execution={'mode': 'trusted_inert_engineering', 'allowed_inert_source_ids': [source_id],
                       'scientific_operations': False, 'path': os.environ.get('PATH', os.defpath)})
        event_file = self.root / 'target-access-events.json'
        args = self.args(review, program)
        result = self.run_python('-c', TARGET_AUDIT_BOOTSTRAP, self.package, self.output,
                                 target, event_file, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        events = json.loads(event_file.read_text())
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0]['target_open_after_complete_candidate_reference_closure'])
        report = json.loads((self.output / 'REPORT.json').read_text())
        self.assertFalse(report['scientifically_qualified'])
        self.assertFalse(report['full_paper_scientifically_reproduced'])
        self.assertFalse(report['all_four_conditions_present'])
        self.assertEqual(report['new_benchmarks'], 0)
        self.assertEqual(len(report['conditions'][0]['native_obligations']), 74)
        scores = report['conditions'][0]['scores']
        self.assertEqual(len(scores), 10)
        self.assertTrue(all(x['official_absolute_value'] is None for x in scores))
        self.assertTrue(all(x['reason'] == 'scientific_execution_not_authorized' for x in scores))
        self.assertEqual(len(report['reference_runs']), 1)
        print(json.dumps({'invented_full_R_A_operator': 'passed', 'obligations': 74,
                          'candidate_and_reference_closed_stages': 8,
                          'protected_target_open_events': events,
                          'scientific_execution': False, 'official_numeric_scores': False}))


if __name__ == '__main__':
    unittest.main()
