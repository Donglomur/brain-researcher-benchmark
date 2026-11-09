"""Exact independent original process admission; no numeric PID mutation."""
import common as c

class Bridge:
    def __init__(self,budget,cleanup_seconds=120):
        c.need(cleanup_seconds==120,'separate source-selected failure interval')
        self.budget=budget;self.deadline_monotonic=budget.end+cleanup_seconds
    def check_clock(self):self.budget.check_clock()
    def charge(self,key,value):
        # The captured observer names its bounded procfs reads source_read.
        # They debit the same selected whole-host read envelope, exactly once.
        self.budget.charge('read_bytes' if key=='source_read' else key,value)

def admit(record,argv,origin,endpoint,stdout,stderr):
    c.need(type(record)is dict and record.get('schema')=='neural053_host_process_observation_v3','captured original observer schema')
    c.need(c.typed_equal(record.get('argv'),argv),'literal actual observed launch')
    for name in ('natural_exit_code','observed_leader_exit_code'):c.need(type(record.get(name))is int and record[name]==0,'natural exact integer-zero exit')
    for name in ('process_reaped','process_group_absent','streams_closed','observer_selector_closed'):c.need(record.get(name)is True,'complete original '+name)
    c.need(c.typed_equal(record.get('stream_eof_observed'),{'stdout':True,'stderr':True}),'both original EOFs')
    c.need(record.get('child_mutation_attempted')is False and record.get('quarantine_token')is None and record.get('separate_authorized_inspection_required')is False and record.get('failure')is None,'no cleanup/unknown state admitted')
    c.need(record.get('group_observation',{}).get('state')=='absent','actual read-only group observation')
    start=c.finite(record.get('started_monotonic'));end=c.finite(record.get('ended_monotonic'));normal=c.finite(record.get('normal_deadline_monotonic'))
    c.need(origin<=start<=end<=normal<=endpoint and record.get('original_deadline_monotonic')==endpoint+120,'same original whole clock, distinct failure interval')
    c.need(record.get('per_stream_cap')==262144 and type(record.get('per_stream_cap'))is int,'exact raw stream cap')
    for name,desc in(('stdout',stdout),('stderr',stderr)):
        c.descriptor(desc,True);row=record['streams'][name]
        c.need(type(row['bytes'])is int and row['bytes']==row['retained_bytes']==desc['bytes']<=262144 and row['sha256']==row['retained_sha256']==desc['sha256'],'complete original raw '+name+' identity')
    return record
