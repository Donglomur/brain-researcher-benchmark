"""Extend accepted logical accounting without changing its numerical/runtime body."""
from banc_runtime.resources import Meter as AcceptedMeter
class Meter(AcceptedMeter):
    def report(self):
        report=super().report();clock=report.pop('attempt_clock',None)
        if clock is not None:report['original_attempt_clock']=dict(clock.record)
        report['child_CPU_reservations_are_not_aggregate_host_CPU_measurements']=True
        return report
