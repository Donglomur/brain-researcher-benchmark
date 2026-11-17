"""Fail-first, signed deployment admission and process-local scoped capabilities.

The trusted public verification key is supplied by the separately qualified
operator installation; it is not selected by a candidate or carried in a job.
No installation is included in this source package.
"""
import base64
import hashlib
import os
import time
from .wire import canonical, need
from .basis import EXPECTED

REQUIRED = ("full_source_identity", "full_mat_schema_and_units", "global_face_identity",
            "independent_native_output_schema", "all_original_clock_support", "immutable_store_custody",
            "candidate_image_excludes_trusted_evaluator", "a_b_exposure_equal_except_author_code",
            "host_and_worker_lossless_accounting", "protected_target_custody",
            "full_workload_resource_profile", "provider_spending_and_data_transfer",
            "native_image_and_conversion_parity")

class _Capability:
    __slots__ = ("nonce",)
    def __init__(self): self.nonce=object()

def verify_document(envelope, public_key):
    need(type(envelope) is dict and set(envelope)=={"document","signature"},"Signed exact document required")
    need(type(public_key) is bytes and len(public_key)==32,"Installed Ed25519 public key required")
    # Optional installation dependency is not installed or probed at import.
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    signature=base64.b64decode(envelope["signature"],validate=True)
    Ed25519PublicKey.from_public_bytes(public_key).verify(signature,canonical(envelope["document"]))
    return envelope["document"]

class Authority:
    def __init__(self,envelope,public_key,*,clock=time.monotonic_ns):
        need(type(envelope) is dict and envelope.get("document",{}).get("installed") is True,
             "No qualified runtime is installed; source cannot authorize execution")
        d=verify_document(envelope,public_key)
        need(d.get("schema")=="paper020_runtime_installation_v1" and d.get("scientific_source_digest")==EXPECTED,
             "Deployment/scientific source identity differs")
        need(set(d.get("qualifications",{}))==set(REQUIRED) and all(d["qualifications"][k] is True for k in REQUIRED),
             "Every independent physical/source qualification is required")
        need(type(d.get("origin_ns")) is int and type(d.get("deadline_ns")) is int
             and d["origin_ns"]<=clock()<d["deadline_ns"],"Original deployment clock expired")
        for key in ("source_root","store_root"):
            need(type(d.get(key)) is str and os.path.isabs(d[key]),"Operator-owned absolute roots required")
        self.document=d;self.clock=clock;self._tokens={};self.contexts={};self.seals={}
        self.fits={};self.closed=None;self.phase=None;self.host_identity=None
        self.provider_calls=0;self._credential=None;self._credential_fd=None
        self._target_issued=False;self._target_consumed=False
    def _clock(self):
        now=self.clock();need(self.document["origin_ns"]<=now<self.document["deadline_ns"],"Original strict deadline exceeded")
        return now
    def token(self,kind,**scope):
        self._clock();cap=_Capability();self._tokens[cap]=(kind,scope);return cap
    def _require(self,cap,action):
        self._clock();need(type(cap) is _Capability and cap in self._tokens and self._tokens[cap][0]==action,
                           "Absent/cross-scope authority capability")
        return self._tokens[cap][1]
    def require_store(self,cap,root):
        self._require(cap,"store");need(root==self.document["store_root"],"Unapproved store root")
        return True
    def source_token(self,action,**scope):
        if action=="source_open":
            need(scope.get("root")==self.document["source_root"],"Unapproved original source root")
        if action=="protected_targets":
            need(self.phase is not None and self.phase["kind"]=="load_targets_last_and_grade"
                 and self.closed is not None,"Protected access requires full validation/closure and final phase")
            need(not self._target_issued,"Protected capability may be issued only once")
            self._target_issued=True
        return self.token("source",action=action,**scope)
    def require_source(self,cap,action,*,admission_digest,mapping_digest,context=None,configuration=None,row_ids=(),seal=None):
        s=self._require(cap,"source")
        need(s.get("action")==action and admission_digest==self.document["admission_digest"]
             and mapping_digest==self.document["mapping_digest"],"Source/admission/capability join differs")
        for key,value in (("context",context),("configuration",configuration),("row_ids",tuple(row_ids)),("seal",seal)):
            if key in s: need(s[key]==value,"Source scope differs: "+key)
        if action=="training":
            desc=self.contexts[context]
            allowed={r["row_id"] for r in desc["training_rows"] if r["configuration"]==configuration}
            need(set(row_ids)<=allowed and len(set(row_ids))==len(row_ids),"Nontraining/repeated response row requested")
        if action=="query_features":
            need(context in self.seals and self.seals[context]==seal,"Unsealed query request")
            need(configuration in self.fits.get(context,{}),"Query precedes actual observed fit")
        if action=="native": need(self.contexts[context]["track"]=="native","Native arrays cannot cross prediction track")
        if action=="protected_targets":
            need(self.closed is not None and self.phase["kind"]=="load_targets_last_and_grade","Target capability used outside final grade")
            need(not self._target_consumed,"Protected capability may be consumed only once")
            self._target_consumed=True
        return True
    def process_qualification(self,manifest):
        self._clock()
        return hashlib.sha256(canonical(manifest)).hexdigest() in self.document["process_qualification_digests"]
    def provider(self,actor,track):
        self._clock();need(actor in ("A","B") and track in ("native","prediction"),"Invalid candidate/provider context")
        return self.document["provider"]
    def reserve_provider_request(self):
        self._clock();policy=self.document["provider"]
        need(self.provider_calls<policy["max_requests"],"Whole-study provider reservation exhausted")
        self.provider_calls+=1
    def provider_credential(self,fd):
        self._clock();need(type(fd) is int and fd>=3,"Operator-owned credential descriptor required")
        if self._credential is None:
            raw=os.read(fd,4097)
            need(0<len(raw)<=4096 and b"\n" not in raw.strip() and b"\r" not in raw,"Bounded single credential required")
            self._credential=raw.decode("ascii").strip();self._credential_fd=fd
        need(fd==self._credential_fd,"Credential capability changed during study")
        return self._credential
    def begin(self,phase,binding):
        self._clock();self.phase=phase;self.binding=binding
    def fit_closed(self,context,case,model,receipt):
        self.fits.setdefault(context,{})[case]=(model,receipt)
    def release(self,context,seal):
        from .basis import basis
        fits=self.fits.get(context,{})
        need(set(fits)==set(basis("programme").CONFIGS),"All 14 actual fit closures required")
        expected=basis("strict").digest({"fit_models":{k:v[0] for k,v in fits.items()},
                                        "fit_receipts":{k:v[1] for k,v in fits.items()}})
        need(expected==seal and context not in self.seals,"Whole-fit seal mismatch/reuse")
        self.seals[context]=seal
