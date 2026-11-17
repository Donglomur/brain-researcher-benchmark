"""Complete original CI panel refusal rows from actual preparation custody.

This is a source-owned in-memory full report contribution. Its evidence Pin is
only the actual optional PreparationReport capture. Missing durable evidence
does not become a successful report or a reduced scientific programme.
"""
from .common import need,bounded_size
from .development_preparation import PreparationHandle,PreparationReporter
from .backend_capture import CapturedRecord
from .precommit_records import CONDITIONS

class FourFinalReport:
    def __init__(self,handle):
        need(type(handle) is PreparationHandle and handle.owner.parent.preparation is handle,
             'actual original preparation handle for report ownership')
        self.handle=handle;self.owner=handle.owner;self.rows=[];self.attempted=False
        self.raw_first=None;self.raw_secondaries=[];self.scope_digest=None
        self.preparation_report=None;self.complete=False
    def retain(self,error):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)
        self.handle.retain(error,'FourFinalReport.preparation_failure')
    def add_preparation_failure_v2(self,handle):
        need(handle is self.handle and handle.raw_first is not None and handle.promotion is None,
             'same failed actual handle; no successful-null-evidence normalization')
        if self.attempted:return self
        self.attempted=True
        try:
            construction=handle.construction;scope=construction.scope
            need(type(scope) is construction.public.Scope and construction.template.scope is scope,
                 'same original complete admitted scientific Scope and template')
            scope.whole_plan(construction.template.body['census_body'])
            need(len(scope.panel_ids)==76 and len(set(scope.panel_ids))==76,
                 'all original CI panels remain, regardless of preparation failure')
            self.owner.enter_terminal()
            self.owner.terminal_host.charge('retained_bytes',76*2*2048)
            self.owner.terminal_host.charge('work_units',76*2*2048)
            self.scope_digest=scope.digest
            PreparationReporter.capture_failure_v2(handle)
            if handle.report_capture is not None:
                need(type(handle.report_capture) is CapturedRecord and
                     handle.report_capture.owner is self.owner and handle.report_capture.kind=='PreparationReport',
                     'actual optional same-owner completed report capture')
                self.preparation_report=handle.report_capture
            evidence=None if self.preparation_report is None else self.preparation_report.pin
            for panel_id in scope.panel_ids:
                for condition in CONDITIONS:
                    self.rows.append({'programme':'PAPER-FIND-050','panel_id':panel_id,'condition':condition,
                        'scope_digest':scope.digest,'status':'required_unscorable',
                        'reason':'original_preparation_failure','preparation_report':evidence,
                        'programme_seal':None,'scientifically_qualified':False})
            need(len(self.rows)==152,'complete original panel-by-condition refusal contribution')
            self.complete=True
        except BaseException as error:self.retain(error)
        return self

