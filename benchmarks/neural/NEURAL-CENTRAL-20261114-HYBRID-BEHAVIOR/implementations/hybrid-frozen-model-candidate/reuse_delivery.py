"""Repackage already accepted reference artifacts, without any scientific fit.

An explicit historical verifier replaces only export-provenance verification.
The unchanged run_authentic/BoundFamily/causal engine consumes this variant.
Historical receipts name the earlier accepted full reference workflow and never
claim that train_anonymous/train_and_seal ran. The existing preparation receipt
certifies only input preparation and compatible selector source, not execution.
No authentic file is read on import or in source controls.
"""
import os
import stat
from pathlib import Path
import protected_delivery as delivery


REUSE_SCHEMA = "hybrid-historical-reference-reuse-v1"
REFERENCE_WORKFLOW_PIN = (6063, "d575b522c24daf4c34f2ca22f954b48c245364ef78336103c8f4374741cbbc0c")
PROGRAMME = ("participant_entry.py", "model_artifact.py", "reference.py", "consumer.py")

# Candidate-only policy; the reference programme and its old bounds are unchanged.
CANDIDATE_PROGRAM_CAP = 192 * 1024
CANDIDATE_MANIFEST_CAP = 8192
CANDIDATE_ARM = "candidate_frozen_models"


def _candidate_roster(root):
    """Read at most five names from an external directory, closing on refusal."""
    names = set()
    with os.scandir(root) as entries:
        for index, entry in enumerate(entries):
            delivery.need(index < len(PROGRAMME), "candidate directory exceeds four entries")
            names.add(entry.name)
    delivery.need(names == set(PROGRAMME), "exact candidate directory roster")


class FrozenCandidate:
    """Capture untrusted programme bytes as data; never import or execute them."""
    def __init__(self, sources, descriptor):
        self.sources = sources
        delivery.need(type(descriptor) is dict and set(descriptor) == {"directory", "manifest"},
                      "closed candidate programme descriptor")
        self.root = delivery.ordinary(descriptor["directory"])
        info = self.root.lstat()
        delivery.need(stat.S_ISDIR(info.st_mode), "ordinary candidate directory")
        self.directory_identity = delivery.stamp(info)
        declared = descriptor["manifest"]
        delivery.need(type(declared) is dict and set(declared) == {"path", "bytes", "sha256"} and
                      type(declared["bytes"]) is int and 0 < declared["bytes"] <= CANDIDATE_MANIFEST_CAP and
                      type(declared["sha256"]) is str and len(declared["sha256"]) == 64 and
                      all(c in "0123456789abcdef" for c in declared["sha256"]), "exact candidate manifest pin")
        snap = delivery.Snapshot(declared["path"], (declared["bytes"], declared["sha256"]), CANDIDATE_MANIFEST_CAP)
        self.snapshots = [snap]
        value = sources.export._json(snap.body, CANDIDATE_MANIFEST_CAP)
        delivery.need(type(value) is dict and set(value) == {"schema", "files"} and
                      value["schema"] == "hybrid-frozen-model-candidate-program-v1", "candidate manifest schema")
        rows = value["files"]
        delivery.need(type(rows) is list and len(rows) == 4, "all four candidate programme files")
        roster, total = {}, 0
        for row in rows:
            delivery.need(type(row) is dict and set(row) == {"name", "bytes", "sha256"} and
                          type(row["name"]) is str and row["name"] in PROGRAMME and row["name"] not in roster and
                          type(row["bytes"]) is int and 0 < row["bytes"] <= CANDIDATE_PROGRAM_CAP and
                          type(row["sha256"]) is str and len(row["sha256"]) == 64 and
                          all(c in "0123456789abcdef" for c in row["sha256"]), "closed distinct candidate source pin")
            total += row["bytes"]
            roster[row["name"]] = row
        delivery.need(set(roster) == set(PROGRAMME) and total <= CANDIDATE_PROGRAM_CAP,
                      "complete candidate programme fits192KiB host-read policy")
        _candidate_roster(self.root)
        self.programme = {}
        for name, row in sorted(roster.items()):
            member = delivery.Snapshot(self.root / name, (row["bytes"], row["sha256"]), CANDIDATE_PROGRAM_CAP)
            self.snapshots.append(member)
            self.programme[name] = member.body
        programme = sources.export.program_manifest(self.programme)
        self.identity = {"schema": "hybrid-frozen-model-candidate-identity-v1",
                         "manifest": {"bytes": snap.pin[0], "sha256": snap.pin[1]}, "programme": programme}
        self.read_bytes = len(snap.body) + total
        self.check()

    def check(self):
        self.sources.check()
        delivery.need(delivery.stamp(delivery.ordinary(self.root).lstat()) == self.directory_identity,
                      "candidate source directory changed")
        _candidate_roster(self.root)
        for snap in self.snapshots:
            snap.check()
        delivery.need(self.sources.export.program_manifest(self.programme) == self.identity["programme"],
                      "captured candidate bytes changed")


def admit_candidate(sources, plan):
    """Unknown/ambiguous arms fail before dispatch; omitted arm is the old reference."""
    arm = plan.get("evaluation_arm", "reference_replay")
    delivery.need(type(arm) is str and arm in {"reference_replay", CANDIDATE_ARM}, "known evaluation arm")
    if arm == "reference_replay":
        delivery.need(plan.get("candidate_program") is None, "reference arm cannot accept candidate input")
        return None
    delivery.need(plan.get("candidate_program") is not None, "candidate arm needs frozen programme")
    return FrozenCandidate(sources, plan["candidate_program"])


def prepare_candidate_reused(sources, candidate, case_path, reference_path, output,
                             receipt_path, secret, *, artifact_locations=None):
    """Same old models/TRAIN provenance; new inference code is bound separately."""
    delivery.need(type(candidate) is FrozenCandidate and candidate.sources is sources,
                  "admitted candidate from this exact source closure")
    candidate.check()
    reference = delivery.Snapshot(reference_path, delivery.REFERENCE_PIN, 2 * 1048576)
    accepted = sources.export._json(reference.body, 2 * 1048576)
    decisions = sources.consumer.load_accepted_private_cases(case_path)
    result = _stage_reused(sources, decisions, accepted, candidate.programme, output, receipt_path,
                           secret, reference.pin, artifact_locations=artifact_locations)
    candidate.check()
    reference.check()
    sources.check()
    return result


class HistoricalExportVerifier:
    """Explicit reviewed origin variant; never fabricate a new-producer receipt."""
    def __init__(self, base, artifact):
        self.base, self.artifact = base, artifact

    def __getattr__(self, name):
        return getattr(self.base, name)

    def verify_export(self, artifact_body, provenance_body, request_body, preparation_body,
                      program_files, secret, *, require_authentic=True):
        ex = self.base
        prepared = ex._check_preparation(request_body, preparation_body, program_files, secret,
                                         require_authentic=require_authentic)
        value = self.artifact.decode_artifact(artifact_body)
        provenance = ex._unsign(provenance_body, secret)
        fields = {"schema", "task_id", "origin", "new_fits", "preparation_sha256", "request_sha256",
            "artifact_sha256", "artifact_bytes", "program_sha256", "selection", "evidence_kind",
            "historical_reference", "historical_producer", "historical_record_sha256"}
        delivery.need(type(provenance) is dict and set(provenance) == fields,
                      "historical origin schema; new-producer receipt not accepted")
        expected = {"schema": "hybrid-private-historical-export-v1", "task_id": ex.TASK_ID,
            "origin": "previously_accepted_complete_reference_workflow", "new_fits": 0,
            "preparation_sha256": ex.sha256(preparation_body), "request_sha256": ex.sha256(request_body),
            "artifact_sha256": ex.sha256(artifact_body), "artifact_bytes": len(artifact_body),
            "program_sha256": prepared["program"]["sha256"], "evidence_kind": prepared["evidence_kind"],
            "historical_producer": {"bytes": REFERENCE_WORKFLOW_PIN[0], "sha256": REFERENCE_WORKFLOW_PIN[1]}}
        delivery.need(all(provenance[k] == v for k, v in expected.items()) and
                      type(provenance["new_fits"]) is int, "historical artifact/source/split/programme binding")
        if require_authentic:
            delivery.need(provenance["historical_reference"] ==
                {"bytes": delivery.REFERENCE_PIN[0], "sha256": delivery.REFERENCE_PIN[1]},
                "fixed accepted historical reference")
        digest = provenance["historical_record_sha256"]
        delivery.need(type(digest) is str and len(digest) == 64 and
                      all(x in "0123456789abcdef" for x in digest), "complete historical fold record pin")
        winner = ex._selection(provenance["selection"])
        delivery.need(value["kind"] == winner["family"], "historical selected model family")
        consumer, _, _ = ex.dependencies()
        for row in ex.decode_training_request(request_body):
            consumer.probability_vector(self.artifact.predict_artifact(value, row["observation"]))
        return {"verified": True, "origin": expected["origin"], "new_fits": 0,
                "scientific_qualification": False, "arbitrary_external_training_attested": False}


LOCATION_SCHEMA = "hybrid-historical-artifact-locations-v1"
MAX_LOCATIONS = 131072


def location_map(sources, descriptor, reference_pin):
    """Trusted operator input, never contestant input; no model body read here."""
    if descriptor is None:
        return None, None
    delivery.need(type(descriptor) is dict and set(descriptor) == {"path", "bytes", "sha256"},
                  "exact external location-map descriptor")
    snapshot = delivery.Snapshot(descriptor["path"], (descriptor["bytes"], descriptor["sha256"]), MAX_LOCATIONS)
    value = sources.export._json(snapshot.body, MAX_LOCATIONS)
    delivery.need(type(value) is dict and set(value) == {"schema", "reference_result", "folds"} and
                  value["schema"] == LOCATION_SCHEMA and
                  value["reference_result"] == {"bytes": reference_pin[0], "sha256": reference_pin[1]} and
                  type(value["reference_result"].get("bytes")) is int,
                  "location map binds exact unchanged historical reference")
    delivery.need(type(value["folds"]) is list and len(value["folds"]) == 80, "all80 location records")
    locations = {}
    for row in value["folds"]:
        delivery.need(type(row) is dict and set(row) == {"historical_record_sha256", "location"},
                      "closed location row")
        key, pin = row["historical_record_sha256"], row["location"]
        delivery.need(type(key) is str and len(key) == 64 and all(x in "0123456789abcdef" for x in key)
                      and key not in locations, "distinct historical record identities")
        delivery.need(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"} and
                      type(pin["bytes"]) is int and 0 < pin["bytes"] <= 65536 and
                      type(pin["sha256"]) is str and len(pin["sha256"]) == 64 and
                      all(x in "0123456789abcdef" for x in pin["sha256"]) and
                      type(pin["path"]) is str and 0 < len(pin["path"]) <= 4096 and "\x00" not in pin["path"],
                      "bounded exact artifact location pin")
        path = delivery.ordinary(pin["path"])
        delivery.need(str(path) == pin["path"], "canonical absolute artifact location")
        locations[key] = pin
    return locations, snapshot


def check_record(sources, record, decisions, programme, secret, counts, authentic):
    """Join the complete historical fold to the exact current TRAIN projection."""
    ex, c = sources.export, sources.consumer
    key = (record["subject_private"], record["held_session_private"])
    delivery.need(key in c.GROUPS and record["training_only"] is True and
                  record["outer_test_available_to_selector"] is False, "historical TRAIN-only fold")
    request, preparation = ex._prepare_common(decisions, *key, programme, secret,
        expected_decisions=counts[0], expected_trials=counts[1],
        evidence_kind="authenticated_case_map" if authentic else "invented_engineering_fixture")
    prepared = ex._unsign(preparation, secret)
    _, held = c.outer_fold(decisions, *key)
    delivery.need(type(record["training_decisions"]) is int and
                  record["training_decisions"] == prepared["training_decisions"] and
                  type(record["held_decisions_private"]) is int and
                  record["held_decisions_private"] == len(held) and
                  record["training_projection_sha256"] == prepared["training_projection_sha256"],
                  "historical complete TRAIN projection and held extent")
    ex._selection(record["selection"])
    return key, request, preparation, prepared


def _stage_reused(sources, decisions, accepted, programme, output, receipt_path, secret,
                  reference_pin, *, fixture_counts=None, artifact_locations=None):
    """Private fixture hook cannot assert authentic provenance."""
    sources.check()
    ex, c = sources.export, sources.consumer
    authentic = fixture_counts is None
    counts = (c.MAIN_ELIGIBLE, c.MAIN_TRIALS) if authentic else fixture_counts
    c.validate_decisions(decisions, expected_eligible=counts[0], expected_trials=counts[1])
    delivery.need(accepted["schema"] == "hybrid-complete-train-only-reference-v1" and
                  type(accepted["complete_outer_folds"]) is int and accepted["complete_outer_folds"] == 80 and
                  accepted["inner_ridge_fits"] == 720 and accepted["final_ridge_fits"] == 80 and
                  accepted["authentic_counts"] == {"decisions": counts[0], "trials": counts[1]},
                  "exact historical complete reference population")
    delivery.need(not authentic or reference_pin == delivery.REFERENCE_PIN, "fixed accepted reference result")
    records = accepted["artifact_manifest_private"]
    delivery.need(type(records) is list and len(records) == 80, "all80 historical exports")
    locations, location_snapshot = location_map(sources, artifact_locations, reference_pin)
    if locations is not None:
        delivery.need(set(locations) == {ex.sha256(ex.canonical(r)) for r in records},
                      "location map equals complete historical80 record support")
        for record in records:
            original_pin = record["artifacts"]["family_train_selected"]
            located = locations[ex.sha256(ex.canonical(record))]
            delivery.need(located["bytes"] == original_pin["bytes"] and located["sha256"] == original_pin["sha256"],
                          "relocation cannot change any historical artifact identity")
    manifest = ex.program_manifest(programme)
    delivery.need(set(programme) == set(PROGRAMME), "unchanged four-file reference replay programme")
    root, receipt_path = delivery.ordinary(output), delivery.ordinary(receipt_path)
    delivery.need(root not in receipt_path.parents and receipt_path != root, "reuse receipt remains outside mounted delivery")
    root.mkdir(mode=0o700)
    for name in ("program", "models", "private"):
        (root / name).mkdir(mode=0o700)
    used = 0
    def write(folder, name, body, cap):
        nonlocal used
        delivery.need(used + len(body) <= delivery.MAX_DELIVERY, "complete reuse delivery admission")
        used += len(body)
        pin = delivery._write_new(root / folder / name, body, cap)
        pin["relative_path"] = folder + "/" + name
        return pin
    for name, body in programme.items():
        write("program", name, body, 1048576)
    bundles, evidence, seen, original_snapshots = [], [], set(), []
    for record in records:
        sources.check()
        key, request, preparation, prepared = check_record(sources, record, decisions, programme,
                                                          secret, counts, authentic)
        delivery.need(key not in seen, "one historical export for each distinct fold")
        seen.add(key)
        pin = record["artifacts"]["family_train_selected"]
        delivery.need(set(pin) == {"path", "bytes", "sha256"}, "exact historical artifact pin")
        selected_location = pin if locations is None else locations[ex.sha256(ex.canonical(record))]
        original = delivery.Snapshot(selected_location["path"], (pin["bytes"], pin["sha256"]), 65536)
        original_snapshots.append(original)
        value = sources.artifact.decode_artifact(original.body)
        winner = ex._selection(record["selection"])
        delivery.need(value["kind"] == winner["family"], "historical selected family")
        historical = {"schema": "hybrid-private-historical-export-v1", "task_id": ex.TASK_ID,
            "origin": "previously_accepted_complete_reference_workflow", "new_fits": 0,
            "preparation_sha256": ex.sha256(preparation),
            "request_sha256": ex.sha256(request), "artifact_sha256": original.pin[1],
            "artifact_bytes": original.pin[0], "program_sha256": prepared["program"]["sha256"],
            "selection": record["selection"], "evidence_kind": prepared["evidence_kind"],
            "historical_reference": {"bytes": reference_pin[0], "sha256": reference_pin[1]},
            "historical_producer": {"bytes": REFERENCE_WORKFLOW_PIN[0], "sha256": REFERENCE_WORKFLOW_PIN[1]},
            "historical_record_sha256": ex.sha256(ex.canonical(record))}
        provenance = ex._sign(historical, secret)
        ex.verify_export(original.body, provenance, request, preparation, programme, secret,
                         require_authentic=authentic)
        opaque = os.urandom(16).hex()
        bundle = {"request": write("private", opaque + ".request.json", request, delivery.MAX_REQUEST),
                  "preparation": write("private", opaque + ".preparation.json", preparation, delivery.MAX_MANIFEST),
                  "provenance": write("private", opaque + ".provenance.json", provenance, delivery.MAX_MANIFEST),
                  "artifact": write("models", opaque + ".json", original.body, 65536)}
        bundles.append(bundle)
        evidence.append({"subject_private": key[0], "held_session_private": key[1],
            "historical_artifact": pin, "selected_artifact_location": selected_location, "delivery_artifact": bundle["artifact"],
            "historical_record_sha256": ex.sha256(ex.canonical(record)),
            "training_projection_sha256": prepared["training_projection_sha256"],
            "training_row_ids_sha256": prepared["training_row_ids_sha256"],
            "preparation_sha256": ex.sha256(preparation), "historical_provenance_sha256": ex.sha256(provenance),
            "selection_sha256": ex.sha256(ex.canonical(record["selection"]))})
    delivery.need(seen == c.GROUPS, "complete20x4 reuse without alias or omission")
    signed = ex._sign({"schema": delivery.SCHEMA, "source_closure": sources.closure,
        "evidence_kind": "authenticated_case_map" if authentic else "invented_engineering_fixture",
        "case_identity": {"bytes": c.MAIN_CASE_BYTES, "sha256": c.MAIN_CASE_SHA256} if authentic else None,
        "counts": {"decisions": counts[0], "trials": counts[1], "folds": 80},
        "programme": manifest, "bundles": bundles}, secret)
    delivery.need(used + len(signed) <= delivery.MAX_DELIVERY, "manifest inclusive admission")
    manifest_pin = delivery._write_new(root / "DELIVERY.private.json", signed, delivery.MAX_MANIFEST)
    for original in original_snapshots:
        original.check()
    if location_snapshot is not None:
        location_snapshot.check()
    sources.check()
    evidence_payload = {"schema": REUSE_SCHEMA, "task_id": ex.TASK_ID,
        "origin": "previously_accepted_complete_reference_workflow",
        "new_fits": 0, "new_train_anonymous_or_train_and_seal_called": False,
        "origin_verifier": "explicit historical-export variant; no new-producer execution receipt",
        "evidence_kind": "authenticated_case_map" if authentic else "invented_engineering_fixture",
        "reference_result": {"bytes": reference_pin[0], "sha256": reference_pin[1]},
        "historical_producer_source": {"bytes": REFERENCE_WORKFLOW_PIN[0], "sha256": REFERENCE_WORKFLOW_PIN[1]},
        "source_closure": sources.closure, "delivery_manifest": manifest_pin,
        "complete_folds": 80, "folds": evidence,
        "artifact_locations": artifact_locations}
    reuse_body = ex._sign(evidence_payload, secret)
    reuse_pin = delivery._write_new(receipt_path, reuse_body, delivery.MAX_MANIFEST)
    for name in ("program", "models", "private"):
        (root / name).chmod(0o500)
    return {"manifest": manifest_pin, "reuse": reuse_pin, "new_fits": 0, "reused_folds": 80}


def prepare_reused(sources, case_path, reference_path, output, receipt_path, secret, *, artifact_locations=None):
    """Future authentic no-refit preparation; never invoked by source tests."""
    sources.check()
    reference = delivery.Snapshot(reference_path, delivery.REFERENCE_PIN, 2 * 1048576)
    accepted = sources.export._json(reference.body, 2 * 1048576)
    programme = {}
    programme_snapshots = []
    for name in PROGRAMME:
        snap = delivery.Snapshot(sources.runner_root / name)
        programme_snapshots.append(snap)
        programme[name] = snap.body
    decisions = sources.consumer.load_accepted_private_cases(case_path)
    result = _stage_reused(sources, decisions, accepted, programme, output, receipt_path,
                           secret, reference.pin, artifact_locations=artifact_locations)
    reference.check()
    for snap in programme_snapshots:
        snap.check()
    sources.check()
    return result


def require_reuse(sources, receipt_path, pin, manifest_pin, secret, *, artifact_locations=None):
    """Mandatory extra origin check before and after unchanged run_authentic."""
    snapshot = delivery.Snapshot(receipt_path, (pin["bytes"], pin["sha256"]), delivery.MAX_MANIFEST)
    value = sources.export._unsign(snapshot.body, secret)
    delivery.need(value["schema"] == REUSE_SCHEMA and value["origin"] == "previously_accepted_complete_reference_workflow" and
                  value["evidence_kind"] == "authenticated_case_map" and
                  type(value["new_fits"]) is int and value["new_fits"] == 0 and
                  value["new_train_anonymous_or_train_and_seal_called"] is False and
                  value["reference_result"] == {"bytes": delivery.REFERENCE_PIN[0], "sha256": delivery.REFERENCE_PIN[1]} and
                  value["source_closure"] == sources.closure and value["delivery_manifest"] == manifest_pin and
                  value["complete_folds"] == 80 and len(value["folds"]) == 80 and
                  {(x["subject_private"], x["held_session_private"]) for x in value["folds"]} == sources.consumer.GROUPS,
                  "mandatory complete historical reuse provenance")
    delivery.need(value.get("artifact_locations") == artifact_locations, "same selected location-map provenance")
    return snapshot
