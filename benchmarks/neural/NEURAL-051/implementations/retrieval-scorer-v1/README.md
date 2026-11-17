# NEURAL-051 portable image-retrieval scorer

This component restores the numerical evaluator missing from the public task directory and repairs paired target-identity validation. It accepts the original seven-file, six-panel score format: three people × V1/IT, each with 1,540 unique query images and 3,700 candidates. It uses no authentic observations or labels bundled in this package.

The original target-free scorer, protocol, bounded file reader and score packager are preserved byte for byte under `legacy/`, with pins in `SOURCE_PINS.json`. The successor `scorer.py` uses the original constants and captured-file reader, preserves exact random-tie Top1/MRR semantics, adds the current contract's Top5 diagnostic, and strengthens private-map checks. It requires paired V1/IT query IDs to have identical target-image indices and native trial groups. It also requires 720 candidate concepts (620 with five images, 100 with six), distinct native trial membership, and 1,440 singleton plus 100 two-presentation query groups per panel. A contradictory trusted mapping is an operator error, not participant failure.

## Run

Use an existing Python environment with NumPy (the original source selected NumPy 2.2.6). No installation, model execution or scientific run is supplied here.

```sh
python scorer.py \
  --submission /operator/completed-scores \
  --roster /operator/public-roster.json --roster-sha256 PUBLIC_FILE_SHA256 \
  --design /operator/protected-design.json --design-sha256 PRIVATE_FILE_SHA256 \
  --output /operator/fresh-score.json
```

Paths and pins are evaluator-selected operands. `--roster-sha256` binds exact file bytes; the submission's `roster_sha256` is the original canonical-JSON digest, so the two digest types must not be confused. The result is create-only. Exit 0 means scored, 1 invalid submission, 2 invalid trusted inputs. The API `evaluate(directory, manifest, roster, private_loader)` allows an existing trusted evaluator to supply the protected mapping only after all six score arrays pass admission. The in-memory `grade_arrays` API is for trusted callers that already hold targets; it is not the deferred-access entry point.

The submission directory contains exactly `submission.json` and `sub-01_V1.npy`, `sub-01_IT.npy`, `sub-02_V1.npy`, `sub-02_IT.npy`, `sub-03_V1.npy`, `sub-03_IT.npy`. NPY v1/v2, C order, float32/64, exact shape, exact payload length and finite values are mandatory. Missing panels, reordered roster IDs, changed hashes and trailing bytes fail admission. The preserved `legacy/public/package_scores.py` builds the unchanged manifest for already-written matrices; final admission remains the scorer's responsibility.

## Endpoint and biological units

For a target tied with `t` candidates and `a` candidates strictly above it, expected Top1 is `1/t` when `a=0`, otherwise zero. Expected Top5 is `min(t, max(0, 5-a))/t`; MRR averages `1/r` over ranks `a+1` through `a+t`. Constant scores are a valid no-information control, not a perfect prediction from deterministic target-favoring tie breaking. Equality is exact score equality.

Each query image receives one vote, including images represented by a mean of two presentations. The current `primary` reports V1 and IT separately, each equally averaging the three people. It does not silently introduce a global ROI average. Per-person Top1, Top5 and MRR, same-concept ranks, singleton/repeat summaries, paired person-specific IT−V1 differences and the mean Top1 difference are retained. `historical_primary` separately preserves the original package's IT-only expected Top1 endpoint. Do not treat six dependent ROI panels, 9,240 rows or repeated presentations as additional independent people.

## Scope and remaining limits

This is numerical source recovery and software repair. It does not prepare or authenticate neural arrays, source trial-response joins, ROI masks, candidate JPEGs or private targets. It does not run the old adapter, create process-closure evidence, qualify candidate isolation, or authorize private historical target access. Keep the evaluator and protected operands outside participant access; hashes do not establish observer authority or source correctness. The existing enclosing runtime must establish completion and isolation before invoking this component.

The score format alone cannot prove whether candidate observations were JPEG-RGB-1, original PNG, direct observation, viewer access, tool-assisted investigation or a frozen program. Attach a separately authenticated observation/mode record to any actual result. The historical JPEG-RGB-1 scope is prospective retrieval from released processed betas, with public source labels and three measured people. It is not original-PNG parity, population generalization, native direct interpretation or a reproduced paper identification score. Canonical task, historical definitions and registered runtime remain unchanged; integration enrollment is a separate owner action.

`test_scorer.py` contains generated software controls, including a complete six-file 9,240-row artifact path and independent tie-permutation calculations. Generated inputs are not scientific data and cannot establish performance. Test outcomes and costs belong in the external frozen handoff, not benchmark readiness flags.
