# Normalized-position spatial-information methods case

RATPLACE-001 keeps its legacy identifier; the supplied recording is mouse M02 CA1, not a rat or spaceflight experiment. This is one fixed-session method/control exercise, not a reproduction of a source-paper estimator or a claim that a predetermined number of place cells exists.

The original NWB and byte-identical internal manifest are under /app/data/ratplace. Public authorities are /app/source_manifest.json, /app/method_contract.json and /app/output_schema.json. The source is DANDI 001695, release 0.260319.2023, asset 1e4d5403-a8cc-4814-a904-7aff57f8cc4d. Authenticate the released bytes before analysis.

## Tracking and its limitations

The position record comes from independently sampled camera tracking aligned using the source acquisition clock. Author processing included low-confidence rejection, PCHIP filling and median filtering; the released finite samples do not certify which positions were directly observed. The source declares centimeters with conversion 0.01, while author example code treats raw positions as centimeters. This unresolved calibration conflict is retained.

The fixed method was amended after header/clock/label inspection and before any spike values or spatial statistics: use raw-axis min–max normalized positions, with no physical distance, speed, running threshold, or inferred maze epoch. The observation window is the supplied first-to-last position clock, [4583.485466666667, 6474.363466666668), not a source-defined maze interval.

A valid dwell piece is a pair of finite XY endpoints with finite strictly increasing timestamps and dt <= 0.1 s, intersected with the observation window. Its position is the original left sample. Never bridge gaps, interpolate further, or extend the final sample. A spike belongs to a valid piece only at its left-inclusive/right-exclusive times. Bounds are behavior-only min/max of valid left positions. Both axes must have positive ranges. Use the 4 x 5 grid and exact bin-edge/flat-index rules in the method JSON; occupied durations use accurate math.fsum in time order.

## Units, information and null

Retain all 110 source units in a ledger, with numeric source-ID ordering and literal decimal strings. Eligibility is exactly CA1, at least 50 spikes assigned to valid dwell pieces, and 0.05 < count/valid_duration < 5 Hz. This is an operational selection, not biological pyramidal-cell classification. Do not force a selected count.

For each eligible unit, calculate the disclosed count/occupancy information in bits/spike. Draw 300 elapsed-window circular offsets with the exact PCG64/SeedSequence schedule. The stream index is the original unit's numeric rank among all 110 units, not its rank among eligible units. Shift all original spikes inside the camera window, then reapply the valid tracking pieces. Preserve zero-count null draws without redrawing. Any such draw makes that unit's null mean, adjusted information and upper-tail p unavailable; raw information remains available. Null offsets are at least 20 s from either endpoint.

Adjusted information is raw minus the null mean, including negative values. The inclusive Monte Carlo tail uses (1 + count(null >= raw))/301, without a numerical tolerance in the decision. This conditional shift comparison is not a universal bias correction or evidence of spatial specificity independent of behavior, temporal structure, or preprocessing.

## Deliverables and authority

Write the five files specified in output_schema.json. Exact original counts, eligibility, masks, clocks, IDs and offsets bind the evidence to the source. Coherent unit/bin/draw permutations are allowed. Safe real storage must satisfy the stated precision; no unconditional six-decimal guarantee applies to occupancy or offset primitives.

Source-close submitted occupancy together with exact submitted counts drives the submission's own information and null replay. Per-unit CSV values are receipts against that replay. Headline means derive from accepted CSV rows, including their allowed independent rounding, not a second hidden scalar answer. Duplicate receipts must satisfy the disclosed propagated linear bound. All-unit metadata records may be reordered by their explicit unit_id; source metadata declarations and integer counts remain exact, while analysis clock/grid values use the occupancy numerical bound.

All unsupported or undefined cases must remain explicit. An empty eligible axis is a completed no_eligible_units outcome with null aggregate means. Any failure_report.json is authoritative failure. Resource-pilot results are never completed production submissions.

