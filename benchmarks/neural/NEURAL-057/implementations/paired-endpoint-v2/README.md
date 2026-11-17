# Paired endpoint evidence for exact Bernoulli losses

The registered scorer retains unclipped infinite native log losses, but its paired summaries discard the whole mode if even one person's loss is infinite. This loses finite contributions from the other people and conflates defined `finite − infinity` / `infinity − finite` contrasts with undefined `infinity − infinity`.

`endpoints.py` derives the complete paired evidence from an operator-owned `neural057-complete-report-v1` after the original campaign has closed all 160 cells and 320 phases. It retains all ten people, every supported concept, every person–concept contribution and the exact unsupported query IDs. Defined contrasts have signed infinity tags; undefined contrasts have an explicit reason. No finite subset becomes a replacement endpoint. Descriptive SEM and t9 intervals remain unavailable whenever a required paired loss is nonfinite.

The primary lower-is-better LATE loss, 53 independent category probabilities, equal-concept/equal-person weighting, F/I modes, four panels and independent BASE/LATE comparisons are preserved. A participant can worsen its own BASE without changing its primary loss or independent comparison. The original registered source and its hashes remain unchanged.

## Operator use

Run after the complete original report is produced, keeping both files in the protected operator output directory:

```sh
python3 endpoints.py --report /operator/run/REPORT.json --output /operator/run/PAIRED_ENDPOINTS.json
```

The output must be new; the command never overwrites the report. It binds the exact source-report bytes by SHA-256 and emits JSON without nonfinite number tokens. The converter checks both complete 80-cell collections, units, denominators, support equality and consistency of each native loss with its concept contributions. This is evidence postprocessing, not a replacement for source authentication, the original phase barrier or execution authority. The output preserves operator-owned opaque query IDs and concept identities; do not put it in public Git or participant inputs.

## Qualification limits

Only generated software controls have been specified here. No authentic taxonomy, EEG, image, target, prediction or model is included. No reference fitting or candidate trial is authorized by this module. The current taxonomy/image/coordinate joins, runtime qualifications and competent full references remain unresolved. Direct observation, viewer interpretation and per-query tool-assisted investigation remain undelivered; this programme endpoint cannot establish those abilities. Public-corpus exposure, released session MVNN and the 200 ms presentation overlap remain limitations.

The source task is prospective category-membership prediction, not reproduction of an original paper endpoint. Source references are inherited, not freshly fetched: Gifford et al., DOI `10.1016/j.neuroimage.2022.119754`, and THINGSplus, DOI `10.3758/s13428-023-02110-8`. Exact local input source pins and the implementation/test qualification receipt are recorded in `SOURCE_PINS.json` and `VALIDATION.json`.
