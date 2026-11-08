"""Keep the first failure; independently attempt each owned cleanup exactly once."""

class Failures:
    def __init__(self):
        self.primary=None;self.traceback=None;self.records=[];self.truncated=False
    def capture(self,error,stage):
        if self.primary is None:self.primary=error;self.traceback=error.__traceback__
        if len(self.records)<32:self.records.append({'stage':stage,'error_type':type(error).__name__,'completion_unknown':True})
        else:self.truncated=True
    def attempt(self,stage,operation):
        try:return operation()
        except BaseException as error:self.capture(error,stage)
    def raise_if_failed(self,known=None):
        if self.primary is None:return
        evidence={'schema':'paper020_ordered_failures_v1','primary_type':type(self.primary).__name__,
                  'failures':self.records,'truncated':self.truncated,'known':known or {},'success':False}
        try:note=u.canonical(evidence).decode()
        except BaseException as error:
            self.capture(error,'failure_evidence_encoding');note='Failure evidence encoding failed; original failure retained.'
        # Call the builtin descriptor, not an arbitrary exception override.
        try:BaseException.add_note(self.primary,note[:16384])
        except BaseException:pass
        raise BaseException.with_traceback(self.primary,self.traceback)
