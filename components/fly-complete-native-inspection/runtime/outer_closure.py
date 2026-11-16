"""After the sole owner exits, probe only its recorded PID/group identities."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time


def main(request_path, dispatch_path, output_path):
    spec = importlib.util.spec_from_file_location('fly_fixed_owner', Path(__file__).with_name('owner.py'))
    owner = importlib.util.module_from_spec(spec); spec.loader.exec_module(owner)
    req, body = owner.read_request(request_path, fresh=False)
    base = owner.module('fly_admitted_small_owner', req['base_owner'])
    def read(path):
        with open(path, 'rb') as handle: raw = handle.read(262145)
        owner.need(len(raw) <= 262144, 'bounded closure metadata')
        return json.loads(raw, object_pairs_hook=owner.strict_pairs)
    dispatch = read(dispatch_path); digest = hashlib.sha256(body).hexdigest()
    expected_argv = [req['python'], '-I', '-S', '-B', req['sources'][0]['path'],
                     '--request', str(Path(request_path).absolute())]
    owner.need(dispatch['argv'] == expected_argv and dispatch['owner_source'] == req['sources'][0],
               'dispatch fixed source and argv')
    owner.need(dispatch['request_sha256'] == digest and dispatch['pid'] == dispatch['pgid']
               and type(dispatch['pid']) is int and dispatch['pid'] > 1, 'dispatch owner identity')
    root = Path(req['owner_output']); pids = {dispatch['pid']}; state = None
    result_path = root/'OWNER_RESULT.json'
    if result_path.exists():
        state = read(result_path)
        owner.need(state['owner_pid'] == dispatch['pid'] and state['owner_pgid'] == dispatch['pgid']
                   and state['request_sha256'] == digest, 'owner result identity')
        for stage in state['stages']:
            if stage['pid'] is not None:
                owner.need(type(stage['pid']) is int and stage['pid'] > 1, 'recorded child identity')
                pids.add(stage['pid'])
    for label in ('VM', 'PRODUCE', 'AUDIT'):
        path = root/(label+'_BIRTH.json')
        if path.exists():
            birth = read(path)
            owner.need(birth['parent_pid'] == dispatch['pid'] and birth['pid'] == birth['pgid']
                       and type(birth['pid']) is int and birth['pid'] > 1, 'birth identity')
            pids.add(birth['pid'])
    probes = []
    for pid in sorted(pids):
        row = dict(pid=pid)
        for name, probe in (('pid_absent', lambda: os.kill(pid, 0)),
                            ('group_absent', lambda: os.killpg(pid, 0))):
            try: probe(); row[name] = False
            except ProcessLookupError: row[name] = True
            except OSError as error: row[name] = None; row[name+'_errno'] = error.errno
        probes.append(row)
    absent = all(r['pid_absent'] is True and r['group_absent'] is True for r in probes)
    record = dict(schema='fly-native-inspection-outer-closure-v1', observed_at_unix_ns=time.time_ns(),
        request_sha256=digest, known_process_probes=probes, all_known_absent=absent,
        owner_result_present=state is not None,
        operation_complete=absent and state is not None and
            state['status'] == 'complete_native_inspection_and_independent_audit_owned_closed',
        limitation='Known recorded identities only; missing owner result never establishes complete operation.',
        signals_sent=[], scientific_admission=False)
    base.write(Path(output_path), record)
    print(json.dumps({'all_known_absent': absent, 'operation_complete': record['operation_complete']}))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    for name in ('request', 'dispatch', 'output'): parser.add_argument('--'+name, required=True)
    args = parser.parse_args(); main(args.request, args.dispatch, args.output)
