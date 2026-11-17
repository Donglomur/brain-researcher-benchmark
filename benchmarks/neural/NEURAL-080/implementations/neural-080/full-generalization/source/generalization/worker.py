"""Pinned isolated reference worker. No source work happens at import.

The runner owns actual namespaces, read-only mounts and resource limits before
this function imports scientific packages. This worker receives all shared
stimulus inputs and only the selected TRAIN/QUERY personal covariates; its sole
EEG body contains outer TRAIN rows. Query EEG is never a worker operand.
"""
from __future__ import annotations

import os
from pathlib import Path

from input_owner import capture
from io_contract import decode
from .artifacts import capture_array, decode_array, descriptor, need
from .splits import VIDEO_IDS, outer_cases

DOCUMENT_LIMIT = 16 * 1024 * 1024


def _coordinates(value, expected):
    need(type(value) is list and all(type(row) is list and len(row) == 2 and
         type(row[0]) is str and type(row[1]) is int for row in value) and
         value == [list(row) for row in expected], "Exact ordered selected worker coordinates required")
    return tuple(expected)


def _read_array(root, row, shape, owner):
    return decode_array(capture_array(root, row, shape, owner), shape, owner)


def reference_case(view_root, case_descriptor, context_descriptor, output, owner):
    """Run one complete seven-arm reference from the runner's actual case view."""
    from .campaign import cost_start, observed_cost, validate_cost, subtract_cost, combine_cost
    started = cost_start(owner)
    record = owner.begin("isolated_full_reference_worker")
    answer = None
    try:
        from .operator import restore_plan, _existing_writer
        from . import models, reference
        descriptor(case_descriptor, DOCUMENT_LIMIT)
        descriptor(context_descriptor, DOCUMENT_LIMIT)
        need(case_descriptor["path"] == "CASE.json" and context_descriptor["path"] == "CONTEXT.json",
             "Exact case/context filenames in the isolated view required")
        case_body = capture(view_root, case_descriptor, owner, max_bytes=DOCUMENT_LIMIT)
        context_body = capture(view_root, context_descriptor, owner, max_bytes=DOCUMENT_LIMIT)
        document, context = decode(case_body), decode(context_body)
        need(type(document) is dict and document.get("schema") == "neural080_generalization_case_input_v1" and
             document.get("units") == "original_eeg" and document.get("logical_limits") == owner.limits,
             "Actual staged original-unit inputs and exact worker limits required")
        need(type(context) is dict and set(context) == {"schema", "case_id", "assignment_sha256", "backend",
             "case_input_identity", "target_manifest_identity", "prepared_manifest_identity", "programme_tree_members"} and
             context["schema"] == "neural080_case_context_v1" and context["case_input_identity"] == case_descriptor,
             "Captured worker context must bind actual CASE bytes")
        descriptor(context["target_manifest_identity"], DOCUMENT_LIMIT)
        descriptor(context["prepared_manifest_identity"], DOCUMENT_LIMIT)
        plan = restore_plan(document["assignment"])
        need(document["assignment_sha256"] == context["assignment_sha256"] == plan.assignment_sha256 and
             document["case_id"] == context["case_id"] and document["backend"] == context["backend"],
             "Full source assignment and backend must join captured context")
        cases = {case.case_id: case for case in outer_cases(plan)}
        need(document["case_id"] in cases, "One selected outer case required")
        case = cases[document["case_id"]]
        train, query = tuple(case.training_coordinates()), tuple(case.query_coordinates())
        coordinates = train + query
        _coordinates(document["training_coordinates"], train)
        _coordinates(document["query_coordinates"], query)
        _coordinates(document["personal_coordinates"], coordinates)
        need(type(document["video_ids"]) is list and all(type(video) is int for video in document["video_ids"]) and
             tuple(document["video_ids"]) == VIDEO_IDS, "Every shared video identity required")
        need(type(document["personal"]) is dict and set(document["personal"]) == {"eye", "timing"},
             "Only exact selected raw personal covariate roles required")
        seed = os.environ.get("NEURAL080_SEED")
        threads = os.environ.get("NEURAL080_THREADS")
        need(type(seed) is str and seed.isdecimal() and 0 <= int(seed) <= 4294967295 and
             type(threads) is str and threads.isdecimal() and int(threads) > 0,
             "Actual runner seed/thread environment required before numeric work")
        from .features import BLOCK_DIMS
        need(document["blocks"] == BLOCK_DIMS, "Exact complete fixed feature dimensions")
        eye = _read_array(view_root, document["personal"]["eye"], (len(coordinates), 150, 8), owner)
        timing = _read_array(view_root, document["personal"]["timing"], (len(coordinates), 26), owner)
        raw_targets = _read_array(view_root, document["training_targets"], (len(train), 127, 150), owner)
        training_targets = models.capture_training_targets(train, raw_targets, owner)
        writer = _existing_writer(output, owner)
        backend = document["backend"]
        base_keys = {"schema", "backend", "assignment", "assignment_sha256", "case_id", "units", "video_ids",
                     "blocks", "training_coordinates", "query_coordinates", "personal_coordinates", "personal",
                     "training_targets", "logical_limits", "target_contract", "access_scope", "authority"}
        if backend == "full_svd_materialized":
            need(set(document) == base_keys | {"shared"}, "Closed full materialized case schema")
        elif backend == "streamed_dual_certified":
            need(set(document) == base_keys | {"stream_spec", "stream_metadata_captures", "mount_contract"},
                 "Closed full streamed case schema")
        if backend == "full_svd_materialized":
            from .features import BLOCK_DIMS
            need(document["blocks"] == BLOCK_DIMS and type(document["shared"]) is dict and
                 set(document["shared"]) == set(BLOCK_DIMS), "Complete selected full source blocks required")
            shared = {name: _read_array(view_root, document["shared"][name], (1102, width), owner)
                      for name, width in BLOCK_DIMS.items()}
            pool = models.capture_case_features(plan, case, shared, coordinates, eye, timing, owner)
        elif backend == "streamed_dual_certified":
            from .feature_stream import ActualFeatureStream, parse_stream_spec, validate_programme_tree
            descriptor(document["stream_spec"], DOCUMENT_LIMIT)
            stream_document = decode(capture(view_root, document["stream_spec"], owner, max_bytes=DOCUMENT_LIMIT))
            spec = parse_stream_spec(stream_document, owner)
            need(spec.programme_root == "/source" and spec.metadata_root == "/tools/feature-metadata" and
                 spec.media_root == "/tools/media" and spec.checkpoint_root == "/tools/checkpoint",
                 "Actual pinned guest source/media/checkpoint roots required")
            validate_programme_tree(spec, context["programme_tree_members"])
            stream = ActualFeatureStream(spec, writer)
            pool = models.capture_stream_case_features(plan, case, stream, coordinates, eye, timing, owner)
        else:
            raise ValueError("No unselected feature/readout backend or fallback")
        seed = os.environ.get("NEURAL080_SEED")
        threads = os.environ.get("NEURAL080_THREADS")
        need(type(seed) is str and seed.isdecimal() and 0 <= int(seed) <= 4294967295 and
             type(threads) is str and threads.isdecimal() and int(threads) > 0,
             "Actual runner seed/thread environment required")
        # The fixed ridge and streaming decomposition are deterministic recipes;
        # set the NumPy global RNG as well for any supported runtime internals.
        import numpy as np
        np.random.seed(int(seed))
        preparation_cost = validate_cost(observed_cost(started, owner), positive=True)
        call_started = cost_start(owner)
        result = reference.run_outer(plan, case, training_targets, pool, owner, writer)
        whole_call = validate_cost(observed_cost(call_started, owner), positive=True)
        cost_pin = result["full_arm_cost"]
        descriptor(cost_pin, DOCUMENT_LIMIT)
        cost_document = decode(capture(writer.root, cost_pin, owner, max_bytes=DOCUMENT_LIMIT))
        need(cost_document["schema"] == "neural080_full_arm_cost_v1" and cost_document["case_id"] == case.case_id and
             cost_document["assignment_sha256"] == plan.assignment_sha256 and
             cost_document["feature_backend"] == backend and cost_document["actual_full_ridge_fits"] == 261,
             "Actual complete FULL construction attribution required")
        full_debit = combine_cost(preparation_cost, subtract_cost(whole_call, cost_document["excluded_cost"]))
        validate_cost(full_debit, positive=True)
        envelope = {"schema": "neural080_worker_reference_v1", "case_context": dict(context_descriptor),
                    "context_sha256": context_descriptor["sha256"], "reference": result,
                    "worker_preparation_cost": preparation_cost, "complete_reference_call_cost": whole_call,
                    "full_decoder_debit": full_debit,
                    "debit_scope": "Actual worker preparation plus complete run_outer call minus its measured disjoint other-arm/mean/reversal exclusions. All remaining call work, including run_outer receipt tail, is charged to FULL; this envelope/CLI publication tail is not self-measured.",
                    "native_aggregate_cost": "Unavailable without independent aggregate and end-to-end host qualification; observed process/logical debit supports developmental diagnostics only"}
        manifest = writer.document("CASE_REFERENCE.json", envelope)
        answer = {"manifest": manifest, "case_id": case.case_id, "output": str(writer.root)}
    except BaseException as exc:
        owner.failure(record, exc)
    owner.complete(record)
    return answer
