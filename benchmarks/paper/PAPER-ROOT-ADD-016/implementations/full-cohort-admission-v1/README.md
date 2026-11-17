# Full-cohort cardiac reference preparation

This operator component admits the exact released 655-row Salzburg table,
prepares all six model inputs and scalar density checks, and independently
recomputes complete saved-draw summaries in the existing cardiac summary format.
It supplies source for reference review. It does not fit a model, accept a private
reference, launch a candidate or qualify scientific execution.

The [original task](../../task.json), [six-model endpoint](../six-model-summary/TASK.md),
[model contract](../matched-artifacts/MODEL_CONTRACT.json) and
[summary convention](../matched-artifacts/MATH_SPEC.md) remain unchanged. All 655
people are exposed development reconstruction inputs. There is no participant
holdout, added exclusion, raw ICA reconstruction or CamCAN replication here.

## Exact input and source preparation

Use Python 3.11 or later and the standard library. The component has no third-party
imports, network operations, inference engine or automatic acquisition. It requires
the admitted original CSV: 47,254 bytes, SHA-256
`6d122f256863197e49e9f7b39420cfe1c46741b3efa1fa66a6ec364337e48f11`.
The original ordered participant-ID digest is also checked. Neither identity can
be replaced by a CLI parameter. All four numerical columns must be complete,
finite and nonconstant; the CSV header and all 655 distinct IDs are mandatory.
The original index column has no newly invented range rule.

From a reviewed checkout, run:

```sh
python3 -I -S -B benchmarks/paper/PAPER-ROOT-ADD-016/implementations/full-cohort-admission-v1/admission.py verify-source
python3 -I -S -B benchmarks/paper/PAPER-ROOT-ADD-016/implementations/full-cohort-admission-v1/admission.py inspect-input \
  --csv /operator/inputs/meg_slope_data_sbg.csv \
  --out /operator/private/fresh-input-review
```

`verify-source` authenticates the five retained task/model/math/scorer dependencies.
The separately published [current source descriptor](../../../../integrity/current-closures/construction-cardiac-admission/SOURCE_BINDINGS.json)
identifies this new package and its tests. Trust those identities through a reviewed
release; running an untrusted replacement checker cannot establish its own trust.

The input report includes full-column population moments, all six separate raw or
standardized model preparations, their source-derived prior scales, the existing
sampling prescription and three independent scalar density expectations per model.
The log-sigma/log-nu Jacobian expectation is reported separately. Native density
comparison is explicitly unperformed. Density probes are operator preparation
data, not fitted posterior estimates or new candidate grading tolerances.

## Complete saved-draw review

For this operator review route, provide all 30 parameter streams: five parameters
(`alpha_c`, `beta`, `sigma`, `nu`, `alpha`) for each of six model identities. Every
stream contains exactly four chains of 2,000 retained draws in chain-major order,
as 64,000 bytes of IEEE-754 little-endian binary64 values. The total is 240,000
retained values, or 1,920,000 stream bytes. Nonfinite values, incomplete streams,
duplicate physical files and nonpositive `sigma`/`nu` draws refuse.

The new transport format is an operator interface choice. It does not replace the
existing candidate summary schema, require candidate draw export or reject a
candidate merely for using a different valid seed or sampler.

The private draw root contains `draws.json`, the 30 streams and three separately
pinned evidence bodies: producer source, an environment record and an execution
record. Those evidence bodies are authenticated as opaque bytes and never executed.
They remain declarations or externally reviewed provenance; their presence cannot
prove an inference run, independence, custody or data dependence.

The manifest has these exact fields:

```json
{
  "schema": "cardiac_operator_draw_review_v1",
  "benchmark_id": "PAPER-ROOT-ADD-016",
  "input_sha256": "6d122f256863197e49e9f7b39420cfe1c46741b3efa1fa66a6ec364337e48f11",
  "participant_id_sha256": "c7d967a7a66f506ff8b90ebd73e445453d5226845bb5308f2409ff00e2ae8682",
  "producer": {"path": "producer.py", "bytes": 1, "sha256": "REPLACE_WITH_EXACT_SHA256"},
  "environment_record": {"path": "environment.json", "bytes": 1, "sha256": "REPLACE_WITH_EXACT_SHA256"},
  "execution_record": {"path": "execution.json", "bytes": 1, "sha256": "REPLACE_WITH_EXACT_SHA256"},
  "models": {}
}
```

The example is deliberately incomplete. Populate `models` with exactly the six
names in `MODEL_CONTRACT.json`. Each model record has `fit_id` (a distinct declared
identifier), `requested_tune_per_chain: 2000`, `seed` (an integer or explicit null),
and `draws`. Each of the five `draws` entries has exactly:

```json
{
  "encoding": "float64-le-chain-major",
  "shape": [4, 2000],
  "artifact": {"path": "raw__ECG_components--beta.f64", "bytes": 64000, "sha256": "REPLACE_WITH_EXACT_SHA256"}
}
```

Every descriptor is a canonical relative path beneath the private draw root and
the exact byte count/hash of an ordinary single-link file. Files with identical
contents are permitted when they are physically distinct. Logical names, fit IDs
and pins do not establish separately performed fits. Raw and standardized models
still require separate inference; an affine posterior shortcut remains invalid.

```sh
python3 -I -S -B benchmarks/paper/PAPER-ROOT-ADD-016/implementations/full-cohort-admission-v1/admission.py review-reference \
  --csv /operator/inputs/meg_slope_data_sbg.csv \
  --draw-root /operator/private/saved-draws \
  --out /operator/private/fresh-reference-review
```

The command first checks the exact original input. It then authenticates every
evidence/stream body and independently calculates population means/SDs, the
historical shortest-94%-interval indexing convention and 100-draw batch MCSE.
It executes the authenticated current `summary_score.validate` body on the complete
result. It does not execute cached bytecode or copy a replacement scorer.

The generated summary preserves unknown diagnostics as null. Four chains and
2,000 retained draws are observed from the complete stream shapes; 2,000 tuning
steps are a manifest prescription, not an observation. Alpha identity errors
(`alpha - (alpha_c - mean(age)*beta)`) are reported across all draws, with no newly
invented tolerance or automatic acceptance decision. Unsupported finite arithmetic
refuses rather than clipping a result. Constant-draw summaries fail the unchanged
reference schema's positive-SD requirement.

Outputs are `input-preparation.json`, `reference-summary.json`,
`reference-review.json` and a final `receipt.json`. They are operator-only files
(0600) in a fresh private directory (0700), outside source/draw roots. The summary
matches the existing six-model grader interface but is **not an accepted reference**.
The component never emits an accepted reference-binding file. Independent operator
review must establish provenance, numerical and scientific competence and custody
before selecting it through the existing [paired binding interface](../matched-artifacts/README.md).

## Boundary and remaining evidence

All output qualification flags remain false. Reference review still needs authentic
input/rights evidence, independently established fitting/data dependence and
reference competence, native numerical comparison, convergence assessment,
complete execution records, measured capacity, protected custody and admission to
the current execution route. The existing mechanically packaged
`reference_program.py` is not an independent fitted reference.

The paper's [Statistical inference section](https://elifesciences.org/articles/100605)
reports no divergent transitions, R-hat below 1.05 and effective sample size above
400. It does not uniquely identify the ESS variant in that statement. Those are
historical diagnostics, not evidence supplied by this preparation command and not
new candidate rejection rules. The pinned author notebook uses `az.summary`; its
rounded displayed outputs are not authoritative posterior references.

Before accepting a new operator reference, record and independently review:

1. The exact original input, rights, source model and complete six-fit population.
2. Native density/Jacobian comparisons against the scalar expectations, with the
   selected numeric tolerance and environment recorded before comparison.
3. Independently established inference implementation/run provenance, seed choices,
   all prescribed chains/tuning/retained draws and complete sample statistics.
4. Diagnostics for every target, the exact R-hat/ESS definitions and a frozen
   convergence policy. Any stricter prospective criteria must be distinguished
   from the paper's historical report.
5. Independent run agreement and Monte Carlo error calibration for all six beta
   means and the reference-SD-normalized endpoint; summary agreement alone is
   insufficient. This component supplies no calibrated acceptance threshold.
6. Full-resource feasibility, stopped-producer/protected-reference custody and
   admission to the exact current paired execution route.

This evidence recipe is preparation for a separate scientific decision. None of
its unobserved requirements is marked passed by file hashes, declared fit IDs,
generated controls or the absence of a software exception.

Files must use absolute physical paths without symlink components or `..`.
Evidence/stream aliases are detected by physical file identity, including on
case-insensitive filesystems. Reads are individually bounded and reject snapshot
changes. This assumes trusted operator directories; it does not establish hostile
same-user filesystem isolation or atomic custody of a changing multi-file tree.
An input failure produces no success receipt. A write failure can leave private
partial output, which must not be treated as complete. No automatic retry occurs.

## Generated source checks

```sh
python3 -I -S -B -m unittest discover -s tests/construction -p test_cardiac_admission.py -v
python3 -I -S -B benchmarks/paper/PAPER-ROOT-ADD-016/implementations/full-cohort-admission-v1/test_admission.py -v
```

The first suite uses independently calculated full-655-row moments and closed-form
HDI/MCSE controls. The second exercises complete generated 30-stream evidence,
the real current summary validator, malformed/aliased streams, withheld authority
and production CLI refusal. Generated structural inputs cannot satisfy the frozen
original CSV/ID pins. No successful authentic-input CLI run, model fit, reference
admission or scientific qualification is claimed by these checks.
