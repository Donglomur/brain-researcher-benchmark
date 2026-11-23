# Build a finite sleep submission from CSV

This command packages completed predictions for the existing **5,450-epoch,
two-person development panel**. It makes the original submission format usable
without writing NumPy archive code. Python 3.11 or later and NumPy are required.
It opens only the supplied probability table and public validator source. It does
not open EEG, labels, score masks or reference predictions, execute a predictor,
grade answers, or establish who produced them.

Write a UTF-8 CSV with the exact header and one row for **every** epoch:

```csv
epoch_id,W,N1,N2,N3,R
development-001/00000,0.1,0.2,0.4,0.2,0.1
development-001/00001,0.1,0.2,0.4,0.2,0.1
```

The two rows above illustrate the format; they are not a complete submission.
Rows must contain `development-001/00000` through `development-001/02779`, then
`development-002/00000` through `development-002/02669`, in that order. Keep
unknown/movement epochs in the table; the existing protected grader applies its
private mask later. Missing, repeated, swapped, extra and out-of-order rows fail.
Headers in another stage order fail rather than being silently rearranged.

```sh
python -I -B benchmarks/neural/NEURAL-007/implementations/submission-builder-v1/compose.py \
  --csv /operator/completed-probabilities.csv \
  --output /operator/new-submission.npz
```

The parent directory must already exist. Existing outputs are refused. The tool
checks finite probabilities in `[0,1]` and the original absolute row-sum tolerance
of `1e-6`. It converts CSV numeric strings to float64 without rounding to float32,
clipping, filling, sorting, or normalization. This standard decimal-to-binary
conversion is explicit; retain the input CSV for provenance.

Output uses the unchanged class order, canonical epoch IDs, and uncompressed
`numpy.savez` layout, within the original 4,000,000-byte limit. Before reporting
success, the exact original public validator checks the newly written archive.
The JSON report on stdout gives input and output hashes. Output is read-only;
keep the original CSV and report alongside it in operator custody. An I/O or
post-write validation failure returns exit 2 and may leave the newly created
file, which must not be treated as accepted without successful validation.
No existing file is replaced. `--adapter-source` supports relocation of the
original byte-authenticated validator; it cannot select different validation rules.

Use the [portable grader](../portable-grading/README.md) for separately provisioned
validation and protected scoring. This builder does not replace programme
commitment, execution, viewer history, isolation or exposure records. Its output
does not qualify a direct/viewer attempt, an unseen population, or the separate
78-person/153-night programme. The primary equal-person fixed-five-class macro-F1
and all target masks remain in the existing grader.

Generated controls exercise a complete table through the original validator,
exact float64 probability preservation, missing/repeated/swapped rows, class
order, nonfinite/range/sum errors, source substitution and existing-output refusal:

```sh
python -I -B benchmarks/neural/NEURAL-007/implementations/submission-builder-v1/test_compose.py
```
