"""Root-reviewed ordinary program registration for the complete54 outer observer."""
import time
ORIGIN=time.monotonic()
import signal
INITIAL_HANDLER=None

def expired(*_):raise TimeoutError('original full54 adapter deadline')
def enter_startup():
    global INITIAL_HANDLER
    if signal.getitimer(signal.ITIMER_REAL)!=(0.,0.):raise ValueError('fresh standalone adapter owner')
    INITIAL_HANDLER=signal.getsignal(signal.SIGALRM)
    installed=False
    try:
        signal.signal(signal.SIGALRM,expired);installed=True
        if time.monotonic()>=ORIGIN+120:raise TimeoutError('adapter startup expired')
        signal.setitimer(signal.ITIMER_REAL,ORIGIN+120-time.monotonic())
    except BaseException as primary:
        if installed:
            try:signal.setitimer(signal.ITIMER_REAL,0)
            except BaseException as cleanup:primary.add_note('startup cancel: '+type(cleanup).__name__)
            try:signal.signal(signal.SIGALRM,INITIAL_HANDLER)
            except BaseException as cleanup:primary.add_note('startup restore: '+type(cleanup).__name__)
        raise
if __name__=='__main__':enter_startup()
import argparse,hashlib,json,math,os,re,stat,sys,types
from pathlib import Path
HERE=Path(__file__).absolute().parent
ROOT=HERE.parents[4]
TASK='NEURAL-084'
READ_CAP=4000000
FINAL_END=ORIGIN+120
CONTROLLER_NAMES={'common.py','policy.py','controller.py','native.py','holder.py','candidate_entry.py','process.py','bootstrap.py','worker.py','observe.py','admission.py','packet.py','BINDING.json','PROGRAM_ABI.md','reference_program.py'}

def need(ok, message):
    if not ok:
        raise ValueError(message)

def parse(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))

def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}

def descriptor(value, maximum):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}, 'exact source descriptor')
    need(type(value['bytes']) is int and 0 < value['bytes'] <= maximum, 'bounded exact extent')
    digest = value['sha256']
    need(type(digest) is str and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest), 'exact lowercase digest')
    return value

def literal(value):
    need(type(value) is str and value and not any(c in value for c in '\x00\r\n,'), 'literal path')
    path = Path(value)
    need(path.is_absolute() and '..' not in path.parts and str(path) == value, 'canonical absolute path')
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'unlinked path')
    return path

class Captures:
    def __init__(self, end):
        self.end = end
        self.reserved = 0

    def tick(self):
        need(time.monotonic() < self.end, 'original adapter work endpoint')

    def read(self, path, maximum, expected=None):
        self.tick()
        path = literal(str(path))
        if expected is not None:
            descriptor(expected, maximum)
        self.tick()
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= maximum, 'ordinary bounded file')
            if expected is not None:
                need(before.st_size == expected['bytes'], 'pinned extent before read')
            charge = before.st_size + 1
            need(self.reserved + charge <= READ_CAP, 'complete adapter read cap')
            self.reserved += charge
            self.tick()
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(charge)
            keys = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_uid', 'st_gid', 'st_mtime_ns', 'st_ctime_ns')
            signature = lambda value: tuple(getattr(value, k) for k in keys)
            need(len(raw) == before.st_size and signature(before) == signature(os.fstat(fd)) == signature(path.lstat()), 'stable fd and named identity')
            if expected is not None:
                need(pin(raw) == expected, 'exact captured content')
            self.tick()
            return raw
        finally:
            os.close(fd)

def relative(value):
    need(type(value) is str and value and '\\' not in value, 'relative source path')
    p=Path(value)
    need(not p.is_absolute() and '..' not in p.parts and p.as_posix()==value, 'confined source')
    return literal(str(ROOT/p))

def selected_descriptor(value, cap):
    need(type(value)is dict and set(value)=={'path','bytes','sha256'},'exact selected descriptor')
    descriptor({k:value[k] for k in ('bytes','sha256')},cap)
    return literal(value['path']),{k:value[k] for k in ('bytes','sha256')}

def metadata_operand(captures,row,cap=32768):
    path,pp=selected_descriptor(row,cap)
    return parse(captures.read(path,cap,pp)),(path,pp)


def own_sources(captures,expected):
    raw=captures.read(HERE/'SOURCE_MANIFEST.json',32768,expected);m=parse(raw)
    need(m['schema']=='neural084_full54_registration_source_v1' and m['task_id']==TASK and set(m['files'])=={'adapter.py','BINDINGS.json','README.md'},'exact adapter source closure')
    bodies={name:captures.read(HERE/name,100000,descriptor(pp,100000)) for name,pp in m['files'].items()}
    b=parse(bodies['BINDINGS.json'])
    need(b['schema']=='neural084_full54_registration_bindings_v1' and b['task_id']==TASK and b['private_grading_authorized']is False,'complete unscored source binding')
    need(b['scope']=={'people':54,'outer_folds':54,'queries_per_fold':400,'training_per_fold':21200,'one_frozen_program':True,'prospective_block_mean_lopo':True,'query_batch_fitting':False},'unchanged complete declared chronology')
    return b


def adapted_observe(raw):
    # This additive controller natively accepts the exact original adapter origin.
    # No source AST or numerical function is rewritten at runtime.
    text=raw.decode('utf-8')
    need(text.count('ORIGIN=globals().get("ADAPTER_ORIGIN",time.monotonic())')==1,'single owned original origin interface')
    return raw


def target(captures,binding):
    row=binding['controller_manifest'];controller={k:row[k] for k in ('bytes','sha256')}
    m=parse(captures.read(relative(row['path']),32768,controller))
    need(set(m)=={'schema','files'} and m['schema']=='neural084_full54_program_source_v1' and set(m['files'])==set(binding['controller_members'])==CONTROLLER_NAMES,'exact complete14 controller closure')
    bodies={}
    for name,row in binding['controller_members'].items():
        pp={k:row[k] for k in ('bytes','sha256')};need(m['files'][name]==pp,'exact member')
        bodies[name]=captures.read(relative(row['path']),100000,pp)
    dependency=parse(bodies['BINDING.json'])
    need(list(dependency['sources'].values())==binding['source_dependencies'],'same original contract dependency closure')
    for row in binding['source_dependencies']:
        captures.read(relative(row['path']),262144,{k:row[k] for k in ('bytes','sha256')})
    path=relative(binding['controller_members']['observe.py']['path'])
    return compile(adapted_observe(bodies['observe.py']),str(path),'exec'),path,controller,bodies,dependency


def original_selection(s,source,binding,captures,bodies,dependency):
    here=relative(binding['controller_members']['common.py']['path']).parent
    def module(name,**kw):
        value=types.ModuleType(name);value.__file__=str(here/name);value.__dict__.update(kw)
        exec(compile(bodies[name],value.__file__,'exec'),value.__dict__);return value
    c=module('common.py');packet=module('packet.py',c=c);policy=module('policy.py',c=c,packet=packet)
    policy.selection(s,source)
    need(literal(s['repository'])==ROOT,'same source repository')
    seen=[]
    def read(path,cap,expected):
        selected=literal(path);seen.append((selected,expected,cap));return captures.read(selected,cap,expected)
    policy.reviews(s,source,dependency,read)
    return seen


def bind(args,captures,expected,binding,bodies,dependency):
    need(type(args.other_reserve_bytes)is int and args.other_reserve_bytes>=0,'current explicit OTHER')
    review_path=literal(args.review);raw=captures.read(review_path,32768);r=parse(raw)
    fields={'schema','task_id','approved','adapter_source','controller_source','selection','program','adapter_runtime','typed_result','private_grading_authorized'}
    need(type(r)is dict and set(r)==fields and r['schema']=='neural084_full54_registration_review_v1' and r['task_id']==TASK and r['approved']is True and r['private_grading_authorized']is False and r['typed_result']=='neural084_full54_unscored_result_v1','root full54 unscored authority')
    controller={k:binding['controller_manifest'][k] for k in ('bytes','sha256')}
    need(descriptor(r['adapter_source'],32768)==expected and r['controller_source']==controller,'exact adapter and original controller')
    s,sp=metadata_operand(captures,r['selection'])
    operands=[(review_path,pin(raw),32768),(sp[0],sp[1],32768)]+original_selection(s,controller,binding,captures,bodies,dependency)
    need(s['program']==r['program'] and literal(args.program)==literal(s['program']['path']),'same reviewed ordinary program; body remains unopened')
    need(literal(args.output)==literal(s['output']) and not os.path.lexists(args.output) and not os.path.lexists(str(args.output)+'.observer'),'fresh complete output and observer sibling')
    need(s['other_future_bytes']==args.other_reserve_bytes,'same current OTHER')
    value,ap=metadata_operand(captures,r['adapter_runtime'])
    keys={'schema','task_id','qualified','adapter_source','controller_source','controller_runtime','host_python','metadata_read_cap','adapter_persistent_writes','native_observer_route_qualified','original_clock_handoff_qualified','full_people','scientific_qualified','private_grading_authorized','evidence'}
    need(type(value)is dict and set(value)==keys and value['schema']=='neural084_full54_registration_runtime_v1' and value['task_id']==TASK and value['qualified']is True,'independent adapter runtime prerequisite')
    need(value['adapter_source']==expected and value['controller_source']==controller and value['controller_runtime']==s['runtime_review'] and value['host_python']==str(Path(sys.executable).resolve()),'exact adapter/controller/runtime join')
    need(value['metadata_read_cap']==READ_CAP and type(value['metadata_read_cap'])is int and value['adapter_persistent_writes']==0 and type(value['adapter_persistent_writes'])is int and value['native_observer_route_qualified']is True and value['original_clock_handoff_qualified']is True and value['full_people']==54 and type(value['full_people'])is int and value['scientific_qualified']is False and value['private_grading_authorized']is False,'complete route and scope')
    selected_descriptor(value['evidence'],1048576);operands.append((ap[0],ap[1],32768));captures.tick()
    return s,sp,operands


class Terminal:
    def __init__(self,end):self.end=end;self.parts=[];self.size=0
    def write(self,value):
        need(type(value)is str and time.monotonic()<self.end,'bounded original-clock terminal');n=len(value.encode());need(self.size+n<=8192,'whole observer terminal cap');self.parts.append(value);self.size+=n;return len(value)
    def flush(self):need(time.monotonic()<self.end,'terminal flush before original end')


def invoke(code,path,selection_operand,controller,end,output,captures,selected):
    need(time.monotonic()<ORIGIN+120 and time.monotonic()<end,'original startup before handoff')
    need(signal.getsignal(signal.SIGALRM)is expired and 0<signal.getitimer(signal.ITIMER_REAL)[0]<=120,'active adapter preflight owner')
    original_argv=sys.argv;original_stdout=sys.stdout;terminal=Terminal(end);zero=False
    external=str(output)+'.observer'
    argv=[str(path),'--source-pin',json.dumps(controller,separators=(',',':')),'--selection',str(selection_operand[0]),'--selection-pin',json.dumps(selection_operand[1],separators=(',',':')),'--external-output',external]
    # Preserve the active original startup timer through observer imports/argparse.
    # Its main replaces and restores this handler; no handoff interval is unguarded.
    try:
        sys.argv=argv;sys.stdout=terminal
        try:exec(code,{'__name__':'__main__','__file__':str(path),'ADAPTER_ORIGIN':ORIGIN})
        except SystemExit as exc:need(type(exc.code)is int and exc.code==0,'original observer natural zero');zero=True
        need(zero and time.monotonic()<end and signal.getitimer(signal.ITIMER_REAL)==(0.,0.) and ''.join(terminal.parts)=='','original silent outer route closed timer')
    finally:
        sys.argv=original_argv;sys.stdout=original_stdout
        need(time.monotonic()<end,'original remaining postflight')
        signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,end-time.monotonic())
    captures.end=end;raw=captures.read(literal(external),8192);need(len(raw)==8192,'fixed durable observer slot');value=parse(raw)
    need(value.get('schema')=='neural084_full54_external_v1' and value.get('status')=='complete_unqualified' and value.get('source')==controller and value.get('selection')==selection_operand[1] and value.get('attempt')==str(output),'exact original complete source/selection/attempt')
    need(type(value.get('query_count'))is int and value['query_count']==selected['plan']['query_count'] and value.get('limits')==selected['limits'],'complete selected query count and resource profile')
    need(value.get('origin_monotonic')==ORIGIN and value.get('whole_deadline')==end and value.get('outer_deadline')==end+60,'unchanged original clock endpoints')
    need(value.get('full54_source_scope')is True and value.get('scientific_qualified')is False and value.get('runtime_qualified')is False and value.get('grading_performed')is False and value.get('nested_native_recovery_may_be_required')is False and value.get('automatic_retry')is False,'original complete unqualified custody')
    child=value['child'];need(child.get('natural_exit')is True and type(child.get('exit_code'))is int and child.get('exit_code')==0 and child.get('process_reaped')is True and child.get('process_group_absent')is True and child.get('streams_closed')is True,'original closed worker')
    need(all(child.get(k) is False for k in ('timed_out','kill_sent')) and all(child.get(k) is None for k in ('error_type','timer_disable_error','timer_restore_error')),'unforced error-free original worker closure')
    descriptor(value['submission'],64000000);descriptor(value['complete'],64000000)
    return {'external':pin(raw),'submission':value['submission'],'complete':value['complete']}


def main(argv=None):
    global FINAL_END
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('program','output','review','source-sha256'):p.add_argument('--'+name,required=True)
    for name in ('source-bytes','other-reserve-bytes'):p.add_argument('--'+name,required=True,type=int)
    args=p.parse_args(argv);result=1;end=ORIGIN+120
    try:
        need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated nonwriting entry')
        need(INITIAL_HANDLER is not None and signal.getsignal(signal.SIGALRM)is expired and 0<signal.getitimer(signal.ITIMER_REAL)[0]<=120,'startup enclosure before imports/source reads')
        need(type(sys.pycache_prefix)is str and sys.pycache_prefix and not os.path.lexists(literal(sys.pycache_prefix)),'fresh disabled bytecode prefix')
        cache=sys.pycache_prefix;captures=Captures(end);expected=descriptor({'bytes':args.source_bytes,'sha256':args.source_sha256},32768)
        binding=own_sources(captures,expected);compiled,path,controller,bodies,lock=target(captures,binding)
        selected,operand,metadata=bind(args,captures,expected,binding,bodies,lock);end=ORIGIN+selected['limits']['whole_seconds'];FINAL_END=end;captures.tick()
        completed=invoke(compiled,path,operand,controller,end,literal(args.output),captures,selected)
        for path,pp,cap in metadata:captures.read(path,cap,pp)
        own_sources(captures,expected);target(captures,binding)
        need(sys.pycache_prefix==cache and not os.path.lexists(cache),'same absent disabled bytecode prefix');captures.tick()
        value={'schema':'neural084_full54_unscored_result_v1','task_id':TASK,'status':'complete_unscored','participant_count':54,'query_count':selected['plan']['query_count'],'controller_result':completed,'adapter_source':expected,'controller_source':controller,'private_grading_authorized':False,'private_grading_performed':False,'scientific_scoring':False,'runtime_qualified':False,'scientific_qualified':False,'adapter_metadata_read_reserved_bytes':captures.reserved,'requires_observed_adapter_exit_zero':True}
        terminal=json.dumps(value,sort_keys=True,separators=(',',':'))
        need(len(terminal.encode())+1<=8192,'bounded adapter result')
        print(terminal,flush=True);captures.tick();result=0
    except BaseException:result=1
    finally:
        try:signal.setitimer(signal.ITIMER_REAL,0)
        except BaseException:result=1
        try:signal.signal(signal.SIGALRM,INITIAL_HANDLER)
        except BaseException:result=1
        if time.monotonic()>=end:result=1
    return result

if __name__=='__main__':
    result=main()
    if time.monotonic()>=FINAL_END:result=1
    raise SystemExit(result)
