"""Trusted paired-arm, fresh-container transport for current spinal predictions.

Candidate code runs only through the reused Docker lifecycle. Source construction
and generated mocks are not actual runtime or reference qualification.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import contract as c
import collect as collector
import materials

RETAINED = 256 * 1024**2
WRITES = 2 * 1024**3
READS = 4 * 1024**3
FLOOR = 60 * 1024**3
TERMINAL_RECEIPTS = 200_000


def retained_tree(root, reserve=0):
    """Bound traversal while enumerating and admit the next allocation first."""
    used = 0; nodes = 0; pending = [Path(root)]
    while pending:
        parent = pending.pop()
        with os.scandir(parent) as entries:
            for entry in entries:
                nodes += 1; c.need(nodes <= 4096, 'bounded campaign traversal')
                info = entry.stat(follow_symlinks=False)
                c.need(stat.S_ISDIR(info.st_mode)
                       or (stat.S_ISREG(info.st_mode) and info.st_nlink == 1),
                       'ordinary campaign tree')
                used += max(info.st_size, info.st_blocks*512)
                c.need(used+reserve <= RETAINED, 'prospective retained campaign budget')
                if stat.S_ISDIR(info.st_mode):
                    pending.append(Path(entry.path))
    c.need(used+reserve <= RETAINED, 'prospective retained campaign budget')
    return used


class Budget:
    """Preventive campaign counters; no claim of OS host-RSS or I/O quotas."""
    def __init__(self, root, other_reserve_bytes=0, *, enforce_space=True):
        self.root = Path(root).absolute(); self.other = other_reserve_bytes
        self.written = 0; self.read = 0; self.enforce_space = enforce_space
        c.need(type(self.other) is int and self.other >= 0, 'nonnegative external reservations')
        c.need(not self.root.exists() and not self.root.is_symlink(), 'exclusive fresh operator attempt')
        c.need(not any(p.is_symlink() for p in self.root.parents), 'real output parent')
        if self.enforce_space:
            c.need(shutil.disk_usage(self.root.parent).free >= FLOOR+self.other+RETAINED,
                   'preserve free-disk reserve before creating attempt')
        self.root.mkdir(mode=0o700)

    def charge(self, *, write=0, read=0):
        c.need(type(write) is int and type(read) is int and write >= 0 and read >= 0, 'nonnegative complete operation cost')
        c.need(self.written + write <= WRITES and self.read + read <= READS, 'cumulative campaign budget')
        if self.enforce_space:
            c.need(shutil.disk_usage(self.root).free >= FLOOR + self.other + RETAINED, 'preserve free-disk reserve')
        self.written += write; self.read += read

    def owned(self, path):
        path = Path(path).absolute()
        c.need(path == self.root or self.root in path.parents, 'owned output destination')
        c.need(not any(p.is_symlink() for p in (path,*path.parents)), 'unlinked owned destination')
        return path

    def guard(self, reserve=0):
        return retained_tree(self.root,reserve)

    def mkdir(self, path, mode=0o700):
        path = self.owned(path); self.charge(write=65536); self.guard(reserve=65536)
        path.mkdir(mode=mode)
        self.guard()

    def parents(self, path):
        path = self.owned(path)
        missing = []
        while not path.exists():
            missing.append(path); path = path.parent
        for part in reversed(missing):
            self.mkdir(part, 0o755)

    def save(self, path, body, cap=1_000_000, *, precharged=False):
        path = self.owned(path)
        c.need(isinstance(body, bytes) and len(body) <= cap, 'bounded owned file write')
        self.charge(write=0 if precharged else len(body)); self.guard(reserve=len(body)+65536)
        with path.open('xb') as stream:
            path.chmod(0o444); stream.write(body); stream.flush(); os.fsync(stream.fileno())
        self.guard()
        return c.pin(body)

    def state(self):
        return {'precharged_managed_write_bytes':self.written, 'precharged_managed_read_bytes':self.read,
                'retained_bytes':self.guard(), 'retained_limit_bytes':RETAINED,
                'write_limit_bytes':WRITES, 'read_limit_bytes':READS}


def tree_pins(root, *, file_limit=256, byte_limit=32*1024**2):
    root = Path(root); result = {}; total = 0; nodes = 0; pending = [root]
    c.need(root.is_dir() and not root.is_symlink(),'ordinary input root')
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                nodes += 1; c.need(nodes <= 512 and not entry.is_symlink(),'bounded unlinked input tree')
                path = Path(entry.path)
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path);continue
                c.need(len(result)<file_limit,'bounded complete input file roster')
                body=c.capture(path,byte_limit-total);total+=len(body)
                result[path.relative_to(root).as_posix()]=c.pin(body)
    return dict(sorted(result.items()))


def verify_tree(root, expected, budget):
    budget.charge(read=sum(p['bytes'] for p in expected.values()))
    actual = tree_pins(root)
    c.need(actual == expected, 'immutable complete source/input tree')
    return actual


def retire_tree(root, expected, budget):
    """Only exact verified task-created views are retired, after context closure."""
    root = budget.owned(root); verify_tree(root, expected, budget)
    for name in expected:
        (root/name).unlink()
    directories = sorted((p for p in root.rglob('*') if p.is_dir()), key=lambda p:len(p.parts), reverse=True)
    for path in directories:
        path.rmdir()
    root.rmdir()
    c.need(not root.exists(), 'previous labelled fold view absent before next context')


def runtime_selection(seconds, memory, other):
    c.need(type(seconds) is int and 1 <= seconds <= 7200, 'explicit bounded seconds per fold')
    c.need(type(memory) is int and 536870912 <= memory <= 4294967296, 'explicit bounded candidate memory')
    c.need(type(other) is int and other >= 0, 'external reservations required')
    return {'candidate_seconds':seconds, 'memory_bytes':memory, 'cpu':1,
            'folds_per_arm':44, 'arms':list(c.ARMS), 'per_fold_wall_seconds':seconds+420,
            'worker_wall_seconds':88*(seconds+420)+180, 'outer_wall_seconds':88*(seconds+420)+240,
            'retained_limit_bytes':RETAINED, 'write_limit_bytes':WRITES, 'read_limit_bytes':READS,
            'automatic_retry':False}


def verify_source(expected_sha):
    c.need(isinstance(expected_sha,str) and len(expected_sha)==64, 'operator frozen source descriptor SHA256')
    raw = c.capture(HERE/'SOURCE_MANIFEST.json',100_000)
    c.need(c.pin(raw)['sha256']==expected_sha, 'source descriptor identity')
    manifest = json.loads(raw)
    for row in manifest['files']:
        c.need(c.pin(c.capture(HERE/row['path'],200_000)) == {k:row[k] for k in ('bytes','sha256')}, 'complete source closure')
    for row in manifest['dependencies']:
        c.need(c.pin(c.capture(HERE.parent/row['path'],200_000)) == {k:row[k] for k in ('bytes','sha256')}, 'frozen scientific dependency')
    return c.pin(raw)


def save_files(root, bodies, budget):
    pins = {}
    for name, body in sorted(bodies.items()):
        target = root/name; budget.parents(target.parent)
        pins[name] = budget.save(target, body,32*1024**2)
    return pins


def source_snapshot(pair, contents, root, budget):
    snapshot = root/'programs'; budget.mkdir(snapshot,0o755)
    results = {}
    for arm in c.ARMS:
        directory = snapshot/arm; budget.mkdir(directory,0o755)
        results[arm] = (directory,save_files(directory,contents[arm],budget))
    budget.save(root/'PAIR_SEAL.json',c.encoded(pair),200_000)
    return results


def run_pair(bank, assets_by_arm, pair, contents, root, runtime, source_pin, docker, *,
             enforce_space=True, other_reserve_bytes=0, lifecycle=None, material_builder=None,
             source_checker=None):
    """Trusted orchestration; injected boundaries are only for generated controls.

    The public CLI supplies the frozen bank, exact assets and real reused Docker
    lifecycle. It never accepts a candidate-provided lifecycle/receipt backend.
    """
    c.check_pair(pair,contents)
    modules = c.load_reused(); actual_lifecycle = modules['lifecycle']
    lifecycle = actual_lifecycle.lifecycle if lifecycle is None else lifecycle
    material_builder = materials.build_materials if material_builder is None else material_builder
    current = materials.load_current()
    started = time.monotonic(); end = started + runtime['worker_wall_seconds']
    budget = Budget(root,other_reserve_bytes,enforce_space=enforce_space)
    # Includes complete program capture, source/dependency metadata and paired assets
    # already authenticated before the first possible label materialization.
    budget.charge(write=TERMINAL_RECEIPTS,read=2*c.PROGRAM_LIMIT+2*1024**2)
    c.need(set(bank.metadata['expected_neurons']) == set(bank.roster['expected_neurons'])
           and len(bank.metadata['expected_neurons']) == 44, 'all44 folds required')
    programs = source_snapshot(pair,contents,budget.root,budget)
    # Both complete programs and both arm inputs are frozen before first label view.
    budget.save(budget.root/'RUNTIME.json',c.encoded(runtime),20_000)
    budget.save(budget.root/'OPERATOR_CENSUS.json',c.encoded(bank.roster),200_000)
    budget.save(budget.root/'ASSET_PINS.json',c.encoded({a:{n:c.pin(b) for n,b in files.items()} for a,files in assets_by_arm.items()}),100_000)
    records = []; common_packets = {}; all_results = {}; all_contexts = set()
    actual_lifecycle.WRITE = budget
    try:
        for arm in c.ARMS:
            c.check_pair(pair,contents)
            arm_root = budget.root/arm; budget.mkdir(arm_root)
            folds = arm_root/'folds'; budget.mkdir(folds)
            candidate = arm_root/'candidate'; budget.mkdir(candidate)
            unit = pair['arms'][arm]['seal']['configuration']['output_unit']
            purpose = pair['arms'][arm]['seal']['configuration']['purpose']
            program_dir, program_files = programs[arm]
            candidate_records = []; seen = set(); contexts = set()
            for held in bank.metadata['expected_neurons']:
                c.need(time.monotonic()+runtime['per_fold_wall_seconds']+60 < end, 'whole paired campaign deadline')
                c.check_pair(pair,contents); verify_tree(program_dir,program_files,budget)
                budget.charge(read=512*1024)  # complete source/asset descriptor rechecks
                if source_checker:
                    source_checker()
                attempt = folds/held; budget.mkdir(attempt)
                selected = {'held_neuron':held,'arm':arm,'selected_seconds':runtime['per_fold_wall_seconds']}
                records.append(selected); budget.save(attempt/'SELECTED.json',c.encoded(selected),4096)
                view = attempt/'input'; budget.mkdir(view,0o755)
                # Conservative precharge covers all allowed record payload reads.
                plan = materials.select_fold(bank,held)
                budget.charge(read=sum(r['operator_payload']['bytes'] for r in plan['training_rows']+plan['query_rows']))
                projected = material_builder(bank,held,arm,purpose)
                bodies = materials.material_bytes(projected,assets_by_arm[arm])
                input_files = save_files(view,bodies,budget)
                common = {name:value for name,value in input_files.items() if not name.startswith('author-code/') and name!='FOLD.json'}
                common['FOLD_COMMON'] = c.pin(c.encoded({k:v for k,v in projected['manifest'].items() if k!='arm'}))
                if arm == c.ARMS[0]:
                    common_packets[held] = common
                else:
                    c.need(common_packets[held] == common, 'same paper/data bytes across access arms')
                binding = c.fold_binding(pair,arm,projected['manifest'],bodies)
                trusted = attempt/'trusted'; budget.mkdir(trusted,0o755)
                for name in ('holder.py','entry.py'):
                    budget.save(trusted/name,c.capture(HERE/'reused'/name,100_000),100_000)
                budget.save(trusted/'PROGRAM_BINDING.json',c.encoded(binding),100_000)
                n = sum(r['samples'] for r in binding['query_records'])
                c.need(8*n+1036 <= 1_000_000, 'whole query fits reviewed holder capture')
                lock = {'schema':'cascade_spinal_capture_lock_v1','prediction_max_bytes':8*n+1036}
                budget.save(trusted/'CAPTURE_LOCK.json',c.encoded(lock),4096)
                cfg = {k:runtime[k] for k in ('candidate_seconds','memory_bytes')}
                cfg.update(program_directory=program_dir,program_files=program_files,
                           program_seal=pair['arms'][arm]['seal_pin'],source_manifest=source_pin,
                           runtime_contract=c.pin(c.encoded(runtime)))
                def unchanged():
                    verify_tree(program_dir,program_files,budget)
                    return verify_tree(view,input_files,budget)
                result = lifecycle(docker,trusted,cfg,lock,{name:view/name for name in input_files},attempt,
                                   unchanged,min(end-60,time.monotonic()+runtime['per_fold_wall_seconds']))
                budget.save(attempt/'LIFECYCLE.json',c.encoded(result),200_000)
                collector.closed(result)
                c.need(result['schema']=='cascade44_fold_lifecycle_v1'
                       and result['program_seal']==cfg['program_seal']
                       and result['source_manifest']==source_pin
                       and result['runtime_contract']==cfg['runtime_contract']
                       and result['public_post_pin']==input_files
                       and result['image']==modules['runtime'].IMAGE
                       and result['candidate_seconds']==runtime['candidate_seconds']
                       and result['memory_bytes']==runtime['memory_bytes']
                       and result['candidate_started'] is True
                       and result['private_scoring_called'] is False,
                       'trusted live lifecycle joins frozen program/source/runtime/input pins')
                namespace = result['namespace']
                c.need(namespace not in all_contexts, 'fresh context for every fold across both arms')
                contexts.add(namespace); all_contexts.add(namespace)
                output_pins = {r['path']:{k:r[k] for k in ('bytes','sha256')} for r in result['outputs']}
                budget.charge(read=sum(p['bytes'] for p in output_pins.values()))
                values = collector.collect_fold(binding,result,attempt/'captured',current)
                c.need(set(values) == {r['recording_id'] for r in plan['query_rows']}, 'all held eligible recording predictions')
                for identity, vector in values.items():
                    c.need(identity not in seen, 'one held prediction per eligible recording'); seen.add(identity)
                    filename = f'prediction-{len(candidate_records):03d}.npz'
                    stream = io.BytesIO(); np.savez(stream,candidate=vector)
                    descriptor = budget.save(candidate/filename,stream.getvalue(),1_000_000)
                    candidate_records.append({'recording_id':identity,'payload':{'path':filename,**descriptor}})
                proof = {'held_neuron':held,'arm':arm,'binding':c.pin(c.encoded(binding)),
                         'input_files':input_files,'program_seal':cfg['program_seal'],
                         'lifecycle':c.pin(c.encoded(result)), 'held_all_source_records_excluded':plan['held_source_excluded_ids'],
                         'query_recording_ids':[r['recording_id'] for r in plan['query_rows']],
                         'fresh_context_namespace':namespace,'candidate_closed_before_capture':True}
                budget.save(attempt/'FOLD_PROOF.json',c.encoded(proof),100_000)
                # Never carry labelled views, scratch or prior candidate outputs into next context.
                retire_tree(view,input_files,budget)
                retire_tree(trusted,tree_pins(trusted),budget)
                c.need(not view.exists() and not trusted.exists(), 'retired previous context views')
                budget.save(attempt/'RETIRED.json',c.encoded({'input_absent':True,'trusted_absent':True}),4096)
            c.need(len(contexts)==44 and len(seen)==116, 'complete44fold116record arm')
            output_manifest = collector.manifest(bank,unit,candidate_records,
                'Produced by current-condition fresh-container program transport; model identity/training provenance is not independently qualified.')
            manifest_pin = budget.save(candidate/'PREDICTIONS.json',c.encoded(output_manifest),100_000)
            all_results[arm] = {'folds':44,'eligible_recordings':116,'prediction_manifest':manifest_pin,
                                'program_seal':pair['arms'][arm]['seal_pin']}
        c.need(set(all_results)==set(c.ARMS) and len(all_contexts)==88, 'both matched access arms complete')
        if source_checker:
            source_checker()
        done = {'schema':'spinal_current_transport_complete_v1','condition_id':c.CONDITION,
                'bank_manifest_sha256':bank.manifest_sha256,'pair_pin':pair['pair_pin'],
                'source_manifest':source_pin,'arms':all_results,'source_recording_census':132,
                'eligible_recordings':116,'noise_exclusions':16,'required_neurons':44,
                'same_data_across_arms':True,'model_training_provenance_qualified':False,
                'scientific_scoring_performed':False,'requires_observed_outer_exit_zero':True,
                'selected_fold_seconds':sum(r['selected_seconds'] for r in records),
                'elapsed_seconds':time.monotonic()-started,'budget':budget.state(),
                'budget_snapshot_stage':'before_worker_complete_and_host_exit',
                'terminal_receipts_precharged_bytes':TERMINAL_RECEIPTS}
        budget.save(budget.root/'WORKER_COMPLETE.json',c.encoded(done),100_000,precharged=True)
        return done
    except BaseException as error:
        failure = {'schema':'spinal_current_transport_failure_v1','error_type':type(error).__name__,
                   'selected_folds':records,'automatic_retry':False,'completion_claimed':False,
                   'partial_operator_materials_may_remain':True}
        try:
            budget.save(budget.root/'FAILED.json',c.encoded(failure),100_000)
        except BaseException:
            pass
        raise


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('bank','assets','program-a','program-b','output','docker','docker-socket'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--source-sha256',required=True)
    p.add_argument('--purpose',choices=('reproduction','improvement'),required=True)
    p.add_argument('--unit',choices=('hz','expected_spikes_per_bin'),required=True)
    p.add_argument('--candidate-seconds',type=int,required=True)
    p.add_argument('--memory-bytes',type=int,required=True)
    p.add_argument('--other-reserve-bytes',type=int,required=True)
    p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    return p


def main():
    args=parser().parse_args(); source=verify_source(args.source_sha256)
    runtime=runtime_selection(args.candidate_seconds,args.memory_bytes,args.other_reserve_bytes)
    modules=c.load_reused()
    if args.worker:
        def expired(signum,frame):
            raise TimeoutError('fixed worker deadline')
        signal.signal(signal.SIGALRM,expired)
        signal.setitimer(signal.ITIMER_REAL,runtime['worker_wall_seconds']-35)
        pair,contents=c.freeze_pair(args.program_a,args.program_b,args.purpose,args.unit)
        c.check_pair(pair,contents)
        current=materials.load_current(); bank=current.load_bank(args.bank)
        assets={arm:materials.capture_assets(args.assets,arm) for arm in c.ARMS}
        docker=modules['runtime'].Docker(str(args.docker.absolute()),args.docker_socket)
        result=run_pair(bank,assets,pair,contents,args.output,runtime,source,docker,
                        other_reserve_bytes=args.other_reserve_bytes,source_checker=lambda:verify_source(args.source_sha256))
        signal.setitimer(signal.ITIMER_REAL,0)
        print(json.dumps({'complete':True,'source_manifest':source,'folds':88,'scientific_scoring':False}))
        return
    c.need(not args.output.exists(), 'fresh output before worker')
    deadline=time.monotonic()+runtime['outer_wall_seconds']
    env=os.environ.copy(); env.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')})
    command=[sys.executable,'-I','-B',str(Path(__file__).resolve()),*sys.argv[1:],'--worker']
    try:
        stdout,observation=modules['child'].child(command,deadline,env)
    except modules['child'].ChildFailure as error:
        print(json.dumps({'outer_exit_admitted':False,'observation':error.record}),file=sys.stderr)
        raise
    expected={'complete':True,'source_manifest':source,'folds':88,'scientific_scoring':False}
    c.need(json.loads(stdout)==expected, 'exact trusted worker completion join')
    verify_source(args.source_sha256)
    completion=capture_completion(args.output,source)
    result={'schema':'spinal_current_transport_host_exit_v1','worker_observation':observation,
            'source_manifest':source,'worker_complete':completion,'scientific_scoring':False,
            'external_supervisor_exit_zero_still_required':True}
    terminal=c.encoded(result);c.need(len(terminal)<=100_000,'precharged bounded outer receipt')
    c.need(shutil.disk_usage(args.output).free >= FLOOR+args.other_reserve_bytes+RETAINED,
           'preserve free-disk reserve for outer receipt')
    retained_tree(args.output,len(terminal)+65536)
    with (args.output/'HOST_EXIT.json').open('xb') as stream:
        (args.output/'HOST_EXIT.json').chmod(0o600);stream.write(terminal);stream.flush();os.fsync(stream.fileno())
    retained_tree(args.output)
    c.need(time.monotonic()<deadline, 'fixed outer deadline')
    print(json.dumps({'host_complete':True,'folds':88,'scientific_scoring':False}))


def capture_completion(root,source):
    body=c.capture(Path(root)/'WORKER_COMPLETE.json',100_000); value=json.loads(body)
    c.need(value['source_manifest']==source and value['required_neurons']==44
           and set(value['arms'])==set(c.ARMS) and all(v['folds']==44 and v['eligible_recordings']==116 for v in value['arms'].values()),
           'complete trusted paired worker result')
    return c.pin(body)


if __name__=='__main__':
    main()
