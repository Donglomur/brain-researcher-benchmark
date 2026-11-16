# iSTTC empirical preparation and reproduction diagnostics

This standalone, standard-library Python component supports the existing `PAPER-paper-method-add-004` investigation. It prepares prospective trial windows, reduces complete four-method fit tables, and compares reproduction outputs. It is **not a new benchmark, an improvement leaderboard, a native estimator, or a complete Figure 7 reproduction**.

The production source is unchanged from its reviewed version. It requires **5,775 unique units across 26 mice**, and all **23,100 unit-by-method coordinates**, including explicit fit failures. No authentic roster, spike data, estimator output, protected reference, or answer is distributed.

## Portable commands

Use Python 3.11 from any directory. Set `ISTTC_COMPONENT` to this directory's absolute path; the examples below assume a checkout-root working directory.

```sh
ISTTC_COMPONENT="$(pwd -P)/components/isttc-empirical-diagnostics"
python3.11 -I -S -B "$ISTTC_COMPONENT/empirical_bridge.py" --help
python3.11 -I -S -B "$ISTTC_COMPONENT/test_public_package.py"
```

The packaging test uses generated JSON fixtures in a temporary relocated directory, including the complete required dimensions. It does not download or read scientific data. The retained `test_generated.py` and `test_arithmetic.py` are development regression sources; this packaging phase does not claim to have replayed their historical suites.

The following are templates for future operator-owned, independently admitted inputs. They are not a selection to execute on authentic data:

```sh
python3.11 -I -S -B "$ISTTC_COMPONENT/empirical_bridge.py" windows \
  --cohort /ABSOLUTE/COHORT.json --seed SELECTED_UINT64 \
  --output /ABSOLUTE/FRESH_WINDOWS.jsonl

python3.11 -I -S -B "$ISTTC_COMPONENT/empirical_bridge.py" reduce \
  --cohort /ABSOLUTE/COHORT.json --estimates /ABSOLUTE/FITS.json \
  --output /ABSOLUTE/FRESH_REDUCTION.jsonl

python3.11 -I -S -B "$ISTTC_COMPONENT/empirical_bridge.py" compare \
  --cohort /ABSOLUTE/COHORT.json --estimates /ABSOLUTE/CANDIDATE.json \
  --reference /ABSOLUTE/PROTECTED_REFERENCE.json \
  --output /ABSOLUTE/FRESH_COMPARISON.jsonl
```

Every named output must be absent. Input files may be at most16 MiB each; output logical bytes are capped at64 MiB. These limits are not hard memory, CPU, wall-time, sandbox, provenance or durability guarantees. An authentic operation needs a separately qualified external owner and complete terminal/custody handling.

`windows` emits one JSON line per unit, each with40 one-second windows from a30-minute signal represented at30 kHz. Starts are uniform integers from0 through signal_ticks-trial_ticks inclusive; windows are half-open and repeats/overlap are retained. Seed and cohort order define a **prospective** draw. They do not recover the historical random state. This command prepares window coordinates; it does not load spikes or fit estimators.

`reduce` and `compare` each emit one full JSON report line. Reduction preserves every original unit and its missingness/exclusion diagnostics. A window-validation failure can leave a zero-byte output, and a streaming/publication failure may leave a partial or complete-looking file. Output existence is never proof of success. The component promises no structured failure JSON, fsync/atomic publication protocol, or execution receipt. The operator must retain the process outcome and verify complete artifacts.

## Inputs and scientific interpretation

See [cohort.schema.json](cohort.schema.json), [estimates.schema.json](estimates.schema.json), [TASK_AND_PROVENANCE.json](TASK_AND_PROVENANCE.json), and [COVARIATE_MAPPING.json](COVARIATE_MAPPING.json). The JSON schemas document field-level requirements; the production code also enforces relational cardinality, membership, uniqueness and finite arithmetic. Schema validation alone cannot authenticate original biological identities or QC.

The cohort's `source_sha256` is a required syntactic declaration. This component does not retrieve or authenticate the named original source from that string. The operator must establish the actual5,775-ID/mouse/session/eight-area roster and literal paper QC, including the unresolved paper amplitude-cutoff0.01 versus retained loader-default0.1 discrepancy. No count is a substitute for that evidence. `fr_hz` means `lv_df.pkl.fr_hz_spont_30min`, not a broader Allen session firing-rate field.

All four fit rows are mandatory for every unit: `acf_full`, `isttc_full`, `pearsonr_trial_avg`, and `sttc_trial_concat`. A missing tau or R-squared requires a nonempty failure reason; do not omit failed coordinates. Fields accept finite numbers or declared nulls as documented. The code requires representable millisecond conversion and summary arithmetic.

Reduction first excludes the union of missing fit/covariate values across all four methods, then negative R-squared values; zero R-squared remains. The reported historical3,053 complete cases are an observation, never a forced selection target. Trial Pearson R pairs with full-recording ACF, and trial concatenated iSTTC pairs with full-recording iSTTC. Pseudo-REE is100*abs(trial-full)/full; tau_ms is50*tau_bins. Full-recording estimates are method-specific pseudo references, not biological truth.

Nonpositive references or undefined arithmetic preserve the complete-case denominator and suppress affected median/percentage summaries. Thresholds are inclusive. Any candidate/reference availability mismatch disables **all** comparable MAE/max summaries; exact mismatches and expected/observed support remain visible. Quantities remain separate, with no invented pass tolerance or combined scalar.

Candidate and reference descriptive reductions may have different complete-case masks. Their medians and threshold percentages must not be compared as an improvement leaderboard. `compare` implements support-gated reproduction diagnostics only; `scientific_pass` remains null.

## What remains outside this package

Authentic cohort/QC reconciliation, full-recording extraction, source-derived covariates, frozen shared windows and independently qualified four-estimator fit provenance remain required. The inferential Figure7C GLMs/p-values, Figure7B/D–G, supplementary analyses, and the full paper are not implemented here. The existing100,000-simulation route is separate and unchanged.

A future paper+data versus paper+data+code experiment needs identical cohort/windows/failure rules and matched budgets, with independently established access/provenance. A constrained-data improvement study needs a separate contract that withholds full-recording pseudo references from the estimator. Neither experiment is run or qualified by this component.

Source files are pinned in [SOURCE.json](SOURCE.json). This component is distributed under GNU GPL version3; see [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md). Data and publication rights remain separate.
