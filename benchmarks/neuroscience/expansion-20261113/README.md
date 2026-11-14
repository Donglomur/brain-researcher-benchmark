# Five neuroscience benchmark construction drafts

This package describes five newly registered drafts: four paper-reproduction/improvement tasks and one neural-data task. The programme now contains **205 registered contracts/drafts: 104 paper and 101 neural. Zero are scientifically qualified or submission-ready.** Registration, source review and engineering checks do not establish a working scientific benchmark.

| Task | Track | Scoped question |
|---|---|---|
| [Horrocks temporal encoding](tasks/horrocks-temporal-encoding.json) | Paper | Reproduce complete five-mouse visual-speed decoding and test chronological robustness. |
| [NIDER meta-analysis](tasks/nider-meta-analysis.json) | Paper | Reproduce three study-summary meta-analyses and evaluate held-cohort predictive calibration. |
| [Sosa reward-relative decoding](tasks/sosa-reward-relative-decoding.json) | Paper | Reproduce hippocampal remapping/decoding and test post-relocation neural decoding under matched calibration. |
| [PFC activity map](tasks/pfc-activity-map.json) | Paper | Rebuild Figure 4's brain-wide activity-map fit and predict held-animal PFC feature distributions. |
| [Helsinki neonatal EEG](tasks/helsinki-neonatal-eeg.json) | Neural data | Compare case investigation and a frozen predictor on infant-grouped, three-expert seizure evidence. |

Paper tasks compare paper plus admitted data with the same materials plus qualified official code. Reproduction preserves the scoped paper method; improvement uses an explicitly separate proposed endpoint and matched baselines. Neural-data conditions compare tool-assisted case investigation with a predictor written before evaluation. Conditions, folds, windows, expert labels and ablations stay within their task; they do not inflate the count.

Each card records public paper/code/data provenance, experimental units, permitted inputs, metrics, leakage boundaries, rights and unresolved construction gates. Data families may overlap or depend on multiple acquisition records. These five tasks are not a claim of five independent datasets. The published source labels and paper results also make contamination a real limitation.

Helsinki uses the distinct `helsinki_full_timestamp_quality_flags_v1` amendment for source construction only. Its original V3 remains unqualified. Quality flags are not proven missingness: all 79 infants and fixed timestamps remain in the primary soft-vote Brier denominator, and matched signal/mask/noise/amplitude/prior controls are required. Fresh per-case context/process isolation must prevent future-signal leakage across overlapping windows; host enforcement remains a gate.

The JSON schema is a descriptive draft format, not an executable runner or a claim of baseline reproduction. Source pins identify the exact construction records used for this projection. Public URLs and reported archive checksums are provenance; they do not certify local data authentication, license sufficiency or successful execution. No data, target values, raw source excerpts, model credentials or fitted outputs are included.

Before scientific qualification, each task needs authentic input and rights checks, complete grouped splits, protected evaluation, competent reference reproduction, frozen tolerances or predictive scoring, matched resource accounting, meaningful negative controls and independently reviewed end-to-end evidence. Runtime/storage figures are metadata or documented requirements, not measurements from this package.
