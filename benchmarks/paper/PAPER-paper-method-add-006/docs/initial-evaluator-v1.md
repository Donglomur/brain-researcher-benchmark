# Rat population geometry: initial evaluator v1

This package implements the rat Gaussian-basis Poisson GLM, its predicted-rate
participation ratio, and the covariance geometry equations for
`PAPER-paper-method-add-006`. It includes a complete local driver for the frozen
figure GLM basis across eight animals, eight sessions and both regions. It does
not establish an empirical reproduction or a scientifically qualified benchmark.
The canonical task and historical evidence remain unchanged.

The implementation is newly written mathematical and data-handling code. No
author code, notebook output, data, or result arrays are vendored. Source-code
redistribution rights at the pinned repository remain unresolved; paper and
DANDI terms must be reviewed separately before releasing any assets.

## Primary sources and exact scope

The source revision is `9674a6cb0c39926d70746024ce17de35f87df8f9` of
[population_geometry_optimal_coding](https://github.com/awakhloo/population_geometry_optimal_coding/tree/9674a6cb0c39926d70746024ce17de35f87df8f9).
The [journal paper](https://www.nature.com/articles/s41593-025-02183-y) is also
available as [PMC12971491](https://pmc.ncbi.nlm.nih.gov/articles/PMC12971491/).
The older arXiv v2 predates the rat extension and is not used to infer rat methods.

| Requirement | Primary evidence | Implemented behavior |
| --- | --- | --- |
| Animal and asset identities | `code/process_rats.py`, task inventory | Eight animals; nine DANDI 000978 version 0.240511.0307 NWBs; ZT2 has two files in declared order. Inventory retained in `source-contract.json`. |
| GLM covariates | `code/rat_utils.py:get_all_lat,bin_positions,bin_velocities,get_covs`; `code/fit-GLMs-rat.py` | Recorded speed strictly above 4 cm/s, position centered per session, basis centers pooled over that animal's first eight sessions; count strictly above 20; normalized Gaussian position and velocity bases; position bases gated by binary trajectory. |
| Source fitting | `code/fit-GLMs-rat.py` | Session-wide standardization before unshuffled ten-fold CV; per-unit Poisson GLM; ten alphas from 10^-0.5 to 10^2; finite-fold D² mean selects alpha; first index breaks ties. |
| Published GLM figure basis | `figures/Fig-readout-with-learning-hp-pfc.ipynb` | Spatial bin 10, velocity bin 3, spatial variance 100, velocity variance 40. The preceding 108-basis search is not reexecuted. |
| GLM dimensionality | `rat_utils.py:format_glm_results,get_pr`, figure notebook | Zero fitted columns if selected D² is at most zero or fewer than nine folds are finite; 19 neurons in each region; 500 independently drawn raw/fitted subset pairs. |
| Raw-count geometry | `rat_utils.py:process_dat`; `run-pfc-hp-analysis-rats.py`; `utils.py:get_geometry,theory_part` | Vector-velocity norm strictly above 4; count rate strictly above 0.1 Hz; `(count-mean)/(std+0.01)`; z-score position and vx/vy; covariance divisor N; eight geometric measures and direct theoretical error. |
| Alternative regularization construction | Task improvement contract | Separate fixed-alpha train-only helper; transformations and eligibility fitted on training rows. It is a prospective within-session recipe, not an animal-transfer result. |
| Cross-region report | New prospective reporting choice | Require every declared animal/session/region; CA1 minus PFC, equal session weight within animal and then equal animal weight. No significance or target threshold is inferred. |

All source constants are reconstructed explicitly. The source GLM filters on
recorded speed `z[:,2]`, whereas raw geometry filters on the norm of velocity
`z[:,3:5]`. These are intentionally distinct. The GLM expected-rate PR is also
distinct from the normalized linear task-subspace dimension returned by the
covariance equations. Position/velocity Gaussian parameters are variances, not
standard deviations. Weighted factorization includes diagonal terms and weights
by coding strength; orthogonal equally strong directions give `1/D`, not zero.

One numerical extension is explicit: weighted factorization is evaluated as
`sum((Phi.T @ Phi)^2) / trace(Phi.T @ Phi)^2`. This is algebraically identical
to the source's weighted squared-cosine expression when each coding direction
is nonzero. It also provides the continuous limit when an individual direction
is zero and total alignment remains positive; the source's column-normalized
calculation is undefined there. Zero total alignment is rejected. This extension
is not evidence of numerical agreement with a native source run.

There are unresolved source/paper differences. The published raw readout uses
24 CA1 and 19 PFC neurons; the pinned raw script uses 19 for both. The GLM figure
notebook uses 19 in both regions. Published GLM prose says D² below zero is
replaced by the null model, while source uses D² at most zero plus the valid-fold
criterion. This implementation follows the pinned GLM code at that boundary and
does not claim exact paper equivalence. Zeroing predictions is equivalent to a
constant null rate for centered PR. The panel uses a recorded `default_rng` seed;
it does not reproduce the author's unrecorded GLM subset RNG stream.

## Interfaces

Use Python with NumPy and scikit-learn already available. Engineering checks used
Python 3.11, NumPy 2.4.6, SciPy 1.17.1 and scikit-learn 1.9.1. No dependencies were
installed. The source did not freeze dependency versions; numerical equality to
an author runtime therefore remains a gate. Fitting runs serially and turns
convergence warnings into failures. This intentionally exposes failures the
author's warning suppression could hide.

`evaluator.py` provides functions and five CLI modes:

```text
python evaluator.py geometry covariance-input.npz geometry.json --training-samples 300
python evaluator.py source-glm session.npz glm.json --parameters basis.json
python evaluator.py source-panel panel.json panel-results.json --seed 123
python evaluator.py train-only split-session.npz prospective.json --parameters basis.json --alpha 1
python evaluator.py contrast paired-results.json contrast.json
```

`geometry` requires finite `responses` and `latents` matrices with aligned rows.
These are analysis-ready representations; the mode centers them and forms the
joint covariance. For raw processed counts, call `prepare_geometry_session`
first. `geometry_from_covariance` validates symmetric positive-semidefinite
joint blocks, an invertible latent covariance, nonzero total signal and valid
sample count. It rejects singular covariances rather than quietly substituting
a pseudoinverse. Infinite noise factors have an explicit JSON status and null
numeric field; JSON never contains NaN/Infinity literals.

GLM inputs use `latents` with seven columns in this exact order:
`x_cm,y_cm,recorded_speed_cm_s,vx_cm_s,vy_cm_s,correct,trajectory_type`.
`counts` are nonnegative integer spike counts in 0.5-second bins, rows aligned
to latents and columns aligned to units. Trajectory must be 0 or 1. A one-session
`source-glm` input also includes `pooled_latents`, assembled from all eight
speed-filtered, separately position-centered sessions of the same animal.
That low-level call cannot attest the pool's provenance; use `source-panel`
for the population driver. `basis.json` contains `position_bin`, `velocity_bin`,
`position_variance`, `velocity_variance`, and optional `min_count` (default 20).

`source-panel` reads a JSON manifest with these top-level fields:

```json
{
  "source_revision": "9674a6cb0c39926d70746024ce17de35f87df8f9",
  "dandiset_version": "0.240511.0307",
  "sessions": [
    {
      "animal": "KL8",
      "session_index": 0,
      "epoch_id": "EXPLICIT_NATIVE_EPOCH_ID",
      "path": "KL8/session0.npz",
      "bytes": 123,
      "sha256": "REPLACE_WITH_ACTUAL_64_CHARACTER_SHA256"
    }
  ]
}
```

The example is intentionally incomplete and cannot execute. A real manifest
must contain exactly 64 distinct rows: animals `KL8,ER1,JS34,JS14,JS17,JS21,JS15,ZT2`
and session indices 0 through 7. Epoch labels must be unique within animal;
paths must not repeat. Each file must match its byte count and SHA-256 before
safe loading with `allow_pickle=False`. NPZs include the latent/count arrays
and nonempty string `locations` aligned to unit columns. Only exact `CA1` and
`PFC` labels enter their respective fits; other labels remain excluded without
an invented anatomical mapping. Unit maps are session-specific, including ZT2.

The driver fits both regions at the frozen figure basis, retains selected alpha,
input hashes, eligible/suppressed counts and all explicit unit-subset indices,
then produces descriptive region contrasts. It fails on missing sessions,
insufficient units, empty bases, constant covariates, nonconvergence or entirely
undefined CV scores. It never reduces 19 neurons, ten folds or 500 subsets to
make a dataset pass. Subsets are sampled independently for raw and fitted PR,
as in source. The driver itself has not been run on authentic inputs.

`train-only` needs explicit integer `train_indices` and `test_indices`. These
must be nonempty, distinct within each partition and disjoint. The caller must
freeze them and alpha without assessment access. Movement filtering preserves
the original indices. Position centering, basis occupancy, covariate moments
and unit-rate eligibility use training rows only. Test targets cannot affect
fits. This is within-session adaptation to the same units; neurons from
different animals are not assumed aligned. No nested animal-level choice of
alpha, prospective animal/session assessment, or nonlinear readout is claimed.

`contrast` takes `rows`, `expected_sessions` pairs and a `metric` key. Every
expected pair must have exactly one finite CA1 and one finite PFC metric. Extra
rows and missing regions fail. The animal is the reporting unit. The function
does not perform the paper's quadratic mixed-intercept trend analysis.

## Native bridge and retained gates

The pinned NWB loader reads trials start/stop/correct/trajectory type, `epoch
intervals`, unit spike times and electrode locations, and
`processing/behavior/Position/SpatialSeries` timestamps/data. It bins at 0.5 s,
interpolates position with Gaussian bandwidth 0.05 s, and smooths derived
velocity with bandwidth 0.7 s. ZT2's two assets concatenate sessions and preserve
separate unit maps. The source's bin-edge construction can omit the final
partial interval; this package does not silently implement a different native
adapter. Native field units, epoch order, boundaries and payloads remain
unverified. Asset IDs and sizes in `source-contract.json` are inventory facts,
not acquisition receipts or content checksums.

Remaining gates include authentic full-panel execution; source-runtime and
independent numeric reference agreement; complete 108-basis search if claimed;
the raw-readout neuron discrepancy; exact epoch mapping and native ingestion;
paper-specific targets/tolerances; mixed-effects session trends; independent
animal/session assessment and nonlinear improvement; protected reference access
and public notebook-output exposure; source/data rights; measured resources and
difficulty; and non-rat/simulation coverage. Better decoding never proves an
optimal biological code. All CLI outputs retain `research_qualified=false` and
`full_contract_complete=false`.

## Engineering verification

Run from the repository root:

```text
PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3.11 -m unittest discover -s benchmarks/paper/PAPER-paper-method-add-006/implementations/initial-evaluator-v1/tests -v
```

Ten controls were independently derived from closed-form covariance identities
and the primary source. Additional tests compare actual bounded Poisson CV fits
against independent scikit-learn scoring, poison test labels/covariates to check
training isolation, distinguish both movement cutoffs, exercise null masking,
test invalid tiny-scale covariances, prevent population omission and duplicate
subsets, verify animal-weighted aggregation, and exercise the JSON CLI. These
generated controls establish engineering behavior only. No NWB files, native
scientific runs, archive downloads, paid/model/API campaigns or result claims
were used.
