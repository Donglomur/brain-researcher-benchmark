# Full-source EEG numeric preparation cores

These standard-library components prepare the numerical policy and streaming logic for the complete original DOSE-I source. **They have been tested on generated inputs only.** They do not include an admitted native execution driver, source acquisition, resource controller, output finalization transaction or finished benchmark packets.

`numeric_policy.py` interprets one raw EEG cell with an explicit ASCII grammar and returns its binary64 representation plus quality bits. Exact decimal comparison determines hardware-range and endpoint flags before binary64 rounding. Missing values, malformed tokens, source nonfinite values, binary64 overflow and nonzero underflow remain distinguishable. Missing/non-numeric/nonfinite/overflow values use a fixed quiet-NaN bit pattern and an invalid flag, never a fabricated zero or 300. Source numeric 300 remains 300 with an out-of-range flag. Endpoint usability is a later packet-policy decision.

`numeric_stream.py` projects every original CSV data row into three padding-free little-endian streams: one int64 exact calendar-ordinal millisecond time (8 bytes), two float64 channels (16 bytes), and two uint8 quality bytes (2 bytes). A source row is its stream index. The code preserves duplicate timestamps, signed zero, sparse channel observations and all rows; it never resamples, interpolates, filters or infers a biological person. Full source rows contain clinical annotations, so these streams and reports remain private preparation artifacts until a separately approved participant projection exists.

The stream core checks the exact source header, whole expanded SHA256/CRC/EOF/byte/row count and clock-anomaly count. Every primary annotation row must match its authenticated saved ledger record in logical row, physical line, raw time, recognized time, anomaly flags and all seven annotation fields. Missing, extra or altered annotations refuse completion. It buffers at most 65,536 packed rows and records bounded private invalid-token auditing; the full quality stream retains every row even if token-audit vocabulary overflows.

The current complete census has 70,760,492 source rows. At 26 bytes per row, the proposed complete numerical payload is **1,839,772,792 bytes** before receipts and sidecars. This is a derived storage requirement, not an existing output or a measured native conversion cost. All 171 recordings are required for a complete run; optional peripheral columns absent in two source header variants do not change the two named EEG channels.

`project_member` accepts supplied streams, expected source pins, authenticated annotation rows and capped output sinks. Its return status is `core_completed_not_finalized`. The caller must authenticate the whole release and saved inputs; enforce cumulative CPU/wall/RAM/read/write limits across workers and failures; preserve partial writes; verify closed stream sizes/hashes; and commit a final success manifest only after all three projections agree. A file's existence or this core's return alone cannot establish an admitted source member. A complete cohort additionally needs all 171 successful final receipts. No ordinary public CLI here can accidentally launch the original-data conversion.

Generated controls cover numeric precision boundaries, underflow/overflow, signed zero, explicit status combinations, exact times and channel order, duplicate clocks, complete source hashes, annotation provenance mismatches, source-row completeness and partial-write refusal. They do not establish numerical validity or performance on original recordings.

```sh
python -I -S -B -m unittest discover -s benchmarks/neural/clinical-dosei-responsiveness/implementations/source-eeg-numeric-v1 -p 'test_numeric_*.py' -v
```

Native EEG packets, source artifact alignment, biological-person grouping, canonical scoring and AI evaluation remain unrun. The component's private source representation does not grant an agent access to future samples or labels. The retrospective marker-relative observation contract and its participant access boundary require a separate reviewed packet producer.
