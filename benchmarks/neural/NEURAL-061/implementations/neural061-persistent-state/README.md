# NEURAL-061 persistent participant state

This package connects the complete NEURAL-061 A0 scientific programme to a concrete participant protocol and isolated-process supervisor. It includes the scientific source, its contracts, the participant implementation, and generated checks. **It is source construction, not a qualified or ready neuroscience benchmark.** No recordings, identities, targets, trained models, credentials, container image, or scientific results are included.

The earlier `components/neural061-planning` component contains only seven planning modules. This package is independently usable and includes the complete current runtime; those seven modules remain byte-identical. Every copied scientific module and contract is listed in [PROVENANCE.json](PROVENANCE.json). The numerical model definitions, scorer, finite-mean correction, and scientific population are unchanged.

## Check the package

Python 3.11 or later and its standard library are sufficient for generated verification. No installation, network, Docker, NumPy, scikit-learn, data download, or model run is needed. Use the package manifest's exact byte count and SHA-256 from the reviewed release or CI selection:

```sh
python3.11 -I -S -B verify_source.py \
  --manifest-bytes MANIFEST_BYTES \
  --manifest-sha256 MANIFEST_SHA256 \
  --check
```

Replace the two uppercase values with the independently selected pin; they are not environment-variable names. The command works from any current directory when `verify_source.py` is given by its absolute path. Use `--inspect` in place of `--check` to authenticate and inspect the package without running controls. Computing a pin from an untrusted local manifest establishes local consistency only; it does not replace a reviewed source selection.

The verifier authenticates every member and all internal dependency pins, rejects missing or extra files, symlinks, special files, and unlisted bytecode, and copies only captured bytes into a temporary directory. It executes the checks from that relocated copy with a different current directory. It never imports implementation code through the private repository's search path.

A successful check runs **26 generated methods: 21 participant/scientific-graph controls and five package controls**, with zero errors, failures, skips, expected failures, or unexpected successes. Any such disposition returns a nonzero exit. The JSON result distinguishes generated methods from benchmark IDs and reports that authentic-input, native, model and scientific qualification remain absent. Its RSS observation is not a whole-runtime capacity guarantee.

The complete-population fixture uses two explicitly generated regions, all 423 source sessions, all 29 evaluation sessions, all ten seeds, six reference arms and both candidate arms: 4,640 planned output dispositions. It exercises the actual collection and common-support code. Numerical references and process effects are replaced with declared generated stand-ins. Two fixture regions are not a reduced scientific region selection or authentic data result.

## What stays complete

| Scientific axis | Current selected contract |
| --- | --- |
| Question | Signed wheel velocity from matched neural populations |
| Source population | 423 sessions, 126 animals, five whole-animal source folds |
| Evaluation population | 29 sessions, 13 disjoint animals |
| Regions and matching | Every original grey-matter region; all ten seeds; k=10; anatomy |
| Reference arms | B, BR, BC, R, C and ZERO, with the original full configuration search |
| Candidate arms | BR and BC, fitted separately from the same frozen method source |
| Agent condition | A0: source-only F authoring, T0, one repeat |
| Support and statistics | Complete ten-seed common support, original denominators and reductions; original reference Holm family |

A1/A2/A3, adaptive I and trained-reference-tool T1 remain prospectively unselected. Candidate competence and region contrasts do not establish causal necessity or a region ranking. Preparation and score qualification, actual eligible support, atlas region count, power and exposure remain unresolved. The exact [selected API](science/API_SELECTED.md), [adopted design](science/contracts/adopted/DESIGN.md), [support contract](science/contracts/adopted/SUPPORT_AND_INFERENCE.md), and [native obligations](science/contracts/original/NATIVE_CONTRACT.md) specify the inherited boundaries. Historical contract scope is superseded only where the selected API explicitly says so.

## Participant and operator interfaces

A participant supplies one frozen `method.py` with these two functions:

```python
def fit(payload):
    # payload: task, complete source views, tool=None under T0
    return fitted_state

def infer(payload, fitted_state):
    # payload: task, one complete unlabeled query view, tool=None
    # Return every ordered query window, including all positions before masking.
    return [{"query": window_identity, "values": prediction_values}, ...]
```

`fit` runs once in a fresh child for one scientific cell and candidate arm. That original arbitrary fitted Python object remains in the same child across the full evaluation roster. It is never pickled, extracted into a reduced model, deserialized in the host, or reused across cells/arms. The child bootstrap supports ordinary module registration, including dataclass states with deferred annotations. The unchanged worker and host validate ordered finite scalar wheel-velocity predictions. Candidate libraries must already be in the separately qualified image; no dependency installation is performed.

`producer/child.py` implements the fixed framed protocol. `producer/enclosure.py` constructs and checks an offline, read-only, unprivileged Docker enclosure with exact source mounts and private namespaces. `producer/supervisor.py` owns bounded requests, deadlines, streams, exit/reap, group and container absence, and cleanup that preserves original errors. `producer/adapter.py` implements the A0 operations and invokes the unchanged full scientific collection caller. The primitive wire codec transports public views and predictions; it never transports fitted objects.

For an already qualified operator integration, the portable API is:

1. `verify_source.authenticate(package_root, manifest_bytes, manifest_sha256)` captures the entire reviewed package into a `bodies` mapping.
2. `verify_source.load_producer(bodies)` compiles the captured accepted producer roles and returns them by name.
3. `modules['loader'].make_host(...)` takes `installed=package_root/'science'`, the parsed captured `producer/INHERITED.json`, explicit private-owner roots, a pinned frozen method, allocated scratch, a prospective native request, an explicit Docker executable/local socket, the original monotonic owner, `package_root=package_root/'producer'`, and that inner manifest's pin from the outer manifest.
4. `modules['adapter'].construct_prepared(prepared, host, owner)` uses the same earlier admitted preparation and full A0 graph. This is an **unqualified component entry**, not an override of public admission.

The factory joins its selected manifest to the exact producer bodies already compiled, then to the bundled scientific source. It rejects lexical overlap with private owners before filesystem metadata. The supplied method is a captured frozen programme, not evidence of a compliant LLM-authoring transcript. The factory installs the captured `n061` namespace before preparation; do not pre-import a different `n061` package. The caller owns the returned import finder's lifetime in that isolated operator process.

The native request fields are `image`, `memory_bytes`, `nano_cpus`, `pids`, `cpu_seconds`, `tmp_bytes`, `frame_bytes`, `stderr_bytes`, `wall_seconds`, `command_seconds`, and `command_bytes`. They require explicit positive integer limits and an immutable local `sha256:` image ID. This package selects no real image, executable, hardware allocation, or numerical limits. A complete input/output that exceeds its prospective allocation fails; sessions, arms and seeds are never truncated to fit.

## Remaining runtime and scientific work

Original same-open raw capture, full atlas/identity admission, measured whole-study and panel allocations, qualified executable/image/dependencies, physical aggregate resource enforcement, provider identity/transcript/spending provenance, trusted outer reference-process ownership, outside publication and a separate late-target capability are still required. The container's CPU rate and per-process CPU limit do not establish aggregate CPU-time enforcement. The qualified numerical stack and exact third-party data/source versions must be selected separately; generated checks use no scientific dependency installation.

The bundled public `prepare`, `collect`, `programme.execute`, `score`, and allocation methods retain their original hard holds. `publish_production` refuses at the outside-publication boundary. No command in this package downloads data, runs the authentic benchmark, opens private targets, or grants a publication/target capability. Green generated checks do not establish historical reproduction, SOTA performance, inference quality, scientific validity, or readiness. The benchmark-ID and ready-count deltas are both zero.

Project-authored source is provided under the accompanying [MIT license](LICENSE). No primary article or third-party implementation body is included. The inherited public source anchor identifies background vocabulary and conventions; it does not license external data or grant runtime authority.
