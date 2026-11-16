"""Generated complete-cohort controls. Fake Docker is NOT native qualification."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import executor
import holder
import runtime_contract as contract
from source_identity_join import bind_public_identity


def encoded(value):
    return (json.dumps(value, allow_nan=False) + '\n').encode()


def save(path, value):
    raw = encoded(value); path.write_bytes(raw)
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def raw_fixture():
    census = []
    for session in range(1, 7):
        delay = 1 if session in (1, 4) else 2; has = session != 6
        census.append({'session_index1': session, 'is_grc': True, 'delay_s': delay,
                       'has_chronic_green': has, 'disposition': 'not_two_second_target' if delay == 1
                       else 'required_registered_target' if has else 'no_chronicGreen_registration'})
    pairs = []
    for ordinal, (source, target, mouse) in enumerate([(1, 2, 'A'), (1, 3, 'A'), (4, 5, 'B')], 1):
        row = {'pair_index1': ordinal, 'source_session_index1': source, 'target_session_index1': target,
               'mouse_id': mouse, 'reward_type': 'DAT', 'source_cells_index1': [1],
               'target_cells_index1': [1], 'source_shape': [5, 1, 2], 'target_shape': [2, 1, 2],
               'source_time_seconds': [0, 3], 'target_time_seconds': [0, 3],
               'registration_rows_source_target': [[1, 1], [0, 2]]}
        for side, extent in [('source', 80), ('target', 32)]:
            row[side + '_file'] = {'path': f'pair{ordinal:04d}_{side}.f64', 'bytes': extent, 'sha256': '0' * 64}
        pairs.append(row)
    return {'schema': 'neural029-raw-projection-v2', 'source_record': '21645651',
            'complete_selected_cohort': True, 'source_part_count': 2, 'source_session_count': 6,
            'selected_target_session_indices1': [2, 3, 5], 'cohort_dispositions': census, 'pairs': pairs,
            'scientific_fits': 0, 'scientific_scores': 0}


class FakeDocker(executor.Docker):
    """Known generated programme runs locally only in this test provider."""
    fault = None
    latest = None

    def __init__(self, *args):
        super().__init__(*args); self.resources = {}; self.observed = []
        type(self).latest = self

    def call(self, argv, seconds=10):
        self.observed.append(argv)
        def answer(code=0, stdout='', stderr=''):
            return {'returncode': code, 'stdout': stdout, 'stderr': stderr}
        if argv[:2] == ['volume', 'inspect'] or argv[:3] == ['inspect', '--type', 'container']:
            name = argv[-1]
            if name not in self.resources:
                kind = 'volume' if argv[0] == 'volume' else 'object'
                return answer(1, '', f'Error: No such {kind}: {name}')
            return answer(stdout=json.dumps([self.resources[name]['info']]))
        if argv[:2] == ['volume', 'create']:
            name = argv[-1]; path = self.output.parent/('fake-' + name); path.mkdir()
            self.resources[name] = {'path': path, 'info': {'Name': name, 'Driver': 'local',
                'Options': {'type': 'tmpfs', 'device': 'tmpfs', 'o': contract.VOLUME_OPTIONS}}}
            return answer(stdout=name)
        if argv[0] == 'create':
            name = argv[argv.index('--name')+1]
            role = 'holder' if '/trusted/holder.py' in argv else 'candidate'
            mounts = {}
            for i, arg in enumerate(argv):
                if arg != '--mount':
                    continue
                bits = argv[i+1].split(','); fields = dict(x.split('=', 1) for x in bits if '=' in x)
                mounts[fields['dst']] = {'type': fields['type'], 'source': fields['src'], 'rw': 'readonly' not in bits}
            lim = contract.limits(role, self.r)
            h = {'NetworkMode': 'none', 'ReadonlyRootfs': True, 'Privileged': False,
                 'CapDrop': ['ALL'], 'CapAdd': None, 'SecurityOpt': ['no-new-privileges:true'],
                 'Devices': None, 'DeviceRequests': None, 'PortBindings': None, 'PidMode': '',
                 'IpcMode': 'private', 'AutoRemove': False, 'RestartPolicy': {'Name': 'no'},
                 'OomKillDisable': None, 'Memory': lim['memory'], 'MemorySwap': lim['memory'],
                 'NanoCpus': lim['nano_cpus'], 'PidsLimit': lim['pids'],
                 'Tmpfs': contract.TMPFS if role == 'candidate' else {},
                 'LogConfig': {'Type': 'local', 'Config': {'max-size': '64k', 'max-file': '1', 'compress': 'false'}},
                 'Ulimits': [{'Name': k, 'Soft': v[0], 'Hard': v[1]} for k, v in
                     {'cpu': (lim['cpu'], lim['cpu']+2), 'nofile': (1024,1024),
                      'core': (0,0), 'fsize': (100000000,100000000)}.items()],
                 'Mounts': [{'Type': v['type'], 'Source': v['source'], 'Target': k,
                            'ReadOnly': not v['rw'], 'VolumeOptions': {'NoCopy': True}} for k,v in mounts.items()]}
            effective = [{'Type': v['type'], 'Name': v['source'], 'Source': v['source'],
                          'Destination': k, 'RW': v['rw']} for k,v in mounts.items()]
            if role == 'candidate':
                effective += [{'Type':'tmpfs','Destination':'/tmp','RW':True}]
            info = {'Name': '/' + name, 'Id': name, 'Image': self.r['image'], 'HostConfig': h,
                    'Config': {'Image': self.r['image'], 'Entrypoint': ['python'], 'Cmd': contract.command(role),
                               'WorkingDir': '/' if role == 'holder' else '/output', 'User': '65534:65534',
                               'Env': [k+'=1' for k in contract.THREADS] + ['PYTHONDONTWRITEBYTECODE=1']},
                    'State': {'Status': 'created', 'Running': False, 'Pid': 0, 'OOMKilled': False, 'ExitCode': 0},
                    'NetworkSettings': {'Networks': {'none': {}}}, 'Mounts': effective}
            if self.fault == 'extra_mount' and role == 'candidate':
                info['Mounts'].append({'Type':'bind','Source':'/private','Destination':'/private','RW':False})
            self.resources[name] = {'info': info, 'role': role, 'mounts': mounts}
            return answer(stdout=name)
        if argv[0] == 'start':
            row = self.resources[argv[1]]; row['info']['State'].update(Status='running', Running=True, Pid=100)
            if row['role'] == 'candidate':
                mounts = row['mounts']; volume = self.resources[mounts['/output']['source']]['path']
                # Only this literal generated test fixture programme is run locally.
                call = subprocess.run([sys.executable, '-I', '-B', mounts['/program/candidate.py']['source'],
                    '--input', str(Path(mounts['/input/public']['source']).parent),
                    '--output', str(volume/'submission.json')], capture_output=True, timeout=5)
                row['info']['State'].update(Status='exited', Running=False, Pid=0, ExitCode=call.returncode)
            return answer()
        if argv[0] == 'wait':
            if self.fault == 'timeout':
                raise TimeoutError('generated wait failure')
            return answer(stdout=str(self.resources[argv[1]]['info']['State']['ExitCode'])+'\n')
        if argv[0] == 'rm':
            name = argv[-1]
            if self.fault == 'cleanup' and 'candidate' in name:
                return answer(1, '', 'generated removal failure')
            self.resources.pop(name, None); return answer()
        if argv[:2] == ['volume', 'rm']:
            self.resources.pop(argv[-1], None); return answer()
        if argv[0] == 'exec':
            self.assert_candidate_absent()
            mounts = self.resources[argv[1]]['mounts']
            volume = self.resources[mounts['/capture']['source']]['path']
            return answer(stdout=json.dumps(holder.capture(volume, Path(mounts['/export']['source']))))
        raise AssertionError(argv)

    def assert_candidate_absent(self):
        assert not any(x.get('role') == 'candidate' for x in self.resources.values())


class CompleteControls(unittest.TestCase):
    def setUp(self):
        import numpy as np
        self.np = np; self.tmp = tempfile.TemporaryDirectory(prefix='neural029-generated-')
        self.base = Path(self.tmp.name).resolve(); self.prepared = self.base/'prepared'
        (self.prepared/'public').mkdir(parents=True); (self.prepared/'private').mkdir()
        (self.base/'dockerconfig').mkdir(); self.program = self.base/'generated.py'
        self.program.write_text("import argparse,json\nfrom pathlib import Path\np=argparse.ArgumentParser();p.add_argument('--input');p.add_argument('--output');a=p.parse_args()\nm=json.loads((Path(a.input)/'public/MANIFEST.json').read_text())\nr={'schema':'neural029-predictions-v1','predictions':[{'pair_id':x['pair_id'],'values':[[[float(t)+(0 if i<2 else 3) for t in range(61)] for c in x['cell_ids']] for q in x['query_ids']]} for i,x in enumerate(m['pairs'])]}\nPath(a.output).write_text(json.dumps(r))\n")
        public = {'schema':'neural029-public-v1','time_seconds':[i/20 for i in range(61)],'pairs':[]}
        targets = {'schema':'neural029-targets-v2','pairs':[]}
        y = np.tile(np.arange(61,dtype=float),(2,1,1))
        for i in range(3):
            key=hashlib.sha256(str(i).encode()).hexdigest(); path=self.prepared/'public'/(key+'.npz')
            np.savez(path,calibration=np.tile(y[0],(4,1,1)),validation=y[:1])
            raw=path.read_bytes()
            public['pairs'].append({'pair_id':key,'cell_ids':[hashlib.sha256(b'cell').hexdigest()],
                'query_ids':[hashlib.sha256(str(q).encode()).hexdigest() for q in range(2)],
                'source_delay_seconds':1,'target_delay_seconds':2,'reward_type':'DAT',
                'calibration_trials':4,'validation_trials':1,
                'file':{'path':'public/'+path.name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}})
            path=self.prepared/'private'/(key+'.npz');np.savez(path,target=y,baseline=y[0],fixed_warp_baseline=y[0]+1)
            raw=path.read_bytes();targets['pairs'].append({'pair_id':key,'mouse_id':'A' if i<2 else 'B',
                'training_scale_squared':1.0,'file':{'path':'private/'+path.name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}})
        pub=save(self.prepared/'public/MANIFEST.json',public)
        truth=save(self.prepared/'private/TARGETS.json',targets)
        identity=save(self.prepared/'private/IDENTITY_MAP.json',bind_public_identity(raw_fixture(),public,'0'*64))
        save(self.prepared/'private/BINDING.json',{'schema':'neural029-binding-v2',
             'public':{'path':'public/MANIFEST.json',**pub},'private':{'path':'private/TARGETS.json',**truth},
             'identity':{'path':'private/IDENTITY_MAP.json',**identity}})
        docker=self.base/'docker-not-executed';docker.write_bytes(b'generated-fake-not-an-executable')
        raw=self.program.read_bytes()
        self.r={'schema':'neural029-program-request-v1','program':str(self.program),
            'program_pin':{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()},
            'prepared_root':str(self.prepared),'public_manifest_pin':pub,
            'binding':str(self.prepared/'private/BINDING.json'),'method_root':str(HERE),
            'grader_python':sys.executable,'docker':str(docker),
            'docker_pin':{'bytes':docker.stat().st_size,'sha256':hashlib.sha256(docker.read_bytes()).hexdigest()},
            'docker_host':'unix:///generated-not-real.sock','docker_config':str(self.base/'dockerconfig'),
            'image':'sha256:'+'0'*64,'output':str(self.base/'run'),
            'candidate_wall_seconds':10,'grade_wall_seconds':10,'cleanup_wall_seconds':30,'whole_wall_seconds':150,
            'candidate_cpu_seconds':10,'candidate_memory_bytes':536870912,'candidate_nano_cpus':1000000000,
            'host_memory_budget_bytes':536870912,'retention_budget_bytes':536870912}
        FakeDocker.fault=None

    def tearDown(self):
        self.tmp.cleanup()

    def run_generated(self):
        with patch.object(executor,'Docker',FakeDocker):
            return executor.execute(self.r)

    def test_complete_three_pair_two_mouse_actual_grader(self):
        result=self.run_generated(); self.assertEqual(result['status'],'programme_captured_and_graded')
        grade=json.loads((Path(self.r['output'])/'grade.json').read_text())
        self.assertEqual(grade['primary_nrmse'],1.5);self.assertEqual(len(grade['pairs']),3)
        names=[x['event'] for x in result['events']]
        self.assertLess(names.index('programme_frozen'),names.index('whole_public_packet_staged'))
        self.assertLess(names.index('candidate_removed_and_absent'),names.index('submission_committed'))
        self.assertLess(names.index('all_candidate_resources_absent'),names.index('private_grading_start'))

    def test_extra_mount_and_failed_cleanup_never_read_binding(self):
        for fault in ('extra_mount','cleanup','timeout'):
            with self.subTest(fault=fault):
                self.r['output']=str(self.base/('run-'+fault));FakeDocker.fault=fault
                old=executor.safe.read
                def watched(path,*args,**kwargs):
                    if str(path)==self.r['binding']:raise AssertionError('private binding read before closure')
                    return old(path,*args,**kwargs)
                with patch.object(executor.safe,'read',watched):
                    with self.assertRaises((ValueError,TimeoutError)):self.run_generated()
                self.assertFalse((Path(self.r['output'])/'binding.json').exists())

    def test_public_extras_and_wrong_program_hash_refuse_before_docker(self):
        (self.prepared/'public/private.json').write_text('{}')
        with self.assertRaises(ValueError):self.run_generated()
        self.r['output']=str(self.base/'run2');self.r['program_pin']['sha256']='0'*64
        with self.assertRaises(ValueError):self.run_generated()
        self.assertFalse((Path(self.r['output'])/'public').exists())

    def test_malformed_full_submission_no_private_numeric_loader(self):
        self.program.write_text(self.program.read_text().replace("Path(a.output).write_text(json.dumps(r))",
            "r['predictions'].pop();Path(a.output).write_text(json.dumps(r))"))
        raw=self.program.read_bytes();self.r['program_pin']={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        # The unchanged grader validates all outputs before attempting missing truth.
        (self.prepared/'private/TARGETS.json').unlink()
        with self.assertRaises(ValueError):self.run_generated()
        text=json.loads((Path(self.r['output'])/'grade-process.json').read_text())['stderr']
        self.assertIn('complete pair inventory',text);self.assertNotIn('FileNotFoundError',text)

    def test_different_binding_manifest_cannot_grade_candidate(self):
        p=self.prepared/'private/BINDING.json';b=json.loads(p.read_text());b['public']['sha256']='f'*64;save(p,b)
        with self.assertRaisesRegex(ValueError,'exact candidate-visible'):self.run_generated()
        self.assertFalse((Path(self.r['output'])/'grade-process.json').exists())

    def test_holder_rejects_extra_and_linked_outputs(self):
        source=self.base/'capture-source';source.mkdir();dest=self.base/'capture-dest';dest.mkdir()
        (source/'submission.json').symlink_to(self.program)
        with self.assertRaises(OSError):holder.capture(source,dest)
        (source/'submission.json').unlink();(source/'submission.json').write_text('{}');(source/'extra').write_text('x')
        with self.assertRaises(ValueError):holder.capture(source,dest)

    def test_prior_350MB_underbooking_refused(self):
        self.r['retention_budget_bytes']=350000000
        with self.assertRaisesRegex(ValueError,'allowances'):executor.validate_request(self.r)


if __name__ == '__main__':
    unittest.main()
