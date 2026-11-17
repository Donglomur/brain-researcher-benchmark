"""Finite original-clock budgets for the campaign and each independent episode.

Reservations are conservative consumption. Failure, retry, missing observation
or matching artifact bytes never refunds a resource or starts a new clock.
Resource ledgers describe accounting, not physical enforcement on their own.
"""
import time
from .protocol import fields,need,integer,finite,Refusal,observation

COUNTERS=('read_bytes','output_bytes','scratch_bytes','cpu_milliseconds','gpu_milliseconds','input_tokens','output_tokens','processes','calls','development_requests')
LIMITS=COUNTERS+('wall_milliseconds','resident_bytes','gpu_resident_bytes','files','per_file_bytes','metadata_bytes','threads')
JOB_FIELDS=('read_bytes','output_bytes','scratch_bytes','cpu_milliseconds','gpu_milliseconds','input_tokens','output_tokens')


class Budget:
    def __init__(self,limits,*,origin=None,deadline=None,label):
        fields(limits,LIMITS,'finite whole or episode resource policy')
        for name,value in limits.items():integer(value,name)
        need(all(limits[k]>0 for k in ('wall_milliseconds','resident_bytes','files','per_file_bytes','metadata_bytes','threads')),'positive selected physical and transport limits')
        self.label=label;self.limits=dict(limits);self.origin=time.monotonic_ns() if origin is None else integer(origin,'original monotonic origin')
        self.deadline=self.origin+limits['wall_milliseconds']*1000000
        if deadline is not None:self.deadline=min(self.deadline,integer(deadline,'original parent deadline'))
        self.reserved={k:0 for k in COUNTERS};self.known={k:0 for k in COUNTERS};self.unknown=[];self.failures=[];self.jobs=[];self.files_reserved=0;self.peak_resident=None;self.peak_gpu_resident=None
    def guard(self,phase):
        if time.monotonic_ns()>self.deadline:
            record={'phase':phase,'kind':'original_deadline_exceeded','deadline_ns':self.deadline,'observed_ns':time.monotonic_ns()};self.failures.append(record);raise Refusal('original deadline exhausted',observation=record)
    def reserve(self,dimension,amount):
        self.guard('reserve:'+dimension);need(dimension in COUNTERS,'known resource dimension');integer(amount,'reserved amount')
        need(self.reserved[dimension]+amount<=self.limits[dimension],'cumulative selected budget:'+self.label+':'+dimension);self.reserved[dimension]+=amount
    def observe(self,dimension,amount):
        need(dimension in COUNTERS,'known observed dimension')
        if amount is None:self.unknown.append({'dimension':dimension,'reason':'original observer unavailable'});return
        integer(amount,'known actual observed amount');self.known[dimension]+=amount
        if self.known[dimension]>self.reserved[dimension]:self.failures.append({'kind':'actual_cost_exceeds_reserved','dimension':dimension,'observed':self.known[dimension],'reserved':self.reserved[dimension]})
    def reserve_file(self):
        self.guard('before_file_creation');need(self.files_reserved<self.limits['files'],'complete original output file reservation');self.files_reserved+=1
    def begin(self,job_id,requested,*,development):
        self.guard('before_original_job');fields(requested,JOB_FIELDS,'complete job reservation')
        need(type(development) is bool and all(j['id']!=job_id for j in self.jobs),'unique original job and typed development scope')
        charges={**requested,'processes':1,'calls':1,'development_requests':int(development)}
        for key,amount in charges.items():integer(amount,'job request');need(self.reserved[key]+amount<=self.limits[key],'complete original job reservation:'+key)
        for key,amount in charges.items():self.reserved[key]+=amount
        record={'id':job_id,'status':'reserved','reserved':charges,'observation':None};self.jobs.append(record);return record
    def end(self,record,actual):
        need(record in self.jobs and record['status']=='reserved','one original completion')
        required=JOB_FIELDS+('spawned','natural_exit','forced_exit','timed_out','reaped','descendants_closed','observer_complete','peak_resident_bytes','peak_gpu_resident_bytes','artifacts','failures')
        fields(actual,required,'original process observation');need(type(actual['spawned']) is bool and type(actual['timed_out']) is bool and type(actual['reaped']) is bool and type(actual['descendants_closed']) is bool and type(actual['observer_complete']) is bool,'typed process facts')
        for k in ('natural_exit','forced_exit'):need(actual[k] is None or type(actual[k]) is int,'actual exit or unavailable')
        complete=True;errors=list(actual['failures']);record['observation']=actual
        for key in COUNTERS:
            amount=int(actual['spawned']) if key=='processes' else 1 if key=='calls' else record['reserved'][key] if key=='development_requests' else actual[key]
            self.observe(key,amount)
            if amount is None:complete=False
            elif amount>record['reserved'][key]:complete=False;errors.append({'kind':'original_job_cost_exceeded','dimension':key,'known':amount,'reserved':record['reserved'][key]})
        for key,attribute,limit in (('peak_resident_bytes','peak_resident','resident_bytes'),('peak_gpu_resident_bytes','peak_gpu_resident','gpu_resident_bytes')):
            value=actual[key]
            if value is None:self.unknown.append({'job':record['id'],'dimension':key});complete=False
            else:
                integer(value,'known peak');old=getattr(self,attribute);setattr(self,attribute,value if old is None else max(old,value))
                if value>self.limits[limit]:complete=False;errors.append({'kind':'original_peak_exceeded','dimension':key,'known':value,'limit':self.limits[limit]})
        try:self.guard('after_original_completion_and_before_admission')
        except BaseException as exc:complete=False;errors.append(observation(exc))
        complete=complete and actual['spawned'] and actual['natural_exit']==0 and actual['forced_exit'] is None and not actual['timed_out'] and actual['reaped'] and actual['descendants_closed'] and actual['observer_complete'] and not errors
        record['status']='completed' if complete else 'failed_or_unqualified';record['failures']=errors
        if not complete:self.failures.append({'kind':'original_job_not_complete','id':record['id'],'failures':errors})
        return record
    def fail(self,phase,error):self.failures.append({'phase':phase,**observation(error)})
    def report(self):
        return {'label':self.label,'origin_ns':self.origin,'deadline_ns':self.deadline,'observed_at_ns':time.monotonic_ns(),'limits':self.limits,'reserved':dict(self.reserved),'known':dict(self.known),'unknown':list(self.unknown),'files_reserved':self.files_reserved,'peak_resident_bytes':self.peak_resident,'peak_gpu_resident_bytes':self.peak_gpu_resident,'jobs':self.jobs,'failures':self.failures,'logical_byte_counts_are_physical_RAM':False}


class CoupledBudget:
    """Two views of one operation, never summed as independent physical work."""
    def __init__(self,campaign,episode):
        self.campaign=campaign;self.episode=episode;self.limits={k:min(campaign.limits[k],episode.limits[k]) for k in LIMITS};self.jobs={}
    @property
    def deadline(self):return min(self.campaign.deadline,self.episode.deadline)
    def guard(self,phase):self.campaign.guard(phase);self.episode.guard(phase)
    def reserve(self,dimension,amount):
        self.guard('coupled_reserve')
        for b in (self.campaign,self.episode):need(b.reserved[dimension]+amount<=b.limits[dimension],'same physical operation within both scopes')
        self.campaign.reserve(dimension,amount);self.episode.reserve(dimension,amount)
    def observe(self,dimension,amount):self.campaign.observe(dimension,amount);self.episode.observe(dimension,amount)
    def reserve_file(self):
        self.guard('coupled_file')
        for b in (self.campaign,self.episode):need(b.files_reserved<b.limits['files'],'same file within both ceilings')
        self.campaign.reserve_file();self.episode.reserve_file()
    def begin(self,job_id,requested,*,development):
        self.guard('coupled_job')
        for b in (self.campaign,self.episode):
            for key,value in {**requested,'processes':1,'calls':1,'development_requests':int(development)}.items():need(b.reserved[key]+value<=b.limits[key],'same complete job within both budgets')
        local=self.episode.begin(job_id,requested,development=development);whole=self.campaign.begin(job_id,requested,development=development);self.jobs[job_id]=local;return whole
    def end(self,record,actual):
        local=self.episode.end(self.jobs[record['id']],actual);observed={**actual,'failures':list(actual['failures'])}
        if local['status']!='completed':observed['failures'].append({'kind':'episode_original_failure','record':record['id'],'failures':local['failures']})
        return self.campaign.end(record,observed)
    def fail(self,phase,error):self.campaign.fail(phase,error);self.episode.fail(phase,error)
    def report(self):return {'campaign':self.campaign.report(),'episode_view_of_same_work':self.episode.report(),'independent_costs_to_sum':False}
