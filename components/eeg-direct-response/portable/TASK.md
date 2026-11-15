# EEG target probability from complete numerical epochs

This is the existing waveform condition of NEURAL-077. Predict whether the current epoch belongs to a target stimulus. There are 400 queries from two exposed development participants, 200 each. This is one benchmark condition, not 400 benchmarks.

The model's entire task input is the unchanged prompt.txt with the exact four demonstrations and one current query substituted. Start a fresh inference context for every query. Do not append this operator document, other queries, original filenames, source event tables, full-training arrays, private labels, previous responses, scores or condition metadata. Do not silently add a numerical class prior: the original prompt explains that the four demonstrations are balanced and supplies no full-training prevalence.

Each query contains the complete 1024 samples of Cz and Pz at 1024 Hz, offsets −256 through 767 relative to the released marker. These are processed epochs: P9/P10 rereferencing and a first 256-sample baseline correction have already been applied. Preserve every sample and its exact supplied decimal serialization. Do not filter, round, resample, crop, normalize, reject epochs or omit a context that does not fit. Native stored amplitude units and physical display timing remain imperfectly characterized; post-marker samples may contain motor or ocular activity.

Return exactly one JSON object with trial_id equal to the current opaque ID and target_probability a finite number from 0 through 1. Maximum 4096 UTF-8 bytes; no booleans, duplicate fields, extra keys or prose. response_schema.json describes the shape; the unchanged response_contract.py adds strict scalar and whole-panel checks.

The evaluation requires all 400 responses. Legacy waveform primary is equal-participant balanced accuracy at the fixed 0.5 threshold; natural log loss is secondary. A complete failure inventory is required for an incomplete collection, but no partial panel is a completed benchmark result. There is no scientific pass threshold.

No tools, code execution, retrieval, files or retained memory from other queries are allowed in this condition. These instructions do not enforce that restriction. The separately admitted model transport must disable those capabilities, preserve fresh contexts and complete raw responses, and account for every attempted query. This package neither supplies nor authorizes that transport.

The assessed people and their outcomes were exposed during benchmark development. Success would be evidence about this representation and panel, not raw continuous-voltage understanding, an unseen-population result or a P3-specific mechanism.
