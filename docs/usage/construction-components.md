# Use the new construction components

These four components add preparation, estimation or evaluation interfaces to
existing tasks. They are not four additional benchmarks or completed scientific
results. The source tests below use generated fixtures and Python's standard
library; they do not download data, run models or qualify the original inputs.

Start each shell block at the repository root. Operational examples require the
external inputs described below; their paths and variables are placeholders.
Package READMEs define the full schemas and scientific limits.

## Helsinki: prepare causal EEG packets and score complete predictions

The [complete-support evaluator](../../benchmarks/neural/NEURAL-EXP-005/implementations/complete-support-evaluator/README.md)
implements the infant-macro soft-vote Brier endpoint across all 79 recordings,
using all three expert streams and every primary timestamp. It retains quality
flags rather than removing flagged cases.

Run its generated source tests:

```sh
python3 -B -m unittest discover -s benchmarks/neural/NEURAL-EXP-005/implementations/complete-support-evaluator -p 'test_*.py' -v
```

This component has a Python API, not a campaign CLI. In trusted preparation code
with the implementation directory on the import path, use its documented API:

```python
from protocol import prepare_reference, packet

# descriptor and read_samples come from the trusted normalization pipeline.
# case_key is an evaluator-held bytes value with at least 32 bytes.
reference = prepare_reference(descriptor, read_samples, case_key)

# recording_id and k are trusted-side selectors, not participant metadata.
public_packet = packet(reference, recording_id, k, read_samples)
```

The assessor then calls `evaluate(reference, rows)` from `evaluate.py` with the
complete ordered prediction stream; `compare(left, right)` compares reports from
the same frozen reference. Missing or invalid predictions withhold the full score.

You must supply the complete normalized description, corrected expert annotations,
native clocks and calibration, the fixed 18-channel montage, frozen folds and
development membership, and a trusted sample-reading callback. The source does
not read EDF files or verify those scientific mappings. Keep the reference, key,
full binding stream and score reports private; participants receive only their
current causal packet. Per-case process isolation and a competent fitted seizure
comparator remain external requirements.

## Vestibular: evaluate complete held-repeat predictions

The [condition evaluator](../../benchmarks/neural/NEURAL-DISC-20261114-VESTIBULAR-VO/implementations/condition-evaluator/README.md)
scores a complete prediction artifact against a frozen normalized reference and
an independently selected, training-only motion/phase prior. Its primary result
is an animal-by-condition vector: equal-repeat means within groups, then
equal-group means within each cell. It does not collapse animals into a headline
average.

Run its generated source tests with Python 3.11 or later:

```sh
PKG=benchmarks/neural/NEURAL-DISC-20261114-VESTIBULAR-VO/implementations/condition-evaluator
python3 -I -S -B "$PKG/test_evaluate.py" -v
```

After preparing the external inputs, use the documented command:

```sh
PKG=benchmarks/neural/NEURAL-DISC-20261114-VESTIBULAR-VO/implementations/condition-evaluator
python3 -I -S -B "$PKG/evaluate.py" \
  --reference /assessor/reference.json \
  --reference-sha256 "$REFERENCE_SHA256" \
  --submission /submissions/fixed-predictions.json \
  --max-reference-bytes "$REFERENCE_BYTE_LIMIT" \
  --max-submission-bytes "$SUBMISSION_BYTE_LIMIT"
```

Supply the reference hash from an independent trusted assessor record and choose
explicit byte limits for the complete inputs. The [schema](../../benchmarks/neural/NEURAL-DISC-20261114-VESTIBULAR-VO/implementations/condition-evaluator/SCHEMA.md)
defines required identities, clocks, masks, targets, prior and unavailable cells.
Participants supply predictions and public alignment fields, never the reference
targets or their own scoring mask. The normalized reference and diagnostic output
stay assessor-private. No MATLAB loader, fitted decoder or prior-selection
procedure is provided.

Add `--investigation /submissions/investigation-predictions.json` to compare
`fixed_program` with `case_investigation` on exactly the same support. The result
reports fixed-minus-investigation MSE per primary cell; artifact mode labels do
not establish matched tools, access or execution. Successful validation establishes
structural and arithmetic consistency, not biological qualification.

## Laser EEG: prepare identical evidence for three access conditions

The [condition-packet builder](../../benchmarks/neural/NEURAL-SCOPE-20261114-LASER-EEG-REPORT/implementations/condition-packets/README.md)
prepares nine experiment folds from the complete 678-record nominal roster. Each
fold has eight training examples; each query includes two labeled calibration
trials. Direct answer, frozen program and investigation receive the same query
bytes. Its private targets are compatible with the sibling full-assay scorer.

Run its generated source tests, keeping that sibling scorer in place:

```sh
python3.11 -I -S -B benchmarks/neural/NEURAL-SCOPE-20261114-LASER-EEG-REPORT/implementations/condition-packets/test_packets.py
```

There is no operational CLI. Load `packets.py` as an owner-only module with
`importlib.util.spec_from_file_location`, then use its `PreparedAssay` class with
the reviewed inputs and callbacks below:

```python
assay = PreparedAssay(
    reviewed_ledger, reviewed_protocol, reviewed_representation,
    epoch_loader,  # private callback: one (experiment, person_key, trial_key) tuple -> bytes
    protocol_sha256=reviewed_protocol_pin,
    representation_sha256=reviewed_representation_pin,
    support_salt=frozen_32_byte_support_salt,
    opaque_key=separate_private_32_byte_key,
)

receipt = assay.prepare_all(
    owner_authoring_staging_sink,  # (opaque_fold_id, packet_bytes)
    owner_query_staging_sink,      # (opaque_query_id, packet_bytes)
    actual_tokenizer_and_framing_counter,
    tokenizer_sha256=reviewed_tokenizer_pin,
)
targets = assay.private_targets()          # evaluator-private
selection = assay.private_selection_audit()  # owner-private, includes source IDs

authoring = assay.authoring_packet(heldout_experiment)  # exactly eight examples
mode_packets = assay.packets_for_modes(one_query_id)   # same bytes for A/B/C
```

Supply the complete normalized ledger, reviewed protocol/representation, exact
epoch bytes, two separate private 32-byte values, and the actual tokenizer plus
full framing counter. Original file loading, preprocessing, units, time alignment
and biological identity/alias reconciliation remain external work. The owner
object, loader, ledger, targets, audit and all-query staging stay private; only the
permitted fold/current-query bytes reach participants. A successful `prepare_all`
is required for complete packet coverage; obtaining targets alone is insufficient.
The builder does not enforce candidate isolation or cumulative execution budgets.

## iSTTC: produce all four per-unit empirical estimates

The [empirical-estimation producer](../../benchmarks/paper/PAPER-paper-method-add-004/implementations/empirical-estimation/README.md)
attempts all 23,100 unit-by-method fits for 5,775 units across 26 mice, retaining
failed fits. It supplies estimates to the existing empirical diagnostics; it does
not implement the Figure 7C GLMs, other paper panels or an improvement study.

Run its generated source tests without scientific dependencies:

```sh
(
  cd benchmarks/paper/PAPER-paper-method-add-004/implementations/empirical-estimation || exit
  python3.11 -I -S -B -m unittest discover -s . -p test_producer.py
)
```

For an authentic operation, supply the frozen cohort, one normalized 30 kHz
30-minute spike recording per unit, and every prospective window row from the
[existing bridge](../../benchmarks/paper/PAPER-paper-method-add-004/implementations/empirical-diagnostics/README.md).
The complete streams must preserve cohort order and IDs. Resolve authentic
cohort/QC membership, including the paper's amplitude-cutoff discrepancy, before
claiming reproduction.

The command also requires an external official iSTTC checkout at
`e78cfd2b2ea79b7a7e707db7b79e218212497e43`; three helper files are hash-verified.
NumPy, SciPy, scikit-learn and statsmodels must already be installed in the chosen
Python environment. No checkout, dataset or dependency installation is performed:

```sh
(
  cd benchmarks/paper/PAPER-paper-method-add-004/implementations/empirical-estimation || exit
  python3.11 -I -B producer.py \
    --cohort /ABSOLUTE/COHORT.json \
    --recordings-jsonl /ABSOLUTE/RECORDINGS.jsonl \
    --windows-jsonl /ABSOLUTE/WINDOWS.jsonl \
    --author-checkout /ABSOLUTE/PINNED_ISTTC_CHECKOUT \
    --output-directory /ABSOLUTE/FRESH_OUTPUT
)
```

The output directory must be absent. Require successful exit and complete,
hash-consistent `estimates.json` and `receipt.json`; one file's existence is not
completion. Full-recording fits are method-specific pseudo references rather
than biological ground truth. A future trial-only improvement experiment must
protect them from the estimator through a separate access contract. Authentic
execution, historical numerical parity and a paper reproduction pass remain
unestablished by the source tests.
