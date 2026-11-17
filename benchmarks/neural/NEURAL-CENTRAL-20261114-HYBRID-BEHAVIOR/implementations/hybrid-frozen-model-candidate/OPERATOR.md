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

## Separate frozen-model candidate arm

Keep the old operator schema for reference replay. For a candidate, use schema `hybrid-frozen-model-candidate-binding-v1`, retain exactly the same fields and immutable asset/runtime constraints, and add only:

```json
"candidate_program": {
  "directory": "/absolute/private/candidate-program",
  "manifest": {"path": "/absolute/private/candidate-manifest.json", "bytes": EXACT_BYTES, "sha256": "EXACT_SHA256"}
}
```

The operator-pinned manifest has exactly `schema` and `files`. Its schema is `hybrid-frozen-model-candidate-program-v1`; files is a four-row list with exactly `name`, `bytes` and `sha256` in each row. The required names are participant_entry.py, model_artifact.py, reference.py and consumer.py. Each file must be nonempty valid UTF-8 Python source, ordinary/single-link with no symlink ancestry, and the directory must contain only those four files. The manifest stays outside the programme directory. The combined source cap is196,608 bytes (192KiB), and manifest cap8,192 bytes. Freeze exact content identities before dispatch; no candidate source is imported or executed on the host. Host syntax parsing and hashing are not candidate execution.

Use the same prepare_operation.py command with this successor's reviewed manifest digest and the new private binding. It materializes the explicit candidate arm and descriptor without reading candidate code or scientific assets. The existing owner authenticates/captures the candidate before dispatch, and the worker repeats admission before any Docker command. Candidate source snapshots are checked again after staging and at closure. Only captured bytes enter the existing signed80-fold delivery. Candidate source is inference provenance; historical model/record/producer pins still attest only to the original reference-model training, not to a new training run or historical execution of candidate code.

The candidate receives one fresh isolated process per complete trial, `/model/model.json` containing that trial's corresponding frozen training-selected model, and the unchanged current-query stream. It must echo each opaque token and commit four valid probabilities before the next query. It has no mounted targets, future rows, identity/fold mapping, private TRAIN receipts or signing key. Network/mount/resource/process restrictions are unchanged. It may retain history within a trial; it receives a new process for the next trial. It can ignore or use the frozen model; no new fitting pipeline or TRAIN-data access is added. Source freezing before dispatch does not prove absence of earlier exposure to public/private benchmark material.

The candidate branch has a distinct terminal status and metadata. It must still complete all20 people/80 folds/4,884 trials/163,135 decisions with zero new fits and all the original ownership, deadline, signal, recovery and provenance checks. Its committed predictions are scored by the unchanged trusted scorer. The outer owner independently recomputes the original20-person paired comparison with its fixed10,000-draw/20261114 seed. Better, equal and worse valid scores can complete; there is no improvement or SOTA threshold. The original reference branch continues requiring complete historical score equality and cannot accept candidate source.

Candidate current admission must additionally bind evaluation_arm=`candidate_frozen_models`, the exact identity returned by trusted FrozenCandidate admission, managed_read_scope=`host_managed_only`, candidate_internal_reads_metered=false and candidate_runtime_whole_read_qualified=false. These declarations make the limitation explicit; they are not runtime qualification. No actual candidate operation is selected by this source delivery.

The candidate conservative HOST-managed bound is16,737,142,333 bytes under the unchanged17,179,869,184-byte ceiling. READ_BOUNDS.json retains every old reference term and total unchanged, then separately derives the candidate host term: replace2×4,884×(27,417+65,536) with2×4,884×(196,608+65,536), and add two candidate programme/manifest captures. Candidate-internal filesystem reads can repeat arbitrarily within the existing time/memory limits and are not metered or claimed bounded by this host figure. Whole candidate I/O/runtime qualification remains unresolved; no enforcement framework or replacement runtime is supplied. Stronger history-sensitive baseline and locked selection/repeated-seed evidence remain separate prerequisites for stronger scientific claims.

The candidate-arm `new_fits=0` field means zero new trusted evaluator/reference-model fits: all 80 original trained artifacts are reused. Arbitrary candidate-internal computation is not inspected or certified as training-free. No private TRAIN data or fitting interface is added.
