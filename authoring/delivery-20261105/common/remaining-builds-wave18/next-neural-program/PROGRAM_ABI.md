# Frozen-program interface

Submit one UTF-8 Python file, at most 1 MiB. Freeze its exact bytes and all
settings before any of the 2,592 candidate/reference conditions. The reference
is a separate immutable source file and cannot receive candidate artifacts.

Each condition has two fresh offline invocations:

```
python -I -B /submission/program.py fit --input /input --out /output/model.bin
python -I -B /submission/program.py infer --input /input --model /model/model.bin --out /output/predictions.json
```

The fit view contains only `case.json` and `training.npy`. Metadata includes
generation, opaque case, setting, arm, array shape/pin, and original opaque
training rows with label, person, donor/calibration role and training-only fold.
It contains no query IDs or data. Preserve whole donor people in internal
tuning. The source's first chronological20/100 calibration selection is fixed;
there is no replacement or class balancing.

The inference view contains only `case.json` and `query.npy`. Metadata includes
the same condition identity, all100 ordered opaque query IDs, array shape/pin
and sealed model/program pins. The model is readonly and at most512MiB. It may
contain any permitted training-derived state, including labeled examples.
There is no separately mounted training packet and no query truth. Query-batch
adaptation is forbidden and requires independent method/exposure admission;
the batch interface cannot universally enforce that rule for arbitrary code.

EEG/PERMUTED_EEG arrays are little-endian float32, C order, with251samples and
20channels per trial. CONTEXT arrays have only the original five covariates.
The full training counts are10620/10600/10700/10620 for target20/transfer0/
target100/other_session20. The input representation does not reveal donor
session membership. The new fit/infer ABI is not binary-compatible with the
original single-call packet, but preserves its permitted numerical values,
labels and scientific endpoint.

Return the exact original `neural083_case_prediction_v1` object with condition
identity and100 ordered finite `p_right` values. A bounded explicit abstention
is permitted. Every result is captured only after producer closure; any missing
condition or abstention leaves the complete comparison unscored. Outputs are
at most100000bytes. No candidate model/cache is shared with another condition.

CPU, RAM, image, phase duration, cumulative I/O, retained allocation, other
reservations and original whole-run deadline are explicit future selections.
The source contains no model/scientific execution authorization. A completion
marker alone is insufficient without the independently observed source-bound
worker/native closures and full output admission.
