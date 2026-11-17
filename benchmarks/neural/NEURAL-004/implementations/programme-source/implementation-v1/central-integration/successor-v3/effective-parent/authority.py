"""External signed qualification joins. No shipped authority or credential."""
import base64
from .common import fields,need,integer,token,pin,check_pin,encode

ROLES=('operator','environment','observer','provider','human_review')
class Authorities:
    def __init__(self,anchors,source_pin,run_id,ledger):
        fields(anchors,ROLES);check_pin(source_pin);token(run_id)
        self.anchors=anchors;self.source_pin=source_pin;self.run_id=run_id;self.ledger=ledger;self.seen={}
        for role,entry in anchors.items():
            fields(entry,('issuer','public_key_base64','independent_selection_pin'))
            token(entry['issuer']);check_pin(entry['independent_selection_pin'])
        need(len({a['issuer'] for a in anchors.values()})==len(ROLES),'separate independently selected authority issuers')
        keys=[base64.b64decode(a['public_key_base64'],validate=True) for a in anchors.values()]
        need(all(len(k)==32 for k in keys) and len(set(keys))==len(ROLES),'distinct exact decoded role public keys')
        need(len({a['independent_selection_pin']['sha256'] for a in anchors.values()})==len(ROLES),'separate independent role selections')
    def verify(self,envelope,role,kind,subject):
        """Caller supplies an envelope, never an assertion that it was verified."""
        need(role in ROLES,'named independent role')
        if type(envelope) is IncrementalEnvelope:
            envelope=envelope.fetch(role,kind,subject,self.source_pin,self.run_id,self.ledger)
        fields(envelope,('payload','signature_base64'))
        p=envelope['payload'];fields(p,('schema','issuer','role','kind','run_id','source_pin','subject','issued_ns','expires_ns','facts'))
        need(p['schema']=='neural004_authority_v1' and p['role']==role and p['kind']==kind and
             p['issuer']==self.anchors[role]['issuer'] and p['run_id']==self.run_id and p['source_pin']==self.source_pin and p['subject']==subject,'authority exact operation/source/role binding')
        now=self.ledger.tick('closeout' if kind in ('operation_closure','operator_phase_closure','study_closure','study_scientific_qualification','human_reviews') else 'scientific')
        need(type(p['issued_ns']) is int and type(p['expires_ns']) is int and self.ledger.origin<=p['issued_ns']<=now<p['expires_ns']<=self.ledger.outer,'original clock and finite authority expiry')
        raw=encode(p,1048576);self.ledger.reserve({'read_bytes':len(raw)},'signed authority verification',cutoff='closeout' if kind in ('operation_closure','operator_phase_closure','study_closure','study_scientific_qualification','human_reviews') else 'scientific')
        # Deferred optional runtime dependency; no installation or key access on import.
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        key=base64.b64decode(self.anchors[role]['public_key_base64'],validate=True)
        signature=base64.b64decode(envelope['signature_base64'],validate=True)
        need(len(key)==32 and len(signature)==64,'exact Ed25519 public verification material')
        Ed25519PublicKey.from_public_bytes(key).verify(signature,raw)
        result={'envelope_pin':pin(envelope),'facts':p['facts'],'subject':subject,'issuer':p['issuer']}
        self.seen[(role,kind,pin(subject)['sha256'])]=result;return result

def complete_closure(verified,job_record,limits,cutoffs,*,require_success=True):
    """Exact independently signed operation facts plus bounded original clocks."""
    from .context_budget import bounded_resources,PHYSICAL_CAPS
    f=verified['facts'];fields(f,('observation_pin','binding_digest','source_pin','view_pin','origin_ns','finished_ns','observation_closed_ns',
        'physical_resources','historical_exposure','isolation','ordinary_files','natural_exit','exit_code','stream_eof',
        'all_descendants_closed','durable_outputs','forced_stop','unknown'))
    observed=job_record['observation'];need(type(observed) is dict,'actual owned job observation')
    need(f['observation_pin']==pin(observed) and f['binding_digest']==job_record['binding_digest'] and
         f['source_pin']==job_record['source_pin'] and f['view_pin']==job_record['view_pin'] and
         f['origin_ns']==job_record['origin_ns']==cutoffs['origin_ns'],'exact source/view/original operation')
    for field in ('finished_ns','observation_closed_ns'):integer(f[field],1)
    need(cutoffs['origin_ns']<=f['finished_ns']<=f['observation_closed_ns']<cutoffs['closeout_ns'],'original process/observation closeout interval')
    need(f['finished_ns']==observed.get('finished_ns') and f['observation_closed_ns']==observed.get('observation_closed_ns'),'actual child and observation clocks retained separately')
    need(not f['unknown'] and all(f[k] is True for k in ('historical_exposure','isolation','all_descendants_closed')),'complete independent custody')
    fields(f['physical_resources'],PHYSICAL_CAPS)
    for value in f['physical_resources'].values():integer(value)
    over=[k for k,cap in PHYSICAL_CAPS.items() if f['physical_resources'][k]>limits[cap]]
    if require_success:
        need(type(f['exit_code']) is int and f['exit_code']==0 and f['forced_stop'] is False and
             f['natural_exit'] is True and f['stream_eof'] is True and f['ordinary_files'] is True and f['durable_outputs'] is True,'actual successful closure types/facts')
        need(type(observed.get('exit_code')) is int and observed['exit_code']==0 and observed.get('natural_exit') is True and
             observed.get('stream_eof') is True and observed.get('forced_stop') is False,'same actual supervisor success')
        need(f['finished_ns']<cutoffs['scientific_ns'],'original scientific completion cutoff')
        bounded_resources(f['physical_resources'],limits)
    else:
        need(f['exit_code'] is None or type(f['exit_code']) is int,'honest failed/unlaunched exit status')
    return {'base_observation_pin':f['observation_pin'],'independent_complete_profile_pin':verified['envelope_pin'],
        'physical_resources':f['physical_resources'],'resource_failures':over,'successful_scientific_operation':require_success,'qualified_custody':True}


CLOSEOUT_KINDS=frozenset(('operation_closure','operator_phase_closure','study_closure','study_scientific_qualification','human_reviews'))

class MetadataChannel:
    """Concrete protected Unix exchange of current signed facts or opaque secrets.

    Selection and peer-process custody are independent deployment operands.
    No signing key or scientific result producer is implemented here.
    """
    def __init__(self,selection,ledger,bodies=None):
        fields(selection,('schema','selected','source_pin','run_id','authority_selection_pin','roles',
            'max_message_bytes','max_requests','credential_cap','seed_bytes'))
        need(selection['schema']=='neural004_incremental_channel_v1' and selection['selected'] is True,'independently selected protected exchange')
        check_pin(selection['source_pin']);check_pin(selection['authority_selection_pin']);token(selection['run_id'])
        fields(selection['roles'],ROLES)
        from pathlib import Path
        for item in selection['roles'].values():
            fields(item,('endpoint','uid','pid'));integer(item['uid']);integer(item['pid'],1)
            need(type(item['endpoint']) is str and Path(item['endpoint']).is_absolute(),'fixed absolute protected role socket')
        need(len({r['pid'] for r in selection['roles'].values()})==len(ROLES),'separate selected role processes')
        for key in ('max_message_bytes','max_requests','credential_cap'):integer(selection[key],1)
        need(selection['seed_bytes']==32,'exact opaque operator seed extent')
        self.selection=selection;self.ledger=ledger;self.bodies=bodies;self.serial=0;self.audit=[]
    def bind_parent(self,ledger,bodies):
        need((ledger.origin,ledger.scientific,ledger.closeout,ledger.outer)==(self.ledger.origin,self.ledger.scientific,self.ledger.closeout,self.ledger.outer),'same original channel clock after bootstrap')
        self.ledger=ledger;self.bodies=bodies
    def exchange(self,role,kind,subject,*,secret=False):
        import os,socket,stat,struct
        from pathlib import Path
        from .common import body_pin,decode,Cleanup
        from .physical.transport import peer_identity,receive
        allowed={'operator':('operator_seed','global_commitment','input_admission','context_exposure','target_release','reconstruction_tolerances','study_scientific_qualification'),'environment':('runtime_profile',),'observer':('operation_closure','operator_phase_closure','study_closure'),'provider':('provider_credential',),'human_review':('human_reviews',)}
        need(role in allowed and kind in allowed[role],'fixed role-specific authority operation')
        need(secret is (kind in ('operator_seed','provider_credential')),'only fixed private secret delivery methods')
        need(not secret or (role,kind) in (('operator','operator_seed'),('provider','provider_credential')),'exact secret delivery role')
        cutoff='closeout' if kind in CLOSEOUT_KINDS else 'scientific';l=self.ledger
        end=l.closeout if cutoff=='closeout' else l.scientific;l.tick(cutoff)
        need(self.serial<self.selection['max_requests'],'complete authority exchange count cap');self.serial+=1
        cap=self.selection['max_message_bytes'];peer=self.selection['roles'][role]
        request={'schema':'neural004_incremental_request_v1','sequence':self.serial,'role':role,'kind':kind,
            'source_pin':self.selection['source_pin'],'run_id':self.selection['run_id'],'subject':subject,
            'authority_selection_pin':self.selection['authority_selection_pin'],
            'clock':{'origin_ns':l.origin,'scientific_ns':l.scientific,'closeout_ns':l.closeout,'outer_ns':l.outer}}
        raw=encode(request,cap);request_pin=body_pin(raw)
        metadata={'sequence':self.serial,'role':role,'kind':kind,'request_pin':request_pin,'secret_reply':secret,'status':'attempted'}
        self.audit.append(metadata)
        if self.bodies is not None:self.bodies.put('authority-request-'+str(self.serial)+'.json',raw,cutoff=cutoff)
        l.reserve({'requests':1,'write_bytes':len(raw)+8},'incremental authority request',cutoff=cutoff)
        endpoint=Path(peer['endpoint'])
        need(not any(p.is_symlink() for p in (endpoint,*endpoint.parents)),'ordinary protected endpoint ancestry')
        need(stat.S_ISSOCK(os.stat(endpoint,follow_symlinks=False).st_mode),'selected protected role socket')
        received=[]
        def exact(sock,n):
            left=n;parts=[]
            while left:
                l.tick(cutoff);extent=min(left,65536);l.reserve({'read_bytes':extent},'bounded authority read',cutoff=cutoff)
                need(l.clock()<end,'original authority read cutoff');sock.settimeout((end-l.clock())/1e9)
                block=sock.recv(extent);need(block,'unexpected framed authority EOF');parts.append(block);left-=len(block)
                if not secret:received.append(block)
            return b''.join(parts)
        try:
            with l.live(4*cap+len(raw),'bounded incremental authority exchange',cutoff=cutoff):
                with Cleanup(l) as cleanup:
                    sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);cleanup.defer('close authority socket',sock.close)
                    sock.settimeout(max(.001,(end-l.clock())/1e9));sock.connect(str(endpoint));identity=peer_identity(sock)
                    need(identity['uid']==peer['uid'] and identity['pid']==peer['pid'],'independently selected exact role peer')
                    l.tick(cutoff);sock.sendall(struct.pack('!Q',len(raw))+raw)
                    size=struct.unpack('!Q',exact(sock,8))[0];need(size<=cap,'response extent before allocation')
                    response_raw=exact(sock,size);reply=decode(response_raw,cap)
                    fields(reply,('schema','request_pin','sequence','role','source_pin','run_id','payload'))
                    need(reply['schema']=='neural004_incremental_response_v1' and reply['request_pin']==request_pin and
                        type(reply['sequence']) is int and reply['sequence']==self.serial and reply['role']==role and reply['source_pin']==self.selection['source_pin'] and
                        reply['run_id']==self.selection['run_id'],'same original protected request and role')
                    value=reply['payload'];l.tick(cutoff)
                    if not secret:
                        need(self.bodies is not None,'signed authority reply retained in private parent journal')
                        self.bodies.put('authority-response-'+str(self.serial)+'.json',response_raw,cutoff=cutoff)
                    # Never hash or publish a secret response, including failure prefixes.
                    metadata.update(status='received',finished_ns=l.clock(),peer={'uid':identity['uid'],'pid':identity['pid']})
            l.tick(cutoff);return value
        except BaseException as error:
            metadata.update(status='failed',error_type=type(error).__name__)
            error.neural004_exchange_metadata=dict(metadata)
            if not secret and self.bodies is not None:
                cleanup=Cleanup(l)
                cleanup.defer('retain bounded failed authority stream',lambda:self.bodies.put('authority-failed-stream-'+str(self.serial)+'.bin',b''.join(received),cutoff='closeout'))
                cleanup.run(error)
            raise

class IncrementalEnvelope:
    """Typed request token; only actual signed envelopes reach ordinary verification."""
    def __init__(self,channel):
        need(type(channel) is MetadataChannel,'source-owned metadata channel');self.channel=channel
    def fetch(self,role,kind,subject,source_pin,run_id,ledger):
        need(self.channel.ledger is ledger and self.channel.selection['source_pin']==source_pin and self.channel.selection['run_id']==run_id,'same original authority instance and channel')
        value=self.channel.exchange(role,kind,subject)
        fields(value,('payload','signature_base64'));return value

class ProviderAccess:
    """Per-context opaque delivery; never reads a credential body from disk."""
    def __init__(self,channel,deployments):
        from .common import GLOBAL_POLICIES
        need(type(channel) is MetadataChannel,'source-owned credential channel');fields(deployments,GLOBAL_POLICIES)
        for item in deployments.values():
            fields(item,('deployment_path','deployment_pin','provider_policy_pin'))
            check_pin(item['deployment_pin']);check_pin(item['provider_policy_pin'])
            from pathlib import Path
            need(type(item['deployment_path']) is str and Path(item['deployment_path']).is_absolute(),'selected provider deployment path')
        self.channel=channel;self.deployments=deployments
    def resolve(self,policy,context):
        item=self.deployments[policy['name']]
        need(item['provider_policy_pin']==policy['provider']['policy_pin'],'correct policy-specific deployed provider')
        subject={'context':context,'policy_pin':pin(policy,4*1048576),'provider_policy_pin':policy['provider']['policy_pin'],
            'endpoint':policy['provider']['endpoint'],'model':policy['provider']['model'],'deployment_pin':item['deployment_pin']}
        reply=self.channel.exchange('provider','provider_credential',subject,secret=True)
        fields(reply,('authorization_header','lease_pin','expires_ns'));header=reply['authorization_header']
        need(type(header) is str and 0<len(header.encode())<=self.channel.selection['credential_cap'] and '\n' not in header and '\r' not in header,'bounded opaque header')
        check_pin(reply['lease_pin']);integer(reply['expires_ns'],1)
        need(self.channel.ledger.clock()<reply['expires_ns']<=self.channel.ledger.outer,'original bounded credential lease')
        self.channel.audit[-1]['lease_pin']=reply['lease_pin']
        return item['deployment_path'],item['deployment_pin'],header

def provider_access(deployment_path,deployment_pin,credential,policy,context):
    if type(credential) is ProviderAccess:
        need(deployment_path is None and deployment_pin is None,'typed per-policy access has no ambiguous fallback deployment')
        return credential.resolve(policy,context)
    need(type(credential) is str,'original literal credential or source-owned policy access')
    return deployment_path,deployment_pin,credential
