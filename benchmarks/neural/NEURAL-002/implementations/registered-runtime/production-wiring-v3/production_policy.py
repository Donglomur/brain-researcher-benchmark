"""Task-local consumers of independently selected evidence, never issuers.

Pins establish custody and exact selection, not the truth of a native/provider
qualification. The trusted operator must independently select the evidence root
and authorization pin. This module neither creates certificates nor promotes a
scientific gate. Actual per-volume enforcement is checked by storage_policy.
"""
import hashlib
import os
from pathlib import Path
import stat
import sys

from contract import PEOPLE, CELLS, SOURCE_COMMIT, require
from morse_selection import canonical_bytes, digest, read_member, strict_json, sha
from morse_broker import validate_model_spec
from morse_docker import DockerCommandTransport


def exact(value, keys, label):
    require(type(value) is dict and set(value) == set(keys), label + " schema")


def captured(root, pin, maximum, budget):
    exact(pin, ("path", "bytes", "sha256"), "selected member")
    require(type(pin["bytes"]) is int and 0 < pin["bytes"] <= maximum,
            "selected member extent")
    sha(pin["sha256"])
    budget.read(pin["bytes"] + 1)
    body = read_member(root, pin, pin["bytes"])
    budget.check()
    return body


def document(root, pin, maximum, budget):
    return strict_json(captured(root, pin, maximum, budget))


def ordinary_directory(value):
    require(type(value) is str and not value.startswith("//") and Path(value).is_absolute()
            and str(Path(value)) == value and ".." not in Path(value).parts,
            "canonical absolute directory")
    p = Path(value)
    for a in (p, *p.parents):
        s = a.lstat()
        require(stat.S_ISDIR(s.st_mode) and not a.is_symlink(), "ordinary directory ancestry")
    return p


def separated(values):
    paths = [Path(v) for v in values]
    require(len(paths) == len(set(paths)), "distinct custody roots")
    for n, a in enumerate(paths):
        for b in paths[n + 1:]:
            require(a not in b.parents and b not in a.parents, "overlapping custody roots")


class SelectedEvidence:
    """Exact external evidence selection; no generated approving state.

The authorization pin is a separate trusted CLI/API operand, not a field that
the candidate or configuration can replace. Its issuer and supporting records
must be independently selected and reviewed before a future authorized run.
This parser does not supply cryptographic issuer authentication or prove the
empirical claims in those records. No default/example accepting record ships.
"""
    def __init__(self, config, root, authorization_pin, source_sha256, budget):
        self.budget = budget
        self.root = str(ordinary_directory(root))
        self.intent = config["intent"]
        self.intent_sha256 = digest(self.intent)
        maximum = config["metadata_member_bytes"]
        auth = document(self.root, authorization_pin, maximum, budget)
        exact(auth, ("schema", "issuer", "selection_id", "intent_sha256",
                     "source_sha256", "operations", "evidence"), "external authorization")
        require(auth["schema"] == "morse-external-operation-selection-v1"
                and type(auth["issuer"]) is str and auth["issuer"]
                and type(auth["selection_id"]) is str and auth["selection_id"],
                "independent external issuer and selection required")
        require(auth["intent_sha256"] == self.intent_sha256
                and auth["source_sha256"] == source_sha256,
                "authorization intent/source mismatch")
        require(auth["operations"] == ["authentic_intake", "paired_candidates",
                "five_references", "private_report"], "complete explicit operation selection")
        exact(auth["evidence"], ("intake", "deployment", "token", "references"),
              "external evidence selection")
        self.pins = auth["evidence"]
        self.records = {k: document(self.root, p, maximum, budget)
                        for k, p in self.pins.items()}
        self.authorization_pin = dict(authorization_pin)
        intake = self.records["intake"]
        exact(intake, ("schema", "source_commit", "intake_manifest", "people", "tasks",
                       "review_record"), "intake evidence")
        require(intake["schema"] == "morse-external-intake-evidence-v1"
                and intake["source_commit"] == SOURCE_COMMIT
                and intake["intake_manifest"] == self.intent["intake_manifest"]
                and intake["people"] == list(PEOPLE)
                and intake["tasks"] == ["dotcount", "firstlast"], "intake evidence binding")
        # Review artifacts are captured too; a caller's affirmative Boolean is
        # not substituted for the independently selected external artifact.
        for key, value in self.records.items():
            captured(self.root, value["review_record"], maximum, budget)
        refs = self.records["references"]
        exact(refs, ("schema", "intent_sha256", "order_nuisance", "methods",
                     "review_record"), "reference evidence")
        require(refs["schema"] == "morse-external-reference-selection-v1"
                and refs["intent_sha256"] == self.intent_sha256
                and refs["order_nuisance"] == self.intent["order_nuisance"],
                "reference evidence binding")
        require(refs["methods"] == {
            "prior_only": "prior_only", "order_only": "order_only",
            "premarker": "premarker", "permutation": "permutation",
            "validated_competent_EEG_reference": "erp_shrinkage"},
            "existing reference implementations must remain exact")
        self.source_receipt_sha256 = self.pins["intake"]["sha256"]

    def require_model_bound(self, spec):
        validate_model_spec(spec)
        token = self.records["token"]
        exact(token, ("schema", "endpoint", "protocol", "model_revision", "bound",
                      "review_record"), "model token evidence")
        require(token["schema"] == "morse-external-model-bound-v1"
                and all(token[k] == spec[k] for k in ("endpoint", "protocol", "model_revision"))
                and token["bound"] == {k: spec["token_bound"][k] for k in
                    ("utf8_multiplier", "fixed_overhead", "per_message_overhead")}
                and spec["token_bound"]["certificate_sha256"] == self.pins["token"]["sha256"],
                "fixed model/token certificate differs")


class SelectedNativeAdmission:
    """Concrete caller checks plus required independent deployment evidence.

Does not assert that source checks qualify Docker/kernel/provider behavior.
The host must already be under its separately qualified external lifetime,
CPU/RAM/storage owner. This class cannot create that qualification.
"""
    def __init__(self, evidence, profile, budget):
        self.evidence, self.profile, self.budget = evidence, profile, budget
        self.storage = None
        self.plan_sha256 = None
        exact(profile, ("docker_binary", "host_python", "docker_socket", "docker_config_root",
                        "deployment_id", "host_owner_source_sha256", "host_dependency_paths",
                        "numpy_version"), "native profile")
        dep = evidence.records["deployment"]
        exact(dep, ("schema", "intent_sha256", "native_profile", "image_digest",
                    "storage_configuration_sha256", "review_record"), "deployment evidence")
        require(dep["schema"] == "morse-external-deployment-evidence-v1"
                and dep["intent_sha256"] == evidence.intent_sha256
                and dep["native_profile"] == profile
                and dep["storage_configuration_sha256"] == evidence.intent["storage_configuration"]["sha256"],
                "deployment evidence differs")
        require(type(profile["deployment_id"]) is str and profile["deployment_id"], "deployment identity")
        sha(profile["host_owner_source_sha256"])
        self._check_native_identity()

    def prepare_dependencies(self):
        """Explicit qualified host dependency roots for actual -I -S startup.

        Directory identity and version checks do not qualify NumPy/BLAS or its
        transitive native libraries. Those exact builds remain deployment proof
        obligations. No candidate path is added to the trusted interpreter.
        """
        paths = self.profile["host_dependency_paths"]
        require(type(paths) is list and 1 <= len(paths) <= 8, "finite selected native dependency roots")
        names = []
        for item in paths:
            exact(item, ("path", "device", "inode", "uid", "mode"), "native dependency identity")
            require(all(type(item[k]) is int and item[k] >= 0 for k in ("device", "inode", "uid", "mode")),
                    "typed native dependency identity")
            p = ordinary_directory(item["path"])
            s = p.lstat()
            require((s.st_dev, s.st_ino, s.st_uid, stat.S_IMODE(s.st_mode)) ==
                    (item["device"], item["inode"], item["uid"], item["mode"])
                    and not (s.st_mode & 0o022), "selected native dependency root identity/permissions")
            names.append(str(p))
        require(len(names) == len(set(names)), "unique native dependency roots")
        require("numpy" not in sys.modules, "native NumPy was imported before selected admission")
        sys.path.extend(names)
        import numpy
        require(type(self.profile["numpy_version"]) is str and self.profile["numpy_version"]
                and numpy.__version__ == self.profile["numpy_version"]
                and any(Path(n) in Path(numpy.__file__).resolve().parents for n in names),
                "actual selected NumPy build/version path differs")
        self.budget.check()

    def bind_plan(self, plan, storage):
        require(self.plan_sha256 is None and self.storage is None,
                "native policy may bind one complete plan only")
        require(storage.plan_sha256 == plan["sha256"], "storage/plan binding")
        self.plan_sha256, self.storage = plan["sha256"], storage

    def _check_native_identity(self):
        require(sys.platform == "linux", "selected Linux deployment required")
        for key in ("docker_binary", "host_python"):
            pin = self.profile[key]
            exact(pin, ("path", "bytes", "sha256"), "native executable pin")
            p = Path(pin["path"])
            require(p.is_absolute(), "absolute native executable")
            captured(str(p.parent), dict(pin, path=p.name), pin["bytes"], self.budget)
            require(p.stat().st_mode & 0o111, "native executable permission")
        require(Path(sys.executable).resolve() == Path(self.profile["host_python"]["path"]).resolve(),
                "actual host interpreter differs")
        socket = self.profile["docker_socket"]
        exact(socket, ("path", "device", "inode", "uid", "mode"), "daemon socket identity")
        require(all(type(socket[k]) is int and socket[k] >= 0 for k in ("device", "inode", "uid", "mode")),
                "typed daemon socket identity")
        ordinary_directory(str(Path(socket["path"]).parent))
        s = Path(socket["path"]).lstat()
        require(stat.S_ISSOCK(s.st_mode) and not Path(socket["path"]).is_symlink()
                and (s.st_dev, s.st_ino, s.st_uid, stat.S_IMODE(s.st_mode)) ==
                    (socket["device"], socket["inode"], socket["uid"], socket["mode"]),
                "actual selected daemon socket identity differs")
        directory = ordinary_directory(self.profile["docker_config_root"])
        directory_info = directory.lstat()
        require(directory_info.st_uid == os.geteuid()
                and stat.S_IMODE(directory_info.st_mode) == 0o700,
                "private operator-owned Docker configuration directory")
        self.budget.check()
        with os.scandir(directory) as entries:
            require(next(entries, None) is None, "explicit empty Docker configuration root required")
        self.budget.check()

    def require_paired_execution(self, plan, records, run_root):
        require(self.storage is not None and plan["sha256"] == self.plan_sha256
                and plan["spec"]["source_receipt_sha256"] == self.evidence.source_receipt_sha256
                and plan["spec"]["engineering_only"] is False
                and len(records) == 9984 and plan["spec"]["people"] == list(PEOPLE)
                and plan["spec"]["cells"] == list(CELLS), "full selected execution binding")
        require(plan["spec"]["environment"]["image_digest"] ==
                self.evidence.records["deployment"]["image_digest"], "selected image differs")
        require(run_root == self.evidence.intent["workspace_root"] + "/execution",
                "fixed production run root")
        self._check_native_identity()
        self.evidence.require_model_bound(plan["spec"]["model_spec"])

    def command_transport(self):
        self._check_native_identity()
        return FixedDaemonTransport(self.profile)


class FixedDaemonTransport(DockerCommandTransport):
    """Existing real transport, with exact binary/socket/empty-config operands."""
    def __init__(self, profile):
        super().__init__(profile["docker_binary"]["path"])
        self.prefix = ["--host", "unix://" + profile["docker_socket"]["path"],
                       "--config", profile["docker_config_root"]]

    def start(self, args):
        return super().start([*self.prefix, *args])
