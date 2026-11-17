"""Original child observation and bounded durable evidence; never retry a child."""
import os
from pathlib import Path
import common as c
from host_observation import Bridge,admit
from transport.process import ProcessObserver

def parent_argv(ctx,operation):
    c.need(operation in('outer','controller'),'original parent operation')
    review=ctx['review'];envelope=ctx['envelope'];source=ctx['parent_source'];config=review['program']
    return [review['launch']['python'],'-I','-B',ctx['parent']['entry']['path'],'--operation',operation,'--config',config['path'],'--config-bytes',str(config['bytes']),'--config-sha256',config['sha256'],'--source',source['path'],'--source-bytes',str(source['bytes']),'--source-sha256',source['sha256'],'--origin',str(review['origin']),'--deadline',str(review['normal_endpoint']),'--bootstrap-read-cap',str(envelope['bootstrap_read_cap'])]

def launch(ctx,argv,name):
    budget=ctx['budget'];budget.check_clock();seconds=budget.end-budget.clock();c.need(seconds>0,'remaining original normal interval before launch')
    env=dict(ctx['review']['launch']['host_environment']);value=None
    try:
        value=os.environ.get(name);c.need(type(value)is str and value and name not in env,'one selected credential exists');env[name]=value
        return ProcessObserver().run(argv,cwd='/',env=env,budget=Bridge(budget),seconds=seconds,cleanup_seconds=120,stream_cap=262144)
    finally:
        env.pop(name,None);value=None

def retain_original(root,original,budget):
    c.exact(original,('stdout','stderr','observation'))
    c.need(all(type(original[k])is bytes and len(original[k])<=262144 for k in('stdout','stderr')),'bounded original byte streams')
    # Persist the exact observation first; later stream-publication errors retain
    # this record and the still-live original bundle in the enclosing handler.
    observation=c.publish_json(root/'ORIGINAL_OBSERVATION.json',original['observation'],budget)
    streams={name:c.publish(root/(name.upper()+'.txt'),original[name],budget)for name in('stdout','stderr')}
    return {'observation':observation,'streams':streams}

class FailureBudget:
    """No new resource grant; only the separately selected120-second closeout."""
    def __init__(self,normal):self.normal=normal;self.end=normal.end+120
    def check_clock(self):c.need(self.normal.clock()<self.end,'fixed failure evidence deadline')
    def charge(self,key,amount):
        self.check_clock();c.integer(amount)
        with self.normal.lock:
            c.need(key in self.normal.used and self.normal.used[key]+amount<=self.normal.limits[key],'retained failure evidence fits original allocation')
            self.normal.used[key]+=amount

def retain_failure(root,error,ctx,intent,original):
    # Only the original available evidence is recorded. Failed publication is
    # itself uncertain; it cannot overwrite evidence or cause another launch.
    row={'schema':'neural081_central_failure_v1','intent':intent,'error_type':type(error).__name__,'automatic_retry':False,'partial_or_unknown':True,'original_child_evidence':getattr(error,'evidence',None),'central_original_endpoint':ctx['budget'].end,'failure_evidence_endpoint':ctx['budget'].end+120}
    if original is not None:
        row['original_observation']=original['observation']
        row['retained_original_streams_hex']={k:original[k].hex()for k in('stdout','stderr')}
        row['stream_completeness_not_inferred_from_retained_bytes']=True
    try:return c.publish_json(root/'FAILURE.json',row,FailureBudget(ctx['budget']))
    except BaseException:return None

def natural(original,argv,ctx,retained):
    admit(original['observation'],argv,ctx['budget'].origin,ctx['budget'].end,retained['streams']['stdout'],retained['streams']['stderr'])
    for name in('stdout','stderr'):c.need(c.pin(original[name])=={k:retained['streams'][name][k]for k in('bytes','sha256')},'original exact retained stream')
    ctx['budget'].check_clock()

def final_result(root,report,budget):
    # This reservation includes bytes produced after the report's own snapshot.
    budget.charge('write_bytes',65536);budget.charge('stream_bytes',4096)
    report['post_snapshot_result_write_reservation']=65536;report['budget']=budget.snapshot()
    raw=c.encoded(report);c.need(len(raw)<=65536,'bounded central report')
    class Reserved:
        def __init__(self):self.consumed=False
        def check_clock(self):budget.check_clock()
        def charge(self,key,amount):
            c.need(not self.consumed and key=='write_bytes'and type(amount)is int and amount<=65536,'one already charged result publication');self.consumed=True;budget.check_clock()
    return c.publish(root/'RESULT.json',raw,Reserved())

def external_completion(record,argv,origin,endpoint,stdout,stderr,result):
    """Concrete predicate for the separate actual central caller's original log.

    The wrapper never calls this on a self-issued substitute. The actual caller
    must retain its original record/streams and authenticate RESULT independently.
    """
    admit(record,argv,origin,endpoint,stdout,stderr)
    c.need(type(result)is dict and result.get('schema')=='neural081_provisional_central_result_v1'and result.get('status')=='requires_independent_original_central_natural_exit','source-owned provisional central result')
    c.need(c.typed_equal(result.get('central_argv'),argv)and result.get('original_origin')==origin and result.get('normal_endpoint')==endpoint,'exact same central invocation/original clock')
    ended=c.finite(result.get('completed_monotonic'));c.need(origin<=ended<=record['ended_monotonic']<=endpoint,'actual external completion after durable result within original bound')
    return {'status':'original_central_natural_exit_admitted','scientific_qualification_from_this_predicate':False}
