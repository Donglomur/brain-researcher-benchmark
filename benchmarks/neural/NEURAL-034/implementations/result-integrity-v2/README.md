# Complete comparator inspection for NEURAL-034

This successor inspects a completed seven-fold operator result using the existing
140-case, seven-mouse endpoint. The original inspector checks the commitment
chain, fold closure, probabilities and equal-mouse co-primary means, but accepts
finite comparator differences without checking the reference values or their
subtraction. Its output also omits those controls. This version authenticates and
reuses that inspector, then checks the exact six reference metric pairs, their
domains, both metric directions, the score alias and every signed difference.
It returns all seven mouse-level scores and all six comparisons.

Run from the repository root on an already completed operator result:

```sh
python3 -I -S -B benchmarks/neural/NEURAL-034/implementations/result-integrity-v2/check_result.py \
  --output /ABSOLUTE/operator/finished-candidate-result
```

This source depends on the unchanged sibling
`neural034-portable/check_result.py` at SHA-256
`d349dac1455ac045c5437929b47c640db3426da79eae5f7b7738a8dae3ac009c`.
The original grader at
`../registered-runtime/grader.py` (SHA-256
`e48954a3b0e6ab44fbe4ad393b2716a31151bd8c2362e472bc0fef99bee2b5e6`)
defines the preserved subtraction, score alias and directions. Both predecessors
remain unchanged; this addition does not select a new runtime or edit its pins.

Balanced accuracy is higher-is-better and log loss is lower-is-better. Every
difference is **candidate minus reference** for both metrics. Mixed outcomes are
retained without a combined scalar or a scientific success threshold. Each
co-primary score remains the arithmetic mean of the seven mouse-level scores.
The result reports only the existing aggregate reference comparisons: no paired
mouse-level comparator results or uncertainty intervals are reconstructed from
aggregate values.

The inspector uses the exact grade bytes authenticated by the original checker.
It checks consistency of trusted operator records, not authenticity of forged
records. It neither opens targets nor calculates scores from predictions and
labels, and it does not verify that the comparator record is the originally
approved private source. Input provisioning and the protected scorer retain that
responsibility. Keep this output under the study's protected feedback policy.

Generated controls in `test_check_result.py` preserve a counterexample accepted
by the predecessor, check every comparator, reject rehashed inconsistent grades
and retain mixed metric outcomes. They use no authentic neural data, historical
predictions, private targets, Docker, models or native scientific preparation.

Scientific scope is unchanged: context decoding in the selected seven processed
mice from [Zenodo 21780255](https://zenodo.org/records/21780255), associated with
the [source paper](https://doi.org/10.1038/s41593-026-02448-0) and
[author code](https://github.com/rsenne/dCA1_Paper/tree/5be84b4).
ROI/session preprocessing, context/day order, behavior polarity, source exposure
and current runtime qualification remain unresolved. Programme result inspection
does not establish direct-observation, viewer or interactive performance.
