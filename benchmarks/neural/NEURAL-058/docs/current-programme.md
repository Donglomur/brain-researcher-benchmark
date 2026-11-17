# NEURAL-058: current complete-programme source

The published [runtime declaration](../implementations/registered-runtime/manifest.json)
describes the full held-animal movement programme: **423 source sessions from 126
animals and 29 evaluation sessions from 13 disjoint animals**. Its status is
`source_only_unqualified`; collection and grading verification are `not_run`, and
both runnable and scientific admission are false. The [task definition](../task.json)
remains authoritative for the registered assignment.

The retained [runtime README](../implementations/registered-runtime/README.md)
describes an earlier exposed single-session, saved-oracle artifact control. Its
instruction to submit an arbitrary directory of listed files does not describe
the current manifest or bridge. Earlier qualification is explicitly not inherited
by the full programme. This guide clarifies the current source interfaces while
preserving those historical documents.

## Find the current source

From the repository root, inspect the public metadata:

```sh
python3 -I -S -B scripts/neurobench.py implementations NEURAL-058
python3 -I -S -B scripts/neurobench.py show NEURAL-058
```

These commands read source registrations and declarations; they do not launch the
programme or read neural inputs, private targets or execution receipts.

| Source | Role |
| --- | --- |
| [Registered bridge](../implementations/registered-runtime/score.py) | Central `collect` and `grade` interface named by the preserved runtime declaration. |
| [Complete programme](../implementations/programme-source/implementation-v1/README.md) | Scientific, preparation, candidate, reference, observation and grading implementation. |
| [Current runtime capture](../implementations/programme-source/implementation-v1/RUNTIME_SOURCE_V3.json) | Exact 41-module source capture used by the complete programme; V1/V2 and their history remain separate. |
| [Central integration](../implementations/programme-source/implementation-v1/central-integration-v1/) | Source authentication, route selection, independent review, dispatch and result readback around the parent programme. |

Neither the central bridge nor the parent's `program/entry.py` has an `inspect`
operation. Use the metadata commands above for discovery. The
[programme API](../implementations/programme-source/implementation-v1/API.md)
and [future operation recipe](../implementations/programme-source/implementation-v1/ROOT_RECIPE.md)
describe the executable source contracts and their admission requirements.

## Complete scientific scope

All original units, emitted intervals and required target timestamps remain in
scope. Seven additional sessions from evaluation animals are excluded from
training and checkpoint lineage. The primary endpoint is signed-velocity
animal-macro R²; absolute-speed animal-macro R² is separate. Negative R² is retained,
and required undefined support is not silently removed. The native-convention
diagnostic is distinct from these endpoints and does not establish SOTA.

The programme describes all 24 matched panels, 168 candidate contexts and 696
evaluation-session predictions. Frozen-program and investigation workflows have
matched whole-panel budgets; context/neural access and trained-tool conditions
remain explicit. These panels, contexts and predictions belong to one existing
task. They are not additional benchmarks or recorded successful runs.

The declaration's `default` collection condition and
`full423_29_held_animal_v1` name the same complete programme. They do not select the
old single-session control or two independent benchmark outcomes.

## Central collection and grading interface

The [bridge parser](../implementations/registered-runtime/score.py) declares the
following operands. This table describes the source contract; it is not a command
to run against the current unqualified checkout.

| Operand | Required meaning |
| --- | --- |
| `--operation collect` or `--operation grade` | Collection with independent observation, or separately authorized late grading. |
| `--condition default` | Default full-scope route; required for grading. Collection also accepts `full423_29_held_animal_v1`. |
| `--program` | For collection, the exact outer-operation request path selected by the review. For grading, the exact completed central-collection artifact path. It is not an arbitrary participant Python file or submission directory. |
| `--output` | Fresh central output location, disjoint from the original and protected namespaces and the other outputs specified by the operation. |
| `--review` | Exact independently admitted `neural058_central_review_v1` document in the source-owned operator-selection namespace. |
| `--other-reserve-bytes` | Nonnegative integer reservation matching the review's other-work accounting. |
| `--source-bytes`, `--source-sha256` | Independently selected identity of the central source manifest. A locally recomputed digest does not grant execution authority. |

The exact interpreter, argument order, working directory, source identity and
reviewed route are also checked. A valid parser invocation alone does not satisfy
those conditions. Grading has its own qualification and protected-target boundary;
it cannot reuse a collection success claim as permission to read targets.

For collection, the central dispatcher launches the parent's `--mode observe`.
That observer owns the literal `collect` child and verifies its complete public
production and closure. Only after successful independently observed closure may
late grading use the matching collection, observation, method/transcript graph and
private-target descriptors.

## Parent programme and deployment requirements

The parent's [literal entry](../implementations/programme-source/implementation-v1/program/entry.py)
accepts `--mode prepare`, `observe`, `grade`, `collect` and `native`. The future
owner recipe selects preparation separately, production through `observe`, and
late `grade`. The internal modes do not bypass their request and source checks.
Every invocation requires the exact source root, manifest and bootstrap pins,
request and request pin, the operation's original monotonic origin/deadline, and
selected read/write ceilings. Late grading has a fresh selected clock while the
production clocks remain frozen in its referenced receipts. The recipe contains
the full syntax and lifecycle requirements.

The unchanged bridge authenticates its historical entry locations and complete
source namespace. Directly invoking the relocated `registered-runtime/score.py`
with operational flags still fails that check. The additive
[source preparer](../implementations/registered-runtime/source-resolution/prepare_sources.py)
reconstructs **326 exact public source files** in a separate directory, including
the original `authoring/`, `tools/` and runtime-registry paths. Its
[source map](../implementations/registered-runtime/source-resolution/SOURCE_MAP.json)
binds every copied file; the four recovered historical helper bodies have explicit
[public provenance](../implementations/registered-runtime/source-resolution/PROVENANCE.json).
Preparation copies and verifies source bytes without importing the recovered
code, installing dependencies, reading neural inputs or authorizing an operation.
Review the [preparation contract and companion pins](../implementations/registered-runtime/source-resolution/README.md)
before copying source.

Replace both absolute paths below. The repository must be this complete public
checkout. The destination must not exist, must be disjoint from the repository,
and must have an existing parent directory. The repository, destination parent and
their ancestors must be ordinary directories, without symlink components. Python
3.9 or later supplies the standard-library interface used by this preparer; the
eventual scientific runtime needs its separately qualified interpreter and
dependencies.

```sh
NEURAL058_REPOSITORY='/absolute/path/to/brain-researcher-benchmark'
NEURAL058_PREPARED='/absolute/path/to/neural058-prepared-source'
python3 -I -S -B "$NEURAL058_REPOSITORY/benchmarks/neural/NEURAL-058/implementations/registered-runtime/source-resolution/prepare_sources.py" \
  --repository "$NEURAL058_REPOSITORY" \
  --destination "$NEURAL058_PREPARED" \
  --max-read-bytes 16777216 \
  --max-write-bytes 8388608 \
  --max-live-bytes 1048576 \
  --deadline-seconds 120
```

Require both exit status zero and `SOURCE_PREPARATION.json` in the destination.
The receipt's state is `source_prepared_not_qualified`; it explicitly grants no
runtime authorization or scientific qualification. The byte ceilings bound the
preparer's counted source reads, writes and retained source buffers; they are not
measurements or limits for total physical memory or CPU. Its deadline is checked
between operations; it is not a preemptive timeout. A failed preparation may
leave a partial directory. Diagnose the reported failure and select a fresh absent
destination before retrying.

After successful preparation, any independently admitted central invocation must
use the prepared directory as its working directory. The frozen collection route
selects `authoring/delivery-20261105/common/remaining-builds-wave29/neural058-complete-design/implementation-v1/central-integration-v1/entry.py`;
grading selects `benchmarks/neuroscience/neural-058-brainwide-wheel/score.py`.
Both source-manifest operands remain `--source-bytes 886` and
`--source-sha256 f3df6e660df0c81f330f6c2e7be255a95d079be408615a0842cfe040d953f214`.
These are historical logical paths inside the prepared directory; they are not
paths to run directly in this public checkout. The operand meanings above still
apply. Source preparation does not change the current `not_run` verification
or false runnable/scientific admission; it is not a collection or grading shortcut.

The preserved standalone recipe uses a `RUNTIME_SOURCE.json` deployment locator.
The preparer retains the `RUNTIME_SOURCE_V3.json` filename and does not create that
alias. The central route authenticates and passes its explicitly bound V3 manifest
path; it does not require an invented alias. Any separately selected standalone
deployment must follow its own authenticated source selection.

A reviewed deployment must admit the complete source closure and route before
selecting an operation. It still needs:

- All 452 original `all_units` objects with independently admitted membership,
  units/sign, clocks, full support and neural/context projections; separately
  prepared public and private stores.
- Qualified numerical dependencies, immutable native image, provider configuration,
  trained-reference competence, namespace isolation and complete physical resource
  bounds. Source recovery does not install or qualify these resources.
- Exact preparation, production, observation and late-grading selections, their
  independent evidence, and the actual process/stream closure records required by
  the original clocks. Candidate or producer booleans cannot substitute for them.
- Protection of evaluation-animal wheel values and target joins until the late
  scoring boundary, with complete matched panels and no cross-condition or
  cross-animal candidate-state transfer.

The [dependency and deployment notes](../implementations/programme-source/implementation-v1/SOURCE_DEPENDENCIES.md)
detail the environment, shared-clock, provenance and native-parity requirements.
The existing generated controls establish only the source behavior they exercise.
This guide adds no execution qualification, authentic-data result or benchmark ID.
