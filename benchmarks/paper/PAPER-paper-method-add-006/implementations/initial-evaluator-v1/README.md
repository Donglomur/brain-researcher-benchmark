# Rat GLM and population geometry evaluator

Implements the Gaussian-basis Poisson GLM, predicted-rate participation ratio,
covariance geometry, and an eight-animal/eight-session CA1/PFC panel driver for
`PAPER-paper-method-add-006`. A separate train-only fitting helper is a
prospective within-session recipe.

Requires Python 3.11+, NumPy, SciPy and scikit-learn. Tested with NumPy 2.4.6,
SciPy 1.17.1 and scikit-learn 1.9.1; nothing is installed or downloaded by this
package. From this directory, using a Python environment with those packages:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 evaluator.py --help
python3 evaluator.py geometry prepared-arrays.npz geometry.json --training-samples 300
```

The geometry input contains aligned `responses` and `latents` matrices. Other
modes accept explicit processed-session arrays or a content-pinned full-panel
manifest; [the detailed interface and provenance](../../docs/initial-evaluator-v1.md)
defines them. `source-contract.json` retains exact code revision, all nine source
asset identities, paper/code discrepancies and rights status.

Generated tests check engineering behavior only. Native NWB ingestion, empirical
references, paper targets, animal/session improvement assessment, source rights
and scientific qualification remain held. The panel does not rerun the original
108-basis search, and the published raw CA1 neuron count differs from the pinned
script. Outputs explicitly retain incomplete-contract and unqualified status.
