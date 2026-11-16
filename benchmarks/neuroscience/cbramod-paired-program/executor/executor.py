"""One frozen program, disjoint A/B views, complete capture, then private grade."""
import hashlib
import os
from pathlib import Path
import re
import signal
import stat
import time
import uuid
import safe_io as safe
import engine
from engine import lexical_path
import runtime_contract as boundary
import operator_api
import packet


def validate(r):
    fields={'schema','program','program_pin','operator_root','packet_root','packet_pin',
            'binding','binding_pin','grader_python','docker','docker_pin','docker_host','docker_config',
            'image','runtime_admission','runtime_admission_pin','output','evaluation_condition',
            'candidate_wall_seconds','capture_wall_seconds','capture_cpu_seconds','grade_wall_seconds',
            'cleanup_wall_seconds','whole_wall_seconds','candidate_cpu_seconds','candidate_memory_bytes',
            'candidate_nano_cpus','host_memory_budget_bytes','retention_budget_bytes','public_bytes_limit'}
    safe.need(type(r) is dict and set(r)==fields and r['schema']=='cbramod_paired_program_request_v1','Closed operator request')
    # Post-bootstrap role ownership is rejected BEFORE filesystem role checks. Otherwise
    # a private binding aliased as program/packet/CLI could be accessed by that role.
    private_owner=lexical_path(r['binding']).parent
    roots=[lexical_path(r[k]) for k in ('operator_root','packet_root','docker_config','output')]
    early_files=[lexical_path(r[k]) for k in ('program','docker','runtime_admission','grader_python')]
    safe.need(type(r['docker_host']) is str and r['docker_host'].startswith('unix:///'),'Explicit local Unix daemon')
    early_files.append(lexical_path(r['docker_host'][7:]))
    source_owner=Path(__file__).parent
    safe.need(all(private_owner!=p and private_owner not in p.parents and p not in private_owner.parents
                  for p in (*roots,*early_files,source_owner)),
              'Dedicated private owner disjoint from every early source/input/output/file/endpoint role')
    for k in ('program','operator_root','packet_root','docker','docker_config','runtime_admission','output'):
        engine.plain_path(r[k])
    for k,cap in [('program_pin',1048576),('packet_pin',4_000_000),('binding_pin',4_000_000),
                  ('docker_pin',134217728),('runtime_admission_pin',65536)]:engine.pin(r[k],cap)
    safe.need(type(r['image']) is str and re.fullmatch('sha256:[0-9a-f]{64}',r['image']),'Immutable common image')
    engine.plain_path(r['docker_host'][7:])
    safe.need(r['evaluation_condition'] in ('current_source_reproduction','matched_support_re_evaluation'),'Explicit scientific condition')
    budgets=fields & {'candidate_wall_seconds','capture_wall_seconds','capture_cpu_seconds','grade_wall_seconds',
                     'cleanup_wall_seconds','whole_wall_seconds','candidate_cpu_seconds','candidate_memory_bytes',
                     'candidate_nano_cpus','host_memory_budget_bytes','retention_budget_bytes','public_bytes_limit'}
    safe.need(all(type(r[k]) is int and r[k]>0 for k in budgets),'Positive exact integral budgets')
    safe.need(r['whole_wall_seconds']<=86400 and r['cleanup_wall_seconds']>=30 and
              r['whole_wall_seconds']>=2*(r['candidate_wall_seconds']+r['capture_wall_seconds']+r['cleanup_wall_seconds'])+
              r['grade_wall_seconds']+r['cleanup_wall_seconds']+120,'Both full runs, captures, staging, grade and cleanup allowances')
    safe.need(max(r['candidate_cpu_seconds'],r['capture_cpu_seconds'])<=r['whole_wall_seconds'] and
              r['candidate_nano_cpus']<=8_000_000_000,'Complete CPU limits')
    safe.need(r['candidate_memory_bytes']>=boundary.VOLUME_BYTES+536870912 and
              r['host_memory_budget_bytes']>=r['candidate_memory_bytes']+1073741824,
              'Explicit whole8GB-output memory reservation plus candidate and operator scratch; not measured capacity')
    safe.need(r['retention_budget_bytes']>=r['public_bytes_limit']+3*boundary.OUTPUT_BYTES+536870912,
              'Two complete captures plus one8GB scorer snapshot and metadata/private allowance')
    roots=[Path(r[k]) for k in ('operator_root','packet_root','docker_config','output')]
    safe.need(all(x!=y and x not in y.parents and y not in x.parents for i,x in enumerate(roots) for y in roots[i+1:]),
              'Disjoint input, official source, daemon config and output owners')
    safe.need(all(Path(r['program'])!=x and x not in Path(r['program']).parents for x in roots),
              'Frozen participant is outside operator/code/data/output owners')
    safe.need(all(Path(r[k])!=roots[-1] and roots[-1] not in Path(r[k]).parents
                  for k in ('binding','grader_python','docker','runtime_admission')),'No output alias')
    return r


def runtime_admission(r):
    value=safe.strict(engine.read_pinned(r['runtime_admission'],r['runtime_admission_pin'],65536))
    safe.need(type(value) is dict and set(value)=={'schema','image','common_dependency_image_without_task_material',
              'independent_program_custody','operator_environment_qualified','daemon_boundary_qualified','review_identity_sha256'}
              and value['schema']=='cbramod_external_runtime_admission_v1' and value['image']==r['image'] and
              all(value[k] is True for k in ('common_dependency_image_without_task_material','independent_program_custody',
                                            'operator_environment_qualified','daemon_boundary_qualified')),
              'External runtime/image/program custody qualification is required; source receipt cannot grant it')
    safe.need(type(value['review_identity_sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['review_identity_sha256']),
              'Explicit external qualification identity')
    return value


def seal_public_projection(root, owner):
    """Normalize only freshly staged participant projections, independent of umask."""
    root=engine.plain_path(str(root));owner=engine.plain_path(str(owner))
    safe.need(root.parent==owner and root.name in ('input','view-A','view-B') and root.is_dir(),
              'Only executor-owned public projections may be sealed')
    directories=[];files=[]
    for base,dirs,names in os.walk(root,followlinks=False):
        directories.append(Path(base))
        safe.need(len(directories)+len(files)+len(dirs)+len(names)<=4096,'Bounded complete public projection tree')
        for name in dirs:
            p=Path(base)/name;safe.need(not p.is_symlink() and p.is_dir(),'Ordinary public directories')
        for name in names:
            p=Path(base)/name;st=p.lstat()
            safe.need(stat.S_ISREG(st.st_mode) and st.st_nlink==1,'Single-link ordinary staged public files')
            files.append(p)
    for p in files:p.chmod(0o444)
    for p in reversed(directories):p.chmod(0o555)
    return {'directories':len(directories),'files':len(files),'directory_mode':'0555','file_mode':'0444'}


def run_grade(r,work,captures,qpin,whole_end,source_pin):
    request={'operator_root':str(work/'operator'),'query':str(work/'input/QUERY.json'),'query_pin':qpin,
             'captures':captures,'binding':r['binding'],'binding_pin':r['binding_pin'],
             'evaluation_condition':r['evaluation_condition'],
             'grade_end':min(whole_end,time.monotonic()+r['grade_wall_seconds'])}
    safe.write_new(work/'GRADE_REQUEST.json',request,65536)
    env={k:os.environ[k] for k in ('HOME','PATH','TMPDIR') if k in os.environ}
    env.update({k:'1' for k in boundary.THREADS});env['PYTHONDONTWRITEBYTECODE']='1'
    original=engine.bounded_command([r['grader_python'],'-I','-B',str(work/'trusted/run.py'),'grade',
        '--source-bytes',str(source_pin['bytes']),'--source-sha256',source_pin['sha256'],
        '--request',str(work/'GRADE_REQUEST.json'),'--result',str(work/'GRADE.json')],env,whole_end,r['grade_wall_seconds'])
    safe.write_new(work/'grade-process.json',original,2_200_000)
    safe.need(original['returncode']==0 and time.monotonic()<whole_end,'Complete bounded unchanged scorer child')
    raw=safe.read(work/'GRADE.json',4_000_000);value=safe.strict(raw)
    safe.need(value['schema']=='cbramod_paired_result_v1' and set(value['arms'])=={'A','B'} and
              value['both_complete_outputs_admitted_before_private_access'] is True,'Complete paired grade result')
    return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def execute(r,bodies,source_manifest):
    validate(r);work=engine.plain_path(r['output']);safe.need(not work.exists(),'Fresh exclusive operator output')
    start=time.monotonic();end=start+r['whole_wall_seconds'];work.mkdir(mode=0o700)
    events=[];docker=None;failure=None;captures={};result={'status':'started'};handlers={}
    def event(name,**values):
        safe.need(len(events)<40,'Bounded complete phase events')
        row={'event':name,'elapsed_seconds':time.monotonic()-start,**values};events.append(row)
        safe.write_new(work/f'event-{len(events):02d}.json',row,65536)
    def cancel(signum,frame):raise InterruptedError('Owned operator signal '+str(signum))
    try:
        for s in (signal.SIGINT,signal.SIGTERM):handlers[s]=signal.signal(s,cancel)
        # Same bytes are frozen once, before the operator opens either public data or view.
        program=engine.read_pinned(r['program'],r['program_pin'],1048576);program.decode('utf8')
        engine.write_bytes(work/'candidate.py',program);event('same_program_frozen',pin=r['program_pin'])
        admission=runtime_admission(r);event('external_runtime_admission_read',identity=r['runtime_admission_pin'])
        host=operator_api.freeze(r['operator_root'],work/'operator')
        trusted=work/'trusted';trusted.mkdir(mode=0o700)
        for name,body in bodies.items():engine.write_bytes(trusted/name,body)
        source_pin=engine.write_bytes(trusted/'SOURCE_MANIFEST.json',source_manifest)
        q,packet_receipt=packet.stage(r,host,work/'input',end-r['grade_wall_seconds']-r['cleanup_wall_seconds'])
        seal_public_projection(work/'input',work)
        host._condition(r['evaluation_condition'],q['purpose'])
        qraw=safe.read(work/'input/QUERY.json',256_000_000)
        qpin={'bytes':len(qraw),'sha256':hashlib.sha256(qraw).hexdigest()};del qraw
        views={};expected={}
        for arm in ('A','B'):
            views[arm]=work/('view-'+arm);host.stage_view(arm,views[arm])
            seal_public_projection(views[arm],work)
            expected[arm]=operator_api.expectation(host,q,arm)
            safe.write_new(work/('expected-'+arm+'.json'),expected[arm],4_000_000)
        event('complete_packet_and_disjoint_views_staged',packet=packet_receipt,scope=operator_api.scope(host))
        # Hashing a trusted CLI is bounded; no CLI invocation occurred before preparation.
        engine.read_pinned(r['docker'],r['docker_pin'],134217728)
        commands=work/'commands';commands.mkdir(mode=0o700)
        docker=engine.Docker(r,commands,end-r['grade_wall_seconds']-r['cleanup_wall_seconds'])
        for arm in ('A','B'):
            docker.end=end-r['grade_wall_seconds']-r['cleanup_wall_seconds']
            suffix=uuid.uuid4().hex;volume='cbramod-output-'+suffix
            holder='cbramod-holder-'+suffix;candidate='cbramod-candidate-'+suffix
            capture=work/('capture-'+arm);capture.mkdir(mode=0o777);capture.chmod(0o777)
            docker.volume(volume)
            hm={'/trusted/holder.py':{'type':'bind','source':str(trusted/'holder.py'),'rw':False},
                '/trusted/expected.json':{'type':'bind','source':str(work/('expected-'+arm+'.json')),'rw':False},
                '/capture':{'type':'volume','source':volume,'rw':False},
                '/export':{'type':'bind','source':str(capture),'rw':True}}
            docker.create(holder,'holder',hm)
            safe.need(docker.call(['start',holder])['returncode']==0 and
                      docker.inspect('container',holder)['State']['Running'] is True,'Live trusted holder')
            cm={'/program/candidate.py':{'type':'bind','source':str(work/'candidate.py'),'rw':False},
                '/input':{'type':'bind','source':str(work/'input'),'rw':False},
                '/view':{'type':'bind','source':str(views[arm]),'rw':False},
                '/output':{'type':'volume','source':volume,'rw':True}}
            # Candidate never gets /operator, /trusted, /view-B in A, or either capture.
            docker.create(candidate,'candidate',cm);event('arm_boundary_checked',arm=arm)
            launched=time.monotonic();safe.need(docker.call(['start',candidate])['returncode']==0,'Candidate started')
            remaining=r['candidate_wall_seconds']-(time.monotonic()-launched);safe.need(remaining>0,'Candidate start included in wall budget')
            waited=docker.call(['wait',candidate],remaining);state=docker.inspect('container',candidate)['State']
            safe.need(waited['returncode']==0 and waited['stdout'].strip()=='0' and
                      state['Running'] is False and state['Pid']==0 and state['OOMKilled'] is False and state['ExitCode']==0
                      and time.monotonic()-launched<=r['candidate_wall_seconds'],'Successful complete arm within matched wall budget')
            docker.remove('container',candidate);event('candidate_absent',arm=arm)
            copied=docker.call(['exec',holder,'python','-I','-B','/trusted/holder.py','capture',str(r['capture_wall_seconds'])],
                               r['capture_wall_seconds'])
            safe.need(copied['returncode']==0 and not copied['stderr'],'Complete trusted streaming capture')
            receipt=safe.strict(copied['stdout'])
            safe.need(set(receipt)=={'status','files','artifact_bytes','submission'} and receipt['status']=='captured' and
                      receipt['files']==len(expected[arm]['cases']) and type(receipt['artifact_bytes']) is int and
                      0<receipt['artifact_bytes']<=boundary.OUTPUT_BYTES,'Full unchanged case and byte roster')
            engine.pin(receipt['submission'],4_000_000)
            docker.end=min(end-r['grade_wall_seconds'],time.monotonic()+r['cleanup_wall_seconds'])
            safe.need(not docker.close(),'Every owned candidate, holder and volume absent')
            # Captured files are now operator-only and cannot be mutated by the removed arm.
            capture.chmod(0o700)
            engine.read_pinned(capture/'submission.json',receipt['submission'],4_000_000)
            captures[arm]={'root':str(capture),'submission':receipt['submission']}
            event('arm_complete_capture_and_closure',arm=arm,receipt=receipt)
        safe.need(set(captures)=={'A','B'},'Both complete arms required')
        docker.end=min(end-r['grade_wall_seconds'],time.monotonic()+r['cleanup_wall_seconds'])
        safe.need(all(docker.missing(kind,name) for kind,name in docker.owned),'Fresh absence check for BOTH arms before private grading')
        event('both_arms_all_owned_resources_absent')
        # run_grade's child admits every probability file in both arms before binding access.
        grade=run_grade(r,work,captures,qpin,end,source_pin);event('paired_grading_completed',pin=grade)
        result.update(status='paired_program_captured_and_graded',program=r['program_pin'],captures=captures,
                      grade=grade,scope=operator_api.scope(host),matched_budgets=True)
        return result
    except BaseException as error:
        failure=error;result.update(status='failed_preserved',error=repr(error),original_command=getattr(error,'command_observation',None));raise
    finally:
        cleanup=[]
        if docker is not None:
            docker.end=min(end,time.monotonic()+r['cleanup_wall_seconds']);cleanup=docker.close()
        result.update(events=events,cleanup_errors=cleanup,elapsed_seconds=time.monotonic()-start,
                      scientific_qualification=False,native_runtime_qualification=False,full_paper_reproduced=False,
                      operating_system_SIGKILL_recovery_automatic=False,external_whole_process_observer_required=True)
        for s,h in handlers.items():signal.signal(s,h)
        try:safe.write_new(work/'RESULT.json',result,4_000_000)
        except BaseException as error:
            if failure is not None:failure.add_note('Result preservation also failed: '+repr(error))
            else:raise
        if cleanup and failure is None:raise RuntimeError('Owned cleanup incomplete; no success claim')
