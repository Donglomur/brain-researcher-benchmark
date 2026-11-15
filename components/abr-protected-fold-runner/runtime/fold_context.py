"""Trusted fold projection and complete-output gate, not an OS sandbox.

Never import this module or expose its objects in a candidate process. A future
selected runtime must create a new process/filesystem/agent conversation for each
context, mount only its exported inputs, stop it before commit, and independently
prove cleanup. The APIs enforce data partitions and feedback ordering only.
"""
import hashlib
import json
import re
from pathlib import Path

import builder
import packet
import score
import split

ROUTES = ("candidate", "layout_only")


def pinned_animal_loader(packet_root, completion_pin, guard):
    """Bind complete accepted inventory bytes before exporting any animal.

    completion_pin is operator-selected, never candidate supplied. The caller
    additionally pins the split manifest to the receipt's private manifest SHA.
    """
    root = Path(packet_root)
    builder.identity(root, directory=True)
    packet.need(completion_pin["path"] == str(root / "evaluator" / "PACKET_COMPLETION.json"),
                "exact trusted completion location")
    raw, _ = builder.read_fixed(completion_pin, guard)
    completion = builder.decode(raw)
    packet.need(completion["schema"] == "abr-background-opaque-packet-completion/v1" and
                completion["profile"] == packet.PROFILE and len(completion["animal_files"]) == 104,
                "complete packet inventory")
    pins = {}
    for pin in completion["animal_files"]:
        name = pin["name"]
        packet.need(type(name) is str and re.fullmatch(r"animal_[0-9a-f]{64}\.json", name)
                    and name[:-5] not in pins, "unique opaque animal filename")
        pins[name[:-5]] = {"path": str(root / "animals" / name), "bytes": pin["bytes"], "sha256": pin["sha256"]}
    def load(aid):
        packet.need(aid in pins, "admitted inventory animal only")
        body, _ = builder.read_fixed(pins[aid], guard, cap=16 * 1024**2)
        animal = packet.validate_animal(builder.decode(body))
        packet.need(animal["animal_id"] == aid, "inventory/animal ID join")
        return animal
    return load


def valid_fold(fold):
    packet.need(type(fold) is int and 0 <= fold < 5, "literal outer fold0..4")


def public_header(manifest, fold, route):
    manifest = split.validate_manifest(manifest); valid_fold(fold)
    packet.need(route in ROUTES, "declared candidate/layout route")
    view = split.public_fold_view(manifest, fold)
    train = set(manifest["folds"][fold]["train_animal_ids"])
    labels = {a["animal_id"]: a["label"] for a in manifest["animals"] if a["animal_id"] in train}
    return {"schema": "abr-background-fold-context/v1", "route": route,
            "partition": view, "training_labels": labels,
            "calibration": "within_release_sample_index_only",
            "state_policy": "fresh_process_filesystem_agent_per_fold; frozen_method_only_shared"}


def iter_animals(manifest, fold, route, load_animal):
    """One bounded animal at a time; no test labels/source witnesses exported."""
    manifest = split.validate_manifest(manifest); valid_fold(fold)
    packet.need(route in ROUTES, "declared route")
    part = manifest["folds"][fold]; train = set(part["train_animal_ids"])
    test = set(part["test_animal_ids"])
    packet.need(len(train | test) == 104 and not train & test, "complete animal partition")
    for aid in sorted(train | test):
        animal = load_animal(aid)
        packet.validate_animal(animal)
        packet.need(animal["animal_id"] == aid, "exact requested opaque animal")
        if route == "layout_only":
            animal = packet.layout_only(animal)
        yield {"role": "train" if aid in train else "test", "animal": animal}


def fold_prediction_bytes(manifest, fold, rows):
    """Validate one complete test fold without reading any target label."""
    valid_fold(fold)
    expected = set(manifest["folds"][fold]["test_animal_ids"])
    packet.need(type(rows) is list and len(rows) == len(expected), "complete test-fold prediction count")
    got = set()
    for row in rows:
        packet.need(type(row) is dict and set(row) == {"animal_id", "outer_fold", "p_6n"},
                    "exact prediction row fields")
        aid = row["animal_id"]; p = row["p_6n"]
        packet.need(type(aid) is str and aid in expected and aid not in got, "unique exact fold animal")
        packet.need(type(row["outer_fold"]) is int and row["outer_fold"] == fold,
                    "prediction belongs to active fold")
        packet.need(type(p) in (int, float) and 0 <= p <= 1, "finite probability; no bool/NaN")
        got.add(aid)
    packet.need(got == expected, "all test animals")
    return packet.canonical(sorted(rows, key=lambda row: row["animal_id"]))


class Campaign:
    """Trusted logical gate: 10 fresh contexts, then complete paired scoring.

    Context IDs must be supplied by the external owner and never reused. A
    cleanup witness is recorded, not independently authenticated by this class.
    Authentic admission requires the owner to verify that witness and physical
    isolation; these pure APIs cannot prevent a caller with host access cheating.
    """
    def __init__(self, manifest, method_sha256, layout_method_sha256):
        self.manifest = split.validate_manifest(manifest)
        for pin in (method_sha256, layout_method_sha256):
            packet.need(type(pin) is str and re.fullmatch(r"[0-9a-f]{64}", pin), "frozen method SHA")
        self.methods = {"candidate": method_sha256, "layout_only": layout_method_sha256}
        self.active = None; self.ids = set(); self.commits = {}; self.scored = False

    def start(self, route, fold, context_id):
        valid_fold(fold)
        packet.need(route in ROUTES and self.active is None and not self.scored,
                    "one active context, no post-score adaptation")
        packet.need((route, fold) not in self.commits, "no retry or replacement of a committed fold")
        packet.need(type(context_id) is str and re.fullmatch(r"[0-9a-f]{64}", context_id)
                    and context_id not in self.ids, "fresh owner context identity")
        self.ids.add(context_id); self.active = (route, fold, context_id)
        return public_header(self.manifest, fold, route)

    def commit_stopped(self, context_id, predictions, cleanup_witness_sha256):
        packet.need(self.active is not None and self.active[2] == context_id,
                    "active context capability, no stale-fold writes")
        packet.need(type(cleanup_witness_sha256) is str and
                    re.fullmatch(r"[0-9a-f]{64}", cleanup_witness_sha256), "bound external cleanup evidence")
        route, fold, _ = self.active
        body = fold_prediction_bytes(self.manifest, fold, predictions)
        self.commits[(route, fold)] = {"context_id": context_id,
            "method_sha256": self.methods[route], "cleanup_witness_sha256": cleanup_witness_sha256,
            "prediction_sha256": hashlib.sha256(body).hexdigest(), "rows": json.loads(body)}
        self.active = None
        # No metric, correctness signal, target or pooled diagnostic at this stage.
        return {"status": "prediction_committed", "prediction_sha256": hashlib.sha256(body).hexdigest()}

    def evaluate(self):
        packet.need(self.active is None and not self.scored and
                    set(self.commits) == {(route, fold) for route in ROUTES for fold in range(5)},
                    "all10 stopped-context commits / complete104 candidate and104 layout outputs before feedback")
        candidate = [r for f in range(5) for r in self.commits[("candidate", f)]["rows"]]
        layout = [r for f in range(5) for r in self.commits[("layout_only", f)]["rows"]]
        result = score.score(self.manifest, candidate, layout)
        self.scored = True
        return {"schema": "abr-background-complete-campaign-score/v1", "score": result,
                "commitments": [{k: v for k, v in self.commits[key].items() if k != "rows"}
                                | {"route": key[0], "outer_fold": key[1]} for key in sorted(self.commits)],
                "runtime_isolation_proven_by_this_module": False}
