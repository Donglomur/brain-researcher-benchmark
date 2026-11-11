"""Supervisor wall-clock policy shared by actual execution and small controls."""
import math
from .guard import real
from .custody import need

class JobDeadline:
    def __init__(self,origin,seconds,campaign_deadline):
        real(origin,0);real(seconds,0);real(campaign_deadline,0)
        need(seconds>0 and campaign_deadline>origin,'positive remaining selected job and campaign durations')
        self.origin=origin;self.seconds=seconds
        self.job_deadline=origin+seconds;self.campaign_deadline=campaign_deadline
        need(math.isfinite(self.job_deadline)and self.job_deadline>origin,'representable job deadline')
        self.deadline=min(self.job_deadline,campaign_deadline)
        self.limiter='job'if self.job_deadline<=campaign_deadline else'campaign'
        # Both declarations bound the whole job. Reserve cleanup/publication
        # inside the earlier limit; never reset the campaign clock.
        self.cleanup_reserve=min(8.0,(self.deadline-origin)/4)
        self.child_cutoff=self.deadline-self.cleanup_reserve
        need(origin<self.child_cutoff<self.deadline,'representable launch and cleanup interval')

    def record(self):
        return {'origin':self.origin,'seconds':self.seconds,'job_deadline':self.job_deadline,
                'campaign_deadline':self.campaign_deadline,'effective_deadline':self.deadline,
                'limiter':self.limiter,'cleanup_reserve':self.cleanup_reserve,'child_cutoff':self.child_cutoff}

    def require_running(self,now,record):
        real(now,0)
        if now>=self.child_cutoff:
            record['timed_out']=True;record['timeout_reason']=self.limiter+'_child_cutoff'
            record['timeout_observed_at']=now
            raise TimeoutError('selected '+self.limiter+' child cutoff; cleanup reserve retained')

    def poll_seconds(self,now,record):
        self.require_running(now,record)
        return min(.05,self.child_cutoff-now)

    def cleanup_seconds(self,now):
        real(now,0)
        return max(0.0,min(3.0,self.deadline-now))

    def require_complete(self,now,record):
        real(now,0)
        if now>=self.deadline:
            record['timed_out']=True;record['timeout_reason']=self.limiter+'_whole_job_deadline'
            record['timeout_observed_at']=now;record['complete_success']=False
            raise TimeoutError('selected whole-job deadline including cleanup/publication')
