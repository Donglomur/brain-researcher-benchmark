"""Actual original-H stream byte captures and existing cost-prefix snapshots.

Root-adopted output V2 adds exact nominal stream/workspace/cost targets.
No decoded record or successful file write creates process/pair authority.
"""
from .common import Store, need, pin
from .backend_capture import CanonicalPublisher, CapturedRecord, CaptureAttempt
from .backend_json import parse, canonical
from .development_handles import DevelopmentAttemptHandle
from .development_streams import DevelopmentStreams, NAMES
from .precommit_records import validate_type

_RAW_CAPTURE=object()

class CapturedStreamBytes:
    __slots__=('_token','evidence','side','raw','descriptor','source_streams','reader_entered')
    def __init__(self,token,evidence,side,raw,descriptor,source_streams):
        need(token is _RAW_CAPTURE,'actual completed original stream capture')
        self._token=token;self.evidence=evidence;self.side=side;self.raw=raw
        self.descriptor=dict(descriptor);self.source_streams=source_streams
        self.reader_entered=False
    @property
    def pin(self):return dict(self.descriptor)

class DevelopmentEvidenceCapture:
    """Fixed H caller, retained before any capture/allocation/clock attempt."""
    def __init__(self,attempt,publisher):
        need(type(attempt) is DevelopmentAttemptHandle,'actual original H attempt')
        attempt.require_live_original()
        need(attempt.finish_attempted and attempt.evidence_capture is None,
             'one post-kernel original evidence owner')
        need(type(publisher) is CanonicalPublisher and publisher.owner is attempt.owner and
             publisher.condition is None and type(publisher.outputs) is Store,
             'same original host publisher, not arm/decoded/replacement authority')
        self.attempt=attempt;self.owner=attempt.owner;self.publisher=publisher
        self.streams=attempt.streams;self.stream_attempts={}
        self.raw_first=attempt.raw_first;self.raw_secondaries=[]
        self.capture_entered=False;self.cost_attempted=False
        self.cost_source_value=None;self.cost_prefix_capture=None
        self.cost_reader_entered=False
        self.manifest_attempted=False;self.stream_manifest=None
        self.workspace_attempted=False;self.workspace_capture=None
        self.completion_cost_attempted=False;self.completion_cost=None
        self.workspace_identity=None;self.workspace_source=None;self.whole_arm_source=None
        attempt.evidence_capture=self

    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)
        self.attempt.retain(error,site)

    def _output_prefix(self):
        launch=self.attempt.arm.launch
        need(type(launch) is CapturedRecord and launch.owner is self.owner and
             launch.kind=='DevelopmentLaunchRequest','actual same-H captured launch request')
        self.publisher.meter.charge('work_units',64*len(launch.raw)+4096)
        self.publisher.meter.charge('retained_bytes',16*len(launch.raw)+4096)
        return launch.body['output_prefix']

    def capture_side_v1(self,side):
        need(side in NAMES and side not in self.stream_attempts,'one fixed original stream capture')
        record=CaptureAttempt(None,'HWorkerStreamBytes')
        self.stream_attempts[side]=record
        try:
            p=self.publisher;s=self.streams
            need(type(s) is DevelopmentStreams and s is self.attempt.streams and s.owner is self.owner,
                 'same actual original stdout/stderr owner')
            prefix=self._output_prefix()
            p.meter.charge('work_units',len(prefix)+128)
            p.meter.charge('retained_bytes',len(prefix)+128)
            name=prefix+'_'+side+'.txt';record.name=name
            key=(str(p.outputs.root),name)
            need(key not in p.parent.canonical_publications and
                 len(p.parent.canonical_publications)<p.maximum_members,
                 'original whole output slots include raw captures and failed attempts')
            p.parent.canonical_publications[key]=record
            raw=s.materialized[side]
            need(s.materialization_attempted[side] and type(raw) is bytes and
                 s.pending_raw[side] is None and side not in s.unknown_reads and
                 len(raw)==s.counts[side] and len(raw)<=s.limit,
                 'actual known ordered materialization within original stream cap')
            record.raw=raw
            # Store.write/read retain their original physical reservations.
            # Admit hash/comparison/descriptor and reread allocation before IO.
            p.meter.charge('work_units',2*len(raw)+4096)
            p.meter.charge('retained_bytes',2*len(raw)+4096)
            record.write_entered=True
            descriptor=p.outputs.write(name,raw);record.provisional=descriptor
            record.readback_entered=True
            reread=p.outputs.read(descriptor,max(1,s.limit),metadata=False)
            need(reread==raw and pin(reread)==pin(raw),
                 'actual complete same-H stream byte/hash readback')
            capture=CapturedStreamBytes(_RAW_CAPTURE,self,side,raw,descriptor,s)
            record.complete=capture
            return capture
        except BaseException as error:
            record.retain(error);self.retain(error,'DevelopmentEvidenceCapture.capture_side')
            raise

    def capture_cost_prefix_v1(self):
        need(not self.cost_attempted,'one actual aggregate CostPrefix snapshot')
        self.cost_attempted=True
        try:
            # This is the already specified aggregate original owner snapshot,
            # not measured per-arm cost or a self-inclusive publication receipt.
            prefix=self._output_prefix()
            # Closed seven-dimensional CostPrefix has a fixed conservative
            # metadata construction bound, reserved before taking the snapshot.
            self.publisher.meter.charge('work_units',8192)
            self.publisher.meter.charge('retained_bytes',8192)
            body=self.owner.cost_prefix();self.cost_source_value=body
            validate_type('CostPrefix',body)
            capture=self.publisher.capture(prefix+'_COST_PREFIX.json','CostPrefix',body)
            self.cost_prefix_capture=capture
            return capture
        except BaseException as error:
            self.retain(error,'DevelopmentEvidenceCapture.capture_cost_prefix')
            raise

    def capture_available_v1(self):
        need(not self.capture_entered,'one original independent evidence capture pass')
        self.capture_entered=True
        # Partial known output is useful failure evidence. A failed side does
        # not discard the other original side or a truthful later cost prefix.
        for side in NAMES:
            try:self.capture_side_v1(side)
            except BaseException:pass # raw owners already retain exact errors
        # Failure prefix is retained at its original occurrence. The successful
        # pre-Completion occurrence follows typed streams AND workspace closure.
        if self.raw_first is not None or self.attempt.raw_first is not None:
            try:self.capture_cost_prefix_v1()
            except BaseException:pass # no fabricated completed capture
        return self

    def read_stream_v1(self,capture):
        need(type(capture) is CapturedStreamBytes and capture._token is _RAW_CAPTURE and
             capture.evidence is self and capture.side in NAMES and
             self.stream_attempts[capture.side].complete is capture and
             capture.source_streams is self.streams and not capture.reader_entered,
             'one actual same-owner stream capture consumer, never a Pin-only handle')
        capture.reader_entered=True
        try:
            self.publisher.meter.charge('work_units',2*len(capture.raw)+4096)
            self.publisher.meter.charge('retained_bytes',2*len(capture.raw)+4096)
            raw=self.publisher.outputs.read(capture.pin,max(1,self.streams.limit))
            need(raw==capture.raw and pin(raw)==pin(capture.raw),'whole original captured bytes remain exact')
            return raw
        except BaseException as error:
            self.retain(error,'DevelopmentEvidenceCapture.read_stream');raise

    def read_cost_prefix_v1(self,capture):
        need(type(capture) is CapturedRecord and capture is self.cost_prefix_capture and
             capture.owner is self.owner and capture.kind=='CostPrefix' and not self.cost_reader_entered,
             'one actual same-owner CostPrefix capture consumer')
        self.cost_reader_entered=True
        try:
            p=self.publisher
            p.meter.charge('retained_bytes',len(capture.raw)*16+4096)
            raw=p.outputs.read(capture.pin,p.maximum_bytes,metadata=True)
            need(raw==capture.raw,'same actual complete captured CostPrefix bytes')
            body=parse(raw,p.maximum_bytes,maximum_depth=p.maximum_depth,
                       maximum_members=p.maximum_bytes,maximum_string_bytes=p.maximum_bytes)
            validate_type('CostPrefix',body)
            need(canonical(body,p.maximum_bytes,maximum_depth=p.maximum_depth)==raw,
                 'unchanged original CostPrefix canonical bytes')
            return body
        except BaseException as error:
            self.retain(error,'DevelopmentEvidenceCapture.read_cost_prefix');raise

    def partial_stream_pins_v1(self):
        # Exact existing DevelopmentFailure.partial_streams order/domain.
        return [self.stream_attempts[side].complete.pin for side in NAMES
                if side in self.stream_attempts and
                type(self.stream_attempts[side].complete) is CapturedStreamBytes]

    @property
    def complete_raw_streams(self):
        return (self.raw_first is None and self.attempt.raw_first is None and
                type(self.streams) is DevelopmentStreams and self.streams.complete and
                len(self.partial_stream_pins_v1())==2)

    def require_nominal_completion_targets(self):
        from .development_targets import require_targets
        return require_targets(self.attempt)

    def capture_stream_manifest_v2(self):
        need(not self.manifest_attempted,'one actual H stream manifest attempt')
        self.manifest_attempted=True
        try:
            need(self.complete_raw_streams and self.capture_entered,
                 'both actual original timed EOF/close/raw captures precede manifest')
            a=self.attempt;p=self.publisher
            need(type(a.prefix_capture) is CapturedRecord and a.prefix_capture.owner is self.owner,
                 'actual earlier original attempt capture')
            p.meter.charge('work_units',8192);p.meter.charge('retained_bytes',8192)
            sides={}
            for side in NAMES:
                original=self.stream_attempts[side].complete
                need(type(original) is CapturedStreamBytes and original.evidence is self,
                     'actual same-H raw capture identity')
                sides[side]={'schema':'ci_h_stream_side_v1','name':side,'raw_bytes':original.pin,
                    'bytes':len(original.raw),'sha256':original.pin['sha256'],'eof_observed':True,
                    'close_state':'closed','closed_ns':self.streams.closed_ns[side],'unknown_bytes':0}
            observed=a.pair.clock()
            body={'schema':'ci_h_stream_capture_v1','condition':a.condition,
                  'original_attempt':a.prefix_capture.pin,'owner_binding':self.owner.parent.binding_pin,
                  'observed_ns':observed,**sides}
            capture=p.capture(self._output_prefix()+'_STREAMS.json','HStreamCaptureV1',body)
            self.stream_manifest=capture;a.complete_stream_capture=capture
            self.owner.parent.known_records.append(capture.pin)
            return capture
        except BaseException as error:self.retain(error,'capture_stream_manifest_v2');raise

    def capture_workspace_closure_v2(self):
        need(not self.workspace_attempted,'one original workspace-closure attempt')
        self.workspace_attempted=True
        try:
            from .observer import OriginalProcessObservation
            from .programme_workspace import retained_workspace_identity
            a=self.attempt
            need(type(a.process_observation) is OriginalProcessObservation and a.process_observation.success and
                 a.finish_attempted and a.raw_first is None and self.stream_manifest is a.complete_stream_capture,
                 'actual stopped natural-zero worker and completed original stream manifest')
            subtree=a.whole_arm_capture
            need(type(subtree) is CapturedRecord and subtree.owner is self.owner and
                 subtree.kind=='SubtreeObservation','actual retained whole-arm observation producer')
            body=subtree.body;ack=a.launch_ack.body
            need(body['producer']=='host' and body['scope']=='whole_arm' and
                 body['root']==ack['worker_identity'] and body['condition']==a.condition and
                 body['attempt']==a.prefix_capture.pin and body['enumeration_complete'] and
                 body['unresolved_count']==0 and body['excluded_live_worker'] is None and
                 all(row['state']=='exited_reaped' for row in body['members']),
                 'actual qualified complete whole-arm descendant/write closure')
            self.whole_arm_source=subtree;self.workspace_source=a.arm.workspace
            self.workspace_identity=retained_workspace_identity(a)
            self.publisher.meter.charge('work_units',16384)
            self.publisher.meter.charge('retained_bytes',16384)
            body={'schema':'ci_development_workspace_closure_v1','condition':a.condition,
                  'original_attempt':a.prefix_capture.pin,'owner_binding':self.owner.parent.binding_pin,
                  'workspace':a.arm.workspace_capture.pin,'subtree':subtree.pin,
                  'retained_workspace_identity':self.workspace_identity,
                  'workspace_state':'retained_for_programme_capture','write_authority_closed':True,
                  'observed_ns':a.pair.clock(),'cost_prefix':self.owner.cost_prefix()}
            capture=self.publisher.capture(self._output_prefix()+'_WORKSPACE_CLOSURE.json',
                                           'DevelopmentWorkspaceClosure',body)
            self.workspace_capture=capture;a.descendant_workspace_closure=capture
            self.owner.parent.known_records.append(capture.pin)
            return capture
        except BaseException as error:self.retain(error,'capture_workspace_closure_v2');raise

    def capture_completion_cost_v2(self):
        need(not self.completion_cost_attempted,'one actual pre-Completion aggregate cost occurrence')
        self.completion_cost_attempted=True
        try:
            need(self.raw_first is None and self.attempt.raw_first is None and
                 type(self.stream_manifest) is CapturedRecord and type(self.workspace_capture) is CapturedRecord,
                 'earlier successful original stream and workspace publications')
            self.publisher.meter.charge('work_units',8192)
            self.publisher.meter.charge('retained_bytes',8192)
            body=self.owner.cost_prefix()
            validate_type('CostPrefix',body)
            need(not body['unknown_dimensions'] and all(v is not None for v in body['observed'].values()),
                 'unknown original costs remain truthful failure evidence, never complete-success zeroes')
            capture=self.publisher.capture(self._output_prefix()+'_COMPLETION_COST.json','CostPrefix',body)
            self.completion_cost=capture;self.attempt.cost_observation=capture
            self.owner.parent.known_records.append(capture.pin)
            return capture
        except BaseException as error:self.retain(error,'capture_completion_cost_v2');raise
