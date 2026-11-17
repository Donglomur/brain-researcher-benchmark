"""Complete iSTTC full100000 reproduction/improvement paired route; no private grading authority."""
import time
ORIGIN = time.monotonic()
import signal
INITIAL_HANDLER = None
INITIAL_HANDLERS = {}


def expired(*_):
    raise TimeoutError('original iSTTC full100000 paired adapter deadline')


def enter_startup():
    global INITIAL_HANDLER, INITIAL_HANDLERS
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise ValueError('fresh standalone adapter has no inherited timer')
    INITIAL_HANDLERS = {n:signal.getsignal(n) for n in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
    INITIAL_HANDLER = INITIAL_HANDLERS[signal.SIGALRM]
    remaining = ORIGIN + 120 - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('original startup deadline already expired')
    try:
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, remaining)
    except BaseException as primary:
        failures=[]
        actions=[lambda:signal.setitimer(signal.ITIMER_REAL,0)]
        actions.extend(lambda number=number,handler=handler:signal.signal(number,handler)
                       for number,handler in INITIAL_HANDLERS.items())
        for action in actions:
            try:action()
            except BaseException as error:failures.append(type(error).__name__)
        if failures:primary.add_note('Independent startup cleanup uncertainty: '+','.join(failures))
        raise


if __name__ == '__main__':
    enter_startup()

import argparse
import ast
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys

HERE = Path(__file__).absolute().parent
ROOT = HERE.parents[4]
TASK = 'PAPER-paper-method-add-004'
READ_CAP = 8 * 1024 ** 2
MIB = 1024 ** 2
FINAL_END = ORIGIN + 120
SCOPE = {'coverage': {'units': 100000, 'continuous_records': 100000, 'continuous_ms': 600000, 'trial_records': 4000000, 'trials_per_unit': 40, 'trial_ms': 1000}, 'arms': ['A', 'B'], 'methods': ['reproduction', 'improvement'], 'global_programs': 4, 'candidate_phases': 4, 'trusted_reference_phases': 1, 'total_phases': 5, 'reproduction_rows_per_arm': 400000, 'improvement_rows_per_arm': 600000, 'fixed_baseline_rows': 400000, 'candidate_program_cap_each': 8388608, 'candidate_program_domain_is_new': True, 'whole_paper_reproduction': False, 'released_Hawkes_simulation_endpoint': True, 'real_neural_signal_test': False, 'author_source_files_B_only': 23}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def equal(left, right):
    return encode(left) == encode(right)


def parse(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def descriptor(value, cap, allow_empty=False):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}, 'exact bounded descriptor')
    need(type(value['bytes']) is int and (0 if allow_empty else 1) <= value['bytes'] <= cap, 'bounded nonboolean extent')
    digest = value['sha256']
    need(type(digest) is str and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest),
         'lowercase SHA256 identity')
    return value


def literal(value):
    need(type(value) is str and value and not any(c in value for c in '\x00\r\n,'), 'literal path')
    path = Path(value)
    need(path.is_absolute() and '..' not in path.parts and str(path) == value, 'canonical absolute path')
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'no linked path components')
    return path


def relative(value):
    need(type(value) is str and value and '\\' not in value, 'repository-relative path')
    path = Path(value)
    need(not path.is_absolute() and all(p not in ('', '.', '..') for p in value.split('/'))
         and path.as_posix() == value, 'confined repository-relative path')
    return literal(str(ROOT / path))


def row(value, cap):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'exact repository descriptor')
    return relative(value['path']), descriptor({k: value[k] for k in ('bytes', 'sha256')}, cap)


class Captures:
    def __init__(self, end):
        self.end = end
        self.reserved = 0

    def tick(self):
        need(time.monotonic() < self.end, 'original adapter deadline')

    def read(self, path, cap, expected=None, *, allow_empty=False):
        self.tick()
        path = literal(str(path))
        if expected is not None:
            descriptor(expected, cap, allow_empty=allow_empty)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and (0 if allow_empty else 1) <= before.st_size <= cap,
                 'ordinary bounded captured metadata')
            need(expected is None or before.st_size == expected['bytes'], 'pinned extent before read')
            charge = before.st_size + 1
            need(self.reserved + charge <= READ_CAP, 'additional adapter metadata read ceiling')
            self.reserved += charge
            self.tick()
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(charge)
            keys = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_uid', 'st_gid', 'st_mtime_ns', 'st_ctime_ns')
            signature = lambda value: tuple(getattr(value, k) for k in keys)
            need(len(raw) == before.st_size and signature(before) == signature(os.fstat(fd)) == signature(path.lstat()),
                 'stable fd and named captured identity')
            need(expected is None or pin(raw) == expected, 'exact captured content')
            self.tick()
            return raw
        finally:
            os.close(fd)


def metadata(captures, value, cap=65536):
    path, identity = row(value, cap)
    return parse(captures.read(path, cap, identity)), (path, identity, cap)



def startup_owned():
    before=time.monotonic(); timer=signal.getitimer(signal.ITIMER_REAL); after=time.monotonic()
    need(signal.getsignal(signal.SIGALRM) is expired and timer[1]==0.0
         and 0.0<timer[0]<=ORIGIN+120-before+0.001 and after<ORIGIN+120,
         'live adapter-owned original120s startup alarm')


def transfer_startup():
    startup_owned()
    signal.signal(signal.SIGALRM,expired)
    # A delayed handoff cannot renew an already-expired original startup window.
    need(time.monotonic()<ORIGIN+120,'original startup still live at transfer')
    remaining=ORIGIN+900240-time.monotonic()
    need(remaining>0,'positive original outer remainder')
    signal.setitimer(signal.ITIMER_REAL,remaining)
    return True


def own_sources(captures,expected):
    manifest=parse(captures.read(HERE/'SOURCE_MANIFEST.json',32768,expected))
    need(set(manifest)=={'schema','task_id','files'} and manifest['schema']=='isttc_full100000_registration_source_v1'
         and manifest['task_id']==TASK and set(manifest['files'])=={'adapter.py','BINDING.json','README.md'},'exact adapter source closure')
    bodies={n:captures.read(HERE/n,131072,descriptor(q,131072)) for n,q in manifest['files'].items()}
    b=parse(bodies['BINDING.json'])
    need(b['schema']=='isttc_full100000_registration_binding_v1' and b['task_id']==TASK and equal(b['scope'],SCOPE)
         and b['private_grading_authorized'] is False and type(b['adapter_metadata_read_cap']) is int and b['adapter_metadata_read_cap']==READ_CAP
         and type(b['adapter_persistent_writes']) is int and b['adapter_persistent_writes']==0
         and b['startup_seconds']==120 and b['work_seconds']==900000 and b['publication_seconds']==900120 and b['outer_seconds']==900240,
         'same complete selected full100000 source/resource profile')
    return b


def adapted_observe(raw,filename):
    """Two reversible AST nodes; preserve original main, verifier and cleanup."""
    original=ast.parse(raw.decode('utf-8'),filename);changed=copy.deepcopy(original)
    origins=[n for n in changed.body if isinstance(n,ast.Assign) and len(n.targets)==1
             and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='ORIGIN']
    expected_origin=ast.parse('time.monotonic()',mode='eval').body
    need(len(origins)==1 and ast.dump(origins[0].value)==ast.dump(expected_origin),'one exact original observer origin')
    origins[0].value=ast.Name(id='ADAPTER_ORIGIN',ctx=ast.Load())
    startup=ast.parse("if __name__=='__main__':enter_startup()").body[0]
    matches=[i for i,n in enumerate(changed.body) if ast.dump(n)==ast.dump(startup)]
    need(len(matches)==1,'one exact standalone startup owner call')
    changed.body[matches[0]]=ast.parse('CLOCK_OWNED=ADAPTER_TRANSFER_STARTUP()').body[0]
    initial=[n for n in original.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name)and t.id=='CLOCK_OWNED' for t in n.targets)]
    need(len(initial)==1 and ast.dump(initial[0].value)==ast.dump(ast.Constant(False)),'original cleanup ownership starts false')
    final=ast.parse("if __name__=='__main__':\n    result = main()\n    need(time.monotonic() < ORIGIN + 900240, 'standalone completion after cleanup before original outer deadline')\n    raise SystemExit(result)").body[0]
    need(ast.dump(original.body[-1])==ast.dump(final) and sum(isinstance(n,ast.Name)and n.id=='__name__' for n in ast.walk(original))==2,'exact startup/final observer guards')
    reverse=copy.deepcopy(changed)
    origin=next(n for n in reverse.body if isinstance(n,ast.Assign)and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)and n.targets[0].id=='ORIGIN')
    origin.value=copy.deepcopy(expected_origin);reverse.body[matches[0]]=copy.deepcopy(startup)
    need(ast.dump(reverse)==ast.dump(original),'exact reversible two-node whole-AST proof')
    ast.fix_missing_locations(changed)
    tail=ast.Module(body=[copy.deepcopy(changed.body[-1])],type_ignores=[]);ast.fix_missing_locations(tail)
    return compile(changed,filename,'exec'),compile(tail,filename,'exec')


def target(captures,binding):
    manifest,_=metadata(captures,binding['controller_manifest'],32768)
    need(set(manifest)=={'schema','task_id','source_only','files'} and manifest['schema']=='isttc_full100000_program_source_v1'
         and manifest['task_id']==TASK and manifest['source_only'] is True
         and equal(manifest['files'],binding['controller_members']) and len(manifest['files'])==24,
         'complete unchanged24-member source-only runtime closure')
    directory=relative(binding['controller_directory'])
    bodies={name:captures.read(directory/name,131072,descriptor(identity,131072,allow_empty=True),allow_empty=True) for name,identity in manifest['files'].items()}
    need(equal(parse(bodies['RESOURCE_PLAN.json']),binding['controller_resources']),'unchanged full campaign resource profile')
    for item in binding['selected_metadata']: metadata(captures,item,131072)
    filename=directory/'observe.py';compiled,guard=adapted_observe(bodies['observe.py'],str(filename))
    return compiled,guard,filename,bodies


def runtime_review(value,source,binding):
    keys={'schema','task_id','qualified','adapter_source','controller_source','host_python','scope','resources','metadata_read_cap',
          'adapter_persistent_writes','whole_route_qualified','original_clock_handoff_qualified','normal_source_output_custody_qualified',
          'evidence','attestation_kind','scientific_qualification','private_grading_authorized','forced_stop_custody_complete'}
    need(type(value) is dict and set(value)==keys and value['schema']=='isttc_full100000_registration_runtime_v1'
         and value['task_id']==TASK and value['qualified'] is True,'separate genuine complete full100000 four-program pair runtime qualification prerequisite')
    need(value['adapter_source']==source and value['controller_source']==binding['controller_manifest'] and value['host_python']==sys.executable
         and equal(value['scope'],SCOPE) and equal(value['resources'],binding['resources']), 'exact qualified source/interpreter/complete scope/resources')
    need(type(value['metadata_read_cap']) is int and value['metadata_read_cap']==READ_CAP
         and type(value['adapter_persistent_writes']) is int and value['adapter_persistent_writes']==0
         and all(value[k] is True for k in ('whole_route_qualified','original_clock_handoff_qualified','normal_source_output_custody_qualified'))
         and value['attestation_kind']=='root_operator_review_not_cryptographic_signature'
         and all(value[k] is False for k in ('scientific_qualification','private_grading_authorized','forced_stop_custody_complete')),
         'runtime qualification never grants science, grading or forced-stop recovery proof')
    row(value['evidence'],MIB) # Descriptor only; no authentic scientific result body.


def pair_metadata(pair):
    need(type(pair) is dict and set(pair)=={'schema','task_id','programs','authorship','authoring_protocol','root_attests_separate_contexts',
          'root_attests_records_are_authentic','root_attests_no_cross_arm_feedback'} and pair['schema']=='isttc_independent_program_pair_v1'
         and pair['task_id']==TASK and type(pair['programs']) is dict and type(pair['authorship']) is dict
         and set(pair['programs'])==set(pair['authorship'])=={'A','B'}
         and all(pair[k] is True for k in ('root_attests_separate_contexts','root_attests_records_are_authentic','root_attests_no_cross_arm_feedback')),
         'complete independent four-program pair descriptor, never one-arm fallback')
    operands=[(pair['authoring_protocol'],MIB),*[(pair['authorship'][a],MIB) for a in ('A','B')]]
    for arm in ('A','B'):
        need(type(pair['programs'][arm]) is dict and set(pair['programs'][arm])=={'reproduction','improvement'},'both original methods per access arm')
        operands.extend((pair['programs'][arm][role],cap) for role,cap in [('reproduction',8*MIB),('improvement',8*MIB)])
    for d,cap in operands:
        need(type(d) is dict and set(d)=={'path','bytes','sha256'},'typed full pair operand')
        literal(d['path']);descriptor({k:d[k] for k in ('bytes','sha256')},cap)


def bind(args,captures,source,binding):
    review_path=literal(args.review);raw=captures.read(review_path,32768);review=parse(raw)
    fields={'schema','task_id','approved','adapter_source','controller_source','selection','output','adapter_runtime','source_exposure',
            'typed_result','private_grading_authorized'}
    need(type(review) is dict and set(review)==fields and review['schema']=='isttc_full100000_registration_review_v1'
         and review['task_id']==TASK and review['approved'] is True and review['adapter_source']==source
         and review['controller_source']==binding['controller_manifest'] and review['private_grading_authorized'] is False
         and review['typed_result']=='isttc_full100000_ungraded_result_v1','exact root complete four-program pair review')
    qualified,runtime_operand=metadata(captures,review['adapter_runtime'],32768)
    runtime_review(qualified,source,binding) # Before pair, selection, candidate/output operand conversion or reads.
    exposure={'condition':'full100000_pair','arms':['A','B'],'methods':['reproduction','improvement'],'four_programs_globally_frozen':True,'full_units':100000,'reproduction_rows_per_arm':400000,'improvement_rows_per_arm':600000,'fixed_baseline_rows':400000,'source_only_independent_authorship_proof':False,'historical_public_exposure_acknowledged':True,'no_cross_arm_feedback_attested':True,'whole_paper_reproduction':False,'private_truth_or_grader_visible':False}
    need(equal(review['source_exposure'],exposure),'complete paired exposure attestation')
    selected,selection_operand=metadata(captures,review['selection'],32768)
    need(selected.get('schema')=='isttc_complete_program_operation_v1' and selected.get('task_id')==TASK and selected.get('operation_selected') is True
         and all(selected.get(k) is False for k in ('runtime_qualified','scientific_qualification','full_paper_reproduction')),
         'exact selected complete source-only operation, not inherited science qualification')
    need(selected.get('repo')==str(ROOT)
         and selected.get('source_manifest')=={k:binding['controller_manifest'][k] for k in ('bytes','sha256')}
         and type(args.other_reserve_bytes) is int and args.other_reserve_bytes>=0
         and type(selected.get('other_future_bytes')) is int and selected['other_future_bytes']==args.other_reserve_bytes,
         'same frozen source/export/repository and current OTHER')
    d=selected['pair'];need(type(d) is dict and set(d)=={'path','bytes','sha256'},'exact selected pair descriptor')
    pair_path=literal(d['path']);pair_pin=descriptor({k:d[k] for k in ('bytes','sha256')},MIB)
    need(pair_path==literal(args.program),'central program operand is the entire selected pair descriptor')
    pair_raw=captures.read(pair_path,MIB,pair_pin);pair=parse(pair_raw);pair_metadata(pair)
    out=literal(args.output);need(out==literal(review['output']) and not os.path.lexists(out),'one fresh root-owned whole observation directory')
    need(not out.is_relative_to(ROOT),'whole attempt outside immutable source repository')
    for operand in (review_path,selection_operand[0],runtime_operand[0],pair_path):
        need(not operand.is_relative_to(out),'authority outside mutable attempt')
    return {'review':review,'selection':selected,'selection_operand':selection_operand,'output':out,'pair':pair,'pair_pin':pair_pin,
            'metadata_pins':[(review_path,pin(raw),32768),selection_operand,runtime_operand,(pair_path,pair_pin,MIB)]}


def invoke(compiled,guard,path,admitted):
    startup_owned()
    namespace={'__name__':'__adapter_load__','__file__':str(path),'ADAPTER_ORIGIN':ORIGIN,'ADAPTER_TRANSFER_STARTUP':transfer_startup}
    old_argv=sys.argv;op=admitted['selection_operand'];returned=False;transferred=False
    try:
        # Imports and argument parsing may fail before original main's cleanup try.
        # Adapter main's independent final cleanup remains authoritative on failure.
        exec(compiled,namespace)
        need(namespace['ORIGIN']==ORIGIN and namespace['CLOCK_OWNED']is True and signal.getsignal(signal.SIGALRM)is expired,'same original origin and literal transferred cleanup ownership')
        transferred=True
        sys.argv=[str(path),'--selection',str(op[0]),'--selection-sha256',op[1]['sha256'],'--output',str(admitted['output'])]
        namespace['__name__']='__main__'
        try:exec(guard,namespace)
        except SystemExit as error:
            need(type(error.code)is int and error.code==0,'original observer natural integer zero');returned=True
        need(returned and time.monotonic()<ORIGIN+900240 and signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0)
             and signal.getsignal(signal.SIGALRM)is expired
             and all(signal.getsignal(n)is INITIAL_HANDLERS[n] for n in (signal.SIGTERM,signal.SIGINT)),
             'original observer cleanup completed and all three captured handlers restored')
    finally:
        sys.argv=old_argv
        if transferred:
            # Cooperative return-to-rearm gap; external natural closure is required.
            remaining=ORIGIN+900240-time.monotonic();need(remaining>0,'original postflight remainder')
            signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,remaining)
    return namespace


def expected_contexts():
    """Declaration pinned to the selected controller; scientific checks stay original."""
    rows=[{'role':r,'arm':a,'fold':None} for r in ('reproduction','improvement') for a in ('A','B')]+[{'role':'reference','arm':None,'fold':None}]
    for i,r in enumerate(rows):r['index']=i;r['phase_id']=f'{i:02d}-{r["role"]}-{r["arm"] or "fixed"}-full'
    return rows


def outcome(captures,binding,admitted):
    root=admitted['output'];source={k:binding['controller_manifest'][k] for k in ('bytes','sha256')}
    observed_raw=captures.read(root/'OBSERVED.json',65536);observed=parse(observed_raw)
    need(observed.get('schema')=='isttc_original_whole_command_observed_v1' and equal(observed.get('source'),source)
         and type(observed.get('original_phase_records_checked'))is int and observed['original_phase_records_checked']==5
         and all(observed.get(k)is False for k in ('runtime_qualified','scientific_qualification','full_paper_reproduction','private_grade_called','automatic_retry_authorized'))
         and observed.get('forced_stop_independent_host_and_daemon_state')=='unknown','exact original observer outcome without grading')
    child=observed['child']
    need(type(child)is dict and type(child.get('returncode'))is int and child['returncode']==0
         and all(child.get(k)is True for k in ('natural_exit','child_reaped','owned_group_absence_observed'))
         and child.get('forced_transitive_custody_complete')is False and equal(child.get('terminal_bytes'),{'stdout':0,'stderr':0})
         and type(child.get('original_origin'))in (int,float) and math.isfinite(child['original_origin']) and child['original_origin']==ORIGIN
         and type(child.get('elapsed_seconds'))in (int,float) and math.isfinite(child['elapsed_seconds']) and 0<=child['elapsed_seconds']<900120,'original child natural zero, original clock, no forced custody inference')
    collection_pin=descriptor(observed['collection'],MIB)
    raw=captures.read(root/'run/COLLECTION.json',MIB,collection_pin);collection=parse(raw)
    need(collection.get('schema')=='isttc_complete_paired_collection_v1' and collection.get('task_id')==TASK
         and equal(collection.get('source_manifest'),source) and equal(collection.get('contexts'),expected_contexts())
         and equal(collection.get('coverage'),SCOPE['coverage'])
         and type(collection.get('original_origin'))in (int,float) and math.isfinite(collection['original_origin']) and collection['original_origin']==ORIGIN
         and type(collection.get('work_end'))in (int,float) and math.isfinite(collection['work_end']) and collection['work_end']==ORIGIN+900000
         and all(collection.get(k)is False for k in ('private_grade_called','runtime_qualified','scientific_qualification','full_paper_reproduction','automatic_retry_authorized')),'same complete original metadata outcome')
    phases=collection['phase_receipts'];contexts=expected_contexts();ids={c['phase_id'] for c in contexts}
    need(type(phases)is list and len(phases)==5 and set(collection['artifacts'])==set(collection['support'])==ids,'all five original metadata sets')
    for row,ctx in zip(phases,contexts):
        need(type(row)is dict and equal(row.get('context'),ctx) and row.get('input_retired_after_exact_closure')is True,'original phase order and retirement')
        descriptor(row['request'],MIB)
        need(type(row['receipt'])is dict and set(row['receipt'])=={'path','bytes','sha256'} and row['receipt']['path']==f'phases/{ctx["phase_id"]}/ACCEPTED_PHASE.json','original owned phase receipt location')
        descriptor({k:row['receipt'][k] for k in ('bytes','sha256')},MIB)
        art=collection['artifacts'][ctx['phase_id']];need(type(art)is dict and set(art)=={'estimates.csv','methods.json'},'complete two-file metadata result')
        for name,cap in (('estimates.csv',100000000),('methods.json',20000)):
            d=art[name];need(type(d)is dict and set(d)=={'path','bytes','sha256'} and d['path']==f'phases/{ctx["phase_id"]}/closed/artifacts/{name}','exact original artifact location')
            descriptor({k:d[k] for k in ('bytes','sha256')},cap)
    commitment_pin=descriptor(collection['commitment'],MIB)
    committed=parse(captures.read(root/'run/PAIR_COMMITMENT.json',MIB,commitment_pin))
    need(committed.get('schema')=='isttc_global_four_program_commitment_v1' and committed.get('task_id')==TASK
         and equal(committed.get('pair'),admitted['pair_pin']) and set(committed.get('programs',{}))==set(committed.get('authorship',{}))=={'A','B'}
         and committed.get('data_or_native_phase_started')is False and committed.get('attestation_is_independent_history_proof')is False,'same original global four-program commitment')
    for arm in ('A','B'):
        need(type(committed['programs'][arm])is dict and set(committed['programs'][arm])=={'reproduction','improvement'},'four committed programs')
        for role in ('reproduction','improvement'):
            d=descriptor(committed['programs'][arm][role],8*MIB)
            need(equal(d,{k:admitted['pair']['programs'][arm][role][k] for k in ('bytes','sha256')}),'same selected program identity')
        need(equal(committed['authorship'][arm],{k:admitted['pair']['authorship'][arm][k] for k in ('bytes','sha256')}),'same selected authorship record')
    for key in ('baseline_policy','baseline_evidence','private_grade_join'):descriptor(collection[key],MIB)
    return {'observer':{'path':str(root/'OBSERVED.json'),**pin(observed_raw)},'collection':collection_pin,'four_program_commitment':commitment_pin,'artifacts':collection['artifacts'],
            'exact_original_record_validation':'The unchanged frozen observer.verify_collection reopens all5 original phase receipts and requests, invokes the exact controller closure validator, verifies retired views, hashes and validates every full CSV and methods artifact for100000 units, authenticates allfour committed programs, and joins fixed baseline/deferred private grading metadata. Adapter requires original observer natural zero and verifies bound metadata identities; it does not repeat scientific payload reads or scoring.',
            'scope':SCOPE}


def main(argv=None):
    global FINAL_END
    code=2;end=ORIGIN+120
    if not INITIAL_HANDLERS:return 2
    try:
        startup_owned();parser=argparse.ArgumentParser(description=__doc__)
        for name in ('program','output','review','source-sha256'):parser.add_argument('--'+name,required=True)
        for name in ('source-bytes','other-reserve-bytes'):parser.add_argument('--'+name,required=True,type=int)
        args=parser.parse_args(argv)
        need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and INITIAL_HANDLER is not None,'isolated pre-import enclosed adapter')
        cache=literal(sys.pycache_prefix);need(not os.path.lexists(cache),'fresh absent parent bytecode cache')
        captures=Captures(end);source=descriptor({'bytes':args.source_bytes,'sha256':args.source_sha256},32768)
        binding=own_sources(captures,source);compiled,guard,path,bodies=target(captures,binding)
        admitted=bind(args,captures,source,binding)
        end=ORIGIN+900240;FINAL_END=end
        invoke(compiled,guard,path,admitted)
        captures.end=end;result=outcome(captures,binding,admitted)
        for path,identity,cap in admitted['metadata_pins']:captures.read(path,cap,identity)
        need(equal(own_sources(captures,source),binding),'same adapter source after execution')
        target(captures,binding) # Source only; no second original observer execution.
        need(not os.path.lexists(cache),'no parent bytecode publication');captures.tick()
        terminal=encode({'schema':'isttc_full100000_ungraded_result_v1','task_id':TASK,'status':'complete_full100000_pair_collected_ungraded',
            'scope':SCOPE,'adapter_source':source,'controller_source':binding['controller_manifest'],'result':result,
            'scientific_qualification':False,'runtime_qualification_inferred_from_result':False,'full_paper_reproduction':False,
            'private_grading_authorized':False,'private_grading_performed':False,'forced_stop_custody_complete':False,
            'requires_observed_adapter_natural_exit_zero':True,'adapter_metadata_read_bytes':captures.reserved})
        need(len(terminal)<=16384,'bounded whole-pair terminal');print(terminal.decode(),flush=True);captures.tick();code=0
    except BaseException:code=2
    finally:
        try:signal.setitimer(signal.ITIMER_REAL,0)
        except BaseException:code=2
        for number,handler in INITIAL_HANDLERS.items():
            try:signal.signal(number,handler)
            except BaseException:code=2
        if time.monotonic()>=end:code=2
    return code


if __name__=='__main__':
    result=main()
    if time.monotonic()>=FINAL_END:result=2
    raise SystemExit(result)
