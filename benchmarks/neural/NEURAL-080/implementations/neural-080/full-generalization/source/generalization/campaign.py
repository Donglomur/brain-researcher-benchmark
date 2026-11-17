"""Complete phase-separated operator campaign, with no work at import.

stage may use numerical libraries; execute must be a new, stdlib-only process.
The actual Linux runner refuses inherited native threads. compare is another
process: all predictions are captured before protected target binding. Nothing
here turns a descriptor, resource limit or source completion into qualification.
"""
from __future__ import annotations

from dataclasses import asdict, fields, replace
from pathlib import Path, PurePosixPath
import hashlib
from fractions import Fraction
import json
import math
import time
import os
import sys

from input_owner import Owner, Writer, capture
from io_contract import decode
from .artifacts import (ARMS, MODES, TOOL_REGIMES, CANDIDATE_CELLS, CANDIDATE_KEYS,
                        array_limit, capture_array, decode_array, descriptor,
                        need, validate_reference, validate_candidate)
from .splits import PERSONS, VIDEO_IDS, outer_cases

DOCUMENT_LIMIT = 16 * 1024 * 1024
BACKENDS = ("full_svd_materialized", "streamed_dual_certified")
COMMON_TOOL_ROLES = {"/tools/candidate": "candidate_programme",
                     "/tools/numerical": "generic_numerical_tools",
                     "/tools/media": "agreed_media",
                     "/tools/checkpoint": "fixed_feature_checkpoint",
                     "/tools/feature-metadata": "agreed_stimulus_metadata"}

# The supplied FULL decoder and generic candidate need the same feasible worker
# envelope. Separate seven-arm totals do not justify more memory/concurrency.
MATCHED_LIMIT_FIELDS = (
    "address_space_bytes", "file_bytes", "tmpfs_bytes", "open_files",
    "processes", "threads", "seed", "poll_seconds", "cleanup_seconds")
SEPARATE_LIMIT_FIELDS = (
    "cpu_seconds", "wall_seconds", "output_bytes", "output_members",
    "stdout_bytes", "stderr_bytes", "report_bytes", "intake_bytes", "intake_members")


def _document(root, row, owner, maximum=DOCUMENT_LIMIT):
    descriptor(row, maximum)
    return decode(capture(root, row, owner, max_bytes=maximum))


def _absolute(value):
    need(type(value) is str and Path(value).is_absolute() and str(Path(value)) == value and
         not any(part in (".", "..") for part in value.split("/")[1:]) and
         not any(ord(char) < 32 or ord(char) == 127 for char in value),
         "Explicit canonical absolute local path required")
    return value


def _limits(value):
    need(type(value) is dict and set(value) == {"read_bytes", "write_bytes", "retained_bytes", "attempts"} and
         all(type(amount) is int and 0 < amount < 2**63 for amount in value.values()),
         "Complete explicit logical phase limits required")
    return dict(value)


def cost_start(owner):
    return ({"monotonic_ns": time.monotonic_ns(), "process_cpu_ns": time.process_time_ns()}, dict(owner.used))


def observed_cost(start, owner):
    clocks, before = start
    return {"monotonic_ns": time.monotonic_ns() - clocks["monotonic_ns"],
            "process_cpu_ns": time.process_time_ns() - clocks["process_cpu_ns"],
            "logical_delta": {key: owner.used[key] - before[key] for key in before}}


def validate_cost(value, *, positive=False):
    need(type(value) is dict and set(value) == {"monotonic_ns", "process_cpu_ns", "logical_delta"},
         "Actual closed clock/logical cost observation required")
    need(all(type(value[key]) is int and value[key] >= (1 if positive else 0)
             for key in ("monotonic_ns", "process_cpu_ns")), "Actual finite nonnegative integer clock deltas")
    logical = value["logical_delta"]
    need(type(logical) is dict and set(logical) == {"read_bytes", "write_bytes", "retained_bytes", "attempts"} and
         all(type(number) is int and number >= 0 for number in logical.values()),
         "Complete actual logical counter delta required")
    return value


def cost_profile(value):
    need(type(value) is dict and set(value) == {"monotonic_ns", "process_cpu_ns", "logical_delta", "scope", "native_aggregate_cost"} and
         type(value["scope"]) is str and bool(value["scope"]) and
         type(value["native_aggregate_cost"]) is str and bool(value["native_aggregate_cost"]),
         "Observed phase cost and honest measurement scope required")
    return validate_cost({key: value[key] for key in ("monotonic_ns", "process_cpu_ns", "logical_delta")}, positive=True)


def combine_cost(*costs):
    need(bool(costs), "Actual measured cost operands required")
    for cost in costs:
        validate_cost(cost)
    return {"monotonic_ns": sum(cost["monotonic_ns"] for cost in costs),
            "process_cpu_ns": sum(cost["process_cpu_ns"] for cost in costs),
            "logical_delta": {key: sum(cost["logical_delta"][key] for cost in costs)
                              for key in costs[0]["logical_delta"]}}


def subtract_cost(gross, excluded):
    validate_cost(gross)
    validate_cost(excluded)
    result = {key: gross[key] - excluded[key] for key in ("monotonic_ns", "process_cpu_ns")}
    result["logical_delta"] = {key: gross["logical_delta"][key] - excluded["logical_delta"][key]
                               for key in gross["logical_delta"]}
    return validate_cost(result)


def common_allocations(total):
    validate_cost(total, positive=True)
    def portion(number, index):
        quotient, remainder = divmod(number, 30)
        return quotient + int(index < remainder)
    result = tuple({"monotonic_ns": portion(total["monotonic_ns"], index),
                    "process_cpu_ns": portion(total["process_cpu_ns"], index),
                    "logical_delta": {key: portion(value, index) for key, value in total["logical_delta"].items()}}
                   for index in range(30))
    need(combine_cost(*result) == total, "Every common nanosecond/byte/attempt allocated exactly once across thirty cases")
    return result


def remaining_budget(config, logical_budget, charged):
    """Observed diagnostic debit; native aggregate and publication tails remain held."""
    validate_cost(charged)
    base = config.limits
    logical = _limits(logical_budget)
    need(type(base.cpu_seconds) is int and base.cpu_seconds > 0 and
         type(base.wall_seconds) in (int, float) and math.isfinite(base.wall_seconds) and base.wall_seconds > 0,
         "Explicit positive CPU/wall base budget required")
    remaining_cpu_ns = base.cpu_seconds * 1_000_000_000 - charged["process_cpu_ns"]
    exact_wall_ns = Fraction(base.wall_seconds) * 1_000_000_000
    remaining_wall_ns = exact_wall_ns.numerator // exact_wall_ns.denominator - charged["monotonic_ns"]
    cpu_seconds, unused_cpu_ns = divmod(remaining_cpu_ns, 1_000_000_000)
    remaining_wall_seconds = math.nextafter(remaining_wall_ns / 1_000_000_000, -math.inf)
    need(cpu_seconds >= 1 and math.isfinite(remaining_wall_seconds) and
         remaining_wall_seconds > base.cleanup_seconds > base.poll_seconds > 0,
         "Observed construction/preparation cost leaves no positive usable worker budget")
    remaining_logical = {key: logical[key] - charged["logical_delta"][key] for key in logical}
    need(all(value > 0 for value in remaining_logical.values()),
         "Observed construction/preparation cost exhausts the explicit logical budget")
    limits = replace(base, cpu_seconds=cpu_seconds, wall_seconds=remaining_wall_seconds)
    observation = {"base_runtime_limits": asdict(base), "base_logical_limits": logical,
                   "charged_observed_cost": charged, "remaining_runtime_limits": asdict(limits),
                   "remaining_logical_limits": remaining_logical,
                   "unused_cpu_ns_after_integer_RLIMIT_floor": unused_cpu_ns,
                   "qualification": "unavailable: process/logical measurements and per-process limits do not establish aggregate whole-job or publication-tail budget compliance"}
    return replace(config, limits=limits), remaining_logical, observation


def _prefix(row, prefix):
    return dict(row, path=prefix + "/" + row["path"])


def _file_pin(row):
    from .runner import FilePin
    need(type(row) is dict and set(row) == {"path", "bytes", "sha256", "executable"} and
         type(row["executable"]) is bool, "Closed exact regular-file runtime pin required")
    path = row["path"]
    need(type(path) is str and bool(path) and not PurePosixPath(path).is_absolute() and
         PurePosixPath(path).as_posix() == path and "\\" not in path and
         all(part not in ("", ".", "..") for part in path.split("/")) and
         not any(ord(char) < 32 or ord(char) == 127 for char in path), "Canonical pinned member path")
    need(type(row["bytes"]) is int and 0 <= row["bytes"] < 2**63 and
         type(row["sha256"]) is str and len(row["sha256"]) == 64 and
         all(char in "0123456789abcdef" for char in row["sha256"]), "Exact ordinary member extent/hash")
    return FilePin(**row)


def tree_pin(value):
    from .runner import TreePin
    need(type(value) is dict and set(value) == {"host_path", "members"} and
         type(value["members"]) is list and bool(value["members"]),
         "Finite nonempty pinned runtime/view tree required")
    members = tuple(_file_pin(row) for row in value["members"])
    need(len({row.path for row in members}) == len(members), "Unique pinned tree members required")
    return TreePin(_absolute(value["host_path"]), members)


def run_config(value):
    """Strict JSON-to-dataclass parser; no runtime discovery or qualification bit."""
    from .runner import RunConfig, ExecutablePin, ReadOnlyMount, Limits
    need(type(value) is dict and set(value) == {
        "bubblewrap", "python_guest_path", "mounts", "limits", "forbidden_host_roots"},
        "Closed actual RunConfig selection required")
    binary = value["bubblewrap"]
    need(type(binary) is dict and set(binary) == {"host_path", "bytes", "sha256"},
         "Exact selected bubblewrap executable identity required")
    _absolute(binary["host_path"])
    descriptor({"path": "binary", "bytes": binary["bytes"], "sha256": binary["sha256"]}, 2**63 - 1)
    limits = value["limits"]
    need(type(limits) is dict and set(limits) == {field.name for field in fields(Limits)},
         "Every runtime limit is explicit; no inherited/default allowance")
    for key, number in limits.items():
        if key in ("wall_seconds", "cleanup_seconds", "poll_seconds"):
            need(type(number) in (int, float) and math.isfinite(number) and number > 0,
                 "Finite positive explicit clock limit")
        elif key == "seed":
            need(type(number) is int and 0 <= number <= 4294967295, "Explicit uint32 seed")
        else:
            need(type(number) is int and 0 < number < 2**63, "Positive explicit runtime capacity")
    need(limits["poll_seconds"] < limits["cleanup_seconds"] < limits["wall_seconds"] and
         limits["open_files"] >= 32 and limits["report_bytes"] >= 4096,
         "Usable explicit cleanup, FD and report capacities required before a fit")
    mounts = value["mounts"]
    need(type(mounts) is list and bool(mounts), "Actual finite runtime/source/tool trees required")
    selected = []
    for mount in mounts:
        need(type(mount) is dict and set(mount) == {"tree", "guest_path"}, "Closed readonly mount required")
        guest = _absolute(mount["guest_path"])
        need(guest not in ("/tools", "/tools/decoder") and not guest.startswith("/tools/decoder/"),
             "Supplied decoder mount is constructed only from this case's actual fixed reference")
        selected.append(ReadOnlyMount(tree_pin(mount["tree"]), guest))
    forbidden = value["forbidden_host_roots"]
    need(type(forbidden) is list and bool(forbidden) and len(set(forbidden)) == len(forbidden),
         "Explicit actual private input exclusion roots required")
    return RunConfig(ExecutablePin(**binary), _absolute(value["python_guest_path"]),
                     tuple(selected), Limits(**limits), tuple(_absolute(path) for path in forbidden))


def require_matched_resource_envelope(reference_config, candidate_config):
    """Require equal actual worker capacities before reference fitting.

    CPU/wall and finite capture/admission totals may differ for the complete
    seven-arm reference. This does not qualify native/aggregate enforcement.
    """
    from .runner import Limits
    need(type(reference_config.limits) is Limits and type(candidate_config.limits) is Limits,
         "Actual typed reference and candidate Limits required")
    matched, separate = set(MATCHED_LIMIT_FIELDS), set(SEPARATE_LIMIT_FIELDS)
    need(len(matched) == len(MATCHED_LIMIT_FIELDS) == 9 and
         len(separate) == len(SEPARATE_LIMIT_FIELDS) == 9 and not matched & separate and
         matched | separate == {field.name for field in fields(Limits)},
         "Every actual Limits field needs an explicit matched or separate classification")
    for name in MATCHED_LIMIT_FIELDS:
        need(getattr(reference_config.limits, name) == getattr(candidate_config.limits, name),
             "Reference FULL decoder and generic candidate must match " + name)


def _no_native_parent():
    forbidden = ("numpy", "scipy", "torch", "cv2", "av", "h5py")
    need(not any(name == prefix or name.startswith(prefix + ".")
                 for name in sys.modules for prefix in forbidden),
         "execute requires a fresh stdlib-only parent process; stage/compare must run separately")


def _mounted_entry(config, entry):
    _absolute(entry)
    matches = [member for mount in config.mounts for member in mount.tree.members
               if mount.guest_path + "/" + member.path == entry]
    need(len(matches) == 1, "Entry script must be one exact selected readonly source/tool member")


def _exact_input_tree(tree, descriptors):
    expected = {}
    for row in descriptors:
        descriptor(row, 2**63 - 1)
        need(row["path"] not in expected or expected[row["path"]] == row,
             "One physical input cannot have conflicting observed identities")
        expected[row["path"]] = row
    actual = {member.path: {"path": member.path, "bytes": member.bytes, "sha256": member.sha256}
              for member in tree.members}
    need(actual == expected and all(not member.executable for member in tree.members),
         "Only the complete exact agreed input-file closure may enter this candidate-visible tree")


def _common_tools(config, selected):
    need(type(selected) is list, "Explicit prefit common-tool classification and complete pins required")
    seen = {}
    for row in selected:
        need(type(row) is dict and set(row) == {"guest_path", "role", "tree"} and
             row["guest_path"] in COMMON_TOOL_ROLES and row["role"] == COMMON_TOOL_ROLES[row["guest_path"]] and
             row["guest_path"] not in seen, "Closed unique ordinary common-tool role required")
        seen[row["guest_path"]] = tree_pin(row["tree"])
    actual = {mount.guest_path: mount.tree for mount in config.mounts if mount.guest_path.startswith("/tools/")}
    need(actual == seen, "Every common tool mount must match the complete prefit classified selection; no extra tools")
    return [{"guest_path": guest, "role": COMMON_TOOL_ROLES[guest], "tree": asdict(seen[guest])}
            for guest in sorted(seen)]


def _validate_view(plan, case, row, context, backend, owner, expected_stream):
    """Reconstruct the exact candidate-visible file closure, not just CASE membership."""
    from .operator import restore_plan
    from .features import BLOCK_DIMS
    view = tree_pin(row["view"])
    case_document = _document(view.host_path, row["case_input"], owner)
    base = {"schema", "backend", "assignment", "assignment_sha256", "case_id", "units", "video_ids", "blocks",
            "training_coordinates", "query_coordinates", "personal_coordinates", "personal", "training_targets",
            "logical_limits", "target_contract", "access_scope", "authority"}
    extra = {"shared"} if backend == "full_svd_materialized" else {
        "stream_spec", "stream_metadata_captures", "mount_contract"}
    need(type(case_document) is dict and set(case_document) == base | extra and
         case_document["schema"] == "neural080_generalization_case_input_v1" and
         case_document["case_id"] == case.case_id and case_document["backend"] == backend and
         case_document["units"] == "original_eeg" and case_document["blocks"] == BLOCK_DIMS and
         case_document["assignment_sha256"] == plan.assignment_sha256 and
         restore_plan(case_document["assignment"]) == plan and
         case_document["logical_limits"] == row["worker_logical_limits"],
         "Closed actual case schema, method, split and worker resource contract required")
    train, query = tuple(case.training_coordinates()), tuple(case.query_coordinates())
    for label, coordinates in (("training_coordinates", train), ("query_coordinates", query),
                               ("personal_coordinates", train + query)):
        supplied = case_document[label]
        need(type(supplied) is list and all(type(item) is list and len(item) == 2 and
             type(item[0]) is str and type(item[1]) is int for item in supplied) and
             supplied == [list(item) for item in coordinates], "Exact selected visible case coordinates")
    need(type(case_document["video_ids"]) is list and all(type(video) is int for video in case_document["video_ids"]) and
         tuple(case_document["video_ids"]) == VIDEO_IDS, "All fixed shared video identities")
    expected = []
    def add(pin, name):
        descriptor(pin, 2**63 - 1)
        need(pin["path"] == name, "Exact generated case-visible basename required")
        expected.append(pin)
    add(row["case_input"], "CASE.json")
    add(row["context"], "CONTEXT.json")
    add(case_document["training_targets"], "training-targets.npy")
    personal = case_document["personal"]
    need(type(personal) is dict and set(personal) == {"eye", "timing"}, "Only permitted personal feature roles")
    for name in ("eye", "timing"):
        add(personal[name], "personal-" + name + ".npy")
    if backend == "full_svd_materialized":
        shared = case_document["shared"]
        need(type(shared) is dict and set(shared) == set(BLOCK_DIMS), "All six fixed shared blocks")
        for name in BLOCK_DIMS:
            add(shared[name], "shared-" + name + ".npy")
    else:
        add(case_document["stream_spec"], "STREAM_INPUT.json")
        guest = _document(view.host_path, case_document["stream_spec"], owner)
        expected_guest = dict(expected_stream)
        expected_guest.update(metadata_root="/tools/feature-metadata", media_root="/tools/media",
                              checkpoint_root="/tools/checkpoint", programme_root="/source")
        canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        need(canonical(guest) == canonical(expected_guest), "Actual guest stream selection must equal the prepared source selection")
        original_map = _document(expected_stream["metadata_root"], expected_stream["source_map_descriptor"], owner)
        selected = {"source_map": expected_stream["source_map_descriptor"], **original_map["evidence"]}
        metadata = case_document["stream_metadata_captures"]
        roles = ("source_map", "audio_presence", "experimental_identity", "provenance_graph")
        need(type(metadata) is list and len(metadata) == 4, "All four source metadata custody copies")
        for role, item in zip(roles, metadata):
            need(type(item) is dict and set(item) == {"role", "original", "captured"} and item["role"] == role and
                 item["original"] == selected[role] and item["captured"]["bytes"] == selected[role]["bytes"] and
                 item["captured"]["sha256"] == selected[role]["sha256"], "Exact original source metadata custody copy")
            add(item["captured"], "source-map.json" if role == "source_map" else "map-evidence-" + role + ".json")
    need(len(expected) == len({pin["path"] for pin in expected}), "No aliased or repeated case-view roles")
    _exact_input_tree(view, expected)
    need(context["case_input_identity"] == row["case_input"], "Context binds this same full visible view schema")
    return view


def _view_row(staged, context):
    members = [{"path": row["path"], "bytes": row["bytes"], "sha256": row["sha256"],
                "executable": False} for row in (*staged["files"], context)]
    need(len({row["path"] for row in members}) == len(members), "Exact fresh case-view census")
    return {"host_path": str(Path(staged["root"]).absolute()), "members": sorted(members, key=lambda row: row["path"])}


def stage(prepared_root, prepared_manifest, selection, output, owner):
    """Create every actual case view; the selected stream route never materializes learned matrices."""
    started = cost_start(owner)
    record = owner.begin("stage_complete_generalization_campaign")
    answer = None
    try:
        from .operator import bind_prepared
        from . import models, staging
        import numpy as np
        need(type(selection) is dict and set(selection) == {"schema", "worker_logical_limits", "programme_tree"} and
             selection["schema"] == "neural080_stage_selection_v1", "Closed stage selection required")
        logical_limits = _limits(selection["worker_logical_limits"])
        programme_tree = tree_pin(selection["programme_tree"])
        programme_members = [asdict(member) for member in programme_tree.members]
        need({"neural080.py", "source/generalization/__init__.py"} <=
             {member.path for member in programme_tree.members}, "Complete concrete package bootstrap required")
        prepared_root = _absolute(str(prepared_root))
        prepared, plan, pool_descriptor, feature_descriptor = bind_prepared(prepared_root, prepared_manifest, owner)
        backend = prepared["backend"]
        need(backend in BACKENDS, "Explicit selected full readout backend required")
        pool_root = str(Path(prepared_root) / "pool")
        pool = _document(pool_root, pool_descriptor, owner)
        writer = Writer(_absolute(str(output)), owner)
        views_root = writer.root / "views"
        views_root.mkdir()
        if backend == "full_svd_materialized":
            shared, personal = staging.materialize_features(str(Path(prepared_root) / "features"),
                                                           feature_descriptor, pool_root, pool_descriptor, owner)
            feature_pool = models.capture_feature_pool(shared, personal, owner)
            stream_document = None
        else:
            need(feature_descriptor is None, "Stream route cannot silently substitute cached learned matrices")
            stream_document = _document(prepared_root, prepared["stream"], owner)
            from .feature_stream import parse_stream_spec, validate_programme_tree
            stream_spec = parse_stream_spec(stream_document, owner)
            need(programme_tree.host_path == stream_spec.programme_root, "Exact selected whole programme source root")
            validate_programme_tree(stream_spec, programme_members)
            personal = staging.materialize_personal(pool_root, pool_descriptor, owner)
            feature_pool = None
        subjects = pool["subjects"]
        need(type(subjects) is list and [row.get("subject") for row in subjects] == list(PERSONS),
             "Complete actual private EEG source roster required for trusted staging")
        targets = {}
        for row in subjects:
            shape = (1102, 127, 150)
            body = capture_array(pool_root, row["arrays"]["eeg_unscaled"], shape, owner)
            targets[row["subject"]] = decode_array(body, shape, owner)
        views = []
        for case in outer_cases(plan):
            train = tuple(case.training_coordinates())
            indices = np.asarray(case.training_video_ids, dtype=np.int64) - 1
            owner.reserve("retained_bytes", len(train) * 127 * 150 * 8 * 2)
            raw = np.concatenate([np.asarray(targets[person][indices], dtype=np.float64)
                                  for person in case.training_persons], axis=0)
            training = models.capture_training_targets(train, raw, owner)
            if backend == "full_svd_materialized":
                staged = staging.stage_case(plan, case, feature_pool, training, owner,
                                            views_root / case.case_id, logical_limits)
            else:
                staged = staging.stage_stream_case(plan, case, stream_document, personal, training,
                                                   owner, views_root / case.case_id, logical_limits)
            need(staged["document"]["backend"] == backend, "Actual staged backend must equal selected backend")
            context = {"schema": "neural080_case_context_v1", "case_id": case.case_id,
                       "assignment_sha256": plan.assignment_sha256, "backend": backend,
                       "case_input_identity": dict(staged["manifest"]),
                       "target_manifest_identity": dict(pool_descriptor),
                       "prepared_manifest_identity": dict(prepared_manifest),
                       "programme_tree_members": programme_members}
            view_writer = Writer.__new__(Writer)
            view_writer.root = Path(staged["root"])
            view_writer.owner = owner
            view_writer.files = []
            context_pin = view_writer.document("CONTEXT.json", context)
            views.append({"case_id": case.case_id, "view": _view_row(staged, context_pin),
                          "case_input": dict(staged["manifest"]), "context": context_pin,
                          "worker_logical_limits": logical_limits})
            del raw, training
        result = {"schema": "neural080_staged_campaign_v1", "backend": backend,
                  "assignment_sha256": plan.assignment_sha256,
                  "programme_tree": asdict(programme_tree),
                  "assignment": prepared["assignment"], "prepared_root": prepared_root,
                  "prepared_manifest": dict(prepared_manifest), "private_pool_root": pool_root,
                  "target_manifest_identity": dict(pool_descriptor), "views": views,
                  "column_width": None if stream_document is None else stream_document["column_width"],
                  "common_staging_cost": {**observed_cost(started, owner),
                      "scope": "Actual stage phase through before STAGED_CAMPAIGN serialization, including all thirty views; final publication and native aggregate costs are not self-measured",
                      "native_aggregate_cost": "Unavailable without independent host counters and end-to-end qualification"},
                  "scope": "Complete thirty TRAIN/QUERY feature views with only raw outer TRAIN EEG; no qualification or new freshness"}
        manifest = writer.document("STAGED_CAMPAIGN.json", result)
        answer = {"manifest": manifest, "staged": result, "output": str(writer.root)}
    except BaseException as exc:
        owner.failure(record, exc)
    owner.complete(record)
    return answer


def _output_pin(observation, name):
    value = observation["outputs"][name]
    row = {"path": name, "bytes": value["bytes"], "sha256": value["sha256"]}
    descriptor(row, 2**63 - 1)
    return row


def _check_output_descriptor(row, observation):
    descriptor(row, 2**63 - 1)
    need(row["path"] in observation["outputs"] and row == _output_pin(observation, row["path"]),
         "Every published reference operand must join actual isolated-run captured bytes")
    return row


def _prefix_case(value, prefix, observation):
    if type(value) is dict:
        if set(value) == {"path", "bytes", "sha256"}:
            return _prefix(_check_output_descriptor(value, observation), prefix)
        return {key: _prefix_case(item, prefix, observation) for key, item in value.items()}
    if type(value) is list:
        return [_prefix_case(item, prefix, observation) for item in value]
    return value


def _decoder_tree(reference_output, reference_case, observation, output, owner):
    """Copy only the actual closed numeric FULL decoder, never query predictions."""
    from .models import decoder_members
    from .runner import TreePin, FilePin
    model_pin = _check_output_descriptor(reference_case["final_models"]["full"], observation)
    model_document = _document(reference_output, model_pin, owner)
    decoder_pin = _check_output_descriptor(model_document["decoder"], observation)
    decoder_document = _document(reference_output, decoder_pin, owner)
    members = decoder_members(decoder_document)
    writer = Writer(output, owner)
    copied = []
    for row in (decoder_pin, *members):
        _check_output_descriptor(row, observation)
        need("/" not in row["path"] and "prediction" not in row["path"].lower(),
             "Only closed TRAIN-fitted decoder state may enter the supplied tool tree")
        body = capture(reference_output, row, owner, max_bytes=row["bytes"])
        copied.append(writer.put(row["path"], body))
    need(len({row["path"] for row in copied}) == len(copied), "Closed unique numeric decoder closure required")
    return TreePin(str(writer.root), tuple(FilePin(row["path"], row["bytes"], row["sha256"], False)
                                         for row in sorted(copied, key=lambda row: row["path"]))), decoder_pin["path"]


def execute(stage_root, staged_manifest, selection, output, owner):
    """Stdlib-only parent: thirty fixed controls plus four fresh candidate cases each.

    Reference controls have their separate seven-arm campaign allowance. Every
    candidate starts with the same base budget. Common preparation is charged
    equally; augmented cells additionally debit their actual observed FULL
    construction before receiving residual CPU/wall/logical allowances. Native
    aggregate and publication-tail qualification remain held. No subset escapes.
    """
    _no_native_parent()
    from .operator import bind_prepared
    from .runner import CaseRequest, OutputMember, ReadOnlyMount, run_case
    from .reference import output_names
    record = owner.begin("execute_complete_generalization_campaign")
    answer = None
    try:
        need(type(selection) is dict and set(selection) == {
            "schema", "reference_config", "candidate_config", "reference_entry",
            "candidate_entry", "candidate_programme_id", "common_tools", "candidate_logical_budget"} and
            selection["schema"] == "neural080_execution_selection_v1", "Closed execution selection required")
        staged = _document(stage_root, staged_manifest, owner)
        need(type(staged) is dict and staged.get("schema") == "neural080_staged_campaign_v1" and
             staged.get("backend") in BACKENDS, "Actual full staged campaign required")
        prepared, plan, pool_descriptor, _ = bind_prepared(staged["prepared_root"], staged["prepared_manifest"], owner)
        need(staged["assignment_sha256"] == plan.assignment_sha256 and
             staged["target_manifest_identity"] == pool_descriptor and
             staged["backend"] == prepared["backend"], "Stage/preparation/target identity joins required")
        reference_config = run_config(selection["reference_config"])
        candidate_config = run_config(selection["candidate_config"])
        need(reference_config.bubblewrap == candidate_config.bubblewrap and
             reference_config.python_guest_path == candidate_config.python_guest_path and
             reference_config.mounts == candidate_config.mounts and
             reference_config.forbidden_host_roots == candidate_config.forbidden_host_roots,
             "Reference/candidate runtime/source inputs must be the same; explicit control budgets may differ")
        require_matched_resource_envelope(reference_config, candidate_config)
        common_tools = _common_tools(candidate_config, selection["common_tools"])
        need(selection["reference_entry"] == "/source/neural080.py", "Fixed complete source reference bootstrap")
        source_mounts = [mount for mount in candidate_config.mounts if mount.guest_path == "/source"]
        need(len(source_mounts) == 1 and asdict(source_mounts[0].tree) ==
             asdict(tree_pin(staged["programme_tree"])), "Actual whole /source runtime tree equals prebound staged programme")
        source_members = [asdict(member) for member in source_mounts[0].tree.members]
        need({"neural080.py", "source/generalization/__init__.py"} <=
             {member.path for member in source_mounts[0].tree.members}, "Pinned concrete package bootstrap")
        stream_document = None
        if staged["backend"] == "streamed_dual_certified":
            from .feature_stream import parse_stream_spec, validate_programme_tree
            stream_document = _document(staged["prepared_root"], prepared["stream"], owner)
            stream_spec = parse_stream_spec(stream_document, owner)
            validate_programme_tree(stream_spec, source_members)
            mounts = {mount.guest_path: mount.tree.host_path for mount in candidate_config.mounts}
            need(all(mounts.get(guest) == expected for guest, expected in (
                ("/source", stream_spec.programme_root), ("/tools/media", stream_spec.media_root),
                ("/tools/checkpoint", stream_spec.checkpoint_root),
                ("/tools/feature-metadata", stream_spec.metadata_root))),
                "Stream worker receives exactly the pinned source/media/checkpoint/metadata roots")
            mounted = {mount.guest_path: mount.tree for mount in candidate_config.mounts}
            source_map_document = _document(stream_spec.metadata_root, stream_spec.source_map_descriptor.row(), owner)
            evidence = source_map_document["evidence"]
            need(type(evidence) is dict and set(evidence) == {"experimental_identity", "audio_presence", "provenance_graph"},
                 "Only the complete agreed source-map evidence roles")
            _exact_input_tree(mounted["/tools/feature-metadata"],
                              (stream_spec.source_map_descriptor.row(), *evidence.values()))
            _exact_input_tree(mounted["/tools/media"], tuple(role.source_media for role in stream_spec.source_map.roles))
            _exact_input_tree(mounted["/tools/checkpoint"], (stream_spec.checkpoint.row(),))
        private_root = _absolute(staged["private_pool_root"])
        need(private_root == str(Path(staged["prepared_root"]) / "pool") and
             any(private_root == root or private_root.startswith(root + "/")
                 for root in candidate_config.forbidden_host_roots),
             "Actual private target pool must lie in the runner's excluded roots")
        for config, entry in ((reference_config, selection["reference_entry"]),
                              (candidate_config, selection["candidate_entry"])):
            _mounted_entry(config, entry)
        need(type(selection["candidate_programme_id"]) is str and bool(selection["candidate_programme_id"]),
             "Actual selected candidate programme identity required")
        common_cost = combine_cost(cost_profile(prepared["common_preparation_cost"]),
                                   cost_profile(staged["common_staging_cost"]))
        allocations = common_allocations(common_cost)
        candidate_logical_budget = _limits(selection["candidate_logical_budget"])
        cases = outer_cases(plan)
        views = staged["views"]
        need(type(views) is list and len(views) == 30 and
             [row.get("case_id") for row in views] == [case.case_id for case in cases],
             "Every staged case in exact selected order required")
        writer = Writer(_absolute(str(output)), owner)
        common_tool_manifest = writer.document("PREFIT_COMMON_TOOLS.json", {
            "schema": "neural080_prefit_common_tools_v1", "tools": common_tools,
            "selection_phase": "Captured before any reference TRAIN fit in this campaign",
            "eligibility": "Pinned role classification and observed bodies require independent source/exposure review; metadata cannot prove absence of previously learned state"})
        for directory in ("reference", "candidate", "logs", "decoder"):
            (writer.root / directory).mkdir()
        for index in range(len(CANDIDATE_KEYS)):
            (writer.root / "candidate" / ("panel-%02d" % index)).mkdir()
        reference_cases, candidate_cases, observations = [], {key: [] for key in CANDIDATE_KEYS}, []
        budget_observations = []
        for case_index, (case, row) in enumerate(zip(cases, views)):
            need(type(row) is dict and set(row) == {"case_id", "view", "case_input", "context", "worker_logical_limits"},
                 "Closed full case-view record required")
            view = tree_pin(row["view"])
            member_map = {member.path: member for member in view.members}
            for pin in (row["case_input"], row["context"]):
                descriptor(pin, DOCUMENT_LIMIT)
                member = member_map.get(pin["path"])
                need(member is not None and (member.bytes, member.sha256) == (pin["bytes"], pin["sha256"]),
                     "CASE and context identities must belong to the actual view census")
            context = _document(view.host_path, row["context"], owner)
            need(context["schema"] == "neural080_case_context_v1" and context["case_id"] == case.case_id and
                 context["assignment_sha256"] == plan.assignment_sha256 and
                 context["target_manifest_identity"] == pool_descriptor and
                 context["case_input_identity"] == row["case_input"] and
                 context["backend"] == staged["backend"] and
                 context["programme_tree_members"] == source_members,
                 "Actual case context binds split, inputs, target pool and complete source tree")
            view = _validate_view(plan, case, row, context, staged["backend"], owner, stream_document)
            logical = _limits(row["worker_logical_limits"])
            argv = (reference_config.python_guest_path, selection["reference_entry"], "worker-reference",
                    "--case", "/view/CASE.json", "--bytes", str(row["case_input"]["bytes"]),
                    "--sha256", row["case_input"]["sha256"], "--context-bytes", str(row["context"]["bytes"]),
                    "--context-sha256", row["context"]["sha256"], "--output", "/output",
                    "--logical-limits", json.dumps(logical, sort_keys=True, separators=(",", ":")))
            names = output_names(case, backend=staged["backend"], column_width=staged["column_width"],
                                 max_members=reference_config.limits.output_members)
            reference_output = writer.root / "reference" / case.case_id
            reference_request = CaseRequest(case.case_id, "fixed-full-seven-arm-reference", MODES[0], view, argv,
                tuple(OutputMember(name, min(reference_config.limits.file_bytes, reference_config.limits.output_bytes)) for name in names),
                str(reference_output), str(writer.root / "logs" / (case.case_id + ".reference")))
            _no_native_parent()
            reference_observation = run_case(reference_config, reference_request)
            observations.append(writer.document(case.case_id + ".reference.runner.json", reference_observation))
            envelope = _document(reference_output, _output_pin(reference_observation, "CASE_REFERENCE.json"), owner)
            need(type(envelope) is dict and set(envelope) == {"schema", "case_context", "context_sha256", "reference",
                 "worker_preparation_cost", "complete_reference_call_cost", "full_decoder_debit", "debit_scope", "native_aggregate_cost"} and
                 envelope["schema"] == "neural080_worker_reference_v1" and
                 envelope["case_context"] == row["context"] and envelope["context_sha256"] == row["context"]["sha256"],
                 "Actual worker output must bind the exact independently captured case context")
            reference_case = envelope["reference"]
            need(reference_case["case_id"] == case.case_id and
                 reference_case["feature_backend"] == staged["backend"],
                 "Actual reference case and selected feature backend identity")
            full_cost_pin = _check_output_descriptor(reference_case["full_arm_cost"], reference_observation)
            full_cost_document = _document(reference_output, full_cost_pin, owner)
            need(full_cost_document["schema"] == "neural080_full_arm_cost_v1" and
                 full_cost_document["case_id"] == case.case_id and full_cost_document["assignment_sha256"] == plan.assignment_sha256 and
                 full_cost_document["feature_backend"] == staged["backend"] and
                 type(full_cost_document["actual_full_ridge_fits"]) is int and full_cost_document["actual_full_ridge_fits"] == 261,
                 "Actual complete FULL-only cost attribution required")
            full_debit = combine_cost(validate_cost(envelope["worker_preparation_cost"], positive=True),
                subtract_cost(validate_cost(envelope["complete_reference_call_cost"], positive=True),
                              full_cost_document["excluded_cost"]))
            validate_cost(full_debit, positive=True)
            need(full_debit == envelope["full_decoder_debit"], "Worker FULL debit equals complete observed call minus actual exclusions plus preparation")
            reference_cases.append(_prefix_case(reference_case, "reference/" + case.case_id, reference_observation))
            decoder, decoder_name = _decoder_tree(reference_output, reference_case, reference_observation,
                                                  writer.root / "decoder" / case.case_id, owner)
            for index, ((mode, regime), key) in enumerate(zip(CANDIDATE_CELLS, CANDIDATE_KEYS)):
                charge = allocations[case_index]
                if regime == "agent_plus_supplied_decoder":
                    charge = combine_cost(charge, full_debit)
                config, residual_logical, budget = remaining_budget(candidate_config, candidate_logical_budget, charge)
                if regime == "agent_plus_supplied_decoder":
                    config = replace(config, mounts=config.mounts + (ReadOnlyMount(decoder, "/tools/decoder"),))
                budget_observations.append({"case_id": case.case_id, "access_mode": mode, "tool_regime": regime,
                    "common_allocation": allocations[case_index], "full_decoder_debit": full_debit if regime == "agent_plus_supplied_decoder" else None,
                    "budget": budget})
                argv = (config.python_guest_path, selection["candidate_entry"], "--case", "/view/CASE.json",
                        "--output", "/output/PREDICTION.npy", "--mode", mode, "--tool-regime", regime,
                        "--logical-limits", json.dumps(residual_logical, sort_keys=True, separators=(",", ":")),
                        "--budget", json.dumps(budget, sort_keys=True, separators=(",", ":")))
                if regime == "agent_plus_supplied_decoder":
                    argv += ("--decoder", "/tools/decoder/" + decoder_name)
                candidate_path = writer.root / "candidate" / ("panel-%02d" % index) / case.case_id
                request = CaseRequest(case.case_id, selection["candidate_programme_id"], mode, view, argv,
                    (OutputMember("PREDICTION.npy", array_limit((len(case.query_video_ids), 127, 150))),),
                    str(candidate_path), str(writer.root / "logs" / (case.case_id + ".candidate-%02d" % index)))
                _no_native_parent()
                observed = run_case(config, request)
                observations.append(writer.document(case.case_id + ".candidate-%02d.runner.json" % index, observed))
                prediction = _prefix(_output_pin(observed, "PREDICTION.npy"),
                                     "candidate/panel-%02d/" % index + case.case_id)
                candidate_cases[key].append({"case_id": case.case_id,
                    "query_coordinates": [list(coordinate) for coordinate in case.query_coordinates()],
                    "prediction": prediction})
        reference_panel = {"schema": "neural080_reference_panel_v1", "assignment_sha256": plan.assignment_sha256,
            "units": "original_eeg", "arms": list(ARMS), "cases": reference_cases,
            "actual_ridge_fit_count": sum(row["actual_ridge_fit_count"] for row in reference_cases),
            "target_manifest_identity": dict(pool_descriptor),
            "historical_scope": "Developmental public crossvalidation; no freshness or competence claim."}
        validate_reference(plan, reference_panel)
        reference_manifest = writer.document("REFERENCE_PANEL.json", reference_panel)
        candidate_manifests = {}
        for index, ((mode, regime), key) in enumerate(zip(CANDIDATE_CELLS, CANDIDATE_KEYS)):
            panel = {"schema": "neural080_candidate_panel_v1", "assignment_sha256": plan.assignment_sha256,
                     "access_mode": mode, "tool_regime": regime, "units": "original_eeg", "cases": candidate_cases[key]}
            validate_candidate(plan, mode, regime, panel)
            candidate_manifests[key] = writer.document("CANDIDATE_PANEL_%02d.json" % index, panel)
        result = {"schema": "neural080_executed_campaign_v1", "assignment_sha256": plan.assignment_sha256,
                  "staged_manifest": dict(staged_manifest), "staged_root": _absolute(str(stage_root)),
                  "target_manifest_identity": dict(pool_descriptor), "reference_manifest": reference_manifest,
                  "candidate_manifests": candidate_manifests, "runner_observations": observations,
                  "reference_run_count": 30, "candidate_run_count": 120,
                  "fixed_reference_prediction_count": 210, "candidate_prediction_count": 120,
                  "prefit_common_tools": common_tool_manifest,
                  "common_unique_unamortized_cost": common_cost,
                  "common_allocations_in_case_order": list(allocations),
                  "per_condition_budget_debits": budget_observations,
                  "budget_qualification": "unavailable: diagnostic observed debits only; aggregate/native/end-to-end and receipt-tail measurement remain genuine host gates",
                  "candidate_budget_protocol": "Candidate --budget carries actual base, charged and residual runtime limits plus rounding/qualification scope; --logical-limits carries its selected residual counters. CASE.logical_limits is the separate reference worker limit and is not a candidate allowance.",
                  "shared_cost_policy": "Prepare plus stage allocated by integer quotient/remainder across thirty cases; each condition pays the same case allocation. Each augmented condition pays its case FULL construction debit in full. The decoder was physically built once, not rerun per condition; charges describe matched counterfactual budgets, not extra observed work.",
                  "candidate_budget": asdict(candidate_config.limits),
                  "separate_fixed_control_budget": asdict(reference_config.limits),
                  "source_status": "Actual completed calls and byte identities only; protected admission/score remains a separate phase"}
        manifest = writer.document("EXECUTED_CAMPAIGN.json", result)
        _no_native_parent()
        answer = {"manifest": manifest, "executed": result, "output": str(writer.root)}
    except BaseException as exc:
        owner.failure(record, exc)
    owner.complete(record)
    return answer


def compare(execution_root, execution_manifest, output, owner):
    """Separate process: capture all390 operands, then open protected target pool."""
    from .operator import bind_prepared
    from .artifacts import capture_panel
    from .scoring import compare as protected_compare
    record = owner.begin("admit_and_compare_complete_executed_campaign")
    answer = None
    try:
        execution = _document(execution_root, execution_manifest, owner)
        need(execution.get("schema") == "neural080_executed_campaign_v1" and
             execution.get("reference_run_count") == 30 and execution.get("candidate_run_count") == 120,
             "Complete actual run panel required; no successful subset")
        staged = _document(execution["staged_root"], execution["staged_manifest"], owner)
        prepared, plan, pool_descriptor, _ = bind_prepared(staged["prepared_root"], staged["prepared_manifest"], owner)
        need(execution["assignment_sha256"] == staged["assignment_sha256"] == plan.assignment_sha256 and
             execution["target_manifest_identity"] == staged["target_manifest_identity"] == pool_descriptor and
             set(execution["candidate_manifests"]) == set(CANDIDATE_KEYS), "Exact complete source/split/target/candidate joins")
        writer = Writer(_absolute(str(output)), owner)
        captured = capture_panel(plan, execution_root, execution["reference_manifest"],
            {key: {"root": execution_root, "manifest": execution["candidate_manifests"][key]} for key in CANDIDATE_KEYS},
            writer.root / "admitted", owner, target_manifest_identity=pool_descriptor)
        scored = protected_compare(plan, captured, str(Path(staged["prepared_root"]) / "pool"), pool_descriptor,
                                   writer.root / "scored", owner)
        result = {"schema": "neural080_campaign_comparison_v1", "execution_manifest": dict(execution_manifest),
                  "prediction_archive": _prefix(captured.manifest, "admitted"),
                  "protected_comparison": _prefix(scored["manifest"], "scored"),
                  "assignment_sha256": plan.assignment_sha256, "target_manifest_identity": pool_descriptor,
                  "budget_qualification": execution["budget_qualification"],
                  "scientific_qualification": "unavailable; developmental diagnostic risks do not issue a qualified grade",
                  "per_condition_budget_debits": execution["per_condition_budget_debits"]}
        manifest = writer.document("CAMPAIGN_COMPARISON.json", result)
        answer = {"manifest": manifest, "comparison": result, "output": str(writer.root)}
    except BaseException as exc:
        owner.failure(record, exc)
    owner.complete(record)
    return answer
