# Historical matched EEG/EOG reference program

This package restores the exact fixed random-forest program used by the original
NEURAL-008 paired development control. The program is byte-identical to the
historical source pinned by `eog-program-completion-v1/ASSETS.json`:
`e6558cae4b20adcccd25ffaaae6021b98422457f8dda7b7fca82b407bb9cf25f`.
It is a benchmark reference recipe, not a claim that these settings were the
Sleep-EDF authors' method or the MNE tutorial's reported result.

The existing [paired program runner](../paired-program-v1/README.md) supplies
the original physical feature views and separate fresh execution realms.
Its public source previously included the runner and scorer but omitted this
specific reference program. Restoring it makes that recipe reviewable and
usable after separate execution qualification. It does not authorize a run or
inherit the historical container's qualification.

## Preserved scientific procedure

The same program performs one fixed fit in each arm: 100 trees, minimum leaf
size 5, all available features per split, balanced class weights, bootstrap
sampling and random seed 241. The original two-worker estimator setting is
unchanged. All remaining constructor arguments are explicit in `PARAMETERS`.
Neither arm tunes parameters or reads development labels.

Each arm pools all six training people: 16,290 chronological epochs, of which
16,211 are scored and 79 are masked. The EEG arm uses the original 15 columns;
the EEG/EOG arm uses the original 21. Both then predict every epoch of
development-001 (2,780) and development-002 (2,670). The program validates
input identities, complete person order, feature geometry and the training
mask. It maps the estimator's available classes into the fixed `W,N1,N2,N3,R`
output columns without normalization or missing-class substitution.

The two development people were exposed historically. This is a descriptive
paired information comparison on engineered features, not native waveform
understanding, a new held-out cohort, a causal EOG effect or population
inference. Positive, zero and negative EOG-minus-EEG differences remain valid.
Both arms' absolute performance must accompany the contrast. The reference
does not create a positive-difference requirement or an accuracy admission
floor.

## Operator use

After independently qualifying the existing paired runner, use this
`fixed_rf.py` as its `--program`, `method.json` as `--method`, and `claims.json`
as `--claims`. The program uses fixed `/input` and `/output` paths inside the
container; arguments passed by the runner do not change those paths.
The operator must retain the original input pins, approved immutable image,
source/method commitment, both stopped-producer captures and the existing
target-last paired scoring procedure.

The RF source imports scikit-learn only when `main()` is called. An environment
must support the full preserved constructor signature, including
`monotonic_cst`; do not remove arguments to make an older environment run.
Current numerical library versions, resource usage and score parity have not
been qualified here. A fixed seed does not establish probability-array bit
identity across versions or execution platforms. Historical checker failures
and subsequent score-based qualification remain historical evidence; this
package does not replay or erase them.

## Construction checks

Run the focused generated tests from the repository root:

```sh
python -I -B benchmarks/neural/NEURAL-008/implementations/historical-fixed-rf-v1/tests/test_fixed_rf.py
```

Eight controls exercise masked training rows, wrong-mask refusal, fixed
five-class mapping, invalid classes and probabilities, chronological identity,
extra archive members, and both complete original arm rosters through the
actual `main()` orchestration. The last control uses generated in-memory files
and a non-fitting estimator double. It verifies one fit request per arm,
16,211 training rows with no development rows, and all 5,450 output identities.
It does not run a random forest, access authentic neural arrays, execute Docker,
measure model performance, or qualify execution isolation. No canonical task
status or access condition changes with this source recovery.
