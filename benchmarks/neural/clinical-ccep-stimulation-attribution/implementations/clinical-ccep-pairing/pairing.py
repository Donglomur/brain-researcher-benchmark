"""Prospective CCEP whole-block pairing and matched-arm diagnostic consumer.

Normalized envelopes are a new benchmark interface, not a native EEG loader.
All mappings and reports are evaluator-private. Only packet() emits candidate data.
"""
import argparse
import base64
import collections
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import types


def _primary():
    path = (Path(__file__).resolve().parent.parent /
            "clinical-ccep-artifact-grading/score.py")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        st = os.fstat(stream.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size != 14609:
            raise ValueError("primary source identity")
        body = stream.read(14610)
    if hashlib.sha256(body).hexdigest() != "2426ddc5585a113fb839e3b3dd78bf2c684d3f0d5fef2dac0b9af4ab1ebd6f32":
        raise ValueError("primary source identity")
    module = types.ModuleType("fixed_ccep_primary")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


P = _primary()
ALGORITHM = "ccep-hash-ordered-distinct-site-rotation-v1"
NUISANCE = ("montage", "pulse_waveform", "pulse_intensity", "pulse_duration", "pulse_rate",
            "sampling_grid", "reference", "filter", "baseline")
MAX_CELLS = 100000
DECIMAL_TIME = re.compile(r"[+-]?[0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?\Z")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(body):
    return hashlib.sha256(body).hexdigest()


def hash_order(*parts):
    return digest(canonical(parts))


def _admit_output(value):
    # Include the command's exact trailing LF; never shrink a complete result.
    P.require(len(canonical(value)) + 1 <= P.MAX_BYTES, "complete output size exceeds reader ceiling")
    return value


def _policy(policy_path, policy_sha256, control_path, control_sha256):
    P.sha(policy_sha256); P.sha(control_sha256)
    p, ph = P.read_document(policy_path, policy_sha256)
    cases, persons = P.validate_policy(p)
    c, ch = P.read_document(control_path, control_sha256)
    P.keys(c, {"schema", "task_id", "primary_policy_sha256", "algorithm", "source_protocol_sha256",
               "envelope_schema", "arms", "rows"}, "pairing control policy")
    P.require(c["schema"] == "ccep-pairing-policy-v1" and c["task_id"] == P.TASK,
              "control schema/task")
    P.require(c["primary_policy_sha256"] == ph and c["algorithm"] == ALGORITHM,
              "control policy/algorithm identity")
    P.require(c["envelope_schema"] == "ccep-complete-block-v1", "normalized envelope version")
    P.sha(c["source_protocol_sha256"])
    P.require(type(c["arms"]) is list and 2 <= len(c["arms"]) <= 16, "complete arm roster")
    arms = {}
    for arm in c["arms"]:
        P.keys(arm, {"id", "role", "provenance_sha256"}, "arm")
        name = P.token(arm["id"])
        P.require(name not in arms and arm["role"] in ("candidate", "reference"), "arm role/identity")
        P.sha(arm["provenance_sha256"]); arms[name] = arm
    P.require({a["role"] for a in arms.values()} == {"candidate", "reference"}, "matched reference required")
    P.require(type(c["rows"]) is list and len(c["rows"]) == len(cases), "complete control census")
    rows = {}
    for row in c["rows"]:
        P.keys(row, {"case_id", "stimulated_site", "nuisance", "response_sha256",
                     "layout_sha256", "context_sha256"}, "control row")
        name = P.token(row["case_id"]); P.token(row["stimulated_site"])
        P.require(name in cases and name not in rows, "control ID set")
        P.keys(row["nuisance"], set(NUISANCE), "complete nuisance identities")
        for value in row["nuisance"].values(): P.sha(value)
        for key in ("response_sha256", "layout_sha256", "context_sha256"): P.sha(row[key])
        rows[name] = row
    P.require(set(rows) == set(cases), "complete control IDs")
    return p, ph, cases, persons, c, ch, rows, arms


def _groups(cases, rows):
    grouped = {}
    for name, case in cases.items():
        # No responses, labels, targets hash, arm outputs or context values in this key.
        key = {k: case[k] for k in ("patient", "session", "VTC_contact", "repetitions")}
        key.update(nuisance=rows[name]["nuisance"], layout_sha256=rows[name]["layout_sha256"])
        group_id = digest(canonical(key))
        if group_id not in grouped:
            grouped[group_id] = {"id": group_id, **key, "cases": []}
        grouped[group_id]["cases"].append(name)
    output = []
    for group_id in sorted(grouped):
        group = grouped[group_id]; group["cases"].sort()
        counts = collections.Counter(rows[name]["stimulated_site"] for name in group["cases"])
        n = len(group["cases"]); largest = max(counts.values())
        if any(cases[name]["coverage"] != "ready" for name in group["cases"]):
            reason = "unresolved_original_coverage"
        elif n == 1:
            reason = "singleton_stratum"
        elif largest * 2 > n:
            reason = "complete_distinct_site_bijection_impossible"
        else:
            reason = None
        group.update(blocks=n, distinct_sites=len(counts), largest_site_multiplicity=largest,
                     supported=reason is None, unsupported_reason=reason,
                     valid_mapping_count=n if reason is None else 0, invalid_mapping_count=0,
                     unsupported_mapping_count=n if reason is not None else 0)
        output.append(group)
    return output


def _rotation(group, rows, seed):
    sites = {}
    for name in group["cases"]:
        sites.setdefault(rows[name]["stimulated_site"], []).append(name)
    site_order = sorted(sites, key=lambda s: (hash_order(ALGORITHM, seed, group["id"], "site", s), s))
    order = []
    for site in site_order:
        order.extend(sorted(sites[site], key=lambda name: (hash_order(ALGORITHM, seed, group["id"], "case", name), name)))
    n, largest = len(order), group["largest_site_multiplicity"]
    P.require(largest * 2 <= n, "no complete distinct-site rotation")
    shift = largest + int(hash_order(ALGORITHM, seed, group["id"], "shift"), 16) % (n - 2 * largest + 1)
    pairs = [{"recipient": name, "donor": order[(idx + shift) % n]} for idx, name in enumerate(order)]
    P.require(len({x["donor"] for x in pairs}) == n, "whole-stratum bijection")
    P.require(all(x["recipient"] != x["donor"] and
                  rows[x["recipient"]]["stimulated_site"] != rows[x["donor"]]["stimulated_site"]
                  for x in pairs), "distinct-site derangement")
    return pairs


def _mapping(ph, ch, cases, rows):
    groups = _groups(cases, rows)
    transforms, by_signature, seeds = [], {}, []
    for seed in range(20):
        pairs = []
        for group in groups:
            if group["supported"]:
                pairs.extend(_rotation(group, rows, seed))
        pairs.sort(key=lambda x: x["recipient"])
        if not pairs:
            seeds.append({"seed": seed, "candidate_attempts": 0, "status": "unavailable", "transform_id": None})
            continue
        signature = canonical(pairs)
        if signature not in by_signature:
            ident = "T" + digest(signature)
            by_signature[signature] = ident
            transforms.append({"id": ident, "first_seed": seed, "donors": pairs})
            status = "first_admissible"
        else:
            ident, status = by_signature[signature], "duplicate_map"
        seeds.append({"seed": seed, "candidate_attempts": 1, "status": status, "transform_id": ident})
    unsupported = [{"case_id": name, "group": g["id"], "reason": g["unsupported_reason"]}
                   for g in groups if not g["supported"] for name in g["cases"]]
    return {"schema": "ccep-private-pairing-map-v1", "task_id": P.TASK, "algorithm": ALGORITHM,
            "primary_policy_sha256": ph, "control_policy_sha256": ch,
            "full_original_case_count": len(cases), "patient_count": 5, "groups": groups,
            "unsupported_cases": unsupported, "seeds": seeds, "transforms": transforms,
            "actual_distinct_transform_count": len(transforms), "candidate_limit_per_seed": 100,
            "sampling_claim": "prospective hash-ordered rotation family; not uniform over all admissible permutations",
            "biological_replicates_added": 0, "evaluator_private": True,
            "native_source_authenticated": False, "packet_materialization_verified": False}


def maps(policy_path, policy_sha256, control_path, control_sha256):
    _, ph, cases, _, _, ch, rows, _ = _policy(policy_path, policy_sha256, control_path, control_sha256)
    return _admit_output(_mapping(ph, ch, cases, rows))


def _frozen_map(map_path, expected_map_sha256, ph, ch, cases, rows):
    P.sha(expected_map_sha256)
    observed, mh = P.read_document(map_path, expected_map_sha256)
    P.require(observed == _mapping(ph, ch, cases, rows), "exact frozen target-free mapping")
    return observed, mh


def _decoded(text, expected):
    P.require(type(text) is str and len(text) <= P.MAX_BYTES, "bounded base64 component")
    try:
        body = base64.b64decode(text, validate=True)
        P.require(base64.b64encode(body).decode("ascii") == text, "canonical base64")
        P.require(digest(body) == expected, "component exact byte identity")
        value = json.loads(body.decode("utf-8"), object_pairs_hook=P._pairs, parse_constant=P._constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise P.Invalid("normalized component syntax/identity") from error
    return value


def _envelope(path, case, row):
    block, _ = P.read_document(path, case["packet_sha256"])
    P.keys(block, {"schema", "task_id", "case_id", "response_b64", "layout_b64", "context_b64"}, "block")
    P.require(block["schema"] == "ccep-complete-block-v1" and block["task_id"] == P.TASK and
              block["case_id"] == case["case_id"], "normalized block identity")
    response = _decoded(block["response_b64"], row["response_sha256"])
    layout = _decoded(block["layout_b64"], row["layout_sha256"])
    context = _decoded(block["context_b64"], row["context_sha256"])
    P.keys(context, {"recording_location"}, "recipient target-free context")
    P.require(type(context["recording_location"]) is str and 0 < len(context["recording_location"]) <= 1024,
              "recording-location descriptor")
    P.keys(layout, {"relative_times_seconds", "units", "missing", "artifact"}, "native layout")
    times = layout["relative_times_seconds"]
    P.require(type(times) is list and 1 <= len(times) <= MAX_CELLS, "complete native time grid")
    parsed = []
    for text in times:
        P.require(type(text) is str and 0 < len(text) <= 32 and DECIMAL_TIME.fullmatch(text), "exact decimal time string")
        try:
            value = Decimal(text)
        except InvalidOperation as error:
            raise P.Invalid("relative time") from error
        P.require(value.is_finite() and Decimal("0.011") <= value <= Decimal("0.5"), "11-500ms domain")
        parsed.append(value)
    P.require(all(a < b for a, b in zip(parsed, parsed[1:])), "increasing original time grid")
    P.require(type(layout["units"]) is str and 0 < len(layout["units"]) <= 32 and
              all(32 <= ord(x) < 127 for x in layout["units"]), "explicit units")
    reps, samples = case["repetitions"], len(times)
    P.require(reps * samples <= MAX_CELLS, "complete block engineering cell ceiling")
    for matrix in (response, layout["missing"], layout["artifact"]):
        P.require(type(matrix) is list and len(matrix) == reps and
                  all(type(line) is list and len(line) == samples for line in matrix), "complete repetitions/samples")
    for i in range(reps):
        for j in range(samples):
            missing, artifact = layout["missing"][i][j], layout["artifact"][i][j]
            P.require(type(missing) is bool and type(artifact) is bool, "exact masks")
            if missing:
                P.require(response[i][j] is None, "missing cell must remain explicit null")
            else:
                P.number(response[i][j])
    return block


def packet(policy_path, policy_sha256, control_path, control_sha256, map_path, map_sha256,
           transform_id, recipient_id, recipient_packet_path, donor_packet_path):
    P.sha(map_sha256)
    _, ph, cases, _, _, ch, rows, _ = _policy(policy_path, policy_sha256, control_path, control_sha256)
    manifest, _ = _frozen_map(map_path, map_sha256, ph, ch, cases, rows)
    selected = [t for t in manifest["transforms"] if t["id"] == transform_id]
    P.require(len(selected) == 1, "selected distinct transform")
    pair = [x for x in selected[0]["donors"] if x["recipient"] == recipient_id]
    P.require(len(pair) == 1, "recipient must have supported mapping")
    donor_id = pair[0]["donor"]
    recipient = _envelope(recipient_packet_path, cases[recipient_id], rows[recipient_id])
    donor = _envelope(donor_packet_path, cases[donor_id], rows[donor_id])
    P.require(recipient["layout_b64"] == donor["layout_b64"], "identical grid/shape/units/masks")
    return _admit_output({"schema": "ccep-paired-complete-block-v1", "task_id": P.TASK,
            "case_id": recipient_id, "transform_id": transform_id,
            "response_b64": donor["response_b64"], "layout_b64": recipient["layout_b64"],
            "context_b64": recipient["context_b64"]})


def _artifact(artifact, p, ph, ch, mh, cases, arms, manifest):
    P.keys(artifact, {"schema", "task_id", "primary_policy_sha256", "control_policy_sha256",
                      "map_sha256", "class_order", "arms"}, "paired artifact")
    P.require(artifact["schema"] == "ccep-paired-predictions-v1" and artifact["task_id"] == P.TASK,
              "paired artifact schema/task")
    P.require(artifact["primary_policy_sha256"] == ph and artifact["control_policy_sha256"] == ch and
              artifact["map_sha256"] == mh and artifact["class_order"] == list(P.CLASSES), "paired artifact identity")
    P.require(type(artifact["arms"]) is list and len(artifact["arms"]) == len(arms), "every frozen arm")
    known = {t["id"]: t for t in manifest["transforms"]}
    output = {}
    for arm in artifact["arms"]:
        P.keys(arm, {"id", "original", "transforms"}, "arm artifact")
        name = P.token(arm["id"])
        P.require(name in arms and name not in output, "arm IDs")
        original = P.validate_predictions(arm["original"], p, ph, cases)
        P.require(type(arm["transforms"]) is list and len(arm["transforms"]) == len(known), "all distinct transforms")
        transformed = {}
        for t in arm["transforms"]:
            P.keys(t, {"id", "rows"}, "transform artifact")
            ident = P.token(t["id"])
            P.require(ident in known and ident not in transformed, "transform ID set")
            support = {pair["recipient"]: cases[pair["recipient"]] for pair in known[ident]["donors"]}
            # Reuse the exact primary vector admission, without invoking its primary-condition scorer.
            proxy = {"schema": "ccep-predictions-v1", "task_id": P.TASK, "policy_sha256": ph,
                     "class_order": list(P.CLASSES), "condition": "original_full_scope", "rows": t["rows"]}
            transformed[ident] = P.validate_predictions(proxy, p, ph, support)
        output[name] = {"original": original, "transforms": transformed}
    return output


def score(policy_path, policy_sha256, control_path, control_sha256, map_path, map_sha256,
          artifact_path, targets_path):
    P.sha(map_sha256)
    p, ph, cases, persons, _, ch, rows, arms = _policy(policy_path, policy_sha256, control_path, control_sha256)
    manifest, mh = _frozen_map(map_path, map_sha256, ph, ch, cases, rows)
    artifact, ah = P.read_document(artifact_path)
    predictions = _artifact(artifact, p, ph, ch, mh, cases, arms, manifest)
    base = {"schema": "ccep-paired-loss-report-v1", "task_id": P.TASK, "primary_policy_sha256": ph,
            "control_policy_sha256": ch, "map_sha256": mh, "artifact_sha256": ah,
            "full_original_case_count": len(cases), "patient_count": 5,
            "actual_distinct_transform_count": len(manifest["transforms"]),
            "group_coverage": manifest["groups"], "unsupported_cases": manifest["unsupported_cases"],
            "seed_dispositions": manifest["seeds"], "evaluator_private": True,
            "reference_competence_established": False, "scientifically_qualified": False,
            "native_source_authenticated": False, "packet_execution_verified": False,
            "original_coverage": [{"case_id": c["case_id"], "patient": c["patient"],
                                   "coverage": c["coverage"], "reason": c["coverage_reason"]}
                                  for c in cases.values()],
            "sampling_claim": manifest["sampling_claim"], "biological_replicates_added": 0}
    if any(c["coverage"] != "ready" for c in cases.values()):
        return _admit_output({**base, "status": "construction_unestablished", "targets_opened": False,
                "original_full_scores": None, "paired_diagnostic": None})
    # All declared arms/originals/transforms passed before protected target bytes open.
    tdoc, th = P.read_document(targets_path, p["targets_sha256"])
    targets = P.validate_targets(tdoc, cases)
    original_scores = {name: P.summarize(p, persons, pred["original"], targets)
                       for name, pred in predictions.items()}
    floor = p["numeric_policy"]["loss_floor"]
    loss = lambda values, name: -math.log(max(values[name][targets[name]], floor))
    results = []
    for transform in manifest["transforms"]:
        ident = transform["id"]
        supported = {pair["recipient"] for pair in transform["donors"]}
        by_person = {person: [name for name in persons[person] if name in supported] for person in p["patients"]}
        supported_people = [person for person, names in by_person.items() if names]
        effects = {}
        for arm, pred in predictions.items():
            person_rows = []
            for person, names in by_person.items():
                differences = [loss(pred["transforms"][ident], name) - loss(pred["original"], name) for name in names]
                person_rows.append({"patient": person, "supported_blocks": len(names),
                                    "original_full_blocks": len(persons[person]),
                                    "supported_case_ids": names,
                                    "original_loss_on_same_support": math.fsum(loss(pred["original"], n) for n in names) / len(names) if names else None,
                                    "transformed_loss_on_same_support": math.fsum(loss(pred["transforms"][ident], n) for n in names) / len(names) if names else None,
                                    "paired_loss_difference": math.fsum(differences) / len(names) if names else None})
            effects[arm] = {"role": arms[arm]["role"], "patient_rows": person_rows,
                            "equal_supported_patient_mean": math.fsum(row["paired_loss_difference"] for row in person_rows
                                                                       if row["supported_blocks"]) / len(supported_people)}
        comparisons = []
        for candidate in [name for name in arms if arms[name]["role"] == "candidate"]:
            for reference in [name for name in arms if arms[name]["role"] == "reference"]:
                comparisons.append({"candidate": candidate, "reference": reference,
                                    "matched_patient_count": len(supported_people),
                                    "candidate_minus_reference_pairing_effect": effects[candidate]["equal_supported_patient_mean"] - effects[reference]["equal_supported_patient_mean"]})
        composition = []
        donor_by_recipient = {x["recipient"]: x["donor"] for x in transform["donors"]}
        for group in manifest["groups"]:
            names = group["cases"]
            counts = [sum(targets[name] == k for name in names) for k in range(4)]
            cross = sum(targets[name] != targets[donor_by_recipient[name]] for name in names) if group["supported"] else None
            unchanged = sum(rows[name]["response_sha256"] == rows[donor_by_recipient[name]]["response_sha256"] for name in names) if group["supported"] else None
            composition.append({"group": group["id"], "target_class_counts_after_mapping_frozen": counts,
                                "cross_class_pairs_after_mapping_frozen": cross,
                                "same_class_pairs_after_mapping_frozen": len(names) - cross if cross is not None else None,
                                "response_bytes_unchanged_pairs_after_mapping_frozen": unchanged})
        results.append({"id": ident, "supported_blocks": len(supported), "supported_patients": supported_people,
                        "patients_without_support": [v for v in p["patients"] if v not in supported_people],
                        "arm_effects": effects, "matched_comparisons": comparisons,
                        "descriptive_postfreeze_composition": composition})
    aggregates = {name: math.fsum(t["arm_effects"][name]["equal_supported_patient_mean"] for t in results) / len(results)
                  for name in arms} if results else None
    comparisons = []
    if results:
        for candidate in [n for n in arms if arms[n]["role"] == "candidate"]:
            for reference in [n for n in arms if arms[n]["role"] == "reference"]:
                comparisons.append({"candidate": candidate, "reference": reference,
                                    "candidate_minus_reference_pairing_effect": aggregates[candidate] - aggregates[reference]})
    return _admit_output({**base, "status": "scored_support_limited_diagnostic" if results else "null_unavailable",
            "targets_opened": True, "targets_sha256": th, "original_full_scores": original_scores,
            "transforms": results, "equal_transform_arm_effects": aggregates,
            "equal_transform_matched_comparisons": comparisons,
            "interpretation": "Transformed minus original loss, same supported cases per person, equal supported people then equal distinct transforms. Descriptive dependence only; no permutation p-value or causal conclusion."})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("maps", "packet", "score"))
    ap.add_argument("--policy", required=True); ap.add_argument("--policy-sha256", required=True)
    ap.add_argument("--control", required=True); ap.add_argument("--control-sha256", required=True)
    ap.add_argument("--map"); ap.add_argument("--map-sha256")
    ap.add_argument("--transform-id"); ap.add_argument("--recipient-id")
    ap.add_argument("--recipient-packet"); ap.add_argument("--donor-packet")
    ap.add_argument("--artifact"); ap.add_argument("--targets")
    args = ap.parse_args(argv)
    common = (args.policy, args.policy_sha256, args.control, args.control_sha256)
    try:
        if args.command == "maps":
            P.require(all(v is None for v in (args.map, args.map_sha256, args.transform_id, args.recipient_id,
                      args.recipient_packet, args.donor_packet, args.artifact, args.targets)), "maps accepts no later inputs")
            result = maps(*common)
        elif args.command == "packet":
            P.require(args.artifact is None and args.targets is None, "packet accepts no answers")
            result = packet(*common, args.map, args.map_sha256, args.transform_id, args.recipient_id,
                            args.recipient_packet, args.donor_packet)
        else:
            P.require(all(v is None for v in (args.transform_id, args.recipient_id, args.recipient_packet, args.donor_packet)),
                      "score accepts no waveform paths")
            result = score(*common, args.map, args.map_sha256, args.artifact, args.targets)
    except (P.Invalid, OSError, TypeError, ValueError, OverflowError, RecursionError):
        print(json.dumps({"schema": "ccep-pairing-refusal-v1", "status": "invalid_or_incomplete"}))
        return 2
    print(canonical(result).decode("utf-8"))
    return 3 if result.get("status") in ("construction_unestablished", "null_unavailable") else 0


if __name__ == "__main__":
    sys.exit(main())
