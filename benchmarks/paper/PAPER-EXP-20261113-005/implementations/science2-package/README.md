# PFC task package materialization

`materialize.py` constructs the existing PFC Full99 Science2 task in the exact
`tasks/life-sciences/neuroscience/pfc-conditional-reconstruction` directory.
It authenticates all 15 frozen task source files, the four already released
public inputs, and four separately pinned release notices before writing.
It renders the two literal Dockerfiles, copies the packet independently into
both build contexts, preserves notices in both, and verifies every output byte.
The evaluator and oracle remain outside the agent build context.

This closes an executable packaging gap. It does not produce an additional
benchmark or establish image, native-harness, scientific or submission readiness.
No authentic public asset has been opened or staged in this source phase.

## Preserved endpoint

The unchanged scorer and independently authored oracle compute all 69 full and
whole-animal-deletion cases for all twelve families of the complete fixed map.
The 19,186 fitting units/68 animals differ from the scored PFC population of
10,243 units/65 animals. No map refit, generalization or frontier result is claimed.
All scientific source, the instruction, exact reward and task.toml are unchanged.
Only the copied README's packaging/artifact explanation and PACKET_SCHEMA's stale
TASK.md pointer changed. SOURCE_MANIFEST records every predecessor identity.

This remains the open-internet/eight-hour Science2 profile. It cannot establish
the original offline paper/data-versus-official-code access comparison: public
code and the analytic oracle are discoverable online.

## Use after input admission

An operator supplies a JSON request with exactly these fields:

```json
{
  "schema": "PFC_SCIENCE2_MATERIALIZE_V1",
  "asset_root": "/absolute/selected/release-directory",
  "output_root": "/absolute/new/tasks/life-sciences/neuroscience/pfc-conditional-reconstruction",
  "agent_image": "registry.example/reviewed/pfc-agent@sha256:<64 lowercase hex>",
  "verifier_image": "registry.example/reviewed/pfc-verifier@sha256:<64 lowercase hex>",
  "notices": [
    {"name": "ATTRIBUTION.md", "bytes": 0, "sha256": "<reviewed digest>"},
    {"name": "PUBLIC_LINEAGE.json", "bytes": 0, "sha256": "<reviewed digest>"},
    {"name": "DANDI_TERMS.md", "bytes": 0, "sha256": "<reviewed digest>"},
    {"name": "RELEASE_NOTES.md", "bytes": 0, "sha256": "<reviewed digest>"}
  ]
}
```

The example is intentionally invalid. Exact notice pins must come from the
accepted release evidence, not invented values. The selected release directory
contains exactly the four named assets and four notices, all ordinary single-link
files. Output parents must already exist and the task directory must not exist.

Run the selected Python interpreter with `-I -S -B materialize.py REQUEST.json`.
Retain its complete JSON stdout as the operation receipt. Failed writes preserve
partial output and cannot be reused as a fresh task. The operator owns process
deadlines and complete stderr/exit capture; this task-specific copier launches no
subprocess or network call. Its managed-body ceiling is 32 MiB, output task ceiling
16 MiB, notice member ceiling 256 KiB and source namespace ceiling 128 entries.
These are explicit body/namespace checks, not OS-wide resource quotas. Inputs and
output are assumed to be exclusively owned during materialization; the checks
are sequential observations, not a hostile-filesystem atomic snapshot.

## Runtime and harness binding

Image syntax must be an explicit repository manifest reference. A local Docker
config ID is not a registry manifest digest. The materializer does not inspect an
image or certify platform, availability, installed packages or redistribution.
The operator must admit those properties before a later build. The currently
constructed local shared runtime has no public manifest reference inferred here.

Harbor's pinned resolver recognizes `tests/Dockerfile`, not its template. A
`verifier.environment.docker_image` override takes priority and suppresses test
upload. Consequently the bare numerical base must not be assigned there: the
complete evaluator sources and assets must be baked into the verifier image.
This package preserves the two real build contexts and no prebuilt override.

The PFC evaluator consumes only `/app/output/submission.jsonl`. Harbor can also
transport its conventional artifact directory. Fixed evaluator paths and imports
remain unchanged; source inspection is not observed isolation.

Primary interfaces were checked at
[Science 45195b2](https://github.com/harbor-framework/terminal-bench-science/tree/45195b2af0653ddc12d43838d9096add9f52acf2)
and [Harbor ec6aeab7](https://github.com/harbor-framework/harbor/blob/ec6aeab7fe0eb51df52b4e72c524daf5ea9cc5f4/src/harbor/models/task/verifier_mode.py).
The separate interface opinion binds exact primary sources and limitations.

## Validation and next operation

Twenty-five invented-asset controls passed through the real copier. They cover
complete source/render/copy/readback, independent packet copies, strict context
separation, source/asset changes, missing or extra answers, aliases, image-command
injection, namespace/byte bounds and preserved corruption failures. Their tiny
invented asset identities replace only the four production expected asset pins;
no scientific kernel, native package or container is executed. Three actual
pinned upstream checks passed on the generated invented package: task structure,
agent Dockerfile references and baked verifier tooling. This is not the full
upstream format check or a Docker build.

The next concrete operation requires exact already accepted release paths and
notice pins, separately admitted image manifest references, an absent output
task namespace and owned process capture. One materialization and independent
complete output review can then be selected. No asset download, authentic copy,
build, model trial or upstream submission is selected by this source package.

Real author/domain review, metadata and expert-time estimate, managed README
header, complete upstream checks and hosting policy remain unresolved. Preserve
the truthful blank author fields. Native Harbor oracle pass, no-op fail,
corruption failure, infrastructure-error handling and actual artifact isolation
must be demonstrated on the intended runtime. Difficulty calibration remains a
separate authorized study. The upstream rubric's domain-knowledge/research-level
requirement needs a domain review; a mathematically correct finite task alone
does not demonstrate that it is appropriately difficult for the main Science set.
