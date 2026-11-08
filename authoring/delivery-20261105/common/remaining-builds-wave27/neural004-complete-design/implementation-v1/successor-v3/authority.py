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
        need(role in ROLES,'named independent role');fields(envelope,('payload','signature_base64'))
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
