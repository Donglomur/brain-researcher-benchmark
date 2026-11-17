# NEURAL-077 — Visual oddball target detection from EEG

For every supplied development trial, predict the probability that its stimulus was the block's target. Train using six other people and assess the two complete development people: 200 trials each. The task uses historical ERP CORE data and is already exposed during reference construction; it is not an unseen final evaluation.

`assets.json` points to existing files without copying recordings. Public training cases provide opaque trial IDs, binary training labels, fixed features and sanitized 33-channel raw epochs. Public development files provide the same observations without labels. Use only these public references. Original continuous recordings, event tables, SET headers, source event identities, target/block letter, response codes, private targets and operator receipts are not candidate inputs.

Each raw epoch contains 1024 float32 samples per channel in native EEGLAB amplitude units. Its offsets are −256 through 767 at 1024 Hz, relative to the released event marker; zero additional monitor-delay correction is applied. Do not interpret these as exact physical P3 latency or pre-response observations. The 0–750 ms observation may contain button-related, ocular and other activity. Features and channel ordering are documented in the public packets and fixed method. Past-history features contain only pooled event occurrence timing, never correctness or the current response.

Submit one NPZ with **exactly two arrays**:

- `trial_ids`: all 400 public development IDs, each exactly once, as a Unicode vector. Any row order is accepted.
- `target_probability`: matching float32/float64 probabilities in `[0,1]`.

No candidate code is executed by the scorer. Files are capped at 1 MiB, with bounded ZIP/NPY header validation and no pickle, linked files, duplicate/extra members, missing cases, nonfinite values or incomplete IDs. Both cases validate before private targets are loaded.

Primary output is the equal-person mean of balanced accuracy, using `p≥0.5` for target. Secondary output is equal-person mean natural log loss, with declared metric-only clipping to `[1e−15,1−1e−15]`. Submitted probabilities remain unchanged. Scores include each person, confusion counts and signed comparisons against all six fixed references. Positive log-loss differences are worse. **There is no scientific pass threshold.**

The fixed EEG reference improved balanced accuracy over prevalence but worsened log loss. Ocular, gross-amplitude, history and EEG+history comparisons remain included. These are authored development comparators, not published SOTA. Two assessed people do not support a population confidence interval; accuracy alone does not establish a P3 mechanism, motor-independent cognition or native LLM understanding.

After runtime qualification, the common command will be `python3 tools/neurobench.py score NEURAL-077 --submission candidate.npz --output fresh-result.json`. Source preparation alone does not register this package as verified. Admission remains limited to local submission scoring; full agent experiments and research/submission qualification are separate gates.
