# Protected delivery for the current spinal condition

This additive implementation supplies candidate programs for
`current_source_noise7_eligible_v1`. It preserves the frozen bank
`33085162e9ba9ea64ef9862f681ec6f43c7065256b89430c313e5ac0dab5c726`, all
132 original recording census rows, exactly 116 eligible recordings and all
44 held-neuron folds (21 glutamatergic and 23 GABAergic neurons). The 16
source-noise exclusions remain operator records. It does not change the bank,
old native-400-ms delivery, historical-paper adapter, preparation receipts,
reference recipes or evaluator.

The source implementation and generated controls are complete. **No authentic
packet has been exported and no container, candidate, reference model or
scientific scoring has been run by this implementation.** Generated lifecycle
receipts test orchestration only; they are not evidence of actual isolation.

## Participant observations

Each fold exposes only the eligible recordings from the held neuron's own
cohort for training, excluding **every original recording of that held neuron**.
The unproved `*_mini` training restriction is not applied to this current
candidate condition. Other-cohort identities and observations remain operator
only; an all-other-43-neuron transfer condition is not implemented here.

| File | Permitted contents |
| --- | --- |
| `FOLD.json` | Held neuron, cohort, arm, purpose, fixed sampling/smoothing/support constants, and ordered original training/query recording boundaries |
| `training.npz` | Same-cohort nonheld fluorescence, electrical-derived `target_hz`, spike `counts`, fixed `support`, and `bin_centers_seconds` |
| `query.npz` | Held-neuron fluorescence, fixed `support`, and `bin_centers_seconds`; no electrical targets or counts |
| `paper.xml` | Exact pinned paper, identical in both arms |
| `author-code/…` | Only in `paper_data_author_code`: 18 pinned author source/license files, as listed in `ASSETS.json` |

Arrays concatenate original recordings without removing context bins. Each
manifest row records its offset and complete length; methods must respect
these boundaries. Fixed support excludes the first and last 32 bins of every
recording. It cannot be changed by a candidate. The bank's sampling/noise
realization is common across both access arms and all methods; it is not a
reconstruction of the paper's original stochastic realization.

`materials.py` projects a whitelist, retaining its full census plan only inside
the trusted operator. It never serializes `BANK.json`, event-count metadata,
source paths, target pins, another cohort's identities or held targets into a
participant file. It is a projection library, not an isolation boundary.

## Frozen programs and fold isolation

`transport.py` implements **frozen-program mode**, not an interactive agent
session. Both complete program trees, their configurations and the paired seal
are captured before the first labelled view is materialized. Every fold executes
that arm's same sealed program in a new container. This matters because labels
permitted in one fold are queries in other folds; a shared interactive context
or persistent model state would leak evaluation information.

Both arms receive identical data and paper bytes. Arm B additionally receives
the exact pinned source files. Program construction must itself respect the
declared access condition; this runner cannot prove what an external author or
model previously saw. Operator storage and program-submission custody are
trusted. The container image must be qualified as free of private data,
cross-fold artifacts, withheld author code/checkpoints and undeclared pretrained
information before real use. In particular, an author package preinstalled in
the common image would invalidate the intended access difference.

The existing task-specific Docker runtime, lifecycle, entry, holder and outer
child observer are reused byte-for-byte. `REUSE.json` records their provenance.
There is no host execution fallback for candidate code and no accepted
candidate-supplied lifecycle backend. The public CLI uses only that real Docker
path. Injectable in-memory boundaries are internal generated-control helpers.

For each of 88 contexts, the real lifecycle checks the exact fixed image and
mounts, no network, a read-only root, nonroot user, one CPU, explicit memory and
time limits, no swap/capabilities, bounded scratch and a fresh output volume.
Only current input files, sealed program/configuration and a minimal binding
are mounted. The operator bank, full census, reference predictions, other
folds, source checkout and Docker socket are never mounted. Candidate output
is held read-only after natural exit and producer removal; holder and volume
closure precede publication. The next fold is not started until the prior
labelled host view and trusted temporary view have been retired. Every context
namespace must differ across both arms.

The trusted lifecycle's program/source/runtime/input pins and resource settings
must match the operator's frozen configuration. Captured output is checked
against the trusted binding, then assembled into a separate candidate-only
bundle. Previous candidate outputs remain operator evidence and are never
mounted into later contexts. A first failure stops the campaign without retry
or a completion claim; private partial evidence may remain for diagnosis.

## Program and output interface

Each submitted directory contains `program.py` and at most 127 other source
files, at most 2,000,000 bytes total. `config.json` is reserved for the operator.
All file bytes are sealed; submitted code is not imported on the host.
The reused entry invokes:

```text
python -I -B /program/program.py --input /input --config /program/config.json \
  --binding /run/PROGRAM_BINDING.json --output /output
```

The configuration declares `reproduction` or `improvement`, the access arm and
`hz` or `expected_spikes_per_bin`. These are declarations, not evidence of
reproduction, superiority, model identity or training provenance. Candidate
source can read permitted author code from `/input/author-code` only in B.

The program writes exactly two files:

- `predictions.npy`: one real numeric vector with full concatenated query
  length in `FOLD.json` order, finite on every original recording's support.
- `fold.json`: exactly `schema=spinal_current_fold_prediction_v1`,
  `condition_id`, `held_neuron`, `arm`, `purpose`, `program_seal_sha256`,
  `binding_sha256`, `unit` and ordered `query_recording_ids`. The binding hash
  is SHA256 of the exact operator binding bytes. Program seal and query order
  come from that binding.

No target, support replacement, alignment adjustment or source reference
prediction is accepted in candidate output. `collect.py` uses the already
reviewed bounded numerical reader, preserves full per-record lengths and writes
the existing evaluator's candidate schema. All 116 eligible predictions are
mandatory in each arm's `candidate/PREDICTIONS.json`.

The operator separately supplies the four source-model reference arrays to
`current-condition-evaluator-v1`; raw fluorescence supplies the fifth original
control. The evaluator compares the same fixed support and retains its explicit
current aggregation within neurons and separate equal-neuron cohort summaries.
This delivery does not load or qualify those reference predictions. In
particular, same-cohort candidate training does not establish source reference
configuration, leave-neuron-out training, cortical-80 data or source-era model
provenance. Those remain separate construction requirements.

## Future execution and resource boundary

The CLI requires explicit `--bank`, `--assets`, `--program-a`, `--program-b`,
`--output`, `--docker`, `--docker-socket`, `--source-sha256`, `--purpose`,
`--unit`, `--candidate-seconds`, `--memory-bytes` and
`--other-reserve-bytes`. The source SHA freezes `SOURCE_MANIFEST.json`, which
pins every runtime file and fixed scientific dependencies. It is not a
readiness certificate or authorization to run.

The reused image is
`sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156`.
It is never pulled automatically. Its current availability, package/model
compatibility, contents and real Docker behavior are **unqualified** here.
The outer host observer launches its worker with the chosen interpreter's `-I`
isolation flag. Dependency availability in that isolated host interpreter has
not been tested by the in-process generated campaign and must also be qualified.
Selected per-fold time and candidate memory must fit an independently accepted
future execution protocol. This source accepts 1–7,200 seconds and
512 MiB–4 GiB, with one CPU and a 128-MiB holder; no such execution is currently
admitted. Tiny scratch/file limits can constrain prospective training methods
and must be considered before selecting a real program.

Host accounting prevents each next managed write/retained allocation and
declares 256 MiB retained, 2 GiB cumulative managed writes, 4 GiB managed reads,
and a 60-GiB free-disk floor plus other active reservations. This is cooperative
host accounting, not an OS I/O or operator-memory quota. Docker tmpfs, external
daemon/image storage and candidate memory have separate runtime bounds. Both
terminal receipts are precharged by their maximum 200,000 combined bytes;
the retained snapshot explicitly precedes those receipts. The outer receipt is
bounded and checked against the same retained limit. Successful worker records
still require observed natural-zero outer exit by the external supervisor.
Forcible host/daemon termination before Docker cleanup does not qualify closure.

## Generated checks and remaining scientific limits

The ordinary generated suite covers all 44 material projections, paired program
freezing, one complete 88-context campaign with 232 recording outputs, exact
candidate schema interoperability, source-bound support and record order,
private-field exclusion, retired prior views, first-failure behavior, changed
program/binding refusal, and preventive accounting. Its lifecycle is mocked;
no synthetic response is presented as a real container or scientific result.

Run the generated suite under the repository's shared two-slot bounded test
pool, with one thread and existing Python/NumPy only:

```text
python -B -m unittest discover -s benchmarks/paper/PAPER-paper-method-replacement-015/implementations/current-condition-delivery-v1 -p 'test_*.py' -v
```

Historical timing shifts, original paper aggregation/realizations, full
condition sweeps, cortical references, source-compatible executable controls,
actual isolation and candidate performance remain unresolved. No paper
reproduction, improvement, SOTA or statistical success threshold is established
by this delivery implementation.
