"""Exact installed aliases and independently qualified full closure."""
import sys
from pathlib import Path
TASK='NEURAL-049'
REGISTRY='benchmarks/neuroscience/neural-049/manifest.json'
SCORE='benchmarks/neuroscience/neural-049/score.py'
ALIASES={None:'curated_retrospective_full_v1','curated_retrospective_full_v1':'curated_retrospective_full_v1'}

def choose(doc,condition):
    u.need(doc.get('id')==TASK,'one canonical neural task')
    if condition is None:return doc
    u.need(condition in ALIASES,'exact full condition')
    value=doc.get('program_conditions',{}).get(condition)
    if value=='default':value=doc.get('program_execution')
    u.need(type(value)is dict,'registered full condition')
    return {**doc,'program_execution':value}

def qualify(doc,cli,env,host):
    selected=choose(doc,cli['condition']);meta=selected.get('program_execution',{})
    if cli['operation']=='grade':
        meta=doc.get('protected_grading_execution',{});selected={**doc,'program_execution':meta}
    # Refuse before any review/submission/program/output operand, even if a
    # caller gives a plausible but unqualified registry.
    u.need(type(meta)is dict and meta.get('verification',{}).get('status')=='passed','not qualified: complete NEURAL049 central interface')
    fp=meta['source_freeze'];u.need(fp['path']==str((env['here']/'QUALIFICATION_SOURCE_FREEZE.json').relative_to(env['repo'])),'exact freeze location')
    raw=host.read(env['repo']/fp['path'],262144,u.only_pin(fp));freeze=u.parse(raw)
    u.need(freeze.get('schema')=='neural049_portable_source_freeze_v1'and freeze.get('task_id')==TASK
           and freeze.get('files')==env['freeze_files'],'entire central/parent/external/installed-alias closure')
    entry=meta['entrypoint'];idx=env['gate'].python_launch(entry['argv'])
    expected=SCORE if cli['operation']=='grade'else str((env['here']/'entry.py').relative_to(env['repo']))
    u.need(entry['argv'][idx]==expected and entry.get('sha256')==env['manifest']['files']['entry.py']['sha256']
           and entry.get('working_directory')=='.','exact source-owned entry')
    # Generic helper can consume4 JSON*2MiB, wrapper up to16MiB, all expected
    # bodies, and one failing growing read up to16MiB. Reserve before calling.
    host.reserve(4*(2097152+1)+2*(16777216+1)+sum(p['bytes']+1 for p in env['freeze_files'].values()))
    for key,sha in (('receipt_path','receipt_sha256'),('qualification_path','qualification_sha256'),('source_binding_path','source_binding_sha256')):
        name=meta['verification'][key];p=env['repo']/name
        u.need(type(name)is str and not Path(name).is_absolute() and str(Path(name))==name
               and '..' not in Path(name).parts and p.parent==env['here']/'runtime-qualification',
               'fixed portable generic evidence namespace')
        raw=host.read(p,2097152,readonly=True)
        u.need(u.pin(raw)['sha256']==meta['verification'][sha],'exact real qualification evidence')
    u.need(env['base'].verified_program_runtime(env['repo']/REGISTRY,selected,env['repo']),'real generic full-program qualification')
    if cli['operation']=='grade':
        v=doc.get('verification',{});u.need(v.get('status')=='passed'and doc.get('admission',{}).get('runnable')is True,'separate scoring qualification')
        # Avoid the generic scorer's unrestricted file digest: pre-admit exact
        # extents, then call its real check with conservatively reserved bound.
        name=v['receipt_path'];p=env['repo']/name
        u.need(type(name)is str and not Path(name).is_absolute() and str(Path(name))==name
               and '..' not in Path(name).parts and p.parent==env['here']/'runtime-qualification',
               'fixed portable scoring-terminal namespace')
        raw=host.read(p,2097152,readonly=True)
        u.need(u.pin(raw)['sha256']==v['receipt_sha256'],'score verification pin')
        terminal=u.parse(raw)
        u.need(terminal.get('candidate_id')==TASK and terminal.get('status')=='passed'
               and type(terminal.get('returncode'))is int and terminal['returncode']==0
               and terminal.get('source_freeze_sha256')==fp['sha256'],'score terminal independently binds current full freeze')
        host.read(env['repo']/SCORE,2097152,env['manifest']['files']['entry.py'])
        # Use the captured metadata predicates above instead of generic
        # verified_runtime's unbounded digest race. Campaign score construction
        # still independently calls that legacy helper in its own host.
    host.tick();return selected

def command(cli,doc,env):
    if cli['operation']=='grade':argv=doc['entrypoints']['score']['argv'];index=1
    else:argv=choose(doc,cli['condition'])['program_execution']['entrypoint']['argv'];index=env['gate'].python_launch(argv)
    values={'{program}':cli['program'],'{submission}':cli['program'],'{output}':cli['output'],'{review}':cli['review'],'{other_reserve_bytes}':str(cli['other_reserve_bytes'])}
    result=[sys.executable,*argv[1:index],str(env['repo']/argv[index]),*[values.get(v,v)for v in argv[index+1:]]]
    expected=env['here']/'entry.py'if cli['operation']=='collect'else env['repo']/SCORE
    u.need(result[index]==str(expected)and cli['actual_argv']==result and cli['actual_cwd']==str(env['repo']),'actual registered argv/interpreter/prefix/order/cwd')
    u.need(cli['source_pin']==env['source'],'actual source pin argv')
    return result

def campaign(review,doc,cli,env,host):
    # Name retained solely as the existing dispatch seam. The result is the
    # explicit new local-instance schema and makes no shared-WORK claim.
    return env['gate'].admit(review,doc,cli,env,host)
