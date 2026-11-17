"""Trusted-host signed capabilities. No import-time filesystem or provider access.

These objects preserve authority within an already isolated trusted host. Python
objects are not a security boundary against arbitrary code in that same host.
Candidates must run in separately admitted processes without issuer key access.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from typing import Mapping, Any


class CustodyError(ValueError):
    pass


_HEX = re.compile(r"^[0-9a-f]{64}$")
_ROLES = frozenset({"admission", "export", "reference_fit", "reference_predict",
                    "candidate_author", "candidate_query", "score", "close"})
_DOMAINS = frozenset({"invented", "authentic"})
_SENTINEL = object()


def canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError) as exc:
        raise CustodyError("noncanonical JSON value") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def require_digest(value: str) -> str:
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        raise CustodyError("expected lowercase SHA256")
    return value


def _unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise CustodyError("duplicate JSON object key")
        obj[key] = value
    return obj


def decode_json(data: bytes, limit: int = 1 << 20):
    if not isinstance(data, bytes) or len(data) > limit:
        raise CustodyError("bounded bytes required")
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_pairs,
                          parse_constant=lambda x: (_ for _ in ()).throw(CustodyError("nonfinite JSON")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CustodyError("invalid JSON") from exc


@dataclass(frozen=True)
class EvidencePin:
    kind: str
    sha256: str
    bytes: int

    def __post_init__(self):
        require_digest(self.sha256)
        if not self.kind or type(self.bytes) is not int or self.bytes <= 0:
            raise CustodyError("invalid evidence pin")

    def to_dict(self):
        return {"kind": self.kind, "sha256": self.sha256, "bytes": self.bytes}


class VerifiedAuthority:
    """Issued only by AuthorityVerifier after MAC and root-selection validation.

    Production components call require() with their exact computed binding.
    No boolean, numeric corpus size or unsigned assessment is an authority.
    This class must never be supplied by deserializing candidate objects.
    """
    __slots__ = ("_claims", "_seal")

    def __init__(self, claims, seal):
        if seal is not _SENTINEL:
            raise CustodyError("authority must be verified by trusted host")
        # Canonical roundtrip prevents alias mutation of the validated input.
        object.__setattr__(self, "_claims", canonical(claims))
        object.__setattr__(self, "_seal", seal)

    def __setattr__(self, name, value):
        raise CustodyError("verified authority is immutable")

    @property
    def domain(self):
        return json.loads(self._claims)["domain"]

    @property
    def role(self):
        return json.loads(self._claims)["role"]

    @property
    def authority_digest(self):
        return hashlib.sha256(self._claims).hexdigest()

    def require(self, *, role: str, domain: str, bindings: Mapping[str, str]):
        if self._seal is not _SENTINEL:
            raise CustodyError("invalid internal authority")
        claims = json.loads(self._claims)
        if role not in _ROLES or domain not in _DOMAINS:
            raise CustodyError("unknown authority role/domain")
        if claims["role"] != role or claims["domain"] != domain:
            raise CustodyError("authority role/domain mismatch")
        if not isinstance(bindings, Mapping) or not bindings:
            raise CustodyError("exact role bindings required")
        for key, value in bindings.items():
            require_digest(value)
            if claims["bindings"].get(key) != value:
                raise CustodyError("authority binding mismatch: " + key)
        return self.authority_digest


class AuthorityVerifier:
    """Operator-configured trust anchor; does not read or discover keys.

    Authentic authority additionally needs a root-signed execution selection.
    BUILD ONLY callers never create such a selection. The constructor's key
    arguments are supplied inside a separately qualified trusted process.
    """
    def __init__(self, *, issuer_id: str, issuer_key: bytes, root_id: str,
                 root_key: bytes, expected_design: str, root_selection: bytes | None = None):
        if not issuer_id or not root_id or type(issuer_key) is not bytes or type(root_key) is not bytes:
            raise CustodyError("explicit trusted issuer/root required")
        if len(issuer_key) < 32 or len(root_key) < 32:
            raise CustodyError("keys must be at least256 bits")
        self.issuer_id, self.root_id = issuer_id, root_id
        self._key, self._root_key = bytes(issuer_key), bytes(root_key)
        self.design = require_digest(expected_design)
        self._selection = None
        if root_selection is not None:
            outer = decode_json(root_selection)
            if set(outer) != {"claims", "mac"}:
                raise CustodyError("root envelope schema")
            claims = outer["claims"]
            expected = hmac.new(self._root_key, canonical(claims), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, str(outer["mac"])):
                raise CustodyError("root selection signature")
            required = {"schema", "root_id", "issuer_id", "design_digest", "domain", "roles",
                        "selection_id", "binding_constraints", "evidence"}
            if not isinstance(claims, dict) or set(claims) != required:
                raise CustodyError("root selection schema")
            if (claims["schema"] != "n073_execution_selection_v1" or claims["root_id"] != root_id
                or claims["issuer_id"] != issuer_id or claims["design_digest"] != self.design
                or claims["domain"] != "authentic" or not claims["selection_id"]):
                raise CustodyError("root selection identity/domain")
            if not isinstance(claims["roles"], list) or not set(claims["roles"]) <= _ROLES:
                raise CustodyError("root roles")
            self._validate_bindings(claims["binding_constraints"])
            if not isinstance(claims["evidence"], list) or not claims["evidence"]:
                raise CustodyError("root evidence required")
            for pin in claims["evidence"]:
                EvidencePin(**pin)
            self._selection = canonical(claims)

    @staticmethod
    def _validate_bindings(bindings):
        if not isinstance(bindings, dict) or not bindings:
            raise CustodyError("explicit content bindings required")
        for key, value in bindings.items():
            if not isinstance(key, str) or not key:
                raise CustodyError("invalid binding name")
            require_digest(value)

    def verify(self, envelope: bytes, *, role: str, domain: str,
               bindings: Mapping[str, str]) -> VerifiedAuthority:
        outer = decode_json(envelope)
        if not isinstance(outer, dict) or set(outer) != {"claims", "mac"}:
            raise CustodyError("capability envelope schema")
        claims = outer["claims"]
        if not isinstance(claims, dict) or set(claims) != {"schema", "issuer_id", "design_digest", "domain",
             "role", "context_id", "nonce", "bindings", "root_selection_digest"}:
            raise CustodyError("capability claims schema")
        expected = hmac.new(self._key, canonical(claims), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, str(outer["mac"])):
            raise CustodyError("capability signature")
        if (claims["schema"] != "n073_capability_v1" or claims["issuer_id"] != self.issuer_id
            or claims["design_digest"] != self.design or claims["domain"] not in _DOMAINS
            or claims["role"] not in _ROLES or not isinstance(claims["context_id"], str)
            or not claims["context_id"] or not isinstance(claims["nonce"], str) or not claims["nonce"]):
            raise CustodyError("capability identity")
        self._validate_bindings(claims["bindings"])
        if claims["domain"] == "authentic":
            if self._selection is None:
                raise CustodyError("authentic execution not selected")
            root = json.loads(self._selection)
            if claims["root_selection_digest"] != hashlib.sha256(self._selection).hexdigest():
                raise CustodyError("wrong root selection")
            if claims["role"] not in root["roles"]:
                raise CustodyError("unselected role")
            for key, value in root["binding_constraints"].items():
                if claims["bindings"].get(key) != value:
                    raise CustodyError("root constraint mismatch")
        elif claims["root_selection_digest"] is not None:
            raise CustodyError("invented capability cannot use authentic selection")
        result = VerifiedAuthority(claims, _SENTINEL)
        result.require(role=role, domain=domain, bindings=bindings)
        return result

    def issue(self, *, role: str, domain: str, context_id: str, nonce: str,
              bindings: Mapping[str, str]) -> bytes:
        """Trusted issuer only; candidate sandboxes cannot import this key-bearing object."""
        self._validate_bindings(dict(bindings))
        root_digest = None
        if domain == "authentic":
            if self._selection is None:
                raise CustodyError("BUILD ONLY: authentic execution not selected")
            root_digest = hashlib.sha256(self._selection).hexdigest()
        claims = {"schema": "n073_capability_v1", "issuer_id": self.issuer_id,
                  "design_digest": self.design, "domain": domain, "role": role,
                  "context_id": context_id, "nonce": nonce, "bindings": dict(bindings),
                  "root_selection_digest": root_digest}
        envelope = canonical({"claims": claims, "mac": hmac.new(self._key, canonical(claims), hashlib.sha256).hexdigest()})
        self.verify(envelope, role=role, domain=domain, bindings=bindings)
        return envelope
