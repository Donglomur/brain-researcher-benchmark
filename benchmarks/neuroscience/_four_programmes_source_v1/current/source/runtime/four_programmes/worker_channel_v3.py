"""Worker-side application custody over the separately owned physical endpoint.

No sockets, descriptor adoption, process creation or general callback lives here.
The exact endpoint class must be supplied by the native owner's frozen source.
"""
from .common import need, DependencyUnavailable
from .worker_context_records_v3 import body, decode, encode, equal, pinned
from .worker_context_schema_v3 import RECORDS

_PENDING = object()
_CHANNEL = object()
_CAPTURE = object()
_REPLIES = {
    'BootstrapHelloV3': ('WorkerBootstrapGrantV1',),
    'BootstrapObjectRequestV1': ('BootstrapObjectChunkV1',),
    'CheckRequestV1': ('CheckAckV1',),
    'EffectIntentV1': ('EffectGrantDeliveryV2',),
    'EffectObservationV1': ('EffectObservationAckV1',),
    'PublicationIntentV1': ('PublicationStartAckV1',),
    'PublicationChunkV1': ('PublicationChunkAckV1',),
    'PublicationCommitV1': ('PublicationAckV1',),
    'PollBackendAdmissionV1': ('PendingBackendAdmissionV1','CompletedBackendAdmissionV1'),
    'AdmissionObjectRequestV1': ('AdmissionObjectChunkV1',),
    'FinishWorkerV1': ('FinishWorkerAckV1',),
}

class ChannelPending:
    __slots__ = ('channel', 'sequence', 'request_kind', 'source_site', 'original_context',
                 'original_request_body', 'raw_sent_prefix', 'raw_received_prefix',
                 'known_sent_bytes', 'known_received_bytes', 'reserved_bounds',
                 'expected_reply', 'completed_reply', 'raw_first', 'ordered_secondaries',
                 'uncertain', 'consumed', 'reply_authenticated', 'captures', 'encoded_request',
                 'send_entered','receive_entered')
    def __init__(self, token, channel, kind, site, payload, expected):
        need(token is _PENDING, 'source-created actual original pending')
        self.channel=channel; self.sequence=channel.sequence; self.request_kind=kind
        self.source_site=site; self.original_context=channel.context_identity
        self.original_request_body=payload; self.expected_reply=expected
        self.raw_sent_prefix=None; self.raw_received_prefix=None
        self.known_sent_bytes=0; self.known_received_bytes=0
        self.reserved_bounds=channel.packet_limit
        self.completed_reply=None; self.raw_first=None; self.ordered_secondaries=[]
        self.uncertain=False; self.consumed=False; self.reply_authenticated=False; self.captures=[]
        self.encoded_request=None;self.send_entered=False;self.receive_entered=False
    def retain(self, error):
        if self.raw_first is None: self.raw_first=error
        elif error is not self.raw_first: self.ordered_secondaries.append(error)

class WorkerCapturedRecord:
    __slots__ = ('context', 'kind', '_raw', '_pin', 'origin', 'original_pending',
                 'selected_table_or_reply_or_publication', 'source_policy')
    def __init__(self, token, context, kind, raw, descriptor, origin, pending, selection):
        need(token is _CAPTURE, 'completed original channel pending is the sole capture issuer')
        self.context=context; self.kind=kind; self._raw=raw; self._pin=dict(descriptor)
        self.origin=origin; self.original_pending=pending
        self.selected_table_or_reply_or_publication=selection; self.source_policy=context.source_policy
    @property
    def raw(self): return self._raw
    @property
    def pin(self): return dict(self._pin)
    @property
    def body(self): return decode(self.kind, self._raw, len(self._raw))

def require_capture(capture, context, kind=None):
    need(type(capture) is WorkerCapturedRecord and capture.context is context,
         'exact source-owned worker capture, never an H capture clone')
    pending=capture.original_pending
    need(type(pending) is ChannelPending and pending.channel is context.channel and
         pending.reply_authenticated and pending.completed_reply is not None and
         any(item is pending for item in context.channel.attempts) and
         any(item is capture for item in pending.captures) and
         any(item is capture for item in context.captures), 'actual completed pending and original capture registration')
    need(kind is None or capture.kind==kind, 'same selected captured record kind')
    pinned(capture.raw,capture.pin)
    return capture

def completed_capture(context, pending, kind, raw, descriptor, origin, selection):
    """Internal issuer; it checks the full source-owned receiving occurrence."""
    need(type(pending) is ChannelPending and pending.channel is context.channel and
         pending.reply_authenticated and pending.completed_reply is not None and
         any(item is pending for item in context.channel.attempts), 'actual completed original reception')
    expected={'bootstrap_delivery':'BootstrapObjectRequestV1',
              'admission_delivery':'AdmissionObjectRequestV1',
              'publication_ack':'PublicationCommitV1',
              'effect_grant_delivery':'EffectIntentV1'}
    need(origin in expected and pending.request_kind==expected[origin], 'closed capture origin and original request')
    need(not pending.captures, 'one capture factory invocation for this completed pending')
    reply=pending.completed_reply['payload']
    if origin=='effect_grant_delivery':
        need(kind=='EffectGrantV1' and equal(descriptor,reply['grant']) and
             raw==encode(kind,reply['grant_body'],len(raw)) and selection is pending,
             'only actual delivered grant body and Pin from same completed pending')
    elif origin=='bootstrap_delivery':
        need(any(row is selection for row in context.object_table['rows']) and
             kind==selection['kind']==reply['kind'] and equal(descriptor,selection['capture']) and
             equal(descriptor,reply['capture']) and reply['final'] and
             pending.original_request_body['ordinal']==selection['ordinal'],
             'actual original table row and final contiguous reception')
    elif origin=='publication_ack':
        from .worker_publication_v3 import PublicationAttempt
        need(type(selection) is PublicationAttempt and context.publisher.pending_publication is selection and
             selection.commit_pending is pending and selection.raw is raw and selection.kind==kind and
             equal(descriptor,reply['capture']) and reply['kind']==kind,
             'actual original publication attempt and exact final capture acknowledgement')
    else:
        need(type(selection) is ChannelPending and selection.channel is context.channel and
             selection.request_kind=='PollBackendAdmissionV1' and selection.reply_authenticated and
             selection.completed_reply['payload']['schema']==RECORDS['CompletedBackendAdmissionV1']['schema_literal'],
             'actual completed original backend admission poll')
        field={'BackendAdmissionAck':'admission','HostInitializationObservation':'host_observation'}[kind]
        need(equal(descriptor,selection.completed_reply['payload'][field]) and equal(descriptor,reply['capture']) and
             kind==reply['kind'] and reply['final'] and reply['completed_reply_sequence']==selection.sequence,
             'exact selected admission object and final reception')
    decode(kind,raw,len(raw)); pinned(raw,descriptor)
    item=WorkerCapturedRecord(_CAPTURE,context,kind,raw,descriptor,origin,pending,selection)
    pending.captures.append(item); context.captures.append(item)
    return item

class WorkerChannel:
    __slots__ = ('endpoint','sequence','previous_ack','pending','attempts','context_identity',
                 'source_policy','packet_limit','sequence_limit','raw_first','secondaries',
                 'poisoned','grant_pending','context','sent_known','received_known')
    def __init__(self, token, endpoint):
        need(token is _CHANNEL, 'fixed native worker entry only')
        self.endpoint=endpoint; self.sequence=0; self.previous_ack=None; self.pending=None
        self.attempts=[]; self.context_identity=None; self.source_policy=None
        self.packet_limit=endpoint.maximum_packet; self.sequence_limit=endpoint.maximum_sequences
        need(type(self.packet_limit) is int and 0<self.packet_limit<=65536 and
             type(self.sequence_limit) is int and 0<self.sequence_limit<=4096,
             'earlier admitted finite channel limits')
        self.raw_first=None; self.secondaries=[]; self.poisoned=False; self.grant_pending=None
        self.context=None; self.sent_known=0; self.received_known=0

    def retain(self,error,pending=None,uncertain=False):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        if pending is not None:pending.retain(error);pending.uncertain|=uncertain
        self.poisoned=True
        if self.context is not None:self.context.retain(error)

    def request(self,kind,site,payload,expected,deadline):
        """Private semantic callers select every variant/site; no user dispatch."""
        need(not self.poisoned and self.pending is None and self.sequence<self.sequence_limit,
             'one outstanding source request within original sequence reservation')
        need(kind in _REPLIES and type(expected) is tuple and expected==_REPLIES[kind],
             'fixed source request/reply alternatives')
        hello=kind=='BootstrapHelloV3'
        need(hello==(self.sequence==0) and (hello or self.context_identity is not None),
             'only original Hello uses sequence zero and absent context')
        # Register before encoding, clock or physical transport effects.
        pending=ChannelPending(_PENDING,self,kind,site,payload,expected)
        self.pending=pending;self.attempts.append(pending)
        try:
            wire=encode('PacketV1',body('PacketV1',context=self.context_identity,
                direction='worker_to_host',payload=payload,previous_ack=self.previous_ack,
                sequence=self.sequence,source_policy=self.source_policy),self.packet_limit)
            pending.encoded_request=wire
            self.endpoint.now(deadline)
            pending.send_entered=True
            sent=self.endpoint.send(wire,self.packet_limit,deadline)
            if type(sent) is int and sent>=0:
                pending.known_sent_bytes=sent;self.sent_known+=sent
                pending.raw_sent_prefix=wire if sent==len(wire) else wire[:min(sent,len(wire))]
            need(type(sent) is int and sent==len(wire),'actual full once-only datagram send')
            pending.receive_entered=True
            raw=self.endpoint.receive(self.packet_limit,deadline)
            pending.raw_received_prefix=raw
            if type(raw) is bytes:
                pending.known_received_bytes=len(raw);self.received_known+=len(raw)
            reply=decode('PacketV1',raw,self.packet_limit)
            need(reply['direction']=='host_to_worker' and reply['sequence']==pending.sequence and
                 equal(reply['previous_ack'],self.previous_ack),'same original packet direction/sequence/ack')
            value=reply['payload'];schema=value['schema']
            if hello:
                need(schema==RECORDS['WorkerBootstrapGrantV1']['schema_literal'] and
                     equal(reply['context'],value['context']) and reply['source_policy'] is not None,
                     'actual nonnull original bootstrap context/policy reply')
                self.endpoint.verify_bootstrap_grant(value)
            else:
                need(equal(reply['context'],self.context_identity) and
                     equal(reply['source_policy'],self.source_policy),'same original context and selected policy')
            pending.completed_reply=reply
            need(schema in tuple(RECORDS[name]['schema_literal'] for name in expected),
                 'only exact expected current reply variant, no bare grant or terminal-success substitution')
            self.endpoint.now(deadline)
            # Semantic callers must authenticate their operation-specific joins
            # before acknowledging the sequence or issuing a capture.
            return pending
        except BaseException as error:
            self.retain(error,pending,uncertain=pending.send_entered)
            raise

    def acknowledge(self,pending):
        need(type(pending) is ChannelPending and self.pending is pending and
             pending.completed_reply is not None and not pending.reply_authenticated and
             not self.poisoned,'one exact fully checked pending acknowledgement')
        pending.reply_authenticated=True;pending.consumed=True
        self.previous_ack=pending.sequence;self.sequence+=1;self.pending=None
        return pending.completed_reply['payload']

def begin_channel(endpoint):
    from .backend_linux_worker_channel import WorkerNativeChannelEndpoint
    need(type(endpoint)is WorkerNativeChannelEndpoint,'actual fixed original admitted worker endpoint')
    endpoint.require_original()
    need(endpoint.protocol is None,'one original worker application protocol')
    channel=WorkerChannel(_CHANNEL,endpoint)
    endpoint.protocol=channel
    return channel
