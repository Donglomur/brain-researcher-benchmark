"""Closed producer, committed output, then target-last collection.

`engineering_run` is an invented-fixture lifecycle test, not an OS sandbox.
Scientific execution consumes the original external owner interface. Local
engineering receipts cannot qualify a protected scientific submission.
"""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from reward_common import (need,canonical_json_bytes,sha256,object_sha256,strict_json_loads,
                           member_pin,read_member,receipt,verify_receipt_link)
from native import original_process_commit



def decode_stopped_submission(data,output_pin):
    value=strict_json_loads(data,max_bytes=max(len(data),1))
    if type(value) is dict and value.get('schema')=='reward_reproduction_submission_v2':
        from provenance import collect_reproduction_bundle
        return collect_reproduction_bundle(data,output_pin,max_bytes=max(len(data),1))
    return value


def _save(path,value):
    path=Path(path);need(not path.exists(),'Immutable output path')
    data=canonical_json_bytes(value);path.write_bytes(data)
    return {'path':path.name,'bytes':len(data),'sha256':sha256(data)}


def _group_exists(pid):
    try:os.killpg(pid,0);return True
    except ProcessLookupError:return False


def engineering_run(program_bytes,public_input,output_dir,private_factory,scorer,timeout=2,max_output=262144):
    """Run only a small explicitly invented test; no authentic files/data.

    The controller never accepts a candidate-supplied success or score. The
    parent reaps the process group, commits output bytes, and only then invokes
    the private factory. This verifies lifecycle ordering, not hostile isolation
    or escaped descendants. Production requires a qualified external owner.
    """
    need(public_input.get('engineering_only') is True,'Invented fixture marker required')
    need(type(program_bytes) is bytes and 0<len(program_bytes)<=32768,'Tiny fixture program')
    need(type(timeout) in (int,float) and 0<timeout<=10,'Tiny engineering time budget')
    root=Path(output_dir);need(root.is_dir() and not any(root.iterdir()),'Empty owned engineering directory')
    program=root/'producer.py';program.write_bytes(program_bytes)
    public_pin=_save(root/'public.json',public_input)
    source=receipt('source_commit',[public_pin],[member_pin(root,'producer.py')],
                   engineering_only=True,program_sha256=sha256(program_bytes))
    _save(root/'01-source.json',source)
    start=time.monotonic();status='failed';timed_out=False
    # File-backed streams avoid unbounded PIPE buffering. Fixture producers are
    # trusted engineering code, not a boundary against hostile filesystem I/O.
    with (root/'stdout.log').open('wb') as out,(root/'stderr.log').open('wb') as err:
        process=subprocess.Popen([sys.executable,'-B',str(program.resolve()),'public.json','submission.json'],
                                 cwd=root,start_new_session=True,stdout=out,stderr=err,
                                 env={'PATH':os.defpath,'PYTHONDONTWRITEBYTECODE':'1'})
        try:process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:timed_out=True
        # Kill the owned group even when the leader exits normally, then reap it.
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait(timeout=2)
    group_absent=not _group_exists(process.pid)
    lifecycle={'pid':process.pid,'returncode':process.returncode,'timed_out':timed_out,
               'observed_group_absent':group_absent,'elapsed_seconds':time.monotonic()-start,
               'escaped_descendants_verified_absent':False,'protected_isolation_qualified':False}
    commit=receipt('producer_closed',[],[],previous=source,engineering_only=True,**lifecycle)
    _save(root/'02-closed.json',commit)
    if timed_out or process.returncode!=0 or not group_absent:
        _save(root/'outcome.json',{'status':'producer_failed','lifecycle':lifecycle,'private_factory_called':False})
        return {'status':'producer_failed','private_factory_called':False,'lifecycle':lifecycle}
    try:
        data=read_member(root,'submission.json',max_output)
        prediction=decode_stopped_submission(data,{'bytes':len(data),'sha256':sha256(data)})
    except (ValueError,OSError) as exc:
        _save(root/'outcome.json',{'status':'invalid_submission','reason':str(exc),'private_factory_called':False})
        return {'status':'invalid_submission','private_factory_called':False}
    output_pin=member_pin(root,'submission.json',max_output)
    captured=receipt('output_commit',[],[output_pin],previous=commit,engineering_only=True,
                     before_private_inputs=True,program_sha256=sha256(program_bytes))
    _save(root/'03-output.json',captured)
    # All producer activity has ended and its bytes are committed before this line.
    private=private_factory();private_pin=_save(root/'private-engineering.json',private)
    try:
        result=scorer(private,prediction);status='scored'
    except (ValueError,KeyError,TypeError,OverflowError) as exc:
        result={'failure':type(exc).__name__,'reason':str(exc)};status='invalid_prediction'
    result_pin=_save(root/'score.json',result)
    final=receipt('engineering_collection',[private_pin,output_pin],[result_pin],previous=captured,
                  status=status,engineering_only=True,scientific_qualification=False)
    _save(root/'04-collection.json',final)
    outcome={'status':status,'private_factory_called':True,'receipt_sha256':object_sha256(final),
             'engineering_only':True,'protected_isolation_qualified':False,'scientific_qualification':False}
    _save(root/'outcome.json',outcome);return outcome


def collect_original_submission(owner,execution,unit_commit,outcome,expected,private_factory,scorer):
    """Production integration of the pre-existing original worker interface.

    `owner` is a trusted external process owner object, never a candidate JSON.
    It independently verifies its producer/holder/volume inventory and retrieves
    bytes from the committed stopped holder. Source-only construction creates
    no owner and confers no execution authorization.
    """
    owner.assert_qualified_full_programme(expected['scope_sha256'])
    owner.assert_original_receipts(execution,unit_commit,outcome)
    owner.assert_all_owned_absent()
    bridge=original_process_commit(execution,unit_commit,outcome,expected,
                 owner.read_original_unit_commit_bytes(),owner.read_full_scope_source_commit())
    data=owner.read_committed_output(bridge['output'])
    need(len(data)==bridge['output']['bytes'] and sha256(data)==bridge['output']['sha256'],'Stopped output identity')
    need(len(data)<=owner.output_byte_limit,'Qualified output byte limit')
    prediction=decode_stopped_submission(data,bridge['output'])
    # No target supplier call before original owner cleanup and immutable capture.
    private=private_factory()
    result=scorer(private,prediction)
    return {'bridge':bridge,'result':result,'scientific_qualification':False,
            'qualification_reason':'Execution and numeric scoring alone do not close the scientific gates'}


def original_run_unit_boundary(lib,run,program_sha256,unit_manifest,budget,deadlines,
                               source_commit,recover_all,private_factory,scorer,admission,support_precommit=None):
    """Concrete unchanged original ten-argument run_unit protocol integration.

    No legacy assets()/public_unit()/grade() call is reused: those bind only the
    old38-mouse slice. The supplied library, new full public unit and resource
    envelope require separate independent qualification before this interface
    may launch. It is exercised only with a tiny invented mock library here.
    """
    need(admission['full_programme_runtime_qualified'] is True and admission['execution_authorized'] is True,
         'Separate full programme runtime admission required')
    need(source_commit['before_public_input_release'] is True and
         source_commit['public_inputs']==unit_manifest['public_inputs'] and
         source_commit['program_sha256']==program_sha256,'Pre-release full public input commitment')
    need(admission['scope_sha256']==source_commit['scope_sha256'],'Full programme admission scope')
    if unit_manifest.get('task_mode')=='improvement':
        need(support_precommit is not None and support_precommit['before_candidate_prediction'] is True,
             'Improvement source mask committed before original worker launch')
        need(source_commit['support_manifest_sha256']==support_precommit['support_manifest_sha256'] and
             object_sha256(source_commit)==support_precommit['source_commit_sha256'],
             'Full run source receipt binds the precommitted support manifest')
    need(time.monotonic()<deadlines['candidate']<deadlines['cleanup']<deadlines['private'],
         'Separately registered candidate, cleanup and collection clocks')
    root=Path(run);limit=admission['output_byte_limit']
    def opaque(body,unused):need(0<len(body)<=limit,'Bounded opaque output before private inputs')
    unit=lib['run_unit'](root/'program.py',program_sha256,unit_manifest,root/'unit',budget,
                         deadlines['candidate'],deadlines['candidate'],None,'PAPER-FIND-044',opaque)
    need(unit['all_owned_absent'] is True,'Original candidate cleanup')
    absence=recover_all(root,deadlines['cleanup'],budget)
    need(absence['absence_verified'] is True and len(absence['resources'])==3,
         'Original producer, holder and volume independently absent')
    _save(root/'independent_absence.json',absence)
    need(unit['status'] in ('unit_committed','invalid_unit_submission','output_boundary_rejected','candidate_program_failed'),
         'Original infrastructure failure is not scientific outcome')
    outcome={'unit_status':unit['status'],'output':unit.get('output'),
             'unit_commit_sha256':unit.get('commit_sha256'),'all_candidate_resources_absent':True,'before_private_inputs':True}
    _save(root/'outcome_commit.json',outcome)
    if unit['status']!='unit_committed':return {'status':unit['status'],'private_factory_called':False}
    commit_bytes=read_member(root,'unit/commit.json',1048576);commit=strict_json_loads(commit_bytes)
    expected={'program_sha256':program_sha256,'public_inputs':unit_manifest['public_inputs'],'scope_sha256':source_commit['scope_sha256']}
    bridge=original_process_commit(unit,commit,outcome,expected,commit_bytes,source_commit)
    data=read_member(root,'unit/submission.json',limit)
    need(bridge['output']=={'bytes':len(data),'sha256':sha256(data)},'Original stopped output bytes')
    prediction=decode_stopped_submission(data,bridge['output'])
    _save(root/'prediction_commit.json',{'unit_commit_sha256':sha256(commit_bytes),
                                     'output_sha256':sha256(data),'all_candidate_resources_absent':True})
    need(time.monotonic()<deadlines['private'],'Collection deadline before private factory')
    target=private_factory()
    if unit_manifest.get('task_mode')=='improvement':
        need(target['source_commit_sha256']==object_sha256(source_commit) and
             target['registered']['support_precommit']==support_precommit,'No grade-stage support registration substitution')
    result=scorer(target,prediction)
    _save(root/'score.json',result)
    return {'status':'scored','private_factory_called':True,'bridge':bridge,
            'scientific_qualification':False,'scope_sha256':source_commit['scope_sha256']}
