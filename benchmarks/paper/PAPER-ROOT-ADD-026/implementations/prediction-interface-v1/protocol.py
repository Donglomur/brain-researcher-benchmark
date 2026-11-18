"""Trusted temporal026 observations and targets, with explicit source branches.

No participant code is executed here. Operators must keep these objects and the
input bank private; returned observations require fresh, isolated job contexts.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


PRODUCER_SHA256 = "1badd56de63fe41e45caee80b0520400edc1a100a205fb2574729bd3a45f6ec6"
PROTOCOL_SCHEMA = "temporal026-candidate-prediction-protocol/v1"
OBSERVATION_SCHEMA = "temporal026-candidate-observation/v1"
CONDITIONS = ("paper_data", "paper_data_author_code")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def is_hash(value):
    return (type(value) is str and len(value) == 64 and
            all(c in "0123456789abcdef" for c in value))


def clone(value):
    return json.loads(encoded(value))


class Source:
    """Load only the exact existing producer and its pinned replay dependencies."""

    def __init__(self, producer_directory=None):
        directory = (Path(producer_directory) if producer_directory is not None else
                     Path(__file__).parent.parent / "source-model-producer-v1")
        path = directory / "producer.py"
        # Reuse no unverified producer function before authenticating its bytes.
        import os
        import stat
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
            before = os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                    0 < before.st_size <= 65536, "bounded producer source required")
            raw = stream.read(65537)
            after = os.fstat(stream.fileno())
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                 before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
                 after.st_ctime_ns) and len(raw) == before.st_size,
                "producer source changed during read")
        require(hashlib.sha256(raw).hexdigest() == PRODUCER_SHA256,
                "original producer source identity mismatch")
        spec = importlib.util.spec_from_file_location("temporal026_candidate_source", path)
        producer = importlib.util.module_from_spec(spec)
        exec(compile(raw, str(path), "exec"), producer.__dict__)
        replay = producer.load_replay(directory.parent / "source-cv-replay-v1")
        self.producer = producer
        self.replay = replay


class Protocol:
    """Frozen plan/method selection for one complete branch and assistance arm.

    The method digest is an operator-attested code/model identity, not proof of
    executed code or a sandbox. Both source none/S coordinate sets are required;
    their names do not prescribe or attest the candidate's architecture.
    """

    def __init__(self, plan, expected_plan_sha256, manifest, method_sha256,
                 condition, source=None):
        require(is_hash(method_sha256), "frozen candidate method SHA256 required")
        require(condition in CONDITIONS, "explicit paper assistance condition required")
        source = source or Source()
        # Snapshot caller-owned values before validation and never return them.
        plan, manifest = clone(plan), clone(manifest)
        source.producer.validate_plan(plan, expected_plan_sha256, manifest,
                                      replay=source.replay)
        require(plan["scalings"] == ["none", "S"] and len(plan["jobs"]) == 2054,
                "complete original DN-none/S comparison panel required")
        self.source = source
        self._plan = plan
        self._manifest = manifest
        self.plan_sha256 = expected_plan_sha256
        self.method_sha256 = method_sha256
        self.condition = condition
        self._jobs = {job["id"]: job for job in plan["jobs"]}
        self._items = {item["electrode_id"]: item for item in manifest["electrodes"]}
        self._delivery_ids = tuple(job["id"] for mode in ("cv", "full")
                                   for job in plan["jobs"] if job["mode"] == mode)
        descriptor = {
            "schema": PROTOCOL_SCHEMA,
            "plan_sha256": expected_plan_sha256,
            "manifest_sha256": plan["manifest_sha256"],
            "method_sha256": method_sha256,
            "condition": condition,
            "cv_column_branch": plan["cv_column_branch"],
            "source_producer_sha256": PRODUCER_SHA256,
            "source_replay_sha256": source.producer.REPLAY_SHA,
            "source_cohort_sha256": source.producer.COHORT_SHA,
            "counts": {"electrodes": 79, "conditions": 72, "samples": 819,
                       "cv_jobs": 1896, "full_jobs": 158, "jobs": 2054},
            "source_coordinate_order_sha256": digest(plan["jobs"]),
            "delivery_order_sha256": digest(self._delivery_ids),
            "delivery_policy": "all CV outputs committed before full-data observations; fresh context per coordinate",
            "scientific_qualification": False,
        }
        self._descriptor = descriptor
        self.protocol_sha256 = digest(descriptor)
        self._locked = True

    def __setattr__(self, name, value):
        require(not getattr(self, "_locked", False), "frozen protocol cannot be reassigned")
        object.__setattr__(self, name, value)

    @property
    def plan(self):
        return clone(self._plan)

    @property
    def manifest(self):
        return clone(self._manifest)

    @property
    def descriptor(self):
        return clone(self._descriptor)

    @property
    def ordered_jobs(self):
        return clone(self._plan["jobs"])

    @property
    def delivery_jobs(self):
        return [clone(self._jobs[name]) for name in self._delivery_ids]

    def job_info(self, job_id):
        require(type(job_id) is str and job_id in self._jobs, "unknown original job coordinate")
        job = self._jobs[job_id]
        item = self._items[job["electrode_id"]]
        if job["mode"] == "cv":
            allocation = item["folds"][job["fold"]]
            train, query = allocation["train_rows"], allocation["test_rows"]
            branch = self._plan["cv_column_branch"]
        else:
            train = query = list(range(72))
            branch = "named_response_columns"
        return clone({"job": job, "source_data_sha256": item["source_data_sha256"],
                      "train_rows": train, "prediction_rows": query,
                      "prediction_identities": [item["rows"][i] for i in query],
                      "column_branch": branch})

    def _read_response(self, input_root, job_id):
        info = self.job_info(job_id)
        electrode = info["job"]["electrode_id"]
        raw = self.source.producer.read_member(
            input_root, self._plan["input_bindings"]["responses"][electrode])
        rows, responses = self.source.replay.parse_source_table(raw)
        require(rows == self._items[electrode]["rows"],
                "source response rows differ from frozen metadata")
        return info, raw, rows, responses

    def project_job(self, input_root, job_id):
        """Trusted primitive; DeliverySession supplies the CV-before-full gate.

        The returned payload contains no source paths or held-out response array.
        Hashes and condition identities are public provenance, not secrecy claims.
        No complete bank or Protocol object may be handed to a participant.
        """
        info, raw, rows, responses = self._read_response(input_root, job_id)
        job = info["job"]
        if job["mode"] == "cv":
            packet = self.source.replay.project(
                raw, self._manifest, self._plan["manifest_sha256"],
                job["electrode_id"], job["fold"], info["column_branch"])
            training, queries, columns = packet["training"], packet["queries"], packet["target_columns"]
        else:
            training = [{"source_row": i, **row, "response": responses[i]}
                        for i, row in enumerate(rows)]
            queries = [{"source_row": i, **row} for i, row in enumerate(rows)]
            columns = self.source.replay.HEADER[3:]
        variables = self.source.producer.read_variables(
            input_root, self._plan["input_bindings"]["variables"], self.source.replay)
        return {"schema": OBSERVATION_SCHEMA,
                "protocol_sha256": self.protocol_sha256,
                "plan_sha256": self.plan_sha256,
                "method_sha256": self.method_sha256,
                "condition": self.condition, "job": clone(job),
                "column_branch": info["column_branch"],
                "source_data_sha256": info["source_data_sha256"],
                "target_columns": list(columns), "training": training, "queries": queries,
                "variables": {key: value.tolist() for key, value in variables.items()},
                "sample_rate": 512,
                "exposure": ("66 observed conditions; six response-free queries" if job["mode"] == "cv"
                             else "all 72 response conditions are observed; not held-out prediction"),
                "context_policy": "fresh job context; no cross-fold, scaling, full-data or branch state transfer",
                "qualification": "trusted observation projection only; no provider/runtime isolation claim"}

    def targets(self, input_root, job_id):
        """Evaluator-only original response read; never a participant endpoint."""
        info, _raw, rows, responses = self._read_response(input_root, job_id)
        if info["column_branch"] == "source_positional_cv":
            responses = [[float(row["temp_cond"])] + values[:-1]
                         for row, values in zip(rows, responses)]
        return {"source_data_sha256": info["source_data_sha256"],
                "prediction_rows": info["prediction_rows"],
                "prediction_identities": info["prediction_identities"],
                "observations": [responses[i] for i in info["prediction_rows"]],
                "column_branch": info["column_branch"]}
