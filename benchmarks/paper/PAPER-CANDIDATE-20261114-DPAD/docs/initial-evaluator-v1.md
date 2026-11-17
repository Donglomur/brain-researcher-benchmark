# DPAD Figure 6h–i initial evaluator

This package completes a paper-grounded **prediction-evaluation component**: it
selects architectures and state dimensions using training-only result records,
then recomputes channel correlations, complete grid results, paired comparisons
and the nonlinear-locus frontier from held prediction arrays. It does not fit
DPAD, prepare authentic neural data, certify the seven-session mapping, reproduce
the figure, or establish a scientifically qualified benchmark. The canonical
registration and its readiness fields are unchanged.

The scientific question is where nonlinear mappings must be placed to explain
behaviorally relevant neural dynamics. Evaluating behavior alone cannot answer
it; the output retains both neural self-prediction and behavior CC for every
declared placement, state dimension, session and fold.

## Sources and frozen semantics

The primary paper is Sani et al., *Dissociative and prioritized modeling of
behaviorally relevant neural dynamics using recurrent neural networks*,
[Nature Neuroscience, DOI 10.1038/s41593-024-01731-2](https://www.nature.com/articles/s41593-024-01731-2).
Relevant sections are the Figure 6 caption, cross-validation, latent state
selection, performance frontier, flexible nonlinearity, and fourth dataset.
Pinned current source is
[DPAD evaluation.py at 41f108bc90252ced19fe3c8eda7eaff2e87c57b3](https://github.com/ShanechiLab/DPAD/blob/41f108bc90252ced19fe3c8eda7eaff2e87c57b3/source/DPAD/tools/evaluation.py).
Source identity and metadata hashes are in `../implementations/initial-evaluator-v1/provenance.json`.
This implementation independently expresses the mathematical rules and does
not vendor the USC-licensed implementation.

The component fixes the following coverage:

* Seven candidate Indy sessions, five equal continuous outer folds, dimensions
  1, 2, 4, 8, 16, 32, 64 and 128, with `n1=min(16,nx)`.
* Fully linear, only A-prime/K/Cy/Cz nonlinear (one hidden layer, 64 ReLU units),
  and both decoding-focused and neural-self-prediction-focused flexible models.
* The flexible model's full 90-architecture training search: 61 linear/feedforward
  cases and 29 LSTM-recursion cases. Local architecture labels describe the
  mathematical alternatives; they are not claimed to be native DPAD config names.
* Two inner-fold CCs for each architecture. The decoding-focused selector maximizes
  neural CC among architectures within one SEM of the best behavior CC; the
  prediction-focused selector reverses the metrics. Exact ties use lexical local
  architecture IDs, an explicitly prospective deterministic choice. The pinned
  source defines the one-SEM threshold as `max(mean - SEM)` across candidates;
  this detail matters when their variances differ and is implemented explicitly.
* For each method and outer fold, choose the larger of the smallest state
  dimensions attaining the peak training neural CC and peak training behavior CC.
  The current source's generic selection helper defaults to a one-SEM rule; the
  historical Figure 6 caller has not been located. The implementation follows the
  paper's explicit peak wording and does not assert historical caller equivalence.
* All 1,960 held cases (7 sessions × 5 folds × 8 dimensions × 7 method profiles)
  are required, including dimensions not selected. The selected figure comparison
  retains 245 method/session/fold outcomes.

Per-channel Pearson CC is recomputed from paired sample arrays, followed by the
arithmetic mean across channels. It is not a correlation of flattened channels.
Raw constant truth or prediction channels produce undefined CC; the evaluation
boundary rejects them instead of silently dropping channels. Current official
`evaluateDecoding` drops invalid prediction rows and later `sanitize_perfs` may
replace means with `nanmean`. This package's finite/full-coverage rule is a
**prospective admission rule** that prevents selective missing predictions from
improving a score. Historical sanitization equivalence remains unresolved.

The paper's frontier requires a one-sided paired signed-rank P≤0.05 and at least
1% relative mean difference, with the comparator mean's absolute value as the
denominator. A method is excluded if some comparator is significantly better in
at least one metric and the method has no significantly better metric in return.
The implementation computes an exact conditional sign-permutation distribution,
average ranks for ties, and removes zero differences. This explicit numerical
profile avoids runtime-dependent approximation defaults but is **not certified
equivalent to the historical SciPy runtime**. Nonzero changes from a zero
comparator mean satisfy the effect-size threshold. SEM uses population standard
deviation divided by square-root count, matching the pinned current source
helper. Historical caller/runtime equivalence remains open.

Signed ranks determine the direction of significance. The absolute relative
mean difference is an effect-size gate; it does not impose an additional mean
direction requirement. Strong outliers can make the mean and signed-rank
directions differ, and the output preserves the source rule in that case.

The paper reporting unit is 35 session-fold pairs. The result labels the
dependence between folds; those SEMs and tests are not independent-session
uncertainty estimates. Additional session summaries average five folds equally.
Animal summaries average seven session means and explicitly identify the single
animal, Indy. These additional summaries are descriptive, not generalization to
an animal population. Every directed nonlinear-locus/comparator contrast appears
in `frontier.pairwise`; no contrast is selected after inspecting the scores.

## Interface and trust boundary

Python 3.10+ and its standard library are sufficient. There is no downloader,
model loader, dependency installer, native DPAD import, or arbitrary code runner.

`evaluator.py select --training training.json --output selection.json` reads only
training metadata. It cannot access held targets. The evaluator owner freezes
and protects the resulting selection file before candidate held predictions
are accepted. A canonical-content SHA256 binds prediction files to that plan.
This is a binding check, not a signature or proof of chronology: a participant
must not be allowed to replace the owner-controlled plan or training records.

`evaluator.py evaluate --targets targets.json --predictions predictions.json
--plan selection.json --output results.json` reads protected target arrays,
candidate prediction arrays and the owner-frozen plan. It recomputes every held
CC and reports all grid rows, selected rows, session/animal summaries, paired
tests and the frontier. Unknown case/method/dimension identities, duplicate JSON
object/case keys, missing cases, reordered sample IDs, nonfinite numbers,
undefined channels and profile drift are rejected. Additional metadata fields
are accepted but confer no validation or qualification.

The generated fixture is the executable schema example. All artifacts contain
the same `protocol` with task ID, profile, fixed session/dimension/fold lists,
per-session sample counts, animal IDs, filter support and purge widths, neural
input lag, and held-behavior-use declaration. The protocol accepts only
`generated_engineering_control` or `owner_supplied_unverified` reference kinds;
neither upgrades qualification.

Training `cases` contain one record per session/fold, unique `fit_sample_ids`
and `selection_sample_ids`, and every dimension's 90 architecture records. Each
architecture record contains two `inner_neural_cc` and two `inner_behavior_cc`
values, plus scalar `training_neural_cc` and `training_behavior_cc`. These are
owner-audited training result records, **not independently verified model fits**.
Dimension selection uses the selected architecture's training CCs. The scorer
does not establish that the training metrics, budgets or configurations are true.

Protected target cases contain `session_id`, `fold`, ascending `sample_ids`, and
time-by-channel `neural` and `behavior` arrays. Prediction cases add `method`,
`dimension` and `architecture` and contain aligned arrays for the complete block.
Session length must be divisible by five in this explicit continuous-block
profile; no historical rounding convention is invented. Channels must already
be fixed and aligned by the protected preparation step.

The declared historical symmetric-filter profile remains separate from the
prospective causal profile. Causal profiles reject future filter support and
training/selection samples whose declared filter support or purge intersects
the held block. Both profiles require past neural input (`neural_lag_samples≥1`)
and prohibit held behavior inputs. These checks audit declarations and sample
memberships; they cannot prove upstream inference causality, context handling,
or correct filtering. No target is passed to a model by this package.

## Engineering verification

From the package directory, set `PYTHONDONTWRITEBYTECODE=1` and run:

```sh
python3 -m unittest -v test_evaluator
python3 generated_control.py --output-dir /tmp/dpad-engineering-control
python3 evaluator.py select --training /tmp/dpad-engineering-control/training.json --output /tmp/dpad-engineering-control/selection.json
python3 evaluator.py evaluate --targets /tmp/dpad-engineering-control/targets.json --predictions /tmp/dpad-engineering-control/predictions.json --plan /tmp/dpad-engineering-control/selection.json --output /tmp/dpad-engineering-control/results.json
```

Controls use four orthogonal generated samples per fold and hand-derived
correlations. They exercise the full 25,200 training-architecture metadata
records and 1,960 held prediction cases, exact signed-rank enumeration, effect
thresholds, selection independence from held truth, incomplete search rejection,
invalid prediction rejection and causal support leakage checks. These are
bounded software tests, not neural simulations, model training, authentic data
evaluation or evidence of baseline competence.

## Gates preserved

The paper identifies the first seven sessions with wideband data between
20160622/01 and 20160921/01. Exact Zenodo record 3854034 contains seven matching
filenames in those date bounds; the hard-coded candidate roster is that explicit
inference, not an independently verified wideband crosswalk. Arbitrarily chosen
subsets of the 47 released sessions are rejected. A source-backed mapping change
would require a distinct reviewed implementation version.

The exact random subset of 32 out of 96 electrodes (77–99 units), original
preprocessing/filter boundaries, full native configuration and historical
runtime are unresolved. The underlying release is about 24 GB; none was
downloaded. The published `refh_results.csv` is excluded from participant inputs.
Native trained models/predictions, complete authentic populations, protected
reference targets, A/B access parity and contamination audits remain unverified.

The Zenodo data are CC-BY-4.0 according to the canonical record. Official DPAD
code has USC educational/research/nonprofit permission; commercial permission
is separate. Current pinned source is not established as publication-era source.
No native code is redistributed or executed by this component.

Whole-session prospective assessment, matched capacity, noninferiority margin,
and permitted time/kinematic controls require a separate frozen prospective
protocol. Temporal-fold results here are not reported as held-session improvement.
Every result retains `scientific_qualification: "unknown"` and the unresolved
gates; registration counts and generated tests are not scientific qualification.
