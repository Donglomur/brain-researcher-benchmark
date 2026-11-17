"""External independent qualification; candidate assertions cannot grant authority."""
import base64
from .common import keys,require,encoded,sha,capture,parse

class Authority:
    def __init__(self,root,trust_descriptor,budget):
        self.root=root;self.budget=budget
        raw=capture(root,trust_descriptor,budget,1048576);self.identity=sha(raw);self.trust=parse(raw)
        keys(self.trust,('schema','issuers','deployment_identity','source_identity'))
        require(self.trust['schema']=='neural055-external-trust-v1','independent trust schema')
        self.used=[]
    def verify(self,receipt_descriptor,kind,subject):
        raw=capture(self.root,receipt_descriptor,self.budget,4194304)
        return self.verify_bytes(raw,kind,subject)
    def verify_bytes(self,raw,kind,subject):
        require(type(raw)is bytes and 0<len(raw)<=4194304,'bounded independently captured qualification')
        r=parse(raw)
        keys(r,('schema','issuer','kind','subject_sha256','evidence','limitations','signature'))
        require(r['schema']=='neural055-independent-qualification-v1' and r['kind']==kind,'specific independent qualification kind')
        require(r['subject_sha256']==sha(encoded(subject)),'exact independently reviewed subject')
        issuer=self.trust['issuers'][r['issuer']]
        require(kind in issuer['roles'] and issuer['independent_of_candidate'] is True,'selected independent issuer role')
        # Public verification only. No secret key is read or generated here.
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        key=Ed25519PublicKey.from_public_bytes(base64.b64decode(issuer['public_key_base64'],validate=True))
        unsigned={k:v for k,v in r.items() if k!='signature'}
        key.verify(base64.b64decode(r['signature'],validate=True),encoded(unsigned))
        require(type(r['evidence'])is list and len(r['evidence'])>0,'substantive original evidence required')
        # Every evidence record is an ordinary attestation/report role; raw private
        # inputs are separately handled only by their qualified producer/consumer.
        for d in r['evidence']:
            require(d['role'] in ('qualification_report','original_process_receipt','source_review','semantic_operation_review','input_join_report','reference_competence_report'),'closed evidence role')
            capture(self.root,d,self.budget,16777216)
        self.budget.check('after independent signature and evidence')
        self.used.append({'kind':kind,'subject_sha256':r['subject_sha256'],'receipt_sha256':sha(raw),'limitations':r['limitations']})
        return r
