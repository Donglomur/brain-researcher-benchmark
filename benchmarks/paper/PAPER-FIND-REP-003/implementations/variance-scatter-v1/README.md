# Figure 5 target-variance / VE companion

This operator-only component derives the missing Figure5 supplement2 E/F scatter from the same complete original-panel input format used by `source-panel-v1/scorer.py`. It retains all12000 points: five mice, paired M1/S1 sessions,50 original fits and24 joints. It adds no fit, new endpoint, pooled scalar or scientific win rule.

The original [plotVEvsVar.m](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/main/fig5/plots/plotVEvsVar.m) calculates sample target variance over the concatenated held-out trial timepoints and pairs it with each fit's joint VE. Despite a comment mentioning a median, the executed loops retain every fit/joint scatter point. [fig5_supp2.m](https://github.com/kaufmanlab/GSK26-public/blob/815b610b3beddfed5a3abf611d3a465ab9e4ce5c/main/fig5/fig5_supp2.m) selects the original `output` branch separately for M1 and S1. These two pinned-revision pages were inspected through the web tool; no new authenticated raw source capture is claimed.

`scatter.py` authenticates the existing scorer bytes before loading them. It calls that scorer to enforce the complete original ten-session support, source folds and ordering, 51timepoints/24ordered joints, source VE, and saved-author-VE agreement. It then independently calculates variance with divisor n-1. The divisor cannot be dropped merely because it cancels in a VE ratio. Concatenating trials before variance retains between-trial target variability; averaging per-trial variances gives a different quantity.

Each private report keeps the source mouse/session/area, joint identity and proximal/distal membership, model number, held-out timepoint count, target variance in degrees squared, author VE, candidate VE and their difference. Negative VE remains. Point ordering follows session, joint, then original model. No target vectors, original trial IDs or predictions are added to this companion report, but derived variances remain protected outcome information and the report must stay private.

## Operator use

Pass the exact reference/candidate schemas documented by the existing source-panel component. Both SHA256 values must already be frozen independently; the program checks bytes but cannot establish a freeze chronology or scientific authenticity.

```sh
python3 -I -B scatter.py \
  --reference /private/reference.json --reference-sha256 RECORDED_REFERENCE_SHA256 \
  --candidate /private/candidate.json --candidate-sha256 RECORDED_CANDIDATE_SHA256 \
  --output /private/new-scatter.json
```

Output creation is exclusive. Authentic complete input/report sizes must be admitted under the operator's separate resource protocol before execution. This component does not provide process isolation, participant delivery or a storage/compute guarantee.

## Validation and limits

Seven generated controls passed once through the shared test pool. They exercise the complete12000-point geometry, n-1 sample variance, concatenation across trial boundaries, missing/misaligned original support, invalid targets, source dependency tampering, candidate commitment and existing-output refusal. No neuroscience arrays, original author output, MATLAB, candidate model or scientific score was run.

The original input manifests, original RNG/fold provenance, qualified author reference, comparator selection, native runtime and numerical reproduction tolerance remain unresolved. Constant targets continue to fail under the existing scorer; no paper-specific zero-variance rule is invented. Other original companion branches and trajectory/posture derivations remain separate. This component is a partial implementation of the existing mandatory granular-evidence requirement, not a completed benchmark or paper-result reproduction. Scientific qualification stays false and `paper_win` stays null.

Suggested CI component command: `python3 -I -B -m unittest discover -s benchmarks/paper/PAPER-FIND-REP-003/implementations/variance-scatter-v1/tests -p test_scatter.py -v`. The sole integrator must enroll this new component and command in the existing ownership/test inventory; this private package does not change central registry files.
