# Cardiac candidate delivery, with fitting explicitly blocked

This additive interface delivers the exact complete 655-person processed Salzburg
input in two matched packets and captures complete candidate summaries for the
existing six-model endpoint. It removes the old packet's platform-specific Linux
wheels/bootstrap and supplies current, accurate delivery instructions. The native
Bambi/PyMC/ArviZ fitting environment is unavailable in the checked pilot Python;
no fit, scientific score or accepted reference is produced by this package.

The original question, six separately fitted raw/standardized Student-t models,
all 30 parameter summaries, data/cohort identities, common numerical specification
and optional official-code comparison remain unchanged. It remains explicitly a
source-informed reconstruction condition. [SOURCE_MAP.md](SOURCE_MAP.md) resolves
CSV/author-variable meanings from the pinned notebook. All 655 people are exposed
development reconstruction inputs, with no newly selected subset or holdout.

## Delivery and ingestion

Run with Python 3.11 or later and the standard library. Provision `--assets` with
the exact common scientific assets and five official-code files listed in
[DELIVERY_SPEC.json](DELIVERY_SPEC.json), preserving their relative names. An
already authenticated historical B packet is a suitable source store. The command
only copies the exact allowlist; wheels, original runtime helper files, private
reference files and unrelated assets are never copied. Scientific data/paper/code
bodies are operator-supplied, not included in the source repository.

From the repository root:

```sh
python3 -I -S -B benchmarks/paper/PAPER-ROOT-ADD-016/implementations/candidate-delivery-v1/delivery.py build \
  --assets /operator/exact-historical-B-packet --out /operator/new-pair
python3 -I -S -B benchmarks/paper/PAPER-ROOT-ADD-016/implementations/candidate-delivery-v1/delivery.py verify-pair \
  --pair /operator/new-pair
```

Give A only `/operator/new-pair/A` and B only `/operator/new-pair/B`. Each packet
includes a target-free `REQUEST.json`, explicit file roster, common scientific
contract and scope. B alone gets the five official-code assets. The private parent
receipt binds both requests. All data/asset pins and the original ordered
participant digest are checked before publication of a success receipt. Paths
must be absolute and physical; output must be fresh and outside source/input
roots. Files are created read-only for candidates and private for operator
receipts, but filesystem permissions are not an isolation boundary on a shared
same-user host.

After separately authorized candidate authoring has ended, capture each complete
program and summary. No candidate execution or inference is performed here:

```sh
python3 -I -S -B benchmarks/paper/PAPER-ROOT-ADD-016/implementations/candidate-delivery-v1/delivery.py capture \
  --pair /operator/new-pair --condition A \
  --program /submissions/A/program.py --summary /submissions/A/summary.json \
  --out /operator/captured-A
python3 -I -S -B benchmarks/paper/PAPER-ROOT-ADD-016/implementations/candidate-delivery-v1/delivery.py capture \
  --pair /operator/new-pair --condition B \
  --program /submissions/B/program.py --summary /submissions/B/summary.json \
  --out /operator/captured-B
python3 -I -S -B benchmarks/paper/PAPER-ROOT-ADD-016/implementations/candidate-delivery-v1/delivery.py close-pair \
  --pair /operator/new-pair --a /operator/captured-A --b /operator/captured-B \
  --out /operator/closed-pair
```

Capture executes the exact pinned current `six-model-summary/summary_score.py`
validator on the submitted JSON, without importing the candidate program or opening
a reference. It requires all six models, all 30 parameter summaries and the exact
input identity. Different valid seeds/samplers and unavailable diagnostics remain
permitted by the existing contract. Closure rechecks both complete packets,
condition/request identities and captured bytes, then snapshots the two native
summary files together. Missing/mixed pairs, packet extras, changed source,
changed capture contents and malformed summaries refuse. Failure never creates a
success receipt; partial owned output must remain a failed attempt, not be reused.

A byte snapshot is not evidence of inference, producer termination, unmodified
prior authoring or independent context. Receipts keep those claims false. This
interface assumes trusted non-mutating operator directories; same-user receipt
forgery and cross-file races are outside its boundary. It is not a sandbox.

## Concrete fitting and reference blockers

Probe the **selected candidate interpreter**, with normal installed-site discovery
(no `-S`), before scheduling a paired attempt:

```sh
python3 -I -B benchmarks/paper/PAPER-ROOT-ADD-016/implementations/candidate-delivery-v1/delivery.py runtime-probe \
  --out /operator/fresh-runtime-probe.json
```

The command discovers module specifications without importing numerical libraries,
installing anything or fitting a model. The checked existing pilot Python 3.11.6
has NumPy, pandas and SciPy but lacks Bambi, PyMC and ArviZ. The default isolated
Python 3.11.5 lacks all six. This is an observed native fitting dependency blocker,
not proof that every possible independently implemented sampler is impossible.
Even a positive discovery result is not runtime qualification: actual imports,
source-model density agreement, all six independent fits, convergence, measured
feasibility and the same declared resources for both arms are still required.
The historical 120-second/3-GiB profile is neither copied nor silently qualified.

No reference path or reference-binding option exists. The historical private
posterior summary is not accepted as a competent oracle by this package. Before
any downstream numerical grading, independent review must establish the complete
fit population, source/native parity, convergence, Monte Carlo agreement and
custody. Existing [full-cohort reference preparation](../full-cohort-admission-v1/README.md)
and the [unchanged continuous scorer](../six-model-summary/README.md) remain
separate components. No scientific pass threshold or qualification is added.

## Evidence and checks

[BUILD_RECORD.json](BUILD_RECORD.json) records authentic delivery coverage and
runtime discovery without empirical rows, posterior values, private paths or
candidate predictions. Production build and revalidation used the exact admitted
655-row CSV, exact paper/caption extracts and exact official-source capture. Both
packets were built; **no candidate fit or authentic submission was run**.

```sh
python3 -I -S -B benchmarks/paper/PAPER-ROOT-ADD-016/implementations/candidate-delivery-v1/test_delivery.py -v
```

The 17 generated software controls exercise complete structural closure and
missing-person, identity, incomplete-summary, duplicate-key, pair-mixing, tamper,
extra-file, symlink, overwrite, source-pin and authority failures. The production
CLI rejects those generated assets. Generated closures are not reference runs,
scientific results or evidence of benchmark difficulty.
