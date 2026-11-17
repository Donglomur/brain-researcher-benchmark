"""Owned trusted preparation children; uses the reviewed strict CLI lifecycle.

These independent process groups are journaled. Outer forced termination cannot
prove their absence: no automatic retry or failure-custody qualification follows.
"""
import os,time
from pathlib import Path
from common import need,save,canonical,capture,parse,descriptor,observed_capture

class Host:
    def __init__(self,engine,binary,script,publish):
        # Reuse the exact streaming/kill/reap/group-absence implementation only.
        self.impl=object.__new__(engine.Docker)
        self.impl.max_calls=1;self.impl.reply_budget=262144;self.impl.reserved=0;self.impl.publish=publish
        self.impl.prefix=[binary,'-I','-S','-B',str(script)];self.impl.records=[];self.impl.reaped=True
        self.impl.env={k:v for k,v in os.environ.items() if k not in ('DOCKER_HOST','DOCKER_CONTEXT','PYTHONPATH','PYTHONHOME')}
        self.engine=engine
    def call(self,args,end,phase):
        raw=self.impl(args,end,phase,262144)
        self.engine.validate_cli_records(self.impl.records)
        self.impl.publish('HOST-CLOSED',self.impl.records[0])
        need(self.impl.reaped is True and raw.strip()==b'{"status":"complete"}','owned trusted child natural closure')
        return self.impl.records


def run(engine,binary,here,request,path,report,budget,journal,seconds):
    need(time.monotonic()+seconds<=budget.end,'whole trusted phase inside original WORK')
    end=min(budget.end,time.monotonic()+seconds);request=dict(request,original_end=end)
    rp=save(path,canonical(request),budget);budget.reading(262144)
    budget.metadata(1048576) # bounded child report before process creation
    host=Host(engine,binary,here/'host_worker.py',journal.append)
    records=host.call(['--request',str(path),'--request-bytes',str(rp['bytes']),'--request-sha256',rp['sha256'],'--report',str(report)],end,'host_'+request['action'])
    raw,pin=observed_capture(report,1048576,budget)
    capture(report,pin,1048576,budget,retain=False)
    v=parse(raw);need(v['schema']=='language_trusted_host_result_v1' and v['request']==rp and v['source_manifest']==request['source_manifest'] and v['original_end']==end and v['action']==request['action'],'exact original host source/request/clock join')
    need(v['scientific_fits_called']is False and v['qualified_by_this_process']is False,'preparation only without qualification')
    need(time.monotonic()<end,'closed host report before original cutoff')
    return v,{'report':{'path':str(report),**pin},'request':rp,'command_metadata':records,'natural_closed':True,'original_end':end,'forced_stop_custody':'unknown'}
