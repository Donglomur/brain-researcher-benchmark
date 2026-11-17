# Input and output files

The candidate sees exactly:
- `/input/INPUT.json`: the source-input schema and its original-input provenance.
- `/input/values.f64`: 11,665,920 bytes, exactly 1,458,240 little-endian binary64 values.
- `/task/TASK.md`, this file, and the same task contract in both arms.
- The same paper material in both production arms, once separately admitted for private delivery.
- In B only, the two selected original MATLAB source files under `/task/released-code/`. The construction fixture uses explicitly invented stand-ins and does not claim original-source delivery.

The six-axis C-order shape is `[4,62,2,7,28,15]`: condition, channel, window, frequency, time, stored position; the last index changes fastest. Conditions are `NT.pin.all`, `NT.pout.all`, `T.pin.all`, `T.pout.all`, in that order. Window index 0 uses source time indices 53–80 inclusive; window index 1 uses 119–146. Frequencies use source indices 8–14. All indices are zero based. Channel labels and original time/frequency coordinates accompany the source manifest. Stored positions 0–14 are never reordered or omitted.

NaN bit patterns are preserved from the source projection, but their numerical meaning is missingness. Do not treat NaN payload bits as labels or answers. The input contains raw stored dB operands, including all 15 entries in every group; it contains no precomputed group means, contributor counts, map categories, interval bounds, scores or hidden reference identities.

The output stream has no header: first 248 little-endian binary64 values, then 248 flags. Maps are NT.delay1, NT.delay2, T.delay1, T.delay2, each followed by its 62 channels. The flags are exactly 0 or 1 and agree with finite versus NaN values. All bytes must be emitted before process exit. Diagnostics go to stderr. Both stderr and execution failures remain owner-private. The candidate receives no target-dependent acceptance status, scores or errors after closure; any separately exposed receipt acknowledges ingestion only.

