"""Separate future private grading entry; requires explicit scientific authority.

The complete two-role producer must already have natural external closure and
independent root admission. No candidate code runs from this grader.
"""
import time
ORIGIN=globals().get('_CAPTURED_LAUNCH_ORIGIN')
import argparse,hashlib,json,os,signal,sys,types
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
BOOT_PIN={'bytes': 1734, 'sha256': 'bf4545385dd30a3d01884ad184e6df80d4cab431d8c0f996265544f70a2077f4'}

def boot(source,deadline):
    p=ROOT/'transport/bootstrap.py'
    if any(q.is_symlink() for q in (p,*p.parents)):raise ValueError('ordinary bootstrap')
    with p.open('rb') as f:raw=f.read(BOOT_PIN['bytes']+1)
    if len(raw)>16384:raise ValueError('bounded bootstrap')
    # Root-captured grader carries this exact bootstrap hash at final freeze.
    if {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}!=BOOT_PIN:raise ValueError('bootstrap identity')
    m=types.ModuleType('neural089_grade_boot');m.__file__=str(p);exec(compile(raw,str(p),'exec'),m.__dict__)
    c,manifest,bodies,cost=m.load(ROOT,source,deadline)
    return c,manifest,bodies,cost+len(raw)+1

def execute(s,source,bodies,c,packet,policy,outputs,read):
    fields={'schema','task_id','scientific_grading_selected','source','producer_selection','producer_external','producer_outer_admitted','original_preparation','targets','seconds','read_bytes','write_bytes','root_memory_and_capacity_qualified'}
    c.need(type(s)is dict and set(s)==fields and s['schema']=='neural089-grading-selection-v1' and s['task_id']=='NEURAL-089' and s['scientific_grading_selected']is True and s['source']==source and s['producer_outer_admitted']is True and s['root_memory_and_capacity_qualified']is True,'separate source-bound scientific grading authority')
    for name in ('producer_selection','producer_external','original_preparation','targets'):
        d=s[name];c.need(type(d)is dict and set(d)=={'path','bytes','sha256'},'exact grading operand');c.only_pin(d);c.path(d['path'])
    producer=policy.selection(c.parse(read(s['producer_selection']['path'],32768,c.only_pin(s['producer_selection']))),source)
    outer=c.parse(read(s['producer_external']['path'],16384,c.only_pin(s['producer_external'])))
    c.need(outer.get('schema')=='neural089_complete_external_v1' and outer.get('status')=='complete_unqualified' and outer.get('source')==source and outer.get('selection')==c.only_pin(s['producer_selection']) and outer.get('attempt')==producer['output'] and outer.get('executing_outer_source')==c.pin(bodies['transport/run.py']) and outer.get('executing_worker_source')==c.pin(bodies['transport/worker.py']),'exact admitted source producer')
    child=outer['child'];c.need(child.get('natural_exit')is True and type(child.get('exit_code'))is int and child['exit_code']==0 and child.get('process_reaped')is True and child.get('process_group_absent')is True and child.get('streams_closed')is True and child.get('error_type')is None,'natural closed producer')
    c.need(outer.get('runtime_qualified')is False and outer.get('scientific_qualified')is False and outer.get('grading_performed')is False,'no inherited qualification')
    result=outer['worker_result'];c.need(c.pin(c.encoded(result))==outer['worker_result_pin'],'exact captured worker result')
    joined=outputs.admit_collection(producer,source,bodies,result,c.path(producer['output']),read)
    c.need(c.encoded(joined)==c.encoded(outer['joined_collection']),'independent full collection equals original outer admission')
    public=c.parse(read(producer['public_manifest']['path'],packet.JSON_CAP,c.only_pin(producer['public_manifest'])))
    projection=c.parse(read(c.path(producer['public_root'])/'PROJECTION.json',packet.JSON_CAP,public['projection_receipt']))
    c.need(projection['original_metadata']['original_preparation']==c.only_pin(s['original_preparation']),'same original preparation metadata')
    original=c.parse(read(s['original_preparation']['path'],256000000,c.only_pin(s['original_preparation'])))
    c.need(original['targets']==c.only_pin(s['targets']),'target identity originates in authenticated original preparation')
    answers={p:c.parse(read(c.path(producer['output'])/(p+'.json'),packet.OUTPUT_CAP,joined['panels'][p])) for p in packet.PANELS}
    # All sources, native phases, sealed models and both full answers precede this callback.
    return outputs.compare(public,answers['candidate'],answers['independent_reference'],lambda:c.parse(read(s['targets']['path'],256000000,c.only_pin(s['targets']))))

def main(argv=None):
    if ORIGIN is None or globals().get('_CAPTURED_OUTER_PIN')is None:raise ValueError('root captured grader and original clock required')
    if not(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):raise ValueError('isolated no-site grader')
    p=argparse.ArgumentParser()
    for name in ('source-pin','selection','selection-pin','external-output'):p.add_argument('--'+name,required=True)
    a=p.parse_args(argv);startup=ORIGIN+120;source=json.loads(a.source_pin)
    c,manifest,bodies,cost=boot(source,startup)
    c.need(c.pin(bodies['program/grade.py'])==globals()['_CAPTURED_OUTER_PIN'],'executing captured grader source')
    raw=c.capture(a.selection,32768,json.loads(a.selection_pin),lambda:c.before(startup));s=c.parse(raw)
    for k in ('seconds','read_bytes','write_bytes'):c.need(type(s.get(k))is int and s[k]>0,'explicit full grading allowance')
    end=ORIGIN+s['seconds'];reads=cost+len(raw)+1
    def tick():c.before(end)
    def charge(n):
        nonlocal reads
        tick();c.need(reads+n<=s['read_bytes'],'complete grading read allowance');reads+=n
    def read(path,cap,expected=None):return c.capture(path,cap,expected,tick,charge)
    def expired(*_):raise TimeoutError('original grading clock')
    previous={n:signal.signal(n,expired) for n in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT)}
    signal.setitimer(signal.ITIMER_REAL,max(.001,end-time.monotonic()))
    try:
        science=c.module(bodies,'program/science.py',ROOT,c=c,source_bodies=bodies)
        packet=c.module(bodies,'program/packet.py',ROOT,c=c,science=science)
        policy=c.module(bodies,'program/policy.py',ROOT,c=c,packet=packet)
        outputs=c.module(bodies,'program/outputs.py',ROOT,c=c,packet=packet,policy=policy,science=science)
        value=execute(s,source,bodies,c,packet,policy,outputs,read);tick()
        value.update(source=source,selection=json.loads(a.selection_pin),read_reservations=reads,original_origin=ORIGIN,elapsed_before_publication=time.monotonic()-ORIGIN,outer_durability_admission_required=True)
        body=c.encoded(value);c.need(len(body)<=s['write_bytes'],'full grading output allowance')
        c.save(a.external_output,body,s['write_bytes'],tick);tick();return 0
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        for n,h in previous.items():signal.signal(n,h)

if __name__=='__main__':raise SystemExit(main())
