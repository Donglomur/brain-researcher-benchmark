"""One dual-clock absolute attempt interval, including admission and continuation.

The first wrapper observation is the origin. Interpreter startup before that
observation, clock integrity and final OS process/stdio completion need the
independent outer runner; this source never certifies them.
"""
import time
from banc_runtime.codec import need
POLICY='banc_first_wrapper_dual_clock_absolute_attempt_v2'
class AttemptClock:
    def __init__(self,origin=None):
        self.entry_mono,self.entry_wall=origin or (time.monotonic_ns(),time.time_ns())
        self.record=None
    def bind(self,seconds):
        need(type(seconds) is int and seconds>0,'positive original attempt duration')
        self.record={'policy':POLICY,'origin_monotonic_ns':self.entry_mono,'origin_wall_ns':self.entry_wall,
          'deadline_monotonic_ns':self.entry_mono+seconds*10**9,'deadline_wall_ns':self.entry_wall+seconds*10**9,
          'duration_seconds':seconds,'outer_completion_qualified':False}
        self.check('after_policy_admission');return self
    def adopt(self,record):
        need(type(record) is dict and set(record)==set(self.record) and record['policy']==POLICY and
          record['duration_seconds']==self.record['duration_seconds'] and record['outer_completion_qualified'] is False,'exact original clock policy')
        need(record['deadline_monotonic_ns']-record['origin_monotonic_ns']==record['duration_seconds']*10**9 and
          record['deadline_wall_ns']-record['origin_wall_ns']==record['duration_seconds']*10**9,'unaltered original clock interval')
        need(record['origin_monotonic_ns']<=self.entry_mono and record['origin_wall_ns']<=self.entry_wall,'continuation cannot move origin forward or cross an observed clock reset')
        self.record=dict(record);self.check('after_original_clock_adoption')
    def check(self,where):
        need(self.record is not None,'attempt clock not admitted')
        m=time.monotonic_ns();w=time.time_ns();r=self.record
        need(r['origin_monotonic_ns']<=m<=r['deadline_monotonic_ns'] and r['origin_wall_ns']<=w<=r['deadline_wall_ns'],'original whole-attempt deadline/clock refusal: '+where)
        return {'where':where,'monotonic_ns':m,'wall_ns':w,'within_observed_interval':True}
    def elapsed(self):return (time.monotonic_ns()-self.record['origin_monotonic_ns'])/10**9

def guard(meter,where):
    meter.check_deadline(where)
    if hasattr(meter,'attempt_clock'):meter.attempt_clock.check(where)
