"""Once-only release of the actual H receiver's retained native handles.

This is terminal custody, not an issuer, worker observation, native admission or
source of successful backend evidence. It runs before the original process
receipt and aggregate cost publication. Every close remains with its original
fixed owner; a late clock/debit failure cannot suppress independent releases.
"""
from .common import need
from .development_handles import DevelopmentAttemptHandle


class DevelopmentHostTerminalCustody:
    def __init__(self,attempt):
        need(type(attempt) is DevelopmentAttemptHandle,'actual original H attempt')
        attempt.require_live_original()
        need(attempt.host_terminal_custody is None,'one original H terminal custody owner')
        self.attempt=attempt;self.channel=None;self.receiver=None;self.observer=None
        self.entered=False;self.closed=False;self.raw_first=None;self.secondaries=[]
        self.native_close_entered=False;self.native_close_result=None
        self.transport_close_entered=False;self.transport_close_result=None
        attempt.host_terminal_custody=self

    def retain(self,error,site,unknown=None):
        first=self.attempt.raw_first if self.attempt.raw_first is not None else error
        if self.raw_first is None:self.raw_first=first
        if error is not self.raw_first:self.secondaries.append(error)
        try:self.attempt.retain(error,'host_terminal_'+site,unknown)
        except BaseException as later:self.secondaries.append(later)

    def _close_admission(self,site):
        try:
            self.attempt.owner.terminal_host.charge('work_units',4096)
            self.attempt.pair.clock()
        except BaseException as error:
            # The finite release still runs. Its work may be unknown; do not
            # turn a refused/failed cost observation into measured zero.
            self.retain(error,site+'_cost','work_units')

    def close_v1(self):
        if self.entered:return self
        self.entered=True;a=self.attempt
        from .backend_linux_channel import HNativeChannelOwner
        from .backend_host_receiver import HChannelReceiver
        from .backend_host_view import HBackendView
        from .backend_host_native_evidence import HBackendNativeEvidence
        # Identity checks do not depend on parent success. A failure never
        # destroys ownership of the concrete returned original handles.
        try:
            a.require_live_original();a.owner.enter_terminal()
            channel=a.native_channel
            need(type(channel) is HNativeChannelOwner and channel.attempt is a and channel.owner is a.owner,
                 'same actual original H channel, never a supplied closer')
            self.channel=channel
        except BaseException as error:self.retain(error,'channel_identity')
        try:
            view=a.backend
            if view is not None:
                need(type(view) is HBackendView and view.attempt is a and view.owner is a.owner,
                     'same actual retained H backend view')
                receiver=view.receiver
                need(type(receiver) is HChannelReceiver and receiver.attempt is a and
                     receiver.backend_view is view and receiver.channel is self.channel and
                     self.channel.protocol is receiver,'same actual original receiver registration')
                self.receiver=receiver
                native=view.host_admission_owner
                if native is not None:
                    need(type(native) is HBackendNativeEvidence and native.view is view and
                         native.attempt is a and native.receiver is receiver and native.channel is self.channel,
                         'same retained original independent H observer')
                    self.observer=native
                need(view.host_closure_owner is None or view.host_closure_owner is native,
                     'original closure observer cannot be replaced')
        except BaseException as error:self.retain(error,'observer_identity')
        if self.observer is not None:
            self.native_close_entered=True;self._close_admission('observer_close')
            try:
                self.native_close_result=self.observer.close_all_once()
                need(self.native_close_result is True and self.observer.closed,
                     'known actual original independent H descriptor closure')
            except BaseException as error:self.retain(error,'observer_close')
        if self.channel is not None:
            self.transport_close_entered=True;self._close_admission('transport_close')
            try:
                if self.receiver is not None:
                    self.transport_close_result=self.receiver.close_transport_once()
                else:
                    # Partial setup can own endpoints/aliases before any
                    # protocol receiver exists. The original channel owns them.
                    self.transport_close_result=self.channel.close_all()
                need(self.transport_close_result is True,
                     'known actual channel/alias/worker-anchor/received-FD closure')
            except BaseException as error:self.retain(error,'transport_close')
        self.closed=(self.channel is not None and self.transport_close_result is True and
                     (self.observer is None or self.native_close_result is True))
        return self

    def require_completed(self):
        a=self.attempt
        need(a.host_terminal_custody is self and self.entered and self.closed and self.raw_first is None and
             a.raw_first is None and a.owner.parent.first_raw is None and not a.owner.parent.unknown,
             'same known original terminal custody; no failure or unknown promotion')
        need(a.native_channel is self.channel and self.channel.attempt is a and
             self.transport_close_entered and self.transport_close_result is True and
             self.channel.raw_first is None and not self.channel.unknown_read and not self.channel.unknown_write,
             'same actual fully closed original channel, not a replaced status')
        if self.observer is not None:
            need(self.observer is a.backend.host_admission_owner and self.observer.view is a.backend and
                 self.native_close_entered and self.native_close_result is True and self.observer.closed and
                 self.observer.raw_first is None,'same actual closed original native observer')
        return self
