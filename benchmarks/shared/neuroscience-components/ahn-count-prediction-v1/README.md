# AHN count-prediction components

These standard-library Python components support development of a benchmark
based on Experiment 17 from
[An amygdala to anterior hypothalamic circuit gates stress sensitivity](https://www.nature.com/articles/s41586-026-11075-5).
They provide an evaluator-side negative-binomial scorer, a local release-file
verifier, and invented-data tests. They do not form a ready research benchmark.

The complete declared scope is 28 mice: 8 controls (Ctrl), 10 stress-naive
animals tested with the auditory stressor (NS), and 10 previously stressed
animals (S). Every prediction must cover all 452 regions for every mouse:
12,656 animal-region pairs. The main figure's omission of controls does not
remove those animals from the regional count experiment.

## Scoring

Run this command from the component directory, with Python 3.11 or a compatible
Python 3 installation:

~~~sh
python3 -I -S -B predictive_score.py \
  --roster /evaluator/roster.json \
  --truth /evaluator/truth.json \
  --predictions /submissions/predictions.json \
  --output score.json
~~~

The output path must not exist. Truth and the audited roster belong to the
evaluator. This command reads existing files; it does not train a model or create
a protected execution environment.

All input objects use strict JSON with no duplicate keys or NaN/Infinity
constants. Their exact top-level fields are:

| File | Schema value | Other fields |
| --- | --- | --- |
| roster | ahn-evaluator-roster-v1 | animals, regions, binding |
| truth | ahn-count-truth-v1 | rows |
| predictions | ahn-nb-predictions-v1 | rows |

The roster has 28 animal records with exactly id and group fields, and 452
unique region identifiers including AHN. Group counts must be 8/10/10.
Identifiers are nonempty strings of at most 128 characters, without characters below U+0020. The binding object has exactly input_manifest_sha256 and
cohort_review_sha256, each a lowercase 64-character digest established by the
evaluator's complete input and cohort review. A correctly shaped digest alone
does not prove that review happened.

Truth rows have exactly animal, region and count. Prediction rows have exactly
animal, region, mean and size. Both files require every unique roster pair
exactly once; missing, duplicate or unknown pairs fail. Count must be a
non-boolean integer from 0 through 1,000,000. Mean and size must be finite,
strictly positive, non-boolean numbers.

The predictive distribution is NB2 with mean mu and size r, whose variance is
mu + mu²/r. The score is the average log probability over 452 regions for each
animal, then the average over all 28 animals. Higher is better. All animal scores
and 8/10/10 group summaries are retained. This is a mean of marginal predictive
scores, not a joint brain-network likelihood.

The implementation uses a per-count log recurrence and rejects nonfinite or
positive log probabilities; it never clips them into a passing value. Its cost
is proportional to the sum of observed counts. The count domain is a software
limit, not permission to exclude a difficult animal or region. If original data
fall outside the supported domain, the complete task needs further engineering
and validation. Extreme floating-point parameter combinations may refuse rather
than produce a score. Independent numerical parity against a pinned trusted
implementation over the admitted biological domain remains required.

Scores carry digests for the input release, cohort review, roster and canonical
truth. The library function paired_difference checks identical bindings,
animal identities, group sizes and region denominators before giving a
descriptive paired comparison. These hashes prevent accidental comparisons
across revisions; they do not authenticate how a participant trained a model.
Training sets overlap across leave-one-animal-out folds, so treating fold scores
as independent experiments is not justified by this component.

The roster input is capped at 256 KiB; each truth/prediction file at 8 MiB;
the output at 64 KiB. These are format limits, not memory or runtime containment.

## Local release verification

The verifier checks the six complete derivative files identified in the
[official pinned release](https://github.com/ZachPenn/2026_Nature/tree/256d17237e6d2786eac1a947c4828cb654c315d7).
Together their declared source sizes are 2,945,407 bytes. Preserve their release
directory structure beneath your authorized local data root.

~~~sh
python3 -I -S -B verify_release.py \
  --root /absolute/authorized-data-root \
  --output integrity.json
~~~

Use a physically resolved path with ordinary, single-link files; symlinks in
the file path and hard-linked files are rejected. The output must not exist.
Each file's exact byte count and Git blob identity are checked, and a SHA256 is
computed in a complete streaming pass. File identities are checked around the
read. No network access, archive extraction or scientific parsing occurs.

An integrity success is not a verified animal/region join, a reconstruction of
historical preprocessing, a data license, or a permission grant. The expected
file paths, sizes and Git hashes are public release metadata. No data bodies
are included here.

## Invented controls

~~~sh
python3 -I -S -B -m unittest discover -s . -p 'test_components.py' -v
~~~

The tests construct an explicitly invented 28-by-452 fixture and temporary
files. They cover complete population/denominator checks, row/identifier
failures, analytic probability identities, numerical extremes, comparison
bindings, and byte/Git-blob/symlink/hardlink verification.

The three Python files are byte-identical to the accepted source component.
Existing evidence for 19 unique controls is reused for this export: 16 scorer
controls and 3 unchanged release-verifier controls. No unchanged test was rerun
solely to create the export, and no original-data result is inferred from these
controls.

## Research and access limits

Paper-result reproduction and predictive improvement are separate activities.
A reproduction workspace exposes the complete released counts; it cannot also
serve as an untouched prediction holdout. Predictive evaluation requires a
committed prediction program and fresh fold-isolated workers, with only the
training animals available. Do not mount the complete data repository in a
prediction worker. The code-access condition needs a source-only snapshot,
identical data/tool budgets, and no embedded result tables or datasets.

The released source and paper have unresolved differences: the count script's
third behavioral fit is intercept-only where the paper describes counts plus
group; the behavior script omits statistical options stated by the paper and
references a dropped export column; some model convergence and missing-value
handling need adjudication. Complete references, numeric tolerances, competent
training-fold baselines, protected execution and calibration/inference remain
unfinished. This scorer is the prospective predictive component; it is not the
paper's reproduction scorer and makes no frontier-performance claim.

The 452-region universe was selected using the original cohort, and the data
are public. Retrospective cross-validation therefore does not establish
pristine prospective generalization or rule out model-training contamination.

The official repository restricts data republication without author consent.
Its GPL-3.0 software license and the article's CC-BY license do not resolve that
data restriction. No research data, authentic labels/counts, fitted models,
reference outputs, private paths or execution authorization are included.
Public-data packaging and submission readiness remain unresolved.

See PROVENANCE.json for exact public source identifiers and component hashes.
