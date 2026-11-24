# Public behavioral submission preparation

`submission.py` prepares and checks the existing source-compatible Figure 1
e/g/h/k submission without the owner-local scorer, private reference, NWB files,
Docker image or additional packages. It uses Python's standard library and the
two unchanged public contracts in the sibling `registered-runtime` directory.
Both contracts are checksum-pinned; an alternate `--public-dir` must contain
those same bytes.

The checked-in registered scoring adapter depends on an owner-local authoring
tree. This helper gives participants a usable preparation/preflight path in a
repository checkout, while preserving that scorer and its historical evidence.

From the repository root:

```sh
python3 -B benchmarks/paper/PAPER-FIND-044/implementations/public-submission-v1/submission.py scaffold --output /path/to/new-submission.json
python3 -B benchmarks/paper/PAPER-FIND-044/implementations/public-submission-v1/submission.py validate --submission /path/to/submission.json
```

The scaffold contains all 309 sessions, 8,679 original cue slots, 302 distinct
mouse/day identities through day 8, 38 mice, 440 trial-level group summaries,
six group endpoints and three comparisons. It keeps the recording-cohort mice,
split-session cue identities and day-9 sessions. Split sessions contribute one
daily identity; day 9 is outside the declared daily learner calculation.

Every scientific observation/status starts **unresolved**. Zero counts and
`cutoff_applied: false` are placeholders, except for the already-public original
cue counts and identity fields. They are not inferred results. Populate the
tables from the original data under the common instructions, retaining removed
and unresolved cue rows. The scaffold is not a completed scientific submission.

Preflight checks the exact public headers, columns, full identity sets, status
vocabulary, status-dependent nulls and scalar/container types. Each endpoint's
included/excluded mouse inventory must partition its complete condition roster.
It also applies the public UTF-8/JSON parser limits and the 2.5 MB payload cap.
Rows may be reordered. Negative normalized lick counts/rates and the explicitly
declared out-of-range source F-probability status remain representable.

Finite inaccurate numbers remain valid, including inconsistent counts,
eligibility or uncertainty. Preflight does not compare an answer with a private
reference, test arithmetic consistency, infer missing values or judge scientific
success. Its successful result is `public_format_valid`, with
`scientific_score: null` and `numerical_correctness_checked: false`. The existing
owner-side scorer remains authoritative for grading; equivalence with its
private validator has not been established. A scaffold passing preflight does
not establish successful reconstruction.

`scaffold` requires a new output path. `validate` prints a report to stdout, or
accepts `--output NEW_REPORT.json`. Invalid input or an existing output path
returns exit code 2 with a JSON error on stderr; existing files are not replaced.
Keep actual submissions and reports outside the source repository.

## Source and information conditions

The exact format comes from the existing
[`SUBMISSION_SCHEMA.json`](../registered-runtime/SUBMISSION_SCHEMA.json), with
identities from [`PUBLIC_CONTRACT.json`](../registered-runtime/PUBLIC_CONTRACT.json)
and scientific conventions from
[`INSTRUCTIONS.md`](../registered-runtime/INSTRUCTIONS.md). This helper provides
no author analysis code, calculated outcomes, thresholds or hidden references.
Any future participant packet that includes it must expose the identical helper
and contracts to both paper+data and paper+data+author-code conditions. Current
packet manifests and runtime bindings are unchanged by this component.

This is preparation for the retained 60s/600s behavioral calibration component.
It does not bind the unresolved matched primary comparison, add dopamine
endpoints, qualify the five-ITI model comparison, establish a code-access
effect or promote reproduction/improvement readiness.

## Generated controls

```sh
cd benchmarks/paper/PAPER-FIND-044/implementations/public-submission-v1
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest -v test_submission
```

The tests use only the public identity inventory and generated values. They
exercise complete original support, split-session/day handling, removal without
dropping cue rows, duplicate and cross-condition identity errors, endpoint
partitions, signed rates, defined/undefined status branches, finite inaccurate
answers, strict parsing, public-source pins and the command interface. No
authentic numerical reference, animal data or scientific run is involved.
`FIND044_PUBLIC_DIR` can locate the same pinned public files for a staged test;
`TMPDIR` can place the single temporary generated submission in an allocated
working directory.
