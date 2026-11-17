# ABR threshold scorer: one case per animal and stimulus

This version fixes a scoring-unit error in the preserved initial evaluator. The
registered endpoint is one threshold for each assembled animal×stimulus series.
Different case IDs for repeated ears, sessions or runs of the same series must
not become additional equally weighted cases within an animal.

For example, suppose an animal has tone/click errors of 0 and 20 dB. Its mean
error is 10 dB. The initial evaluator accepts a third case ID for a repeated tone
with error 0, reducing the animal's mean to 20/3 dB. With a second animal whose
error is zero, the overall score falls from 5 to 10/3 dB without improving either
scientific series. The v2 evaluator rejects that reference before scoring.

`validate_reference` requires unique `(animal_id, stimulus)` pairs as well as the
existing unique case IDs. Tone frequencies compare numerically, and click remains
an explicit stimulus category. It does not pick a preferred repeat, merge target
annotations, infer identities, or require a guessed 104×9 Cartesian census. A
source-justified assembly policy must resolve repeated observations upstream.

The arithmetic, failure ledger, censoring rules and bootstrap are reused from
the preserved [initial evaluator](../initial-evaluator-v1/abr_evaluator.py), whose
SHA-256 is `54235e6913ff00f021592ecc73fced31eea1177d33fd48b7bda588181bcceb80`.
Both directories are required. Valid, unique-series references return identical
numerical results, plus `implementation_version` and `case_unit` report fields.
Duplicate series are malformed references (CLI exit 2), not candidate errors.
The historical contract pin remains unchanged.

```sh
python3 benchmarks/neural/NEURAL-SCOPE-20261114-ABR-TRANSFER/implementations/series-evaluator-v2/abr_evaluator.py \
  --reference generated-reference.json --predictions generated-predictions.json \
  --baseline generated-baseline.json --bootstrap-replicates 2000 --seed 0
python3 -m unittest discover \
  -s benchmarks/neural/NEURAL-SCOPE-20261114-ABR-TRANSFER/implementations/series-evaluator-v2/tests -v
```

The input format and other exit codes follow the
[initial evaluator guide](../../docs/initial-evaluator-v1.md). All tests use
generated controls. The module continues to refuse authentic aggregate scoring;
no source data, source labels, author model, candidate model or waveform converter
is supplied or run here. Complete native identity/case assembly, physical units,
timing, annotation semantics, calibrated source-only comparators and protected
participant delivery remain unresolved. Unique series IDs alone authenticate none
of those requirements. This is a software correction, not scientific qualification.

Scientific scope comes from the preserved registration's `primary_target` and
the current `understanding.v1.json`: agreement with expert mouse ABR threshold
annotations, equal weighting of animals, and all recorded stimuli. Historical
source preparation and source-only reasoning are preserved separately. Registry,
current contract and generated catalog adoption of this version require integration;
this task-local component does not rewrite them.
