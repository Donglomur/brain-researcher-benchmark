"""Trusted selected-role issuance; explicit anchors, no key/environment discovery."""
from ..core.custody import AuthorityVerifier,CustodyError,require_digest

class RoleIssuer:
    def __init__(self,verifier,*,global_bindings,domain):
        if type(verifier) is not AuthorityVerifier or domain not in ('invented','authentic'):
            raise CustodyError('explicit trusted verifier/domain required')
        self.verifier=verifier;self.domain=domain;self.global_bindings=dict(global_bindings)
        verifier._validate_bindings(self.global_bindings)
        self.ordinal=0

    def capability(self,role,context_id,bindings):
        if not isinstance(context_id,str) or not context_id:
            raise CustodyError('explicit context ID')
        for k,v in bindings.items():
            require_digest(v)
            if k in self.global_bindings and self.global_bindings[k]!=v:
                raise CustodyError('component conflicts with global selected binding: '+k)
        merged={**self.global_bindings,**bindings};self.ordinal+=1
        nonce=f'{self.ordinal:016x}'
        envelope=self.verifier.issue(role=role,domain=self.domain,context_id=context_id,
            nonce=nonce,bindings=merged)
        return self.verifier.verify(envelope,role=role,domain=self.domain,bindings=merged)
