"""Closed once-only worker publication protocol; H remains the actual writer."""
import hashlib
from .common import need, DependencyUnavailable
from .worker_context_records_v3 import body, encode, equal, pinned, validate
from .worker_context_schema_v3 import SITES
from .worker_channel_v3 import completed_capture

_PUBLISHER=object()
_ROLES=('server_executable','model_gguf','template','tokenizer_source','renderer_source')

def require_original_capture_source(context):
    """Compare the live installed admission, original carrier and received policy."""
    if context.local_raw_first is not None:raise context.local_raw_first
    try:
        context.require_active()
        endpoint=context.channel.endpoint
        endpoint.require_original()
        selected=endpoint.require_canonical_publisher_source_v3()
        policy=context.bootstrap('NativeContextPolicyV2').body
        need(equal(policy['canonical_publisher_source'],selected),
             'same independently selected installed publisher and actual earlier carrier policy')
        return selected
    except BaseException as error:
        context.retain(error);context.channel.retain(error,context.channel.pending)
        raise context.local_raw_first

class PublicationAttempt:
    __slots__=('publisher','site','kind','ordinal','name','value','raw','intent_pending',
               'chunk_pending','commit_pending','start','complete','raw_first','secondaries')
    def __init__(self,publisher,site,kind,ordinal,name,value):
        self.publisher=publisher;self.site=site;self.kind=kind;self.ordinal=ordinal;self.name=name;self.value=value
        self.raw=None;self.intent_pending=None;self.chunk_pending=[];self.commit_pending=None
        self.start=None;self.complete=None;self.raw_first=None;self.secondaries=[]
    def retain(self,error):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)

def fixed_path(site,value,ordinal):
    need(type(site) is str and site in SITES and type(ordinal) is int and ordinal>=0,
         'closed source publication site and ordinal')
    endpoint=None;role=None
    if '{endpoint}' in SITES[site]['path']:
        endpoint=value.get('endpoint');need(endpoint in ('health','slots','completion'),'fixed HTTP endpoint')
    if site=='artifact':
        role=value.get('role');need(role in _ROLES,'fixed ordered artifact role')
        need(ordinal==_ROLES.index(role),'artifact ordinal is fixed role index')
    if site=='snapshot':need(ordinal in (0,1,2),'three original snapshots')
    if site=='process':need(ordinal in (0,1),'two original process observations')
    if '{ordinal}' not in SITES[site]['path'] and site!='artifact':need(ordinal==0,'single original fixed slot')
    return SITES[site]['path'].format(ordinal=ordinal,endpoint=endpoint,role=role)

class WorkerCanonicalPublisher:
    __slots__=('context','same_channel','pending_publication','attempts','raw_first','ordered_secondaries')
    def __init__(self,token,context):
        need(token is _PUBLISHER,'fixed actual context publisher factory')
        self.context=context;self.same_channel=context.channel;self.pending_publication=None
        self.attempts={};self.raw_first=None;self.ordered_secondaries=[]
    @classmethod
    def _from_context(cls,context):
        from .worker_context_v3 import WorkerContextProxy
        need(type(context) is WorkerContextProxy and context.channel.context is context and context.publisher is None,
             'same original context after complete bootstrap')
        return cls(_PUBLISHER,context)
    def capture_fixed_site(self,site,value,*,ordinal=0,stage):
        context=self.context;channel=self.same_channel;context.require_active()
        capture_source=require_original_capture_source(context)
        need(self.raw_first is None and self.pending_publication is None and context.meter.current_effect is None,
             'no prior failed publication or unresolved original effect')
        need(site in SITES,'no wildcard publisher')
        kind=SITES[site]['kind'];name=fixed_path(site,value,ordinal)
        need(name not in self.attempts and len(self.attempts)<context.maximum_publications,
             'one original bounded publication slot, including failed attempts')
        attempt=PublicationAttempt(self,site,kind,ordinal,name,value)
        self.attempts[name]=attempt;self.pending_publication=attempt
        try:
            validate(kind,value)
            if 'condition' in value:need(value['condition']==context.context_identity['condition'],'same actual arm')
            if 'ordinal' in value:need(value['ordinal']==ordinal,'same original body and publication ordinal')
            if site=='snapshot':need(value['snapshot_ordinal']==ordinal,'same actual snapshot ordinal')
            if site=='completion_request':need(value['request_ordinal']==ordinal,'same actual semantic request ordinal')
            if site=='snapshot' and ordinal:
                previous=self.attempts.get(SITES['snapshot']['path'].format(ordinal=ordinal-1))
                need(previous is not None and previous.complete is not None,'actual earlier original snapshot')
            if site=='process' and ordinal:
                previous=self.attempts.get(SITES['process']['path'].format(ordinal=0))
                need(previous is not None and previous.complete is not None,'actual earlier original process observation')
            if site=='completion_request':
                previous=self.attempts.get(SITES['rendered_template']['path'].format(ordinal=ordinal))
                need(previous is not None and previous.complete is not None and
                     equal(value['rendered_template_observation'],previous.complete.pin),
                     'same actual earlier rendered-template publication')
            raw=encode(kind,value,context.logical_limit);attempt.raw=raw
            digest=hashlib.sha256(raw).hexdigest();deadline=context.deadline(stage)
            need(channel.sequence+3<=channel.sequence_limit,'minimum complete publication sequence headroom')
            intent=body('PublicationIntentV1',canonical_bytes=len(raw),canonical_sha256=digest,
                        kind=kind,ordinal=ordinal,site=site)
            pending=channel.request('PublicationIntentV1',site,intent,('PublicationStartAckV1',),deadline)
            attempt.intent_pending=pending;start=pending.completed_reply['payload'];attempt.start=start
            size=start['chunk_bytes'];count=start['chunk_count']
            need(start['intent_sequence']==pending.sequence and 0<size<=16384 and
                 count==(len(raw)+size-1)//size and channel.sequence+count+2<=channel.sequence_limit,
                 'exact finite complete publication chunk plan before any chunk')
            # Publication IDs and ledger slots originate in H's actual reply;
            # equality checks do not independently manufacture either authority.
            need(all(old is attempt or old.start is None or old.start['publication_id']!=start['publication_id']
                     for old in self.attempts.values()),'no reused H publication occurrence')
            channel.acknowledge(pending)
            for index in range(count):
                offset=index*size;chunk=raw[offset:offset+size]
                request=body('PublicationChunkV1',index=index,offset=offset,
                             publication_id=start['publication_id'],raw_hex=chunk.hex())
                pending=channel.request('PublicationChunkV1',site,request,('PublicationChunkAckV1',),deadline)
                attempt.chunk_pending.append(pending);reply=pending.completed_reply['payload']
                need(reply['publication_id']==start['publication_id'] and reply['index']==index and
                     reply['acknowledged_bytes']==len(chunk),'actual exact chunk acknowledgement')
                channel.acknowledge(pending)
            request=body('PublicationCommitV1',canonical_bytes=len(raw),canonical_sha256=digest,
                         publication_id=start['publication_id'])
            pending=channel.request('PublicationCommitV1',site,request,('PublicationAckV1',),deadline)
            attempt.commit_pending=pending;ack=pending.completed_reply['payload']
            need(ack['commit_sequence']==pending.sequence and ack['publication_id']==start['publication_id'] and
                 ack['kind']==kind and equal(ack['context'],context.context_identity),
                 'same original completed publication and context')
            # Pin.path is verified against the selected H store publication path
            # by the real H producer. W never synthesizes that path into a Pin.
            pinned(raw,ack['capture'])
            need(equal(ack['original_capture_source'],capture_source),
                 'actual original selected H capture source')
            channel.acknowledge(pending)
            capture=completed_capture(context,pending,kind,raw,ack['capture'],'publication_ack',attempt)
            attempt.complete=capture;context.meter.last_acknowledged_cost_prefix=ack['cost_prefix']
            self.pending_publication=None
            return capture
        except BaseException as error:
            attempt.retain(error)
            if self.raw_first is None:self.raw_first=error
            elif error is not self.raw_first:self.ordered_secondaries.append(error)
            context.retain(error);channel.retain(error,channel.pending,uncertain=True)
            raise
