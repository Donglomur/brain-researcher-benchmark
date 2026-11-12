"""Operator-issued qualification, not a caller's self-asserted execution flag."""
from __future__ import annotations
import base64
from .common import require, encode, identity, Refusal

ALL_GATES = {f'G{i:02d}' for i in range(1, 25)}

class Authority:
    def __init__(self, trusted_policy, signed_permit, *, now):
        require(trusted_policy['status'] == 'QUALIFIED_EXECUTION_POLICY',
                'BUILD_ONLY_SCIENTIFIC_EXECUTION_DISABLED')
        require(trusted_policy['issuer_public_key_hex'], 'OPERATOR_ISSUER_NOT_SELECTED')
        permit = signed_permit['payload']
        # Imported only for a future selected permit verification, never for design/control work.
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        verifier = Ed25519PublicKey.from_public_bytes(bytes.fromhex(trusted_policy['issuer_public_key_hex']))
        try:verifier.verify(base64.b64decode(signed_permit['signature'], validate=True), encode(permit))
        except Exception as exc:raise Refusal('INVALID_OPERATOR_PERMIT') from exc
        require(permit['issuer'] == trusted_policy['issuer'], 'ISSUER_MISMATCH')
        require(now() < permit['expires_utc'], 'EXPIRED_QUALIFICATION_PERMIT')
        require(set(permit['gate_evidence']) == ALL_GATES, 'INCOMPLETE_GATE_EVIDENCE')
        require(all(x['status'] == 'ACCEPTED' and x['evidence_sha256'] for x in permit['gate_evidence'].values()),
                'OPEN_SCIENTIFIC_GATE')
        self.permit, self.now, self.hash = permit, now, identity(permit)

    def admit(self, *, plan, source_manifest, route, input_registry, effect):
        require(self.now() < self.permit['expires_utc'], 'EXPIRED_QUALIFICATION_PERMIT', effect)
        for key, actual in [('plan_sha256', plan), ('source_manifest_sha256', source_manifest),
                            ('input_registry_sha256', input_registry)]:
            require(self.permit[key] == actual, 'QUALIFICATION_BINDING_MISMATCH', key)
        require(route in self.permit['routes'], 'ROUTE_NOT_QUALIFIED')
        require(self.permit['no_network'] and self.permit['isolation_qualified'], 'UNQUALIFIED_ISOLATION')
        return self.hash

    def permit_paper(self, descriptor, arm):
        require(arm in {'A','B'} and descriptor in self.permit['matched_paper_inputs'],
                'PAPER_INPUT_NOT_SEPARATELY_QUALIFIED')
        require(self.now() < self.permit['expires_utc'], 'EXPIRED_PAPER_ACCESS')

    def producer(self, producer_id, source_sha256):
        require(self.permit['producers'].get(producer_id) == source_sha256,
                'UNQUALIFIED_SCIENTIFIC_PRODUCER', producer_id)
