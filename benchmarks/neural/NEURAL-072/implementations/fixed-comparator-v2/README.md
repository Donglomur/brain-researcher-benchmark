# Fixed comparator scoring for NEURAL-072

This additive implementation closes the supplied-comparator substitution defect identified as N072-R01. Participants submit contextual predictions only. The operator fits and freezes nuisance/lexical predictions before receiving candidate submissions, retains their exact SHA-256 outside participant control, and supplies that expected digest when scoring. Tampering with predictions, fit ledger, feature identity, cases, protocol or source is rejected. The original `initial-evaluator-v1` source and all canonical/history files remain unchanged.

The scoring API authenticates bytes against a caller-owned trust root. It does not establish who called it: the operator must own the expected digest and freeze inputs. A digest copied from a participant's artifact does **not** establish ownership. This package does not provide an OS sandbox, participant transport, candidate method/capacity certification, or proof of temporal ordering. An untrusted process sharing the operator account must not be given the protected scorer or freeze configuration.

## Operator use

Use an existing Python environment with NumPy. Files containing responses and predictions belong outside Git. First freeze the reference, with the same reviewed matrices/cases/protocol accepted by the predecessor:

```sh
python evaluator.py freeze-reference --protocol protocol.json --cases cases.json --features evaluator_features.json --targets train_dev_targets.json --output fixed_reference.json
```

The command prints `artifact_sha256`. Record that digest in protected operator configuration **before** accepting submissions. The output is created exclusively and cannot overwrite an existing artifact. The reference contains exact comparator predictions, source hashes, semantic feature/training-input hashes, selected hyperparameters and the complete fit ledger. It contains no held-out responses. The feature and fit lineage hashes authenticate the freeze record, not the scientific authenticity of input data.

The candidate response has exactly these keys (the `contextual` object contains every frozen test run and its complete rows × targets matrix):

```json
{
  "schema": "neural072-contextual-predictions/v2",
  "task_id": "NEURAL-072",
  "protocol_sha256": "SEMANTIC_PROTOCOL_SHA256",
  "cases_sha256": "SEMANTIC_CASES_SHA256",
  "contextual": {"TEST_RUN_ID": [[0.1, 0.2], [0.3, 0.4]]}
}
```

The illustrative two-row matrix is not an admissible case. Real dimensions follow the unchanged frozen cases. No comparator, ledger, reference path or expected-digest field is accepted from the participant. After freezing the candidate submission, score with the previously retained operator digest:

```sh
python evaluator.py score --protocol protocol.json --cases cases.json --candidate candidate.json --reference fixed_reference.json --expected-reference-sha256 OPERATOR_RETAINED_SHA256 --targets protected_test_targets.json --output report.json
```

The CLI authenticates reference bytes and validates candidate support before opening the target file. It reads input bytes once for consistent parsing and file hashes. The scorer API has the same authentication boundary, although callers naturally control when they load its target argument. Neither interface launches candidate code or gives it feedback.

## Preserved estimand and explicit limits

The implementation executes only the pinned predecessor source (`66acc703b7f169d87d0d6e334e30588e03af4e41409ecc48e975d213051e375f`) for fitting, validation and numerical scoring. Nuisance/lexical references use that exact prospective whitened-ridge recipe. Its shared alpha is selected using **operator-owned, fixed** lexical and contextual feature blocks; candidate features never enter comparator selection. This does not introduce a different baseline or change the prior equal-rank mathematical recipe. It is not an author encoding model and its competence remains unqualified.

The signed contextual-minus-fixed-lexical R² uses unchanged within-run-centered SST, run pooling within listener/family cells, equal target averages, equal family averages within listener and equal listener averages. Negative effects remain valid. All previous descriptive crossed-bootstrap and circular-shift limitations remain. Added diagnostics report per-cell target SSE/SST, run row counts and listener-macro absolute R² for every arm. Authentication binds the fit ledger and predictions; a participant cannot improve its effect merely by replacing its lexical comparator.

This is a tested software component, not a qualified benchmark or direct neural-understanding result. Authentic Narratives inputs, exact NEURAL-071 case equivalence, scanner/transcript/HRF alignment, atlas/checkpoint lineage, source rights, competent references and protected execution remain open. The predecessor uses alternative equal-rank lexical/contextual blocks plus nuisance; it does not itself enforce the canonical description of a contextual arm containing the complete lexical block. Candidate capacity/feature admissibility and that nested-versus-matched-rank discrepancy require scientific reconciliation before ranking. The canonical contract's full task remains unqualified and no capability labels are changed here.

Generated controls reproduce the predecessor comparator-degradation exploit, reject candidate comparator injection and changed committed artifacts, check unchanged fitting/results, prohibit hidden-target fitting, verify complete support and signed/absolute metrics, and exercise CLI freeze/score plus rejection before target access. They use generated matrices only, with no data downloads, authentic-data processing, model calls or native trials.
