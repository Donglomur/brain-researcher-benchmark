"""Complete128-dispatch execution; no target read until all resources close."""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import time
import uuid
import io_utils as safe
import native
import runtime_contract as contract
import views
import budget

RETAIN_MIN = 68719476736


def validate_request(r):
    fields = {'schema', 'fixed_program', 'fixed_program_pin', 'adaptive_driver', 'adaptive_driver_pin',
        'public', 'public_pin', 'private', 'private_pin', 'grader_python', 'docker', 'docker_pin',
        'docker_host', 'docker_config', 'image', 'output', 'candidate_wall_seconds',
        'grade_wall_seconds', 'cleanup_wall_seconds', 'whole_wall_seconds', 'candidate_cpu_seconds',
        'candidate_memory_bytes', 'candidate_nano_cpus', 'host_memory_budget_bytes', 'retention_budget_bytes',
        'submission_cap_bytes'}
    safe.need(type(r) is dict and set(r) == fields and r['schema'] == 'neural030-fixed-adaptive-request-v1', 'Closed request')
    # Private operand admission is lexical only. Do not inspect the target or
    # its ancestors here; safe.read performs filesystem checks in final grade.
    private = r['private']
    safe.need(type(private) is str and private and not any(c in private for c in '\x00\n\r') and
        Path(private).is_absolute() and Path(private).anchor == '/' and
        str(Path(private)) == private and '..' not in Path(private).parts,
        'Canonical lexical private path')
    # Reject an alias into every request-supplied early-read role before even
    # checking another role's filesystem metadata. This is lexical overlap
    # rejection; no private stat/resolve is used to infer physical identity.
    early_roles = ('fixed_program', 'adaptive_driver', 'public', 'docker',
                   'docker_config', 'grader_python', 'output')
    safe.need(type(r['docker_host']) is str and r['docker_host'].startswith('unix:///'),
              'Local explicit daemon')
    for operand in [r[name] for name in early_roles] + [r['docker_host'][7:]]:
        safe.need(type(operand) is str and operand and not any(c in operand for c in '\x00\n\r') and
                  Path(operand).is_absolute() and Path(operand).anchor == '/' and
                  str(Path(operand)) == operand and '..' not in Path(operand).parts,
                  'Canonical lexical early-read operand')
        other = Path(operand); protected = Path(private)
        safe.need(protected != other and protected not in other.parents and other not in protected.parents,
                  'Private operand disjoint from every early-read role')
    for name in ('fixed_program', 'adaptive_driver', 'public', 'docker', 'docker_config', 'output'):
        native.plain_path(r[name])
    for name, cap in (('fixed_program_pin', 1048576), ('adaptive_driver_pin', 1048576),
                      ('public_pin', 64000000), ('private_pin', 64000000), ('docker_pin', 134217728)):
        native.pin(r[name], cap)
    py = r['grader_python']
    safe.need(type(py) is str and Path(py).is_absolute() and str(Path(py)) == py and
              '..' not in Path(py).parts and not any(c in py for c in '\x00\n\r'), 'Trusted grader interpreter')
    safe.need(type(r['image']) is str and re.fullmatch('sha256:[0-9a-f]{64}', r['image']), 'Immutable shared image')
    safe.need(type(r['docker_host']) is str and r['docker_host'].startswith('unix:///'), 'Local explicit daemon')
    native.plain_path(r['docker_host'][7:])
    for name in ('candidate_wall_seconds', 'grade_wall_seconds', 'cleanup_wall_seconds', 'whole_wall_seconds',
                 'candidate_cpu_seconds', 'candidate_memory_bytes', 'candidate_nano_cpus',
                 'host_memory_budget_bytes', 'retention_budget_bytes'):
        safe.need(type(r[name]) is int and r[name] > 0, 'Positive integral budget')
    safe.need(r['cleanup_wall_seconds'] >= 30 and r['whole_wall_seconds'] >=
        128*(r['candidate_wall_seconds']+r['cleanup_wall_seconds']+120) + r['grade_wall_seconds'] +
        r['cleanup_wall_seconds'] + 120, 'Full128 schedule and preparation/cleanup allowances')
    safe.need(r['whole_wall_seconds'] <= 604800 and r['candidate_cpu_seconds'] <= r['candidate_wall_seconds']*8 and
        r['candidate_memory_bytes'] >= 536870912 and r['candidate_nano_cpus'] <= 8000000000, 'Bounded per-case matched resources')
    safe.need(r['host_memory_budget_bytes'] >= 2147483648 and r['retention_budget_bytes'] >= RETAIN_MIN,
        'Prospective whole-panel memory/retention envelope; not measured fit')
    safe.need(type(r['submission_cap_bytes']) is int and 0 < r['submission_cap_bytes'] <= contract.OUTPUT_BYTES,
              'Explicit full-submission cap within native100MB limit')
    budget.admit_bytes(r)
    out = Path(r['output'])
    for name in ('fixed_program', 'adaptive_driver', 'public', 'private', 'docker', 'docker_config', 'grader_python'):
        p = Path(r[name]); safe.need(out != p and out not in p.parents and p not in out.parents, 'Output disjoint from inputs')
    return r


def invoke(r, job, case_dir, program, holder_source, end, event):
    """One new Docker resource set per case/arm/mode. Never reuse writable state."""
    commands = job/'commands'; commands.mkdir(mode=0o700)
    capture = job/'capture'; capture.mkdir(mode=0o777); capture.chmod(0o777)
    engine = native.Docker(r, commands, end)
    suffix = uuid.uuid4().hex
    volume, holder, candidate = ('neural030-'+role+'-'+suffix for role in ('output', 'holder', 'candidate'))
    failure = None
    try:
        engine.volume(volume)
        engine.create(holder, 'holder', {
            '/trusted/holder.py': {'type': 'bind', 'source': str(holder_source), 'rw': False},
            '/capture': {'type': 'volume', 'source': volume, 'rw': False},
            '/export': {'type': 'bind', 'source': str(capture), 'rw': True}})
        safe.need(engine.call(['start', holder])['returncode'] == 0 and
            engine.inspect('container', holder)['State']['Running'] is True, 'Output holder alive')
        engine.create(candidate, 'candidate', {
            '/program/candidate.py': {'type': 'bind', 'source': str(program), 'rw': False},
            '/input/public': {'type': 'bind', 'source': str(case_dir), 'rw': False},
            '/output': {'type': 'volume', 'source': volume, 'rw': True}})
        start = time.monotonic()
        safe.need(engine.call(['start', candidate])['returncode'] == 0, 'Candidate start')
        remaining = r['candidate_wall_seconds']-(time.monotonic()-start)
        safe.need(remaining > 0, 'Start included in candidate wall budget')
        waited = engine.call(['wait', candidate], remaining)
        state = engine.inspect('container', candidate)['State']
        safe.need(waited['returncode'] == 0 and waited['stdout'].strip() == '0' and
            state['Running'] is False and state['Pid'] == 0 and state['OOMKilled'] is False and
            state['ExitCode'] == 0 and time.monotonic()-start <= r['candidate_wall_seconds'], 'Successful bounded candidate termination')
        engine.remove('container', candidate)
        captured = engine.call(['exec', holder, 'python', '-I', '-B', '/trusted/holder.py', 'capture'], 30)
        safe.need(captured['returncode'] == 0 and not captured['stderr'], 'Closed-producer output capture')
        descriptor = safe.strict(captured['stdout'])
        safe.need(type(descriptor) is dict and set(descriptor) == {'status', 'bytes', 'sha256'} and
            descriptor['status'] == 'captured', 'Exact capture descriptor')
        output_pin = native.pin({k: descriptor[k] for k in ('bytes', 'sha256')}, r['submission_cap_bytes'])
        engine.end = min(end, time.monotonic()+r['cleanup_wall_seconds'])
        safe.need(not engine.close(), 'Every owned case resource absent')
        raw = native.read_pinned(capture/'submission.json', output_pin, r['submission_cap_bytes'])
        safe.need({p.name for p in capture.iterdir()} == {'submission.json'}, 'Exact capture membership')
        native.write_bytes(job/'submission.json', raw)
        event('case_closed', job=job.name, submission=output_pin)
        return safe.strict(raw)
    except BaseException as error:
        failure = error
        raise
    finally:
        engine.end = min(end+r['cleanup_wall_seconds'], time.monotonic()+r['cleanup_wall_seconds'])
        errors = engine.close()
        try:
            safe.write_new(job/'closure.json', {'errors': errors, 'resources': engine.cleanup_rows}, 2200000)
        except BaseException as persistence_error:
            if failure is None:
                raise
            failure.add_note('Closure preservation failed: '+repr(persistence_error)+
                             '; cleanup errors: '+repr(errors))
        if errors:
            if failure is not None:
                failure.add_note('Cleanup incomplete: '+repr(errors))
            else:
                raise RuntimeError('Cleanup incomplete')


def execute(r, bodies, source_raw):
    validate_request(r)
    work = native.plain_path(r['output']); safe.need(not work.exists(), 'Fresh output')
    work.mkdir(mode=0o700)
    start = time.monotonic(); end = start+r['whole_wall_seconds']; events = []
    result = {'status': 'started', 'scientific_qualification': False, 'native_qualification': False}
    failure = None; handlers = {}
    def event(name, **values):
        safe.need(len(events) < 140, 'Bounded full-panel phase record')
        row = {'event': name, 'elapsed_seconds': time.monotonic()-start, **values}
        events.append(row); safe.write_new(work/f'event-{len(events):03d}.json', row, 16384)
    def interrupted(signum, frame):
        raise InterruptedError('Operator signal '+str(signum))
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            handlers[sig] = signal.signal(sig, interrupted)
        programs = []
        for name in ('fixed_program', 'adaptive_driver'):
            raw = native.read_pinned(r[name], r[name+'_pin'], 1048576); raw.decode('utf8')
            path = work/(name+'.py'); native.write_bytes(path, raw); programs.append(path)
        event('both_programmes_frozen_before_public_read')
        method = work/'method'; method.mkdir(mode=0o755)
        for name, raw in bodies.items():
            native.write_bytes(method/name, raw)
        native.write_bytes(method/'SOURCE_MANIFEST.json', source_raw)
        raw = native.read_pinned(r['public'], r['public_pin'], 64000000)
        public = views.validate(safe.strict(raw)); native.write_bytes(work/'public.json', raw)
        safe.write_new(work/'MEMORY_ADMISSION.json', budget.admit(public, r), 16384)
        projected = work/'cases'; projected.mkdir(mode=0o755); projected.chmod(0o755)
        # Identical bytes mounted in both modes. No mode, mouse, path or target
        # is inserted into the one-case public view.
        for a, arm in enumerate(views.ARMS):
            for i, case in enumerate(public['cases']):
                directory = projected/f'{a}-{i:02d}'; directory.mkdir(mode=0o755); directory.chmod(0o755)
                projected_raw = json.dumps(views.project(case, arm), allow_nan=False,
                                           separators=(',', ':')).encode()
                safe.need(len(projected_raw) <= 64000000, 'Complete projected case cap')
                native.write_bytes(directory/'case.json', projected_raw)
        event('complete16_session_public_views_frozen', groups=[5, 5, 6])
        native.read_pinned(r['docker'], r['docker_pin'], 134217728)
        jobs = work/'jobs'; jobs.mkdir(mode=0o700)
        for m, mode in enumerate(views.MODES):
            for a, arm in enumerate(views.ARMS):
                for i, case in enumerate(public['cases']):
                    safe.need(time.monotonic() < end-r['grade_wall_seconds']-r['cleanup_wall_seconds'], 'Panel deadline')
                    key = f'{m}-{a}-{i:02d}'; job = jobs/key; job.mkdir(mode=0o700)
                    rows = invoke(r, job, projected/f'{a}-{i:02d}', programs[m], method/'holder.py',
                                  end-r['grade_wall_seconds']-r['cleanup_wall_seconds'], event)
                    views.predictions(rows, case)
        safe.need(len([x for x in events if x['event'] == 'case_closed']) == 128, 'Complete128 closed dispatches')
        safe.write_new(work/'PANEL.json', {'schema': 'neural030-closed-panel-v1', 'public_pin': r['public_pin'],
            'jobs': {x['job']: x['submission'] for x in events if x['event'] == 'case_closed'}}, 262144)
        event('all128_candidates_closed_before_private_grading')
        safe.write_new(work/'request.json', r, 65536)
        env = {k: os.environ[k] for k in ('PATH', 'HOME', 'TMPDIR') if k in os.environ}
        env.update({k: '1' for k in contract.THREADS}); env['PYTHONDONTWRITEBYTECODE'] = '1'
        grade = native.bounded_command([r['grader_python'], '-I', '-B', str(method/'run.py'), 'grade',
            '--source-bytes', str(len(source_raw)), '--source-sha256', hashlib.sha256(source_raw).hexdigest(),
            '--request', str(work/'request.json')], env, end, r['grade_wall_seconds'])
        safe.write_new(work/'grade-process.json', grade, 2200000)
        safe.need(grade['returncode'] == 0 and time.monotonic() <= end, 'Complete trusted grading phase')
        event('grade_completed')
        result.update(status='complete128_candidates_captured_and_graded', dispatches=128,
            programme_pins={k: r[k+'_pin'] for k in ('fixed_program', 'adaptive_driver')})
        return result
    except BaseException as error:
        failure = error; result.update(status='failed_preserved', error=repr(error)); raise
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
        result.update(events=events, elapsed_seconds=time.monotonic()-start,
            whole_process_observer_required=True, automatic_SIGKILL_recovery=False,
            authentic_adaptive_agent_established=False)
        try:
            safe.write_new(work/'RESULT.json', result, 2500000)
        except BaseException as error:
            if failure is None:
                raise
            failure.add_note('Result preservation failed: '+repr(error))
