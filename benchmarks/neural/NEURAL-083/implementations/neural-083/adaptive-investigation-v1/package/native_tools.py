"""Actual owned native dispatch using the unchanged original Docker bridge."""
import json
import os
from pathlib import Path


def assembled(core,worker,mode,action,analysis=''):
    if type(analysis)is not str or len(analysis.encode())>65536:
        raise ValueError('bounded transient analysis source')
    prefix=('TOOL_MODE='+repr(mode)+'\nACTION='+repr(action)+'\nANALYSIS='+repr(analysis)+'\n').encode()
    body=core+b'\n'+prefix+worker
    if len(body)>1048576:raise ValueError('original candidate programme cap')
    return body


class NativeTools:
    def __init__(self,c,native,selection,source,trusted,core,worker,budget,deadline):
        self.c=c;self.native=native;self.selection=selection;self.source=source
        self.trusted=trusted;self.core=core;self.worker=worker
        self.budget=budget;self.deadline=deadline;self.records=[]

    def dispatch(self,kind,view,model,folder,ordinal,body,grant=None):
        c=self.c;b=self.budget;folder=c.path(folder)
        c.need(not os.path.lexists(folder),'fresh owned native tool attempt')
        folder.mkdir(mode=0o700);c.sync_dir(folder.parent,b.tick)
        program=folder/'program.py';program_pin=c.save(program,body,1048576,b.tick,b.write)
        c.readable(program,b.tick)
        attempt=folder/'native';attempt.mkdir(mode=0o700)
        b.native(kind,ordinal)
        start=dict(kind=kind,ordinal=ordinal,program=program_pin,attempt=str(attempt),
                   source=self.source,automatic_retry=False)
        phase_selection=self.selection;phase_deadline=self.deadline
        if grant is not None:
            c.need(kind=='infer' and type(grant['producer_seconds'])is int and
                0<grant['producer_seconds']<=self.selection['infer_seconds']
                and grant['query_started']<grant['query_deadline']<=self.deadline,
                'actual positive grant within original query and whole deadlines')
            phase_selection=dict(self.selection,infer_seconds=grant['producer_seconds'])
            phase_deadline=grant['query_deadline'];start['query_grant']=grant
        c.save(folder/'INTENT.json',c.encoded(start),65536,b.tick,b.write)
        try:
            value=self.native.phase(phase_selection,self.trusted,view,program,model,attempt,
                                    kind,ordinal,self.source,b,phase_deadline)
            c.need(value['status']=='captured' and value['all_native_resources_closed'] is True,
                   'actual complete owned native tool closure')
            receipt=c.capture(attempt/'NATIVE.json',262144,None,b.tick,b.read)
            row=dict(start,native=c.pin(receipt),output=value['output'],status='captured',
                     output_path=str(attempt/('model.bin' if kind=='fit' else 'predictions.json')))
            self.records.append(row)
            return row
        except BaseException as error:
            row=dict(start,status='failed',error_type=type(error).__name__,error=str(error)[:2048],
                     native_recovery_may_be_required=True)
            self.records.append(row)
            try:c.save(folder/'FAILURE.json',c.encoded(row),65536,b.tick,b.write)
            except BaseException as secondary:error.add_note('Tool failure publication failed: '+type(secondary).__name__)
            raise

    def construct(self,view,folder,ordinal,mode):
        return self.dispatch('fit',view,None,folder,ordinal,
            assembled(self.core,self.worker,mode,'construct_training_state'))

    def query(self,view,model,folder,ordinal,mode,action,code='',*,grant):
        row=self.dispatch('infer',view,model,folder,ordinal,
            assembled(self.core,self.worker,mode,action,code),grant=grant)
        raw=self.c.capture(row['output_path'],65536,row['output'],self.budget.tick,self.budget.read)
        value=self.c.parse(raw)
        self.c.need(type(value)is dict and set(value)=={'schema','identity','query','action','result'}
                    and value['schema']=='neural083_single_query_tool_result_v1'
                    and value['action']==action,'exact captured numerical result')
        return value,row
