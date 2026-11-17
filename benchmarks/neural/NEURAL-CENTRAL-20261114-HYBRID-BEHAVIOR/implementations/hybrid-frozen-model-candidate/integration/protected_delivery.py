"""Hybrid TRAIN export -> existing complete protected participant callable.

Source import is inert. Authentic preparation and evaluation are explicit future
calls inside a separately admitted operation, never the old reference-fit worker.
The trusted host owns receipts and OnlineSession; candidate containers receive
only the unchanged flat programme and anonymous artifact mount.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types

TRAIN_PIN = (23855, '09852837525fe701731b7e10afb7d408eb17036f906547bc598d034fcf501a52')
RUNNER_LOCK_PIN = (3712, '76166183a18be9478ea89dcda912b733e474e2bf33009ddfaa696f4b74065cc4')
REFERENCE_PIN = (351850, "f9bb15d421d9182b594225c501214269af86ea9b89c83480bd4320efd1d702d5")
SCHEMA = "hybrid-private-protected-delivery-v1"
MAX_MANIFEST = 1048576
MAX_DELIVERY = 256 * 1048576
MAX_REQUEST = 128 * 1048576
FULL_EPISODE_RESERVATION = 22161470228


class DeliveryError(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise DeliveryError(reason)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def ordinary(path):
    p = Path(path)
    need(p.is_absolute() and ".." not in p.parts, "absolute selected path")
    need(not any(q.is_symlink() for q in (p, *p.parents)), "no linked path ancestor")
    return p


def stamp(s):
    return tuple(getattr(s, k) for k in ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"))


class Snapshot:
    """One bounded stable read, then exact integer identity checks; no rereads."""
    def __init__(self, path, pin=None, cap=1048576):
        self.path = ordinary(path)
        if pin is not None:
            need(type(pin) is tuple and len(pin) == 2 and type(pin[0]) is int and 0 < pin[0] <= cap and
                 type(pin[1]) is str and len(pin[1]) == 64 and all(c in "0123456789abcdef" for c in pin[1]), "exact selected identity descriptor")
        fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            s = os.fstat(fd)
            need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and 0 < s.st_size <= cap, "ordinary bounded file")
            if pin is not None:
                need(s.st_size == pin[0], "selected file extent")
            self.identity = stamp(s)
            with os.fdopen(fd, "rb", closefd=False) as f:
                self.body = f.read(s.st_size + 1)
            need(len(self.body) == s.st_size and stamp(os.fstat(fd)) == self.identity, "stable complete file read")
        finally:
            os.close(fd)
        self.pin = (len(self.body), digest(self.body))
        need(pin is None or self.pin == pin, "selected file digest")
        self.check()

    def check(self):
        need(stamp(ordinary(self.path).lstat()) == self.identity, "late file mutation: " + self.path.name)


def _module(name, snapshot):
    existing = sys.modules.get(name)
    if existing is not None:
        need(getattr(existing, "__file__", None) == str(snapshot.path), "foreign loaded module: " + name)
        return existing
    m = types.ModuleType(name)
    m.__file__ = str(snapshot.path)
    sys.modules[name] = m
    try:
        exec(compile(snapshot.body, m.__file__, "exec"), m.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return m


class Sources:
    """Exact source composition for a fresh trusted worker, without native calls."""
    def __init__(self, training_root, runner_root):
        self.training_root, self.runner_root = ordinary(training_root), ordinary(runner_root)
        self.snapshots = [Snapshot(Path(__file__).absolute())]
        training = Snapshot(self.training_root / "train_export.py", TRAIN_PIN)
        self.snapshots.append(training)
        self.export = _module("train_export", training)
        self.consumer, self.reference, self.artifact = self.export.dependencies()
        for name, pin in self.export.SOURCE_PINS.items():
            self.snapshots.append(Snapshot(self.training_root / "accepted" / (name + ".py"), pin))
        lock = Snapshot(self.runner_root / "SOURCE_LOCK.json", RUNNER_LOCK_PIN, 65536)
        self.snapshots.append(lock)
        declared = self.export._json(lock.body, 65536)
        need(declared["schema"] == "hybrid-complete-participant-source-lock-v2", "accepted runner lock")
        bodies = {}
        for name, pin in declared["files"].items():
            need(Path(name).name == name, "flat selected runner source")
            bodies[name] = Snapshot(self.runner_root / name, (pin["bytes"], pin["sha256"]))
        need(sum(len(s.body) for s in bodies.values()) <= 1048576, "whole accepted runner source bound")
        self.snapshots.extend(bodies.values())
        for name, pin in self.export.SOURCE_PINS.items():
            need(bodies[name + ".py"].pin == pin, "byte-identical shared source semantics")
        # Consumer/reference/artifact already have the exact train_export origins.
        # No sys.path insertion or foreign-module exception relaxation is needed.
        order = ("donor_checked_source", "donor_create_lifecycle", "donor_process_closure",
                 "endpoint_guard", "episode_owner_base", "scoring", "reference_workflow",
                 "trial_transport", "transport_harness")
        self.modules = {name: _module(name, bodies[name + ".py"]) for name in order}
        self.harness = self.modules["transport_harness"]
        self.workflow = self.modules["reference_workflow"]
        self.closure = {"integration_sha256": self.snapshots[0].pin[1],
                        "train_export_sha256": TRAIN_PIN[1], "runner_lock_sha256": RUNNER_LOCK_PIN[1],
                        "producer_closure": self.export.producer_closure()}
        self.check()

    def check(self):
        for item in self.snapshots:
            item.check()


def _write_new(path, body, cap):
    path = ordinary(path)
    need(type(body) is bytes and 0 < len(body) <= cap, "complete output extent")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as f:
            need(f.write(body) == len(body), "complete output write")
            f.flush()
            os.fsync(fd)
        os.fchmod(fd, 0o400)
    finally:
        os.close(fd)
    return {"relative_path": str(path.name), "bytes": len(body), "sha256": digest(body)}


def _stage(sources, decisions, programme_files, output, secret, *, fixture_counts=None):
    """Trusted implementation; authentic caller alone supplies authenticated cases."""
    sources.check()
    ex, c = sources.export, sources.consumer
    fixture = fixture_counts is not None
    counts = fixture_counts if fixture else (c.MAIN_ELIGIBLE, c.MAIN_TRIALS)
    c.validate_decisions(decisions, expected_eligible=counts[0], expected_trials=counts[1])
    manifest = ex.program_manifest(programme_files)
    need("participant_entry.py" in programme_files, "existing participant entry required")
    root = ordinary(output)
    root.mkdir(mode=0o700)
    for name in ("program", "models", "private"):
        (root / name).mkdir(mode=0o700)
    used = 0
    def write(directory, name, body, cap):
        nonlocal used
        need(used + len(body) <= MAX_DELIVERY, "whole staged delivery admission")
        used += len(body)
        pin = _write_new(root / directory / name, body, cap)
        pin["relative_path"] = directory + "/" + name
        return pin
    for name, body in programme_files.items():
        write("program", name, body, 1048576)
    bundles = []
    for subject, held in sorted(c.GROUPS):
        sources.check()
        request, preparation = ex._prepare_common(decisions, subject, held, programme_files, secret,
            expected_decisions=counts[0], expected_trials=counts[1],
            evidence_kind="invented_engineering_fixture" if fixture else "authenticated_case_map")
        # The unchanged producer receives anonymous TRAIN bytes only.
        artifact, provenance = ex.train_and_seal(request, preparation, programme_files, secret)
        ex.verify_export(artifact, provenance, request, preparation, programme_files, secret, require_authentic=not fixture)
        opaque = os.urandom(16).hex()
        bundles.append({"request": write("private", opaque + ".request.json", request, MAX_REQUEST),
                        "preparation": write("private", opaque + ".preparation.json", preparation, MAX_MANIFEST),
                        "provenance": write("private", opaque + ".provenance.json", provenance, MAX_MANIFEST),
                        "artifact": write("models", opaque + ".json", artifact, 65536)})
    sources.check()
    signed = ex._sign({"schema": SCHEMA, "source_closure": sources.closure,
        "evidence_kind": "invented_engineering_fixture" if fixture else "authenticated_case_map",
        "case_identity": None if fixture else {"bytes": c.MAIN_CASE_BYTES, "sha256": c.MAIN_CASE_SHA256},
        "counts": {"decisions": counts[0], "trials": counts[1], "folds": 80},
        "programme": manifest, "bundles": bundles}, secret)
    need(used + len(signed) <= MAX_DELIVERY, "manifest-inclusive delivery admission")
    result = _write_new(root / "DELIVERY.private.json", signed, MAX_MANIFEST)
    for name in ("program", "models", "private"):
        (root / name).chmod(0o500)
    return result


def prepare_authentic(sources, case_path, programme_files, output, secret):
    """Future TRAIN construction; authentic file is authenticated exactly once.

    This performs new producer fits if explicitly invoked. It is NOT called by
    evaluation, and accepted historical references never need to be refitted.
    """
    sources.check()
    decisions = sources.consumer.load_accepted_private_cases(case_path)
    return _stage(sources, decisions, programme_files, output, secret)


def _production_family(sources, family):
    need(type(family) is sources.harness.EpisodeFamily, "existing admitted EpisodeFamily required")
    need(family.source == sources.runner_root and family.count == 0 and family.rows == [] and family.reserved_output == 0,
         "fresh selected whole participant family")
    need(type(family.plan.get("maximum_episodes")) is int and family.plan["maximum_episodes"] == sources.consumer.MAIN_TRIALS,
         "full participant operation, not old17-control plan")
    reservation = family.plan.get("episode_output_reservation_bytes")
    need(type(reservation) is int and reservation >= FULL_EPISODE_RESERVATION, "complete participant output admission")
    need(family.plan.get("producer_delivery_source_closure") == sources.closure, "successor integration bound by selected operation")


class BoundFamily:
    """Signed TRAIN provenance and immutable operands around existing EpisodeFamily.

    This is trusted evaluator code. The wrapped production family alone owns
    Docker and OnlineSession. A failure poisons this adapter permanently.
    """
    def __init__(self, sources, decisions, root, manifest_pin, secret, family, *, _fixture_counts=None):
        self.sources, self.family = sources, family
        self.root = ordinary(root)
        self.fixture = _fixture_counts is not None
        self.poisoned = False
        self.completed_trials = set()
        self.snapshots = []
        self.folds = {}
        self.decisions = tuple(decisions)
        ex, c = sources.export, sources.consumer
        counts = _fixture_counts if self.fixture else (c.MAIN_ELIGIBLE, c.MAIN_TRIALS)
        c.validate_decisions(self.decisions, expected_eligible=counts[0], expected_trials=counts[1])
        self.trials = {(t[0].subject, t[0].session, t[0].trial): tuple(t)
                       for t in sources.workflow.group_complete_trials(self.decisions)}
        if not self.fixture:
            _production_family(sources, family)
        manifest_snapshot = Snapshot(self.root / "DELIVERY.private.json", manifest_pin, MAX_MANIFEST)
        self.snapshots.append(manifest_snapshot)
        payload = ex._unsign(manifest_snapshot.body, secret)
        need(type(payload) is dict and set(payload) == {"schema", "source_closure", "evidence_kind", "case_identity", "counts", "programme", "bundles"}, "exact delivery schema")
        need(payload["schema"] == SCHEMA and payload["source_closure"] == sources.closure, "delivery source closure")
        expected_evidence = "invented_engineering_fixture" if self.fixture else "authenticated_case_map"
        need(payload["evidence_kind"] == expected_evidence, "no fixture-to-authentic promotion")
        need(payload["case_identity"] == (None if self.fixture else {"bytes": c.MAIN_CASE_BYTES, "sha256": c.MAIN_CASE_SHA256}), "delivery case identity")
        need(payload["counts"] == {"decisions": counts[0], "trials": counts[1], "folds": 80}, "complete delivery population")
        programme = payload["programme"]
        need(type(programme) is dict and type(programme.get("members")) is list, "programme manifest")
        need(programme["members"] and all(type(p) is dict and type(p.get("bytes")) is int and 0 < p["bytes"] <= 1048576 for p in programme["members"]), "bounded declared programme members")
        need(sum(p["bytes"] for p in programme["members"]) <= 1048576, "whole programme admission before reads")
        self.programme = self.root / "program"
        programme_files = {}
        for pin in programme["members"]:
            need(type(pin) is dict and set(pin) == {"name", "bytes", "sha256"}, "programme member fields")
            name = pin["name"]
            need(type(name) is str and Path(name).name == name and name not in programme_files, "unique flat programme member")
            snap = Snapshot(self.programme / name, (pin["bytes"], pin["sha256"]), 1048576)
            self.snapshots.append(snap)
            programme_files[name] = snap.body
        need(ex.program_manifest(programme_files) == programme, "complete programme bytes bound to delivery")
        self.programme_pins = {x["name"]: {"bytes": x["bytes"], "sha256": x["sha256"]} for x in programme["members"]}
        need("participant_entry.py" in self.programme_pins, "existing participant entry")
        bundles = payload["bundles"]
        need(type(bundles) is list and len(bundles) == 80, "all80 signed exports")
        paths = set()
        used = sum(len(x.body) for x in self.snapshots)
        for bundle in bundles:
            need(type(bundle) is dict and set(bundle) == {"request", "preparation", "provenance", "artifact"}, "exact export bundle")
            artifact_rel = bundle["artifact"].get("relative_path") if type(bundle["artifact"]) is dict else None
            need(type(artifact_rel) is str and re.fullmatch(r"models/[0-9a-f]{32}\.json", artifact_rel), "opaque artifact mount path")
            opaque = Path(artifact_rel).stem
            parts = {}
            for key, folder, cap in (("request", "private", MAX_REQUEST), ("preparation", "private", MAX_MANIFEST),
                                     ("provenance", "private", MAX_MANIFEST), ("artifact", "models", 65536)):
                pin = bundle[key]
                need(type(pin) is dict and set(pin) == {"relative_path", "bytes", "sha256"}, "exact bundle pin")
                rel = pin["relative_path"]
                need(type(rel) is str and len(Path(rel).parts) == 2 and Path(rel).parts[0] == folder and ".." not in Path(rel).parts and rel not in paths, "unique private/artifact member path")
                need(key == "artifact" or rel == "private/" + opaque + "." + key + ".json", "matching opaque private sidecar")
                need(type(pin["bytes"]) is int and 0 < pin["bytes"] <= cap and used + pin["bytes"] <= MAX_DELIVERY, "whole delivery admission before body read")
                used += pin["bytes"]
                paths.add(rel)
                parts[key] = Snapshot(self.root / rel, (pin["bytes"], pin["sha256"]), cap)
                self.snapshots.append(parts[key])
            ex.verify_export(parts["artifact"].body, parts["provenance"].body, parts["request"].body,
                             parts["preparation"].body, programme_files, secret, require_authentic=not self.fixture)
            prepared = ex._check_preparation(parts["request"].body, parts["preparation"].body, programme_files, secret, require_authentic=not self.fixture)
            key = (prepared["subject_private"], prepared["held_session_private"])
            need(key not in self.folds, "unique authenticated fold mapping")
            train, _ = c.outer_fold(self.decisions, *key)
            need(prepared["training_row_ids_sha256"] == ex.sha256(ex.canonical([d.source_row for d in train])), "training source rows agree with evaluator cohort")
            need(prepared["training_projection_sha256"] == ex.sha256(ex.canonical(c.training_view(train))), "TRAIN projection agrees with evaluator cohort")
            art = parts["artifact"]
            self.folds[key] = {"path": str(art.path), "bytes": art.pin[0], "sha256": art.pin[1]}
        need(set(self.folds) == c.GROUPS, "complete authenticated20x4 fold map")
        need(sum(len(x.body) for x in self.snapshots) <= MAX_DELIVERY, "complete cached delivery extent")
        self.rosters = {folder: {Path(p).name for p in paths if Path(p).parts[0] == folder}
                        for folder in ("private", "models")}
        self.directory_identities = {}
        for directory in (self.root, self.programme, self.root / "models", self.root / "private"):
            info = ordinary(directory).lstat()
            need(stat.S_ISDIR(info.st_mode), "ordinary delivery directory")
            self.directory_identities[directory] = stamp(info)
        self.check()

    def check(self):
        try:
            need(not self.poisoned, "participant adapter already failed")
            self.sources.check()
            for snapshot in self.snapshots:
                snapshot.check()
            for directory, identity in self.directory_identities.items():
                need(stamp(ordinary(directory).lstat()) == identity, "late delivery-directory mutation")
            need({p.name for p in self.programme.iterdir()} == set(self.programme_pins), "programme roster changed")
            need({p.name for p in self.root.iterdir()} == {"program", "models", "private", "DELIVERY.private.json"}, "delivery roster changed")
            for folder, names in self.rosters.items():
                need({p.name for p in (self.root / folder).iterdir()} == names, "private/artifact roster changed")
        except BaseException:
            self.poisoned = True
            raise

    def run(self, trial, programme, artifact, entry, programme_pins, artifact_pin, secret=None):
        try:
            self.check()
            need(secret is None, "signing/token key is not a participant operand")
            need(trial, "complete nonempty held trial")
            first = trial[0]
            key = (first.subject, first.session)
            trial_key = key + (first.trial,)
            need(trial_key not in self.completed_trials, "one fresh episode per complete trial")
            expected = self.trials.get(trial_key)
            need(tuple(trial) == expected, "exact complete evaluator-held trial")
            pin = self.folds[key]
            need(Path(programme) == self.programme and Path(artifact) == Path(pin["path"]) and entry == "participant_entry.py" and programme_pins == self.programme_pins and artifact_pin == pin, "authenticated fold/programme/artifact handoff")
            # Only existing public operands enter the trusted transport API. It
            # never receives request/preparation/provenance or the signing key.
            result, predictions, directory = self.family.run(trial, self.programme, Path(pin["path"]), entry,
                                                             self.programme_pins, dict(pin))
            self.check()
            need(type(result) is dict and result.get("complete") is True, "complete protected episode")
            need(result.get("error") is None and type(result.get("private_decision_count")) is int and
                 result["private_decision_count"] == len(trial), "consistent episode result")
            operand = {"read_bytes": sum(p["bytes"] for p in self.programme_pins.values()) + pin["bytes"],
                       "programme_files": len(self.programme_pins), "model_sha256": pin["sha256"]}
            need(result.get("operand_before") == operand and result.get("operand_after") == operand, "consistent public operand receipts")
            clean = result.get("cleanup")
            need(type(clean) is dict and clean.get("absent") is True and clean.get("errors") == [], "uncertain cleanup poisons whole campaign")
            attach = result.get("attach")
            need(type(attach) is dict and attach.get("complete") is True, "complete causal commitment transcript")
            child = attach.get("direct_child")
            need(attach.get("issue") is None and type(child) is dict and child.get("reaped") is True and
                 child.get("errors") == [] and child.get("signals_sent") == [] and
                 type(child.get("exit_code")) is int and child["exit_code"] == 0, "natural reaped participant child")
            counts = attach.get("counts")
            need(type(counts) is dict and set(counts) == {"queries", "commits"} and all(type(v) is int and v == len(trial) for v in counts.values()), "every current query must be committed")
            need(type(predictions) in (list, tuple) and len(predictions) == len(trial), "complete committed predictions")
            for decision, pair in zip(trial, predictions):
                need(type(pair) in (list, tuple) and len(pair) == 2 and pair[0] == decision, "prediction row/order provenance")
                self.sources.consumer.probability_vector(pair[1])
            self.completed_trials.add(trial_key)
            return result, predictions, directory
        except BaseException:
            self.poisoned = True
            raise

    def references_for_existing_runner(self, accepted_references):
        self.check()
        return {"artifact_manifest_private": [{"subject_private": s, "held_session_private": k,
            "artifacts": {"family_train_selected": self.folds[(s, k)]}} for s, k in sorted(self.folds)],
            "scores": accepted_references["scores"]}


def run_authentic(sources, case_path, reference_path, delivery_root, manifest_pin, secret, family):
    """Future full participant integration under an already admitted owner.

    No producer/refit is called here. It reuses the existing full4884-trial runner,
    causal transport, scorer and frozen reference score. Outer worker-group and
    independent namespace recovery are still mandatory before operation success.
    """
    sources.check()
    _production_family(sources, family)
    reference = Snapshot(reference_path, REFERENCE_PIN, 2 * 1048576)
    accepted = sources.export._json(reference.body, 2 * 1048576)
    decisions = sources.consumer.load_accepted_private_cases(case_path)
    bound = BoundFamily(sources, decisions, delivery_root, manifest_pin, secret, family)
    try:
        result = sources.harness.run_complete_participant(decisions, bound.references_for_existing_runner(accepted),
                                                          bound.programme, bound.programme_pins, bound)
        bound.check()
        reference.check()
        need(len(bound.completed_trials) == sources.consumer.MAIN_TRIALS, "all complete participant episodes")
        need(family.count == sources.consumer.MAIN_TRIALS and len(family.rows) == family.count and all(r["complete"] is True for r in family.rows), "whole production family containment")
        return {"schema": "hybrid-protected-train-export-participant-v1", "participant_result": result,
                "delivery_manifest_sha256": manifest_pin[1], "reference_sha256": REFERENCE_PIN[1],
                "source_closure": sources.closure, "outer_recovery_still_required": True,
                "scientific_qualification": False, "count_delta": 0}
    except BaseException:
        bound.poisoned = True
        raise
