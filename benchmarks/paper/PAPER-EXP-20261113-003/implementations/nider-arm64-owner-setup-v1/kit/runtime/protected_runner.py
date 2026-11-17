"""Owner-controlled four-case Docker runner. SOURCE ONLY until selected.

One immutable candidate R artifact is run in four fresh offline containers. No
candidate code executes on the host. Scores are computed only after all cases
close; no target or interim feedback enters a candidate mount or environment.
"""
import hashlib
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time

from custody import Invalid, decode, encoded, need, pin, plain, read_pin, write_new
from owner_binding import admit_catalogue, admit_materials, stage_exposure
import runtime_policy as rp
from scientific_score import assemble_responses, normalize_case_response, score_submission

SOURCE_NAMES = {'custody.py', 'reporting_core.py', 'scientific_score.py', 'owner_binding.py', 'protected_runner.py', 'runtime_policy.py', 'build_spec.py', 'DEPENDENCIES.json'}


def validate_outcome(record):
    need(record['reason'] is None and record['exit_code'] == 0 and record['reaped'] and
         record['EOF'] == ['stderr', 'stdout'] and not record['truncated'], 'execution_incomplete_or_resource_failure')


def bounded_process(argv, seconds, stdout_path, stderr_path, cap=65536):
    """Capture child pipes concurrently; kill only this owned process group."""
    need(type(argv) is list and all(type(x) is str for x in argv) and 0 < seconds <= 180, 'process_spec')
    started = time.monotonic()
    proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True)
    selector = selectors.DefaultSelector()
    streams = {'stdout': proc.stdout, 'stderr': proc.stderr}
    files = {}; lengths = {'stdout': 0, 'stderr': 0}; eof = []; reason = None; truncated = False
    killed_at = None
    exit_code = None; reaped = False
    try:
        for name, stream in streams.items():
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
            files[name] = plain(stdout_path if name == 'stdout' else stderr_path).open('xb')
            os.chmod(files[name].name, 0o600)
        while selector.get_map():
            now = time.monotonic()
            if now - started > seconds and reason is None:
                reason = 'wall_limit'
            if reason and killed_at is None:
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                killed_at = now
            if killed_at is not None and now - killed_at > 5:
                break
            for key, _ in selector.select(.05):
                name = key.data
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    eof.append(name); selector.unregister(key.fileobj); continue
                room = max(0, cap - lengths[name])
                files[name].write(chunk[:room]); lengths[name] += len(chunk)
                if len(chunk) > room:
                    reason = reason or 'stream_extent'; truncated = True
        try:
            exit_code = proc.wait(timeout=5)
            reaped = True
        except subprocess.TimeoutExpired:
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            exit_code = proc.wait(timeout=5); reaped = True; reason = reason or 'post_EOF_reap_timeout'
    finally:
        if proc.poll() is None:
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            proc.wait(timeout=5)
        selector.close()
        for stream in streams.values(): stream.close()
        for stream in files.values(): stream.close()
    return {'argv': argv, 'exit_code': exit_code, 'reason': reason, 'elapsed_seconds': time.monotonic() - started,
            'EOF': sorted(eof), 'reaped': reaped, 'truncated': truncated,
            'observed_pipe_bytes_at_least': lengths,
            'stdout': pin(Path(stdout_path).read_bytes(), stdout_path),
            'stderr': pin(Path(stderr_path).read_bytes(), stderr_path)}


def candidate_argv(name, stage, paper, program, runtime):
    """Finite allowlist. No Docker socket, network, owner root or output mount."""
    return ['docker', 'create', '--pull=never', '--name', name,
            '--network=none', '--read-only', '--cpus=1', '--memory=2g', '--memory-swap=2g',
            '--pids-limit=64', '--log-driver=none', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--user=' + rp.user(runtime), '--workdir=/work',
            '--tmpfs=/work:rw,nosuid,nodev,size=134217728,mode=1777',
            '--tmpfs=/tmp:rw,nosuid,nodev,size=134217728,mode=1777',
            '--ulimit=nofile=1024:1024', '--ulimit=fsize=1048576:1048576',
            '--mount', f'type=bind,src={stage},dst=/input,readonly',
            '--mount', f'type=bind,src={paper},dst=/paper/article.pdf,readonly',
            '--mount', f'type=bind,src={program},dst=/candidate/solution.R,readonly',
            '--label', 'nider.owner=' + name,
            '--entrypoint=/usr/local/bin/Rscript', runtime['image'], '--vanilla', '/candidate/solution.R']


def validate_inspection(obj, cid, expected_mounts, name, runtime, final=False):
    need(type(obj) is list and len(obj) == 1, 'container_inspection')
    item = obj[0]; host = item['HostConfig']; state = item['State']
    need(item['Id'] == cid and item['Image'] == runtime['image'] and item['RestartCount'] == 0, 'container_identity')
    config=item['Config']
    need(item['Name']=='/'+name and config['Labels'].get('nider.owner')==name and
         config['Entrypoint']==['/usr/local/bin/Rscript'] and config['Cmd']==['--vanilla','/candidate/solution.R'] and
         config['User']==rp.user(runtime) and config['WorkingDir']=='/work', 'container_process_configuration')
    need(host['NetworkMode'] == 'none' and host['ReadonlyRootfs'] is True and host['Memory'] == 2147483648 and
         host['MemorySwap'] == 2147483648 and host['NanoCpus'] == 1000000000 and host['PidsLimit'] == 64 and
         host['LogConfig']['Type'] == 'none' and host['CapDrop'] == ['ALL'], 'container_resources')
    need(host['SecurityOpt']==['no-new-privileges'] and host['UsernsMode']=='' and host['Privileged'] is False, 'container_security_options')
    need(host['Tmpfs']=={'/work':'rw,nosuid,nodev,size=134217728,mode=1777','/tmp':'rw,nosuid,nodev,size=134217728,mode=1777'}, 'container_tmpfs')
    limits={(x['Name'],x['Soft'],x['Hard']) for x in host['Ulimits']}
    need(limits=={('nofile',1024,1024),('fsize',1048576,1048576)} and len(host['Ulimits'])==2,'container_ulimits')
    actual = {(x['Source'], x['Destination'], x['RW']) for x in item['Mounts'] if x['Type'] == 'bind'}
    need(actual == expected_mounts and len([x for x in item['Mounts'] if x['Type'] == 'bind']) == 3, 'container_mounts')
    need(all(x['Type'] in ('bind', 'tmpfs') for x in item['Mounts']), 'unexpected_container_volume')
    if final:
        need(state['Status'] == 'exited' and state['ExitCode'] == 0 and not state['Running'] and not state['OOMKilled'] and
             not state['Error'] and not state['Paused'] and not state['Restarting'], 'candidate_container_failure')
    else:
        need(state['Status'] == 'created' and not state['Running'], 'initial_container_state')
    return item


def run(plan_pin):
    """Trusted owner CLI supplies the pinned plan; candidate cannot choose it."""
    plan = decode(read_pin(plan_pin))
    required = {'schema', 'selection_id', 'owner_root', 'catalogue', 'materials', 'program', 'arm', 'sources', 'runtime_policy'}
    need(type(plan) is dict and set(plan) == required and plan['schema'] == 'nider_protected_runner_plan_v1', 'plan_schema')
    need(plan['arm'] in ('A', 'B') and type(plan['selection_id']) is str and 1 <= len(plan['selection_id']) <= 100, 'plan_identity')
    need(type(plan['sources']) is dict and set(plan['sources']) == SOURCE_NAMES, 'complete_source_binding')
    for name, entry in plan['sources'].items():
        read_pin(entry)
        need(Path(entry['path']) == Path(__file__).with_name(name), 'source_location')
    root = plain(plan['owner_root']); root.mkdir(mode=0o700)
    logs = root / 'logs'; logs.mkdir(mode=0o700)
    write_new(root / 'ATTEMPT_GUARD.json', encoded({'plan': plan_pin, 'selection_id': plan['selection_id']}))
    began = time.monotonic(); calls = []; cases_run = []; failure = None; active_cid = None; active_name = None
    cleanup = []; responses = []; admitted_pins = []; counter = 0; created_cids = []; live_pin = None
    # The separately bounded outer observer signals this owner, which must
    # unwind through exact-CID cleanup rather than abandon a live container.
    def outer_cancel(_signum, _frame):
        raise Invalid('outer_observer_cancelled')
    previous_term = signal.signal(signal.SIGTERM, outer_cancel)

    def call(argv, seconds=5, cleanup_call=False):
        nonlocal counter
        counter += 1
        remaining = 180 - (time.monotonic() - began)
        need(cleanup_call or remaining > 0, 'whole_runner_wall_limit')
        duration = seconds if cleanup_call else min(seconds, remaining)
        record = bounded_process(argv, duration, logs / f'{counter:02d}.stdout', logs / f'{counter:02d}.stderr')
        calls.append(record)
        need(cleanup_call or sum(sum(min(65536, n) for n in x['observed_pipe_bytes_at_least'].values()) for x in calls) <= 786432, 'whole_stream_budget')
        validate_outcome(record)
        return decode(Path(record['stdout']['path']).read_bytes()) if argv[1:2] == ['inspect'] else Path(record['stdout']['path']).read_bytes()

    def clean():
        nonlocal active_cid, active_name
        if active_cid is None: return
        cid, name = active_cid, active_name
        call(['docker', 'rm', '-f', cid], cleanup_call=True)
        by_id = call(['docker', 'ps', '-aq', '--no-trunc', '--filter', f'id={cid}'], cleanup_call=True)
        by_name = call(['docker', 'ps', '-aq', '--no-trunc', '--filter', f'name=^/{name}$'], cleanup_call=True)
        need(not by_id.strip() and not by_name.strip(), 'owned_container_cleanup_absence')
        cleanup.append({'cid': cid, 'name': name, 'removed_and_absence_verified': True})
        active_cid = active_name = None

    try:
        runtime = rp.admit(plan['runtime_policy'])
        def runtime_json(argv):
            value = call(argv)
            return value if type(value) in (dict,list) else decode(value)
        live = rp.observe_live(runtime, runtime_json)
        live_pin = write_new(root / 'RUNTIME_ADMISSION.json', encoded(live))
        catalogue, cases = admit_catalogue(plan['catalogue'])
        need(catalogue['runtime_policy'] == plan['runtime_policy'], 'runner_catalogue_runtime_join')
        material, paper_raw = admit_materials(plan['materials'])
        program_raw = read_pin(plan['program'], 262144)
        program = root / 'solution.R'; paper = root / 'article.pdf'
        admitted_pins += [write_new(program, program_raw), write_new(paper, paper_raw)]
        rp.owned_files(runtime, admitted_pins)
        for number, case in enumerate(cases):
            read_pin(plan['program'], 262144)
            stage = root / f'input_{number}'
            staged = stage_exposure(stage, case, catalogue, plan['arm']); admitted_pins += staged
            rp.owned_files(runtime, staged)
            name = 'nider-protected-' + hashlib.sha256((str(root) + ':' + str(number)).encode()).hexdigest()[:24]
            need(not call(['docker', 'ps', '-aq', '--no-trunc', '--filter', f'name=^/{name}$']).strip(), 'fresh_container_name')
            active_name = name
            argv = candidate_argv(name, stage, paper, program, runtime)
            created = call(argv).decode().strip()
            need(len(created) == 64 and all(c in '0123456789abcdef' for c in created), 'created_container_id')
            active_cid, active_name = created, name
            created_cids.append(created)
            mounts = {(str(stage), '/input', False), (str(paper), '/paper/article.pdf', False), (str(program), '/candidate/solution.R', False)}
            initial = call(['docker', 'inspect', created]); validate_inspection(initial, created, mounts, name, runtime)
            response_raw = call(['docker', 'start', '-a', created], seconds=30)
            final = call(['docker', 'inspect', created]); validate_inspection(final, created, mounts, name, runtime, final=True)
            clean()
            for entry in staged: read_pin(entry)
            item = normalize_case_response(response_raw, case)
            responses.append(item)
            cases_run.append({'case_id': case['case_id'], 'workbook_sha256': case['workbook']['sha256'],
                              'program_sha256': plan['program']['sha256'], 'response_sha256': hashlib.sha256(response_raw).hexdigest(),
                              'container': created, 'closed': True})
        need(len(responses) == 4, 'complete_four_executions')
        for entry in admitted_pins: read_pin(entry, maximum=8388608)
        raw = assemble_responses(responses, plan['arm'])
        write_new(root / 'CANDIDATE_SUBMISSION.json', raw)
        score = score_submission(raw, cases, plan['arm'])
        score['candidate_execution_verified'] = True
        score['same_program_all_four_cases'] = True
        write_new(root / 'PRIVATE_SCORE.json', encoded(score))
    except Exception as error:
        failure = {'class': type(error).__name__, 'code': str(error) if isinstance(error, Invalid) else 'unexpected_owner_failure'}
    finally:
        # A create command may have completed daemon-side before its client
        # timed out. Recover only the uniquely named and owner-labelled CID.
        if active_cid is None and active_name is not None:
            try:
                recovered = call(['docker', 'ps', '-aq', '--no-trunc', '--filter', f'name=^/{active_name}$',
                                  '--filter', 'label=nider.owner=' + active_name], cleanup_call=True).decode().strip()
                if recovered:
                    need(len(recovered) == 64 and all(c in '0123456789abcdef' for c in recovered), 'unique_recovered_CID')
                    observation = call(['docker', 'inspect', recovered], cleanup_call=True)
                    need(len(observation) == 1 and observation[0]['Id'] == recovered and
                         observation[0]['Config']['Labels'].get('nider.owner') == active_name, 'recovered_owned_identity')
                    active_cid = recovered
                    if recovered not in created_cids: created_cids.append(recovered)
            except Exception:
                failure = {'class': 'OwnedCreateRecovery', 'code': 'owned_create_recovery_unverified', 'preceding_failure': failure}
        if active_cid is not None:
            try: clean()
            except Exception as error:
                failure = {'class': type(error).__name__, 'code': 'owned_cleanup_unverified', 'preceding_failure': failure}
        lifecycle = {'schema': 'nider_protected_runner_lifecycle_v1', 'selection_id': plan['selection_id'],
                     'plan': plan_pin, 'runtime_policy': plan['runtime_policy'], 'runtime_admission': live_pin, 'cases': cases_run, 'calls': calls, 'cleanup': cleanup,
                     'failure': failure, 'elapsed_seconds': time.monotonic() - began,
                     'all_four_closed': len(cases_run) == 4 and len(cleanup) == 4,
                     'created_CIDs': created_cids,
                     'all_owned_containers_removed': active_cid is None and set(created_cids) == {x['cid'] for x in cleanup} and
                         not (failure and failure.get('code') in ('owned_create_recovery_unverified','owned_cleanup_unverified')),
                     'score_written': (root / 'PRIVATE_SCORE.json').is_file(),
                     'retained_file_pins': [pin(p.read_bytes(), p) for p in sorted(root.rglob('*')) if p.is_file()],
                     'private_output_only': True, 'scientifically_qualified_benchmark': False}
        write_new(root / 'LIFECYCLE.json', encoded(lifecycle))
        signal.signal(signal.SIGTERM, previous_term)
    return 0 if failure is None else 1


if __name__ == '__main__':
    # A selected owner launches this script with a private plan path and digest.
    # This entry point does not accept a candidate-supplied scoring universe.
    need(len(sys.argv) == 3, 'owner_plan_and_digest_required')
    p = plain(sys.argv[1]); entry = {'path': str(p), 'bytes': p.stat().st_size, 'sha256': sys.argv[2]}
    sys.exit(run(entry))
