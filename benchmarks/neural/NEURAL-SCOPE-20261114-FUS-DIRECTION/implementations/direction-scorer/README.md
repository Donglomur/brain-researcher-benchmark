# Complete fUS direction scorer

This component implements the missing scorer for registered
`NEURAL-SCOPE-20261114-FUS-DIRECTION`. It evaluates an independently prepared
private intake and committed eight-class predictions. It preserves the existing
V3 scientific endpoint and adds no task, actual result, protected cohort or
readiness claim.

The fixed public metadata roster has 49 session/run records from two macaques,
including one declared zero-trial record. The 20,622 declared source trials and
20,238 potential queries are metadata arithmetic, not authenticated observations.
The full original archive, trial identities, acquisition clocks and eligibility
have not been inspected in this source phase. `SCHEMA.md` defines an operator
projection; it does not assert that these keys exist in the released MAT files.

The scorer admits all 49 records, reconciles the declared counts, checks complete
source order and global trial lineage, validates eligible timing intervals, and
selects the earliest eligible example of each direction as calibration. Every
other eligible case is a query, including cases earlier than some calibration
examples. A missing direction after calibration makes the scientific estimand
undefined and prevents scoring. The zero row remains in the census with no
invented trials. A contradiction with metadata requires a reviewed versioned
intake amendment, never an automatic subset.

Primary balanced accuracy is the eight-class mean recall within each session,
then the equal-session mean within each animal, then the equal mean of the two
animals. Forty-eight positive records are not 48 independent animals.
Secondary outputs include accuracy, wrapped angular error, Brier score,
confusion matrices, invalid counts, confidence-bin sufficient statistics,
record-level elapsed days, and descriptive system/native-Hz strata with their
actual animal support. `paired_delta` reports complete matched-support
candidate-minus-reference differences; matching information and provenance
remain the caller's responsibility. No confidence interval or significance
threshold is fabricated. A future session-cluster bootstrap would describe
these two animals conditionally, not establish animal-population uncertainty.
Saved paired outputs retain both evidence-condition labels and the exact intake
identity, so an augmented comparison cannot silently lose its label. V2 adds
these fields following independent review; the scorer mathematics and V1
generated-control evidence remain unchanged and preserved.

Every missing or malformed known prediction remains in its frozen denominator:
incorrect classification, 180-degree angular error and Brier 2. Duplicate known
IDs invalidate that query. Extra/unassignable rows, including calibration IDs,
invalidate the entire submitted collection and give **all frozen queries** the
same worst-case penalties. They never add trials or reduce the denominator.
Malformed JSON receives the same complete penalty. This is the explicit fixed
resolution of the V3 contract's extra-output ambiguity. It is distinct from a
construction-invalid cohort, which produces no score.

Argmax ties select the smallest angle. Each accepted probability vector has
eight finite values in [0,1], sum within 1e-6 of one, and is divided by that sum
before Brier/reliability computation. This fixed numerical convention keeps the
loss in [0,2]. Ten confidence bins use [0,.1), ... [.9,1]; exact 1 belongs to the
last bin. Invalid predictions remain explicitly counted outside those bins;
the bins alone are a valid-prediction summary, not a complete calibration claim.

Run the generated controls with the component directory as the sole added
source path:

```python
import sys, unittest
sys.path.insert(0, "/absolute/path/to/component")
suite = unittest.defaultTestLoader.loadTestsFromName("test_scorer")
assert unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()
```

A future admitted private grader can run `python -I -S -B evaluate.py` with
`--intake`, `--intake-sha256`, `--predictions`, `--predictions-sha256` and
`--condition`. It captures the committed prediction bytes before the private
intake. Operands must be ordinary, single-link files with stable identity and
the selected hash; the JSON parser rejects duplicate keys and nonfinite tokens.
Source/schema errors and file/custody errors fail the operation. The scorer's
64 MiB intake and 16 MiB prediction byte caps are format bounds, not measured
scientific runtime or memory allocations. Decode/tree/output overhead must be
included in a separately admitted whole operation.

This source package contains software, public factual roster metadata and
explicitly generated controls. It contains no actual trial mapping, target,
signal, private reference identity, raw HTTP capture or communications.
References and unresolved qualification work are in `PROVENANCE.md`.
