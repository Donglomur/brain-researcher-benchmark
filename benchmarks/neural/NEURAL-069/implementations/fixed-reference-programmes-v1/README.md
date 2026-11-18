# Fixed reference programmes for NEURAL-069

Two self-contained reference programmes now fit the existing candidate entrypoint: `training_mean_program.py` and `layer4_ridge_program.py`. The original prepared `baseline.py` requires a `--method` argument and a nonexistent output directory. The unchanged transport instead supplies only `--public-root` and `--output-dir`, with an existing output volume. These programmes freeze one method in the committed source and accept that existing empty volume. They do not modify the transport, task, scorer or original preparation.

Each source is under the existing131072-byte programme limit. The reference is selected by committing the corresponding complete source file; there is no runtime method selection. A future invocation inside the already-qualified candidate runtime is:

```sh
python -I -B /submission/program.py --public-root /public --output-dir /output
```

This is an interface example, not authority to launch a workload. The existing review, commitment, image, resource, input-lock, closed-producer and separate numerical-grade requirements still apply. `/output` must exist and be empty. Files are created exclusively. The final `submission.json` is attempted only after all80 predictions have been written. Failure before that attempt leaves the existing prediction files without a manifest; an interrupted final write or fsync can leave an invalid/partial manifest. Such an output must fail the unchanged stopped-producer and complete-output admission. No failure record is treated as a completed submission.

## Endpoint and source preservation

Both programmes require the exact prepared public roster SHA256 and byte extent, all ten participants, all eight ROIs, all1000 training videos and102 query videos in their original order, and every native coordinate. They emit all80 ordered prediction matrices plus the final submission. Only declared public training responses and, for ridge, the fixed layer4 feature pair are opened. No private target, category annotation, motion array, model, network or scientific grader is accessed. File traversal rejects symlink leaves/directories; this is a local I/O restriction, not proof of participant OS isolation.

The numerical modules are embedded byte-for-byte from the pinned prepared benchmark reference (`SOURCE.json` records their identities). The mean uses the existing constant-safe training mean. Ridge uses the existing fixed lambda1, unpenalized intercept, training-feature standardization and exact100-dimensional released layer4 PCA features. Training-constant features are ignored in both partitions. There is no new tuning, PCA, feature selection or mathematical readout change. These are prospective benchmark references, not the author's original PCA/OLS reproduction.

The source remains Version B/MNI152 with joint upstream GLMsingle processing, query-dependent availability masks and separately standardized query covariates in the released PCA features. Neither reference makes this an inductive unseen-video holdout. Published query exposure remains. Static-frame and motion/time comparator qualification is still missing; neither programme can establish temporal understanding by itself.

Predictions are scored by the unchanged current response scorer. Its current primary is participant-macro/ROI-macro coordinate Pearson; its legacy family-weighted score remains a separate companion. The old prepared task prose's family weighting is not silently adopted. Programmes contain no score arithmetic and introduce no passing threshold. Native/direct interpretation, scientific difficulty, improvement, SOTA and benchmark readiness remain unestablished.

## Validation

```sh
python -I -B test_programs.py -q
```

Fifteen generated controls passed in one invocation. They test the exact transport CLI/existing-volume interface; no runtime method override; frozen-source and roster rejection; complete80-case routing/native shapes and final-manifest ordering; separate original mean/ridge arithmetic; fixed training statistics; refusal of partial/reordered support; pin-before-parse; private-path and symlink refusal; nonfinite outputs; exclusive writes; and failure without a final manifest. The full-panel orchestration checks stub array capture/arithmetic and retain output bytes in memory; separate numerical controls exercise the unchanged numerical functions on generated matrices. This is not an authentic80-array run. No original neural/feature/target array was read and no model programme or Docker workload ran.

The shared test-pool wrapper reported0.349411seconds, exit0, and86474752bytes maximum child RSS (not a simultaneous process-tree memory bound). The local generated test environment does not qualify the production Python3.12.8/NumPy2.2.6 image. These tests must be enrolled as a new component command when the sole integrator imports this additive package; no existing CI or runtime selection is changed here.
