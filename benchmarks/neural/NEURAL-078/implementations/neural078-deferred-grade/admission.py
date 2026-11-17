"""Join complete original producer evidence before any private-reference access."""
import math,os,re
from pathlib import Path
from bound_io import need,identity,capture,parse,ordinary

def pin(value,cap=1000000):
    need(type(value)is dict and set(value)=={'bytes','sha256'} and type(value['bytes'])is int and 0<value['bytes']<=cap and type(value['sha256'])is str and re.fullmatch('[0-9a-f]{64}',value['sha256']) is not None,'Exact bounded content pin')
    return value

def only(value):return pin({k:value[k] for k in ('bytes','sha256')},100000000)

def same(a,b):
    # Strict recursive type equality: bool is never an integer receipt operand.
    if type(a)is not type(b):return False
    if type(a)is dict:return set(a)==set(b) and all(same(a[k],b[k]) for k in a)
    if type(a)is list:return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    return a==b

def finite(value,maximum):
    try:return type(value) in (int,float) and 0<=value<=maximum and math.isfinite(value)
    except OverflowError:return False

def absent(pid,pgid):
    need(type(pid)is int and type(pgid)is int and pid>1 and pgid>1,'Exact positive observed process IDs')
    for fn,n in ((os.kill,pid),(os.killpg,pgid)):
        try:fn(n,0)
        except ProcessLookupError:continue
        raise ValueError('Observed producer process/group still exists')
    return True

def closed_process(record,seconds):
    for key in ('natural_exit','process_reaped','process_group_absent','streams_closed'):need(record.get(key) is True,'Strict successful process closure')
    for key in ('timed_out','kill_sent'):need(record.get(key) is False,'Unforced successful process closure')
    for key in ('error_type','timer_disable_error','timer_restore_error'):need(record.get(key,'missing') is None,'Error-free process closure')
    need(type(record.get('exit_code'))is int and record['exit_code']==0,'Integer natural exit zero')
    need(finite(record.get('elapsed_seconds'),seconds),'Original process interval')
    need(type(record.get('pid'))is int and record['pid']>1,'Saved worker PID')
    for name in ('combined_stream_bytes','stdout_bytes'):need(type(record.get(name))is int and 0<=record[name]<=65536,'Bounded original process streams')
    need(record['stdout_bytes']<=record['combined_stream_bytes'],'Joined original stream counts')

def admit(args,sources,mods,observation,check=absent):
    c,policy,observer=mods['common'],mods['policy'],mods['observer']
    source=identity(sources['producer/program/SOURCE_MANIFEST.json']);adapter=identity(sources['producer/SOURCE_MANIFEST.json'])
    old=ordinary(args.producer_source);repo=ordinary(args.repository)
    need(old==repo/'authoring/delivery-20261105/common/neural078-holder-readiness-successor-v1','Selected latest original producer location')
    for name,raw in sources.items():
        if name.startswith('producer/'):capture(old/name[len('producer/'):],1000000,identity(raw))
    selection_raw=capture(args.producer_selection,32768,pin(args.selection_pin,32768));s=policy.selection(parse(selection_raw),source)
    need(s['repository']==str(repo),'Same selected original repository')
    root=ordinary(s['output']);need(root==ordinary(args.producer_attempt),'Same original output attempt')
    review_raw=capture(args.producer_review,32768,pin(args.review_pin,32768));review=parse(review_raw)
    expected_exposure=dict(condition='full8_investigation',agent_mode='frozen_program',public_files=15,primitive_files=8,private_source_visible=False,source_history_attested_by_root=True)
    need(review.get('schema')=='neural078_full8_central_review_v1' and review.get('task_id')=='NEURAL-078' and review.get('approved') is True and review.get('numeric_grade_authorized') is False,'Original producer-only central review')
    need(same(review['adapter_source'],adapter) and same(review['selection'],dict(path=str(ordinary(args.producer_selection)),**args.selection_pin)) and same(review['source_exposure'],expected_exposure),'Original review/source/selection/exposure join')
    need(type(review['authoring_context_id'])is str and 0<len(review['authoring_context_id'])<=512 and type(review['adapter_additional_read_cap'])is int and review['adapter_additional_read_cap']==500000 and type(review['adapter_additional_retained_bytes'])is int and review['adapter_additional_retained_bytes']==0,'Original central review context/budget')
    class ReviewBudget:
        tick=staticmethod(lambda:None)
        read=staticmethod(lambda n:None)
    policy.reviews(s,ReviewBudget())
    external_path=ordinary(args.producer_external);need(str(external_path)==review['external_output'],'Exact original external receipt')
    external_raw=capture(external_path,8192,pin(args.external_pin,8192));e=parse(external_raw)
    need(e.get('schema')=='neural078_full8_external_v1' and e.get('status')=='complete_unqualified' and same(e['source'],source) and same(e['selection'],args.selection_pin) and e['attempt']==str(root),'Complete original observer/source/selection join')
    for key in ('full8_source_scope',):need(e.get(key) is True,'Full original scope')
    for key in ('scientific_qualified','runtime_qualified','numerical_grading_performed','nested_cli_and_native_recovery_may_be_required','automatic_retry'):need(e.get(key) is False,'Original unqualified closed producer')
    need(e.get('error_type','missing') is None and finite(e['elapsed_before_publication'],2100),'Original observer completion interval')
    need(finite(e['origin_monotonic'],1e15) and e['whole_deadline']==e['origin_monotonic']+2100 and e['outer_deadline']==e['origin_monotonic']+2160,'Original observer deadlines')
    closed_process(e['child'],2080)
    need(check(e['child']['pid'],e['child']['pid']) is True,'Original worker freshly absent')
    o=observation
    need(type(o)is dict and set(o)=={'schema','authority_id','adapter_source','program_source','selection','review','external_receipt','argv','process','signals_sent','completion_observed_after_process_exit','candidate_access_closed','scope'},'Exact independent outer-observation fields')
    need(o['schema']=='neural078_trusted_outer_exit_v1' and type(o['authority_id'])is str and 0<len(o['authority_id'])<=512,'Separately trusted observer authority identifier')
    for key,value in [('adapter_source',adapter),('program_source',source),('selection',args.selection_pin),('review',args.review_pin),('external_receipt',args.external_pin),('scope',policy.SCOPE)]:need(same(o[key],value),'External observer exact '+key)
    need(o['signals_sent']==[] and o['completion_observed_after_process_exit'] is True and o['candidate_access_closed'] is True,'Natural outer closure and no remaining candidate access')
    proc=o['process'];need(set(proc)=={'pid','pgid','returncode','natural_exit','reaped','group_absent','elapsed_seconds'},'Exact external process observation')
    need(type(proc['returncode'])is int and proc['returncode']==0 and all(proc[k] is True for k in ('natural_exit','reaped','group_absent')) and finite(proc['elapsed_seconds'],2100),'Actual natural outer zero within original interval')
    need(check(proc['pid'],proc['pgid']) is True,'Outer process and group freshly absent')
    argv=o['argv'];need(type(argv)is list and len(argv)==19 and all(type(x)is str for x in argv),'Exact original adapter argv shape')
    need(Path(argv[0]).is_absolute() and argv[1:5]==['-I','-S','-B','-X'] and argv[5].startswith('pycache_prefix='),'Isolated original adapter startup')
    cache=ordinary(argv[5].split('=',1)[1]);need(not os.path.lexists(cache),'Original adapter cache still absent')
    expected=[str(old/'adapter.py'),'--source-bytes',str(adapter['bytes']),'--source-sha256',adapter['sha256'],'--program',s['program']['path'],'--output',str(root),'--review',str(ordinary(args.producer_review)),'--other-reserve-bytes',str(s['other_future_bytes'])]
    need(argv[6:]==expected,'Exact externally observed selected producer operands')
    need(type(e['argv'])is list and len(e['argv'])==17 and e['argv'][1:5]==['-I','-S','-B','-X'] and e['argv'][6]==str(old/'program/worker.py'),'Original observer launched original worker')
    need(e['argv'][7:] == ['--source-pin',e['argv'][8],'--selection',str(ordinary(args.producer_selection)),'--selection-pin',e['argv'][12],'--origin',repr(e['origin_monotonic']),'--worker-end',repr(e['whole_deadline']-20)] and same(parse(e['argv'][8].encode()),source) and same(parse(e['argv'][12].encode()),args.selection_pin),'Original worker argv/source/selection/clock join')
    need(e['argv'][5]=='pycache_prefix='+str(external_path)+'.UNUSED-PYCACHE' and not os.path.lexists(str(external_path)+'.UNUSED-PYCACHE'),'Original worker cache absent')
    binding=parse(sources['producer/program/BINDINGS.json']);rows={r['target']:r for r in binding['files']}
    need(len(rows)==76 and same(binding['scope'],policy.SCOPE),'Original complete collection')
    package=repo/binding['package'];need(package==ordinary(args.package),'Exact selected original package')
    for name in ('source_descriptor','export_descriptor'):
        desc=binding[name];doc=parse(capture(repo/desc['path'],100000,only(desc)))
        need(doc['task_ids']==['NEURAL-078'],'Collection task binding')
        if name=='export_descriptor':need(same(doc['files'],binding['files']) and same(doc['source_manifest'],binding['source_descriptor']),'Exact complete export collection')
        else:need(same([{k:r[k] for k in ('target','bytes','sha256','role','visibility')} for r in doc['files']],binding['files']),'Exact complete source collection')
    terminal=dict(schema='neural078_full8_worker_v1',status='complete_unqualified',source=source,scope=policy.SCOPE,complete=e['complete'])
    report_pin,complete_pin=observer.admit(c,root,terminal,source,binding,float('inf'),lambda n:None)
    need(same(report_pin,e['report']),'Same complete report in external receipt')
    complete=parse(capture(root/'COMPLETE.json',32768,complete_pin))
    need(same(complete['program'],only(s['program'])),'Frozen selected candidate program')
    capture(root/'commitment/program.py',131072,only(s['program']))
    commitment=parse(capture(root/'commitment/COMMITMENT.json',8192,complete['commitment']));need(same(commitment['method_review'],only(s['method_review'])),'Frozen method review commitment')
    report=capture(root/'candidate/report.json',65536,report_pin)
    native=[]
    for phase in ('candidate','admission'):
        record=parse(capture(root/phase/'NATIVE.json',262144,complete[phase+'_native']))
        need(record.get('error_type','missing') is None and record.get('numerical_grading_called') is False and finite(record['elapsed_seconds'],1050 if phase=='candidate' else 450),'Original complete ungraded native phase')
        native.extend(record['closures'])
    need(len(native)==6,'All six former native resources')
    return dict(selection=s,binding=binding,rows=rows,report=report,report_pin=report_pin,complete_pin=complete_pin,external=identity(external_raw),observation=o,native=native,program=only(s['program']))
