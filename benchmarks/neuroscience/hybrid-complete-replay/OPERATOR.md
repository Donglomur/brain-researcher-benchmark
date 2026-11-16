# Operator-local source preparation

All paths below are operator-local examples, not available assets. Choose an ordinary absolute private directory outside the checkout. Preparation accepts one JSON object with exactly these fields:

```json
{
  "schema": "hybrid-operator-local-binding-v1",
  "paths": {
    "base_entry": "/absolute/runtime/base/python3.11",
    "venv": "/absolute/runtime/venv",
    "venv_entry": "/absolute/runtime/venv/bin/python3.11",
    "cases": "/absolute/private/cases.json",
    "references": "/absolute/private/reference.json",
    "runtime_receipt": "/absolute/runtime/RUNTIME_IDENTITY.json",
    "operator_home": "/absolute/private/home",
    "caller": "/absolute/private/new-capture",
    "capacity_binding": "/absolute/private/fresh-capacity.json",
    "output": "/absolute/private/new-output",
    "docker_config": "/absolute/private/empty-docker-config"
  },
  "operation_token": "unique-private-operation-0001",
  "endpoint": {
    "original_executable_path": "/absolute/docker-alias",
    "original_symlink_target": "literal-alias-target",
    "expected_observation": {
      "binary": {"path": "/absolute/docker-target", "physical_identity": [0,0,0,0,0,1], "mode": 33261, "uid": 0, "gid": 0},
      "socket": {"path": "/absolute/docker.sock", "physical_identity": [0,0,0,0,0,1], "mode": 49536, "uid": 0, "gid": 0}
    }
  },
  "historical_artifact_locations": null
}
```

The example is deliberately not an admission: replace every endpoint number with the exact current authoritative integer values. physical_identity is `[device,inode,size,mtime_ns,ctime_ns,link_count]`, preserving integers above 2^53. Observe the resolved regular executable and Unix socket using the existing endpoint admission process; the guard later checks full mode/uid/gid/path equality, original symlink literal/resolution and complete fixed Docker binary hash. Merely declaring fields does not qualify them. The image remains `sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156`. Empty Docker config, private HOME and runtime assets must be provisioned separately; no automatic install, pull or fallback exists.

If moved artifacts require a location map, replace null with exactly `{"path":"/absolute/private/map.json","bytes":INTEGER,"sha256":"LOWERCASE64HEX"}`. The complete map is bounded131,072 bytes, binds the frozen351,850-byte reference and all 80 canonical historical record hashes, and preserves each model's original byte count/SHA256. Use the sibling command (its published manifest is a separate trust root):

```sh
python3 -I -B ../hybrid-artifact-provisioning/provision.py --source-manifest-sha256 VERIFIED_PROVISIONING_MANIFEST_SHA256 locations --reference /absolute/private/reference.json --artifact-directory /absolute/private/models --output /absolute/private/map.json
```

Generate the private binding's exact byte count and SHA256, then authenticate this release's SOURCE_MANIFEST.json against its reviewed digest. Run:

```sh
python3 -I -B prepare_operation.py --manifest-sha256 VERIFIED_RELEASE_MANIFEST_SHA256 --binding /absolute/private/operator.json --binding-bytes EXACT_BYTES --binding-sha256 VERIFIED_BINDING_SHA256 --output /absolute/private/new-operation-source
```

The fresh source/output/caller directories must be disjoint with existing ordinary parents. Source preparation writes only the new source directory; it does not create the actual output/caller, inspect asset availability, qualify a socket or invoke the owner. Failure preserves any partial prepared directory; use a new reviewed binding/namespace after diagnosis, never automatic retry.

The host is exactly macOSarm64 CPython3.11.6/NumPy2.2.6. Base and venv Python each remain52,640 bytes / SHA256 4959d784e83b29c47836a946a6ce6ac7f8f36bb1edc90b394dde44a6376cb1a1. The unchanged4,955-byte runtime receipt SHA25619c00d6304c6f75dd40c63889dc125133fc0a4bfad40eb36aced4f52d2a6f010 binds a complete inventory at venv.parent/RUNTIME_FILES.jsonl and absolute approved alias identities. An operator without that exact authorized runtime/layout cannot yet execute this frozen route. A portable runtime relocation/requalification would be a separate reviewed successor; the newer PFC image is not substituted.

Before actual invocation, current external capacity evidence must cover all 4,884 episodes,163,135 decisions, zero new fits,2GiB host plus1GiB serial container,24GiB output and16GiB explicit managed reads. Work is capped86,400s and the outer owner87,000s, retaining at least600s recovery reserve. The worst-case120s per trial exceeds this whole bound; the route fails closed rather than producing a partial score. These are fixed planning ceilings, not measured runtime or present reservations. The existing owner requires the exact generated lock/token and a positive capacity observation no older than 300s. Obtain that receipt through an independently selected capacity operation; do not forge it from this document or preparation output.

The generated PREPARATION.json includes the literal prospective base-interpreter argv. The original owner enforces current asset/runtime authentication, image identity, fresh namespace, owned-worker closure, complete scope and reference reconciliation. Run only after actual selection; it is not part of source checks. Authenticated case200,756,614 bytes / SHA256 ba3fca8449f6da71f431db27a31a595134d20fece65557f8aea9fbb59e98afe7 and reference351,850 bytes / SHA256 f9bb15d421d9182b594225c501214269af86ea9b89c83480bd4320efd1d702d5 remain private. Model/artifact contents, labels, reference results, keys, identities, journals and operator bindings must never be published or mounted to the participant beyond the two permitted programme/model mounts.

The accepted copied interpreter is specifically `venv/bin/python3.11`, as established by both original operation and legacy runner PLAN metadata. A `venv/bin/python` alias is not accepted as a substitute for that frozen file identity.
