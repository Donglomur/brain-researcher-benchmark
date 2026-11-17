"""Root-selected NEURAL075 paired-root descriptor to the complete60 controller."""
import time
ORIGIN = time.monotonic()
import argparse, hashlib, json, os, signal, stat, sys, types
from pathlib import Path
HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[3]
TASK = 'NEURAL-075'
READ_CAP = 750000

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

def source_module(captures, row, name):
    need(type(row)is dict and set(row)=={'path','bytes','sha256'},'source descriptor')
    p=relative(row['path']); raw=captures.read(p,200000,descriptor({k:row[k] for k in ('bytes','sha256')},200000))
    m=types.ModuleType(name);m.__file__=str(p);exec(compile(raw,str(p),'exec'),m.__dict__);return m

def selected_descriptor(value, cap):
    need(type(value)is dict and set(value)=={'path','bytes','sha256'},'exact selected descriptor')
    descriptor({k:value[k] for k in ('bytes','sha256')},cap)
    return literal(value['path']),{k:value[k] for k in ('bytes','sha256')}


def own_sources(captures, expected):
    raw=captures.read(HERE/'SOURCE_MANIFEST.json',32768,expected);manifest=parse(raw)
    need(manifest['schema']=='neural075_complete_pair_adapter_source_v1' and manifest['task_id']==TASK,'exact adapter source schema')
    need(type(manifest['files'])is dict and set(manifest['files'])=={'adapter.py','BINDINGS.json','ACCESS_BINDING.json','README.md'},'exact adapter source closure')
    bodies={n:captures.read(HERE/n,100000,descriptor(p,100000))for n,p in manifest['files'].items()}
    binding=parse(bodies['BINDINGS.json']);access=parse(bodies['ACCESS_BINDING.json'])
    need(binding['schema']=='neural075_complete_pair_adapter_bindings_v1' and binding['task_id']==access['task_id']==TASK,'task source binding')
    need(binding['paired_access_binding']=={'path':(HERE/'ACCESS_BINDING.json').relative_to(ROOT).as_posix(),**pin(bodies['ACCESS_BINDING.json'])},'exact access material binding')
    need(access['conditions']==binding['conditions'] and access['full_article_supplied']is False,'no invented full-paper exposure')
    return binding


CLOCK_DELTAS=(
    ('origin=time.monotonic();end=origin+total_seconds',
     'origin=SELECTED_ORIGIN;end=origin+total_seconds'),
    ('signal.setitimer(signal.ITIMER_REAL,total_seconds)',
     "m.need(time.monotonic()<end);signal.setitimer(signal.ITIMER_REAL,end-time.monotonic())"),
)


def adapted_panel(raw):
    text=raw.decode('utf-8');original=text
    for old,new in CLOCK_DELTAS:
        need(text.count(old)==1 and new not in text,'exact single panel clock adaptation')
        text=text.replace(old,new,1)
    reverse=text
    for old,new in reversed(CLOCK_DELTAS):reverse=reverse.replace(new,old,1)
    need(reverse==original,'exact reverse clock delta')
    return text.encode('utf-8')


def target(captures,binding):
    row=binding['controller_manifest'];source={k:row[k]for k in ('bytes','sha256')}
    raw=captures.read(relative(row['path']),32768,source);manifest=parse(raw)
    need(manifest['schema']=='neural075_invocation_source_v1' and set(manifest['runtime_files'])=={'LOCK.json','entry.py','holder.py','invoke.py','panel.py','stage.py'},'complete frozen controller source')
    bodies={}
    for name,row in binding['controller_members'].items():
        q={k:row[k]for k in ('bytes','sha256')};need(manifest['runtime_files'][name]==q,'controller member pin')
        bodies[name]=captures.read(relative(row['path']),100000,q)
    need(set(bodies)==set(manifest['runtime_files']),'complete controller body capture')
    lock=parse(bodies['LOCK.json']);need(lock['cases']==binding['cases'] and len(lock['cases'])==30 and lock['condition']==binding['condition'] and lock['collection_manifest']==binding['collection_manifest'],'unchanged complete30 task')
    modules={}
    for name in ('invoke.py','panel.py'):
        p=relative(binding['controller_members'][name]['path']);m=types.ModuleType('_neural075_registration_'+name[:-3]);m.__file__=str(p)
        body=adapted_panel(bodies[name]) if name=='panel.py' else bodies[name]
        m.__dict__['SELECTED_ORIGIN']=ORIGIN;exec(compile(body,str(p),'exec'),m.__dict__);modules[name]=m
    return modules['panel.py'],modules['invoke.py'],lock


def metadata_operand(captures,row,cap=32768):
    path,pp=selected_descriptor(row,cap)
    return parse(captures.read(path,cap,pp)),(path,pp)


def runtime_receipt(value,role,expected,binding):
    need(type(value)is dict and set(value)=={'schema','task_id','qualified','role','controller_source','adapter_source','dependencies','image','python_executable','natural_zero_observed','evidence'},'exact root runtime prerequisite')
    need(value['schema']=='neural075_pair_runtime_prerequisite_v1' and value['task_id']==TASK and value['qualified']is True and value['role']==role and value['natural_zero_observed']is True,'independent positive runtime prerequisite')
    need(value['controller_source']=={k:binding['controller_manifest'][k]for k in ('bytes','sha256')} and value['adapter_source']==expected and value['dependencies']==binding['dependencies'],'current exact runtime/task versions')
    need(value['image']==binding['fixed_image'],'fixed candidate image')
    need(value['python_executable']==str(Path(sys.executable).resolve()) if role=='trusted_staging' else value['python_executable']=='python','exact trusted interpreter operand')
    selected_descriptor(value['evidence'],1048576)


def commit_metadata(c,arm,program,expected,binding):
    required={'schema','condition','program','source','lock','image','cases','seconds','memory','exposure','access','collection_manifest'}
    need(type(c)is dict and set(c)==required,'exact original frozen commit schema')
    source={k:binding['controller_manifest'][k]for k in ('bytes','sha256')}
    lock={k:binding['controller_members']['LOCK.json'][k]for k in ('bytes','sha256')}
    need(c['schema']=='neural075_program_commit_v1' and c['condition']==binding['condition'] and c['access']==arm and c['source']==source and c['lock']==lock and c['image']==binding['fixed_image'],'original commit source/access identity')
    need(c['cases']==binding['cases'] and c['collection_manifest']==binding['collection_manifest'] and c['program']=={k:program[k]for k in ('bytes','sha256')},'complete cases and selected program')
    need(type(c['seconds'])is int and 1<=c['seconds']<=7200 and type(c['memory'])is int and 536870912<=c['memory']<=4294967296,'original committed resources')
    need(type(c['exposure'])is str and 0<len(c['exposure'])<=4096,'original declared exposure')


def bind(args,captures,expected,binding):
    need(type(args.other_reserve_bytes)is int and args.other_reserve_bytes>=0,'explicit current other reservation')
    review_path=literal(args.review);review_raw=captures.read(review_path,32768);review=parse(review_raw)
    need(type(review)is dict and set(review)=={'schema','task_id','approved','adapter_source','selection','program_bundle','private_scoring_authorized'},'exact root review')
    need(review['schema']=='neural075_complete_pair_review_v1' and review['task_id']==TASK and review['approved']is True and review['private_scoring_authorized']is False,'explicit paired unscored authority')
    need(descriptor(review['adapter_source'],32768)==expected,'current adapter review')
    selection,sp=metadata_operand(captures,review['selection'])
    required={'schema','task_id','execution_selected','repository','output','collection','docker_socket','other_future_bytes','source','programs','commitments','authoring_exposure_attestation','host_runtime_receipt','candidate_runtime_receipt','case_count','arm_view_count','retain_bytes','read_bytes','write_bytes','whole_seconds','private_scoring_authorized'}
    need(type(selection)is dict and set(selection)==required,'exact complete paired selection')
    need(selection['schema']=='neural075_complete_pair_selection_v1' and selection['task_id']==TASK and selection['execution_selected']is True and selection['private_scoring_authorized']is False,'complete unscored selection')
    need(selection['repository']==str(ROOT) and selection['source']=={k:binding['controller_manifest'][k]for k in ('bytes','sha256')},'exact repository and controller source')
    need(type(selection['other_future_bytes'])is int and selection['other_future_bytes']==args.other_reserve_bytes,'same current other reservation')
    need(literal(selection['output'])==literal(args.output) and not os.path.lexists(args.output),'same fresh paired output')
    for name in ('collection','docker_socket'):literal(selection[name])
    need(selection['case_count']==30 and type(selection['case_count'])is int and selection['arm_view_count']==60 and type(selection['arm_view_count'])is int,'all30/60 preserved')
    need(selection['retain_bytes']==2000000000 and selection['read_bytes']==200000000000 and selection['write_bytes']==32000000000,'unchanged whole controller resource ceilings')
    need(all(type(selection[k])is int for k in ('retain_bytes','read_bytes','write_bytes','whole_seconds')),'integer complete phase resources')
    need(type(selection['programs'])is dict and set(selection['programs'])=={'A','B'} and type(selection['commitments'])is dict and set(selection['commitments'])=={'A','B'},'both frozen programs')
    bundle_path,bundle_pin=selected_descriptor(review['program_bundle'],32768)
    need(bundle_path==literal(args.program),'program operand is the exact paired-root descriptor')
    att,ap=metadata_operand(captures,selection['authoring_exposure_attestation'])
    fields={'schema','task_id','qualified','source','adapter_source','programs','commitments','program_bundle','paired_access_binding','case_feedback_before_global_commitment','query_payload_before_program_commitment','separately_authored','arms'}
    need(type(att)is dict and set(att)==fields and att['schema']=='neural075_root_pair_authoring_attestation_v1' and att['task_id']==TASK and att['qualified']is True,'independent root paired context attestation')
    programs={arm:{k:row[k]for k in ('bytes','sha256')}for arm,row in selection['programs'].items()}
    need(att['source']==selection['source'] and att['adapter_source']==expected and att['programs']==programs and att['commitments']==selection['commitments'] and att['program_bundle']==bundle_pin,'exact pair/context/source commitments')
    need(att['paired_access_binding']==binding['paired_access_binding'] and att['case_feedback_before_global_commitment']is False and att['query_payload_before_program_commitment']is False and att['separately_authored']is True,'source-defined access and pre-query freeze custody')
    need(type(att['arms'])is dict and set(att['arms'])=={'A','B'},'both independently authored contexts')
    context_ids=[];provenance=[];directories=[]
    for arm in ('A','B'):
        program_path,program_pin=selected_descriptor(selection['programs'][arm],131072)
        row=selection['commitments'][arm];need(type(row)is dict and set(row)=={'directory','commit_pin'},'original frozen-program directory descriptor')
        directory=literal(row['directory']);descriptor(row['commit_pin'],10000);directories.append(str(directory))
        need(program_path==directory/'program.py','program exactly inside frozen commitment')
        a=att['arms'][arm];need(type(a)is dict and set(a)=={'context_id','information_condition','program','commitment','provenance'},'exact arm provenance')
        need(a['information_condition']==binding['conditions'][arm] and a['program']==program_pin and a['commitment']==row,'exact independent material and frozen program identity')
        ident=a['context_id'];need(type(ident)is str and 0<len(ident)<=96 and ident[0].isalnum() and all(c.isalnum()or c in '_.:-'for c in ident),'bounded authoring context')
        _,pp=selected_descriptor(a['provenance'],1048576);provenance.append((pp['bytes'],pp['sha256']));context_ids.append(ident)
    need(len(set(context_ids))==len(set(provenance))==len(set(directories))==2,'two distinct context/provenance/commitment records')
    # The root owns independent provenance verification. These descriptors do
    # not prove authorship histories; no candidate/provenance bodies are opened.
    operands=[(review_path,pin(review_raw)),sp,(bundle_path,bundle_pin),ap]
    for name,role in [('host_runtime_receipt','trusted_staging'),('candidate_runtime_receipt','candidate_image')]:
        value,operand=metadata_operand(captures,selection[name]);runtime_receipt(value,role,expected,binding);operands.append(operand)
    bundle=parse(captures.read(bundle_path,32768,bundle_pin))
    need(type(bundle)is dict and set(bundle)=={'schema','task_id','programs','commitments'} and bundle['schema']=='neural075_committed_pair_descriptor_v1' and bundle['task_id']==TASK,'typed complete paired-root descriptor')
    need(bundle['programs']==selection['programs'] and bundle['commitments']==selection['commitments'],'exact pair, no single-arm proxy')
    commits={}
    for arm,row in selection['commitments'].items():
        operand=(literal(row['directory'])/'COMMIT.json',row['commit_pin'])
        commits[arm]=parse(captures.read(operand[0],10000,operand[1]));commit_metadata(commits[arm],arm,selection['programs'][arm],expected,binding);operands.append(operand)
    whole=sum(30*(commits[a]['seconds']+660+900+120)for a in ('A','B'))+1800
    need(selection['whole_seconds']==whole,'exact original complete-controller time formula')
    captures.tick();return selection,operands


def invoke(panel,invocation,selection,captures):
    captures.tick();panel.SELECTED_ORIGIN=ORIGIN
    value=panel.run(invocation,ROOT,selection['source'],selection['commitments'],selection['collection'],
                    selection['output'],selection['other_future_bytes'],selection['docker_socket'])
    need(type(value)is dict and set(value)=={'status','completion','outputs'} and value['status']=='complete_unscored' and value['outputs']==60,'complete unscored60 result')
    descriptor(value['completion'],100000);return value


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('program','output','review','source-sha256'):p.add_argument('--'+key,required=True)
    for key in ('source-bytes','other-reserve-bytes'):p.add_argument('--'+key,required=True,type=int)
    args=p.parse_args(argv);saved=None;code=1;end=ORIGIN+60
    try:
        need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,'isolated no-site nonwriting launch')
        need(type(sys.pycache_prefix)is str and bool(sys.pycache_prefix),'explicit disabled cache prefix')
        cache=literal(sys.pycache_prefix);need(not os.path.lexists(cache),'fresh disabled cache prefix')
        need(signal.getitimer(signal.ITIMER_REAL)==(0.,0.),'no inherited timer')
        saved=signal.getsignal(signal.SIGALRM)
        def expired(*_):raise TimeoutError('original complete-pair adapter deadline')
        signal.signal(signal.SIGALRM,expired);need(time.monotonic()<end,'original startup deadline')
        signal.setitimer(signal.ITIMER_REAL,end-time.monotonic())
        captures=Captures(end);expected=descriptor({'bytes':args.source_bytes,'sha256':args.source_sha256},32768)
        binding=own_sources(captures,expected);panel,invocation,lock=target(captures,binding)
        selection,operands=bind(args,captures,expected,binding)
        end=ORIGIN+selection['whole_seconds']
        # Only our preflight alarm is removed. The captured panel's two exact
        # clock adaptations arm the remaining original whole-clock budget.
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,saved);captures.tick()
        value=invoke(panel,invocation,selection,captures)
        need(signal.getitimer(signal.ITIMER_REAL)==(0.,0.) and time.monotonic()<end,'panel timer closed before original endpoint')
        signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,end-time.monotonic());captures.end=end
        for path,pp in operands:captures.read(path,32768,pp)
        own_sources(captures,expected)
        need(sys.pycache_prefix==str(cache) and not os.path.lexists(cache),'same absent disabled cache')
        captures.tick();print(json.dumps(value,separators=(',',':')));code=0
    except BaseException:code=1
    finally:
        if saved is not None:
            try:signal.setitimer(signal.ITIMER_REAL,0)
            except BaseException:code=1
            try:signal.signal(signal.SIGALRM,saved)
            except BaseException:code=1
    return code if time.monotonic()<end else 1


if __name__=='__main__':raise SystemExit(main())

