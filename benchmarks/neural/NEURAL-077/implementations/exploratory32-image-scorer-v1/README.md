# Exploratory32-case image-pilot subset scorer

This separate operator-side scorer admits paired direct and programme prediction files for exactly32 anonymous cases (`case-01` through `case-32`). It does not execute a participant, render images or change the existing full6,400-case evaluator. Source controls use invented labels and predictions; they are not benchmark performance.

The endpoint is target versus standard stimulus **event identity**, not physiological P3 presence. Each selected query must come from a different person. Both arms use identical fixed query pixels and the same four labelled demonstrations. The programme must be frozen from demos only before query access. The operator retains evidence for that timing, first responses and available tool traces. Hashes alone do not establish honest capture, instruction compliance or native isolation.

`score_subset.py` provides a strict `--admit-only` mode and a separately authorized scoring mode. Each arm file has schema `erp-exploratory-predictions/v1`, `arm`, `protocol_sha256` and exactly32 records with `trial_id`, `status`, `target_probability` and `first_response`. A successful `ok` record must preserve the first exact two-key response JSON; its finite probability must agree with the canonical value. Explicit abstain/invalid/error/not_attempted records carry null probability. Missing, extra or duplicate files/IDs, malformed records and pin mismatches are rejected before any gold callback.

Supply externally committed protocol and prediction-commit SHA256 values. The commit binds two files (`direct.json`, `programme.json`) in an otherwise empty prediction directory plus the already-frozen programme source. Raw logs belong elsewhere. The later gold binding supplies configurable paths for the official `full32-paired-benchmark-v1` consumer/evaluator and original public/private material. The source bodies and material must match the constants in this scorer. No host paths, packet, protocol, predictions, images, selection mapping or gold binding are distributed here.

After both arms pass, the optional original-data adapter authenticates the public PacketSession index and uses the unchanged official private parser. This trusted operator step reads the full private cohort internally and returns only the32 selected labels; it does not call a query accessor or read query shards. Full private access requires a separate explicit scoring selection. The generated suite does not qualify that original gold path.

Balanced accuracy uses threshold `p >= 0.5`; explicit failures count incorrect in their true-class denominator. Coverage and failure counts remain visible. The primary contrast is direct minus programme balanced accuracy. Uncertainty uses10,000 paired resamples stratified by observed event class, shared across both arms, NumPy PCG64 seed20261122 and95% percentile intervals with linear quantiles. Absolute-arm intervals are secondary and unadjusted. One-class support makes BA/intervals unavailable. This is a finite exploratory32-person single-query subset, not the registered full-cohort participant-macro endpoint or a population/SOTA claim.

Generated controls require Python3.11.6 and NumPy1.26.3:

```sh
python -I -B controls/test_score_subset.py
```

The16 methods cover admission ordering, raw-response fidelity, explicit failure accounting, imbalanced classes, paired resampling, orientation, deterministic seed/linear quantiles, single-class handling and file cleanup. Fixtures are generated and deleted; cumulative writes remain counted. Local source qualification passed16/16 once. It establishes neither actual participant performance nor enforced tool restrictions.
