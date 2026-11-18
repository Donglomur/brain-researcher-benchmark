"""One complete trusted temporal026 control, with original branch attribution.

This operator code runs only after the separate native admission/bootstrap.
It executes a globally fixed zero rule, not an AI or an eligible assistance-arm
trial. All original scientific and participant-isolation limits remain.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import time


BRANCHES = ("source_positional_cv", "named_response_columns")
EXPECTED_RETURNED_BYTES = 9387131288
EXPECTED_SOURCE_READS = 28440
INTERFACE_BYTES = {"source_positional_cv": 40693215,
                   "named_response_columns": 40697009}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode() + b"\n"


def load_bytes_module(name, filename, raw):
    spec = importlib.util.spec_from_file_location(name, filename)
    module = importlib.util.module_from_spec(spec)
    exec(compile(raw, str(filename), "exec"), module.__dict__)
    return module


class WriteBudget:
    """Precharge writes or a whole fixed source envelope; never refund failures."""
    def __init__(self, cap):
        self.cap = cap
        self.charged = 0
        self.entries = []

    def charge(self, name, size, basis):
        require(type(size) is int and size >= 0 and self.charged + size <= self.cap,
                "cumulative control artifact allowance exceeded")
        self.charged += size
        self.entries.append({"name": name, "bytes": size, "basis": basis})

    def write(self, path, value, cap):
        raw = encoded(value)
        require(len(raw) <= cap, "bounded control report exceeded")
        self.charge(str(Path(path).name), len(raw), "exact bytes precharged before exclusive write")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o400)
        return {"path": Path(path).name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


class SourceReads:
    """Whitelist and account calls to the unchanged authentic member reader.

    The original implementation still performs all extent/hash/stability checks.
    A failed call retains its complete requested-byte allowance, not an invented
    count of returned bytes. Runtime/source/import reads are separate.
    """
    def __init__(self, input_root, bindings, original_read, checkpoint):
        self.root = str(Path(input_root))
        self.original = original_read
        self.checkpoint = checkpoint
        self.rows = {}
        for role, values, calls in [("response", bindings["responses"], 100),
                                     ("variable", bindings["variables"], 4108)]:
            for name, pin in values.items():
                require(pin["path"] not in self.rows, "unique original input paths required")
                self.rows[pin["path"]] = {"role": role, "name": name, "pin": pin,
                                          "expected_calls": calls, "attempts": 0,
                                          "returned_bytes": 0, "unknown_failed_allowance": 0}
        require(len(self.rows) == 84, "all79responses andfivevariables required")
        self.attempts = self.returned = self.requested = 0

    def __call__(self, root, pin):
        self.checkpoint()
        require(str(Path(root)) == self.root and type(pin) is dict and
                pin.get("path") in self.rows, "read outside admitted original input bank")
        row = self.rows[pin["path"]]
        require(pin == row["pin"] and row["attempts"] < row["expected_calls"],
                "changed input pin or original-read multiplicity exceeded")
        row["attempts"] += 1
        self.attempts += 1
        allowance = pin["bytes"] + 1
        self.requested += allowance
        require(self.attempts <= EXPECTED_SOURCE_READS and
                self.requested <= EXPECTED_RETURNED_BYTES + EXPECTED_SOURCE_READS,
                "complete authentic read allowance exceeded")
        try:
            raw = self.original(root, pin)
        except BaseException:
            row["unknown_failed_allowance"] += allowance
            raise
        require(type(raw) is bytes and len(raw) == pin["bytes"], "source reader return extent changed")
        row["returned_bytes"] += len(raw)
        self.returned += len(raw)
        self.checkpoint()
        return raw

    def summary(self, complete=False):
        if complete:
            require(self.attempts == EXPECTED_SOURCE_READS and self.returned == EXPECTED_RETURNED_BYTES,
                    "full source-read support/count differs")
            require(all(row["attempts"] == row["expected_calls"] and
                        row["returned_bytes"] == row["pin"]["bytes"] * row["expected_calls"] and
                        not row["unknown_failed_allowance"] for row in self.rows.values()),
                    "source input multiplicities or failed allowances differ")
        return {"logical_source_read_attempts": self.attempts,
                "logical_source_returned_bytes": self.returned,
                "logical_source_requested_allowance_including_eof_probes": self.requested,
                "rows": list(self.rows.values()),
                "scope": "application calls only; not downloads, runtime imports or kernel/physical IO"}


def inspect_observation(protocol, job, observation):
    """Check complete original shape/identity metadata without copying responses."""
    info = protocol.job_info(job["id"])
    require(observation["protocol_sha256"] == protocol.protocol_sha256 and
            observation["method_sha256"] == protocol.method_sha256 and
            observation["plan_sha256"] == protocol.plan_sha256 and
            observation["condition"] == "paper_data" and observation["job"] == job and
            observation["column_branch"] == info["column_branch"], "observation identity changed")
    require([x["source_row"] for x in observation["training"]] == info["train_rows"] and
            [x["source_row"] for x in observation["queries"]] == info["prediction_rows"],
            "original ordered training/query support changed")
    require(all(set(row) == {"source_row", "trial_type", "img_cat", "temp_cond"}
                for row in observation["queries"]), "query includes unexpected payload")
    require(all(len(row["response"]) == 819 for row in observation["training"]),
            "complete819sample training observations required")
    require(len(observation["variables"]["t"]) == 819, "original time support changed")
    return len(observation["queries"])


def fixed_score_checks(score, protocol):
    """Same zero rule must agree across paired source comparison slots.

    Regional bootstrap draws deliberately advance across slots and are not
    required to agree. These checks do not impose a scientific effect threshold.
    """
    require(score["protocol_sha256"] == protocol.protocol_sha256 and
            score["plan_sha256"] == protocol.plan_sha256 and
            score["method_sha256"] == protocol.method_sha256 and
            score["condition"] == "paper_data" and
            score["source_branch"] == protocol.plan["cv_column_branch"],
            "source score protocol/plan/method/condition/branch join differs")
    require(score["complete_job_count"] == 2054 and not score["failures"] and
            score["candidate_status_counts"] == {"submitted": 2054, "failed": 0, "cv": 1896, "full": 158},
            "complete submitted fixed-control support required")
    require(type(score["cv_cells"]) is list and len(score["cv_cells"]) == 1896 and
            all(type(row) is dict and type(row.get("job_id")) is str for row in score["cv_cells"]),
            "exact complete typed CV score rows required")
    cells = {row["job_id"]: row for row in score["cv_cells"]}
    require(len(cells) == 1896, "all1896CV score cells required")
    pairs = 0
    for electrode in protocol.source.replay.cohort():
        for fold in range(12):
            a = cells[electrode["id"] + "/DN-none/fold%02d" % fold]
            b = cells[electrode["id"] + "/DN-S/fold%02d" % fold]
            for key in ("status", "condition_r2", "rounded_condition_r2", "fold_r2"):
                require(encoded(a[key]) == encoded(b[key]), "fixedzero paired source slots differ")
            pairs += 1
    require(type(score["electrode_cv"]) is list and len(score["electrode_cv"]) == 158 and
            all(type(row) is dict and type(row.get("id")) is str and
                type(row.get("scaling")) is str for row in score["electrode_cv"]),
            "exact complete typed electrode score rows required")
    electrodes = {(row["id"], row["scaling"]): row for row in score["electrode_cv"]}
    require(len(electrodes) == 158, "all158electrode/scaling summaries required")
    for electrode in protocol.source.replay.cohort():
        a, b = electrodes[electrode["id"], "none"], electrodes[electrode["id"], "S"]
        require(encoded(a["fold_r2"]) == encoded(b["fold_r2"]) and
                encoded(a["r2"]) == encoded(b["r2"]), "fixedzero electrode slots differ")
    undefined = sum(row["fold_r2"] is None for row in cells.values())
    return {"paired_cv_coordinates_equal": pairs, "paired_electrodes_equal": 79,
            "undefined_fold_scores_preserved": undefined,
            "regional_bootstrap_equality_required": False}


def interface_inventory(directory):
    """Bounded generated-output metadata census; bodies were checked by source."""
    root = Path(directory)
    expected = {"CV_FREEZE.json", "DELIVERY_RECEIPT.json", "predictions"}
    require({p.name for p in root.iterdir()} == expected, "unexpected branch output entries")
    files = [root / "CV_FREEZE.json", root / "DELIVERY_RECEIPT.json"]
    predictions = root / "predictions"
    names = {"prediction-%04d.json" % i for i in range(2054)} | {"MANIFEST.json"}
    require({p.name for p in predictions.iterdir()} == names, "complete source prediction inventory differs")
    files.extend(predictions / name for name in sorted(names))
    size = 0
    for path in files:
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                not (info.st_mode & 0o222), "ordinary readonly exclusive control outputs required")
        size += info.st_size
    return {"files": len(files), "bytes": size}


def collect_branch(protocol, branch, input_root, output_root, delivery_module,
                   zero_rule, budget, checkpoint):
    require(branch in BRANCHES and protocol.plan["cv_column_branch"] == branch,
            "separate original branch required")
    budget.charge(branch, INTERFACE_BYTES[branch],
                  "complete exact integer-zero source-interface envelope; retained in full on failure")
    session = delivery_module.DeliverySession(protocol, Path(output_root) / branch)
    scalar_count = training_rows = 0
    start = time.monotonic()
    for index, job in enumerate(protocol.delivery_jobs):
        checkpoint()
        observation = session.observe(input_root)
        query_count = inspect_observation(protocol, job, observation)
        training_rows += len(observation["training"])
        prediction = zero_rule.predict(query_count)  # sees no observations or source values
        require(type(prediction) is list and len(prediction) == query_count and
                all(type(row) is list and len(row) == 819 and
                    all(type(value) is int and value == 0 for value in row) for row in prediction),
                "globally fixed integer-zero rule changed")
        scalar_count += query_count * 819
        session.submit(predictions=prediction)
        del prediction, observation
    require(index + 1 == 2054 and scalar_count == 18633888 and training_rows == 136512,
            "complete original projection/prediction support differs")
    commitment = session.seal()
    inventory = interface_inventory(session.directory)
    require(inventory == {"files": 2057, "bytes": INTERFACE_BYTES[branch]},
            "fixed source-interface serialization differs from frozen arithmetic")
    checkpoint()
    return {"branch": branch, "protocol_sha256": protocol.protocol_sha256,
            "plan_sha256": protocol.plan_sha256, "observations": 2054,
            "cv_predictions": 1896, "full_predictions": 158,
            "prediction_scalars": scalar_count, "training_rows_projected_ephemerally": training_rows,
            "training_matrix_files_written": 0, "commitment": commitment,
            "interface_inventory": inventory,
            "wall_seconds": time.monotonic() - start,
            "role": "engineering control only; paper_data is a schema tag, not an eligible assistance-arm trial",
            "scientific_qualification": False}


def score_branch(protocol, collected, input_root, output_root, submissions, budget, checkpoint):
    branch = collected["branch"]
    require(branch in BRANCHES and collected["observations"] == 2054 and
            collected["protocol_sha256"] == protocol.protocol_sha256,
            "complete branch commitment required before metric evaluation")
    checkpoint()
    score = submissions.evaluate(Path(output_root) / branch / "predictions", protocol,
                                 collected["commitment"]["submission"]["sha256"], input_root, 19)
    checks = fixed_score_checks(score, protocol)
    pin = budget.write(Path(output_root) / (branch + "-scores.json"), score, 8 * 1024**2)
    checkpoint()
    return {"branch": branch, "score": pin, "fixed_rule_checks": checks,
            "regional": score["figure3_regional_cv"], "scientific_qualification": False}


def stage_interfaces(admission, output, budget):
    staged = {}
    for item in admission.protocol["interface_files"]:
        relative = Path(item["destination"])
        require(not relative.is_absolute() and ".." not in relative.parts and
                len(relative.parts) == 2 and relative.parts[0] in
                ("prediction-interface-v1", "source-model-producer-v1", "source-cv-replay-v1"),
                "selected original source destination required")
        path = output / "trusted_source" / "implementations" / relative
        require(str(relative) not in staged, "duplicate selected source path")
        raw = admission.read_pin(item["source"])
        budget.charge(str(relative), len(raw), "authenticated source byte copy, precharged before exclusive write")
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
            os.fchmod(handle.fileno(), 0o400)
        staged[str(relative)] = (path, raw)
    require(set(staged) == {"prediction-interface-v1/protocol.py", "prediction-interface-v1/delivery.py",
                           "prediction-interface-v1/submissions.py", "source-model-producer-v1/producer.py",
                           "source-cv-replay-v1/replay.py", "source-cv-replay-v1/cohort.json"},
            "exact six original runtime dependencies required")
    return staged


def execute(admission):
    """Finite trusted run: metadata first, both panels frozen, then metrics.

    This function is invoked only by run_control.py after native lease, exact
    runtime and source authentication. It never admits a participant process.
    """
    p = admission.protocol
    require(p["pipeline"] == {"branch_order": list(BRANCHES), "condition": "paper_data",
                             "bootstrap_seed": 19, "expected_interface_bytes": INTERFACE_BYTES},
            "frozen complete pipeline identity differs")
    require(p["output"]["reserved_bytes"] == 128 * 1024**2,
            "exact finite artifact reservation required")
    require(p["source_limits"] == {"calls": EXPECTED_SOURCE_READS,
                                  "returned_bytes": EXPECTED_RETURNED_BYTES,
                                  "requested_bytes_with_eof": EXPECTED_RETURNED_BYTES + EXPECTED_SOURCE_READS},
            "exact original logical read bounds required")
    budget = WriteBudget(p["output"]["reserved_bytes"])
    output = admission.create_output()
    reads = None
    collected, evaluated = [], []
    try:
        # Snapshot the frozen operator protocol. All other metadata already has
        # independently pinned originals and is referenced rather than recopied.
        budget.write(output / "PROTOCOL.json", p, 256 * 1024)
        staged = stage_interfaces(admission, output, budget)
        def module(name, relative):
            path, raw = staged[relative]
            return load_bytes_module(name, path, raw)
        interface = module("temporal_control_interface", "prediction-interface-v1/protocol.py")
        delivery = module("temporal_control_delivery", "prediction-interface-v1/delivery.py")
        submissions = module("temporal_control_submissions", "prediction-interface-v1/submissions.py")
        zero_raw = admission.read_pin(p["zero_rule"])
        zero = load_bytes_module("temporal_control_zero", p["zero_rule"]["path"], zero_raw)
        bindings = json.loads(admission.read_pin(p["input_bindings"]))
        prior = json.loads(admission.read_pin(p["prior_input_join"]))
        source = interface.Source(staged["source-model-producer-v1/producer.py"][0].parent)
        require(source.replay.digest(prior["ordered_metadata"]) == p["expected_ordered_metadata_sha256"],
                "accepted original ordered metadata differs")
        manifest = source.replay.freeze(prior["ordered_metadata"], 0)
        require(manifest["manifest_sha256"] == p["expected_manifest_sha256"],
                "original prospective folds differ; refusing any replacement or subset")
        plans = {branch: source.producer.make_plan(manifest, manifest["manifest_sha256"],
                                                  bindings, branch, replay=source.replay)
                 for branch in BRANCHES}
        for branch in BRANCHES:
            require(plans[branch]["plan_sha256"] == p["expected_plans"][branch],
                    "accepted complete original source plan differs")
        protocols = {branch: interface.Protocol(plans[branch], p["expected_plans"][branch],
                                               manifest, p["zero_rule"]["sha256"], "paper_data", source)
                     for branch in BRANCHES}
        reads = SourceReads(p["input_root"], bindings, source.producer.read_member, admission.checkpoint)
        source.producer.read_member = reads
        admission.activate_numpy()
        for branch in BRANCHES:
            collected.append(collect_branch(protocols[branch], branch, p["input_root"], output,
                                            delivery, zero, budget, admission.checkpoint))
        # Neither evaluator has opened a target through Protocol.targets before
        # both complete branch commitments have been returned and retained.
        require([row["branch"] for row in collected] == list(BRANCHES), "both panels must be frozen")
        for branch, row in zip(BRANCHES, collected):
            evaluated.append(score_branch(protocols[branch], row, p["input_root"], output,
                                          submissions, budget, admission.checkpoint))
        source_reads = reads.summary(complete=True)
        report = {"schema": "temporal026-full-fixed-control-result/v1", "status": "completed",
                  "operator_protocol_sha256": admission.protocol_sha256,
                  "rule_sha256": p["zero_rule"]["sha256"], "collected": collected, "evaluated": evaluated,
                  "source_reads": source_reads, "admission": admission.report(),
                  "artifact_accounting_before_final_report": {"charged_bytes": budget.charged,
                                                               "entries": budget.entries},
                  "expected_unchanged_collector_reread_bytes": 419559796,
                  "collector_read_basis": "source-derived logical returned bytes for full completion; not runtime instrumentation",
                  "entry_authentication_reads": getattr(admission, "entry_authentication_reads", None),
                  "scope": "trusted fixed-zero engineering control; no AI, learning, fitting or paper reproduction",
                  "downloaded_bytes": 0, "fresh_context_provider_isolation_qualified": False,
                  "scientific_qualification": False, "readiness_promotion": False,
                  "remaining_gaps": ["interactive fresh-context/provider isolation",
                                     "original category selection recipe", "Figure4-9 downstream recipe",
                                     "author method reproduction", "candidate scientific improvement"]}
        final = budget.write(output / "RESULT.json", report, 1024**2)
        return {"status": "completed", "result": final, "output": str(output),
                "artifact_charged_bytes_including_final_report": budget.charged,
                "scientific_qualification": False}
    except BaseException as exc:
        # No retry, overwrite, cleanup, or refund of a partially attempted panel.
        failure = {"schema": "temporal026-full-fixed-control-result/v1", "status": "failed",
                   "operator_protocol_sha256": admission.protocol_sha256,
                   "error_type": type(exc).__name__, "error": str(exc)[:2048],
                   "collected": collected, "evaluated": evaluated,
                   "source_reads": None if reads is None else reads.summary(),
                   "guard_read_meters": admission.meters.snapshot(),
                   "entry_authentication_reads": getattr(admission, "entry_authentication_reads", None),
                   "artifact_charged_bytes_before_failure_receipt": budget.charged,
                   "artifact_entries": budget.entries, "scientific_qualification": False,
                   "partial_files_preserved": True, "automatic_retry": False}
        try:
            budget.write(output / "FAILURE.json", failure, 1024**2)
        except BaseException:
            pass  # Outer frozen reservation remains charged if receipt is impossible.
        raise
