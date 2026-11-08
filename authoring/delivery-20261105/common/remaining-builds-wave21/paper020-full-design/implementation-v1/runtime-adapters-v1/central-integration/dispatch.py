"""Stage captured bytes and invoke the actual immutable adapter exactly once."""
import importlib
import os
from pathlib import Path
import sys
import types

def stage(env,reader,root):
    root=u.components(root);u.need(not root.exists(),'fresh private source staging root')
    root.mkdir(mode=0o700)
    for member in env['parent']['members']:
        dest=root/u.relative(member.staged_path);dest.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        u.need(u.pin(member.body)=={'bytes':member.size_bytes,'sha256':member.sha256},'captured stage bytes changed')
        reader.write(dest,member.body)
    u.freeze_directories(root);reader.tick();return root

def load_adapter(env,reader,stage_root):
    # Scientific import is reachable only after fixed registry/preference,
    # signed installation/job, repeat routing and captured source staging.
    root=stage_root/'implementation-v1/runtime-adapters-v1/successor-v3'
    expected={m.staged_path for m in env['parent']['members']};actual=set();directories=0
    for current,dirs,files in os.walk(u.components(stage_root),followlinks=False):
        directories+=1;u.need(directories<=64 and len(files)<=34 and len(dirs)<=32,'bounded exact source tree')
        for name in dirs+files:u.components(Path(current)/name)
        actual.update((Path(current)/name).relative_to(stage_root).as_posix()for name in files)
        u.need(len(actual)<=34,'extra staged source file')
    u.need(actual==expected,'complete exact staged source tree; pycache/extra imports forbidden')
    for member in env['parent']['members']:
        reader.file_pin(stage_root/member.staged_path,{'bytes':member.size_bytes,'sha256':member.sha256})
    name='_paper020_central_actual_'+env['source_pin']['sha256']
    u.need(name not in sys.modules,'fresh source-owned adapter module namespace')
    pkg=types.ModuleType(name);pkg.__path__=[str(root)];sys.modules[name]=pkg
    reader.tick();entry=importlib.import_module(name+'.entry');reader.tick();return entry

def _call_once(entry,operands,journal,credential_fd):
    """Only instrumentation replacement delegates to the captured constructor.

    No executor/scorer/prediction callback is accepted. Parent source, controller,
    dispatch kernels and protected grader remain unchanged in the staged files.
    """
    original=entry.construct;created=[]
    def traced(*args,**kwargs):
        u.need(not created,'actual runtime construction may occur once')
        bound=original(*args,**kwargs);wrapped=transcript.BoundTrace(bound,journal);created.append(wrapped);return wrapped
    entry.construct=traced
    try:
        result=entry.run_full_study(operands['runtime_envelope'],operands['public_key'],operands['contract'],
            operands['admission'],operands['mapping'],credential_fd=credential_fd)
        u.need(len(created)==1 and created[0].pending is None,'one fully observed actual runtime required')
        return result,created[0]
    finally:entry.construct=original

def run(env,reader,operands,output):
    root=u.components(output);u.need(not root.exists(),'fresh complete private output directory required')
    root.mkdir(mode=0o700);job=operands['job'];d=operands['runtime_document']
    stage_root=stage(env,reader,root/'source-stage');entry=load_adapter(env,reader,stage_root)
    # Optional credential transfer is a concrete gated FD operation, not a model callback.
    fd=env['credential'].receive(job['credential_broker'],job,reader)
    global transcript;transcript=env['transcript']
    journal=None
    try:
        journal=env['transcript'].Journal(root/'phases.jsonl',reader,job['metadata_limits']['trace_bytes'])
        provisional,bound=_call_once(entry,operands,journal,fd)
    finally:
        os.close(fd)
        if journal is not None:journal.close()
    entry._validate_complete_provisional(provisional,d);reader.tick()
    raw=reader.read(root/'phases.jsonl',job['metadata_limits']['trace_bytes'])
    validation=env['transcript'].validate(entry,operands['contract'],d,provisional,raw)
    index=env['artifacts'].capture(bound,reader)
    # Current process check plus exact source remains necessary, never a terminal proof.
    u.need(bound.monitor.host.identity==provisional['host_identity'],'actual central/adapter host identity differs')
    indexraw=u.canonical(index);u.need(len(indexraw)<=job['metadata_limits']['artifact_index_bytes'],'complete artifact index budget')
    files={'phases.jsonl':u.pin(raw),'artifacts.json':reader.write(root/'artifacts.json',indexraw),
           'inner.json':reader.write(root/'inner.json',u.canonical(provisional))}
    summary={'schema':'paper020_central_provisional_v1','status':'provisional_pending_external_natural_exit',
        'task_id':'PAPER-ROOT-ADD-020','run_id':job['run_id'],'central_source':env['source_pin'],
        'source_closure_digest':u.sha(u.canonical(env['source_rows'])),'program_pin':operands['program_pin'],
        'mode':job['mode'],'origin_ns':job['origin_ns'],'deadline_ns':job['deadline_ns'],
        'host_identity':provisional['host_identity'],'files':files,'phase_count':validation['phase_count'],
        'phase_head':validation['head'],'phase_counts':validation['counts'],'parent_entry_calls':1,
        'parent_controller_executions':1,'external_numerical_grader_calls':0,
        'publication_started_ns':reader.tick(),'logical_metadata_costs':reader.report(),'routing':env['route_receipt'],
        'scientific_qualification_claim':False,'physical_qualification_claim':False,'new_canonical_ids':0}
    # Include the summary's own eventual successful write in its cost record.
    # Its pin stays outside the file, avoiding a self-hash cycle.
    for _ in range(16):
        rawsummary=u.canonical(summary);expected=reader.write_bytes+len(rawsummary)
        if summary['logical_metadata_costs']['logical_write_bytes']==expected:break
        summary['logical_metadata_costs']['logical_write_bytes']=expected
    else:raise ValueError('summary cost extent did not stabilize')
    pin=reader.write(root/'summary.json',rawsummary)
    u.need(reader.write_bytes==summary['logical_metadata_costs']['logical_write_bytes'],'complete summary write charge differs')
    os.chmod(root,0o500);reader.tick()
    return {'status':'provisional_pending_external_natural_exit','summary_pin':pin,'scientific_qualification_claim':False}
