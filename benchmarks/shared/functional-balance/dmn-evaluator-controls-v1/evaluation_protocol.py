"""SOURCE-only complete DMN56 wire/scorer implementation; no CLI or data I/O.

The parent owner opens, authenticates and closes all streams and evidence.
This module neither generates an authentic reference nor grants execution.
Its proposed tolerance and authentication path remain unqualified until the
separately selected controls, native census and thirteen provenance gates close.
"""
import hashlib
import json
import math
import re

KERNEL_REFERENCE = {
    "path": "functional_balance.py",
    "bytes": 15493,
    "sha256": "38c57c6ed5b33b84f362abd29f082c79df6cbf44da132eeb2ccf565ba356ca83",
}
CONDITIONS = ("paper_data", "paper_data_code")
KEYS = tuple((c, e, d, n) for c in ("mics", "hcp")
             for e in ("cortical", "extended")
             for d in ("input", "output") for n in range(2, 9))
GATES = (
    "mean_matrix_lineage", "directed_axis_orientation", "all_four_matrix_label_joins",
    "extended_model_endpoint", "external_type_mapping_helper", "wall_and_spin_semantics",
    "producer_consumer_field_disposition", "six_type_row_disposition",
    "null_network_column_disposition", "empirical_null_mask_disposition",
    "undefined_value_disposition", "strict_tail_disposition", "private_evaluation_rights",
)
NULL_PROTOCOLS = ("code_aligned_source_unmasked_null", "matched_extrinsic_null_prospective")
SPINS = 10000
MAX_LINE_BYTES = 1536
CELL_RECORDS = SPINS + 2
MAX_CELL_BYTES = CELL_RECORDS * MAX_LINE_BYTES
MAX_TOTAL_WIRE_BYTES = (56 * CELL_RECORDS + 2) * MAX_LINE_BYTES
TOLERANCE_ID = "dmn-f64-abs1e-12-rel1e-10-proposed-v1"
ABSOLUTE_TOLERANCE = 1e-12
RELATIVE_TOLERANCE = 1e-10
STREAM_SCHEMA = "dmn56-profile-stream-v1"
CONTEXT_KEYS = {"scope", "case_set_id", "input_manifest_sha256", "method_binding_sha256",
                "spin_manifest_sha256", "null_protocol", "tolerance_id"}
PROFILE_KEYS = {"status", "reason", "strengths", "total_strength", "probabilities", "kl_terms", "kl_bits"}
TAIL_KEYS = {"status", "strict_count", "N", "p", "tie_count", "infinite_null_count",
             "undefined_null_count", "plus_one_p"}


class ProtocolError(ValueError):
    pass


class ScoreMismatch(ProtocolError):
    """A numerical/semantic disagreement; messages deliberately omit reference values."""


class AdmissionError(ProtocolError):
    pass


class StreamRejection(ProtocolError):
    def __init__(self, message, report):
        super().__init__(message)
        self.report = report


def _need(ok, reason):
    if not ok:
        raise ProtocolError(reason)


def _keys(value, expected, label):
    _need(type(value) is dict and set(value) == set(expected), label + ": exact fields required")


def _integer(value, lower, upper, label):
    _need(type(value) is int and lower <= value <= upper, label + ": bounded integer required")


def _digest(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_context(context):
    _keys(context, CONTEXT_KEYS, "context")
    _need(context["scope"] in ("INVENTED_ANALYTICAL", "AUTHENTIC"), "context scope")
    _need(type(context["case_set_id"]) is str and
          re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", context["case_set_id"]) is not None, "case_set_id")
    _need(context["null_protocol"] in NULL_PROTOCOLS, "explicit null protocol")
    _need(context["tolerance_id"] == TOLERANCE_ID, "frozen proposed tolerance identity")
    for key in ("input_manifest_sha256", "method_binding_sha256", "spin_manifest_sha256"):
        if context["scope"] == "INVENTED_ANALYTICAL":
            _need(context[key] is None, "invented witnesses cannot claim authentic identity pins")
        else:
            _need(_digest(context[key]), "authentic context identity must be bound")
    return context


def encode_scalar(value):
    if value is None:
        return {"status": "UNDEFINED", "value": None}
    _need(type(value) in (int, float), "scalar must be numeric or None, never bool")
    if type(value) is int:
        _need(abs(value) <= 2**53, "profile integer exceeds exact binary64 range")
    value = float(value)
    if math.isnan(value):
        return {"status": "UNDEFINED", "value": None}
    if value == math.inf:
        return {"status": "POSITIVE_INFINITY", "value": None}
    _need(value != -math.inf, "negative infinity has no valid wire meaning")
    return value


def decode_scalar(value):
    if type(value) in (int, float):
        if type(value) is int:
            _need(abs(value) <= 2**53, "profile integer exceeds exact binary64 range")
        result = float(value)
        _need(math.isfinite(result), "raw JSON nonfinite value is forbidden")
        return result
    _keys(value, {"status", "value"}, "special scalar")
    _need(value["value"] is None, "special scalar needs null value")
    _need(value["status"] in ("UNDEFINED", "POSITIVE_INFINITY"), "unknown nonfinite status")
    return None if value["status"] == "UNDEFINED" else math.inf


def _same_scalar(actual, expected):
    if actual is None or expected is None:
        return actual is None and expected is None
    if math.isinf(actual) or math.isinf(expected):
        return actual == expected
    return abs(actual - expected) <= ABSOLUTE_TOLERANCE + RELATIVE_TOLERANCE * abs(expected)


def _six(values, label):
    _need(type(values) is list and len(values) == 6, label + ": all six ordered types required")
    return [decode_scalar(value) for value in values]


def _derived(strengths):
    _need(len(strengths) == 6, "six strengths")
    _need(all(value is None or value >= 0 for value in strengths), "negative strength")
    if any(value is None for value in strengths):
        total, reason = None, "NONFINITE_STRENGTH"
    else:
        total = sum(strengths)
        if any(not math.isfinite(value) for value in strengths):
            reason = "NONFINITE_STRENGTH"
        elif not math.isfinite(total):
            reason = "NONFINITE_TOTAL_STRENGTH"
        elif total == 0:
            reason = "ZERO_TOTAL_STRENGTH"
        else:
            reason = None
    if reason is not None:
        return "UNDEFINED", reason, total, [None] * 6, [None] * 6, None
    probabilities = [value / total for value in strengths]
    terms = [math.inf if probability == 0 else
             (math.log2(1 / 6) - math.log2(probability)) / 6 for probability in probabilities]
    infinite = any(math.isinf(term) for term in terms)
    return ("INFINITE" if infinite else "FINITE", "ZERO_PROBABILITY" if infinite else None,
            total, probabilities, terms, sum(terms))


def profile_to_wire(raw):
    """Adapt unchanged V2 profile fields; derive totals/terms explicitly.

    No missing null partner counts are fabricated. Undefined probabilities
    become six explicit undefined slots instead of disappearing from the wire.
    """
    _need(type(raw) is dict and raw.get("status") in ("FINITE", "INFINITE", "UNDEFINED"), "strict source profile")
    _need({"status", "strengths", "probabilities", "KL_bits"}.issubset(raw), "complete source profile fields")
    _need(type(raw.get("strengths")) is list and len(raw["strengths"]) == 6, "source six strengths")
    strengths_wire = [encode_scalar(value) for value in raw["strengths"]]
    strengths = [decode_scalar(value) for value in strengths_wire]
    status, reason, total, probabilities, terms, kl = _derived(strengths)
    _need(raw["status"] == status, "source profile status contradicts strengths")
    _need(_same_scalar(decode_scalar(encode_scalar(raw.get("KL_bits"))), kl), "source KL contradicts profile")
    if status == "UNDEFINED":
        _need(raw.get("probabilities") is None, "undefined source normalization must be explicit")
    else:
        source_p = raw.get("probabilities")
        _need(type(source_p) is list and len(source_p) == 6, "source six probabilities")
        _need(all(type(p) in (int, float) and math.isfinite(p) and 0 <= p <= 1 for p in source_p),
              "source probability domain")
        _need(all(_same_scalar(decode_scalar(encode_scalar(a)), e) for a, e in zip(source_p, probabilities)),
              "source probabilities contradict strengths")
        # Preserve supplied source probabilities/KL; only terms/total are derived.
        probabilities = source_p
        terms = [math.inf if p == 0 else (math.log2(1 / 6) - math.log2(p)) / 6 for p in probabilities]
    return {"status": status, "reason": reason, "strengths": strengths_wire,
            "total_strength": encode_scalar(total),
            "probabilities": [encode_scalar(value) for value in probabilities],
            "kl_terms": [encode_scalar(value) for value in terms],
            "kl_bits": encode_scalar(raw.get("KL_bits"))}


def validate_profile(profile):
    _keys(profile, PROFILE_KEYS, "profile")
    strengths = _six(profile["strengths"], "strengths")
    probabilities = _six(profile["probabilities"], "probabilities")
    terms = _six(profile["kl_terms"], "KL terms")
    total, kl = decode_scalar(profile["total_strength"]), decode_scalar(profile["kl_bits"])
    _need(all(value is None or (math.isfinite(value) and 0 <= value <= 1) for value in probabilities),
          "profile probability outside domain")
    _need(total is None or total >= 0, "profile negative total strength")
    status, reason, expected_total, expected_p, expected_terms, expected_kl = _derived(strengths)
    _need(profile["status"] == status and profile["reason"] == reason, "profile domain/status disagreement")
    _need(_same_scalar(total, expected_total), "profile total-strength disagreement")
    _need(all(_same_scalar(a, e) for a, e in zip(probabilities, expected_p)), "profile normalization disagreement")
    _need(all(_same_scalar(a, e) for a, e in zip(terms, expected_terms)), "profile KL-term disagreement")
    _need(_same_scalar(kl, expected_kl), "profile KL disagreement")
    return strengths, probabilities, terms, total, kl


class TailAccumulator:
    """Strict comparisons over every supplied slot; no finite-only denominator."""
    def __init__(self, empirical):
        self.empirical = empirical
        self.n = self.less = self.ties = self.infinite = self.undefined = 0

    def add(self, value):
        _need(self.n < SPINS, "extra null profile")
        self.n += 1
        if value is None:
            self.undefined += 1
        else:
            self.infinite += value == math.inf
            if self.empirical is not None:
                self.less += self.empirical > value
                self.ties += self.empirical == value

    def wire(self):
        _need(self.n == SPINS, "complete10000 null distribution required")
        undefined = self.empirical is None or self.undefined > 0
        status = "UNDEFINED" if undefined else (
            "EXTENDED_REAL" if self.empirical == math.inf or self.infinite else "FINITE")
        return {"status": status, "strict_count": None if undefined else self.less, "N": SPINS,
                "p": encode_scalar(None if undefined else self.less / SPINS),
                "tie_count": None if self.empirical is None else self.ties,
                "infinite_null_count": self.infinite, "undefined_null_count": self.undefined,
                "plus_one_p": encode_scalar(None if undefined else (self.less + 1) / (SPINS + 1))}


def _validate_tail(tail, expected):
    _keys(tail, TAIL_KEYS, "tail")
    _need(type(tail["status"]) is str and tail["status"] == expected["status"], "tail status disagreement")
    for key in ("strict_count", "N", "tie_count", "infinite_null_count", "undefined_null_count"):
        if expected[key] is None:
            _need(tail[key] is None, "undefined tail count must be null")
        else:
            _integer(tail[key], 0, SPINS, "tail " + key)
            _need(tail[key] == expected[key], "tail count disagreement: " + key)
    for key in ("p", "plus_one_p"):
        _need(decode_scalar(tail[key]) == decode_scalar(expected[key]), "tail probability disagreement: " + key)


def _kernel_tail(raw, expected, plus_one=False):
    _need(type(raw) is dict, "source tail missing")
    for key in ("status", "strict_count", "N"):
        _need(raw.get(key) == expected[key], "source tail disagrees with all null profiles")
    target = decode_scalar(expected["plus_one_p" if plus_one else "p"])
    _need(raw.get("p") == target, "source tail probability disagreement")
    if target is not None:
        protocol = ("prospective_plus_one_lower_tail_separate" if plus_one else
                    "historical_strict_lower_tail_k_over_N")
        _need(raw.get("protocol") == protocol, "source tail protocol identity")


def _partner_counts(rows):
    _need(type(rows) is list and len(rows) == 6, "six empirical partner counts required")
    center = None
    for index, row in enumerate(rows, 1):
        _keys(row, {"type", "center_count", "outside_type_count"}, "partner count")
        _integer(row["type"], 1, 6, "type")
        _need(row["type"] == index, "ordered six types")
        for field in ("center_count", "outside_type_count"):
            _integer(row[field], 0, 400, field)
        _need(center is None or row["center_count"] == center, "inconsistent network size")
        center = row["center_count"]
    _need(center + sum(row["outside_type_count"] for row in rows) == 400,
          "empirical network and six outside-type counts must cover400 parcels")
    return rows


def make_header(context, role, assistance=None):
    validate_context(context)
    _need(role in ("candidate", "reference"), "stream role")
    if role == "candidate":
        _need(assistance in CONDITIONS, "one matched assistance condition required")
    else:
        _need(assistance is None, "private reference is not an assistance condition")
    return {"record": "header", "schema": STREAM_SCHEMA, "role": role,
            "assistance": assistance, "context": dict(context), "cells": 56, "spins_each": SPINS}


def make_end():
    return {"record": "end", "cells": 56, "null_profiles": 56 * SPINS,
            "profile_records": 56 * (SPINS + 1)}


def iter_result_stream(result, context, *, role, assistance=None):
    """Stream existing unchanged run_all56 output; additional storage is O(1)."""
    yield make_header(context, role, assistance)
    _need(type(result) is dict and result.get("complete_cells") == 56 and result.get("spins_each") == SPINS,
          "complete source result")
    records = result.get("records")
    _need(type(records) is list and len(records) == 56, "all56 source cells")
    for key, source in zip(KEYS, records):
        _need(type(source) is dict and source.get("key") == list(key), "source ordered cell roster")
        _need(source.get("null_protocol") == context["null_protocol"], "source null protocol")
        profile = profile_to_wire(source["empirical"])
        counts = _partner_counts(source["partner_counts"])
        yield {"record": "empirical", "cell": list(key), "profile": profile, "partner_counts": counts}
        accumulator = TailAccumulator(decode_scalar(profile["kl_bits"]))
        nulls = source.get("all10000_null_profiles")
        _need(type(nulls) is list and len(nulls) == SPINS, "all10000 source null profiles")
        for spin, raw in enumerate(nulls, 1):
            profile = profile_to_wire(raw)
            accumulator.add(decode_scalar(profile["kl_bits"]))
            yield {"record": "null", "cell": list(key), "spin": spin, "profile": profile}
        tail = accumulator.wire()
        _kernel_tail(source["historical_strict_tail"], tail)
        _kernel_tail(source["plus_one_tail_separate"], tail, True)
        yield {"record": "tail", "cell": list(key), "tail": tail}
    yield make_end()


def _next(iterator, label):
    try:
        return next(iterator)
    except StopIteration as exc:
        raise ProtocolError("missing record: " + label) from exc


def _eof(iterator, label):
    try:
        next(iterator)
    except StopIteration:
        return
    raise ProtocolError("extra record after " + label)


def _record_id(record, kind, key=None, spin=None):
    fields = {"record", "cell", "profile"}
    if kind == "empirical":
        fields.add("partner_counts")
    elif kind == "null":
        fields.add("spin")
    elif kind == "tail":
        fields = {"record", "cell", "tail"}
    _keys(record, fields, kind)
    _need(record["record"] == kind and type(record["cell"]) is list and record["cell"] == list(key),
          "ordered cell/record identity disagreement")
    _need(len(record["cell"]) == 4 and all(type(x) is str for x in record["cell"][:3])
          and type(record["cell"][3]) is int, "exact typed cell identity required")
    if spin is not None:
        _integer(record["spin"], 1, SPINS, "spin")
        _need(record["spin"] == spin, "ordered spin identity disagreement")


def _header(record, context, role):
    _keys(record, {"record", "schema", "role", "assistance", "context", "cells", "spins_each"}, "header")
    expected = make_header(context, role, record["assistance"])
    _need(record == expected, "header/context identity disagreement")
    _integer(record["cells"], 56, 56, "cells")
    _integer(record["spins_each"], SPINS, SPINS, "spins_each")


def _end(record):
    _keys(record, {"record", "cells", "null_profiles", "profile_records"}, "end")
    _need(record == make_end(), "complete stream end disagreement")
    for field in ("cells", "null_profiles", "profile_records"):
        _need(type(record[field]) is int, "end counts must be integers")


def _compare_profiles(actual, expected, location):
    av, ev = validate_profile(actual), validate_profile(expected)
    if actual["status"] != expected["status"] or actual["reason"] != expected["reason"]:
        raise ScoreMismatch(location + ": profile status/reason disagreement")
    for index, name in enumerate(("strengths", "probabilities", "kl_terms")):
        if not all(_same_scalar(a, e) for a, e in zip(av[index], ev[index])):
            raise ScoreMismatch(location + ": " + name + " disagreement")
    for index, name in ((3, "total_strength"), (4, "kl_bits")):
        if not _same_scalar(av[index], ev[index]):
            raise ScoreMismatch(location + ": " + name + " disagreement")
    return av[4], ev[4]


class _Findings:
    def __init__(self, limit):
        _integer(limit, 0, 1000, "finding sample cap")
        self.limit = limit
        self.total = 0
        self.by_kind = {}
        self.sample = []

    def add(self, kind, location):
        self.total += 1
        self.by_kind[kind] = self.by_kind.get(kind, 0) + 1
        if len(self.sample) < self.limit:
            self.sample.append({"kind": kind, "location": location})


def _compare_profile_record(actual, expected, location, findings):
    ev = validate_profile(expected)  # Invalid private references never establish a score.
    try:
        av = validate_profile(actual)
    except ProtocolError:
        findings.add("invalid_profile", location)
        return None, ev[4], False
    for field in ("status", "reason"):
        if actual[field] != expected[field]:
            findings.add("semantic", location + ":" + field)
    for index, field in enumerate(("strengths", "probabilities", "kl_terms")):
        for type_index, (a, e) in enumerate(zip(av[index], ev[index]), 1):
            if not _same_scalar(a, e):
                findings.add("numeric", location + ":" + field + ":type%d" % type_index)
    for index, field in ((3, "total_strength"), (4, "kl_bits")):
        if not _same_scalar(av[index], ev[index]):
            findings.add("numeric", location + ":" + field)
    return av[4], ev[4], True


def _score_core(candidate, reference, context, findings, progress):
    candidate, reference = iter(candidate), iter(reference)
    ch, rh = _next(candidate, "candidate header"), _next(reference, "reference header")
    _header(ch, context, "candidate")
    _header(rh, context, "reference")
    progress["assistance_condition"] = ch["assistance"]
    for cell_index, key in enumerate(KEYS):
        actual, expected = _next(candidate, "empirical"), _next(reference, "empirical")
        _record_id(actual, "empirical", key)
        _record_id(expected, "empirical", key)
        _partner_counts(expected["partner_counts"])
        try:
            _partner_counts(actual["partner_counts"])
            counts_valid = True
        except ProtocolError:
            findings.add("invalid_partner_counts", "cell%d" % cell_index)
            counts_valid = False
        if counts_valid and actual["partner_counts"] != expected["partner_counts"]:
            findings.add("partner_counts", "cell%d" % cell_index)
        ak, ek, cell_valid = _compare_profile_record(actual["profile"], expected["profile"],
                                                    "cell%d empirical" % cell_index, findings)
        progress["profile_pairs_compared"] += 1
        progress["profile_scalar_comparisons"] += 20 if cell_valid else 0
        at, et = TailAccumulator(ak), TailAccumulator(ek)
        for spin in range(1, SPINS + 1):
            actual, expected = _next(candidate, "null"), _next(reference, "null")
            _record_id(actual, "null", key, spin)
            _record_id(expected, "null", key, spin)
            ak, ek, valid = _compare_profile_record(actual["profile"], expected["profile"],
                                                    "cell%d spin%d" % (cell_index, spin), findings)
            cell_valid = cell_valid and valid
            progress["profile_pairs_compared"] += 1
            progress["profile_scalar_comparisons"] += 20 if valid else 0
            progress["null_pairs_compared"] += 1
            at.add(ak)
            et.add(ek)
        actual, expected = _next(candidate, "tail"), _next(reference, "tail")
        _record_id(actual, "tail", key)
        _record_id(expected, "tail", key)
        _validate_tail(expected["tail"], et.wire())
        if not cell_valid:
            findings.add("tail_unverifiable", "cell%d" % cell_index)
        else:
            try:
                _validate_tail(actual["tail"], at.wire())
                tail_valid = True
            except ProtocolError:
                findings.add("invalid_tail", "cell%d" % cell_index)
                tail_valid = False
            if tail_valid:
                for field in sorted(TAIL_KEYS):
                    if actual["tail"][field] != expected["tail"][field]:
                        findings.add("tail", "cell%d:%s" % (cell_index, field))
        progress["cells_completed"] += 1
    _end(_next(candidate, "end"))
    _end(_next(reference, "end"))
    _eof(candidate, "candidate end")
    _eof(reference, "reference end")
    return {"status": "COMPLETE_MATCH" if findings.total == 0 else "COMPLETE_MISMATCH",
            "accepted": findings.total == 0, "complete_traversal": True,
            "assistance_condition": ch["assistance"],
            "cells": 56, "null_profiles": 560000, "empirical_profiles": 56,
            "profile_scalar_slots": 20 * 560056,
            "profile_scalar_comparisons": progress["profile_scalar_comparisons"], "tolerance_id": TOLERANCE_ID,
            "evidence_scope": context["scope"], "scientific_admission": False,
            "scientific_improvement_score": None, "biological_units": "two cohort aggregates",
            "benchmark_count": 1, "reference_values_disclosed": False}


def _score_streams(candidate, reference, context, max_findings):
    findings = _Findings(max_findings)
    progress = {"profile_pairs_compared": 0, "null_pairs_compared": 0, "cells_completed": 0,
                "profile_scalar_comparisons": 0}
    try:
        report = _score_core(candidate, reference, context, findings, progress)
    except ProtocolError as exc:
        findings.add("structural_or_reference_invalid", "stream rejection")
        report = {"status": "INCOMPLETE_REJECTED", "accepted": False, "complete_traversal": False,
                  "discrepancy_count": findings.total, "discrepancies_by_kind": findings.by_kind,
                  "findings_sample": findings.sample, "findings_sample_limit": max_findings,
                  "progress": progress, "scientific_admission": False,
                  "reference_values_disclosed": False}
        raise StreamRejection(str(exc), report) from exc
    report.update(discrepancy_count=findings.total, discrepancies_by_kind=findings.by_kind,
                  findings_sample=findings.sample, findings_sample_limit=max_findings,
                  progress=progress)
    return report


def score_analytical_streams(candidate, reference, context, *, max_findings=100):
    validate_context(context)
    _need(context["scope"] == "INVENTED_ANALYTICAL", "analytical scorer accepts invented scope only")
    return _score_streams(candidate, reference, context, max_findings)


def validate_protected_binding(binding, expected_binding_sha256, accepted_gate_digests):
    """Check owner-supplied exact metadata joins, not authenticity by assertion.

    The owner must independently authenticate each evidence body and supply
    its accepted digest pair out of participant reach. This API's fields and
    authentication mechanism remain unqualified; no positive authentic witness
    exists in this source. Candidate metadata must never be passed as authority.
    """
    if not _digest(expected_binding_sha256):
        raise AdmissionError("protected binding is unbound; no stream may be consumed")
    expected_fields = {"schema", "execution_selected", "context", "kernel_reference", "native_census_sha256",
                       "reference_manifest_sha256", "gate_evidence", "assistance_conditions",
                       "participant_packet_manifests", "reference_visibility", "authentication_qualified",
                       "tolerance_status", "tolerance_controls_sha256"}
    _keys(binding, expected_fields, "protected binding")
    _need(binding["schema"] == "dmn56-protected-admission-v1", "protected binding schema")
    if binding["execution_selected"] is not True or binding["authentication_qualified"] is not True:
        raise AdmissionError("protected execution/authentication remains unselected or unqualified")
    validate_context(binding["context"])
    _need(binding["context"]["scope"] == "AUTHENTIC", "authentic owner context")
    _need(binding["kernel_reference"] == KERNEL_REFERENCE, "exact accepted V2 kernel reference")
    _need(binding["assistance_conditions"] == list(CONDITIONS), "both matched assistance conditions")
    _need(binding["reference_visibility"] == "EVALUATOR_PRIVATE", "private reference visibility")
    _need(binding["tolerance_status"] == "ACCEPTED_BEFORE_AUTHENTIC_RESULTS", "tolerance has not been prospectively accepted")
    for key in ("native_census_sha256", "reference_manifest_sha256", "tolerance_controls_sha256"):
        _need(_digest(binding[key]), "unbound protected evidence: " + key)
    _keys(binding["participant_packet_manifests"], CONDITIONS, "packet manifests")
    _need(all(_digest(value) for value in binding["participant_packet_manifests"].values()), "packet manifest digests")
    _keys(binding["gate_evidence"], GATES, "all thirteen provenance gates")
    _keys(accepted_gate_digests, GATES, "owner-verified gate digest set")
    for gate in GATES:
        entry, trusted = binding["gate_evidence"][gate], accepted_gate_digests[gate]
        _keys(entry, {"status", "evidence_sha256", "review_sha256"}, "gate " + gate)
        _keys(trusted, {"evidence_sha256", "review_sha256"}, "verified gate " + gate)
        _need(entry["status"] == "ACCEPTED" and all(_digest(entry[k]) and entry[k] == trusted[k]
              for k in ("evidence_sha256", "review_sha256")), "unclosed or unverified gate: " + gate)
    body = json.dumps(binding, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    _need(len(body) <= 65536, "protected binding metadata cap")
    _need(hashlib.sha256(body).hexdigest() == expected_binding_sha256, "exact canonical protected binding digest")
    return binding["context"]


def score_protected_streams(candidate, reference, *, binding, expected_binding_sha256, accepted_gate_digests,
                            max_findings=100):
    context = validate_protected_binding(binding, expected_binding_sha256, accepted_gate_digests)
    return _score_streams(candidate, reference, context, max_findings)


def encode_record(record):
    try:
        raw = (json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise ProtocolError("record cannot be encoded as bounded standard JSON") from exc
    _need(len(raw) <= MAX_LINE_BYTES, "wire line exceeds1536 bytes")
    return raw


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _need(key not in result, "duplicate JSON object key")
        result[key] = value
    return result


def _no_constant(value):
    raise ProtocolError("nonstandard JSON constant forbidden: " + value)


def _json_float(value):
    result = float(value)
    _need(math.isfinite(result), "JSON number overflows finite binary64")
    return result


def read_jsonl_records(binary_stream, *, max_records=CELL_RECORDS, accounting=None):
    """Consume every byte/line; caller owns file authentication and closure."""
    _integer(max_records, 1, CELL_RECORDS, "per-stream record cap")
    consumed = records = 0
    complete = False
    try:
        while True:
            line = binary_stream.readline(MAX_LINE_BYTES + 1)
            _need(type(line) is bytes, "JSONL stream must be binary")
            consumed += len(line)
            if not line:
                complete = True
                return
            _need(len(line) <= MAX_LINE_BYTES, "wire line exceeds1536 bytes")
            _need(line.endswith(b"\n") and not line.endswith(b"\r\n"), "one complete LF-terminated JSON record required")
            _need(records < max_records, "extra JSONL record")
            try:
                record = json.loads(line.decode("utf-8"), object_pairs_hook=_unique_object,
                                    parse_constant=_no_constant, parse_float=_json_float)
            except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
                raise ProtocolError("invalid JSONL record") from exc
            _need(type(record) is dict, "wire record must be a JSON object")
            records += 1
            yield record
    finally:
        if accounting is not None:
            accounting.update(bytes_consumed=consumed, records=records, complete_eof=complete,
                              counters_are_lower_bounds=not complete)


def _ordered_frames(iterator):
    """Yield (physical shard index, record); -1=header,56=end."""
    iterator = iter(iterator)
    header = _next(iterator, "header")
    _need(type(header) is dict and header.get("record") == "header", "header first")
    _header(header, header.get("context"), header.get("role"))
    yield -1, header
    for index, key in enumerate(KEYS):
        record = _next(iterator, "empirical")
        _record_id(record, "empirical", key)
        yield index, record
        for spin in range(1, SPINS + 1):
            record = _next(iterator, "null")
            _record_id(record, "null", key, spin)
            yield index, record
        record = _next(iterator, "tail")
        _record_id(record, "tail", key)
        yield index, record
    record = _next(iterator, "end")
    _end(record)
    yield 56, record
    _eof(iterator, "end")


def write_sharded_jsonl(records, header_sink, cell_sinks, end_sink):
    _need(type(cell_sinks) in (list, tuple) and len(cell_sinks) == 56, "exact56 ordered cell sinks")
    sizes, counts = [0] * 58, [0] * 58
    for shard, record in _ordered_frames(records):
        raw = encode_record(record)
        slot = shard + 1
        sink = header_sink if shard == -1 else end_sink if shard == 56 else cell_sinks[shard]
        _need(sink.write(raw) == len(raw), "short JSONL write")
        sizes[slot] += len(raw)
        counts[slot] += 1
        _need(sizes[slot] <= (MAX_LINE_BYTES if shard in (-1, 56) else MAX_CELL_BYTES), "shard byte cap")
    _need(counts == [1] + [CELL_RECORDS] * 56 + [1], "complete shard record counts")
    return {"bytes": sizes, "records": counts, "total_bytes": sum(sizes), "complete": True}


def read_sharded_jsonl(header_stream, cell_streams, end_stream):
    _need(type(cell_streams) in (list, tuple) and len(cell_streams) == 56, "exact56 ordered cell streams")
    header = iter(read_jsonl_records(header_stream, max_records=1))
    record = _next(header, "header")
    _need(record.get("record") == "header", "header first")
    _header(record, record.get("context"), record.get("role"))
    _eof(header, "header shard")
    yield record
    for key, stream in zip(KEYS, cell_streams):
        rows = iter(read_jsonl_records(stream))
        record = _next(rows, "empirical")
        _record_id(record, "empirical", key)
        yield record
        for spin in range(1, SPINS + 1):
            record = _next(rows, "null")
            _record_id(record, "null", key, spin)
            yield record
        record = _next(rows, "tail")
        _record_id(record, "tail", key)
        yield record
        _eof(rows, "cell shard")
    end = iter(read_jsonl_records(end_stream, max_records=1))
    record = _next(end, "end")
    _end(record)
    _eof(end, "end shard")
    yield record
