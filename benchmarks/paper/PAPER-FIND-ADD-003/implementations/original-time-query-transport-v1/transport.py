"""Operator-only query delivery for the original seven-bin time endpoint.

Accepts already-prepared ROI vectors; never extracts, transforms or scores them.
Private state must be kept outside participant access. This is not an OS sandbox.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import hmac
import importlib.util
import json
import math
import os
from pathlib import Path
import secrets
import stat

MAPPING_SHA256 = "188fba737d63aaf7b23b92f70158b1c7dae656c62d13ba27b9a5dd97f052d0ac"
PACKET_SCHEMA = "h_original_time_signal_query_v1"
RESPONSE_SCHEMA = "h_original_time_signal_response_v1"
CONTEXT_SCHEMA = "h_original_time_signal_context_v1"
RECORD_LIMIT = 16384
MAX_ROIS = 10000
SOURCE_INPUT_SHA256 = "2ddee31087cd4ee4d6b133e02e05432a27d5fa5ee5beb81915fae65416b69f61"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def exact(value, keys):
    require(type(value) is dict and set(value) == set(keys), "Exact fields required")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def hex_digest(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def load_mapping(path=None):
    path = Path(path) if path is not None else Path(__file__).resolve().parent.parent / "original-time-opaque-v1" / "mapping.py"
    with path.open("rb") as handle:
        raw = handle.read(8938)
    require(len(raw) == 8937 and hashlib.sha256(raw).hexdigest() == MAPPING_SHA256,
            "Pinned opaque mapper identity changed")
    spec = importlib.util.spec_from_file_location("_h_time_signal_pinned_mapping", path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def new_context(candidate_sha256, access_condition, preparation_sha256):
    """Freeze once and retain privately; restart uses this exact same context."""
    return {"schema": CONTEXT_SCHEMA, "outcome": "improvement",
            "candidate_sha256": candidate_sha256, "access_condition": access_condition,
            "preparation_sha256": preparation_sha256, "input_sha256": SOURCE_INPUT_SHA256,
            "run_nonce": secrets.token_hex(32)}


def validate_context(context):
    exact(context, ("schema", "outcome", "candidate_sha256", "access_condition",
                    "preparation_sha256", "input_sha256", "run_nonce"))
    require(context["schema"] == CONTEXT_SCHEMA and context["outcome"] == "improvement",
            "Original time improvement context required")
    require(context["access_condition"] in ("paper_data", "paper_data_author_code"), "Unknown access condition")
    require(context["input_sha256"] == SOURCE_INPUT_SHA256, "Original smoothed/floored input required")
    require(all(hex_digest(context[k]) for k in ("candidate_sha256", "preparation_sha256", "run_nonce")),
            "Frozen candidate, preparation and nonce digests required")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate durable record field")
        result[key] = value
    return result


def _read(path):
    # Ancestor custody is an operator requirement; these checks cover the leaf.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_size <= RECORD_LIMIT, "Bounded regular record required")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            raw = handle.read(RECORD_LIMIT + 1)
        after = os.fstat(fd)
        require(len(raw) == info.st_size and (info.st_size, info.st_mtime_ns, info.st_ino) ==
                (after.st_size, after.st_mtime_ns, after.st_ino), "Record changed during read")
    finally:
        os.close(fd)
    return json.loads(raw, object_pairs_hook=_unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite record")))


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class SignalDelivery:
    """Single operator store, with durable first-final claims and private joins.

    State files are append-once, HMAC-authenticated, fsynced and never repaired.
    An incomplete claim is permanently failed on recovery. Truncated/corrupted
    records refuse recovery. There is no anti-rollback protection if an operator
    deletes/replaces the entire store, and no physical filesystem isolation.
    """

    @classmethod
    def create(cls, path, roster, context, secret, *, mapping_path=None):
        self = cls(path, roster, context, secret, mapping_path=mapping_path)
        self.root.mkdir(mode=0o700)  # Exclusive: never silently reset a prior store.
        fd = os.open(self.root / "LOCK", os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        self._write("MANIFEST.json", self._manifest)
        _sync_directory(self.root.parent)
        return self

    @classmethod
    def resume(cls, path, roster, context, secret, *, mapping_path=None):
        self = cls(path, roster, context, secret, mapping_path=mapping_path)
        with self._locked():
            pass
        return self

    def __init__(self, path, roster, context, secret, *, mapping_path=None):
        validate_context(context)
        require(type(secret) is bytes and len(secret) == 32, "Private 32-byte secret required")
        self.root = Path(path).absolute()
        self.context = json.loads(canonical(context))
        self._key = hmac.new(secret, canonical(["signal-delivery/v1", self.context]), hashlib.sha256).digest()
        self.mapping = load_mapping(mapping_path)
        self.plan = self.mapping.IdentityPlan(roster, self._key)
        self._manifest = {"schema": "h_time_signal_store_v1", "context": self.context,
                          "roster_sha256": self.plan._roster_hash, "mapping_sha256": MAPPING_SHA256,
                          "fold_count": len(self.plan.operator_fold_ids())}

    def _write(self, name, payload):
        envelope = {"payload": payload, "hmac": hmac.new(self._key, canonical([name, payload]), hashlib.sha256).hexdigest()}
        raw = canonical(envelope)
        require(len(raw) <= RECORD_LIMIT, "Durable record exceeds bound")
        fd = os.open(self.root / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            at = 0
            while at < len(raw):
                count = os.write(fd, raw[at:])
                require(count > 0, "Short durable write")
                at += count
            os.fsync(fd)
        finally:
            os.close(fd)
        _sync_directory(self.root)

    def _record(self, name):
        value = _read(self.root / name)
        exact(value, ("payload", "hmac"))
        require(hex_digest(value["hmac"]) and hmac.compare_digest(value["hmac"], hmac.new(
            self._key, canonical([name, value["payload"]]), hashlib.sha256).hexdigest()), "Private record authentication failed")
        return value["payload"]

    def _exists(self, name):
        try:
            (self.root / name).lstat()
            return True
        except FileNotFoundError:
            return False

    @contextmanager
    def _locked(self):
        require(stat.S_ISDIR(self.root.lstat().st_mode), "Operator store must be a directory, not a symlink")
        fd = os.open(self.root / "LOCK", os.O_RDONLY | os.O_NOFOLLOW)
        try:
            require(stat.S_ISREG(os.fstat(fd).st_mode), "Regular lock file required")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            require(self._record("MANIFEST.json") == self._manifest, "Context, candidate, access or roster changed")
            yield
        finally:
            os.close(fd)

    def _open_fold(self, fold_id):
        self.plan._lookup(fold_id)
        require(not self._exists("FINISHED.json"), "Collection is finalized")
        require(not self._exists(fold_id + ".claim.json"), "Fold already has a final disposition")

    def _packet(self, fold_id, prepared):
        """Join exact seven source keys; preserve every ROI value and its order."""
        binding = self.plan.operator_binding(fold_id)
        exact(prepared, ("input_sha256", "preparation_sha256", "roi_order_sha256", "roi_count", "rows"))
        require(prepared["input_sha256"] == self.context["input_sha256"] and
                prepared["preparation_sha256"] == self.context["preparation_sha256"], "Prepared source identity mismatch")
        require(hex_digest(prepared["roi_order_sha256"]), "Private ROI-order commitment required")
        n = prepared["roi_count"]
        require(type(n) is int and 1 <= n <= MAX_ROIS, "Original ROI vector size must be 1..10000")
        require(type(prepared["rows"]) is list and len(prepared["rows"]) == 7, "Exactly seven prepared query rows required")
        keyed = {}
        for row in prepared["rows"]:
            exact(row, ("animal", "day", "cue", "control", "trial_index", "actual_bin", "features"))
            require(all(type(row[k]) is type(binding[k]) and row[k] == binding[k]
                        for k in ("animal", "day", "cue", "control", "trial_index")), "Source-to-fold key mismatch")
            actual = row["actual_bin"]
            require(type(actual) is int and actual in range(1, 8) and actual not in keyed, "Duplicate or invalid source bin")
            values = row["features"]
            require(type(values) is list and len(values) == n and all(
                type(v) in (int, float) and math.isfinite(v) for v in values), "Finite numeric ROI vector required")
            keyed[actual] = list(values)
        require(set(keyed) == set(range(1, 8)), "Complete original seven-bin support required")
        # Mapper order is secret-dependent, never prepared-row or actual-bin order.
        queries = [{"query_id": q["query_id"], "features": keyed[q["actual_bin"]]}
                   for q in binding["queries"]]
        private_join = {"binding": binding, "input_sha256": prepared["input_sha256"],
                        "preparation_sha256": prepared["preparation_sha256"],
                        "roi_order_sha256": prepared["roi_order_sha256"], "roi_count": n,
                        "feature_hashes_by_actual_bin": [digest(keyed[i]) for i in range(1, 8)]}
        join_hash = digest(private_join)
        delivery_id = "d_" + hmac.new(self._key, canonical(["delivery", fold_id, join_hash]), hashlib.sha256).hexdigest()
        public = {"schema": PACKET_SCHEMA, "delivery_id": delivery_id, "fold_id": fold_id, "queries": queries}
        # Do not serialize the private binding, ROI identities or context into public.
        receipt = {"schema": "h_time_signal_issue_v1", "fold_id": fold_id, "delivery_id": delivery_id,
                   "context_sha256": digest(self.context), "private_join_sha256": join_hash,
                   "packet_sha256": digest(public), "roi_count": n}
        return public, receipt

    def issue(self, fold_id, prepared):
        """First exposure only. Caller must keep prepared/source/state private."""
        with self._locked():
            self._open_fold(fold_id)
            public, receipt = self._packet(fold_id, prepared)
            self._write(fold_id + ".issue.json", receipt)
            return public

    def resume_packet(self, fold_id, prepared):
        """Recover the IDENTICAL issued packet, never create a fresh exposure."""
        with self._locked():
            self._open_fold(fold_id)
            public, receipt = self._packet(fold_id, prepared)
            require(self._record(fold_id + ".issue.json") == receipt, "Issued content or private join changed")
            return public

    def _claim(self, fold_id):
        self._open_fold(fold_id)
        issued = self._record(fold_id + ".issue.json")
        self._write(fold_id + ".claim.json", {"schema": "h_time_signal_claim_v1",
                    "fold_id": fold_id, "issue_sha256": digest(issued)})
        # This is durable BEFORE any untrusted response fields are inspected.
        return issued

    def _validate_response(self, fold_id, response, issued):
        exact(response, ("schema", "fold_id", "delivery_id", "packet_sha256", "predictions"))
        require(response["schema"] == RESPONSE_SCHEMA and response["fold_id"] == fold_id and
                response["delivery_id"] == issued["delivery_id"] and
                response["packet_sha256"] == issued["packet_sha256"], "Stale, cross-fold or changed signal packet")
        # Bridge only after signal-content validation; preserve the unchanged
        # mapper's exact response validation and private seven-bin restoration.
        bridged = {"schema": self.mapping.RESPONSE_SCHEMA, "fold_id": fold_id,
                   "packet_sha256": self.mapping.content_hash(self.plan.public_fold(fold_id)),
                   "predictions": response["predictions"]}
        collector = self.mapping.Collector(self.plan)
        collector.submit(fold_id, bridged)
        return json.loads(canonical(bridged))

    def submit(self, fold_id, response):
        with self._locked():
            issued = self._claim(fold_id)
            try:
                bridged = self._validate_response(fold_id, response, issued)
            except (ValueError, TypeError, OverflowError):
                self._write(fold_id + ".result.json", {"status": "failed", "reason": "Malformed first-final signal response"})
                raise
            self._write(fold_id + ".result.json", {"status": "finite", "response": bridged})

    def fail(self, fold_id, reason):
        with self._locked():
            self._claim(fold_id)
            # Claim stays consumed even if the supplied failure reason is bad.
            require(type(reason) is str and 0 < len(reason.strip()) <= 1024, "Bounded failure reason required")
            self._write(fold_id + ".result.json", {"status": "failed", "reason": reason})

    def finish(self):
        """Restore all original support using the existing collector; no scoring."""
        with self._locked():
            collector = self.mapping.Collector(self.plan)
            for fold_id in self.plan.operator_fold_ids():
                claim_name, result_name = fold_id + ".claim.json", fold_id + ".result.json"
                if not self._exists(claim_name):
                    require(not self._exists(result_name), "Orphan final result")
                    continue
                issued = self._record(fold_id + ".issue.json")
                require(self._record(claim_name) == {"schema": "h_time_signal_claim_v1", "fold_id": fold_id,
                        "issue_sha256": digest(issued)}, "Claim-to-issue commitment mismatch")
                if not self._exists(result_name):
                    collector.fail(fold_id, "First-final claim interrupted before durable result")
                    continue
                result = self._record(result_name)
                require(type(result) is dict, "Malformed final result")
                if result.get("status") == "finite":
                    exact(result, ("status", "response"))
                    collector.submit(fold_id, result["response"])
                else:
                    exact(result, ("status", "reason"))
                    require(result["status"] == "failed", "Unknown final disposition")
                    collector.fail(fold_id, result["reason"])
            document = collector.finish()
            final = {"schema": "h_time_signal_finished_v1", "predictions_sha256": digest(document)}
            if self._exists("FINISHED.json"):
                require(self._record("FINISHED.json") == final, "Final collection changed")
            else:
                self._write("FINISHED.json", final)
            return document
