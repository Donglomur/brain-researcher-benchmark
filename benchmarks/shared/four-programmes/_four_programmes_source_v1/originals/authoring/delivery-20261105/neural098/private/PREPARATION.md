# Future exact-source preparation and reference

No scientific run or source recording has been used for this package. The official source and experiment description establish field expectations, not actual local schema compatibility. Source access remains unresolved. No sample download is attempted; the advertised MEG sample alone is approximately 28–29 GB and does not establish this full 33-person cohort.

`source-plan.schema.json` describes an operator-owned source plan containing all 33 declared participants. Each participant must supply the original V1 task-dur retained-epoch FIF path, exact bytes and SHA256; an authenticated event-bindings JSON path/SHA256; and actual preprocessing provenance. FIF files are immutable operator-controlled inputs capped at 2 GB each. Preparation verifies their streaming hashes before and after the MNE read and detects ordinary source changes. This is not a hostile concurrent-filesystem sandbox: source ownership/immutability is external. No epochs or raw-event bindings are supplied, and the 2 GB per-file cap has not been demonstrated compatible with the real cohort.

Each event binding joins **every retained `epochs.selection` entry**, including records excluded later, to one original raw run/onset and explicit `epoch_event_sample` equal to `epochs.events[pos,0]`. It also binds the stimulus trigger and actual offset, next-onset and complete button sample list. `sfreq` in this binding is the **raw-event clock**. It may differ from `epochs.info['sfreq']`; conversion must not assume equality after concatenation/resampling. An operator must authenticate the original event files and the exact raw-to-concatenated/resampled epoch mapping independently. The adapter checks the supplied joins; it does not establish that an invented binding is true. Implementing/validating that actual source-to-binding exporter remains a data blocker. Do not guess whether a particular 96/97 marker is the physical offset from its name alone.

P04 source names `Response_time(s)` but assigns a raw sample difference without dividing by sampling rate. This recipe never consumes that field. It uses exact boolean `Response` and independently clocked raw button events. P07 concatenates metadata without adding a run/miniblock column; this package does not fabricate those fields from row order. `Stim_trigger`, Category, Orientation, Duration and Task_relevance are checked against the declared vocabularies. Actual retained event stimulus code must also match metadata.

Future deterministic preparation (no fitting/scoring) is:

```
python private/prepare.py --source-plan /operator/plan.json --source-plan-sha256 SHA256 --output /fresh/packet
```

It requires all six fixed good magnetometers, validates actual epoch time samples, computes baseline-subtracted window means and preserves all supported category/duration/relevance/orientation strata in the fixed cohort. It excludes response/next-stimulus-censored trials without examining decoding outcomes, and fails the panel if any required support is absent. It does not resample, smooth, filter, rerun ICA or fit a model. It writes `features.npy` (little-endian float64, trials ×5×6), `packet.json` (complete observed experimental rows plus the exact feature SHA256) and a source/preparation record. Only the deliberately unavailable duration/window combinations contain NaN. Actual derived hashes cannot be specified before authentic preparation.

Inputs are public **observed analysis data** for this investigation, including labels. The independent computed report is private. A future fixed reference build is a separate scientific execution, not construction:

```
python private/reference_program.py --packet /packet/packet.json --packet-sha256 SHA256 --output /operator/independent-reference.json
```

Its output must be independently reproduced and bound to exact source, data, protocol and environment before using the verifier. No such output exists here. Supplied source code does not justify marking reference execution complete. The portable verifier accepts a fresh output path and explicit reference hash:

```
python private/score.py --submission /submission/analysis.json --reference /operator/independent-reference.json --reference-sha256 SHA256 --output /fresh/grade.json
```

The first command is deterministic data construction; the latter two perform scientific reference computation or scoring and remain unexecuted. Future operator reference-read failures return a null primary result, distinct from malformed candidate submissions. No graded feedback is authorized for tuning this fixed definition.

After authentic packet preparation, `private/stage_view.py --view A|B --packet /packet/packet.json --packet-sha256 SHA256 --output /fresh/view` copies only the selected pinned public files and exact captured observed packet/feature bytes. The private benchmark reference, scorer, event-source mappings, preparation records and targets are excluded from both. B includes original author-source material; A does not. Fresh process/network/filesystem isolation and A/B exposure control remain external, not attested by a copy operation.
