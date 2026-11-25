"""NEURAL-073 admitted original-corpus query -> existing typed map viewer.

All arguments and this object are operator-private. Only dispatch() responses
may enter a separately qualified participant transport. This module neither
loads/converts NIfTI nor creates source, runtime, calibration or mode authority.
"""
from __future__ import annotations

import hashlib
import json
from types import ModuleType
import weakref


CONTRACT_BYTES = 3350
CONTRACT_SHA256 = "227bca5d4f370240b89e67288020ceaac47ca1b150a1b6827680845b49b59b74"


class InputError(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise InputError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def hex64(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def closed(value, fields, name):
    need(type(value) is dict and set(value) == set(fields), "closed fields: " + name)


def positive(value):
    return type(value) is int and 0 < value <= 2**53 - 1


def pinned(raw, pin, cap):
    closed(pin, ("bytes", "sha256"), "metadata pin")
    need(positive(pin["bytes"]) and pin["bytes"] <= cap and hex64(pin["sha256"]),
         "bounded exact metadata pin required")
    need(type(raw) is bytes and len(raw) == pin["bytes"] and sha(raw) == pin["sha256"],
         "metadata body identity mismatch")


def _display_key(context_digest, source_key):
    # This is a private ABI alias, never a replacement source/evaluation key.
    return sha(b"n073-query-viewer-alias-v1\0" + bytes.fromhex(context_digest)
               + bytes.fromhex(source_key))[:32]


def _retain_until_map_dies(values):
    # weakref.finalize's argument retains the CanonicalValues owner, which owns
    # the corpus workspace reservation for these same immutable backing bytes.
    pass


class QueryInput:
    """Task-specific original-condition query adapter; not an OS boundary.

    corpus_module must be the SAME loaded source module that issued bundle;
    viewer_module is the accepted typed-map-viewer-v1 module. Source loading and
    exact dependency-pin verification remain the trusted operator's duties.
    """

    def __init__(self, *, corpus_module, viewer_module, bundle, export_plan,
                 export_authority, inventory_pin, converter_contract,
                 conversion_result, conversion_result_pin, limits, clock=None):
        need(type(corpus_module) is ModuleType and type(viewer_module) is ModuleType,
             "actual operator-loaded modules required")
        c, v = corpus_module, viewer_module
        a = c.admission
        need(type(bundle) is c.CorpusBundle and bundle._seal is c._BUNDLE_SEAL,
             "actual corpus bundle required")
        need(type(bundle.values_by_id) is c.CanonicalMapping and
             not bundle.values_by_id._closed, "open canonical mapping required")
        need(type(export_plan) is a.ExportPlan, "actual issued export plan required")
        export_plan.require_issued()
        export_plan.context.validate()
        need(export_plan.context.condition == "original" and
             export_plan.scramble_bank_commitment is None,
             "only original canonical-map condition is supported")
        need(type(export_authority) is a.export.VerifiedAuthority,
             "verified existing export capability required")
        authority_digest = export_authority.require(
            role="export", domain=export_plan.authority_domain,
            bindings=export_plan.bindings)

        catalogue, assessment = bundle.catalogue, bundle.assessment
        need(type(catalogue) is a.Catalogue and type(assessment) is a.CorpusAssessment,
             "issued catalogue and assessment required")
        catalogue.require_valid()
        assessment.require_issued()
        need(1 <= len(catalogue.records) <= 9532, "bounded complete source catalogue required")
        need(assessment.numeric_checks_passed and not assessment.issues,
             "unresolved corpus assessment")
        need(export_plan.domain == catalogue.domain == assessment.domain and
             export_plan.catalogue_digest == catalogue.fingerprint == assessment.catalogue_digest and
             export_plan.assessment_digest == assessment.fingerprint,
             "corpus/plan assessment identity mismatch")
        need(bundle.geometry == assessment.geometry == bundle.values_by_id.geometry,
             "corpus geometry mismatch")
        bundle.geometry.validate(full=True)
        records = catalogue.by_id
        ids = set(records)
        need(set(bundle.values_by_id) == ids == set(assessment.private_ids) ==
             set(bundle.observations) == set(bundle.original_receipts),
             "complete corpus identities required")
        need(a.arrays.observations_digest(bundle.observations) == assessment.observations_digest and
             c.digest([bundle.original_receipts[k].fingerprint for k in sorted(ids)]) ==
             assessment.original_receipts_digest, "corpus receipt/observation binding mismatch")
        need(tuple(export_plan.label_order) == catalogue.label_order and
             len(catalogue.label_order) == 25, "exact issued 25-class order required")

        # Validate the complete held-person join without examining target arrays
        # or retaining query labels in the viewer-facing loader's lookup table.
        held = export_plan.context.outer_person
        need(held in catalogue.people, "unknown held person")
        expected_query = {rid for rid, r in records.items() if r.person == held}
        expected_train = ids - expected_query
        seen_ids, seen_keys, groups = set(), set(), {}
        query_pairs = []
        for role, rows, expected in (("training", export_plan.training_map, expected_train),
                                     ("query", export_plan.query_map, expected_query)):
            need(type(rows) is tuple and len(rows) == len(expected) and rows,
                 "complete nonempty role roster required")
            role_ids = set()
            for row in rows:
                need(type(row) is tuple and len(row) == (4 if role == "training" else 3),
                     "issued role tuple shape")
                key, rid, label = row[:3]
                need(hex64(key) and key not in seen_keys and type(rid) is str and
                     rid in expected and rid not in seen_ids and type(label) is int and
                     label == records[rid].label, "role key/record/label join mismatch")
                seen_keys.add(key)
                seen_ids.add(rid)
                role_ids.add(rid)
                if role == "training":
                    group = row[3]
                    need(hex64(group), "opaque training group required")
                    person = records[rid].person
                    need(person not in groups or groups[person] == group,
                         "inconsistent training-person group")
                    groups[person] = group
                else:
                    query_pairs.append((key, rid))
            need(role_ids == expected, "complete role identity set required")
        need(len(set(groups.values())) == len(groups), "training group collision")
        need(seen_ids == ids, "complete corpus partition required")

        pinned(converter_contract, {"bytes": CONTRACT_BYTES, "sha256": CONTRACT_SHA256},
               CONTRACT_BYTES)
        contract = c.strict_json(converter_contract)
        need(contract["dtype"] == "<f8" and contract["order"] == "C" and
             contract["native_grid_only"] is True and contract["resample_mask_crop_reorient"] is False,
             "accepted native converter contract required")
        closed(inventory_pin, ("path", "bytes", "sha256"), "admitted inventory pin")
        need(type(inventory_pin["path"]) is str and inventory_pin["path"] and
             positive(inventory_pin["bytes"]) and hex64(inventory_pin["sha256"]),
             "explicit admitted inventory identity required")
        need(c.digest(inventory_pin) == bundle.admission_bindings["inventory_pin_digest"],
             "inventory differs from corpus admission")
        pinned(conversion_result, conversion_result_pin, 65536)
        result = c.strict_json(conversion_result)
        closed(result, ("schema", "domain", "catalogue_digest", "geometry", "spatial_units",
                        "unit_conversion_performed", "records", "canonical_bytes", "inventory",
                        "independent_fidelity_rights_identity_qualification", "deployment_enabled"),
               "converter result")
        geometry = {"shape": list(bundle.geometry.shape), "affine": list(bundle.geometry.affine),
                    "orientation": list(bundle.geometry.orientation)}
        extent = 8 * bundle.geometry.voxels
        need(result["schema"] == "n073_conversion_result_v1" and
             result["domain"] == catalogue.domain and
             result["catalogue_digest"] == catalogue.fingerprint and result["geometry"] == geometry,
             "converter/corpus identity or geometry mismatch")
        need(all(type(n) is int for n in result["geometry"]["shape"]) and
             all(type(n) in (int, float) for n in result["geometry"]["affine"]),
             "literal numeric geometry types required")
        need(type(result["records"]) is int and result["records"] == len(ids) and
             type(result["canonical_bytes"]) is int and
             result["canonical_bytes"] == extent * len(ids), "complete converter support required")
        closed(result["inventory"], ("bytes", "sha256"), "converter inventory")
        need(result["inventory"] == {k: inventory_pin[k] for k in ("bytes", "sha256")},
             "converter inventory identity mismatch")
        need(result["spatial_units"] in ("unknown", "meter", "mm", "micron") and
             result["unit_conversion_performed"] is False and
             result["independent_fidelity_rights_identity_qualification"] is False and
             result["deployment_enabled"] is False, "converter scope or spatial units mismatch")
        for rid in ids:
            pin, receipt, obs = (bundle.values_by_id.entries[rid],
                                 bundle.original_receipts[rid], bundle.observations[rid])
            need(pin["bytes"] == extent and pin["sha256"] == obs.decoded_sha256 and
                 receipt.decoder_contract_digest == CONTRACT_SHA256 and
                 receipt.record_id == rid and receipt.domain == catalogue.domain and
                 obs.geometry == bundle.geometry, "canonical/decoder receipt mismatch")

        # A new display alias namespace is necessary because the unchanged
        # viewer accepts128-bit keys and the admitted source exports256-bit keys.
        context = export_plan.context.fingerprint
        pairs = [(_display_key(context, key), key, rid) for key, rid in query_pairs]
        need(all(v.token(alias) for alias, _, _ in pairs) and
             len({alias for alias, _, _ in pairs}) == len(pairs), "display alias collision")
        aliases = tuple(row[0] for row in pairs)
        # Each private case key is obtained through a charged status/describe
        # action before its answer. No following key is disclosed by answer.
        need(type(limits) is v.Limits and limits.max_actions >= 2 * len(aliases),
             "budget must permit key lookup and answer for the complete query roster")
        self._corpus, self._viewer, self._bundle = c, v, bundle
        self._query = {alias: (key, rid) for alias, key, rid in pairs}
        self._aliases = aliases
        self._source_keys = tuple(key for _, key, _ in pairs)
        self._shape = tuple(bundle.geometry.shape)
        self._affine = tuple(tuple(bundle.geometry.affine[i:i+4]) for i in (0, 4, 8, 12))
        self._units = result["spatial_units"]
        self._context = context
        self._ontology = sha(v.json_body(list(export_plan.label_order)).encode())
        self._authority = authority_digest
        self._result_pin = dict(conversion_result_pin)
        self._closed = False
        options = {} if clock is None else {"clock": clock}
        self._session = v.ViewerSession(
            case_ids=aliases, roster_sha256=sha(v.json_body(list(aliases)).encode()),
            class_labels=tuple(export_plan.label_order), ontology_sha256=self._ontology,
            loader=self._load, limits=limits, **options)

    def _load(self, alias):
        need(not self._closed and alias in self._query, "query display key required")
        _, rid = self._query[alias]
        mapping = self._bundle.values_by_id
        values = mapping[rid]  # Existing descriptor-safe canonical reader; no new I/O path.
        need(type(values) is self._corpus._CanonicalValues and type(values._raw) is bytes,
             "actual immutable canonical backing required")
        pin = mapping.entries[rid]
        volume = self._viewer.CanonicalMap(values._raw, self._shape, self._affine,
                                            self._units, pin["sha256"])
        weakref.finalize(volume, _retain_until_map_dies, values)
        return volume

    def dispatch(self, request):
        need(not self._closed, "query input closed")
        return self._session.dispatch(request)

    def finish(self):
        """Operator-only restore, with both distinct schemas/digests preserved."""
        need(not self._closed, "query input closed")
        collection = self._session.finish()
        need(tuple(r["case_id"] for r in collection["records"]) == self._aliases,
             "complete unchanged viewer response roster required")
        rows = [{"case_id": self._query[row["case_id"]][0],
                 "probabilities": row["probabilities"]} for row in collection["records"]]
        self._closed = True
        return {"schema": "n073-corpus-viewer-query-result/v1", "task_id": "NEURAL-073",
                "context_digest": self._context, "export_authority_digest": self._authority,
                "source_query_keys_sha256": sha(canonical(list(self._source_keys))),
                "public_ontology_sha256": self._ontology,
                "conversion_result_pin": self._result_pin,
                "viewer_collection": collection,
                "source_records": rows, "source_response_sha256": sha(canonical(rows)),
                "scope": "existing_original_condition_query_only",
                "scientific_qualification": False, "runtime_or_mode_adopted": False,
                "calibration_delivery_qualified": False, "isolated_transport_qualified": False}
