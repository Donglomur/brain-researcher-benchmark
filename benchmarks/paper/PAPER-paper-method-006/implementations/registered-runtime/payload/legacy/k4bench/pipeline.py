"""Sequential complete job graph composition with immutable failure custody."""
from pathlib import Path
from .admission import validate_manifest
from .protocol import require, digest, write_new, outcome, validate_pin
from .runtime import Worker
from .identity import manifest_digest, plan_digest, job_digest, profile_digest, bind_profile, identity


class Pipeline:
    """Concrete native pipeline. Metric jobs use the protected grading endpoint.

    Undefined producers cannot be substituted by a function callback. Every
    selected instance resolves to an exact supported worker request, or yields
    a required-unscorable receipt. Stopping one dependency never drops its
    downstream obligation from the complete final coverage vector.
    """
    def __init__(self, store, authority, meter, catalog):
        self.store, self.authority, self.meter, self.catalog = store, authority, meter, catalog

    def run_native_graph(self, manifest, output_root, input_roots):
        admission = validate_manifest(manifest, self.catalog)
        require(admission["manifest_digest"] == self.authority.selection["manifest_digest"],
                "authority-manifest-mismatch", "complete graph")
        root = Path(output_root)
        require(root.is_dir() and not root.is_symlink(), "invalid-run-root", str(root))
        jobs = {x["id"]: x for x in manifest["jobs"]}
        results = {}
        worker = Worker(self.store, self.authority, self.meter)
        for ordinal, job_id in enumerate(admission["order"]):
            job = jobs[job_id]
            # Later admission may explicitly select an already validated node.
            # Reuse requires the identical job, manifest, producer and complete
            # evidence pin. A failed/reconfigured node is never silently reused.
            reuse_pin = self.authority.admission.get("validated_job_receipt_pins", {}).get(job_id)
            if reuse_pin is not None:
                prior = self.store.json(validate_pin(reuse_pin), 4 * 1024 * 1024)
                require(prior["job_digest"] == job_digest(job) and
                        prior["manifest_digest"] == manifest_digest(manifest) and
                        prior["status"] == "native-output-validated", "unsafe-node-reuse", job_id)
                require(prior["producer_descriptor_digest"] == digest(
                    manifest["producer_profiles"][job["producer_id"]]), "unsafe-producer-reuse", job_id)
                results[job_id] = prior
                write_new(root / f"job-{ordinal:06}-COMPOSITION.json",
                          {"job_id": job_id, "result": prior, "immutable_reuse_pin": reuse_pin}, self.meter)
                continue
            blocked = [x for x in job["depends_on"] if results[x]["status"] != "native-output-validated"]
            if blocked:
                result = outcome("required-unscorable", gaps=[{
                    "id": "dependency-not-qualified", "reason": x} for x in blocked])
            else:
                profile_descriptor = manifest["producer_profiles"][job["producer_id"]]
                if profile_descriptor["status"] != "concrete-source-bound":
                    result = outcome("required-unscorable", gaps=profile_descriptor["gaps"])
                elif profile_descriptor["kind"] not in {"kilosort4", "preparation", "candidate", "provider", "scientific"}:
                    result = outcome("required-unscorable", gaps=[{
                        "id": "separate-protected-or-constructor-dispatch-required",
                        "reason": profile_descriptor["kind"]}])
                else:
                    profile = self.store.json(validate_pin(profile_descriptor["profile_pin"]), 4 * 1024 * 1024)
                    try:
                        attempt = worker.run(manifest, job, profile, root, input_roots,
                                             f"job-{ordinal:06}-attempt-000001")
                    except BaseException as error:
                        attempt = {"status": "failed", "failure": {"code": "dispatch-or-custody-failed",
                                   "type": type(error).__name__, "detail": str(error)},
                                   "termination": "unknown if effects began", "scientific_pass": None}
                    # A zero native exit code is not scientific success. Full
                    # output decoding, telemetry and reference/native parity
                    # have separate protected receipts and cannot be inferred.
                    result = {"status": "native-awaiting-output-validation" if attempt["failure"] is None else "failed",
                              "attempt": attempt, "scientific_pass": None,
                              "downstream_automatically_enabled": False}
            results[job_id] = result
            write_new(root / f"job-{ordinal:06}-COMPOSITION.json",
                      {"job_id": job_id, "result": result}, self.meter)
        summary = {"schema": "kilosort4_complete_native_graph_receipt_v1",
                   "manifest_digest": manifest_digest(manifest), "results": results,
                   "all_original_instances_retained": True,
                   "scientific_ready": False,
                   "remaining_work": "protected output admission and metric/reference composition",
                   "logical_meter": self.meter.receipt()}
        write_new(root / "GRAPH.json", summary, self.meter)
        return summary


def join_validated_job(store, authority, manifest, job):
    """Only selected authenticated execution/output/telemetry tuples can close a node.

    Callers supply no alternate loaded profile or receipt. Issuer profile pins
    and output/telemetry receipt pins come from external root admission.
    """
    authority.permit(manifest, job)
    binding = authority.admission["validated_job_bindings"][job["id"]]
    return validate_execution_binding(store, manifest, job, binding)


def validate_execution_binding(store, manifest, job, binding):
    """Shared pure authentication path; caller must select binding via authority."""
    descriptor = manifest["producer_profiles"][job["producer_id"]]
    producer = store.json(validate_pin(descriptor["profile_pin"]), 4 * 1024 * 1024)
    pd = bind_profile(manifest, job, producer)
    native = store.json(validate_pin(binding["native_receipt_pin"]), 4 * 1024 * 1024)
    output = store.json(validate_pin(binding["output_receipt_pin"]), 4 * 1024 * 1024)
    telemetry = store.json(validate_pin(binding["telemetry_receipt_pin"]), 4 * 1024 * 1024)
    require(native["job_id"] == native["permit"]["job_id"] == job["id"]
            and native["job_digest"] == native["permit"]["job_digest"] == job_digest(job)
            and native["manifest_digest"] == native["permit"]["manifest_digest"] == manifest_digest(manifest)
            and native["plan_digest"] == native["permit"]["plan_digest"] == plan_digest(manifest),
            "native-job-manifest-binding", job["id"])
    require(native["permit"]["selection_pin"] == binding["execution_selection_pin"],
            "native-selection-binding", job["id"])
    execution = store.json(validate_pin(binding["execution_selection_pin"]), 1024 * 1024)
    require(execution["purpose"] == "scientific-execution"
            and execution["canonical_id"] == "PAPER-paper-method-006"
            and execution["manifest_digest"] == manifest_digest(manifest)
            and job["id"] in execution["scoped_job_ids"]
            and execution["admission_receipt_pin"] == native["permit"]["admission_receipt_pin"],
            "execution-selection-mismatch", job["id"])
    require(native["profile_digest"] == pd and native["producer_profile_pin"] == descriptor["profile_pin"]
            and native["producer_descriptor_digest"] == digest(descriptor),
            "native-producer-profile-mismatch", job["id"])
    require(native["status"] == "native-exited" and native["failure"] is None
            and native["termination"]["custody_complete"] and not native["termination"]["residual_processes"],
            "native-attempt-not-complete", job["id"])
    for role, receipt in (("output-validator", output), ("telemetry-validator", telemetry)):
        issuer_pin = binding[role + "_profile_pin"]
        issuer = store.json(validate_pin(issuer_pin), 1024 * 1024)
        require(issuer["role"] == role and receipt["issuer_profile_pin"] == issuer_pin
                and receipt["issuer_profile_digest"] == identity("validator-profile", issuer),
                "unselected-validator-issuer", role)
        require(receipt["native_receipt_pin"] == binding["native_receipt_pin"]
                and receipt["native_attempt_digest"] == digest(native)
                and receipt["job_id"] == job["id"] and receipt["job_digest"] == job_digest(job)
                and receipt["manifest_digest"] == manifest_digest(manifest)
                and receipt["producer_profile_digest"] == pd,
                "validation-receipt-identity-mismatch", role)
    require(output["status"] == "full-output-validated" and output["complete_support"] is True
            and output["output_pins"] and telemetry["status"] == "complete-within-caps",
            "job-not-qualified", job["id"])
    for pin in output["output_pins"]:
        store.read(validate_pin(pin))
    return {"status": "native-output-validated", "job_id": job["id"],
            "job_digest": native["job_digest"], "manifest_digest": native["manifest_digest"],
            "producer_profile_digest": pd, "producer_descriptor_digest": digest(descriptor),
            "binding_digest": digest(binding), "native_receipt_pin": binding["native_receipt_pin"],
            "output_receipt_pin": binding["output_receipt_pin"],
            "telemetry_receipt_pin": binding["telemetry_receipt_pin"], "scientific_claim": None}
