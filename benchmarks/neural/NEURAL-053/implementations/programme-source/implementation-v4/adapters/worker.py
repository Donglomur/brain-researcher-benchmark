"""Concrete exact-case prediction worker staging, launch and observation."""
from pathlib import Path
import json
import uuid

from .common import (BoundAdapter, authenticate, canonical, copy_exact, digest,
                     file_pin, json_exact, need, write_fresh)
from .process import DockerSandbox


INPUT_NAMES = ("registry", "receipt", "bindings", "plan", "whole_method_gate",
               "reference_selection", "query_descriptor", "query")


def container_path(role):
    return "/case/" + role + (".npy" if role == "query" else ".json")


class DockerWorkerLauncher(BoundAdapter):
    def __init__(self, config, budget, authorization, *, case_files):
        super().__init__(config, budget, authorization, "predict_all")
        self.case_files = {tuple(key): json.loads(canonical(value)) for key, value in case_files.items()}
        self._used = set()

    def __call__(self, key, request, method_gate):
        self.verify_current()
        key = tuple(key)
        need(key in self.case_files and key not in self._used, "one exact admitted worker invocation; no automatic retry")
        self._used.add(key)
        case = self.case_files[key]
        need(set(case) == {"request", "inputs", "output_dir"} and set(case["inputs"]) == set(INPUT_NAMES), "exact per-case worker staging inventory")
        budget = self.new_budget()
        actual_request = json_exact(case["request"], budget)
        need(canonical(actual_request) == canonical(request) and request.get("profile") == "canonical"
             and request.get("context_key") == list(key), "exact approved canonical request body")
        for role in INPUT_NAMES:
            artifact, wanted = case["inputs"][role], request[role]
            need(wanted["path"] == container_path(role) and
                 wanted["bytes"] == artifact["bytes"] and wanted["sha256"] == artifact["sha256"], "worker input path/pin mapping changed")
        need(request["output_path"] == "/output/probabilities.npy" and
             request["output_manifest_path"] == "/output/worker_manifest.json", "exact worker output layout")
        bindings = json_exact(case["inputs"]["bindings"], budget)
        descriptor = json_exact(case["inputs"]["query_descriptor"], budget)
        selection = json_exact(case["inputs"]["reference_selection"], budget)
        whole = json_exact(case["inputs"]["whole_method_gate"], budget)
        need(whole.get("reference_selection_sha256") == digest(selection), "selection joins approved whole-method seal")
        descriptor_pin = bindings["artifacts"]["query_descriptor"]
        need(descriptor_pin["bytes"] == case["inputs"]["query_descriptor"]["bytes"] and
             descriptor_pin["sha256"] == case["inputs"]["query_descriptor"]["sha256"], "query descriptor joins approved bindings")
        own = next((x for x in whole.get("methods", []) if x["context_key"] == list(key)), None)
        need(own is not None and own["receipt_sha256"] == method_gate["receipt_sha256"] and
             own["bindings_sha256"] == digest(bindings), "current method gate joins whole-case seal")
        output = Path(case["output_dir"])
        need(output.is_absolute() and output.resolve().is_relative_to(Path(self.config["workspace_root"]).resolve()), "fresh output must belong to admitted workspace root")
        output.mkdir(mode=0o700, parents=False)
        root = output / ("worker-" + uuid.uuid4().hex); root.mkdir(mode=0o700)
        stage = root / "case"; stage.mkdir(mode=0o755)
        work = root / "work"; work.mkdir(mode=0o777); work.chmod(0o777)
        emitted = root / "output"; emitted.mkdir(mode=0o777); emitted.chmod(0o777)
        source = self.stage_source(root / "benchmark", budget)
        # Source/query bodies are copied only after all request/gate/selection
        # metadata joins above. The parent has already approved all160 methods.
        for role in INPUT_NAMES:
            copy_exact(case["inputs"][role], stage / Path(container_path(role)).name, budget)
        request_pin = copy_exact(case["request"], stage / "request.json", budget)
        docker = DockerSandbox(self.config["sandbox"], budget, root)
        clock_observation = docker.verify_shared_clock(work)
        source_before = digest(self.source_manifest())
        child_caps = request.get("worker_budget")
        need(isinstance(child_caps, dict) and set(child_caps) == {"source_read", "artifact_write"}
             and all(type(v) is int and v > 0 for v in child_caps.values()), "explicit pinned worker resource reservation")
        for name, value in child_caps.items():
            budget.charge(name, value)
        args = ["--request", "/case/request.json", "--request-bytes", str(request_pin["bytes"]),
                "--request-sha256", request_pin["sha256"],
                "--origin-monotonic", str(budget.origin_monotonic), "--deadline-monotonic", str(budget.deadline_monotonic),
                "--source-read-cap", str(child_caps["source_read"]),
                "--artifact-write-cap", str(child_caps["artifact_write"])]
        observed = docker.run_python("/benchmark/prediction_worker.py",
            mounts=[(str(stage), "/case", True), (str(source), "/benchmark", True),
                    (str(work), "/work", False), (str(emitted), "/output", False)], work_root=root, args=args)
        import json
        summary = json.loads(observed["stdout"])
        need(summary.get("status") == "worker_returned" and summary.get("profile") == "canonical" and
             set(summary.get("used", {})) == set(child_caps), "complete bounded worker logical-usage summary")
        for name, value in summary["used"].items():
            need(type(value) is int and 0 <= value <= child_caps[name], "typed bounded child resource usage")
        manifest_pin = file_pin(emitted / "worker_manifest.json", self.config["sandbox"]["workspace_cap_bytes"], budget)
        worker = json_exact(manifest_pin, budget, cap=self.config["sandbox"]["workspace_cap_bytes"])
        need(worker.get("context_key") == list(key) and worker.get("profile") == "canonical" and
             worker.get("method_admission", {}).get("receipt_sha256") == method_gate["receipt_sha256"] and
             worker.get("bindings_digest") == digest(bindings) and
             worker.get("query_descriptor_digest") == digest(descriptor) and
             worker.get("reference_selection_digest") == digest(selection), "worker output failed exact method/support/selection join")
        probability = worker["probability_artifact"]
        need(probability["path"] == "/output/probabilities.npy", "worker output cannot redirect to another artifact")
        host_probability = {**probability, "path": str(emitted / "probabilities.npy")}
        authenticate(host_probability, budget)
        for role in INPUT_NAMES:
            staged = {**case["inputs"][role], "path": str(stage / Path(container_path(role)).name)}
            authenticate(staged, budget)
        self.verify_current()
        need(source_before == digest(self.source_manifest()), "actual worker source changed during inference")
        self.verify_staged_source(source, budget)
        container = observed["container_observation"]
        need(type(container.get("natural_exit_code")) is int and container["natural_exit_code"] == 0 and
             container.get("owned_container_absent") is True, "strict independent natural-zero and owned retirement")
        execution = {"schema": "neural053_prediction_execution_v1", "context_key": list(key),
                     "method_admission_digest": method_gate["receipt_sha256"],
                     "query_descriptor_digest": digest(descriptor), "reference_selection_digest": digest(selection),
                     "probabilities_digest": worker["probabilities_digest"], "natural_exit_code": 0,
                     "source_state_unchanged": True, "adapter_source_manifest_sha256": self._bound_source_digest,
                     "adapter_config_sha256": self._bound_config_digest, "request_sha256": case["request"]["sha256"],
                     "worker_manifest": manifest_pin, "host_process_and_container": container,
                     "clock_observation": clock_observation, "child_logical_usage": summary["used"],
                     "child_reserved_usage": child_caps, "child_unused_reservation_refunded": False,
                     "budget": budget.snapshot(), "independent_operator_approval": "required_before_grading",
                     "scientific_qualification_conferred": False}
        write_fresh(root / "execution_observation.json", canonical(execution), budget)
        worker = {**worker, "probability_artifact": host_probability}
        budget.check_clock()
        return {"worker_manifest": worker, "execution_receipt": execution}
