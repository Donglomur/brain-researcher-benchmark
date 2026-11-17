"""Hybrid fixed-profile TRAIN-only producer and private export provenance.

No source cases, NumPy, scientific fit, process or network operation occurs on
import. The producer accepts only anonymous three-session training JSON. The
curator authenticates full cases separately and retains signed provenance; only
the existing anonymous artifact enters the existing prediction transport.
"""
from __future__ import annotations

import ast
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import stat
import sys
import types

TASK_ID = "NEURAL-CENTRAL-20261114-HYBRID-BEHAVIOR"
CONTRACT_SHA256 = '5b6165223576f4659cfa12610a803d776b03881680e09fcf7af002065a8f7e8c'
PROFILE = "hybrid-anonymous-statistical-training-v1"
MAX_PROGRAM_BYTES = 1048576
MAX_ARTIFACT_BYTES = 65536
MAX_REQUEST_BYTES = 128 * 1024 * 1024
MAX_PRIVATE_RECEIPT_BYTES = 1048576
SOURCE_PINS = {
    "consumer": (13637, "c5876452457f05c3f9fe69015f7e6cff565dcfa43b6a7b9e8921b096cdd1d00b"),
    "reference": (7009, "625b200de1d7cc1fb61d725e9ea067d4877291fc89518520b36e2e15760e675d"),
    "model_artifact": (4769, "3e78daa79e400aae2902cba2de59b614be7e081a0c7ec22fafa51ab6679e3481"),
}
SPECS = (("uniform", None), ("context_counts", None),
         ("ridge", 0.01), ("ridge", 0.1), ("ridge", 1.0))
_SOURCE_CACHE = {}


class ExportError(ValueError):
    pass


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError, OverflowError) as exc:
        raise ExportError("canonical finite JSON required") from exc


def sha256(body):
    return hashlib.sha256(body).hexdigest()


def _json(body, limit):
    if type(body) is not bytes or not body or len(body) > limit:
        raise ExportError("bounded nonempty bytes required")
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ExportError("duplicate JSON key")
            result[key] = value
        return result
    try:
        value = json.loads(body, object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ExportError("nonfinite JSON")))
        canonical(value)
        return value
    except (UnicodeError, ValueError, OverflowError) as exc:
        raise ExportError("invalid finite JSON") from exc


def _source_body(path):
    """Reuse a checked immutable body; invalidate on any observed file identity change."""
    path = Path(path)
    def identity():
        s = path.lstat()
        if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_size > MAX_PROGRAM_BYTES:
            raise ExportError("ordinary bounded single-link source required")
        return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    before = identity()
    cached = _SOURCE_CACHE.get(str(path))
    if cached is not None and cached[0] == before:
        return cached[1]
    body = path.read_bytes()
    if identity() != before or len(body) != before[4]:
        raise ExportError("source changed during identity read")
    _SOURCE_CACHE[str(path)] = (before, body)
    return body


def dependencies():
    """Import only the exact three accepted source bodies, without bytecode cache."""
    directory = Path(__file__).resolve().parent / "accepted"
    modules = []
    for name, (size, digest) in SOURCE_PINS.items():
        path = directory / (name + ".py")
        if path.is_symlink() or not path.is_file():
            raise ExportError("accepted dependency must be an ordinary source file")
        body = _source_body(path)
        if len(body) != size or sha256(body) != digest:
            raise ExportError("accepted dependency identity changed")
        existing = sys.modules.get(name)
        if existing is not None:
            if getattr(existing, "__file__", None) != str(path):
                raise ExportError("foreign module would replace accepted dependency")
            module = existing
        else:
            module = types.ModuleType(name)
            module.__file__ = str(path)
            sys.modules[name] = module
            try:
                exec(compile(body, str(path), "exec"), module.__dict__)
            except BaseException:
                sys.modules.pop(name, None)
                raise
        modules.append(module)
    return tuple(modules)


def producer_closure():
    dependencies()
    source = _source_body(Path(__file__))
    if len(source) > MAX_PROGRAM_BYTES:
        raise ExportError("producer source bound")
    return {"profile": PROFILE, "producer_sha256": sha256(source),
            "accepted_sources": {name + ".py": {"bytes": size, "sha256": digest}
                                 for name, (size, digest) in SOURCE_PINS.items()},
            "central_contract_sha256": CONTRACT_SHA256}


def program_manifest(program_files):
    """Bind the existing flat <=1MiB prediction-program profile, without running it."""
    if type(program_files) is not dict or not program_files:
        raise ExportError("nonempty flat programme roster required")
    members, total = [], 0
    for name in program_files:
        if type(name) is not str or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.py", name) is None:
            raise ExportError("flat Python programme filenames only")
    for name, body in sorted(program_files.items()):
        if type(body) is not bytes or not body or len(body) > MAX_PROGRAM_BYTES:
            raise ExportError("programme member bytes")
        total += len(body)
        if total > MAX_PROGRAM_BYTES:
            raise ExportError("complete programme exceeds fixed 1MiB profile")
        try:
            ast.parse(body.decode("utf-8"), filename=name)
        except (UnicodeError, SyntaxError, ValueError) as exc:
            raise ExportError("valid UTF8 Python programme required") from exc
        members.append({"name": name, "bytes": len(body), "sha256": sha256(body)})
    return {"members": members, "bytes": total, "sha256": sha256(canonical(members))}


def _key(secret):
    if type(secret) is not bytes or len(secret) < 32:
        raise ExportError("curator-only signing key requires at least32 bytes")
    return secret


def _sign(payload, secret):
    body = canonical(payload)
    envelope = canonical({"payload": payload,
                          "hmac_sha256": hmac.new(_key(secret), body, hashlib.sha256).hexdigest()})
    if len(envelope) > MAX_PRIVATE_RECEIPT_BYTES:
        raise ExportError("private provenance receipt bound")
    return envelope


def _unsign(body, secret):
    envelope = _json(body, MAX_PRIVATE_RECEIPT_BYTES)
    if type(envelope) is not dict or set(envelope) != {"payload", "hmac_sha256"}:
        raise ExportError("exact signed-envelope fields")
    signature = envelope["hmac_sha256"]
    if type(signature) is not str or re.fullmatch(r"[0-9a-f]{64}", signature) is None:
        raise ExportError("signature form")
    expected = hmac.new(_key(secret), canonical(envelope["payload"]), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ExportError("private provenance authentication failed")
    return envelope["payload"]


def decode_training_request(body):
    consumer, _, _ = dependencies()
    request = _json(body, MAX_REQUEST_BYTES)
    if type(request) is not dict or set(request) != {"schema", "profile", "training"}:
        raise ExportError("exact anonymous TRAIN request; no held or identity fields")
    if request["schema"] != "hybrid-train-only-request-v1" or request["profile"] != PROFILE:
        raise ExportError("fixed training profile required")
    rows = request["training"]
    if type(rows) is not list or not 1 <= len(rows) <= consumer.MAIN_ELIGIBLE:
        raise ExportError("complete bounded TRAIN rows")
    groups, episodes, previous_episode = set(), {}, 0
    for row in rows:
        if type(row) is not dict or set(row) != {"episode", "training_session_group", "observation", "action"}:
            raise ExportError("exact anonymous training row fields")
        episode, group, action = row["episode"], row["training_session_group"], row["action"]
        if type(episode) is not int or episode < 1 or type(group) is not int or group not in (1, 2, 3):
            raise ExportError("anonymous episode and three training groups only")
        if type(action) is not int or action not in (1, 2, 3, 4):
            raise ExportError("four-action TRAIN label required")
        try:
            consumer.validate_observation(row["observation"])
        except (ValueError, TypeError, OverflowError) as exc:
            raise ExportError("invalid target-free training observation") from exc
        if episode != previous_episode:
            if episode != previous_episode + 1:
                raise ExportError("contiguous complete anonymous episode order")
            episodes[episode] = []
            previous_episode = episode
        episodes[episode].append(row)
        groups.add(group)
    if groups != {1, 2, 3}:
        raise ExportError("exactly three outer-training sessions required")
    for episode in episodes.values():
        if len({r["training_session_group"] for r in episode}) != 1:
            raise ExportError("one session per training episode")
        if episode[-1]["action"] not in (3, 4) or any(r["action"] in (3, 4) for r in episode[:-1]):
            raise ExportError("complete training terminal chronology")
        if len({r["observation"]["nB"] for r in episode}) != 1:
            raise ExportError("constant blocked cue in training episode")
        cursor, clock, switched = None, 0, False
        for row in episode:
            x = row["observation"]
            changed = cursor is not None and x["gL"] != cursor
            if changed:
                switched = True
            clock = 0 if cursor is None or changed else clock + 1
            if x["t"] != clock or x["first_visit"] != (not switched):
                raise ExportError("training causal clock/visit convention changed")
            cursor = x["gL"]
    return rows


def _prepare_common(decisions, subject, held_session, program_files, secret, *,
                    expected_decisions, expected_trials, evidence_kind):
    consumer, _, _ = dependencies()
    manifest = program_manifest(program_files)
    consumer.validate_decisions(decisions, expected_eligible=expected_decisions, expected_trials=expected_trials)
    train, held = consumer.outer_fold(decisions, subject, held_session)
    # Never pass held observations, identities, labels, lengths or scores below.
    projected = consumer.training_view(train)
    request = canonical({"schema": "hybrid-train-only-request-v1", "profile": PROFILE, "training": projected})
    decode_training_request(request)
    private = {"schema": "hybrid-private-training-preparation-v1", "task_id": TASK_ID,
               "profile": PROFILE, "contract_sha256": CONTRACT_SHA256,
               "evidence_kind": evidence_kind, "subject_private": subject,
               "held_session_private": held_session,
               "training_sessions_private": sorted({d.session for d in train}),
               "training_row_ids_sha256": sha256(canonical([d.source_row for d in train])),
               "training_projection_sha256": sha256(canonical(projected)),
               "training_decisions": len(train), "training_trials": len({(d.session, d.trial) for d in train}),
               "request_sha256": sha256(request), "request_bytes": len(request),
               "program": manifest, "producer_closure": producer_closure(),
               "source_case": {"bytes": consumer.MAIN_CASE_BYTES, "sha256": consumer.MAIN_CASE_SHA256}
               if evidence_kind == "authenticated_case_map" else None}
    return request, _sign(private, secret)


def _prepare_from_decisions(decisions, subject, held_session, program_files, secret, *,
                            expected_decisions, expected_trials,
                            evidence_kind="invented_engineering_fixture"):
    """Private invented-control path; cannot claim authenticated source ingestion."""
    if evidence_kind != "invented_engineering_fixture":
        raise ExportError("direct supplied decisions cannot assert authentic case provenance")
    return _prepare_common(decisions, subject, held_session, program_files, secret,
                           expected_decisions=expected_decisions, expected_trials=expected_trials,
                           evidence_kind=evidence_kind)


def prepare_from_case_file(case_path, subject, held_session, program_files, secret):
    """Future trusted preparation; authentic full-case read requires separate selection.

    This authenticates the existing full source and exact exclusions through the
    accepted reader. It performs no scientific fit. Not invoked in source tests.
    """
    consumer, _, _ = dependencies()
    program_manifest(program_files)
    _key(secret)
    decisions = consumer.load_accepted_private_cases(case_path)
    return _prepare_common(decisions, subject, held_session, program_files, secret,
                           expected_decisions=consumer.MAIN_ELIGIBLE,
                           expected_trials=consumer.MAIN_TRIALS, evidence_kind="authenticated_case_map")


def _check_preparation(request_body, preparation_body, program_files, secret, *, require_authentic):
    consumer, _, _ = dependencies()
    rows = decode_training_request(request_body)
    prepared = _unsign(preparation_body, secret)
    fields = {"schema", "task_id", "profile", "contract_sha256", "evidence_kind", "subject_private",
              "held_session_private", "training_sessions_private", "training_row_ids_sha256",
              "training_projection_sha256", "training_decisions", "training_trials", "request_sha256",
              "request_bytes", "program", "producer_closure", "source_case"}
    if type(prepared) is not dict or set(prepared) != fields:
        raise ExportError("exact private preparation schema")
    if (prepared["schema"], prepared["task_id"], prepared["profile"], prepared["contract_sha256"]) != (
            "hybrid-private-training-preparation-v1", TASK_ID, PROFILE, CONTRACT_SHA256):
        raise ExportError("preparation task/profile binding")
    held = prepared["held_session_private"]
    if type(prepared["subject_private"]) is not str or type(held) is not int or (prepared["subject_private"], held) not in consumer.GROUPS:
        raise ExportError("private canonical outer fold")
    train_sessions = prepared["training_sessions_private"]
    if type(train_sessions) is not list or any(type(s) is not int for s in train_sessions) or train_sessions != sorted({1, 2, 3, 4} - {held}):
        raise ExportError("wrong three outer-training sessions")
    evidence = prepared["evidence_kind"]
    if evidence not in ("authenticated_case_map", "invented_engineering_fixture"):
        raise ExportError("unknown evidence kind")
    expected_case = {"bytes": consumer.MAIN_CASE_BYTES, "sha256": consumer.MAIN_CASE_SHA256}
    if prepared["source_case"] != (expected_case if evidence == "authenticated_case_map" else None):
        raise ExportError("source case identity")
    if require_authentic and evidence != "authenticated_case_map":
        raise ExportError("invented controls cannot authorize authentic export")
    checks = ((prepared["request_sha256"], sha256(request_body)),
              (prepared["request_bytes"], len(request_body)),
              (prepared["training_projection_sha256"], sha256(canonical(rows))),
              (prepared["training_decisions"], len(rows)),
              (prepared["training_trials"], len({r["episode"] for r in rows})),
              (prepared["program"], program_manifest(program_files)),
              (prepared["producer_closure"], producer_closure()))
    if any(left != right for left, right in checks):
        raise ExportError("request, source, split or programme provenance changed")
    if re.fullmatch(r"[0-9a-f]{64}", prepared["training_row_ids_sha256"]) is None:
        raise ExportError("private training identity digest")
    return prepared


def _selection(trace):
    if type(trace) is not dict or set(trace) != {"selection", "ledger", "winner", "all_outer_test_inputs_unavailable_to_selector"}:
        raise ExportError("exact private selection trace")
    if trace["selection"] != "train-only inner held-session NLL" or trace["all_outer_test_inputs_unavailable_to_selector"] is not True:
        raise ExportError("TRAIN-only selection declaration")
    ledger = trace["ledger"]
    if type(ledger) is not list or len(ledger) != len(SPECS):
        raise ExportError("complete fixed-family selection ledger")
    for item, (family, penalty) in zip(ledger, SPECS):
        if type(item) is not dict or set(item) != {"family", "penalty", "inner_session_losses", "mean"}:
            raise ExportError("exact selection candidate fields")
        if (item["family"], item["penalty"]) != (family, penalty) or type(item["penalty"]) is not type(penalty):
            raise ExportError("fixed candidate family/penalty order")
        losses = item["inner_session_losses"]
        if type(losses) is not list or len(losses) != 3 or any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in losses):
            raise ExportError("all three finite inner held-session losses")
        if type(item["mean"]) not in (int, float) or not math.isfinite(item["mean"]) or item["mean"] != math.fsum(losses) / 3:
            raise ExportError("selection must equally weight all three inner sessions")
    winner = min(range(len(ledger)), key=lambda i: (ledger[i]["mean"], i))
    if trace["winner"] != ledger[winner]:
        raise ExportError("selected model differs from locked inner-fold rule")
    return trace["winner"]


def train_anonymous(request_body):
    """Concrete fixed-profile producer: only three anonymous TRAIN sessions enter.

    A future authentic invocation runs the unchanged accepted reference selector,
    including its fixed ridge fits. Invented controls replace only ridge fitting;
    no authentic fit or NumPy invocation is required for source verification.
    """
    consumer, reference, artifact = dependencies()
    rows = decode_training_request(request_body)
    train = tuple(consumer.Decision(i + 1, "anonymous", row["training_session_group"], row["episode"],
                                   consumer.validate_observation(row["observation"]), row["action"])
                  for i, row in enumerate(rows))
    model, trace = reference.select_reference(train)
    winner = _selection(trace)
    value = artifact.from_model(model)
    if value["kind"] != winner["family"]:
        raise ExportError("selected family and exported artifact disagree")
    body = artifact.encode_artifact(value)
    artifact.decode_artifact(body)
    # A finite parameter array alone does not guarantee finite valid predictions.
    for row in rows:
        try:
            consumer.probability_vector(artifact.predict_artifact(value, row["observation"]))
        except (ValueError, TypeError, ArithmeticError) as exc:
            raise ExportError("invalid exported probabilities on TRAIN observations") from exc
    return {"artifact": value, "selection": trace}


def train_and_seal(request_body, preparation_body, program_files, secret):
    """Trusted host operation; never forward the signing key or receipt to producer."""
    _, _, artifact = dependencies()
    prepared = _check_preparation(request_body, preparation_body, program_files, secret, require_authentic=False)
    # The producer's sole argument is serialized anonymous TRAIN data.
    result = train_anonymous(request_body)
    if type(result) is not dict or set(result) != {"artifact", "selection"}:
        raise ExportError("fixed producer result schema")
    winner = _selection(result["selection"])
    value = artifact.validate_artifact(result["artifact"])
    if value["kind"] != winner["family"]:
        raise ExportError("selection/export family mismatch")
    body = artifact.encode_artifact(value)
    provenance = {"schema": "hybrid-private-training-export-v1", "task_id": TASK_ID, "profile": PROFILE,
                  "preparation_sha256": sha256(preparation_body), "request_sha256": sha256(request_body),
                  "artifact_sha256": sha256(body), "artifact_bytes": len(body),
                  "program_sha256": prepared["program"]["sha256"],
                  "producer_closure": prepared["producer_closure"], "selection": result["selection"],
                  "evidence_kind": prepared["evidence_kind"], "inner_training_session_groups": [1, 2, 3]}
    return body, _sign(provenance, secret)


def verify_export(artifact_body, provenance_body, request_body, preparation_body,
                  program_files, secret, *, require_authentic=True):
    """Verify the exact curator-approved binding without a fit or held-data access.

    This authenticates trusted-host provenance, not arbitrary external code, source
    cleanliness, absent pretraining contamination or a model's scientific quality.
    """
    consumer, _, artifact = dependencies()
    prepared = _check_preparation(request_body, preparation_body, program_files, secret,
                                  require_authentic=require_authentic)
    value = artifact.decode_artifact(artifact_body)
    provenance = _unsign(provenance_body, secret)
    fields = {"schema", "task_id", "profile", "preparation_sha256", "request_sha256", "artifact_sha256",
              "artifact_bytes", "program_sha256", "producer_closure", "selection", "evidence_kind",
              "inner_training_session_groups"}
    if type(provenance) is not dict or set(provenance) != fields:
        raise ExportError("exact private export provenance")
    expected = {"schema": "hybrid-private-training-export-v1", "task_id": TASK_ID, "profile": PROFILE,
                "preparation_sha256": sha256(preparation_body), "request_sha256": sha256(request_body),
                "artifact_sha256": sha256(artifact_body), "artifact_bytes": len(artifact_body),
                "program_sha256": prepared["program"]["sha256"], "producer_closure": prepared["producer_closure"],
                "evidence_kind": prepared["evidence_kind"], "inner_training_session_groups": [1, 2, 3]}
    if any(provenance[key] != expected[key] for key in expected):
        raise ExportError("export artifact/source/split/programme binding mismatch")
    winner = _selection(provenance["selection"])
    if value["kind"] != winner["family"]:
        raise ExportError("export not the selected model family")
    for row in decode_training_request(request_body):
        try:
            consumer.probability_vector(artifact.predict_artifact(value, row["observation"]))
        except (ValueError, TypeError, ArithmeticError) as exc:
            raise ExportError("exported artifact yields invalid probabilities") from exc
    return {"verified": True, "profile": PROFILE, "artifact_sha256": sha256(artifact_body),
            "program_sha256": prepared["program"]["sha256"], "evidence_kind": prepared["evidence_kind"],
            "scientific_qualification": False, "arbitrary_external_training_attested": False}


def main():
    if sys.argv[1:] != ["produce"]:
        raise ExportError("usage: train_export.py produce < anonymous_train_request.json")
    request = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    result = train_anonymous(request)
    # This whole response is PRIVATE to the curator. Only its separately encoded
    # artifact is admitted to the unchanged prediction transport.
    output = canonical(result) + b"\n"
    if len(output) > 2 * MAX_ARTIFACT_BYTES:
        raise ExportError("bounded producer response")
    sys.stdout.buffer.write(output)


if __name__ == "__main__":
    main()
