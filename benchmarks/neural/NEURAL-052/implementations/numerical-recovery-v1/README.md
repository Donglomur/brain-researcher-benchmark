# Recovered numerical investigation

This package restores the executable NEURAL-052 numerical bodies omitted from
the registered-runtime declaration. It retains the existing prospective
three-person THINGS-fMRI investigation: all 100 repeated concepts, 12 sessions,
1,200 rows/person, independently defined complete V1/IT ROIs, 15 crossed
concept/session folds, four fixed ridge models, and 1,000 shared concept draws.
It does not replace the canonical task or its historical specification.

The recovered [protocol](TASK.md) defines continuous liveliness and size norms,
not binary animacy or physical length. The primary arithmetic score is mean
absolute error across all 18 person × ROI × incremental-variance estimates.
Signed negative biological effects remain valid. The code also returns
within-person IT-minus-V1 differences, equal-person descriptive summaries,
training-only reliability controls, and explicit undefined support.

`SOURCE_RECOVERY.json` pins the exact predecessor files. Seven implementation
modules, four predecessor generated-test modules, four protocol documents and
the original numerical dependency pin are byte-identical recoveries. A fifth
test module replaces one external-DESIGN check with generated metadata so this
source-only suite does not require an authentic packet. The new
`run.py` supplies an explicit external packet location and checks that both
`result.json` and nonempty UTF-8 `METHODS.md` are present. It records the prose
hash without grading interpretation quality. The new generated test module
checks the four-model endpoint against an independently implemented augmented
least-squares calculation, signed-error scoring, and the new entry points.

## Operator use

Authentic numerical execution requires the existing complete external packet;
no data search or download is performed. `--packet-root` must contain:

```text
private/DESIGN.json
private/PACKET_BINDING.json
public/input/INPUTS.json
public/input/features.json
public/input/<three metadata JSON files>
public/input/<three response NPY files>
```

The unchanged loader checks exact design identity, all seven member hashes,
100 concepts, participant IDs, full native ROI counts (5,130/4,962/4,218 union
voxels), complete concept/session support and finite native float32 responses.
It verifies bounded regular NPY files before and after same-open decoding;
there is no pickle loading, partial-panel CLI option, or implicit imputation.
The closed packet binding is an operator trust anchor and must be provisioned
from the retained source receipt. Copying these source files alone does not
recreate or authenticate that external packet.

With an existing environment satisfying `requirements.txt`, run from this
directory and provide fresh output paths outside the repository:

```sh
python -B run.py schema --packet-root /external/packet --output /external/submission.schema.json
python -B run.py reference --packet-root /external/packet --output /external/reference.json
python -B run.py score --packet-root /external/packet --submission /external/result.json --methods /external/METHODS.md --output /external/score.json
```

The schema command reads identity metadata only. Reference and score perform
authentic numerical work and require the project's separately scheduled native
execution protocol. This recovery did not run them on authentic observations.
Use `run.py` for the portable route: the unchanged predecessor `grade.py` and
`reference.py` retain their old package-relative command-line defaults.

`prepare_packet.py` also preserves the original exact projection recipe from
the complete shared V1/IT source pool. It requires pinned original design,
source metadata and acquisition evidence; it is not a dataset downloader.
Reuse accepted matching preparation rather than rerunning that projection.
The retained TASK/INPUTS/SOURCES/FEATURE_PROTOCOL documents describe predecessor
construction evidence, not newly executed preparation. The source-only recovery
does not ship images, arrays, feature values, targets, outputs or local paths.

## Qualification boundary

The two-slot pool run `neural04-n052-recovery-05` passed all 54 generated
checks (Python 3.12.8 / NumPy 2.4.6): 0.405 seconds in unittest, 0.485 CPU
seconds and 66,502,656-byte peak child RSS. Coverage includes the independent
four-model arithmetic oracle, negative effects, exact constant responses,
training-only reliability/scaling, row permutation, missing panel support,
same-open file mutation, and malformed-report rejection before numerical
loading. The earlier run had one missing external-DESIGN test dependency;
the adapted generated test fixes that dependency without reading real data.

This is numerical source recovery with generated software controls. All neural
responses are intentionally public in the investigation condition; internal
cross-validation does not create an unseen-outcome actor evaluation. The
protocol remains a prospective extension of the author's in-sample OLS, not
original-paper reproduction, superiority, causal evidence or population
generalization. Direct/viewer access and a scientific reasoning rubric remain
undelivered. No candidate trial, authentic reference fit, empirical score or
new source acquisition was performed here.

The original numerical pin remains NumPy 2.2.6. Current generated replay uses
the available NumPy 2.4.6 environment; compatibility checks do not qualify a
change to the authentic numerical environment. Runtime/memory qualification,
independent authentic recomputation, external-packet reauthentication and
central catalog/contract integration remain separate work.

## Participant public-package preflight

`participant_check.py` supplies the schema and complete report-structure check
using only the delivered public `input/` directory. Participants do not need
operator-private DESIGN or PACKET_BINDING files. Obtain the INPUTS.json SHA-256
from the operator's delivery record; a digest derived from an untrusted local
replacement does not establish packet authenticity.

```sh
python -B participant_check.py schema --input-dir /input/input --manifest-sha256 "$INPUTS_SHA256" --output /work/submission.schema.json
python -B participant_check.py check --input-dir /input/input --manifest-sha256 "$INPUTS_SHA256" --submission /work/result.json --methods /work/METHODS.md --output /work/preflight.json
```

Run these participant preparation commands from this source directory with
Python 3.9 or newer; they require only the standard library. The route captures
the pinned manifest and features JSON, derives only concept/feature/participant
identity, and reuses the unchanged complete report contract. No response matrix,
private file, reference fit, candidate programme or network route is opened.
The result must include all three people, both ROIs, all endpoints and support
dispositions, and bind the same public manifest; METHODS must be nonempty UTF-8.
An exit code of 0 and `valid_structure` mean only that those public structural
checks passed. A numerically wrong report can pass. Complete packet integrity,
numerical reconstruction and interpretation quality remain separate. Failures
return `preflight_rejected` and exit code 2; output files must be fresh.

This optional preparation utility does not alter the frozen programme's
14-file exposure, runtime dependencies, allowed in-trial actions, or resource
limits. It is not automatically mounted into a participant container. Enrolling
it in a future matched-condition delivery requires the operator to freeze that
delivery and any preparation budget equally across compared participants.
